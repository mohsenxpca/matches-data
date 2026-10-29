"""Egyptaway Outage Monitor & Auto Breaking News (mohsen 2026-10-29).
Monitors live service outage reports from our Apps Script API + Google News RSS for outages in Egypt.
When a confirmed outage occurs (Vodafone, InstaPay, WhatsApp, Vodafone Cash, Facebook, WE, Orange, etc.):
- Automatically generates an original breaking-news article explaining the issue and troubleshooting steps.
- Directly links to the dedicated live tracker page (/p/is-{service}-down.html) and hub (/p/is-it-down-egypt.html).
- Generates a branded cover image and publishes the post immediately to Egyptaway.
Runs via GitHub Actions workflow (outage.yml) every 15-20 minutes.
"""
import datetime, html, json, os, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import football as f
import cover

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
WARNING_ICON = "https://wsrv.nl/?url=cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/Warning/3D/warning_3d.png&w=300&h=300&output=png"

API_URL = "https://script.google.com/macros/s/AKfycbx_xEqWCdWDpnIl-HmKC3PWqVHNMQDQtCFYxpHb9rWXT4QVNN8LCCo7tUbG_C4v-Tvztg/exec?a=all"
POSTED_FILE = "outage_posted.json"

SERVICES = {
    "vodafone": {"name": "فودافون", "cat": "الشبكة والإنترنت المحمول", "support": "888", "slug": "is-vodafone-down"},
    "orange": {"name": "أورنج", "cat": "الشبكة والإنترنت", "support": "110", "slug": "is-orange-down"},
    "etisalat": {"name": "اتصالات e&", "cat": "الشبكة والمكالمات", "support": "333", "slug": "is-etisalat-down"},
    "we": {"name": "WE (المصرية للاتصالات)", "cat": "الإنترنت الأرضي والمحمول", "support": "111 أو 19777", "slug": "is-we-down"},
    "instapay": {"name": "إنستاباي (InstaPay)", "cat": "التحويلات البنكية اللحظية", "support": "تطبيق البنك التابع له", "slug": "is-instapay-down"},
    "fawry": {"name": "فوري", "cat": "المدفوعات الإلكترونية وشحن الرصيد", "support": "16421", "slug": "is-fawry-down"},
    "vodafone-cash": {"name": "فودافون كاش", "cat": "المحفظة الإلكترونية وتحويل الأموال", "support": "888 أو كود *9#", "slug": "is-vodafone-cash-down"},
    "facebook": {"name": "فيسبوك", "cat": "تطبيق وموقع فيسبوك والماسنجر", "support": "مركز المساعدة الرسمي", "slug": "is-facebook-down"},
    "whatsapp": {"name": "واتساب", "cat": "إرسال واستقبال الرسائل والوسائط", "support": "تطبيق واتساب الرسمي", "slug": "is-whatsapp-down"},
    "instagram": {"name": "إنستجرام", "cat": "نشر وتصفح الصور والريلز", "support": "موقع وتطبيق إنستجرام", "slug": "is-instagram-down"},
    "youtube": {"name": "يوتيوب", "cat": "مشاهدة وتشغيل الفيديوهات", "support": "منصة يوتيوب", "slug": "is-youtube-down"},
    "tiktok": {"name": "تيك توك", "cat": "تشغيل وتصفح الفيديوهات القصيرة", "support": "تطبيق تيك توك", "slug": "is-tiktok-down"},
    "ahly-bank": {"name": "البنك الأهلي المصري (الأهلي نت)", "cat": "الخدمات المصرفية الإلكترونية وتطبيق الموبايل", "support": "19623", "slug": "is-ahly-bank-down"},
    "banque-misr": {"name": "بنك مصر (BM Online)", "cat": "المعاملات البنكية الرقمية", "support": "19888", "slug": "is-banque-misr-down"},
    "cib": {"name": "البنك التجاري الدولي (CIB)", "cat": "تطبيق وموقع البنك الرقمي", "support": "19666", "slug": "is-cib-down"},
    "pubg": {"name": "ببجي موبايل", "cat": "سيرفرات لعبة ببجي موبايل", "support": "الدعم داخل اللعبة", "slug": "is-pubg-down"},
}

