# WhatsApp Integration - Setup Complete ✅

## Credentials Updated

The following Twilio credentials and WhatsApp configuration have been added to [prod.env](../env/prod.env):

```bash
# Twilio WhatsApp integration
export ENABLE_WHATSAPP="1"
export TWILIO_ACCOUNT_SID="YOUR_SID_HERE"
export TWILIO_AUTH_TOKEN="YOUR_TOKEN_HERE"
export TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"
export WHATSAPP_TO="whatsapp:+YOUR_NUMBER_HERE"
export TWILIO_WHATSAPP_CONTENT_SID="YOUR_TEMPLATE_SID_HERE"
```

## Test Results ✅

### 1. Text Message Test
**Command:**
```bash
D:/iMouseGuard/.venv/Scripts/python.exe whatsapp_call.py "🐭 iMouseGuard test alert"
```

**Result:**
```
[WHATSAPP] WhatsApp message sent: SMb557a2f767499ab9d823adb6a98026fa
```
✅ **SUCCESS**

### 2. Template Message Test
**Command:**
```bash
echo '{"template_sid":"HX350d429d32e64a552466cafecbe95f3c","variables":{"1":"12/1","2":"3pm"}}' | \
  D:/iMouseGuard/.venv/Scripts/python.exe whatsapp_call.py
```

**Result:**
```
[WHATSAPP] WhatsApp template message sent: MMb17bf10afe192fa597abd993562cc124
```
✅ **SUCCESS**

## Configuration Details

| Setting | Value |
|---------|-------|
| **Twilio Account SID** | YOUR_SID_HERE |
| **Twilio Auth Token** | YOUR_TOKEN_HERE |
| **WhatsApp From** | whatsapp:+14155238886 (Twilio Sandbox) |
| **WhatsApp To** | whatsapp:+49 (Recipient) |
| **Template SID** | HX350d429d32e64a552466cafecbe95f3c |
| **Status** | ✅ ENABLED |

## Files Modified

1. **[prod.env](../env/prod.env)** - Added Twilio configuration
2. **[whatsapp_call.py](../bin/whatsapp_call.py)** - WhatsApp integration script
3. **[WHATSAPP_INTEGRATION.md](../WHATSAPP_INTEGRATION.md)** - Complete integration guide

## Usage Examples

### Simple Alert
```bash
/opt/iMouseGuard/bin/whatsapp_call.py "Motion detected in zone A"
```

### Hook Integration
```bash
echo '{"message":"🐭 Event detected"}' | /opt/iMouseGuard/bin/whatsapp_call.py
```

### Template-Based
```bash
echo '{"template_sid":"HX...","variables":{"1":"value1","2":"value2"}}' | \
  /opt/iMouseGuard/bin/whatsapp_call.py
```

## Next Steps

1. ✅ Copy prod.env to `/opt/iMouseGuard/env/prod.env` on production system
2. ✅ Ensure recipient number is joined to Twilio WhatsApp sandbox
3. ✅ Integrate with ZoneMinder event hooks if needed
4. ✅ Monitor logs for any issues: `tail -f /opt/iMouseGuard/logs/forwarder.log`

## Troubleshooting

If messages don't arrive:
- Verify recipient has joined Twilio sandbox
- Check Twilio dashboard for delivery status
- Review auth token - ensure no extra spaces
- Confirm account has WhatsApp API enabled

## Security Note

⚠️ **IMPORTANT:** The prod.env file contains sensitive credentials.

```bash
chmod 600 /opt/iMouseGuard/env/prod.env
```

Never commit this file to version control. Use `.gitignore`:
```
env/prod.env
```
