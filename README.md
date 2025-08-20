Here’s a drop-in **README.md** you can copy/paste into your repo. It’s written so a new person can set up iMouseGuard quickly and understand how it fits together.

---

# iMouseGuard

Lightweight alerting layer on top of ZoneMinder’s Event Server (ES).
It listens to ES WebSocket events, enriches each event via the ZoneMinder API, and posts clean alerts to a Telegram group/topic.

## What you get

* 📡 Reliable event forwarding from the ES (port 9000)
* 🔎 Enriched alerts (monitor name, cause/zone, scores, direct “View Event” link)
* 💬 Telegram delivery to a group **topic/thread**
* 🩺 Simple guard scripts to start/stop/status and auto-heal the ES + forwarder
* 📁 One tidy folder: `/opt/iMouseGuard` (code, config, env, logs, vendor)

---

## Architecture (at a glance)

```
ZoneMinder (API + ES:9000)
         │ (WebSocket)
         ▼
 zmes_ws_to_telegram.py  ──(stdin JSON)──▶  imouse_hook_alert.py
         │                                       │
         └─────────── guard scripts manage both ─┘
                                       │
                                       ▼
                                 Telegram Bot
```

---

## Folder layout

```
/opt/iMouseGuard
├─ bin/                      # runnable scripts
│  ├─ zmes_ws_to_telegram.py
│  ├─ imouse_hook_alert.py
│  ├─ es-start  es-stop
│  ├─ fwd-start fwd-stop
│  ├─ guard-start guard-stop guard-status guard-watch
├─ config/
│  └─ zmeventnotification.ini
├─ env/
│  └─ prod.env              # exported environment vars
├─ logs/
│  ├─ es.log
│  ├─ forwarder.log
│  └─ guard.log
├─ vendor/
│  └─ zmeventnotification/  # ES source (perl script + docs)
└─ venv/                    # python virtual environment
```

---

## Prerequisites

* ZoneMinder running and reachable from this host/container (API and DB OK).
* ES Perl deps (installed once):
  `cpanm JSON JSON::XS Net::WebSocket::Server`
  (If `cpanm` isn’t present: `apt-get update && apt-get install -y cpanminus`.)

---

## Quick start (≈ 60 seconds)

```bash
# 1) Create base tree
sudo mkdir -p /opt/iMouseGuard/{bin,config,env,logs,vendor}
sudo chown -R root:root /opt/iMouseGuard

# 2) Python venv + deps
python3 -m venv /opt/iMouseGuard/venv
/opt/iMouseGuard/venv/bin/pip install --upgrade pip
/opt/iMouseGuard/venv/bin/pip install websocket-client requests

# 3) Environment file (edit values!)
cat >/opt/iMouseGuard/env/prod.env <<'EOF'
export TELEGRAM_TOKEN='YOUR_TELEGRAM_BOT_TOKEN'
export TELEGRAM_CHAT_ID='-100XXXXXXXXXX'      # group ID (negative for supergroup)
export TELEGRAM_THREAD_ID='3'                 # topic id (optional)
export IMOUSE_API_BASE='http://127.0.0.1'     # ZM API base
export IMOUSE_WEB_BASE='http://10.0.2.2'      # for “View Event” link
export WS_URL='ws://127.0.0.1:9000'           # ES WebSocket endpoint
export WS_SEND_AUTH=0                         # 1 to send ES credentials
export ES_USER=''
export ES_PASSWORD=''
EOF
chmod 600 /opt/iMouseGuard/env/prod.env
. /opt/iMouseGuard/env/prod.env

# 4) Put your two Python scripts into /opt/iMouseGuard/bin (chmod +x them)
#    (zmes_ws_to_telegram.py and imouse_hook_alert.py)

# 5) Place zmeventnotification (vendor) and a minimal config:
cat >/opt/iMouseGuard/config/zmeventnotification.ini <<'EOF'
[general]
port = 9000
address = ::
event_check_interval = 5
monitor_reload_interval = 300
verbose = yes
es_debug_level = 5
send_event_start_notification = yes
send_event_end_notification = no

[auth]
enable = no

[ssl]
enable = no

[hook]
enable = no

[push]
enable = fcm
EOF

# 6) Start ES and forwarder
/opt/iMouseGuard/bin/es-start
/opt/iMouseGuard/bin/fwd-start

# 7) Check status/logs
/opt/iMouseGuard/bin/guard-status
tail -n 60 /opt/iMouseGuard/logs/{es.log,forwarder.log}
```

---

## Scripts & usage

### Event forwarder

`bin/zmes_ws_to_telegram.py`

* Connects to `WS_URL` (ES port 9000) and receives alarm frames.
* For each new event, calls the hook (`imouse_hook_alert.py`) with:

  * argv: `eid`, `mid`
  * stdin JSON payload (`behavior`, `notes`, monitor name if present)

Start/stop:

```bash
/opt/iMouseGuard/bin/fwd-start
/opt/iMouseGuard/bin/fwd-stop
```

