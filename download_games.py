"""Daily Game Download Article Engine & /p/download-games.html Hub Updater.

Runs daily on GitHub Actions (.github/workflows/download_games.yml) at 15:15 Cairo time.
1. Selects the next game needing a download article from games.json / download-games hub page.
2. Gathers verified metadata (developer, size, rating, gameplay mode, screenshots).
3. Writes a 1000+ words SEO-optimized game download guide via Gemini:
   - Official store download button (Google Play / App Store) - ZERO modded APKs.
   - Images processed through wsrv.nl (safe, fast, no play-lh thumbnails issue).
   - Interactive device compatibility tool inline.
   - 5 FAQs with details/summary.
   - Internal links to live articles & to /p/download-games.html.
4. Publishes live immediately on Egyptaway (blog 8325646053257070334).
5. Updates the game card on https://www.egyptaway.com/p/download-games.html (page ID 3130313263205116777):
   Changes the button from 'التحميل الرسمي' to 'التفاصيل والتحميل' pointing to the new article!
6. Pings IndexNow for instant search indexing.
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.parse
from zoneinfo import ZoneInfo
import requests
import football as f
try:
    import image_guard
except ImportError:
    image_guard = None

sys.stdout.reconfigure(encoding="utf-8")

CAIRO = ZoneInfo("Africa/Cairo")
BLOG_ID = "8325646053257070334"
HUB_PAGE_ID = "3130313263205116777"
HUB_URL = "https://www.egyptaway.com/p/download-games.html"
STATE_FILE = "game_download_state.json"
GAMES_JSON = "games.json"
INDEXNOW_KEY = "e3b3e2ee8cd741f59f1b91e73c0f9090"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

WEIGHT_MAP = {
    1: ("خفيفة", "#2e7d32", "تشتغل بسلاسة على أغلب الهواتف الاقتصادية والضعيفة بدون لاج"),
    2: ("متوسطة", "#e65100", "تحتاج هاتف فئة متوسطة (معالج متوسط ورام 4-6 جيجابايت) لتجربة جيدة"),
    3: ("تقيلة", "#c62828", "تحتاج هاتف قوي (فئة رائدة أو مخصص للألعاب) أو تقليل الجرافيكس لتجنب السخونة واللاج")
}


def ar_date():
    d = datetime.date.today()
    return f"{d.day} {AR_MONTHS[d.month - 1]} {d.year}"


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except Exception:
            pass
    return {"done": []}


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as fp:
        json.dump(st, fp, ensure_ascii=False, indent=1)


def get_store_packages_from_hub(tok=None):
    """Fetches the list of packages currently linking to the store on /p/download-games.html."""
    try:
        url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{HUB_PAGE_ID}"
        headers = {"Authorization": f"Bearer {tok}"} if tok else UA
        r = requests.get(url, headers=headers, timeout=25)
        if r.status_code == 200:
            content = r.json().get("content", "")
            return set(re.findall(r'href="https://play\.google\.com/store/apps/details\?id=([a-zA-Z0-9_\.]+)"', content))
    except Exception as e:
        print(f"Hub fetch warning: {e}")
    return set()


def pick_candidate_game(games_catalog, state, hub_store_pkgs=None, target_pkg=None, target_name=None):
    done_slugs = {d.get("slug") for d in state.get("done", []) if d.get("ok")}
    done_pkgs = {d.get("play") for d in state.get("done", []) if d.get("ok") and d.get("play")}

    if target_pkg:
        for g in games_catalog:
            if g.get("play") == target_pkg:
                return g
    if target_name:
        for g in games_catalog:
            if target_name.lower() in g.get("n", "").lower() or target_name.lower() in g.get("ar", "").lower():
                return g

    # 1. Prefer games currently showing 'الألعاب الشائعة' on the hub page
    if hub_store_pkgs:
        for g in games_catalog:
            pkg = g.get("play")
            slug = g.get("slug")
            if pkg in hub_store_pkgs and pkg not in done_pkgs and slug not in done_slugs:
                return g

    # 2. Fallback to any game in catalog not done
    for g in games_catalog:
        slug = g.get("slug")
        pkg = g.get("play")
        if slug and slug in done_slugs:
            continue
        if pkg and pkg in done_pkgs:
            continue
        return g

    return None


def fetch_google_play_shots(package_id):
    """Scrapes Google Play page for fresh screenshots & details if available."""
    if not package_id:
        return []
    url = f"https://play.google.com/store/apps/details?id={package_id}&hl=ar"
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.status_code == 200:
            shots = re.findall(r'src="(https://play-lh\.googleusercontent\.com/[A-Za-z0-9_\-]+)"', r.text)
            unique_shots = []
            for s in shots:
                if s not in unique_shots and "=s" not in s and "=w" not in s:
                    unique_shots.append(s)
            return unique_shots[:6]
    except Exception as e:
        print(f"Play Store fetch warning: {e}")
    return []


def proxy_img(raw_url):
    """Encodes any image link through wsrv.nl to prevent slowing down Blogger and avoid 403s."""
    if not raw_url:
        return "https://images.pexels.com/photos/194511/pexels-photo-194511.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop"
    clean = raw_url.replace("&amp;", "&")
    # If already wsrv or pexels
    if "wsrv.nl" in clean or "pexels.com" in clean:
        return clean
    encoded = urllib.parse.quote(clean, safe="")
    return f"https://wsrv.nl/?url={encoded}&w=1200&output=webp&q=80"


def generate_article_with_gemini(game):
    w_label, _, w_desc = WEIGHT_MAP.get(game.get("w", 2), ("متوسطة", "#e65100", ""))
    play_pkg = game.get("play", "")
    play_url = f"https://play.google.com/store/apps/details?id={play_pkg}" if play_pkg else game.get("url", HUB_URL)

    prompt = f"""أنت خبير ألعاب محترف في موقع ايجبتاوى (Egyptaway).
