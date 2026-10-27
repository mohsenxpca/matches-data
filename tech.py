"""Daily tech news on Egyptaway (apps, WhatsApp, AI, Android/iOS/Windows updates, security), written in our own Arabic words.

Runs daily on GitHub Actions (.github/workflows/tech.yml). Picks fresh stories from a few English tech feeds, reads the
article, asks Gemini (same writer/checker/scheduler as football.py), draws a 3D-icon cover, and schedules them at random
times today. Phone launch stories are skipped (those go to Review / the phone-news routine).
Env: COUNT (default 2), DAY_CAP (default 18).
"""
import datetime, html, json, os, random, re, sys
import requests
from bs4 import BeautifulSoup
import football as f
import cover

COUNT = int(os.environ.get("COUNT") or 2)
f.DAY_CAP = int(os.environ.get("DAY_CAP") or 18)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
FEEDS = [("https://techcrunch.com/feed/", "TechCrunch"), ("https://www.bleepingcomputer.com/feed/", "BleepingComputer"),
         ("https://www.androidpolice.com/feed/", "Android Police"), ("https://www.theverge.com/rss/index.xml", "The Verge")]
FLUENT = "https://wsrv.nl/?url=cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/{}&w=300&h=300&output=png"
TOPICS = [  # (regex on the English title, label, kicker word, 3D icon, priority: lower = more interesting for our readers)
    (r"whatsapp|messenger|telegram|signal", "واتساب", "واتساب وتطبيقات المحادثة", "Speech balloon/3D/speech_balloon_3d.png", 0),
    (r"chatgpt|openai|gemini|claude|copilot|\bai\b|llm|deepseek|grok", "الذكاء الاصطناعى", "ذكاء اصطناعي", "Robot/3D/robot_3d.png", 1),
    (r"android|google|chrome|gmail|youtube|play store", "اندرويد", "جوجل وأندرويد", "Mobile phone/3D/mobile_phone_3d.png", 2),
    (r"instagram|facebook|tiktok|snapchat|\bx\b|twitter|threads", "تطبيقات", "تطبيقات التواصل", "Mobile phone/3D/mobile_phone_3d.png", 2),
    (r"windows|microsoft|\bpc\b|laptop|office", "كمبيوتر", "ويندوز والكمبيوتر", "Laptop/3D/laptop_3d.png", 3),
    (r"hack|malware|ransomware|vulnerab|breach|scam|phishing|password|security", "شروحات", "أمان واختراق", "Locked/3D/locked_3d.png", 3),
    (r"ios|iphone|apple|mac", "تطبيقات", "أبل", "Mobile phone/3D/mobile_phone_3d.png", 4),
]
SKIP = r"launch(es|ed)? .*(galaxy|iphone|pixel|phone)|hands-on|review:|deal|% off|sale|best .* to buy|podcast|newsletter|funding|raises \$|series [a-e]"

PROMPT = """أنت محرر تقنية في موقع ايجبتاوى المصري. اكتب خبر تقنية أصلي بالكامل بالعربي البسيط القريب من المصري عن الموضوع ده.

قواعد صارمة:
- استخدم المعلومات اللي في «النص المصدر» بس. ممنوع تضيف أي رقم أو تاريخ أو سعر أو ميزة مش موجودة فيه.
- اكتب كل الأرقام بالأرقام (مش بالحروف). أسماء الشركات والتطبيقات تفضل بالإنجليزي زي ما هي (WhatsApp، Google).
- ممنوع تترجم حرفيًا: اكتب بأسلوبك، ورتّب الأفكار من الأهم للقارئ العربي.
- القيمة المضافة: اشرح الخبر يعني إيه للمستخدم العادي في مصر والوطن العربي، وإيه اللي يعمله دلوقتي (يحدّث؟ يستنى؟ ياخد باله؟)، من غير ما تخترع معلومات.
- لو الميزة لسه تجريبية أو مش متاحة للكل، قول كده بوضوح.
- الطول: الـ body من 600 لـ 900 كلمة، بعناوين h2 (من 4 لـ 6) وفقرات <p>، وممكن <ul>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان واضح وصادق أقل من 65 حرف", "kicker": "2-4 كلمات للصورة", "headline": "جملة الخبر للصورة أقل من 60 حرف", "slug": "3 to 6 english words with hyphens", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
عنوان الخبر الأصلي: {title}

النص المصدر:
{src}
"""


def topic(title):
    for rx, label, kick, icon, prio in TOPICS:
        if re.search(rx, title, re.I):
            return label, kick, icon, prio
    return None


