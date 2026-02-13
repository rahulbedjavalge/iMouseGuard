#!/usr/bin/env python3
import os, json, time, subprocess
from websocket import create_connection

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9000")
HOOK = "/opt/iMouseGuard/bin/imouse_hook_alert.py"
DEBUG = os.getenv("IMOUSE_WS_DEBUG", "0") == "1"

def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "|", *a, flush=True)

def run_hook(eid, mid, payload):
    try:
        p = subprocess.Popen([HOOK, str(eid), str(mid)], stdin=subprocess.PIPE)
        p.communicate(input=json.dumps(payload).encode("utf-8"), timeout=5)
    except Exception as e:
        log("hook error:", e)

def parse_events(data):
    out = []
    ev = data.get("events", []) or data.get("Events", []) or data.get("items", []) or []
    if isinstance(ev, dict):
        ev = [ev]

    for obj in ev:
        eid = (
            obj.get("eid")
            or obj.get("event_id")
            or obj.get("eventId")
            or obj.get("EventId")
            or obj.get("EventID")
            or obj.get("EventID".lower())
            or data.get("eid")
            or data.get("event_id")
        )
        mid = (
            obj.get("mid")
            or obj.get("monitor_id")
            or obj.get("monitorId")
            or obj.get("MonitorId")
            or obj.get("MonitorID")
            or data.get("mid")
            or data.get("monitor_id")
        )
        cause = obj.get("cause") or obj.get("Cause") or data.get("cause") or data.get("Cause") or ""
        name = obj.get("name") or obj.get("Name") or data.get("name") or data.get("Name") or ""

        if eid and mid:
            out.append({"eid": str(eid), "mid": str(mid), "cause": cause, "name": name})
    return out


def try_subscriptions(ws):
    """
    Try a few subscription messages so we work across ES versions.
    We won’t error if a format is unrecognized; ES will ignore it.
    """
    msgs = [
        {"event":"filter","data":{"monitors":"all","tags":[],"interval":0}},
        {"event":"filter","data":{"monitors":["all"],"tags":[]}},
        {"event":"monitor","data":{"monitors":"all"}},
        {"event":"monitor","monitors":["all"]},
        {"event":"listen","data":{"monitors":["all"]}},
    ]
    for m in msgs:
        ws.send(json.dumps(m))
        if DEBUG: log("-> sent subscribe", m)

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

            # auth (empty creds also fine when ES auth is off)
            ws.send(json.dumps({"event":"auth","data":{"user":"","password":""}}))
            if DEBUG: log("-> sent auth")

            # subscribe to all monitors
            try_subscriptions(ws)

            now = time.time()
            if sent_connect_notice_at == 0 or (now - sent_connect_notice_at) > CONNECT_NOTICE_GAP:
                run_hook("ws_conn", "0", {"behavior": "ws_connected", "notes": "forwarder connected"})
                sent_connect_notice_at = now
                log("connected; connect notice sent")

            while True:
                msg = ws.recv()
                if not msg:
                    continue
                if DEBUG: log("< recv:", msg[:300])
                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                # ignore auth replies
                if str(data.get("event","")).lower() == "auth":
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
                    payload = {"behavior":"zm_event","notes":e["cause"],"monitor_name":e["name"]}
                    log("forwarding event eid:", eid, "mid:", mid)
                    run_hook(eid, mid, payload)

        except Exception as e:
            log("ws error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
