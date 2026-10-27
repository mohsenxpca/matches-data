"""Trending-topic posts on Egyptaway from Google Trends (Egypt + Saudi Arabia), every 3 hours.

Picks the hottest topic we haven't covered (and that isn't crime/suicide/etc.), reads 2-3 of the news articles Google
links to it, has Gemini explain "what's happening and why everyone is searching for it" from those facts only, draws a
cover and publishes it ~30 minutes later (trends are about speed). Max one post per run, at most PER_DAY a day.
Env: DAY_CAP (default 18), PER_DAY (default 4), MIN_TRAFFIC (default 200).
"""
import datetime, html, json, os, random, re
import requests
from bs4 import BeautifulSoup
import football as f
import cover

f.DAY_CAP = int(os.environ.get("DAY_CAP") or 18)
PER_DAY = int(os.environ.get("PER_DAY") or 4)
MIN_TRAFFIC = int(os.environ.get("MIN_TRAFFIC") or 200)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
FIRE = "https://wsrv.nl/?url=cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Fire/3D/fire_3d.png&w=300&h=300&output=png"
AVOID = r"بث مباشر|بث مباريات|live stream|stream free|قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|sex|porn|murder|suicide"
SKIP_DOMAINS = ("yallakora.com",)

PROMPT = """أنت محرر أخبار في موقع ايجبتاوى المصري. موضوع «{q}» عليه بحث كبير دلوقتي في {geo}. اكتب خبر أصلي يشرح للقارئ إيه اللي حصل وليه الناس بتدور عليه.

قواعد صارمة:
- استخدم المعلومات اللي في «المصادر» بس. ممنوع تخترع أرقام أو تصريحات أو تفاصيل أو توقعات.
- اكتب بحياد: من غير اتهامات، ومن غير رأي شخصي، ومن غير مبالغة في العنوان.
- اكتب كل الأرقام بالأرقام. ممنوع تذكر أسماء المواقع أو الجرايد كمصادر جوه النص.
- لو المعلومات متضاربة أو لسه مش مؤكدة، قول كده بوضوح.
- اللغة: عربي بسيط قريب من المصري، فقرات قصيرة.
- الطول: الـ body من 500 لـ 800 كلمة، بعناوين h2 (من 3 لـ 5) وفقرات <p>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان واضح وصادق أقل من 65 حرف", "kicker": "2-4 كلمات للصورة", "headline": "جملة للصورة أقل من 60 حرف", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
المصادر:
{src}
"""


def trends():
    out = []
    for geo, name in (("EG", "مصر"), ("SA", "السعودية")):
        try:
            s = BeautifulSoup(requests.get(f"https://trends.google.com/trending/rss?geo={geo}", headers=UA, timeout=30).content, "xml")
        except Exception as e:
            print("trends failed", geo, e)
            continue
        for it in s.find_all("item"):
            q = it.find("title").text.strip()
            tr = it.find("approx_traffic") or it.find("ht:approx_traffic")
            traffic = int(re.sub(r"\D", "", tr.text) or 0) if tr else 0
            news = []
            for n in it.find_all(["news_item", "ht:news_item"]):
                u = n.find(["news_item_url", "ht:news_item_url"])
                t = n.find(["news_item_title", "ht:news_item_title"])
                if u and not any(d in u.text for d in SKIP_DOMAINS):
                    news.append((u.text.strip(), (t.text if t else "").strip()))
            out.append({"q": q, "geo": name, "traffic": traffic, "news": news})
    out.sort(key=lambda x: -x["traffic"])
    return out


def text(url):
    s = BeautifulSoup(requests.get(url, headers=UA, timeout=25).text, "html.parser")
    box = s.find("article") or s.find("main") or s
    return "\n".join(p for p in (x.get_text(" ", strip=True) for x in box.find_all("p")) if len(p) > 60)


def main():
    try:
        state = json.load(open("trends_posted.json", encoding="utf-8"))
    except Exception:
        state = {"done": []}
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()
    if len([d for d in state["done"] if d.get("at") == today and d.get("ok")]) >= PER_DAY:
        print("trend posts for today done")
        return
    if not (9 <= now.hour <= 22):
        print("outside publishing hours")
        return
    seen = {f.norm(d["q"]) for d in state["done"][-200:]}
    cands = [t for t in trends() if t["traffic"] >= MIN_TRAFFIC and t["news"] and f.norm(t["q"]) not in seen
             and not re.search(AVOID, t["q"] + " " + " ".join(n[1] for n in t["news"]), re.I)]
    if not cands:
        print("no new trend worth a post")
        return
    tok = f.token()
    existing = [p["t"] for p in f.site_posts(tok)]
    sched = f.api("GET", f"/blogs/{f.BLOG}/posts", tok, {"status": ["live", "scheduled"], "fetchBodies": "false",
                                                        "startDate": today + "T00:00:00+02:00", "maxResults": 60, "view": "ADMIN"})
    taken = []
    for it in sched.get("items", []):
        try:
            taken.append(datetime.datetime.fromisoformat(it["published"]).astimezone(f.CAIRO))
        except Exception:
            pass
    if len([t for t in taken if t.date().isoformat() == today]) >= f.DAY_CAP:
        print("daily cap reached")
        return
    when = now + datetime.timedelta(minutes=random.randint(20, 40))
    for _ in range(12):  # keep 30+ minutes away from any other post
        if all(abs((when - t).total_seconds()) >= 1800 for t in taken):
            break
        when += datetime.timedelta(minutes=15)
    when = when.replace(second=0, microsecond=0)
    for c in cands[:3]:
        parts = []
        for u, t in c["news"][:3]:
            try:
                tx = text(u)
            except Exception:
                continue
            if len(tx) > 300:
                parts.append(f"[{t}]\n{tx[:2500]}")
        src = "\n\n".join(parts)
        if len(src) < 800:
            state["done"].append({"q": c["q"], "at": today, "ok": False, "why": "no source text"})
            continue
        extra, art, errs = "", None, ["no draft"]
        for _ in range(2):
            art = f.gemini(PROMPT.format(q=c["q"], geo=c["geo"], extra=extra, src=src))
            errs = f.check(art, src + " " + c["q"], "", existing, min_words=450)
            if not errs:
                break
            print("  retry:", errs)
            extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
        state["done"].append({"q": c["q"], "at": today, "ok": not errs})
        if errs:
            print("SKIPPED", c["q"], errs)
            continue
        os.makedirs("img", exist_ok=True)
        p = f"img/{art['slug']}.jpg"
        cover.make_topic_cover(FIRE, "تريند · " + (art.get("kicker") or c["q"])[:30], art.get("headline") or art["title"], p)
        e = html.escape
        body = (f'<img src="{f.CDN + p}" alt="{e(art["title"])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
                + art["body"]
                + '<p><button type="button" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden" style="border:0;border-radius:999px;padding:7px 16px;font:inherit;font-weight:700;color:#fff;background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer">الخلاصة</button>'
                  f'<span hidden style="display:block;margin-top:8px;padding:10px;border-radius:10px;background:#fff7ed">{e(art.get("desc", ""))}</span></p>'
                + "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in art.get("faq", [])[:4]))
        fin = f.schedule(tok, art, body, ["أخبار", "تريند"], when)
        state["done"][-1].update({"url": fin.get("url"), "title": art["title"]})
        print("SCHEDULED", when.strftime("%H:%M"), fin.get("url"), "|", art["title"], "| trend:", c["q"], c["traffic"])
        break
    state["done"] = state["done"][-400:]
    json.dump(state, open("trends_posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