def candidates(done):
    out = []
    for url, name in FEEDS:
        try:
            s = BeautifulSoup(requests.get(url, headers=UA, timeout=30).content, "xml")
        except Exception as e:
            print("feed failed", name, e)
            continue
        for it in s.find_all(["item", "entry"])[:25]:
            t = (it.find("title").text or "").strip()
            ln = it.find("link")
            link = (ln.get("href") or ln.text or "").strip() if ln else ""
            if not t or not link or link in done or re.search(SKIP, t, re.I):
                continue
            tp = topic(t)
            if tp:
                out.append({"t": t, "u": link, "src": name, "topic": tp})
    random.shuffle(out)
    out.sort(key=lambda c: c["topic"][3])
    return out


def article_text(url):
    s = BeautifulSoup(requests.get(url, headers=UA, timeout=30).text, "html.parser")
    box = s.find("article") or s.find("main") or s
    ps = [p.get_text(" ", strip=True) for p in box.find_all("p")]
    return "\n".join(p for p in ps if len(p) > 60)


def build(art, c, cover_url):
    e = html.escape
    first = f'<img src="{cover_url}" alt="{e(art["title"])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px">'
    faq = "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in art.get("faq", [])[:4])
    tool = ('<p><button type="button" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden" '
            'style="border:0;border-radius:999px;padding:7px 16px;font:inherit;font-weight:700;color:#fff;background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer">'
            'الخلاصة في سطرين</button><span hidden style="display:block;margin-top:8px;padding:10px;border-radius:10px;background:#fff7ed">'
            f'{e(art.get("desc", ""))}</span></p>')
    src = f'<p style="font-size:13px;color:#6b7280">المصدر: <a href="{e(c["u"])}" rel="nofollow noopener" target="_blank">{e(c["src"])}</a></p>'
    return first + art["body"] + tool + faq + src


def main():
    try:
        state = json.load(open("tech_posted.json", encoding="utf-8"))
    except Exception:
        state = {"done": []}
    done = {d["u"] for d in state["done"]}
    tok = f.token()
    posts = f.site_posts(tok)
    existing = [p["t"] for p in posts]
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()
    sched = f.api("GET", f"/blogs/{f.BLOG}/posts", tok, {"status": ["live", "scheduled"], "fetchBodies": "false",
                                                        "startDate": today + "T00:00:00+02:00", "maxResults": 60, "view": "ADMIN"})
    taken = []
    for it in sched.get("items", []):
        try:
            taken.append(datetime.datetime.fromisoformat(it["published"]).astimezone(f.CAIRO))
        except Exception:
            pass
    room = f.DAY_CAP - len([t for t in taken if t.date().isoformat() == today])
    n = min(COUNT, room)
    if n <= 0:
        print(f"Egyptaway already has {len(taken)} posts today (cap {f.DAY_CAP})")
        return
    times = f.schedule_times(n, taken)
    made = 0
    os.makedirs("img", exist_ok=True)
    for c in candidates(done):
        if made >= len(times):
            break
        try:
            src = article_text(c["u"])
        except Exception as ex:
            print("source failed", c["u"], ex)
            continue
        if len(src) < 900:
            continue
        extra, art, errs = "", None, ["no draft"]
        for _ in range(2):
            art = f.gemini(PROMPT.format(extra=extra, title=c["t"], src=src[:7000]))
            errs = f.check(art, src + " " + c["t"], "", existing, min_words=550)
            if not errs:
                break
            print("  retry:", errs)
            extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
        state["done"].append({"u": c["u"], "t": c["t"], "at": today, "ok": not errs})
        if errs:
            print("SKIPPED", c["t"], errs)
            continue
        label, kick, icon, _ = c["topic"]
        p = f"img/{art['slug']}.jpg"
        cover.make_topic_cover(FLUENT.format(requests.utils.quote(icon, safe="/")), art.get("kicker") or kick,
                               art.get("headline") or art["title"], p)
        html_out = build(art, c, f.CDN + p)
        fin = f.schedule(tok, art, html_out, ["أخبار", label], times[made])
        state["done"][-1].update({"url": fin.get("url"), "title": art["title"]})
        print("SCHEDULED", times[made].strftime("%H:%M"), fin.get("url"), "|", art["title"])
        existing.append(art["title"])
        made += 1
    state["done"] = state["done"][-400:]
    json.dump(state, open("tech_posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done: {made} tech post(s)")


if __name__ == "__main__":
    main()
