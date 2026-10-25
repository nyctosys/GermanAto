#!/usr/bin/env python3
"""
WhatsApp Automated Notifications System using Twilio WhatsApp API
Handles sending automated WhatsApp messages to clients
"""

import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)

class WhatsAppNotifier:
    def __init__(self):
        """Initialize WhatsApp notifier with Twilio API credentials"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        
        if not self.account_sid or not self.auth_token or not self.whatsapp_number:
            logger.warning("Twilio WhatsApp API credentials not configured. Notifications will be logged only.")
            self.enabled = False
        else:
            self.enabled = True
    
    def format_phone_number(self, phone: str) -> str:
        """Format phone number for Twilio WhatsApp API"""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone))
        
        # Add country code if not present (assuming Pakistan +92)
        if not cleaned.startswith('92') and len(cleaned) == 10:
            cleaned = '92' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('0'):
            cleaned = '92' + cleaned[1:]
        
        # Format for Twilio WhatsApp API (whatsapp:+92XXXXXXXXXX)
        return f"whatsapp:+{cleaned}"
    
    def send_message(self, phone_number: str, message: str, template_name: str = None) -> Dict:
        """Send WhatsApp message to client using Twilio API"""
        try:
            formatted_phone = self.format_phone_number(phone_number)
            
            if not self.enabled:
                # Log the message instead of sending
                logger.info(f"WhatsApp Message (SIMULATED) to {formatted_phone}: {message}")
                return {
                    'success': True,
                    'message_id': f'sim_{datetime.now().timestamp()}',
                    'status': 'simulated'
                }
            
            # Twilio WhatsApp API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            
            # Prepare the request data
            data = {
                'From': f"whatsapp:{self.whatsapp_number}",
                'To': formatted_phone,
                'Body': message
            }
            
            # Make the request to Twilio
            response = requests.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token)
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"WhatsApp message sent successfully to {formatted_phone}")
            
            return {
                'success': True,
                'message_id': result.get('sid'),
                'status': 'sent'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'failed'
            }
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp message: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
    
    def send_invoice_notification(self, invoice_data: Dict) -> Dict:
        """Send invoice notification to client"""
        try:
            customer_name = invoice_data.get('customer_name', 'Valued Customer')
            invoice_id = invoice_data.get('id')
            total_amount = invoice_data.get('net_total', 0)
            invoice_type = invoice_data.get('type_of', 'invoice')
            
            # Format amount
            formatted_amount = f"{float(total_amount):,.2f} PKR"
            
            # Create message based on invoice type
            if invoice_type == 'invoice':
                message = self._create_invoice_message(customer_name, invoice_id, formatted_amount)
            else:  # quote
                message = self._create_quote_message(customer_name, invoice_id, formatted_amount)
            
            phone_number = invoice_data.get('customer_phone')
            
            if not phone_number:
                return {
                    'success': False,
                    'error': 'No phone number provided',
                    'status': 'failed'
                }
            
            return self.send_message(phone_number, message, 'invoice_notification')
            
        except Exception as e:
            logger.error(f"Error creating invoice notification: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
    
    def _create_invoice_message(self, customer_name: str, invoice_id: int, amount: str) -> str:
        """Create invoice notification message"""
        return f"""🏁 *GermanATO - Invoice Generated*

Dear {customer_name},

Your invoice has been successfully generated!

📋 *Invoice Details:*
• Invoice ID: #{invoice_id}
• Total Amount: {amount}
• Status: Pending Payment

💳 *Payment Options:*
• Cash Payment
• Bank Transfer
• Online Payment

📞 *Contact Us:*
For any queries, please contact us at:
• Phone: +92-XXX-XXXXXXX
• Email: info@germanato.com

Thank you for choosing GermanATO!

Best regards,
GermanATO Team 🚗🔧"""
    
    def _create_quote_message(self, customer_name: str, quote_id: int, amount: str) -> str:
        """Create quote notification message"""
        return f"""📋 *GermanATO - Quote Generated*

Dear {customer_name},

Your quote has been successfully generated!

📋 *Quote Details:*
• Quote ID: #{quote_id}
• Estimated Amount: {amount}
• Status: Pending Approval

✅ *Next Steps:*
1. Review the quote details
2. Approve or request modifications
3. We'll proceed with the work upon approval

📞 *Contact Us:*
For any questions or modifications:
• Phone: +92-XXX-XXXXXXX
• Email: info@germanato.com

Thank you for choosing GermanATO!

Best regards,
GermanATO Team 🚗🔧"""
    
    def send_payment_reminder(self, invoice_data: Dict, days_overdue: int = 0) -> Dict:
        """Send payment reminder to client"""
        try:
            customer_name = invoice_data.get('customer_name', 'Valued Customer')
            invoice_id = invoice_data.get('id')
            total_amount = invoice_data.get('net_total', 0)
            formatted_amount = f"{float(total_amount):,.2f} PKR"
            
            message = f"""💰 *GermanATO - Payment Reminder*

Dear {customer_name},

This is a friendly reminder about your pending payment.

📋 *Invoice Details:*
• Invoice ID: #{invoice_id}
• Amount Due: {formatted_amount}
• Status: Pending Payment

{f"⏰ *Overdue by: {days_overdue} days*" if days_overdue > 0 else ""}

💳 *Payment Options:*
• Cash Payment
• Bank Transfer
• Online Payment

📞 *Contact Us:*
For payment arrangements:
• Phone: +92-XXX-XXXXXXX
• Email: info@germanato.com

Thank you for your prompt attention.

Best regards,
GermanATO Team 🚗🔧"""
            
            phone_number = invoice_data.get('customer_phone')
            return self.send_message(phone_number, message, 'payment_reminder')
            
        except Exception as e:
            logger.error(f"Error creating payment reminder: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
    
    def send_repair_status_update(self, repair_order_data: Dict, status: str) -> Dict:
        """Send repair status update to client"""
        try:
            customer_name = repair_order_data.get('customer_name', 'Valued Customer')
            repair_id = repair_order_data.get('id')
            
            status_messages = {
                'received': 'Your vehicle has been received and is being diagnosed.',
                'in_progress': 'Work on your vehicle has started.',
                'completed': 'Your vehicle repair has been completed and is ready for pickup.',
                'ready': 'Your vehicle is ready for pickup!'
            }
            
            status_message = status_messages.get(status, f'Your repair status has been updated to: {status}')
            
            message = f"""🔧 *GermanATO - Repair Status Update*

Dear {customer_name},

{status_message}

📋 *Repair Order Details:*
• Repair ID: #{repair_id}
• Current Status: {status.title()}

📞 *Contact Us:*
For any questions:
• Phone: +92-XXX-XXXXXXX
• Email: info@germanato.com

Thank you for choosing GermanATO!

Best regards,
GermanATO Team 🚗🔧"""
            
            phone_number = repair_order_data.get('customer_phone')
            return self.send_message(phone_number, message, 'repair_status')
            
        except Exception as e:
            logger.error(f"Error creating repair status update: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }

# Global instance
whatsapp_notifier = WhatsAppNotifier() 