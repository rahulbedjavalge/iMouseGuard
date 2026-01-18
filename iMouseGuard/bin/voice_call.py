#!/usr/bin/env python3
"""
iMouseGuard - Voice Call integration via Twilio

Makes voice calls using Twilio API with text-to-speech.
"""

import os, sys, json
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
    print(f"[VOICE] {msg}", file=sys.stderr, flush=True)

def log_info(msg: str) -> None:
    print(f"[VOICE] {msg}", flush=True)

def make_voice_call(message: str) -> bool:
    """Make a voice call via Twilio with TTS."""
    account_sid = get_env("TWILIO_ACCOUNT_SID")
    auth_token = get_env("TWILIO_AUTH_TOKEN")
    from_num = get_env("TWILIO_VOICE_FROM")
    to_num = get_env("VOICE_CALL_TO")
    
    if not account_sid or not auth_token:
        log_err("TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing")
        return False
    
    if not from_num or not to_num:
        log_err("TWILIO_VOICE_FROM or VOICE_CALL_TO missing")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        # Use Twimlet for instant TTS without hosting TwiML
        url = f"http://twimlets.com/message?Message={message.replace(' ', '%20')}"
        call = client.calls.create(to=to_num, from_=from_num, url=url)
        log_info(f"Voice call initiated: {call.sid}")
        return True
    except Exception as e:
        log_err(f"Voice call failed: {e}")
        return False

def main() -> int:
    """Main entry point."""
    enabled = get_env("ENABLE_VOICE_CALL") == "1"
    if not enabled:
        log_info("Voice call disabled (ENABLE_VOICE_CALL=0)")
        return 0
    
    # Read JSON from stdin if provided
    raw = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    
    if raw:
        try:
            data = json.loads(raw)
            message = data.get("message", "")
            if not message:
                log_err("No message provided in JSON")
                return 1
            success = make_voice_call(message)
        except json.JSONDecodeError:
            log_err("Invalid JSON from stdin")
            return 1
    else:
        # Direct command-line usage
        msg = " ".join(sys.argv[1:]).strip()
        if not msg:
            log_err("Usage: voice_call.py <message> OR echo JSON | voice_call.py")
            return 1
        success = make_voice_call(msg)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
