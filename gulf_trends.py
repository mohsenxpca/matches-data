"""Egyptaway Automated Live Saudi & Gulf Trends Engine (mohsen 2026-10-29).
Tracks hot trending topics in Saudi Arabia (SA), UAE (AE), and Kuwait (KW) 24/7.
Features:
- Monitors Google Trends RSS in real time for Saudi Arabia and Gulf countries.
- Fetches linked news stories and extracts the REAL NEWS PHOTO (og:image / twitter:image).
- Explains why the topic is trending with factual background, official decrees, and public context.
- Cross-links to our permanent Gulf service pages (Currency, Gold, Prayer, Work Visas).
- Publishes immediately with clean permalinks + IndexNow notification.

Runs via GitHub Actions (.github/workflows/gulf_trends.yml) every 30 minutes.
Usage:
  python gulf_trends.py           # live publish
  DRY_RUN=1 python gulf_trends.py # dry run
"""
import datetime, difflib, html, json, os, random, re, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import football as f

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
INDEXNOW_KEY = "e3b3e2ee8cd741f59f1b91e73c0f9090"
STATE_FILE = "gulf_trends_posted.json"
DAY_CAP = int(os.environ.get("GULF_TRENDS_DAY_CAP", "25"))
MIN_TRAFFIC = int(os.environ.get("MIN_TRAFFIC", "100"))

COUNTRIES = [
    ("SA", "السعودية", "المملكة العربية السعودية"),
    ("AE", "الإمارات", "دولة الإمارات العربية المتحدة"),
    ("KW", "الكويت", "دولة الكويت"),
]

AVOID = r"بث مباشر|بث مباريات|live stream|stream free|قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|sex|porn|murder|suicide"
SKIP_DOMAINS = ("yallakora.com",)

GULF_PROMPT = """أنت محرر شؤون الخليج العربي في موقع ايجبتاوى. موضوع «{q}» يتصدر تريند البحث حالياً في {country_full}. اكتب تقريراً إخبارياً أصلياً وشاملاً يشرح للقارئ العربي تفاصيل الموضوع ولماذا يبحث عنه الجميع الآن.

قواعد مهنية صارمة:
- الحقيقة والمصداقية: اعتمد تماماً على المعلومات والوقائع المذكورة في «النص المصدر». لا تخترع أي أرقام أو تصريحات أو اتهامات.
- اكتب بحيادية وموضوعية تامة وبلغة عربية فصيحة وسلسة قريبة من القارئ العربي.
- هيكل المقال:
  1. فقرة افتتاحية تشرح سبب تصدر الموضوع لمحركات البحث والتريند.
  2. التفاصيل والخلفية الكاملة للحدث والقرارات أو البيانات الرسمية المتعلقة به.
  3. ردود الأفعال الشعبية وتفاعل رواد مواقع التواصل في {country_full}.
- الطول: صلب الموضوع (body) من 550 إلى 800 كلمة، مقسم بعناوين h2 واضحة (من 3 لـ 5 عناوين)، وفقرات مريحة.
- لا تضع صوراً أو روابط داخل الـ body (سيتم وضعها تلقائياً).

رجّع JSON بالشكل ده بالظبط:
{{"title": "عنوان جذاب وصادق ومحدد أقل من 65 حرف", "slug": "english-slug-3-to-6-words", "desc": "وصف دقيق للبحث من 140 لـ 160 حرف", "kicker": "تريند {country_short}", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}

الموضوع التريند: {q}
الدولة: {country_full}

النص المصدر المجمع من التغطيات الإخبارية:
{src_text}
"""


def fetch_gulf_trends():
    trends = []
    for geo, short_name, full_name in COUNTRIES:
        try:
            url = f"https://trends.google.com/trending/rss?geo={geo}"
            resp = requests.get(url, headers=UA, timeout=20)
            soup = BeautifulSoup(resp.content, "xml")
            for it in soup.find_all("item")[:15]:
                q = it.find("title").text.strip() if it.find("title") else ""
                tr = it.find("approx_traffic") or it.find("ht:approx_traffic")
                traffic = int(re.sub(r"\D", "", tr.text) or 0) if tr else 0
                if not q or traffic < MIN_TRAFFIC:
                    continue
                if re.search(AVOID, q, re.I):
                    continue

                news_list = []
                for n in it.find_all(["news_item", "ht:news_item"]):
                    u = n.find(["news_item_url", "ht:news_item_url"])
                    t = n.find(["news_item_title", "ht:news_item_title"])
                    if u and not any(d in u.text for d in SKIP_DOMAINS):
                        news_list.append((u.text.strip(), (t.text if t else "").strip()))

                if news_list:
                    trends.append({
                        "q": q,
                        "geo": geo,
                        "country_short": short_name,
                        "country_full": full_name,
                        "traffic": traffic,
                        "news": news_list
                    })
        except Exception as e:
            print(f"Trends for {short_name} ({geo}) failed:", e)

    trends.sort(key=lambda x: -x["traffic"])
    return trends


