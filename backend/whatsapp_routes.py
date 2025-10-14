#!/usr/bin/env python3
"""
WhatsApp Notifications API Routes
Handles WhatsApp notification management and tracking
"""

from flask import Blueprint, jsonify, request
from models import db, WhatsAppNotification
from sqlalchemy import desc, func
from datetime import datetime, timedelta
import logging
from jwt_auth import login_required, role_required, admin_required

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint('whatsapp', __name__)

@whatsapp_bp.route('/whatsapp/notifications', methods=['GET'])
@login_required
def get_notifications(current_user=None):
    """Get all WhatsApp notifications with optional filters"""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status_filter = request.args.get('status')
        type_filter = request.args.get('type')
        search = request.args.get('search')
        
        # Build query
        query = WhatsAppNotification.query
        
        # Apply filters
        if status_filter and status_filter != 'all':
            query = query.filter(WhatsAppNotification.status == status_filter)
        
        if type_filter and type_filter != 'all':
            query = query.filter(WhatsAppNotification.notification_type == type_filter)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    WhatsAppNotification.customer_name.ilike(search_term),
                    WhatsAppNotification.customer_phone.ilike(search_term),
                    WhatsAppNotification.message_content.ilike(search_term)
                )
            )
        
        # Order by most recent first
        query = query.order_by(desc(WhatsAppNotification.created_at))
        
        # Paginate results
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        notifications = [notification.to_dict() for notification in pagination.items]
        
        # Calculate statistics
        stats = calculate_notification_stats()
        
        return jsonify({
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
        return jsonify({'error': 'Failed to fetch notifications'}), 500

@whatsapp_bp.route('/whatsapp/notifications/<int:notification_id>', methods=['GET'])
@login_required
def get_notification(notification_id, current_user=None):
    """Get a specific notification by ID"""
    try:
        notification = WhatsAppNotification.query.get(notification_id)
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        return jsonify(notification.to_dict())
        
    except Exception as e:
        logger.error(f"Error fetching notification {notification_id}: {e}")
        return jsonify({'error': 'Failed to fetch notification'}), 500

@whatsapp_bp.route('/whatsapp/notifications/<int:notification_id>/resend', methods=['POST'])
@role_required(['admin', 'accountant'])
def resend_notification(notification_id, current_user=None):
    """Resend a failed notification"""
    try:
        notification = WhatsAppNotification.query.get(notification_id)
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        if notification.status != 'failed':
            return jsonify({'error': 'Only failed notifications can be resent'}), 400
        
        # Import WhatsApp notifier
        from whatsapp_notifications import whatsapp_notifier
        
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
            db.session.commit()
            
            return jsonify({
                'message': 'Notification resent successfully',
                'status': 'sent'
            })
        else:
            notification.mark_failed(result.get('error', 'Unknown error'))
            db.session.commit()
            
            return jsonify({
                'error': 'Failed to resend notification',
                'details': result.get('error')
            }), 400
        
    except Exception as e:
        logger.error(f"Error resending notification {notification_id}: {e}")
        return jsonify({'error': 'Failed to resend notification'}), 500

@whatsapp_bp.route('/whatsapp/stats', methods=['GET'])
@login_required
def get_notification_stats(current_user=None):
    """Get notification statistics"""
    try:
        stats = calculate_notification_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error calculating notification stats: {e}")
        return jsonify({'error': 'Failed to calculate statistics'}), 500

def calculate_notification_stats():
    """Calculate notification statistics"""
    try:
        # Total notifications
        total_notifications = WhatsAppNotification.query.count()
        
        # Status counts
        status_counts = db.session.query(
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
        recent_notifications = WhatsAppNotification.query.filter(
            WhatsAppNotification.created_at >= week_ago
        ).count()
        
        stats['recent_notifications'] = recent_notifications
        
        # Type breakdown
        type_counts = db.session.query(
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

@whatsapp_bp.route('/whatsapp/test', methods=['POST'])
@admin_required
def test_whatsapp_connection(current_user=None):
    """Test WhatsApp API connection"""
    try:
        from whatsapp_notifications import whatsapp_notifier
        
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
        
        return jsonify({
            'success': result['success'],
            'status': result['status'],
            'message': 'Test notification sent successfully' if result['success'] else 'Test failed',
            'details': result
        })
        
    except Exception as e:
        logger.error(f"Error testing WhatsApp connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to test WhatsApp connection'
        }), 500 