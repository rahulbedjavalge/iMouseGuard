#!/usr/bin/env python3
import os, json, time, subprocess
from websocket import create_connection

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9000")
HOOK = "/opt/iMouseGuard/bin/imouse_hook_alert.py"

def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "|", *a, flush=True)

def run_hook(eid, mid, payload):
    try:
        p = subprocess.Popen([HOOK, str(eid), str(mid)], stdin=subprocess.PIPE)
        p.communicate(input=json.dumps(payload).encode("utf-8"), timeout=5)
    except Exception as e:
        log("hook error:", e)

def parse_events(data):
    """Return list of dicts {eid, mid, cause, name} from ES message."""
    out = []
    ev = data.get("events", []) or data.get("Events", []) or []
    items = data.get("items", []) or []
    for obj in (ev + items):
        eid = (
            obj.get("eid")
            or obj.get("event_id")
            or obj.get("EventID")
            or obj.get("eventId")
            or obj.get("EventId")
        )
        mid = (
            obj.get("mid")
            or obj.get("monitor_id")
            or obj.get("monitorId")
            or obj.get("MonitorID")
            or obj.get("MonitorId")
            or data.get("monitor_id")
        )
        cause = obj.get("cause") or data.get("cause") or "ZM event"
        name = obj.get("name") or obj.get("Name") or data.get("name") or ""
        out.append({"eid": str(eid) if eid is not None else "", "mid": str(mid) if mid is not None else "", "cause": cause, "name": name})
    return out

def main():
    sent_connect_notice_at = 0
    CONNECT_NOTICE_GAP = 600
    seen_eids = set()
    SEEN_MAX = 500

    while True:
        try:
            log("connecting to", WS_URL)
            ws = create_connection(WS_URL, timeout=5, ping_interval=30, ping_timeout=10)
            ws.settimeout(300)

            # Send an auth frame (some ES builds expect it even if auth is disabled)
            if os.environ.get("WS_SEND_AUTH") == "1":
                user = os.getenv("ES_USER", "")
                pwd = os.getenv("ES_PASSWORD", "")
                ws.send(json.dumps({"event": "auth", "data": {"user": user, "password": pwd}}))
            else:
                ws.send(json.dumps({"event": "auth", "data": {"user": "", "password": ""}}))

            now = time.time()
            if sent_connect_notice_at == 0 or (now - sent_connect_notice_at) > CONNECT_NOTICE_GAP:
                run_hook("ws_conn", "0", {"behavior": "ws_connected", "notes": "forwarder connected"})
                sent_connect_notice_at = now
                log("connected; connect notice sent")

            while True:
                msg = ws.recv()
                if not msg:
                    continue
                log("< recv:", msg[:200])
                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                # Auth replies aren't fatal — ES can still push alarms with NOAUTH/BADAUTH when auth is off
                if str(data.get("event", "")).lower() == "auth":
                    continue

                for e in parse_events(data):
                    eid, mid = e["eid"], e["mid"]
                    if not eid or eid == "0":
                        continue
                    if eid in seen_eids:
                        continue
                    seen_eids.add(eid)
                    if len(seen_eids) > SEEN_MAX:
                        seen_eids.clear()

                    payload = {
                        "behavior": "zm_event",
                        "notes": e["cause"],
                        "monitor_name": e["name"],
                    }
                    log("forwarding event eid:", eid, "mid:", mid)
                    run_hook(eid, mid, payload)

        except Exception as e:
            log("ws error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
