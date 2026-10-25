"""FastAPI router ported from Flask. Preserves URL paths and JSON shapes."""
from __future__ import annotations

import json
import logging
import os
import re as _re
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import desc, or_, and_, func, text, extract
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import *  # noqa: F403,F401
from app.invoice_math import *
from app.log_utils import log_action, document_log_entries, save_uploaded_file
from app.petty_cash import wants_till, till_expenses, till_receipts
from app.period_lock import (
    guard_period, guard_both, body_date, record_date, check_period_editable, is_period_open,
)
from app.document_links import apply_links, resolve_customer, resolve_car
from app.search_suggestions import suggestions_for
from app.inventory_utils import find_inventory_item_by_name as _inv_find_by_name
from app.inventory_transaction_utils import (
    log_inventory_transaction, log_issue_out, log_received, log_adjustment, get_inventory_transactions,
)
from app.repair_order_inventory_utils import (
    deduct_inventory_quantity, process_repair_order_parts,
    handle_repair_order_edit_inventory, restore_inventory_for_deleted_repair_order,
    calculate_inventory_changes, find_inventory_item_by_part_number, find_inventory_item_by_name,
)
from app.payroll import preview as payroll_preview, run_payroll, compute_salary
from app.whatsapp_notifications import whatsapp_notifier

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

#!/usr/bin/env python3
"""
WhatsApp Notifications API Routes
Handles WhatsApp notification management and tracking
"""

