"""Morning reminder for «مين اللاعب؟» (/p/who-is-player.html), only to people who pressed «فكّرني كل يوم» (OneSignal tag
daily_game). One push a day; game_push_state.json keeps the last date so a re-run can't send twice.
Env: ONESIGNAL_API_KEY, DRY_RUN=1.
"""
import datetime, json, os
from zoneinfo import ZoneInfo
import requests

STATE = "game_push_state.json"
URL = "https://www.egyptaway.com/p/who-is-player.html"


def main():
    today = datetime.datetime.now(ZoneInfo("Africa/Cairo")).date()
    num = (today - datetime.date(2026, 11, 2)).days + 1
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if st.get("last") == today.isoformat():
        print("already sent today")
        return
    msg = {"app_id": "c6f8318f-a6ce-4e8d-b9f0-f329f31e2a72", "target_channel": "push",
           "filters": [{"field": "tag", "key": "daily_game", "relation": "exists"}],
           "headings": {"ar": f"⚽ مين اللاعب؟ #{num}", "en": f"Who is the player? #{num}"},
           "contents": {"ar": "لاعب النهارده جاهز. تعرفه من أول تلميح؟", "en": "Today's player is ready"},
           "web_url": URL + "?utm_source=push&utm_medium=game", "name": f"game {num}"}
    if os.environ.get("DRY_RUN") == "1" or not os.environ.get("ONESIGNAL_API_KEY"):
        print("DRY/no key", msg["headings"]["ar"])
        return
    r = requests.post("https://api.onesignal.com/notifications?c=push", json=msg, timeout=30,
                      headers={"Authorization": "Key " + os.environ["ONESIGNAL_API_KEY"]})
    print("OneSignal", r.status_code, r.text[:200])
    if r.status_code < 300:
        json.dump({"last": today.isoformat()}, open(STATE, "w"))


if __name__ == "__main__":
    main()