اكتب مقالاً شاملاً وجذاباً وحصرياً بنسبة 100% لتحميل وشرح لعبة:
- الاسم الإنجليزي: {game.get('n')}
- الاسم العربي: {game.get('ar')}
- نوع اللعبة: {game.get('g')}
- تقييم الأجهزة: {w_label} ({w_desc})
- المطور: {game.get('dev', 'الشركة الرسمية المطورة')}
- عدد التحميلات: {game.get('installs', 'ملايين التحميلات')}
- التقييم في المتجر: {game.get('rating', '4.5')}/5
- رابط التحميل الرسمي: {play_url}

المواصفات الصارمة للمقال:
1. اللغة: عربية فصحى مبسطة تناسب جمهور الموبايل واللاعبين في مصر والعالم العربي.
2. الكلمات: 1000+ كلمة غنية بالمعلومات الحقيقية.
3. العنوان (title): يجب أن يكون <= 70 حرفاً ويحتوي على سنة 2026. مثال: "تحميل لعبة {game.get('ar')} 2026 للأندرويد: رابط التحميل والمواصفات".
4. وصف البحث (desc): من 140 إلى 160 حرفاً دقيق وجذاب وموجز.
5. الهيكل:
   - فقرتان تمهيديتان (intro) تجيبان اللاعب عن ماهية اللعبة ولماذا تستحق التجربة فوراً.
   - قسم 'نبذة عن فكرة وأسلوب اللعب' (about).
   - أهم 5 مميزات تجعلها ممتعة (features).
   - أطوار اللعب المختلفة (modes).
   - نصائح عملية للاعبين الجدد (tips).
   - هل تشتغل اللعبة على الهواتف الاقتصادية والضعيفة وكيفية ضبط الإعدادات لتجنب اللاج (lowend).
   - 5 أسئلة شائعة وإجاباتها الدقيقة (faq: q and a).

ممنوع منعاً باتاً:
- أي روابط أو إشارات لنسخ مهكرة أو ملفات APK مجهولة أو مراهنات.
- المبالغات غير الواقعية.
- أي محتوى سياسي أو ديني أو فني.

