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

f.DAY_CAP = int(os.environ.get("DAY_CAP") or 50)
PER_DAY = int(os.environ.get("PER_DAY") or 12)
MIN_TRAFFIC = int(os.environ.get("MIN_TRAFFIC") or 200)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
FIRE = "https://wsrv.nl/?url=cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Fire/3D/fire_3d.png&w=300&h=300&output=png"
# فلترة صارمة لمنع أي أخبار سياسية أو حروب أو شؤون فنية (قرار محسن 2026-10-31)
BANNED_TOPICS_REGEX = (
    # السياسة واللقاءات والحكومات والدبلوماسية
    r"رئيس الجمهورية|السيسي|الرئيس|الحكومة|مجلس الوزراء|رئيس الوزراء|مدبولي|وزير الخارجية|وزير العدل|"
    r"البرلمان|مجلس النواب|مجلس الشيوخ|أحزاب|انتخابات|سياسي|سياسة|دبلوماسي|سفير|سفارة|مباحثات|"
    r"مستشار|لقاء|استقبل|استقبال|مؤتمر صحفي|بيان رسمي|زيارة رسمية|قمة|اتفاقية دولية|معاهدة|شأن سياسي|"
    # الحروب والنزاعات والعمليات العسكرية والصراعات
    r"حرب|حروب|معركة|معارك|عسكري|جيش|قوات|صواريخ|صاروخ|طائرات حربية|غارة|غارات|قصف|انفجار|استهداف|"
    r"هجوم|مسيرة|مسيّرة|طائرة مسيرة|مسيرات|مقذوف|شهداء|قتلى|جرحى|إيران|طهران|إسرائيل|تل أبيب|"
    r"غزة|لبنان|حزب الله|الحوثي|اليمن|سوريا|روسيا|أوكرانيا|الشرق الأوسط|نووي|أسلحة|دبابات|غارات جوية|"
    # الفن والغناء والرقص والتمثيل والمهرجانات الفنية
    r"فنان|فنانة|ممثل|ممثلة|نجوم الفن|مطرب|مطربة|مغني|مغنية|غناء|أغنية|كليب|فيديو كليب|رقص|راقصة|"
    r"مهرجان الجونة|مهرجان القاهرة|مسلسل|مسلسلات|فيلم|أفلام|سينما|دراما|تيك توك|مشاهير|زواج الفنان|طلاق الفنان|فستان|"
    # الجرائم والحوادث البشعة
    r"بث مباشر|بث مباريات|live stream|stream free|قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|فيديو إباحي|اباحي|شذوذ|فضايح|sex|porn|murder|suicide"
)

# الاقتصار حصراً على مجالات موقعنا وأقسامه وصفحات الخدمات والتكنولوجيا والألعاب والرياضة
ALLOWED_TOPICS_REGEX = (
    # 1. التكنولوجيا والهواتف والذكاء الاصطناعي والتطبيقات
    r"تكنولوجي|هاتف|هواتف|موبايل|موبايلات|أندرويد|آيفون|سامسونج|شاومي|هونر|أوبو|فيفو|ريلمي|موتورولا|"
    r"ذكاء اصطناعي|شات جي بي تي|جيميني|تطبيق|تطبيقات|واتساب|فيسبوك|تحديث|معالج|كاميرا|شاشة|بطارية|تسريب|مواصفات|"
    # 2. الألعاب والجيمنج
    r"لعبة|ألعاب|جيمنج|ببجي|فري فاير|كول أوف ديوتي|إي فوتبول|فيفا|فورتنايت|ماين كرافت|روبلوكس|شحن|أكواد|جواهر|شدات|"
    # 3. الرياضة وكرة القدم
    r"كرة قدم|كورة|مباراة|مباريات|الأهلي|الزمالك|بيراميدز|الدوري المصري|دوري أبطال|محمد صلاح|ريال مدريد|برشلونة|ليفربول|مانشستر|"
    # 4. الخدمات والصفحات التي أنشأناها بموقعنا
    r"ذهب|عيار 21|الجنيه الذهب|سعر الذهب|بورصة الذهب|"
    r"دولار|عملات|سعر الدولار|سعر الصرف|سعر الفائدة|شهادات|البنك الأهلي|بنك مصر|البنك المركزي|شهادة ادخار|"
    r"طقس|أرصاد|درجات الحرارة|أمطار|سيول|حالة الجو|بيان الأرصاد|نوة|"
    r"مواقيت الصلاة|موعد أذان|الفجر|المغرب|العشاء|الجمعة|"
    r"قطارات|قطار|مواعيد القطارات|سكة حديد|مترو|مواعيد المترو|تذاكر|"
    r"مرتبات|صرف المرتبات|معاشات|صرف المعاشات|تكافل وكرامة|حد أدنى للأجور|"
    r"امتحانات|جدول الامتحانات|مواعيد الامتحانات|مدارس|جامعات|إجازة رسمية|إجازات|عطلة رسمية|التوقيت الشتوي|التوقيت الصيفي|"
    r"إسكان|شقق الإسكان|سكن لكل المصريين|الإسكان الاجتماعي|بوابة مسكن|طرح الإسكان|شقق جنة|سكن مصر|دار مصر|"
    r"بنزين|سعر البنزين|السولار|أسعار الوقود|لجنة التسعير|أنبوبة الغاز|"
    r"عطل|انقطاع|توقف|شبكة|فودافون|أورنج|وي|إتصالات|إنستاباي|انستاباي|فوري|فودافون كاش|تطبيق البنك"
)

