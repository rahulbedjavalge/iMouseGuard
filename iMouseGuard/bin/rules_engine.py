#!/usr/bin/env python3
import os, sys, json, time, threading, datetime as dt
import urllib.parse, urllib.request
from websocket import create_connection
import yaml

CONF = "/opt/iMouseGuard/config/rules.yaml"
ENV_FILES = ["/opt/iMouseGuard/env/prod.env"]
STATE_FILE = "/opt/iMouseGuard/state/last_seen.json"
LOG_FILE = "/opt/iMouseGuard/logs/rules.log"

# ---------------- utils ----------------

def log(*a):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = " ".join(str(x) for x in a)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} | {msg}\n")
    print(ts, "|", msg, flush=True)

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def _clean(val):
    if val is None: return ""
    s = str(val).strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s.replace("\r","").replace("\n","").strip()

def get_env(name):
    v = os.getenv(name)
    if v: return _clean(v)
    for p in ENV_FILES:
        try:
            with open(p) as f:
                for line in f:
                    line=line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith(f"export {name}="):
                        return _clean(line.split("=",1)[1])
        except Exception:
            pass
    return ""

# ---------------- telegram ----------------

def send_telegram(text, topic=None):
    token  = get_env("TELEGRAM_TOKEN")
    chat   = get_env("TELEGRAM_CHAT_ID")
    thread = get_env("TELEGRAM_THREAD_ID")  # default

    # allow per-topic threads
    if topic == "litter":
        thread = get_env("TELEGRAM_THREAD_ID_LITTER") or thread
    elif topic == "drink":
        thread = get_env("TELEGRAM_THREAD_ID_DRINK") or thread

    if not token or not chat:
        log("telegram creds missing (TELEGRAM_TOKEN/TELEGRAM_CHAT_ID)")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat, "text": text}
    if thread:
        params["message_thread_id"] = thread

    data = urllib.parse.urlencode(params).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != 200:
                log("telegram http", r.status)
    except Exception as e:
        log("telegram error:", e)

def send_whatsapp(text):
    """Send WhatsApp alert via whatsapp_call.py if enabled."""
    enabled = get_env("ENABLE_WHATSAPP") == "1"
    if not enabled:
        return
    
    import subprocess
    # Determine paths based on OS
    if os.name == 'nt':  # Windows
        python_exe = "D:/iMouseGuard/.venv/Scripts/python.exe"
        script_path = "d:\\iMouseGuard\\iMouseGuard\\bin\\whatsapp_call.py"
    else:  # Linux/Unix
        python_exe = "/opt/iMouseGuard/venv/bin/python"
        script_path = "/opt/iMouseGuard/bin/whatsapp_call.py"
    
    # Build environment with required variables
    env = os.environ.copy()
    env["ENABLE_WHATSAPP"] = "1"
    for key in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "WHATSAPP_TO"]:
        val = get_env(key)
        if val:
            env[key] = val
    
    try:
        p = subprocess.Popen(
            [python_exe, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        payload = json.dumps({"message": text})
        stdout, stderr = p.communicate(input=payload.encode("utf-8"), timeout=10)
        if p.returncode != 0:
            log(f"whatsapp failed (rc={p.returncode}):", stderr.decode()[:200])
    except Exception as e:
        log("whatsapp error:", e)

# ---------------- state ----------------

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"last_seen": {}, "last_alert": {}}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)

def minutes_since(ts):
    return (time.time() - ts) / 60.0

# ---------------- ES parsing ----------------

def parse_zone_from_cause(cause):
    if not cause: return ""
    # e.g. "Linked: Litter Zone, obj: motion" -> "Litter Zone"
    parts = cause.split(":", 1)
    if len(parts) == 2:
        return parts[1].strip().split(",")[0].strip()
    return cause.strip()

def parse_events(msg):
    try:
        data = json.loads(msg)
    except Exception:
        return []
    out, batch = [], []
    for k in ("events","Events","items"):
        if isinstance(data.get(k), list):
            batch += data.get(k)
    if not batch:
        batch = [data]
    for obj in batch:
        eid = (obj.get("eid") or obj.get("event_id") or obj.get("EventID") or
               obj.get("eventId") or data.get("eid") or "")
        mid = (obj.get("mid") or obj.get("monitor_id") or obj.get("MonitorID") or
               obj.get("monitorId") or data.get("mid") or "")
        cause = obj.get("cause") or data.get("cause") or ""
        if str(eid) and str(mid):
            out.append({"eid": str(eid), "mid": str(mid), "cause": str(cause)})
    return out

