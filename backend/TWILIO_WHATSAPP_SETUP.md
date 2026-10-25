# Twilio WhatsApp API Setup Guide

## Overview

This application uses Twilio WhatsApp API to send automated notifications to clients. The system has been migrated from Meta WhatsApp Business API to Twilio WhatsApp API for better reliability and easier setup.

## Prerequisites

1. **Twilio Account**: Sign up at [twilio.com](https://www.twilio.com)
2. **WhatsApp Business API Access**: Request access to Twilio WhatsApp Business API
3. **Verified WhatsApp Number**: Your business WhatsApp number must be verified with Twilio

## Setup Steps

### 1. Create Twilio Account

1. Go to [twilio.com](https://www.twilio.com) and create an account
2. Verify your email and phone number
3. Complete account verification

### 2. Get Twilio Credentials

1. Log into your Twilio Console
2. Note down your **Account SID** (found on the dashboard)
3. Note down your **Auth Token** (found on the dashboard)
4. Keep these credentials secure

### 3. Set Up WhatsApp Business API

1. In Twilio Console, go to **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Follow the setup wizard to connect your WhatsApp Business account
3. Note down your **WhatsApp Number** (format: +1234567890)

### 4. Configure Environment Variables

1. Copy the configuration template:

   ```bash
   cp whatsapp_config_template.env .env
   ```

2. Edit the `.env` file and add your Twilio credentials:

   ```env
   # Twilio Account SID (from Twilio Console)
   TWILIO_ACCOUNT_SID=AC1234567890abcdef1234567890abcdef

   # Twilio Auth Token (from Twilio Console)
   TWILIO_AUTH_TOKEN=your_twilio_auth_token_here

   # Twilio WhatsApp Number (your Twilio WhatsApp number)
   TWILIO_WHATSAPP_NUMBER=+1234567890

   # Optional: Enable/Disable WhatsApp notifications (true/false)
   WHATSAPP_ENABLED=true

   # Optional: Test mode - sends notifications to console instead of WhatsApp
   WHATSAPP_TEST_MODE=false
   ```

### 5. Test the Setup

1. Start the application
2. Go to the WhatsApp Notifications page
3. Use the "Test Connection" feature to verify your setup

## API Features

### Supported Message Types

- **Invoice Notifications**: Sent when invoices are created
- **Quote Notifications**: Sent when quotes are generated
- **Payment Reminders**: Automated payment reminders
- **Repair Status Updates**: Vehicle repair progress updates

### Message Format

Messages are formatted with:

- Business branding (GermanATO)
- Clear structure with emojis and formatting
- Contact information
- Professional tone

## Troubleshooting

### Common Issues

1. **"Credentials not configured"**

   - Check that all environment variables are set correctly
   - Verify the `.env` file is in the correct location

2. **"Failed to send WhatsApp message"**

   - Verify your Twilio credentials are correct
   - Check that your WhatsApp number is verified
   - Ensure you have sufficient Twilio credits

3. **"Phone number format error"**
   - The system automatically formats Pakistan numbers (+92)
   - For other countries, ensure the number includes country code

### Testing Mode

Enable test mode to log messages instead of sending:

```env
WHATSAPP_TEST_MODE=true
```

This will log all messages to the console for debugging.

## Security Notes

- Keep your Twilio credentials secure
- Never commit `.env` files to version control
- Regularly rotate your Auth Token
- Monitor your Twilio usage and costs

## Cost Considerations

- Twilio charges per message sent
- WhatsApp Business API has additional costs
- Monitor usage in your Twilio Console
- Set up billing alerts to avoid unexpected charges

## Migration from Meta WhatsApp Business API

The system has been migrated from Meta WhatsApp Business API to Twilio WhatsApp API. Key changes:

- **Authentication**: Uses Twilio Account SID and Auth Token instead of Meta API Token
- **API Endpoint**: Uses Twilio's REST API instead of Meta's Graph API
- **Phone Format**: Uses `whatsapp:+XXXXXXXXXX` format
- **Message ID**: Uses Twilio's SID instead of Meta's message ID

## Support

For Twilio-specific issues:

- [Twilio Support](https://support.twilio.com)
- [Twilio WhatsApp API Documentation](https://www.twilio.com/docs/whatsapp)

For application-specific issues:

- Check the application logs
- Review the WhatsApp notifications page for error details