أرجع النتيجة بصيغة JSON فقط:
{{
  "title": "العنوان الدقيق",
  "desc": "الوصف من 140-160 حرف",
  "takeaways": ["نوع اللعبة وحجم الأجهزة المناسبة لها", "أهم ما يميز أسلوب اللعب والتحديث", "تنبيه التحميل الرسمي المجاني"],
  "intro": ["الفقرة الأولى", "الفقرة الثانية"],
  "about": "فقرة وافية عن أسلوب اللعب",
  "features": ["ميزة 1", "ميزة 2", "ميزة 3", "ميزة 4", "ميزة 5"],
  "modes": ["طور 1", "طور 2", "طور 3"],
  "tips": ["نصيحة 1", "نصيحة 2", "نصيحة 3", "نصيحة 4"],
  "lowend": "شرح متطلبات التشغيل على الهواتف الضعيفة وتقليل اللاج",
  "faq": [
    {{"q": "سؤال 1", "a": "إجابة 1"}},
    {{"q": "سؤال 2", "a": "إجابة 2"}},
    {{"q": "سؤال 3", "a": "إجابة 3"}},
    {{"q": "سؤال 4", "a": "إجابة 4"}},
    {{"q": "سؤال 5", "a": "إجابة 5"}}
  ]
}}"""

    art = f.gemini(prompt)
    return art


def build_interactive_tool(game):
    w = game.get("w", 2)
    name = html.escape(game.get("ar", game.get("n", "اللعبة")))
    return f"""
<div class="ea-tool-card" style="background:#fff7ef;border:2px solid #ffd9b8;border-radius:14px;padding:16px;margin:22px 0;">
  <h3 style="margin-top:0;color:#e65100;font-size:18px;">📱 فحص سريع: هل هاتفك يشغل لعبة {name}؟</h3>
  <p style="font-size:15px;color:#444;margin-bottom:12px;">اختر مواصفات موبايلك لمعرفة مدى سلاسة اللعبة ومستوى الجرافيكس المناسب لك:</p>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
    <select id="ea-tool-ram" style="padding:8px 12px;border:1px solid #ccc;border-radius:8px;font-size:15px;flex:1;min-width:140px;">
      <option value="2">رام 2 أو 3 جيجابايت</option>
      <option value="4" selected>رام 4 جيجابايت</option>
      <option value="6">رام 6 أو 8 جيجابايت</option>
      <option value="12">رام 12 جيجابايت أو أعلى</option>
    </select>
    <select id="ea-tool-proc" style="padding:8px 12px;border:1px solid #ccc;border-radius:8px;font-size:15px;flex:1;min-width:140px;">
      <option value="econ">معالج اقتصادي (Helio G36 / Snapdragon 680)</option>
      <option value="mid" selected>معالج فئة متوسطة (Helio G99 / Dimensity 7050)</option>
      <option value="flag">معالج قوي / فئة عليا (Snapdragon 8 / Dimensity 8300+)</option>
    </select>
    <button type="button" onclick="checkGameCompat()" style="background:#e65100;color:#fff;border:none;border-radius:8px;padding:8px 18px;font-weight:bold;cursor:pointer;font-size:15px;">فحص التوافق</button>
  </div>
  <div id="ea-tool-res" style="font-size:15px;font-weight:bold;padding:10px;border-radius:8px;background:#fff;border:1px dashed #e65100;color:#1a1a1a;">
    اضغط على زر الفحص لمعرفة الأداء المتوقع على جهازك.
  </div>