# ---------------- engine ----------------

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

    def _alert_text(self, mname, mid, zname, idle, threshold):
        # specialized copy for litter/drink
        zlow = zname.lower()
        if "litter" in zlow:
            return (f"🐭 Mouse not in litter zone for {idle:.0f} minutes "
                    f"(threshold {threshold:.0f}m)\nMonitor: {mname} (ID {mid})")
        if "drink" in zlow or "water" in zlow:
            return (f"🐭 Mouse not drinking for {idle:.0f} minutes "
                    f"(threshold {threshold:.0f}m)\nMonitor: {mname} (ID {mid})")
        # generic
        return (f"🐭 No activity in '{zname}' for {idle:.0f} minutes "
                f"(threshold {threshold:.0f}m)\nMonitor: {mname} (ID {mid})")

    def _topic_for_zone(self, zname):
        zlow = zname.lower()
        if "litter" in zlow:
            return "litter"
        if "drink" in zlow or "water" in zlow:
            return "drink"
        return None

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
                        if not last:
                            continue
                        idle = minutes_since(last)
                        if idle > max_idle and self.should_alert(key, sup):
                            text  = self._alert_text(mname, mid, zname, idle, max_idle)
                            topic = self._topic_for_zone(zname)
                            send_telegram(text, topic=topic)
                            send_whatsapp(text)
                            self.mark_alert(key)
                time.sleep(60)
            except Exception as e:
                log("check loop error:", e)
                time.sleep(5)

    def ws_loop(self):
        backoff = 2
        while True:
            try:
                log("connecting WS", self.ws_url)
                ws = create_connection(self.ws_url, timeout=5, ping_interval=30, ping_timeout=10)
                ws.settimeout(300)
                # ES is fine with empty auth when auth is disabled
                ws.send(json.dumps({"event":"auth","data":{"user":"","password":""}}))
                log("connected")
                backoff = 2
                while True:
                    msg = ws.recv()
                    if not msg:
                        continue
                    for e in parse_events(msg):
                        mid = e["mid"]
                        mconf = (self.cfg.get("monitors") or {}).get(mid)
                        if not mconf:
                            continue
                        zone_hint = parse_zone_from_cause(e["cause"])
                        for zname, zconf in mconf.get("zones", {}).items():
                            kw = (zconf.get("keyword") or "").lower()
                            if kw and kw in zone_hint.lower():
                                self.note(mid, zname)
                                log(f"activity mid={mid} zone={zname} cause='{e['cause']}'")
            except Exception as e:
                log("ws error:", e)
                time.sleep(backoff)
                backoff = min(backoff*2, 30)

# ---------------- test helpers ----------------

def simulate(mid, zone):
    st = load_state()
    st.setdefault("last_seen", {})[f"{mid}:{zone}"] = time.time()
    save_state(st)
    log(f"SIM activity mid={mid} zone={zone}")

def backdate(mid, zone, minutes):
    st = load_state()
    st.setdefault("last_seen", {})[f"{mid}:{zone}"] = time.time() - (minutes*60)
    save_state(st)
    log(f"BACKDATE mid={mid} zone={zone} by {minutes}m")

def clear_state():
    save_state({"last_seen": {}, "last_alert": {}})
    log("STATE cleared")

def one_shot_check(cfg):
    # run a single pass of the checker (no websocket)
    eng = Engine(cfg)
    sup = float(cfg.get("suppress_minutes", 30))
    for mid, mconf in (cfg.get("monitors") or {}).items():
        mname = mconf.get("name", f"Monitor {mid}")
        for zname, zconf in (mconf.get("zones") or {}).items():
            max_idle = float(zconf.get("max_inactive_minutes", 60))
            key = f"{mid}:{zname}"
            last = eng.state["last_seen"].get(key)
            if not last:
                continue
            idle = minutes_since(last)
            if idle > max_idle and eng.should_alert(key, sup):
                text  = eng._alert_text(mname, mid, zname, idle, max_idle)
                topic = eng._topic_for_zone(zname)
                send_telegram(text, topic=topic)
                send_whatsapp(text)
                eng.mark_alert(key)
                log("ONE-SHOT alerted:", text)

# ---------------- main ----------------

def main():
    cfg = load_yaml(CONF)

    # CLI helpers:
    #   --simulate MID ZONE
    #   --backdate MID ZONE 10m|90m
    #   --clear-state
    #   --check   (single pass without WS)
    if len(sys.argv) >= 2:
        cmd = sys.argv[1]
        if cmd == "--simulate":
            if len(sys.argv) < 4: print("usage: --simulate MID ZONE"); return 2
            simulate(sys.argv[2], sys.argv[3]); return 0
        if cmd == "--backdate":
            if len(sys.argv) < 5: print("usage: --backdate MID ZONE <Nm>"); return 2
            amt = sys.argv[4].lower().rstrip("m")
            minutes = float(amt)
            backdate(sys.argv[2], sys.argv[3], minutes); return 0
        if cmd == "--clear-state":
            clear_state(); return 0
        if cmd == "--check":
            one_shot_check(cfg); return 0

    eng = Engine(cfg)
    threading.Thread(target=eng.check_loop, daemon=True).start()
    eng.ws_loop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
