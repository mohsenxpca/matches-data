"""Per-team match pushes (mohsen 2026-11-02): people who star a team on /p/matches-today.html get a OneSignal tag
tm_<hash(team)>; this sends them at most 2 pushes per match: ~1 hour before kick-off (time + channel) and the final
score ~2h20m after kick-off. Score only, never stream links. Runs from live.yml (every 5 minutes); state in team_push_state.json.
Env: ONESIGNAL_API_KEY, DRY_RUN=1 to only print.
"""
import datetime, json, os
from zoneinfo import ZoneInfo
import requests

APP_ID = "c6f8318f-a6ce-4e8d-b9f0-f329f31e2a72"
CAIRO = ZoneInfo("Africa/Cairo")
PAGE = "https://www.egyptaway.com/p/matches-today.html"
STATE = "team_push_state.json"
QUIET = range(3, 9)  # Cairo hours with no pushes (matches end by ~3am)
PRE = (50, 70)       # minutes before kick-off
DONE = 140           # a match counts as finished 2h20m after kick-off (same as results.py)


def tag(team):
    """Same hash as the page script: djb2 over UTF-16 code units -> 'tm_<hex>'."""
    h, b = 5381, team.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = (h * 33 + (b[i] | b[i + 1] << 8)) & 0xFFFFFFFF
    return f"tm_{h:x}"


def send(m, heading, text, key, dry):
    filters = [{"field": "tag", "key": tag(m["h"]), "relation": "=", "value": "1"}, {"operator": "OR"},
               {"field": "tag", "key": tag(m["a"]), "relation": "=", "value": "1"}]
    msg = {"app_id": APP_ID, "target_channel": "push", "filters": filters, "headings": {"ar": heading, "en": heading},
           "contents": {"ar": text, "en": text}, "web_url": PAGE + "?utm_source=push&utm_medium=team",
           "name": "team " + key[:60], "ttl": 3600}
    if dry:
        print("DRY", heading, "|", text)
        return True
    r = requests.post("https://api.onesignal.com/notifications?c=push", json=msg, timeout=30,
                      headers={"Authorization": "Key " + os.environ["ONESIGNAL_API_KEY"]})
    print("OneSignal", r.status_code, r.text[:200])
    return r.status_code < 300


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    if not dry and not os.environ.get("ONESIGNAL_API_KEY"):
        print("ONESIGNAL_API_KEY missing, no team pushes")
        return
    now = datetime.datetime.now(CAIRO)
    if now.hour in QUIET and not dry:
        return
    data = json.load(open("data.json", encoding="utf-8"))
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    cutoff = (now - datetime.timedelta(days=3)).date().isoformat()
    state = {k: v for k, v in state.items() if k[:10] >= cutoff}
    sent = 0
    for m in data.get("matches", []):
        try:
            ko = datetime.datetime.fromisoformat(f"{m['d']}T{m['t']}").replace(tzinfo=CAIRO)
        except Exception:
            continue
        mins = (now - ko).total_seconds() / 60
        base = f"{m['d']}|{m['h']}|{m['a']}"
        vs = f"{m['h']} × {m['a']}"
        ch = m.get("c") if m.get("c") and m.get("c") != "لم تُعلن" else ""
        if -PRE[1] <= mins <= -PRE[0] and base + "|pre" not in state:
            if send(m, f"⚽ {vs} كمان ساعة", f"الماتش الساعة {m['t']} بتوقيت القاهرة" + (f" على {ch}" if ch else "") + f" · {m['l']}",
                    base + "|pre", dry):
                state[base + "|pre"] = now.isoformat(timespec="minutes")
                sent += 1
        elif DONE <= mins <= DONE + 120 and m.get("s") and "-" in m["s"] and base + "|ft" not in state:
            h, a = m["s"].split("-", 1)
            if send(m, f"🏁 انتهت: {m['h']} {h} - {a} {m['a']}", f"النتيجة النهائية · {m['l']}" + (f" · {m['r']}" if m.get("r") else ""),
                    base + "|ft", dry):
                state[base + "|ft"] = now.isoformat(timespec="minutes")
                sent += 1
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("team pushes sent:", sent)


if __name__ == "__main__":
    main()