PROMPT = """أنت محرر تقني في موقع ايجبتاوى المصري. هناك بلاغات وتأكيدات عن حدوث عطل مفاجئ أو توقف في خدمة «{name}» في مصر والشرق الأوسط، خاصة في {cat}.

اكتب خبر عاجل وافي ومطمئن يشرح للقارئ:
1. طبيعة المشكلة والأعراض اللي بيشتكي منها المستخدمين (صعوبة تسجيل الدخول، بطء أو تعذر المعاملات، انقطاع الاتصال).
2. إزاي يتأكد إذا كانت المشكلة عطل عام عنده وعند غيره ولا عطل فردي في جهازه أو راوتره.
3. حلول وبدائل سريعة (إعادة تشغيل وضع الطيران، تجربة شبكة بيانات أخرى، تجنب تكرار عمليات التحويل المالي حتى لا تخصم مرتين).
4. أرقام خدمة العملاء والدعم الرسمي ({support}).

قواعد صارمة:
- العنوان واضح وصادق وأقل من 65 حرف وفيه اسم الخدمة والسنة {year}.
- ممنوع المبالغة أو التهويل: اكتب بحيادية ومهنية.
- الطول: الـ body من 450 لـ 700 كلمة، بعناوين h2 وفقرات <p>، وقائمة نصائح <ul><li>..</li></ul>.
- من غير صور ومن غير روابط جوه النص (هنضيفها تلقائيًا).

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان عاجل وواضح أقل من 65 حرف", "kicker": "عطل مفاجئ", "headline": "جملة للغلاف أقل من 55 حرف", "slug": "english-slug-3-to-6-words", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
"""


def fetch_api_status():
    try:
        r = requests.get(API_URL, headers=UA, timeout=20)
        if r.status_code == 200:
            return r.json().get("list", [])
    except Exception as e:
        print("API check failed:", e)
    return []


def decode_gn_link(link):
    """Decodes Google News RSS redirect link to original publisher URL."""
    try:
        aid = link.split("/articles/")[1].split("?")[0]
        h = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=UA, timeout=15).text
        sg = re.search(r'data-n-a-sg="([^"]+)"', h).group(1)
        ts = re.search(r'data-n-a-ts="([^"]+)"', h).group(1)
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=15,
                          headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                          data="f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])))
        return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except Exception:
        return None


