#!/usr/bin/env python3
"""
iMouseGuard - WhatsApp integration via Twilio

Sends WhatsApp messages using Twilio API.
Can be called as a hook from zmes_ws_to_telegram or directly.
"""

import os, sys, json, time
from twilio.rest import Client

# ---------- utils ----------
ENV_FILES = ("/opt/iMouseGuard/env/prod.env", "d:/iMouseGuard/iMouseGuard/env/prod.env")

def _clean(val: str) -> str:
    if val is None:
        return ""
    v = str(val).strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        v = v[1:-1]
    return v.replace("\r","").replace("\n","").strip()

def get_env(name: str) -> str:
    v = os.getenv(name, None)
    if v:
        return _clean(v)
    for path in ENV_FILES:
        try:
            with open(path, "r") as f:
                for line in f:
                    line=line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith(f"export {name}="):
                        return _clean(line.split("=",1)[1])
        except Exception:
            pass
    return ""

def log_err(msg: str) -> None:
    print(f"[WHATSAPP] {msg}", file=sys.stderr, flush=True)

def log_info(msg: str) -> None:
    print(f"[WHATSAPP] {msg}", flush=True)

def send_whatsapp(text: str, retries: int = 2) -> bool:
    """Send WhatsApp message via Twilio."""
    account_sid = get_env("TWILIO_ACCOUNT_SID")
    auth_token = get_env("TWILIO_AUTH_TOKEN")
    from_num = get_env("TWILIO_WHATSAPP_FROM")
    to_num = get_env("WHATSAPP_TO")
    
    if not account_sid or not auth_token:
        log_err("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing")
        return False
    
    if not from_num or not to_num:
        log_err("TWILIO_WHATSAPP_FROM or WHATSAPP_TO missing")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=text,
            from_=from_num,
            to=to_num
        )
        log_info(f"WhatsApp message sent: {message.sid}")
        return True
    except Exception as e:
        log_err(f"WhatsApp send failed: {e}")
        return False

def send_whatsapp_template(template_sid: str, variables: dict = None) -> bool:
    """Send WhatsApp template message via Twilio."""
    account_sid = get_env("TWILIO_ACCOUNT_SID")
    auth_token = get_env("TWILIO_AUTH_TOKEN")
    from_num = get_env("TWILIO_WHATSAPP_FROM")
    to_num = get_env("WHATSAPP_TO")
    
    if not account_sid or not auth_token:
        log_err("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing")
        return False
    
    if not from_num or not to_num:
        log_err("TWILIO_WHATSAPP_FROM or WHATSAPP_TO missing")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            content_sid=template_sid,
            content_variables=json.dumps(variables) if variables else None,
            from_=from_num,
            to=to_num
        )
        log_info(f"WhatsApp template message sent: {message.sid}")
        return True
    except Exception as e:
        log_err(f"WhatsApp template send failed: {e}")
        return False

def main() -> int:
    """Main entry point."""
    enabled = get_env("ENABLE_WHATSAPP") == "1"
    if not enabled:
        log_info("WhatsApp integration disabled (ENABLE_WHATSAPP=0)")
        return 0
    
    # Read JSON from stdin if provided (from hook)
    raw = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    
    if raw:
        try:
            data = json.loads(raw)
            # Extract message content
            template_sid = data.get("template_sid", "")
            message = data.get("message", "")
            variables = data.get("variables", {})
            
            if template_sid:
                success = send_whatsapp_template(template_sid, variables)
            elif message:
                success = send_whatsapp(message)
            else:
                log_err("No template_sid or message provided in JSON")
                return 1
        except json.JSONDecodeError:
            log_err("Invalid JSON from stdin")
            return 1
    else:
        # Direct command-line usage
        msg = " ".join(sys.argv[1:]).strip()
        if not msg:
            log_err("Usage: whatsapp_call.py <message> OR echo JSON | whatsapp_call.py")
            return 1
        success = send_whatsapp(msg)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