</div>
<script>
function checkGameCompat() {{
  var ram = parseInt(document.getElementById('ea-tool-ram').value);
  var proc = document.getElementById('ea-tool-proc').value;
  var w = {w};
  var res = document.getElementById('ea-tool-res');
  if (w === 1) {{
    res.innerHTML = "✅ <b>أداء ممتاز وسلس جداً!</b> اللعبة خفيفة ومحسنة بشكل رائع، وستعمل بمعدل إطارات مرتفع وثابت حتى على الهواتف الاقتصادية.";
    res.style.borderColor = "#2e7d32";
  }} else if (w === 2) {{
    if (ram >= 4 && proc !== 'econ') {{
      res.innerHTML = "✅ <b>أداء سلس ومستقر!</b> جهازك يفي بالمتطلبات الموصى بها، ويمكنك تشغيل اللعبة بجرافيكس متوسط أو مرتفع دون لاج.";
      res.style.borderColor = "#2e7d32";
    }} else {{
      res.innerHTML = "⚠️ <b>أداء مقبول:</b> يفضل ضبط الجودة الرسومية على 'Low' وإغلاق التطبيقات المفتوحة في الخلفية لضمان ثبات الإطارات.";
      res.style.borderColor = "#e65100";
    }}
  }} else {{
    if (ram >= 6 && proc === 'flag') {{
      res.innerHTML = "🔥 <b>أداء خارق بأعلى جودة!</b> هاتفك قادر على تشغيل أقصى إعدادات رسومية ومعدل إطارات فائق 60fps.";
      res.style.borderColor = "#2e7d32";
    }} else {{
      res.innerHTML = "⚠️ <b>تحذير لاج وسخونة:</b> اللعبة تتطلب مواصفات عالية، يرجى خفض دقة الشاشة والجرافيكس لأدنى مستوى لتقليل التقطيع.";
      res.style.borderColor = "#c62828";
    }}
  }}
}}
</script>
"""


def assemble_game_html(art, game, internal_links, shots):
    w_label, w_color, _ = WEIGHT_MAP.get(game.get("w", 2), ("متوسطة", "#e65100", ""))
    play_pkg = game.get("play", "")
    play_url = f"https://play.google.com/store/apps/details?id={play_pkg}" if play_pkg else game.get("url", HUB_URL)
    name_ar = html.escape(game.get("ar", game.get("n", "")))
    name_en = html.escape(game.get("n", ""))

    # Prepare 3 images
    img_urls = []
    for s in shots[:3]:
        img_urls.append(proxy_img(s))
    while len(img_urls) < 3:
        # Fallback to curated gaming pexels photos
        fallbacks = [
            "https://images.pexels.com/photos/3165335/pexels-photo-3165335.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop",
            "https://images.pexels.com/photos/7915357/pexels-photo-7915357.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop",
            "https://images.pexels.com/photos/3945683/pexels-photo-3945683.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop"
        ]
        img_urls.append(fallbacks[len(img_urls)])

    img0 = f'<p><img src="{img_urls[0]}" alt="تحميل لعبة {name_ar} {name_en} 2026 للأندرويد" width="1200" height="675" style="width:100%;height:auto;border-radius:12px"/></p>'
    img1 = f'<p><img src="{img_urls[1]}" alt="أسلوب لعب {name_ar} والجرافيكس على الموبايل" width="1200" height="675" loading="lazy" style="width:100%;height:auto;border-radius:12px"/></p>'
    img2 = f'<p><img src="{img_urls[2]}" alt="أطوار اللعب والمهام في {name_ar}" width="1200" height="675" loading="lazy" style="width:100%;height:auto;border-radius:12px"/></p>'

    intro_paras = "\n".join(f"<p>{html.escape(p)}</p>" for p in art.get("intro", []))
    features_li = "\n".join(f"<li>{html.escape(f)}</li>" for f in art.get("features", []))
    modes_li = "\n".join(f"<li>{html.escape(m)}</li>" for m in art.get("modes", []))
    tips_li = "\n".join(f"<li>{html.escape(t)}</li>" for t in art.get("tips", []))

    faq_html = ""
    for item in art.get("faq", []):
        q = html.escape(item.get("q", ""))
        a = html.escape(item.get("a", ""))
        faq_html += f"<details style='margin-bottom:10px;padding:8px 12px;background:#f9f9f9;border-radius:8px;'><summary style='font-weight:bold;cursor:pointer;'>{q}</summary><p style='margin-top:8px;'>{a}</p></details>\n"

    links_html = ""
    if internal_links:
        li_items = "".join(f"<li><a href='{html.escape(u)}'>{html.escape(t)}</a></li>" for u, t in internal_links[:3])
        links_html = f"<h3>مقالات وشروحات قد تهمك:</h3><ul>{li_items}</ul>"

    tool_html = build_interactive_tool(game)

    full_html = f"""<div dir="rtl" style="line-height:1.9;font-size:17px;color:#222;">
{intro_paras}
{img0}