### Telegram hook

`bin/imouse_hook_alert.py`

* Reads env from `env/prod.env` (no secrets hard-coded).
* Looks up event/monitor via ZM API (`/api/events/view/{eid}.json`, `/api/monitors/view/{mid}.json`).
* Builds a clean message and posts to Telegram (uses `TELEGRAM_THREAD_ID` if set).

> If your ZM web is not `127.0.0.1`, set `IMOUSE_WEB_BASE` so “View Event” opens correctly.

### Guard helpers

* `es-start` / `es-stop` – run/stop the Perl ES with our config into `logs/es.log`.
* `fwd-start` / `fwd-stop` – run/stop the forwarder into `logs/forwarder.log`.
* `guard-status` – quick health check (are ES & forwarder up? is port 9000 listening?)
* `guard-watch` – tiny loop that restarts ES if port 9000 stops listening and restarts the forwarder if it dies.
  You can run it persistently via `nohup` or a simple `cron @reboot`.

Example `cron` entry:

```bash
# crontab -e
@reboot /opt/iMouseGuard/bin/guard-start
* * * * * /opt/iMouseGuard/bin/guard-watch
```

---

## Environment variables

| Name                    | What it does                                               |
| ----------------------- | ---------------------------------------------------------- |
| `TELEGRAM_TOKEN`        | Bot token (from @BotFather).                               |
| `TELEGRAM_CHAT_ID`      | Target chat (group) ID.                                    |
| `TELEGRAM_THREAD_ID`    | Topic/thread ID inside the group (optional).               |
| `IMOUSE_API_BASE`       | Base URL for ZM API (e.g., `http://127.0.0.1`).            |
| `IMOUSE_WEB_BASE`       | Base URL for web links (e.g., `http://10.0.2.2`).          |
| `WS_URL`                | ES WebSocket URL (`ws://127.0.0.1:9000`).                  |
| `WS_SEND_AUTH`          | `1` to send ES credentials, else blank auth frame is sent. |
| `ES_USER`/`ES_PASSWORD` | If ES auth is enabled.                                     |

Load into current shell:

```bash
. /opt/iMouseGuard/env/prod.env
```

---

## Logs

* ES: `/opt/iMouseGuard/logs/es.log`
* Forwarder: `/opt/iMouseGuard/logs/forwarder.log`
* Guard: `/opt/iMouseGuard/logs/guard.log`

Helpful tails:

```bash
tail -n 80 /opt/iMouseGuard/logs/es.log
tail -n 80 /opt/iMouseGuard/logs/forwarder.log
```

---

## Troubleshooting

**ES not listening on 9000**

* Check `/opt/iMouseGuard/logs/es.log` first lines for missing Perl modules.

  * Install: `cpanm JSON JSON::XS Net::WebSocket::Server`
* Confirm the config path in `es-start` matches `config/zmeventnotification.ini`.

**Forwarder says “Connection refused”**

* ES isn’t up or port isn’t open inside this container/host.
  Run: `ss -ltnp | grep :9000` (or `netstat -lntp`)
  Start ES: `/opt/iMouseGuard/bin/es-start`

**Telegram error: “URL can’t contain control characters”**

* Your token/chat/thread env values probably have stray quotes or spaces.
  Open `env/prod.env`, remove quotes around numbers, ensure one value per line:

  ```
  export TELEGRAM_TOKEN='123:ABC...'     # quotes fine for token
  export TELEGRAM_CHAT_ID=-1002597925763 # no quotes for pure numbers
  export TELEGRAM_THREAD_ID=3            # optional, numeric
  ```

**Event links open to 127.0.0.1**

* Set `IMOUSE_WEB_BASE` to your browser-reachable address, e.g., `http://10.0.2.2`.

**Lots of “Use of uninitialized value …” lines in es.log**

* These are harmless warnings from ES when some fields are blank.
  They don’t affect alerting.

---

## Security notes

* Keep `env/prod.env` mode `600` (`chmod 600`) to protect the bot token.
* If you need TLS or ES auth, enable it in `config/zmeventnotification.ini` and set `WS_SEND_AUTH=1`.

---

## Uninstall

```bash
/opt/iMouseGuard/bin/fwd-stop || true
/opt/iMouseGuard/bin/es-stop  || true
rm -rf /opt/iMouseGuard
```

---

## Appendix: What the scripts do

### `zmes_ws_to_telegram.py` (forwarder)

* Maintains a WebSocket connection to the ES (reconnects with backoff).
* Normalizes different ES payload shapes (different field names across ES versions).
* Debounces duplicate event IDs.
* Triggers the hook for each unique event.

### `imouse_hook_alert.py` (hook)

* Accepts `(eid, mid)` on argv and JSON on stdin.
* Calls ZM API to enrich the alert (event timing, max score, monitor name).
* Posts a formatted message to Telegram (optionally in a thread).

---

If you want, I can also generate a minimal `es-start`, `fwd-start`, and `guard-watch` for your repo so this README exactly matches your files.