def fetch_trend_story(url):
    """Fetches article text and real news photo from news publisher."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code != 200:
            return None, None
        soup = BeautifulSoup(r.text, "html.parser")

        # Real news photo
        img_url = None
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og and og.get("content"):
            c = og["content"].strip()
            if c.startswith("http") and not any(bad in c.lower() for bad in ["logo", "favicon", "avatar", "icon", "pixel"]):
                img_url = f"https://wsrv.nl/?url={urllib.parse.quote(c)}&w=1000&output=webp&q=82"

        # Article text
        box = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"article|content|story", re.I)) or soup
        paras = [p.get_text(" ", strip=True) for p in box.find_all("p") if len(p.get_text(" ", strip=True)) > 40]
        text = "\n".join(paras)
        return img_url, text
    except Exception:
        return None, None


def ping_indexnow(urls):
    try:
        data = {
            "host": "www.egyptaway.com",
            "key": INDEXNOW_KEY,
            "keyLocation": f"https://www.egyptaway.com/{INDEXNOW_KEY}.txt",
            "urlList": urls
        }
        requests.post("https://api.indexnow.org/IndexNow", json=data, timeout=15)
    except Exception:
        pass


def main():
    dry = os.environ.get("DRY_RUN") == "1"
        # Enforce strict quiet hours: No publishing on Egyptaway from 11:00 PM (23:00) to 9:00 AM Cairo
    now = datetime.datetime.now(CAIRO)
    if (now.hour >= 23 or now.hour < 9) and not dry:
        print(f"Egyptaway publishing window is closed ({now.hour:02d}:00 Cairo). Quiet hours: 11:00 PM to 9:00 AM. Exiting.")
        return


    today = now.date().isoformat()
    print(f"[{now:%Y-%m-%d %H:%M}] Starting Saudi & Gulf Trends Engine...")

    state = {"done": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            state = {"done": []}

    done_queries = {f.norm(d.get("q", "")) for d in state.get("done", []) if d.get("q")}
    done_titles = [d.get("title", "") for d in state.get("done", [])]

    # Daily cap check
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today) and d.get("ok")]
    if len(today_posts) >= DAY_CAP:
        print(f"Daily Gulf trends cap ({DAY_CAP}) reached. Exiting.")
        return

    tok = None if dry else f.token()
    existing_posts = [p["t"] for p in f.site_posts(tok)] if not dry else []
    all_known_titles = existing_posts + done_titles

    trends = fetch_gulf_trends()
    candidates = [t for t in trends if f.norm(t["q"]) not in done_queries and not re.search(AVOID, t["q"], re.I)]
    print(f"Found {len(candidates)} candidate Gulf trends.")
    if not candidates:
        return

    published_urls = []
    for cand in candidates[:4]:
        if len(published_urls) >= 1:  # 1 trend per run to pace articles evenly
            break

        print(f"Processing Trend: {cand['q']} ({cand['country_short']} - {cand['traffic']} searches)...")

        # Gather source texts and find a real news photo
        src_parts = []
        real_img = None
        for u, t in cand["news"][:3]:
            img_u, txt = fetch_trend_story(u)
            if img_u and not real_img:
                real_img = img_u
            if txt and len(txt) > 250:
                src_parts.append(f"[{t}]\n{txt[:2500]}")

        combined_src = "\n\n".join(src_parts)
        if len(combined_src) < 400:
            print("  Sources text too short. Skipping.")
            continue

        print(f"  Real Photo Found: {real_img is not None}")

        if dry and not f.secret("GEMINI_API_KEY"):
            print("  [DRY RUN - No Gemini Key] Simulating trend draft...")
            art = {
                "title": f"لماذا تصدر «{cand['q']}» تريند البحث في {cand['country_full']}؟",
                "slug": "gulf-trend-details-2026",
                "desc": f"تعرف على القصة الكاملة وسبب تصدر {cand['q']} لمحركات البحث والتريند في {cand['country_full']}.",
                "kicker": f"تريند {cand['country_short']}",
                "body": f"<h2>ما القصة ولماذا يبحث الجميع؟</h2><p>{combined_src[:500]}</p>",
                "faq": [{"q": f"لماذا يبحث الناس في {cand['country_short']} عن هذا الموضوع؟", "a": "بسبب اهتمام واسع بالقرارات والتطورات الأخيرة المعلنة رسمياً."}]
            }
            errs = []
        else:
            prompt = GULF_PROMPT.format(q=cand["q"], country_full=cand["country_full"], country_short=cand["country_short"], src_text=combined_src[:5500])
            art = f.gemini(prompt)
            errs = f.check(art, combined_src + " " + cand["q"], "", all_known_titles, min_words=450)

        if errs:
            print("  Fact check failed:", errs)
            state["done"].append({"q": cand["q"], "country": cand["geo"], "at": now.isoformat(), "ok": False, "err": errs})
            continue

        # Format Post HTML
        lead_img_html = f'<img src="{real_img}" alt="{html.escape(art["title"])}" width="1000" height="563" style="width:100%;height:auto;border-radius:14px;box-shadow:0 4px 14px rgba(0,0,0,.08);margin:12px 0 18px;" loading="eager">' if real_img else ""

        # Contextual Gulf Service Callout
        if cand["geo"] == "SA":
            service_box = '''<div style="background:#f0fdf4;border:2px solid #86efac;border-radius:14px;padding:16px;margin:20px 0;text-align:center;">
  <div style="font-size:16.5px;font-weight:900;color:#166534;margin-bottom:6px;">🇸🇦 خدمات ومعلومات تهم المقيمين والزائرين بالمملكة العربية السعودية</div>
  <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:10px;">
    <a href="https://www.egyptaway.com/p/currency-sa.html" style="background:#15803d;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">💵 سعر الريال السعودي اليوم</a>
    <a href="https://www.egyptaway.com/p/gulf-work-visas.html" style="background:#0f172a;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✈️ تأشيرات العمل ومنصة قوى</a>
    <a href="https://www.egyptaway.com/p/gold-sa.html" style="background:#ca8a04;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✨ أسعار الذهب بالسعودية</a>
  </div>
</div>'''
        elif cand["geo"] == "AE":
            service_box = '''<div style="background:#f0f9ff;border:2px solid #7dd3fc;border-radius:14px;padding:16px;margin:20px 0;text-align:center;">
  <div style="font-size:16.5px;font-weight:900;color:#0369a1;margin-bottom:6px;">🇦🇪 خدمات ومعلومات تهم المقيمين والباحثين عن عمل في الإمارات</div>
  <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:10px;">
    <a href="https://www.egyptaway.com/p/currency-ae.html" style="background:#0284c7;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">💵 سعر الدرهم الإماراتي اليوم</a>
    <a href="https://www.egyptaway.com/p/gulf-work-visas.html" style="background:#0f172a;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✈️ الإقامة الخضراء وتأشيرات العمل</a>
    <a href="https://www.egyptaway.com/p/gold-ae.html" style="background:#ca8a04;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✨ أسعار الذهب بالإمارات</a>
  </div>
</div>'''
        else:
            service_box = '''<div style="background:#fdf4ff;border:2px solid #f0abfc;border-radius:14px;padding:16px;margin:20px 0;text-align:center;">
  <div style="font-size:16.5px;font-weight:900;color:#86198f;margin-bottom:6px;">🇰🇼 خدمات ومعلومات تهم المقيمين والزائرين في الكويت</div>
  <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:10px;">
    <a href="https://www.egyptaway.com/p/currency-kw.html" style="background:#a21caf;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">💵 سعر الدينار الكويتي اليوم</a>
    <a href="https://www.egyptaway.com/p/gulf-work-visas.html" style="background:#0f172a;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✈️ تأشيرات وإقامات العمل بالخليج</a>
    <a href="https://www.egyptaway.com/p/gold-kw.html" style="background:#ca8a04;color:#fff!important;text-decoration:none!important;font-weight:700;padding:8px 16px;border-radius:8px;font-size:13.5px;">✨ أسعار الذهب بالكويت</a>
  </div>
</div>'''

        faq_html = ""
        if art.get("faq"):
            faq_items = "".join(f'<details style="border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin:8px 0;background:#fff;"><summary style="font-weight:800;font-size:15px;cursor:pointer;color:#1e293b;">{html.escape(q["q"])}</summary><p style="margin:10px 0 0;font-size:14.5px;color:#334155;border-top:1px dashed #e2e8f0;padding-top:10px;">{html.escape(q["a"])}</p></details>' for q in art["faq"][:4])
            faq_html = f'<div style="margin:24px 0;"><h2 style="font-size:19px;font-weight:900;color:#1e293b;margin-bottom:12px;">❓ أسئلة شائعة حول التريند</h2>{faq_items}</div>'

        full_html = lead_img_html + service_box + art["body"] + faq_html + service_box

        if dry:
            print(f"  [DRY RUN] Would publish: {art['title']}")
            print(f"  Slug: {art['slug']} | Real Image: {bool(real_img)}")
            state["done"].append({"q": cand["q"], "country": cand["geo"], "at": now.isoformat(), "ok": True, "dry": True})
            published_urls.append("dry-run-gulf-trend")
            break

        labels = ["أخبار", "تريند الخليج", cand["country_short"]]
        try:
            res = f.publish_live(tok, art, full_html, labels)
            post_url = res.get("url", "")
            print(f"  >>> PUBLISHED GULF TREND: {post_url} | {art['title']}")
            state["done"].append({
                "title": art["title"],
                "q": cand["q"],
                "country": cand["geo"],
                "post_url": post_url,
                "has_real_img": bool(real_img),
                "at": now.isoformat(),
                "ok": True
            })
            published_urls.append(post_url)
            all_known_titles.append(art["title"])
            break
        except Exception as ex:
            print("  Publishing failed:", ex)
            break

    state["done"] = state["done"][-300:]
    with open(STATE_FILE, "w", encoding="utf-8") as f_st:
        json.dump(state, f_st, ensure_ascii=False, indent=2)

    if published_urls and not dry:
        valid_urls = [u for u in published_urls if u.startswith("http")]
        if valid_urls:
            ping_indexnow(valid_urls)

    print(f"Gulf trends run completed. Published: {len(published_urls)} post(s).")


if __name__ == "__main__":
    main()