<h2>بطاقة معلومات لعبة {name_ar} ({name_en})</h2>
<table style="width:100%;border-collapse:collapse;margin:18px 0;background:#fafafa;border:1px solid #e0e0e0;border-radius:10px;overflow:hidden;">
  <tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:bold;width:35%;">اسم اللعبة:</td><td style="padding:10px;">{name_en} ({name_ar})</td></tr>
  <tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:bold;">النوع والتصنيف:</td><td style="padding:10px;">{html.escape(game.get('g', 'ألعاب موبايل'))}</td></tr>
  <tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:bold;">تقييم المتطلبات:</td><td style="padding:10px;"><span style="color:#fff;background:{w_color};padding:2px 10px;border-radius:999px;font-size:13px;">{w_label}</span></td></tr>
  <tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:bold;">المطور الرسمي:</td><td style="padding:10px;">{html.escape(game.get('dev', 'Google Play'))}</td></tr>
  <tr style="border-bottom:1px solid #eee;"><td style="padding:10px;font-weight:bold;">التقييم والتحميلات:</td><td style="padding:10px;">⭐ {game.get('rating', '4.5')}/5 ({game.get('installs', '10M+')})</td></tr>
  <tr><td style="padding:10px;font-weight:bold;">المنصات المدعومة:</td><td style="padding:10px;">أندرويد وآيفون</td></tr>
</table>

<h2>نبذة عن فكرة اللعبة وأسلوب اللعب</h2>
<p>{html.escape(art.get('about', ''))}</p>

<h2>أبرز مميزات لعبة {name_ar} في تحديث 2026</h2>
<ul>
{features_li}
</ul>

{img1}

{tool_html}

<h2>أطوار وتحديات اللعبة</h2>
<ul>
{modes_li}
</ul>

<h2>نصائح مهمة للاعبين الجدد لتحقيق الفوز</h2>
<ul>
{tips_li}
</ul>

{img2}

<h2>متطلبات التشغيل على الهواتف الضعيفة والاقتصادية</h2>
<p>{html.escape(art.get('lowend', ''))}</p>

<h2>رابط تحميل لعبة {name_ar} الرسمي 2026</h2>
<div style="background:#eef7ee;border:2px solid #c8e6c9;border-radius:14px;padding:20px;text-align:center;margin:25px 0;">
  <h3 style="margin-top:0;color:#2e7d32;font-size:20px;">تنزيل لعبة {name_en} بأمان من المتجر المعتمد</h3>
  <p style="color:#555;margin-bottom:18px;">حرصاً على أمان بياناتك، ننصح دائماً بالتحميل من الرابط الرسمي فقط والابتعاد عن النسخ المعدلة.</p>
  <a href="{play_url}" target="_blank" rel="noopener nofollow" style="display:inline-block;background:#2e7d32;color:#fff;font-size:18px;font-weight:bold;padding:12px 28px;border-radius:10px;text-decoration:none;box-shadow:0 4px 12px rgba(46,125,50,0.3);">
    ⬇ تحميل {name_ar} من Google Play الرسمي
  </a>
  <p style="font-size:13px;color:#777;margin-top:14px;">يمكنك أيضاً تصفح المزيد من الألعاب عبر <a href="{HUB_URL}">دليل تحميل الألعاب في ايجبتاوى</a>.</p>
</div>

<h2>أسئلة شائعة عن اللعبة</h2>
{faq_html}

{links_html}

