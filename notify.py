"""After-publish jobs for new Egyptaway posts, every 30 minutes on GitHub Actions (.github/workflows/notify.yml):

1. IndexNow: tells Bing, Yandex, Seznam and Naver about every new live post right away (key file is served at the site root
   by the Cloudflare Worker egyptaway-push-sw).
2. Telegram: posts each new live post to the channel @egyptaway1 (needs secret TELEGRAM_BOT_TOKEN; the bot must be an admin).
3. Web push via OneSignal: the newest post, with a daily cap, a minimum gap between pushes and quiet hours at night so people
   don't switch notifications off (needs secret ONESIGNAL_API_KEY).
Env: PER_DAY (default 6), GAP_MIN (default 90), DRY_RUN=1 to only print, FORCE=1 to ignore quiet hours/gap/cap for a test push.
"""
import datetime, html, json, os, re, sys
import requests
import football as f

APP_ID = "c6f8318f-a6ce-4e8d-b9f0-f329f31e2a72"
INDEXNOW_KEY = "e3b3e2ee8cd741f59f1b91e73c0f9090"
CHANNEL = "@egyptaway1"
PER_DAY = int(os.environ.get("PER_DAY") or 6)
GAP_MIN = int(os.environ.get("GAP_MIN") or 90)
QUIET = range(0, 9)  # Cairo hours with no pushes
LOOKBACK_H = 4
TG_PER_RUN = 3


def snippet(body, n=110):
    body = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", body or "", flags=re.S | re.I)
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", " ", p))
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 40:
            return t[:n].rsplit(" ", 1)[0] + "…" if len(t) > n else t
    return "اضغط واقرأ التفاصيل على ايجبتاوى"


def first_image(body):
    m = re.search(r'<img[^>]+src="(https://[^"]+)"', body or "")
    return html.unescape(m.group(1)) if m else None


def indexnow(urls, dry):
    if not urls:
        return True
    body = {"host": "www.egyptaway.com", "key": INDEXNOW_KEY,
            "keyLocation": f"https://www.egyptaway.com/{INDEXNOW_KEY}.txt", "urlList": urls}
    if dry:
        print("IndexNow would submit", len(urls))
        return False
    r = requests.post("https://api.indexnow.org/indexnow", json=body, timeout=30)
    print("IndexNow", r.status_code, len(urls), "url(s)")
    return r.status_code in (200, 202)


def telegram(p, dry):
    tok = f.secret("TELEGRAM_BOT_TOKEN")
    title = html.unescape(p["title"])
    url = p["url"].replace("http://", "https://")
    text = f"<b>{html.escape(title)}</b>\n\n{html.escape(snippet(p.get('content'), 300))}\n\n🔗 {url}"
    img = first_image(p.get("content"))
    if dry or not tok:
        print("Telegram", "(dry)" if dry else "(no TELEGRAM_BOT_TOKEN)", title)
        return False
    api = f"https://api.telegram.org/bot{tok}/"
    if img:
        r = requests.post(api + "sendPhoto", data={"chat_id": CHANNEL, "photo": img, "caption": text[:1024], "parse_mode": "HTML"}, timeout=30)
        if r.ok:
            return True
        print("  photo failed, sending text:", r.status_code, r.text[:150])
    r = requests.post(api + "sendMessage", data={"chat_id": CHANNEL, "text": text, "parse_mode": "HTML"}, timeout=30)
    print("Telegram", r.status_code, r.text[:150] if not r.ok else title)
    return r.ok


def facebook(p, dry):
    tok, page = f.secret("FB_PAGE_TOKEN"), f.secret("FB_PAGE_ID")
    if dry or not tok or not page:
        print("Facebook", "(dry)" if dry else "(no FB_PAGE_TOKEN/FB_PAGE_ID)", p["title"][:60])
        return False
    title = html.unescape(p["title"])
    msg = f"{title}\n\n{snippet(p.get('content'), 220)}"
    r = requests.post(f"https://graph.facebook.com/v21.0/{page}/feed", timeout=30,
                      data={"message": msg, "link": p["url"].replace("http://", "https://"), "access_token": tok})
    print("Facebook", r.status_code, r.text[:150] if not r.ok else title)
    return r.ok


