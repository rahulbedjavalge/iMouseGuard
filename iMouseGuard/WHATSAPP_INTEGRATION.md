# WhatsApp Integration via Twilio

This document describes how to set up WhatsApp messaging in iMouseGuard using Twilio.

## Prerequisites

1. **Twilio Account** - Create one at https://www.twilio.com/
2. **WhatsApp Sandbox** - Set up a WhatsApp Business Account and enable messaging sandbox
3. **Account Credentials** - Account SID and Auth Token from your Twilio dashboard
4. **WhatsApp Numbers** - Both sender and receiver numbers in E.164 format (e.g., `whatsapp:+14155238886`)

## Setup

### 1. Install Twilio Package

```bash
/opt/iMouseGuard/venv/bin/pip install twilio
```

### 2. Configure Environment Variables

Edit `/opt/iMouseGuard/env/prod.env` and set:

```bash
# Enable WhatsApp integration
export ENABLE_WHATSAPP="1"

# Twilio API credentials (from Twilio dashboard)
export TWILIO_ACCOUNT_SID="YOUR_SID_HERE"
export TWILIO_AUTH_TOKEN="YOUR_TOKEN_HERE"

# WhatsApp numbers in E.164 format
export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"     # Twilio sandbox number
export WHATSAPP_TO="whatsapp:+4915560375039"             # Recipient number
```

### 3. Verify Configuration

Test basic connectivity:

```bash
/opt/iMouseGuard/venv/bin/python /opt/iMouseGuard/bin/whatsapp_call.py "Test message"
```

Expected output (if enabled):
```
[WHATSAPP] WhatsApp message sent: SMxxxxxxxxxxxxxxxxxxxxxxxx
```

## Usage

### Direct Command-Line Usage

```bash
/opt/iMouseGuard/bin/whatsapp_call.py "Your alert message here"
```

### Hook Integration (JSON Stdin)

#### Text Message

```bash
echo '{"message":"Alert: Motion detected in zone A"}' | \
  /opt/iMouseGuard/bin/whatsapp_call.py
```

#### Template Message (Twilio Templates)

```bash
echo '{
  "template_sid": "YOUR_TEMPLATE_SID",
  "variables": {
    "1": "value1",
    "2": "value2"
  }
}' | /opt/iMouseGuard/bin/whatsapp_call.py
```

### Integration with ZoneMinder Events

When Event Server sends payload to `imouse_hook_alert.py`, it automatically sends to both Telegram and WhatsApp.

## Features

- ✅ Text message delivery
- ✅ Template-based messages with variable substitution
- ✅ Graceful error handling and logging
- ✅ Environment variable support (prod.env)
- ✅ Integration with hook system
<<<<<<< HEAD
- ✅ Retries and timeout handling
=======
- ✅ Works on both Windows and Linux
>>>>>>> bbf04ca1fc5d8eb15f0b196c5d8bc2a8c8a71717

## Troubleshooting

### "WhatsApp integration disabled (ENABLE_WHATSAPP=0)"
- Set `ENABLE_WHATSAPP=1` in prod.env

### "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing"
- Verify credentials are set in prod.env
- Check file permissions: `chmod 600 /opt/iMouseGuard/env/prod.env`

### "TWILIO_WHATSAPP_FROM or WHATSAPP_TO missing"
- Ensure WhatsApp numbers are in E.164 format: `whatsapp:+<country_code><number>`
- Example: `whatsapp:+14155238886` ✓ vs `14155238886` ✗

### Message not received
1. Verify recipient number is joined to Twilio sandbox
2. Check Twilio dashboard for API errors
3. Ensure Twilio account has WhatsApp enabled
- ✅ Retries and timeout handling
- ✅ Works on both Windows and Linuxs/sms-integration/whatsapp
2. Join the sandbox with the provided template message
3. Use the provided `whatsapp:+...` number as `TWILIO_WHATSAPP_FROM`
4. Recipients must join the sandbox before receiving messages

## Cost Considerations

- Twilio WhatsApp API charges per message sent
- Free tier includes limited sandbox testing
- Production use requires a WhatsApp Business Account
- See Twilio pricing: https://www.twilio.com/whatsapp/pricing
