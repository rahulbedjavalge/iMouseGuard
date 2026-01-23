#!/usr/bin/env python3
"""
iMouseGuard - Telegram alert hook (enriched)

Reads JSON on stdin and argv:
  argv[1] = Event ID (eid)
  argv[2] = Monitor ID (mid)

Enriches the alert by calling ZoneMinder API for event and monitor details.
Sends a Telegram message to a group topic.
"""

import sys, os, json, time
import urllib.parse, urllib.request

#from wasabi import msg

# ---------- utils ----------
ENV_FILES = (
    #"/opt/iMouseGuard/env/prod.env",
    "D:\\iMouseGuard\\iMouseGuard\\env\\prod.env",)

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
    print(f"[HOOK] {msg}", file=sys.stderr, flush=True)

def http_get_json(url: str, timeout: int = 4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                log_err(f"HTTP {resp.status} for {url}")
                return None
            payload = resp.read().decode("utf-8", "ignore")
            return json.loads(payload)
    except Exception as e:
        log_err(f"GET failed {url}: {e}")
        return None

def send_telegram(text: str, retries: int = 2) -> None:
    token = get_env("TELEGRAM_TOKEN")
    chat  = get_env("TELEGRAM_CHAT_ID")
    thread= get_env("TELEGRAM_THREAD_ID")
    if not token or not chat:
        log_err("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat, "text": text}
    if thread:
        params["message_thread_id"] = thread
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"})
    backoff = 0.7
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    log_err(f"Telegram HTTP {resp.status}")
                return
        except Exception as e:
            if attempt >= retries:
                log_err(f"Telegram send failed: {e}")
                return
            time.sleep(backoff)
            backoff *= 2
            
def send_slack(text: str, retries: int = 2) -> None:
    webhook = get_env("SLACK_WEBHOOK_URL").strip()

    if not webhook:
        log_err("SLACK_WEBHOOK_URL missing")
        return

    if not webhook.startswith("https://hooks.slack.com/services/"):
        log_err("SLACK_WEBHOOK_URL looks invalid (must start with https://hooks.slack.com/services/...)")
        return

    payload = json.dumps({"text": text}).encode("utf-8")

    backoff = 0.7
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                webhook,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8", "ignore").strip()
                # Slack often returns "ok" on success
                if resp.status == 200 and (body == "" or body.lower() == "ok"):
                    log_err("[SLACK] sent ok")
                    return

                log_err(f"[SLACK] HTTP {resp.status}, body={body}")
                return
        except Exception as e:
            if attempt >= retries:
                log_err(f"[SLACK] send failed: {e}")
                return
            time.sleep(backoff)
            backoff *= 2


# ---------- enrichment ----------
def fetch_event(eid: str):
    base = get_env("IMOUSE_API_BASE") or "http://127.0.0.1"
    url = f"{base}/api/events/view/{eid}.json"
    j = http_get_json(url)
    if not j or "event" not in j:
        return {}
    ev = j["event"]["Event"]
    return {
        "Name": ev.get("Name"),
        "Cause": ev.get("Cause"),
        "Start": ev.get("StartDateTime"),
        "End": ev.get("EndDateTime"),
        "Length": ev.get("Length"),
        "TotScore": ev.get("TotScore"),
        "MaxScore": ev.get("MaxScore"),
        "MonitorId": str(ev.get("MonitorId") or ""),
    }

def fetch_monitor_name(mid: str):
    if not mid:
        return ""
    base = get_env("IMOUSE_API_BASE") or "http://127.0.0.1"
    url = f"{base}/api/monitors/view/{mid}.json"
    j = http_get_json(url)
    try:
        return j["monitor"]["Monitor"]["Name"]
    except Exception:
        return ""

def guess_zone_from_cause(cause: str):
    if not cause:
        return ""
    parts = [p.strip() for p in cause.split(":")]
    if len(parts) >= 2:
        return parts[1]
    return ""

def event_link(eid: str):
    web = get_env("IMOUSE_WEB_BASE") or "http://127.0.0.1"
    return f"{web}/index.php?view=event&eid={eid}"

# ---------- main ----------
def main() -> int:
    raw = sys.stdin.read().strip()
    eid = sys.argv[1] if len(sys.argv) > 1 else ""
    mid = sys.argv[2] if len(sys.argv) > 2 else ""

    body = {}
    if raw:
        try:
            body = json.loads(raw)
        except Exception:
            body = {}

    behavior = str(body.get("behavior", "") or "zm_event")
    notes    = str(body.get("notes", "") or "")
    #ev = fetch_event(eid) if eid else {}
    ev = {}
    #mon_name = fetch_monitor_name(mid) if mid else ""
    mon_name = ""
    cause = ev.get("Cause") or notes
    zone  = guess_zone_from_cause(cause)

    lines = ["🐭 iMouse Alert"]
    if mon_name:
        lines.append(f"Monitor: {mid} ({mon_name})")
    elif mid:
        lines.append(f"Monitor: {mid}")
    if eid:
        lines.append(f"Event ID: {eid}")
    if behavior:
        lines.append(f"Behavior: {behavior}")
    if zone:
        lines.append(f"Zone: {zone}")
    if cause:
        lines.append(f"Cause: {cause}")
    if ev.get("Start"):
        lines.append(f"Start: {ev['Start']}")
    if ev.get("Length"):
        lines.append(f"Length: {ev['Length']}s")
    if ev.get("MaxScore") is not None:
        lines.append(f"Max score: {ev['MaxScore']}")
    if eid:
        lines.append(f"View: {event_link(eid)}")

    msg = "\n".join(lines)
    send_telegram(msg)
    send_slack(msg)

    return 0

if __name__ == "__main__":
    sys.exit(main())