def fetch_news_outages():
    """Checks Google News RSS for sudden outage reports in Egypt, returns dict {sid: real_photo_url}."""
    out = {}
    queries = ["عطل فودافون", "عطل انستاباي", "عطل واتساب", "عطل فودافون كاش", "عطل فيسبوك", "عطل شبكة we", "عطل اتصالات"]
    for q in queries:
        try:
            url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:6h") + "&hl=ar&gl=EG&ceid=EG:ar"
            x = requests.get(url, headers=UA, timeout=20).text
            items = re.findall(r"<item><title>(.*?)</title><link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", x, re.S)
            if len(items) >= 2:  # 2 or more distinct news stories about outage in last 6h
                for sid, data in SERVICES.items():
                    if data["name"] in q or any(w in q for w in data["name"].split()):
                        # Try to get real news photo from top story
                        photo = None
                        try:
                            pub_url = decode_gn_link(items[0][1].strip())
                            if pub_url:
                                h_page = requests.get(pub_url, headers=UA, timeout=15).text
                                soup = BeautifulSoup(h_page, "html.parser")
                                og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                                if og and og.get("content"):
                                    c = og["content"].strip()
                                    if c.startswith("http") and not any(bad in c.lower() for bad in ["logo", "favicon", "avatar", "icon", "pixel"]):
                                        photo = f"https://wsrv.nl/?url={urllib.parse.quote(c)}&w=1000&output=webp&q=80"
                        except Exception:
                            photo = None
                        out[sid] = photo
        except Exception:
            continue
    return out


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    now = datetime.datetime.now(CAIRO)
    
    posted_state = {}
    if os.path.exists(POSTED_FILE):
        try:
            posted_state = json.load(open(POSTED_FILE, encoding="utf-8"))
        except Exception:
            posted_state = {}

    cutoff = (now - datetime.timedelta(hours=12)).isoformat()
    recent_posted = {k: v for k, v in posted_state.items() if v.get("at", "") > cutoff}

    # 1. Check API for 'down' or high report count
    down_services = set()
    api_list = fetch_api_status()
    for item in api_list:
        sid = item.get("s")
        st = item.get("status")
        last = item.get("last", 0)
        if sid in SERVICES and (st == "down" or last >= 15):
            down_services.add(sid)

    # 2. Check News spikes
    news_down = fetch_news_outages()
    for sid in news_down:
        down_services.add(sid)

    print(f"[{now:%Y-%m-%d %H:%M}] Detected outages:", down_services)

    # Filter out services already posted in the last 12 hours
    candidates = [sid for sid in down_services if sid not in recent_posted]
    if not candidates:
        print("No new outages to post.")
        return

    tok = f.token()
    existing = [p["t"] for p in f.site_posts(tok)]

    for sid in candidates[:1]:  # Post at most 1 outage alert per run to avoid spam
        svc = SERVICES[sid]
        print(f"Processing outage breaking news for: {svc['name']}")

        prompt = PROMPT.format(name=svc["name"], cat=svc["cat"], support=svc["support"], year=now.year)
        art = f.gemini(prompt)
        if not art or not art.get("title") or not art.get("body"):
            print("Gemini generation failed for", sid)
            continue

        # Add interactive callout box directly to our live outage tracker page
        tracker_url = f"{f.SITE}/p/{svc['slug']}.html"
        hub_url = f"{f.SITE}/p/is-it-down-egypt.html"
        
        callout = f'''<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:14px;padding:16px;margin:18px 0;text-align:center;box-shadow:0 4px 12px rgba(239,68,68,.12);">
  <div style="font-size:18px;font-weight:900;color:#991b1b;margin-bottom:8px;">🔴 رادار متابعة الأعطال والبلاغات المباشرة في مصر</div>
  <p style="font-size:14.5px;color:#374151;margin:0 0 12px;">لو الخدمة واقعة عندك أو بتواجه مشكلة في {svc['cat']}، ادخل على الرادار وسجل بلاغك لمساعدة الآخرين ومعرفة خريطة الأعطال بالمحافظات لحظة بلحظة:</p>
  <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;">
    <a href="{tracker_url}" style="background:#dc2626;color:#fff!important;text-decoration:none!important;font-weight:800;padding:10px 20px;border-radius:10px;font-size:15px;display:inline-block;">⚡ رصد حالة {svc['name']} المباشرة والبلاغات</a>
    <a href="{hub_url}" style="background:#1f2937;color:#fff!important;text-decoration:none!important;font-weight:700;padding:10px 18px;border-radius:10px;font-size:14px;display:inline-block;">🌐 حالة باقي الخدمات والشبكات بمصر</a>
  </div>
</div>'''

        lead_img_src = news_down.get(sid) or f"{f.CDN}img/{art['slug']}.jpg"
        body = (f'<img src="{lead_img_src}" alt="{html.escape(art["title"])}" width="1000" height="563" style="width:100%;height:auto;border-radius:12px;margin-bottom:14px">'
                + callout
                + art["body"]
                + "<h2>أسئلة شائعة</h2>" + "".join(f"<details><summary>{html.escape(q['q'])}</summary><p>{html.escape(q['a'])}</p></details>" for q in art.get("faq", [])[:4])
                + callout)

        os.makedirs("img", exist_ok=True)
        img_path = f"img/{art['slug']}.jpg"
        if not news_down.get(sid):
            cover.make_topic_cover(WARNING_ICON, f"عاجل · عطل {svc['name']}", art.get("headline") or art["title"], img_path)

        if dry:
            print("DRY RUN:", art["title"])
            print("Slug:", art["slug"])
            recent_posted[sid] = {"title": art["title"], "at": now.isoformat()}
            break

        post_res = f.schedule(tok, art, body, ["أخبار", "أعطال وتوقف الخدمات"], now + datetime.timedelta(minutes=1))
        post_url = post_res.get("url", "")
        print(f"PUBLISHED OUTAGE NEWS: {post_url} | {art['title']}")

        recent_posted[sid] = {
            "title": art["title"],
            "url": post_url,
            "at": now.isoformat()
        }

        # Push notification via OneSignal / Telegram if notify.py is present
        try:
            import notify
            notify.send_push(art["title"], f"بلاغات عن توقف خدمات {svc['name']} في مصر.. تابع التفاصيل المباشرة", post_url)
        except Exception:
            pass
        break

    with open(POSTED_FILE, "w", encoding="utf-8") as pf:
        json.dump(recent_posted, pf, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
