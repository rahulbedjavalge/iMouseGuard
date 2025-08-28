#!/usr/bin/env python3
import os, sys, json, time, threading, datetime as dt
import urllib.parse, urllib.request
from websocket import create_connection
import yaml

CONF = "/opt/iMouseGuard/config/rules.yaml"
ENV_FILES = ["/opt/iMouseGuard/env/prod.env"]
STATE_FILE = "/opt/iMouseGuard/state/last_seen.json"
LOG_FILE = "/opt/iMouseGuard/logs/rules.log"

def log(*a):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = " ".join(str(x) for x in a)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f: f.write(f"{ts} | {msg}\n")
    print(ts, "|", msg, flush=True)

def load_yaml(path):
    with open(path, "r") as f: return yaml.safe_load(f)

def _clean(val):
    if val is None: return ""
    s = str(val).strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')): s = s[1:-1]
    return s.replace("\r","").replace("\n","").strip()

def get_env(name):
    v = os.getenv(name); 
    if v: return _clean(v)
    for p in ENV_FILES:
        try:
            with open(p) as f:
                for line in f:
                    line=line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith(f"export {name}="): return _clean(line.split("=",1)[1])
        except Exception: pass
    return ""

def send_telegram(text):
    token = get_env("TELEGRAM_TOKEN"); chat = get_env("TELEGRAM_CHAT_ID"); thread=get_env("TELEGRAM_THREAD_ID")
    if not token or not chat: log("telegram creds missing"); return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat, "text": text}
    if thread: params["message_thread_id"] = thread
    data = urllib.parse.urlencode(params).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != 200: log("telegram http", r.status)
    except Exception as e:
        log("telegram error:", e)

def load_state():
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except Exception:
        return {"last_seen": {}, "last_alert": {}}
def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f: json.dump(state, f)
    os.replace(tmp, STATE_FILE)

def minutes_since(ts): return (time.time() - ts) / 60.0
def now_hhmm(): return dt.datetime.now().strftime("%H:%M")

def parse_zone_from_cause(cause):
    if not cause: return ""
    parts = cause.split(":", 1)
    if len(parts) == 2: return parts[1].strip().split(",")[0].strip()
    return cause.strip()

def parse_events(msg):
    try: data = json.loads(msg)
    except Exception: return []
    out, batch = [], []
    for k in ("events","Events","items"):
        if isinstance(data.get(k), list): batch += data.get(k)
    if not batch: batch = [data]
    for obj in batch:
        eid = obj.get("eid") or obj.get("event_id") or obj.get("EventID") or obj.get("eventId") or data.get("eid")
        mid = obj.get("mid") or obj.get("monitor_id") or obj.get("MonitorID") or obj.get("monitorId") or data.get("mid")
        cause = obj.get("cause") or data.get("cause") or ""
        if eid and mid: out.append({"eid": str(eid), "mid": str(mid), "cause": str(cause)})
    return out

class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ws_url = cfg.get("ws_url", "ws://127.0.0.1:9000")
        self.state = load_state()
        self.lock = threading.Lock()

    def note(self, mid, zone):
        key = f"{mid}:{zone}"
        with self.lock:
            self.state["last_seen"][key] = time.time()
            save_state(self.state)

    def should_alert(self, key, suppress_min):
        last = self.state["last_alert"].get(key, 0)
        return minutes_since(last) > suppress_min

    def mark_alert(self, key):
        with self.lock:
            self.state["last_alert"][key] = time.time()
            save_state(self.state)

    def check_loop(self):
        while True:
            try:
                sup = float(self.cfg.get("suppress_minutes", 30))
                for mid, mconf in (self.cfg.get("monitors") or {}).items():
                    mname = mconf.get("name", f"Monitor {mid}")
                    for zname, zconf in (mconf.get("zones") or {}).items():
                        max_idle = float(zconf.get("max_inactive_minutes", 60))
                        key = f"{mid}:{zname}"
                        last = self.state["last_seen"].get(key)
                        if not last: continue
                        idle = minutes_since(last)
                        if idle > max_idle and self.should_alert(key, sup):
                            send_telegram(f"🐭 iMouse Alert\nMonitor: {mname} (ID {mid})\nZone: {zname}\nNo activity for {idle:.0f} min (threshold {max_idle:.0f})")
                            self.mark_alert(key)
                time.sleep(60)
            except Exception as e:
                log("check loop error:", e); time.sleep(5)

    def ws_loop(self):
        backoff = 2
        while True:
            try:
                log("connecting WS", self.ws_url)
                ws = create_connection(self.ws_url, timeout=5, ping_interval=30, ping_timeout=10)
                ws.settimeout(300)
                ws.send(json.dumps({"event":"auth","data":{"user":"","password":""}}))
                log("connected")
                backoff = 2
                while True:
                    msg = ws.recv()
                    if not msg: continue
                    for e in parse_events(msg):
                        mid = e["mid"]
                        mconf = (self.cfg.get("monitors") or {}).get(mid)
                        if not mconf: continue
                        zone_hint = parse_zone_from_cause(e["cause"])
                        for zname, zconf in mconf.get("zones", {}).items():
                            kw = (zconf.get("keyword") or "").lower()
                            if kw and kw in zone_hint.lower():
                                self.note(mid, zname)
                                log(f"activity mid={mid} zone={zname} cause='{e['cause']}'")
            except Exception as e:
                log("ws error:", e)
                time.sleep(backoff); backoff = min(backoff*2, 30)

def simulate(mid, zone):
    st = load_state()
    st.setdefault("last_seen", {})[f"{mid}:{zone}"] = time.time()
    save_state(st); log(f"SIM activity mid={mid} zone={zone}")

def main():
    cfg = load_yaml(CONF)
    if len(sys.argv) >= 2 and sys.argv[1] == "--simulate":
        simulate(sys.argv[2], sys.argv[3]); return 0
    eng = Engine(cfg)
    threading.Thread(target=eng.check_loop, daemon=True).start()
    eng.ws_loop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