AVOID = BANNED_TOPICS_REGEX
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


# High-res natural editorial trend photography fallbacks (no text overlays)
TREND_FALLBACKS = {
    "prayer": "https://images.pexels.com/photos/2233416/pexels-photo-2233416.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "gold": "https://images.pexels.com/photos/844124/pexels-photo-844124.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "weather": "https://images.pexels.com/photos/1118873/pexels-photo-1118873.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "sports": "https://images.pexels.com/photos/114296/pexels-photo-114296.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
    "general": "https://images.pexels.com/photos/518543/pexels-photo-518543.jpeg?auto=compress&cs=tinysrgb&w=1000&h=563&fit=crop",
}

def get_trend_fallback(text):
    t = text.lower()
    if re.search(r"صلاة|أذان|مواقيت|مسجد|فجر|ظهر|عصر|مغرب|عشاء|رمضان|جمعة", t):
        return TREND_FALLBACKS["prayer"]
    if re.search(r"ذهب|عيار|دولار|عملات|جنيه|بورصة|سعر الذهب", t):
        return TREND_FALLBACKS["gold"]
    if re.search(r"طقس|أرصاد|مطر|حرارة|شتاء|صيف|رياح", t):
        return TREND_FALLBACKS["weather"]
    if re.search(r"مباراة|دوري|أهلي|زمالك|كورة|منتخب", t):
        return TREND_FALLBACKS["sports"]
    return TREND_FALLBACKS["general"]


def fetch_trend_source(url):
    s = BeautifulSoup(requests.get(url, headers=UA, timeout=25).text, "html.parser")
    real_img = None
    og = s.find("meta", property="og:image") or s.find("meta", attrs={"name": "twitter:image"})
    if og and og.get("content"):
        u = og["content"].strip()
        if u.startswith("http") and not any(x in u for x in ["default", "placeholder", "logo", "avatar", "icon"]):
            real_img = u
    box = s.find("article") or s.find("main") or s
    txt = "\n".join(p for p in (x.get_text(" ", strip=True) for x in box.find_all("p")) if len(p) > 60)
    return real_img, txt


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
    # 24/7 publishing allowed
    pass
    seen = {f.norm(d["q"]) for d in state["done"][-200:]}
    cands = [t for t in trends() if t["traffic"] >= MIN_TRAFFIC and t["news"] and f.norm(t["q"]) not in seen
             and re.search(ALLOWED_TOPICS_REGEX, t["q"] + " " + " ".join(n[1] for n in t["news"]), re.I)
             and not re.search(BANNED_TOPICS_REGEX, t["q"] + " " + " ".join(n[1] for n in t["news"]), re.I)]
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
        if f._DOWN:
            break
        parts = []
        trend_real_img = None
        for u, t in c["news"][:3]:
            try:
                u_img, tx = fetch_trend_source(u)
                if u_img and not trend_real_img:
                    trend_real_img = u_img
            except Exception:
                continue
            if len(tx) > 300:
                parts.append(f"[{t}]\n{tx[:2500]}")
        src = "\n\n".join(parts)
        if len(src) < 800:
            state["done"].append({"q": c["q"], "at": today, "ok": False, "why": "no source text"})
            continue
        if re.search(BANNED_TOPICS_REGEX, src[:2500], re.I):
            print("  Banned political/war/art content found in source. Skipping:", c["q"])
            state["done"].append({"q": c["q"], "at": today, "ok": False, "why": "banned topic"})
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
        e = html.escape
        lead_img_url = None
        if trend_real_img:
            candidate_proxy = f"https://wsrv.nl/?url={requests.utils.quote(trend_real_img, safe='')}&w=1000&output=webp&q=80"
            try:
                chk = requests.head(candidate_proxy, headers=UA, timeout=3, allow_redirects=True)
                if chk.status_code == 200:
                    lead_img_url = candidate_proxy
                else:
                    print(f"  Trend img proxy returned {chk.status_code}. Using fallback.")
            except Exception as e:
                print(f"  Trend img proxy check failed ({e}). Using fallback.")
        if not lead_img_url:
            lead_img_url = get_trend_fallback(c["q"] + " " + art["title"])
        body = (f'<img src="{lead_img_url}" alt="{e(art["title"])}" width="1000" height="563" style="width:100%;height:auto;border-radius:12px">'
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
