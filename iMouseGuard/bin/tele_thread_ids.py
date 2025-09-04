# tele_thread_ids.py
# Usage:
#   python tele_thread_ids.py --token <BOT_TOKEN> --chat -1001234567890
# Or if env vars are set:
#   export TELEGRAM_BOT_TOKEN=...; export TELEGRAM_CHAT_ID=-100...
#   python tele_thread_ids.py

import os, sys, json, argparse, urllib.request, urllib.parse

def api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.load(r)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"))
    p.add_argument("--chat", default=os.getenv("TELEGRAM_CHAT_ID"))
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--clear-webhook", action="store_true", help="delete webhook if set")
    args = p.parse_args()

    if not args.token:
        print("Missing bot token. Use --token or set TELEGRAM_BOT_TOKEN.")
        sys.exit(1)
    if not args.chat:
        print("Missing chat id. Use --chat or set TELEGRAM_CHAT_ID.")
        sys.exit(1)

    # sanity check
    me = api(args.token, "getMe")
    if not me.get("ok"):
        print("Token check failed:", me)
        sys.exit(1)

    if args.clear_webhook:
        api(args.token, "deleteWebhook")

    # fetch updates
    resp = api(args.token, "getUpdates", {"limit": args.limit})
    results = resp.get("result", [])
    if not results:
        print("No updates. In each topic, send a message like '@YourBotUsername LITTER PING' and rerun.")
        return

    seen = set()
    hits = []
    for u in results:
        msg = u.get("message") or u.get("edited_message") or {}
        if not msg:
            continue
        chat_id = str(msg.get("chat", {}).get("id"))
        if chat_id != str(args.chat):
            continue
        thread_id = msg.get("message_thread_id")
        text = msg.get("text") or ""
        if thread_id is not None:
            key = (chat_id, thread_id)
            if key not in seen:
                seen.add(key)
                hits.append((thread_id, text))

    if not hits:
        print("No topic messages found for this chat. Make sure you posted in the forum topics.")
        return

    print("Topic thread IDs seen for chat", args.chat)
    for thr, text in hits:
        tag = ""
        up = text.upper()
        if "LITTER" in up:
            tag = "  # likely Litter topic"
        elif "DRINK" in up:
            tag = "  # likely Drinking topic"
        print(f"  thread_id={thr}  text={text!r}{tag}")

    # helpful export lines
    litter = next((thr for thr, t in hits if "LITTER" in (t or "").upper()), None)
    drink  = next((thr for thr, t in hits if "DRINK"  in (t or "").upper()), None)
    if litter or drink:
        print("\nSuggested env lines:")
        if litter:
            print(f"TELEGRAM_THREAD_ID_LITTER={litter}")
        if drink:
            print(f"TELEGRAM_THREAD_ID_DRINKING={drink}")

if __name__ == "__main__":
    main()