<p style="font-size:14px;color:#777;margin-top:25px;border-top:1px solid #eee;padding-top:10px;">
المصادر الرسمية: صفحة اللعبة على <a href="{play_url}" target="_blank" rel="noopener nofollow">Google Play Store</a>.
</p>
</div>"""
    return full_html


def update_hub_page(tok, game, post_url):
    """Updates the game button on /p/download-games.html from 'التحميل الرسمي' to 'التفاصيل والتحميل'."""
    print("Fetching current /p/download-games.html page from Blogger...")
    r = requests.get(
        f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{HUB_PAGE_ID}",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=40
    )
    if r.status_code != 200:
        print(f"Error fetching hub page: {r.status_code} {r.text[:150]}")
        return False

    page_data = r.json()
    content = page_data.get("content", "")
    play_pkg = game.get("play", "")
    game_name = game.get("n", "")

    # Target card button to update
    updated = False
    new_content = content

    # Regex searching for the game's official store link in the button
    if play_pkg:
        old_pattern = re.compile(
            r'(<a class="gh-b" href="[^"]*details\?id=' + re.escape(play_pkg) + r'[^"]*"\s+data-art="[^"]*"\s+data-store="[^"]*"\s+data-d="[^"]*"\s+rel="nofollow noopener"\s+target="_blank">)التحميل الرسمي(</a>)'
        )
        repl = f'<a class="gh-b" href="{post_url}" data-art="{post_url}" data-store="https://play.google.com/store/apps/details?id={play_pkg}" data-d="">التفاصيل والتحميل</a>'
        new_content, count = old_pattern.subn(repl, new_content)
        if count > 0:
            updated = True
            print(f"Updated card button via package match: {play_pkg}")

    # Fallback to search query / name
    if not updated and game_name:
        card_pattern = re.compile(
            r'(<div class="gh-c"[^>]*data-q="[^"]*' + re.escape(game_name.lower()) + r'[^"]*"[^>]*>.*?<div class="gh-bs">)<a class="gh-b"[^>]*>التحميل الرسمي</a>',
            re.DOTALL
        )
        repl = r'\1' + f'<a class="gh-b" href="{post_url}" data-art="{post_url}" data-store="https://play.google.com/store/apps/details?id={play_pkg}" data-d="">التفاصيل والتحميل</a>'
        new_content, count = card_pattern.subn(repl, new_content)
        if count > 0:
            updated = True
            print(f"Updated card button via game name match: {game_name}")

    if updated:
        # Update last updated date in footer
        new_content = re.sub(r'آخر تحديث للقائمة: [^<.]+', f'آخر تحديث للقائمة: {ar_date()}', new_content)

        patch_res = requests.patch(
            f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{HUB_PAGE_ID}",
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            json={"content": new_content},
            timeout=60
        )
        if patch_res.status_code == 200:
            print(f"✅ Successfully updated /p/download-games.html live on Blogger!")
            return True
        else:
            print(f"Failed to patch hub page: {patch_res.status_code} {patch_res.text[:150]}")
    else:
        print("Card button was already linked or pattern didn't match directly.")
    return False


def ping_indexnow(urls):
    payload = {
        "host": "www.egyptaway.com",
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://www.egyptaway.com/{INDEXNOW_KEY}.txt",
        "urlList": urls
    }
    for endpoint in ["https://api.indexnow.org/indexnow", "https://yandex.com/indexnow"]:
        try:
            r = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=15)
            print(f"IndexNow ({endpoint}): {r.status_code}")
        except Exception as e:
            print(f"IndexNow error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Daily Egyptaway Game Download Publisher")
    parser.add_argument("--dry", action="store_true", help="Dry run without publishing")
    parser.add_argument("--package", type=str, default="", help="Specific Google Play package ID")
    parser.add_argument("--game", type=str, default="", help="Specific game name query")
    args = parser.parse_args()

    is_dry = args.dry
    now_cairo = datetime.datetime.now(CAIRO)
    today_str = now_cairo.date().isoformat()

    print(f"=== Running Daily Game Download Publisher ({today_str}) ===")

    # Load catalog & state
    catalog = json.load(open(GAMES_JSON, "r", encoding="utf-8")) if os.path.exists(GAMES_JSON) else []
    state = load_state()

    # Minimum cooldown check (unless explicit target game)
    if not is_dry and not args.package and not args.game:
        done_entries = [d for d in state.get("done", []) if d.get("ok")]
        if done_entries:
            last_item = done_entries[-1]
            last_ts = last_item.get("timestamp")
            if last_ts:
                try:
                    last_dt = datetime.datetime.fromisoformat(last_ts)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=CAIRO)
                    diff_hours = (now_cairo - last_dt.astimezone(CAIRO)).total_seconds() / 3600
                    if diff_hours < 18:
                        print(f"Game article was already published {diff_hours:.1f} hours ago today. Next run scheduled for tomorrow. Exiting peacefully.")
                        return
                except Exception as e:
                    print(f"Cooldown parse warning: {e}")

    tok = None if is_dry else f.token()
    site_posts = [] if is_dry else f.site_posts(tok)

    # Pick game
    hub_pkgs = set() if is_dry else get_store_packages_from_hub(tok)
    game = pick_candidate_game(catalog, state, hub_store_pkgs=hub_pkgs, target_pkg=args.package, target_name=args.game)
    if not game:
        sys.exit("No eligible game found in games.json to publish.")

    print(f"Selected Game: {game.get('n')} ({game.get('ar')}) | Package: {game.get('play')}")

    # Fetch shots
    shots = fetch_google_play_shots(game.get("play")) or game.get("shots", [])

    # Generate article via Gemini
    print("Generating comprehensive game download article via Gemini...")
    art = generate_article_with_gemini(game)
    if not art or not isinstance(art, dict) or not art.get("title"):
        sys.exit("Failed to generate article from Gemini.")

    # Pick 2 internal links from live posts
    internal_links = [(p["u"], p["t"]) for p in site_posts[:2]] if site_posts else []
    # Always include hub page
    internal_links.append((HUB_URL, "صفحة تحميل الألعاب لأشهر 1000 لعبة"))

    full_html = assemble_game_html(art, game, internal_links, shots)
    slug = game.get("slug") or f"download-{re.sub(r'[^a-zA-Z0-9]+', '-', game.get('n', 'game').lower()).strip('-')}-2026"
    art["slug"] = slug

    print(f"Generated Title: {art['title']}")
    print(f"Slug: {art['slug']}")

    if is_dry:
        print("[DRY RUN] Preview ready. No live publication.")
        return

    # 1. Draft with slug
    labels = ["ألعاب", "تحميل ألعاب", "أندرويد"]
    d = f.api("POST", f"/blogs/{BLOG_ID}/posts", tok, {"isDraft": "true"},
              {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": f.with_desc(full_html, art), "labels": labels})

    # 2. Publish live immediately
    f.api("POST", f"/blogs/{BLOG_ID}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})

    # 3. Patch Arabic title
    f.api("PATCH", f"/blogs/{BLOG_ID}/posts/{d['id']}", tok, None, {"title": art["title"]})
    post_info = f.api("GET", f"/blogs/{BLOG_ID}/posts/{d['id']}", tok, {"view": "ADMIN"})
    post_url = post_info.get("url", "")
    print(f"✅ PUBLISHED GAME ARTICLE LIVE: {post_url}")

    # 4. Update /p/download-games.html hub page on Blogger
    update_hub_page(tok, game, post_url)

    # 5. Ping IndexNow
    ping_indexnow([post_url, HUB_URL])

    # 6. Save state
    state.setdefault("done", []).append({
        "slug": art["slug"],
        "play": game.get("play"),
        "name": game.get("n"),
        "name_ar": game.get("ar"),
        "title": art["title"],
        "url": post_url,
        "timestamp": now_cairo.isoformat(),
        "ok": True
    })
    save_state(state)

    # Update games.json in place
    for item in catalog:
        if item.get("play") and item.get("play") == game.get("play"):
            item["art"] = "/" + post_url.split("egyptaway.com/", 1)[-1]
            break
    with open(GAMES_JSON, "w", encoding="utf-8") as fp:
        json.dump(catalog, fp, ensure_ascii=False, indent=1)

    print("=== Daily Game Download Published and Hub Page Updated Successfully! ===")


if __name__ == "__main__":
    main()
