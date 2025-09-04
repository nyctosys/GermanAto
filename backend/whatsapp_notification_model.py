#!/usr/bin/env python3
"""
WhatsApp Notification Database Model
Tracks all WhatsApp notifications sent to clients
"""

from datetime import datetime
from models import db

class WhatsAppNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Client information
    customer_name = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    
    # Notification details
    notification_type = db.Column(db.String(50), nullable=False)  # invoice, quote, payment_reminder, repair_status
    message_content = db.Column(db.Text, nullable=False)
    
    # Related document
    related_document_type = db.Column(db.String(50), nullable=True)  # invoice, repair_order
    related_document_id = db.Column(db.Integer, nullable=True)
    
    # WhatsApp API response
    whatsapp_message_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, delivered, failed
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        super(WhatsAppNotification, self).__init__(**kwargs)
    
    def mark_sent(self, whatsapp_message_id: str = None):
        """Mark notification as sent"""
        self.status = 'sent'
        self.sent_at = datetime.utcnow()
        if whatsapp_message_id:
            self.whatsapp_message_id = whatsapp_message_id
    
    def mark_delivered(self):
        """Mark notification as delivered"""
        self.status = 'delivered'
        self.delivered_at = datetime.utcnow()
    
    def mark_failed(self, error_message: str):
        """Mark notification as failed"""
        self.status = 'failed'
        self.error_message = error_message
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'notification_type': self.notification_type,
            'message_content': self.message_content,
            'related_document_type': self.related_document_type,
            'related_document_id': self.related_document_id,
            'whatsapp_message_id': self.whatsapp_message_id,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None
        } 