from sqlalchemy import desc, func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@router.get('/whatsapp/notifications')
def get_notifications(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all WhatsApp notifications with optional filters"""
    try:
        # Get query parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 50))
        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('type')
        search = request.query_params.get('search')
        
        # Build query
        query = db.query(WhatsAppNotification)
        
        # Apply filters
        if status_filter and status_filter != 'all':
            query = query.filter(WhatsAppNotification.status == status_filter)
        
        if type_filter and type_filter != 'all':
            query = query.filter(WhatsAppNotification.notification_type == type_filter)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    WhatsAppNotification.customer_name.ilike(search_term),
                    WhatsAppNotification.customer_phone.ilike(search_term),
                    WhatsAppNotification.message_content.ilike(search_term)
                )
            )
        
        # Order by most recent first
        query = query.order_by(desc(WhatsAppNotification.created_at))
        
        # Paginate results
        _total = query.count()
        _pages = max(1, (_total + int(per_page) - 1) // int(per_page))
        _items = query.offset((int(page) - 1) * int(per_page)).limit(int(per_page)).all()
        class _Pg:
            pass
        pagination = _Pg()
        pagination.items = _items
        pagination.page = int(page)
        pagination.per_page = int(per_page)
        pagination.total = _total
        pagination.pages = _pages
        pagination.has_next = int(page) < _pages
        pagination.has_prev = int(page) > 1
        
        notifications = [notification.to_dict() for notification in pagination.items]
        
        # Calculate statistics
        stats = calculate_notification_stats(db)
        
        return _json({
            'notifications': notifications,
            'stats': stats,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return _json({'error': 'Failed to fetch notifications'}, 500)

@router.get('/whatsapp/notifications/{notification_id:int}')
def get_notification(notification_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get a specific notification by ID"""
    try:
        notification = db.get(WhatsAppNotification, notification_id)
        
        if not notification:
            return _json({'error': 'Notification not found'}, 404)
        
        return _json(notification.to_dict())
        
    except Exception as e:
        logger.error(f"Error fetching notification {notification_id}: {e}")
        return _json({'error': 'Failed to fetch notification'}, 500)

@router.post('/whatsapp/notifications/{notification_id:int}/resend')
def resend_notification(notification_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Resend a failed notification"""
    try:
        notification = db.get(WhatsAppNotification, notification_id)
        
        if not notification:
            return _json({'error': 'Notification not found'}, 404)
        
        if notification.status != 'failed':
            return _json({'error': 'Only failed notifications can be resent'}, 400)
        
        # Import WhatsApp notifier
        
        # Prepare data for resending
        notification_data = {
            'customer_name': notification.customer_name,
            'customer_phone': notification.customer_phone,
            'id': notification.related_document_id,
            'net_total': 0,  # This will be extracted from the message content if needed
            'type_of': notification.notification_type
        }
        
        # Resend the notification
        result = whatsapp_notifier.send_message(
            notification.customer_phone,
            notification.message_content,
            notification.notification_type
        )
        
        # Update notification record
        if result['success']:
            notification.mark_sent(result.get('message_id'))
            notification.error_message = None
            db.commit()
            
            return _json({
                'message': 'Notification resent successfully',
                'status': 'sent'
            })
        else:
            notification.mark_failed(result.get('error', 'Unknown error'))
            db.commit()
            
            return _json({
                'error': 'Failed to resend notification',
                'details': result.get('error')
            }, 400)
        
    except Exception as e:
        logger.error(f"Error resending notification {notification_id}: {e}")
        return _json({'error': 'Failed to resend notification'}, 500)

@router.get('/whatsapp/stats')
def get_notification_stats(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get notification statistics"""
    try:
        stats = calculate_notification_stats(db)
        return _json(stats)
        
    except Exception as e:
        logger.error(f"Error calculating notification stats: {e}")
        return _json({'error': 'Failed to calculate statistics'}, 500)

def calculate_notification_stats(db: Session):
    """Calculate notification statistics"""
    try:
        # Total notifications
        total_notifications = db.query(WhatsAppNotification).count()
        
        # Status counts
        status_counts = db.query(
            WhatsAppNotification.status,
            func.count(WhatsAppNotification.id)
        ).group_by(WhatsAppNotification.status).all()
        
        stats = {
            'total_notifications': total_notifications,
            'total_sent': 0,
            'total_delivered': 0,
            'total_failed': 0,
            'total_pending': 0,
            'success_rate': 0
        }
        
        # Populate status counts
        for status, count in status_counts:
            if status == 'sent':
                stats['total_sent'] = count
            elif status == 'delivered':
                stats['total_delivered'] = count
            elif status == 'failed':
                stats['total_failed'] = count
            elif status == 'pending':
                stats['total_pending'] = count
        
        # Calculate success rate
        successful = stats['total_sent'] + stats['total_delivered']
        total_attempted = successful + stats['total_failed']
        
        if total_attempted > 0:
            stats['success_rate'] = (successful / total_attempted) * 100
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_notifications = db.query(WhatsAppNotification).filter(
            WhatsAppNotification.created_at >= week_ago
        ).count()
        
        stats['recent_notifications'] = recent_notifications
        
        # Type breakdown
        type_counts = db.query(
            WhatsAppNotification.notification_type,
            func.count(WhatsAppNotification.id)
        ).group_by(WhatsAppNotification.notification_type).all()
        
        stats['type_breakdown'] = {notification_type: count for notification_type, count in type_counts}
        
        return stats
        
    except Exception as e:
        logger.error(f"Error calculating notification stats: {e}")
        return {
            'total_notifications': 0,
            'total_sent': 0,
            'total_delivered': 0,
            'total_failed': 0,
            'total_pending': 0,
            'success_rate': 0,
            'recent_notifications': 0,
            'type_breakdown': {}
        }

@router.post('/whatsapp/test')
def test_whatsapp_connection(request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin']))):
    """Test WhatsApp API connection"""
    try:
        
        # Test data
        test_data = {
            'customer_name': 'Test Customer',
            'customer_phone': '1234567890',  # This will be simulated
            'id': 999,
            'net_total': 1000,
            'type_of': 'invoice'
        }
        
        # Send test notification
        result = whatsapp_notifier.send_invoice_notification(test_data)
        
        return _json({
            'success': result['success'],
            'status': result['status'],
            'message': 'Test notification sent successfully' if result['success'] else 'Test failed',
            'details': result
        })
        
    except Exception as e:
        logger.error(f"Error testing WhatsApp connection: {e}")
        return _json({
            'success': False,
            'error': str(e),
            'message': 'Failed to test WhatsApp connection'
        }, 500) 