def push(posts, state, now, key, dry, force):
    today = now.date().isoformat()
    if not key and not dry:
        print("ONESIGNAL_API_KEY secret is missing, no push")
        return
    if now.hour in QUIET and not force:
        print("push: quiet hours")
        return
    if len([s for s in state["sent"] if s.get("at", "").startswith(today)]) >= PER_DAY and not force:
        print(f"push: daily cap reached ({PER_DAY})")
        return
    if state["sent"] and not force:
        last = datetime.datetime.fromisoformat(state["sent"][-1]["at"])
        if (now - last).total_seconds() < GAP_MIN * 60:
            print("push: last one was less than", GAP_MIN, "minutes ago")
            return
    done = {s["url"] for s in state["sent"]}
    posts = [p for p in posts if p["url"] not in done]
    if not posts:
        print("push: no new posts")
        return
    p = posts[-1]
    title = html.unescape(p["title"])
    url = p["url"].replace("http://", "https://")
    msg = {"app_id": APP_ID, "target_channel": "push", "included_segments": ["Total Subscriptions"],
           "headings": {"en": title, "ar": title}, "contents": {"en": snippet(p.get("content")), "ar": snippet(p.get("content"))},
           "web_url": url + "?utm_source=push&utm_medium=onesignal", "name": "auto " + url.split("/")[-1][:40]}
    img = first_image(p.get("content"))
    if img:
        msg["chrome_web_image"] = img
    if dry:
        print(json.dumps(msg, ensure_ascii=False, indent=1))
        return
    r = requests.post("https://api.onesignal.com/notifications?c=push", json=msg, timeout=30,
                      headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
    print("OneSignal", r.status_code, r.text[:300])
    if r.status_code >= 400:
        print("OneSignal failed gracefully, continuing.")
        return
    if not r.json().get("id"):
        print("push: not sent (no subscribers yet?)")
        return
    state["sent"].append({"url": p["url"], "title": title, "at": now.isoformat(timespec="seconds")})
    print("PUSHED", title, url)


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    force = os.environ.get("FORCE") == "1"
    try:
        state = json.load(open("notify_sent.json", encoding="utf-8"))
    except Exception:
        state = {}
    for k in ("sent", "indexed", "tg", "fb"):
        state.setdefault(k, [])
    now = datetime.datetime.now(f.CAIRO)
    tok = f.token()
    since = (now - datetime.timedelta(hours=24 if force else LOOKBACK_H)).isoformat(timespec="seconds")
    res = f.api("GET", f"/blogs/{f.BLOG}/posts", tok, {"status": "live", "startDate": since, "maxResults": 20,
                                                      "fetchBodies": "true", "fetchImages": "true"})
    posts = sorted([p for p in res.get("items", []) if p.get("url")], key=lambda x: x["published"])
    print(len(posts), "live post(s) in the window")

    new = [p["url"].replace("http://", "https://") for p in posts if p["url"] not in state["indexed"]]
    try:
        if indexnow(new, dry):
            state["indexed"] += [p["url"] for p in posts if p["url"] not in state["indexed"]]
    except Exception as ex:
        print("IndexNow step error:", ex)

    for p in [p for p in posts if p["url"] not in state["tg"]][:TG_PER_RUN]:
        try:
            if telegram(p, dry):
                state["tg"].append(p["url"])
        except Exception as ex:
            print("Telegram step error:", ex)

    for p in [p for p in posts if p["url"] not in state["fb"]][:2]:
        try:
            if facebook(p, dry):
                state["fb"].append(p["url"])
        except Exception as ex:
            print("Facebook step error:", ex)

    try:
        push(posts, state, now, f.secret("ONESIGNAL_API_KEY"), dry, force)
    except Exception as ex:
        print("Push step error:", ex)

    for k in ("sent", "indexed", "tg", "fb"):
        state[k] = state[k][-400:]
    if not dry:
        json.dump(state, open("notify_sent.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
