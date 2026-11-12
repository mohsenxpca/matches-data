"""Review (review-mobile.com) Autonomous Phone News & Review Engine (mohsen 2026-10-29, updated 2026-11-02).
Publishes 100% brand-new, comprehensive phone reviews AND breaking smartphone news 24/7.
Strict AdSense compliance:
- Reviews (1000+ words): specs matrix, EGP/SAR/AED pricing with converter, pros/cons, FAQs, internal links.
- Phone News (800+ words): in-depth technical analysis of leaks, updates, processors, cameras, displays, and phone tech.
- 100% watermark-free, clean phone imagery: all images are smartly cropped to remove source site names/logos,
  aesthetically altered with contrast/color/sharpness enhancements, and saved in high-res 1200x675.

Usage:
  python review_engine.py                        # Scans for hottest unreviewed phones and breaking phone news
  python review_engine.py "Samsung W27"          # Publishes a review/news for a specific model on-demand
  python review_engine.py --mode news            # Prioritize breaking phone news
  python review_engine.py --mode review          # Prioritize full phone reviews
  python review_engine.py --dry                  # Dry run (prints draft without publishing)
"""
import argparse, datetime, difflib, html, io, json, os, random, re, sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None
import football as f
import notify
import image_guard

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
GSMA_UA = {**UA, "Referer": "https://www.gsmarena.com/"}
REVIEW_BLOG = "2997328666613207792"
REVIEW_HOST = "www.review-mobile.com"
STATE_FILE = "review_posted.json"
REVIEW_CAP = int(os.environ.get("REVIEW_DAY_CAP", "8"))
COUNT = int(os.environ.get("COUNT", "2"))
CDN = "https://cdn.jsdelivr.net/gh/mohsenxpca/matches-data@main/"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "img")
WM_LIGHT = os.path.join(IMG_DIR, "review_wm_light.png")
WM_DARK = os.path.join(IMG_DIR, "review_wm_dark.png")
AR_FONT_PATH = os.path.join(BASE_DIR, "fonts", "NotoKufiArabic.ttf")
AR_FONT_URL = "https://github.com/google/fonts/raw/main/ofl/notokufiarabic/NotoKufiArabic%5Bwght%5D.ttf"

EUR_RATES = {"egp": 52.0, "sar": 4.05, "aed": 3.97}
CNY_RATES = {"egp": 6.8, "sar": 0.527, "aed": 0.516}
USD_RATES = {"egp": 49.0, "sar": 3.75, "aed": 3.67}

BAD_IMG_PATTERNS = (
    "pexels.com", "unsplash.com", "pixabay.com", "shutterstock.com", "istockphoto.com",
    "amazon-com", "icon", "logo", "banner", "avatar", "advert", "button",
    "badge", "favicon", "gravatar", "emoji", "spinner", "placeholder", "150x150", "-184x111"
)

DISCLAIMER = "هذه المراجعة مبنية على المواصفات الرسمية والمصادر المعلنة، وليست تجربة استخدام شخصية."

BRANDS = [
    ("ريد ماجيك", re.compile(r"red ?magic|ريد ماجيك|nubia", re.I)),
    ("سامسونج", re.compile(r"samsung|galaxy|سامسونج", re.I)),
    ("أبل", re.compile(r"\b(iphone|apple)\b|(?:\b|(?<=[\s,.:]))(أبل|ابل|آيفون|ايفون)(?:\b|(?=[\s,.:]))", re.I)),
    ("شاومي", re.compile(r"xiaomi|redmi|poco|شاومي|ريدمي|بوكو", re.I)),
    ("اوبو", re.compile(r"oppo|اوبو|أوبو|find x|reno", re.I)),
    ("فيفو", re.compile(r"vivo|iqoo|فيفو|آيكو", re.I)),
    ("هونر", re.compile(r"honor|هونر|magic", re.I)),
    ("ريلمى", re.compile(r"realme|ريلمى|ريلمي", re.I)),
    ("هواوي", re.compile(r"huawei|هواوي|هوواوى|mate|pura", re.I)),
    ("وان بلس", re.compile(r"oneplus|one plus|وان بلس|ون بلس|nord", re.I)),
    ("انفينكس", re.compile(r"\b(infinix|zero|hot\s*\d+|smart\s*\d+)\b|انفينكس", re.I)),
    ("تيكنو", re.compile(r"tecno|تيكنو|تكنو|camon|spark|phantom", re.I)),
    ("موتورولا", re.compile(r"motorola|moto\b|موتورولا|موتوريلا|razr|edge", re.I)),
    ("بيكسل", re.compile(r"pixel|بيكسل|google pixel", re.I)),
    ("اسوس", re.compile(r"asus|rog phone|اسوس|zenfone", re.I)),
    ("نوكيا", re.compile(r"nokia|نوكيا", re.I)),
    ("سوني", re.compile(r"sony|xperia|إكسبيريا", re.I)),
    ("ناثينج", re.compile(r"nothing\s*phone|ناثينج|cmf", re.I)),
]


HALLUCINATED_OR_FAKE_EXCLUSIONS = re.compile(
    r"\b(s27|s28|s29|s30|z fold9|z fold10|android\s*(?:1[7-9]|[2-9]\d)|ios\s*(?:2[2-9]|[3-9]\d)|one\s*ui\s*(?:9|\d{2})|x500|x600|honor\s*(?:600|700|x80)|signature\s*27|iphone\s*duo|11000\s*mah|12000\s*mah|doorbell|projector|headphones?|earbuds?|smartwatch(?:es)?)\b",
    re.I
)

NON_PHONE_EXCLUSIONS = re.compile(
    r"\b(watch(?:es)?|smartwatch(?:es)?|smart\s*ring|band\b|buds\d*|earbuds\d*|airpods\d*|headphones?\d*|earphones?\d*|headsets?\d*|speakers?|soundbars?|laptops?|macbooks?|imac|mac\s*mini|chromebooks?|windows\s*11|copilot\+?\s*pc|ipads?|tablets?|pads?|tab\b|tvs?|television|apple\s*tv|apple\s*watch|carplay|vision\s*pro|vacuum|cleaners?|cars?|ev\b|auto\b|ring\b|projectors?|doorbells?|drones?|refrigerators?|washers?|washing|shoes?|massag(?:er|es|ing)?|waist|heater|heating|purifier|toothbrush|blanket|pillow|shaver|clipper|cooker|kettle|oven|fryer|humidifier|dehumidifier|scale|thermometer|lamp|light|bulb|fan\b|desk|table|chair|backpack|jacket|coat|umbrella|pen\b|bottle|eyewear|glasses)\b",
    re.I
)

NON_MOBILE_NEWS_EXCLUSIONS = re.compile(
    r"\b(linkedin|facebook|instagram|tiktok|snapchat|twitter|x\.com|reddit|discord|netflix|spotify|youtube|antitrust|lawsuit|court|judge|ruling|verdict|trial|regulator|congress|senate|FTC|DOJ|SEC|copyright|journalist|journalists|election|politics|layoff|layoffs|merger|acquisition|ipo|stock\s*price|cyberattack|ransomware|data\s*breach|workplace|hiring|subscription\s*hike|streaming\s*service|social\s*network|privacy\s*ruling)\b",
    re.I
)

CSS = """<style>
.rv-wrap{color:#1a1a1a;background:#fff;line-height:1.9;font-size:17px;font-family:system-ui,-apple-system,sans-serif}
.rv-wrap h2{color:#0f172a;margin-top:1.8em;padding-bottom:6px;border-bottom:2px solid #e2e8f0;font-size:22px}
.rv-wrap h3{color:#1e293b;margin-top:1.3em;font-size:19px}
.rv-fig{background:#f8fafc;padding:12px;text-align:center;margin:20px 0;border-radius:12px;border:1px solid #e2e8f0}
.rv-fig img{max-width:100%;height:auto;border-radius:8px}
.rv-fig figcaption{color:#64748b;font-size:14px;margin-top:8px;font-weight:500}
.rv-scroll{overflow-x:auto;margin:16px 0}
.rv-table{border-collapse:collapse;width:100%;color:#1a1a1a;background:#fff;font-size:15px}
.rv-table th,.rv-table td{border:1px solid #cbd5e1;padding:10px 12px;text-align:right}
.rv-table th{background:#f1f5f9;color:#0f172a;font-weight:700}
.rv-box{background:#eff6ff;border-right:4px solid #2563eb;padding:12px 16px;margin:18px 0;border-radius:8px;font-size:15px;line-height:1.7}
.rv-pros{background:#f0fdf4;border-right:4px solid #16a34a;padding:14px 18px;margin:16px 0;border-radius:8px}
.rv-cons{background:#fef2f2;border-right:4px solid #dc2626;padding:14px 18px;margin:16px 0;border-radius:8px}
.rv-pros strong{color:#15803d;font-size:17px}
.rv-cons strong{color:#b91c1c;font-size:17px}
.rv-tool{background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:16px;margin:20px 0}
.rv-tool input,.rv-tool button{font:inherit;font-size:15px;padding:8px 12px;border-radius:8px;border:1px solid #94a3b8}
.rv-tool button{background:#2563eb;color:#fff;font-weight:700;border:none;cursor:pointer;margin-top:8px}
.rv-wrap details{border:1px solid #e2e8f0;border-radius:10px;padding:10px 14px;margin:10px 0;background:#f8fafc}
.rv-wrap details summary{font-weight:700;cursor:pointer;color:#0f172a}
.rv-wrap details p{margin:8px 0 0;color:#334155}
.rv-tldr{background:#eff6ff;border:1px solid #bfdbfe;border-right:4px solid #2563eb;border-radius:12px;padding:14px 16px;margin:16px 0}
.rv-scorecard{background:#f8fafc;border:1px solid #cbd5e1;border-radius:14px;padding:16px;margin:20px 0}
.rv-sc-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px}
.rv-sc-badge{background:#0f172a;color:#fff;font-weight:900;font-size:18px;padding:4px 12px;border-radius:999px}
.rv-sc-row{margin:9px 0}
.rv-sc-lbl{display:flex;justify-content:space-between;font-size:14.5px;font-weight:700;color:#1e293b;margin-bottom:4px}
.rv-sc-bar{background:#e2e8f0;height:10px;border-radius:999px;overflow:hidden}
.rv-sc-fill{background:linear-gradient(90deg,#2563eb,#16a34a);height:100%;border-radius:999px}
.rv-sc-fill-b{background:linear-gradient(90deg,#ea580c,#f59e0b);height:100%;border-radius:999px}
.rv-vote{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:14px 16px;margin:18px 0}
.rv-vote-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.rv-vote-btns button{background:#fff;border:1.5px solid #2563eb;color:#1e40af;border-radius:10px;padding:8px 14px;font-weight:800;cursor:pointer;flex:1;min-width:130px;font:inherit}
.rv-vote-btns button:hover{background:#2563eb;color:#fff}
.rv-diff-btn{background:#0f172a;color:#fff;border:0;border-radius:8px;padding:7px 14px;font:inherit;font-size:14px;font-weight:700;cursor:pointer;margin:8px 0}
.rv-hide-row{display:none}
</style>"""

REVIEW_PROMPT_TEMPLATE = """أنت محرر ومراجع هواتف محترف وخبير تقني في موقع «رفيو» (review-mobile.com).
الموقع يستعد للتقديم والقبول في Google AdSense، لذلك يجب أن تكون المراجعة ذات قيمة مضافة حقيقية، غنية بالتحليل والشرح، وتتجاوز 1000 كلمة (بين 1050 إلى 1300 كلمة).

الموضوع أو الهاتف المستهدف: «{topic_title}»
البيانات والمصادر الموثقة:
{src_text}

قواعد التحرير الصارمة لرفيو:
1. عدم تكرار الكلام السطحي: اكتب بأسلوب تحليلي صحفي راقٍ ومفهوم لجمهور الوطن العربي، واشرح عواقب كل مواصفة عملياً.
2. جدول المواصفات الكامل: ضع جدول HTML (<table class="rv-table">) يشمل كل البنود بدقة تامة اعتماداً على المصدر فقط:
   - الشاشة والتردد والسطوع
   - المعالج والرسوميات
   - الرام والتخزين
   - الكاميرات الخلفية والأمامية وقدرات الفيديو
   - البطارية وسرعة الشحن والشاحن في العلبة
   - مقاومة الماء والوزن والخامات
3. أقسام تفصيلية (H2 و H3) تغطي:
   - التصميم والشاشة وخامات التصنيع
   - الأداء وتجربة الألعاب والاستخدام اليومي ونظام التبريد
   - الكاميرات وجودة الصور في النهار والليل
   - البطارية والشحن وعمر الاستخدام
4. السعر والتحويل: احسب السعر الرسمي أو المتوقع بالأرقام:
   - باليورو أو الدولار
   - بالجنيه المصري (1 يورو = 52 جنيه أو 1 دولار = 49 جنيه)
   - بالريال السعودي (1 يورو = 4.05 ريال أو 1 دولار = 3.75 ريال)
   - بالدرهم الإماراتي (1 يورو = 3.97 درهم أو 1 دولار = 3.67 درهم)
5. المميزات والعيوب: 4 إلى 5 مميزات قوية في (<div class="rv-pros">)، و 3 إلى 4 عيوب واضحة بمصداقية في (<div class="rv-cons">).
6. لمن يناسب هذا الهاتف؟: جدول (<table class="rv-table">) يوضح (فئة المستخدم، هل يناسبه؟، السبب بالتفصيل).
7. رأي رفيو النهائي (هل يستحق الشراء؟): فقرة تقييمية ختامية تقدم نصيحة شراء مخلصة وقاطعة.
8. أسئلة شائعة: 4 أسئلة شائعة وإجاباتها في علامات <details><summary>السؤال</summary><p>الإجابة</p></details>.
9. الالتزام بجميع الأرقام الواردة في المصدر وعدم اختراع أي رقم غير منشور.
10. لا تذكر اسم الموقع المصدر (مثل GSMArena أو Gizmochina) داخل نص المراجعة.
11. أضف تقييماً موضوعياً من 10 في حقل scores بناءً على مواصفات المصدر فقط (screen, performance, camera, battery, value)، و3-4 نقاط ملخصة حاسمة في حقل takeaways.

رجّع الرد بتنسيق JSON صالح فقط كالتالي دون أي زيادات:
{{
  "kind": "review",
  "phone_name": "{topic_title}",
  "title": "مراجعة {topic_title} 2026: المواصفات الكاملة والسعر والمميزات والعيوب",
  "slug": "english-slug-3-to-6-words",
  "desc": "وصف دقيق للبحث من 140 إلى 160 حرف يبدأ بأهم مواصفة والسعر الرسمي بالجنيه والريال.",
  "brand": "اسم الماركة بالعربي فقط (مثال: سامسونج، شاومي، هونر، أوبو، فيفو)",
  "price_eur": 450,
  "scores": {{"screen": 8.5, "performance": 8.2, "camera": 8.0, "battery": 8.6, "value": 8.4}},
  "takeaways": ["أبرز ميزة بالأرقام من المصدر", "نقطة القوة الأساسية في الأداء أو الشاشة", "تفاصيل البطارية والشحن", "خلاصة القيمة مقابل السعر"],
  "body": "<h2>..</h2><p>..</p>...",
  "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]
}}
"""

NEWS_PROMPT_TEMPLATE = """أنت صحفي تقني وخبير هواتف ذكية ومحرر في موقع «رفيو» (review-mobile.com).
الموقع يقدم تغطية إخبارية وتحليلية شاملة لكل ما يخص الهواتف الذكية (تسريبات، إعلانات رسمية، تحديثات نظام، معالجات هواتف، تقنيات كاميرات وبطاريات).
المطلوب كتابة تقرير إخباري تحليلي متكامل يتجاوز 850 كلمة (بين 850 إلى 1100 كلمة) يواكب معايير Google AdSense و Google Discover.

عنوان الخبر أو الموضوع: «{topic_title}»
البيانات والنص المصدر:
{src_text}

قواعد التحرير الصارمة لرفيو:
1. الجاذبية في Google Discover (Curiosity Gap): صياغة عنوان مشوق يثير فضول القارئ بمصداقية كاملة (بين 45 و 68 حرفاً) يجيب على التساؤل الفعلي ويوضح الفائدة المباشرة (أمثلة: التفاصيل الكاملة لما تخفيه مواصفات Galaxy S27 Ultra.. موعد الإطلاق الرسمي وأهم المزايا، أو: هل يستحق الترقية؟ ما الفارق الحقيقي بين الجيلين.. المراجعة الشاملة). ممنوع العناوين المضللة أو المبهمة.
2. العمق والتحليل: اشرح تفاصيل الخبر وسياقه التقني، ماذا تعني هذه الميزة أو المواصفة للمستخدم، وكيف ستؤثر على سوق الهواتف الذكية وتجربة الاستخدام اليومية.
3. هيكل التقرير (أقسام H2 و H3):
   - تفاصيل الخبر أو التسريب أو الإعلان الرسمي بدقة
   - التحليل التقني والمواصفات المرتبطة وتأثيرها على الأداء
   - مقارنة بالجيل السابق أو بالهواتف المنافسة في السوق
   - الموعد المتوقع للتوفر والأسعار التقديرية بالعملات العربية (إن وردت)
4. جدول المواصفات: لو الخبر عن موبايل أو تابلت معيّن، لازم تحط جدول من عمودين بس (<table class="rv-table">) أول صف فيه <tr><th>المواصفة</th><th>اسم الموبايل بالإنجليزي</th></tr> وبعده صف لكل مواصفة مذكورة في المصدر (الشاشة، المعالج، الرام والتخزين، الكاميرا الخلفية، الكاميرا الأمامية، البطارية والشحن، نظام التشغيل، الأبعاد والوزن، المقاومة، الألوان، السعر). اكتب المذكور في المصدر فقط، وما تكتبش صف لمواصفة مش موجودة. المقارنة بالجيل السابق تبقى في جدول تاني منفصل. ولو الخبر مش عن موبايل معيّن، ضع صندوق (<div class="rv-box">) يلخص أهم النقاط.
5. أسئلة شائعة: 3 إلى 4 أسئلة شائعة وإجاباتها في علامات <details><summary>السؤال</summary><p>الإجابة</p></details>.
6. الأسعار: إن ذكرت أسعار في المصدر، حولها تقريبياً للجنيه المصري (52 ج لكل يورو أو 49 ج لكل دولار)، الريال السعودي (4.05 ر.س)، والدرهم الإماراتي (3.97 د.إ).
7. لا تذكر اسم الموقع المصدر (مثل GSMArena أو Gizmochina) داخل صلب النص.
8. قيد إلزامي لنطاق الموقع: إذا كان النص المصدر لا يتعلق بالهواتف الذكية أو معالجات الموبايل أو أنظمة تشغيلها أو بطارياتها وكاميراتها (مثلاً أخبار شبكات التواصل أو المحاكم أو القوانين أو الحواسيب أو السياسة)، أرجع JSON يحتوي فقط على {{"skip": true, "title": "", "body": ""}}.

رجّع الرد بتنسيق JSON صالح فقط كالتالي دون أي زيادات:
{{
  "kind": "news",
  "title": "عنوان إخباري جذاب ودقيق أقل من 68 حرف",
  "slug": "english-slug-3-to-6-words",
  "desc": "وصف دقيق للبحث من 140 إلى 160 حرف يبدأ بجوهر الخبر التقني وأهم تفاصيله.",
  "brand": "اسم الماركة أو الشركة المعنية بالعربي (مثال: سامسونج، شاومي، كوالكوم، أبل)",
  "price_eur": 0,
  "takeaways": ["خلاصة الخبر بالأرقام في سطر واحد", "أبرز تأثير على أداء أو سعر الهاتف", "الموعد الرسمي أو الخطوة القادمة"],
  "body": "<h2>..</h2><p>..</p>...",
  "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]
}}
"""

COMPARE_PROMPT_TEMPLATE = """أنت محرر مقارنة هواتف محترف في موقع «رفيو» (review-mobile.com) بأسلوب NanoReview التحليلي الدقيق.
المطلوب كتابة مقارنة شاملة وحاسمة تتجاوز 1100 كلمة بين الهاتفين:
الهاتف الأول: «{phone_a}»
الهاتف الثاني: «{phone_b}»

بيانات الهاتف الأول الموثقة:
{specs_a}

بيانات الهاتف الثاني الموثقة:
{specs_b}

قواعد التحرير الصارمة:
1. اعتمد 100% على البيانات الموثقة أعلاه ولا تخترع أي رقم غير منشور.
2. ضع في بداية المقال جدول مقارنة من 3 أعمدة بالضبط (<table class="rv-table rv-vs-table">) أول صف فيه <tr><th>البند</th><th>{phone_a}</th><th>{phone_b}</th></tr> ويقارن كل بند في صف (الشاشة، المعالج، الرام والتخزين، الكاميرا الخلفية، الكاميرا الأمامية، البطارية والشحن، الأبعاد والوزن، السعر التقديري).
3. قسّم المقارنة لعناوين H2 واضحة: التصميم والشاشة أيهما أفضل؟، مقارنة المعالج والأداء في الألعاب، مقارنة الكاميرات والتصوير، البطارية وسرعة الشحن، الأسعار بالعملات العربية (1 يورو = 52 ج / 4.05 ر.س / 3.97 د.إ)، والخلاصة النهائية: أيهما تشتري ولماذا؟
4. أضف صندوق (<div class="rv-pros">) لنقاط تفوق {phone_a} وصندوق (<div class="rv-box">) لنقاط تفوق {phone_b}.
5. أضف 4 أسئلة شائعة في علامات <details><summary>السؤال</summary><p>الإجابة</p></details>.
6. أرجع JSON صالح فقط يحتوي على تقييمات رقمية موضوعية لكلا الهاتفين من 10:
{{
  "kind": "compare",
  "phone_a": "{phone_a}",
  "phone_b": "{phone_b}",
  "title": "مقارنة {phone_a} ضد {phone_b} 2026: أيهما أفضل للشراء؟",
  "slug": "compare-phone-a-vs-phone-b-2026",
  "desc": "مقارنة شاملة بين {phone_a} و{phone_b} في الشاشة والمعالج والكاميرا والبطارية والسعر بالجنيه والريال لحسم قرار الشراء.",
  "brand": "اسم ماركة الهاتف الأول بالعربي",
  "price_eur": 450,
  "scores_a": {{"screen": 8.6, "performance": 8.5, "camera": 8.4, "battery": 8.3, "value": 8.2}},
  "scores_b": {{"screen": 8.4, "performance": 8.1, "camera": 8.2, "battery": 8.7, "value": 8.5}},
  "takeaways": ["الفائز في الشاشة والأداء مع السبب الرقمي", "الفائز في الكاميرا والتصوير", "الفائز في البطارية والشحن والسعر", "قرار الشراء الحاسم حسب نوع المستخدم"],
  "body": "<h2>..</h2><p>..</p>...",
  "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]
}}
"""


def extract_brand(text):
    for l, p in BRANDS:
        if p.search(text):
            return l
    return "اخرى"


def classify_candidate(cand_title, source):
    """Accurately classifies candidate as either full phone 'review' or breaking phone 'news'."""
    if source == "gsmarena_db":
        return "review"
    t_lower = cand_title.lower()
    news_patterns = [
        r"\b(leak|leaks|leaked|rumor|rumors|rumored|certified|certification|teaser|teased|prowess)\b",
        r"\b(update|updates|rollout|rolling out|firmware|patch|beta|developer preview)\b",
        r"\b(snapdragon|dimensity|exynos|tensor|chipset|processor|soc|modem|benchmark|geekbench)\b",
        r"\b(android\s*\d+|ios\s*\d+|one\s*ui|hyperos|coloros|oxygenos|magic\s*os|harmonyos)\b",
        r"\b(vs|versus|comparison|compared|different|experience|which is better|worth buying)\b",
        r"\b(discount|price drop|sale|deal|trade-in|carrier|satellite|telecom)\b",
        r"\b(battery capacity|charging speed|fast charging|camera sensor|periscope|mp sensor)\b",
        r"\b(first look|case leak|protective case|render leak|schematics)\b",
    ]
    if any(re.search(pat, t_lower) for pat in news_patterns):
        return "news"

    review_patterns = [
        r"\b(review|in-depth review|hands-on review|full review)\b",
        r"\b(goes official|is official|officially announced|launched with|unveiled with)\b",
        r"\b(specs and price|specifications and price|price announced)\b",
    ]
    if any(re.search(pat, t_lower) for pat in review_patterns):
        return "review"

    if re.search(r"\breviews?\b", t_lower):
        return "review"
    return "news"


_GSMA_CATALOG_CACHE = {}

GSMA_MAKER_SLUGS = {
    "samsung": "samsung-phones-9.php",
    "galaxy": "samsung-phones-9.php",
    "apple": "apple-phones-48.php",
    "iphone": "apple-phones-48.php",
    "ipad": "apple-phones-48.php",
    "xiaomi": "xiaomi-phones-80.php",
    "redmi": "xiaomi-phones-80.php",
    "poco": "xiaomi-phones-80.php",
    "oppo": "oppo-phones-82.php",
    "reno": "oppo-phones-82.php",
    "find": "oppo-phones-82.php",
    "vivo": "vivo-phones-98.php",
    "iqoo": "vivo-phones-98.php",
    "honor": "honor-phones-121.php",
    "magic": "honor-phones-121.php",
    "realme": "realme-phones-118.php",
    "huawei": "huawei-phones-58.php",
    "mate": "huawei-phones-58.php",
    "pura": "huawei-phones-58.php",
    "oneplus": "oneplus-phones-95.php",
    "nord": "oneplus-phones-95.php",
    "motorola": "motorola-phones-4.php",
    "moto": "motorola-phones-4.php",
    "razr": "motorola-phones-4.php",
    "google": "google-phones-107.php",
    "pixel": "google-phones-107.php",
    "infinix": "infinix-phones-119.php",
    "tecno": "tecno-phones-120.php",
    "nothing": "nothing-phones-128.php",
    "cmf": "nothing-phones-128.php",
    "asus": "asus-phones-46.php",
    "rog": "asus-phones-46.php",
    "nokia": "nokia-phones-1.php",
    "sony": "sony-phones-7.php",
    "xperia": "sony-phones-7.php",
    "zte": "zte-phones-62.php",
    "nubia": "zte-phones-62.php",
    "redmagic": "zte-phones-62.php",
    "lenovo": "lenovo-phones-73.php",
}


def _find_latin_font():
    for cand in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ):
        if os.path.exists(cand):
            return cand
    return None


def _ensure_ar_font():
    if os.path.exists(AR_FONT_PATH):
        return AR_FONT_PATH
    try:
        os.makedirs(os.path.dirname(AR_FONT_PATH), exist_ok=True)
        r = requests.get(AR_FONT_URL, timeout=15)
        if r.status_code == 200 and len(r.content) > 50000:
            open(AR_FONT_PATH, "wb").write(r.content)
            return AR_FONT_PATH
    except Exception:
        pass
    return None


def _shape_ar(text):
    if not text:
        return ""
    if arabic_reshaper and get_display:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            pass
    return text


def _load_font(path, size, weight=None):
    try:
        fnt = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC) if path else ImageFont.load_default()
        if weight and path:
            try:
                fnt.set_variation_by_name(weight)
            except Exception:
                pass
        return fnt
    except Exception:
        return ImageFont.load_default()


def _is_bad_img_url(url):
    if not url or not url.startswith("http"):
        return True
    low = url.lower()
    return any(b in low for b in BAD_IMG_PATTERNS)


def _has_white_corners(im):
    w, h = im.size
    corners = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    pts = [im.getpixel(c) for c in corners]
    return sum(1 for r, g, b in pts if r > 232 and g > 232 and b > 232) >= 3


def _strip_gsmarena_corner(im, src_url=""):
    """Cleanly removes www.GSMArena.com text watermark in bottom-right without slicing curved bezels."""
    if "gsmarena" not in (src_url or "").lower():
        return im
    w, h = im.size
    if w < 260 or h < 260:
        return im
    out = im.copy()
    px = out.load()
    x0 = max(0, w - 155)
    y0 = max(0, h - 24)
    for y in range(y0, h - 2):
        for x in range(x0, w - 2):
            r, g, b = px[x, y]
            if r > 240 and g > 240 and b > 240:
                continue
            sy = max(0, y - 12)
            sr, sg, sb = px[x, sy]
            lum_cur = (r + g + b) / 3
            lum_above = (sr + sg + sb) / 3
            if lum_cur - lum_above > 18 or (lum_cur < 210 and lum_above > 240):
                px[x, y] = (sr, sg, sb)
    return out


_BRAND_CASE = {
    "samsung": "Samsung", "galaxy": "Galaxy", "apple": "Apple", "iphone": "iPhone",
    "ipad": "iPad", "xiaomi": "Xiaomi", "redmi": "Redmi", "poco": "POCO",
    "oppo": "Oppo", "reno": "Reno", "vivo": "vivo", "iqoo": "iQOO",
    "honor": "Honor", "realme": "realme", "huawei": "Huawei", "oneplus": "OnePlus",
    "motorola": "Motorola", "moto": "Moto", "google": "Google", "pixel": "Pixel",
    "infinix": "Infinix", "tecno": "Tecno", "nothing": "Nothing", "sony": "Sony",
    "xperia": "Xperia", "asus": "Asus", "rog": "ROG", "nokia": "Nokia",
    "zte": "ZTE", "nubia": "Nubia", "redmagic": "RedMagic", "lenovo": "Lenovo",
}


def _proper_brand_case(s):
    if not s:
        return ""
    words = s.split()
    out = []
    for w in words:
        lw = w.lower()
        out.append(_BRAND_CASE.get(lw, w))
    return " ".join(out)


def _clean_display_model_name(raw_name):
    if not raw_name:
        return ""
    s = re.sub(r"\s+", " ", str(raw_name)).strip()
    # Extract crisp Brand + Model name if a full English headline was passed
    m_brand = re.search(
        r"\b(Samsung\s+Galaxy\s+[A-Za-z0-9\+\-]+(?:\s+(?:S\d+|A\d+|Z\s*Fold\s*\d*|Z\s*Flip\s*\d*|Ultra|Pro|Plus|FE|Edge|TriFold|5G|4G|\d+[A-Za-z]?)){0,3}|"
        r"iPhone\s+[0-9]{1,2}[A-Za-z]?(?:\s+(?:Pro\s*Max|Pro|Plus|Air|Mini|Ultra|SE|5G|4G)){0,2}|"
        r"iPad\s+[A-Za-z0-9\+\-]+(?:\s+(?:Pro|Air|Mini|\d+|5G)){0,2}|"
        r"(?:Xiaomi|Redmi|POCO|vivo|iQOO|Oppo|OnePlus|Honor|Realme|Motorola|Moto|Google\s+Pixel|Pixel|Infinix|Tecno|Nothing\s+Phone|Nothing|Huawei|Asus|ROG\s+Phone|Sony\s+Xperia|RedMagic|Nubia)\s+(?:Note|Reno|Find|Magic|Pura|Mate|Nord|Edge|Razr|Turbo|Pad|Camon|Spark|Hot|Zero|Smart|GT|X|S|V|A|C|F|M|Y)?\s*[A-Za-z0-9\+\-\(\)]{1,14}(?:\s+(?:[A-Za-z]{0,3}\d+[A-Za-z]?|Pro|Ultra|Max|Plus|Mini|Lite|FE|SE|Turbo|Fold|Flip|Note|Edge|Air|Neo|Power|Slim|View|GT|Global|5G|4G)){0,3})",
        s, re.I
    )
    stop_news = r"\b(tipped|leaks?|leaked|rumor|rumors|blind|orders|official|launch|announced|with|features?|specs?|review|price|to|for|in|at|on|and|now|or|risk|will|have|drop|gets|could|may|how|why|best|202\d)\b.*$"
    if m_brand:
        cand = re.sub(stop_news, "", m_brand.group(0), flags=re.I).strip(" -:|,")
        if len(cand) >= 4:
            return _proper_brand_case(cand[:36].strip())
    s = re.sub(r"\b(reviews?|specs?|price|leaks?|rumors?|hands-on|unboxing|202\d)\b", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" -:|,")
    lat = re.findall(r"[A-Za-z0-9][A-Za-z0-9\+\(\)\.\- ]{2,}", s)
    if re.search(r"[\u0600-\u06FF]", s) and lat:
        best = max(lat, key=lambda x: len(x.strip())).strip()
        best = re.sub(stop_news, "", best, flags=re.I).strip(" -:|,")
        if len(best) >= 5 and re.search(r"[A-Za-z]", best):
            s = best
    if len(s) > 34:
        s = s[:32].rsplit(" ", 1)[0]
    return _proper_brand_case(s.strip())


def process_clean_image(img_url, slug, index, out_dir=IMG_DIR, phone_name="", subtitle="المواصفات والمراجعة الكاملة"):
    """
    Downloads genuine phone photo, cleans corner source watermarks cleanly without slicing bezels,
    formats studio card (for official white-bg / portrait renders) or enhanced 16:9 landscape frame,
    adds the phone model name badge/title + faint Review («رفيو») watermark, and saves to img/review-{slug}-{index}.jpg.
    Returns (cdn_url, local_path) or None on failure.
    """
    if _is_bad_img_url(img_url):
        return None
    try:
        os.makedirs(out_dir, exist_ok=True)
        headers = GSMA_UA if "gsmarena" in img_url.lower() else UA
        r = requests.get(img_url, headers=headers, timeout=18)
        if (r.status_code != 200 or len(r.content) < 1200) and headers is GSMA_UA:
            r = requests.get(img_url, headers=UA, timeout=18)
        if r.status_code != 200 or len(r.content) < 1200:
            return None
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        w, h = im.size
        # Accept GSMArena official 160x212 bigpic renders (>=120px) while filtering tiny UI icons
        if w < 120 or h < 120:
            return None

        im = _strip_gsmarena_corner(im, img_url)
        w, h = im.size
        white_bg = _has_white_corners(im)
        is_portrait_or_sq = (w / h) < 1.25
        clean_name = _clean_display_model_name(phone_name)
        latin_font = _find_latin_font()
        ar_font = _ensure_ar_font()

        if white_bg or is_portrait_or_sq:
            if white_bg:
                canvas = Image.new("RGBA", (1200, 675), (255, 255, 255, 255))
                draw = ImageDraw.Draw(canvas)
                for y in range(675):
                    v = int(255 - (y / 675) * 9)
                    draw.line([(0, y), (1200, y)], fill=(v, min(255, v + 1), min(255, v + 3), 255))
            else:
                bg = ImageOps.fit(im, (1200, 675), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
                bg = ImageEnhance.Brightness(bg).enhance(0.65)
                canvas = bg.convert("RGBA")

            max_w = 720 if clean_name else 960
            max_h = 565
            scale = min(max_w / w, max_h / h)
            if w < 250:
                scale = min(scale, 2.75)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            scaled = im.resize((nw, nh), Image.Resampling.LANCZOS)
            scaled = ImageEnhance.Sharpness(scaled).enhance(1.18 if w < 250 else 1.08)
            scaled = ImageEnhance.Contrast(scaled).enhance(1.04)

            s_rgba = scaled.convert("RGBA")
            if white_bg:
                cr, cg, cb, _ = s_rgba.getpixel((2, 2))
                thresh_r, thresh_g, thresh_b = max(230, cr - 10), max(230, cg - 10), max(230, cb - 10)
                px = s_rgba.load()
                for yy in range(nh):
                    for xx in range(nw):
                        pr, pg, pb, _ = px[xx, yy]
                        if pr >= thresh_r and pg >= thresh_g and pb >= thresh_b and max(pr, pg, pb) - min(pr, pg, pb) <= 14:
                            px[xx, yy] = (255, 255, 255, 0)

            px_x = (1200 - nw) // 2 + (140 if clean_name else 0)
            px_x = max(40, min(px_x, 1200 - nw - 48))
            px_y = (675 - nh) // 2
            canvas.alpha_composite(s_rgba, (px_x, px_y))

            wm_file = WM_LIGHT if white_bg else WM_DARK
            if os.path.exists(wm_file):
                wm = Image.open(wm_file).convert("RGBA")
                canvas.alpha_composite(wm, (34, 675 - wm.height - 22))
            else:
                d_wm = ImageDraw.Draw(canvas)
                f_wm = _load_font(latin_font, 18)
                d_wm.text((34, 636), "review-mobile.com", font=f_wm, fill=(100, 116, 139, 130) if white_bg else (255, 255, 255, 145))

            if clean_name:
                d = ImageDraw.Draw(canvas)
                text_x = 50
                text_y = 255
                ink = (15, 23, 42, 240) if white_bg else (255, 255, 255, 245)
                sub_ink = (100, 116, 139, 215) if white_bg else (226, 232, 240, 210)
                d.rounded_rectangle((text_x, text_y - 34, text_x + 48, text_y - 28), radius=3, fill=(37, 99, 235, 225))
                has_ar_name = bool(re.search(r"[\u0600-\u06FF]", clean_name))
                font_size = 36 if len(clean_name) <= 18 else (30 if len(clean_name) <= 26 else 24)
                f_title = _load_font(ar_font if has_ar_name and ar_font else latin_font, font_size, "Bold" if has_ar_name else None)
                disp_name = _shape_ar(clean_name) if has_ar_name else clean_name
                words = disp_name.split() if not has_ar_name else [disp_name]
                lines, cur = [], ""
                max_tw = max(230, px_x - text_x - 30)
                for wt in words:
                    cand_line = (cur + " " + wt).strip()
                    if d.textlength(cand_line, font=f_title) <= max_tw or not cur:
                        cur = cand_line
                    else:
                        lines.append(cur)
                        cur = wt
                if cur:
                    lines.append(cur)
                yy = text_y - 10
                for ln in lines[:3]:
                    d.text((text_x, yy), ln, font=f_title, fill=ink)
                    yy += font_size + 10
                if subtitle and ar_font and (arabic_reshaper and get_display):
                    f_sub = _load_font(ar_font, 18, "Medium")
                    d.text((text_x, yy + 8), _shape_ar(subtitle), font=f_sub, fill=sub_ink)

            target = canvas.convert("RGB")
        else:
            # Landscape photo: trim tiny margin (and bottom corner/banner watermark on GSMArena/Gizmochina/SamMobile)
            low_u = img_url.lower()
            bot_ratio = 0.855 if "gsmarena" in low_u else (0.925 if any(k in low_u for k in ("gizmochina", "sammobile", "phonearena", "notebookcheck")) else 0.99)
            im_c = im.crop((int(w * 0.01), int(h * 0.01), int(w * 0.99), int(h * bot_ratio)))
            target = ImageOps.fit(im_c, (1200, 675), method=Image.Resampling.LANCZOS, centering=(0.5, 0.48))
            target = ImageEnhance.Contrast(target).enhance(1.04)
            target = ImageEnhance.Color(target).enhance(1.02)
            target = ImageEnhance.Sharpness(target).enhance(1.08)
            canvas = target.convert("RGBA")

            if os.path.exists(WM_DARK):
                wm = Image.open(WM_DARK).convert("RGBA")
                pad = 40
                sh = Image.new("RGBA", (wm.width + pad * 2, wm.height + pad * 2), (0, 0, 0, 0))
                ImageDraw.Draw(sh).rounded_rectangle((pad, pad, wm.width + pad, wm.height + pad), radius=24, fill=(15, 23, 42, 72))
                sh = sh.filter(ImageFilter.GaussianBlur(14))
                canvas.alpha_composite(sh, (28 - pad, 675 - wm.height - 20 - pad))
                canvas.alpha_composite(wm, (28, 675 - wm.height - 20))
            else:
                d_wm = ImageDraw.Draw(canvas)
                f_wm = _load_font(latin_font, 18)
                d_wm.text((28, 636), "review-mobile.com", font=f_wm, fill=(255, 255, 255, 155))

            if clean_name:
                has_ar_name = bool(re.search(r"[\u0600-\u06FF]", clean_name))
                pill_text = clean_name if not has_ar_name else (_shape_ar(clean_name) if (ar_font and arabic_reshaper and get_display) else "")
                if pill_text:
                    d = ImageDraw.Draw(canvas)
                    f_pill = _load_font(ar_font if has_ar_name else latin_font, 22, "Bold" if has_ar_name else None)
                    tw = d.textlength(pill_text, font=f_pill)
                    if tw < 580:
                        pad_x = 18
                        bx1 = 1200 - int(tw) - pad_x * 2 - 26
                        bx2 = 1200 - 26
                        by1, by2 = 24, 24 + 44
                        d.rounded_rectangle((bx1, by1, bx2, by2), radius=22, fill=(15, 23, 42, 175), outline=(255, 255, 255, 75), width=1)
                        d.text((bx1 + pad_x, (by1 + by2) // 2), pill_text, font=f_pill, fill=(255, 255, 255, 245), anchor="lm")

            target = canvas.convert("RGB")

        fname = f"review-{slug}-{index}.jpg"
        out_path = os.path.join(out_dir, fname)
        target.save(out_path, format="JPEG", quality=88, optimize=True)
        cdn_url = f"{CDN}img/{fname}"
        return cdn_url, out_path
    except Exception as e:
        print(f"  process_clean_image error ({img_url[:60]}...): {e}")
        return None


def fetch_live_review_titles(tok):
    """Fetches all existing live post titles on Review blog to guarantee ZERO duplicates."""
    try:
        posts = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts", tok, {
            "status": ["live", "scheduled"],
            "fetchBodies": "false",
            "maxResults": 500,
            "view": "ADMIN"
        })
        return [p["title"] for p in posts.get("items", [])]
    except Exception as e:
        print("Warning fetching review titles:", e)
        return []


STOP_WORDS = {
    "phone", "mobile", "smartphone", "smartphones", "announced", "launched", "unveiled", "goes", "official",
    "quietly", "reportedly", "china", "india", "global", "specs", "features", "price", "review", "reviews",
    "leak", "leaks", "rumored", "first", "new", "with", "and", "the", "for", "gets", "receives",
    "teardown", "video", "confirms", "edition", "series", "full", "hands", "test", "will", "from",
    "this", "that", "here", "what", "know", "everything", "details", "about", "more", "than",
    "com", "news", "gsmarena", "sammobile", "androidauthority", "gizmochina", "mashable", "howtogeek", "newscord", "feed", "rss", "via", "source", "html", "php"
}


def extract_model_terms(text):
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in clean.split() if len(w) > 1 and w not in STOP_WORDS]


VARIANTS = {"pro", "max", "ultra", "plus", "lite", "fe", "mini", "neo", "edge", "fold", "flip", "power", "turbo", "air", "prime"}
NEWS_EVENT_WORDS = ("update", "android 1", "one ui", "hyperos", "coloros", "origin os", "funtouch", "magicos",
                    "price cut", "discount", "deal", "sale", "recall", "problem", "issue", "bug", "battery drain",
                    "تحديث", "تخفيض", "خصم", "عرض", "مشكلة", "عطل")


def model_keys(text):
    """Phone model keys like 's26 ultra', 'x500 pro max', 'note 15 pro plus' (Arabic or English titles)."""
    toks = re.sub(r"[^\w\s+]", " ", text.lower()).replace("+", " plus ").split()
    keys = set()
    for i, t in enumerate(toks):
        if not re.search(r"\d", t) or re.fullmatch(r"\d+(hz|mah|mp|w|gb|tb|g|k|mm|nm)|20\d\d", t):
            continue
        j, var = i + 1, []
        while j < len(toks) and toks[j] in VARIANTS:
            var.append(toks[j]); j += 1
        head = [toks[i - 1]] if t.isdigit() and i > 0 else []
        keys.add(" ".join(head + [t] + var))
    return keys


def is_already_covered(cand, existing_titles, done_urls, done_items=None):
    """
    Strict deduplication logic:
    - For reviews: Ensures this specific phone model hasn't been reviewed already (handles models with or without digits).
    - For news: Checks candidate link, distinctive topic terms against previously published posts, done history and URLs.
    """
    cand_title = cand["title"]
    cand_link = cand["link"]
    cand_kind = cand.get("kind", "news")

    if cand_link in done_urls:
        return True, "URL already processed in done history"

    done_list = (done_items or [])[-80:]

    if cand_kind == "review":
        before_rev = re.split(r'\b(?:review|specs|tested|hands[\s-]on|in[\s-]depth)\b', cand_title, flags=re.I)[0]
        model_terms = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', before_rev) if w.lower() not in STOP_WORDS]
        model_codes = [t for t in model_terms if re.search(r'\d', t)]
        variants = {'pro', 'max', 'ultra', 'plus', 'lite', 'fe', 'mini', 'neo', 'air', 'prime'}
        cand_vars = set(model_terms) & variants

        for t in existing_titles:
            if not t.startswith("مراجعة"):
                continue
            t_words = set(re.findall(r'[a-zA-Z0-9]+', t.lower()))
            if model_codes:
                for code in model_codes:
                    if code in t_words and (not cand_vars or cand_vars == (t_words & variants)):
                        return True, f"Model code [{code}] with variants {cand_vars} found in review: {t}"
            else:
                distinctive = [w for w in model_terms if w not in variants and len(w) >= 3]
                if distinctive and all(w in t_words for w in distinctive):
                    return True, f"Non-digit model {distinctive} found in review: {t}"

        for d in done_list:
            if d.get("kind") == "review":
                d_text = (d.get("cand_title", "") + " " + d.get("title", "") + " " + d.get("post_url", "")).lower()
                d_words = set(re.findall(r'[a-zA-Z0-9]+', d_text))
                if model_codes:
                    for code in model_codes:
                        if code in d_words and (not cand_vars or cand_vars == (d_words & variants)):
                            return True, f"Model code [{code}] found in done review history: {d.get('title')}"
                else:
                    distinctive = [w for w in model_terms if w not in variants and len(w) >= 3]
                    if distinctive and all(w in d_words for w in distinctive):
                        return True, f"Non-digit model {distinctive} found in done review history: {d.get('title')}"
    else:
        cand_words = {w for w in re.findall(r'[a-zA-Z0-9]{4,}', cand_title.lower())} - STOP_WORDS
        generic_news = STOP_WORDS | {'android', 'ios', 'apple', 'samsung',
                        'xiaomi', 'oppo', 'vivo', 'honor', 'realme', 'huawei', 'google', 'device', 'devices',
                        'tech', 'technology', 'report', 'reports', 'reportedly', 'details', 'about', 'phone',
                        'phones', 'smartphone', 'smartphones', 'specs', 'feature', 'features', 'camera',
                        'battery', 'display', 'screen', 'update', 'edition', 'launch', 'release'}

        # Compare only with recent 35 done items (title-to-title, ignore URLs)
        for d in done_list[-35:]:
            d_raw = (d.get("cand_title", "") + " " + d.get("title", "")).lower()
            d_words = {w for w in re.findall(r'[a-zA-Z0-9]{4,}', d_raw)} - STOP_WORDS
            overlap = (cand_words & d_words) - generic_news
            # 3 or more distinctive specific words indicate identical news event
            if len(overlap) >= 3:
                return True, f"Recent story overlap on key terms {list(overlap)[:4]!r}"

        # Title similarity against live posts
        cand_norm = f.norm(cand_title)
        for t in existing_titles:
            if difflib.SequenceMatcher(None, cand_norm, f.norm(t)).ratio() >= 0.70:
                return True, f"High title similarity with live post: {t}"

        if not any(w in cand_title.lower() for w in NEWS_EVENT_WORDS):
            keys = model_keys(cand_title)
            if keys:
                for t in existing_titles:
                    if keys & model_keys(t):
                        return True, f"Phone {sorted(keys & model_keys(t))[0]!r} already covered in: {t}"

    return False, ""


def find_review_internal_links(brand_name, tok, limit=2):
    """Finds 2-3 live articles on Review for contextual internal linking."""
    links = []
    try:
        posts = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts", tok, {
            "status": "live",
            "fetchBodies": "false",
            "maxResults": 40,
            "view": "ADMIN"
        })
        items = posts.get("items", [])
        for it in items:
            if brand_name in it.get("labels", []) and it.get("url"):
                links.append((it["title"], it["url"]))
                if len(links) >= limit:
                    break
        if len(links) < limit:
            for it in items:
                pair = (it["title"], it["url"])
                if pair not in links and it.get("url"):
                    links.append(pair)
                    if len(links) >= limit:
                        break
    except Exception:
        pass
    return links


PHONE_TOPICS_REGEX = re.compile(
    r"\b(phone|smartphone|smartphones|handset|flagship|foldable|galaxy\s*[saqmzf]\w*|samsung\s+galaxy|iphone|xiaomi|redmi|poco|oppo|vivo|iqoo|honor|realme|huawei|motorola|moto\s+(?:g|edge|razr)|oneplus|infinix|tecno|pixel\s+\d+|nothing\s+phone|snapdragon|dimensity|exynos|tensor|kirin|mediatek|one\s*ui|hyperos|coloros|oxygenos|android\s*\d+|ios\s*\d+|mobile\s+camera|periscope|silicon[- ]carbon|fast\s+charging|mah|amoled|ltpo)\b",
    re.I
)


def is_phone_candidate_title(title):
    if not title:
        return False
    if NON_PHONE_EXCLUSIONS.search(title) or HALLUCINATED_OR_FAKE_EXCLUSIONS.search(title) or NON_MOBILE_NEWS_EXCLUSIONS.search(title):
        return False
    return bool(PHONE_TOPICS_REGEX.search(title))


def fetch_phone_candidates():
    """Scrapes top mobile authorities for reviews, breaking phone news, and VS comparisons."""
    cands = []
    seen = set()

    # 1. Gizmochina RSS (Breaking phone launches, leaks & chipsets)
    try:
        r = requests.get("https://www.gizmochina.com/feed/", headers=UA, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:20]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not link or link in seen or not is_phone_candidate_title(title):
                    continue
                seen.add(link)
                cands.append({"title": title, "link": link, "source": "gizmochina", "kind": classify_candidate(title, "gizmochina")})
    except Exception as e:
        print("Gizmochina RSS error:", e)

    # 2. GSMArena Direct RSS (Daily reviews, breaking leaks & certifications)
    try:
        r = requests.get("https://www.gsmarena.com/rss-news-reviews.php3", headers=UA, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:20]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not link or link in seen or not is_phone_candidate_title(title):
                    continue
                seen.add(link)
                cands.append({"title": title, "link": link, "source": "gsmarena", "kind": classify_candidate(title, "gsmarena")})
    except Exception as e:
        print("GSMArena RSS error:", e)

    # 3. SamMobile RSS (Samsung Galaxy launches, leaks & One UI updates)
    try:
        r = requests.get("https://www.sammobile.com/feed/", headers=UA, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:15]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen or NON_PHONE_EXCLUSIONS.search(title) or HALLUCINATED_OR_FAKE_EXCLUSIONS.search(title) or NON_MOBILE_NEWS_EXCLUSIONS.search(title):
                    continue
                if re.search(r"galaxy|s25|s26|a56|a36|z fold|z flip|one ui|snapdragon|exynos|phone|smartphone", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "sammobile", "kind": classify_candidate(title, "sammobile")})
    except Exception as e:
        print("SamMobile RSS error:", e)

    # 4. Android Authority RSS (Android OS, Pixel, Qualcomm & smartphone tech)
    try:
        r = requests.get("https://www.androidauthority.com/feed/", headers=UA, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:15]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not link or link in seen or not is_phone_candidate_title(title):
                    continue
                seen.add(link)
                cands.append({"title": title, "link": link, "source": "androidauthority", "kind": classify_candidate(title, "androidauthority")})
    except Exception as e:
        print("Android Authority RSS error:", e)

    # 5. Masrawy Tech RSS (Local market releases & mobile prices in Egypt)
    try:
        r = requests.get("https://www.masrawy.com/rss/feed/382/" + urllib.parse.quote("علوم-وتكنولوجيا"), headers=UA, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:10]:
                title = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if not title or link in seen or NON_MOBILE_NEWS_EXCLUSIONS.search(title):
                    continue
                if re.search(r"لينكد إن|فيسبوك|تيك توك|إنستجرام|يوتيوب|محكمة|حكم قضائي|انتخابات|برلمان", title, re.I):
                    continue
                if re.search(r"موبايل|هاتف|سامسونج|آيفون|ايفون|شاومي|ريدمي|ريلمي|أوبو|اوبو|فيفو|هواوي|معالج|أندرويد", title, re.I):
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "masrawy_tech", "kind": classify_candidate(title, "masrawy_tech")})
    except Exception as e:
        print("Masrawy Tech RSS error:", e)

    # 6. Google News Targeted Phone RSS
    gn_urls = [
        "https://news.google.com/rss/search?q=site:gsmarena.com+when:48h&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=(smartphone+OR+phone)+(launched+OR+announced+OR+specs)+when:48h&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=(smartphone+OR+phone+OR+samsung+OR+iphone+OR+xiaomi)+(leak+OR+update+OR+snapdragon+OR+android)+when:48h&hl=en-US&gl=US&ceid=US:en"
    ]
    for gu in gn_urls:
        try:
            r = requests.get(gu, headers=UA, timeout=15)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for it in root.findall(".//item")[:15]:
                    title = (it.find("title").text or "").strip()
                    link = (it.find("link").text or "").strip()
                    if not link or link in seen or not is_phone_candidate_title(title):
                        continue
                    seen.add(link)
                    cands.append({"title": title, "link": link, "source": "googlenews", "kind": classify_candidate(title, "googlenews")})
        except Exception:
            pass

    # 7. GSMArena Fresh Devices Fallback + NanoReview-style VS Pairs
    db_devices = []
    try:
        r = requests.get("https://www.gsmarena.com/", headers=UA, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                strong = a.find("strong")
                span = a.find("span")
                txt = (strong.get_text() if strong else (span.get_text() if span else a.get_text())).strip()
                if re.search(r"-\d+\.php$", href) and not re.search(r"-(news|phones|review)-\d+\.php$", href):
                    if txt and len(txt) > 3 and not re.search(r"specs|pictures|opinion|compare|\breview\b|watch|buds|tv|band|pad|tab", txt, re.I):
                        if NON_PHONE_EXCLUSIONS.search(txt) or HALLUCINATED_OR_FAKE_EXCLUSIONS.search(txt) or NON_MOBILE_NEWS_EXCLUSIONS.search(txt):
                            continue
                        full_link = "https://www.gsmarena.com/" + href
                        db_devices.append((txt, full_link))
                        if full_link not in seen:
                            seen.add(full_link)
                            cands.append({"title": txt, "link": full_link, "source": "gsmarena_db", "kind": "review"})
    except Exception as e:
        print("GSMArena Devices Fallback error:", e)

    # Deduplicate DB devices preserving order and synthesize VS head-to-head candidates
    uniq_db = []
    seen_db_names = set()
    for dname, durl in db_devices:
        k = dname.lower()
        if k not in seen_db_names:
            seen_db_names.add(k)
            uniq_db.append((dname, durl))
    for a_idx, b_idx in [(0, 1), (2, 3), (0, 2), (1, 3), (4, 5)]:
        if max(a_idx, b_idx) < len(uniq_db):
            pa, ua = uniq_db[a_idx]
            pb, ub = uniq_db[b_idx]
            vs_link = f"{ua}||{ub}"
            if vs_link not in seen:
                seen.add(vs_link)
                cands.append({
                    "title": f"{pa} vs {pb}",
                    "link": vs_link,
                    "link_a": ua,
                    "link_b": ub,
                    "phone_a": pa,
                    "phone_b": pb,
                    "source": "gsmarena_vs",
                    "kind": "compare"
                })

    # Deduplicate candidate links
    unique = []
    seen_links = set()
    for c in cands:
        if c["link"] not in seen_links:
            seen_links.add(c["link"])
            unique.append(c)
    return unique


def decode_gn_link(link):
    """Decodes Google News RSS redirect link to original publisher URL."""
    try:
        aid = link.split("/articles/")[1].split("?")[0]
        h = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=UA, timeout=20).text
        sg_m = re.search(r'data-n-a-sg="([^"]+)"', h)
        ts_m = re.search(r'data-n-a-ts="([^"]+)"', h)
        if not sg_m or not ts_m:
            return None
        sg, ts = sg_m.group(1), ts_m.group(1)
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts), sg]
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", timeout=20,
                          headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                          data="f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])))
        return json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except Exception:
        return None


def _norm_phone_tokens(text):
    s = re.sub(r"[^a-z0-9\+\s]", " ", (text or "").lower().replace("+", " plus "))
    drop = {"5g", "4g", "lte", "global", "edition", "review", "reviews", "specs", "price",
            "phone", "smartphone", "mobile", "vs", "nfc", "with", "for", "new", "the", "and",
            "2024", "2025", "2026", "2027"}
    return [t for t in s.split() if t and t not in drop]


def fetch_gsmarena_device_photos(page_url, soup=None):
    """Extracts ONLY genuine device photos from a GSMArena phone spec page & its -pictures- gallery (ignoring sidebars)."""
    photos = []
    try:
        if soup is None:
            r = requests.get(page_url, headers=UA, timeout=20)
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")

        # 1. Dedicated device picture gallery (-pictures-XXXX.php) -> high-res vv/pics/ renders & lifestyle shots
        pic_a = soup.select_one('a[href*="-pictures-"]') or soup.select_one("div.specs-photo-main a")
        if pic_a and pic_a.get("href") and "pictures" in pic_a["href"]:
            gal_url = urllib.parse.urljoin(page_url, pic_a["href"])
            try:
                gr = requests.get(gal_url, headers=UA, timeout=20)
                if gr.status_code == 200:
                    gsoup = BeautifulSoup(gr.text, "html.parser")
                    for img in gsoup.select("#pictures-list img"):
                        src = img.get("src") or img.get("data-src") or ""
                        if src.startswith("//"):
                            src = "https:" + src
                        if src.startswith("http") and "gsmarena.com/vv/" in src and not _is_bad_img_url(src):
                            if src not in photos:
                                photos.append(src)
                        if len(photos) >= 5:
                            break
            except Exception:
                pass

        # 2. Main official device hero photo inside .specs-photo-main (never sidebar!)
        main_img = soup.select_one("div.specs-photo-main img")
        if main_img:
            src = main_img.get("src") or main_img.get("data-src") or ""
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("http") and not _is_bad_img_url(src) and src not in photos:
                photos.append(src)

        # 3. og:image on device page if still empty
        if not photos:
            og = soup.find("meta", property="og:image")
            if og and og.get("content") and not _is_bad_img_url(og["content"]):
                photos.append(og["content"].strip())
    except Exception as e:
        print(f"  fetch_gsmarena_device_photos warning ({page_url[:50]}): {e}")
    return photos[:5]


def _load_gsmarena_brand_devices(maker_slug):
    if maker_slug in _GSMA_CATALOG_CACHE:
        return _GSMA_CATALOG_CACHE[maker_slug]
    items = []
    urls = [f"https://www.gsmarena.com/{maker_slug}"]
    m = re.match(r"(.+)-phones-(\d+)\.php", maker_slug)
    if m:
        urls.append(f"https://www.gsmarena.com/{m.group(1)}-phones-f-{m.group(2)}-0-p2.php")
    for u in urls:
        try:
            r = requests.get(u, headers=UA, timeout=15)
            if r.status_code != 200:
                continue
            sp = BeautifulSoup(r.text, "html.parser")
            devs = sp.select("div.makers ul li a")
            if not devs:
                break
            brand_prefix = maker_slug.split("-")[0]
            for a in devs:
                sp_tag = a.find("span")
                name = sp_tag.get_text(" ", strip=True) if sp_tag else a.get_text(" ", strip=True)
                full = name if name.lower().startswith(brand_prefix) else f"{brand_prefix} {name}"
                im = a.find("img")
                items.append({
                    "name": name,
                    "full": full,
                    "toks": _norm_phone_tokens(full),
                    "url": urllib.parse.urljoin("https://www.gsmarena.com/", a.get("href", "")),
                    "thumb": im.get("src", "") if im else "",
                })
        except Exception:
            continue
    _GSMA_CATALOG_CACHE[maker_slug] = items
    return items


def lookup_real_phone_photos(model_query):
    """Finds verified genuine photos for a specific phone model via GSMArena catalog + Gizmochina WP JSON."""
    q_toks = _norm_phone_tokens(model_query)
    if not q_toks:
        return []
    q_set = set(q_toks)
    num_toks = {t for t in q_set if any(c.isdigit() for c in t)}

    # Determine relevant GSMArena maker pages from brand/series tokens
    maker_slugs = []
    for tok in q_toks:
        ms = GSMA_MAKER_SLUGS.get(tok)
        if ms and ms not in maker_slugs:
            maker_slugs.append(ms)

    best_dev, best_score = None, 0.0
    for ms in maker_slugs[:2]:
        for dev in _load_gsmarena_brand_devices(ms):
            d_toks = set(dev["toks"])
            if not d_toks:
                continue
            # Require at least one matching alphanumeric model number if query has numbers
            if num_toks and not (num_toks & d_toks):
                continue
            inter = len(q_set & d_toks)
            score = inter / max(len(d_toks), len(q_set))
            # Penalize Pro/Ultra/Max/Plus mismatch gently unless equal
            mods = {"pro", "ultra", "max", "plus", "mini", "lite", "fe", "se", "air", "fold", "flip"}
            if (mods & q_set) != (mods & d_toks):
                score -= 0.18
            if score > best_score:
                best_score = score
                best_dev = dev

    if best_dev and best_score >= 0.65:
        photos = fetch_gsmarena_device_photos(best_dev["url"])
        if not photos and best_dev.get("thumb"):
            photos = [best_dev["thumb"]]
        if photos:
            return photos

    # Gizmochina WP REST search fallback with strict title token verification
    try:
        search_q = " ".join(q_toks[:5])
        api_u = f"https://www.gizmochina.com/wp-json/wp/v2/posts?search={urllib.parse.quote(search_q)}&per_page=6&_embed"
        gr = requests.get(api_u, headers=UA, timeout=15)
        if gr.status_code == 200:
            posts = gr.json()
            for post in posts:
                ptitle = html.unescape(re.sub(r"<[^>]+>", "", post.get("title", {}).get("rendered", "")))
                ptoks = set(_norm_phone_tokens(ptitle))
                if not ptoks:
                    continue
                if num_toks and not (num_toks & ptoks):
                    continue
                if len(q_set & ptoks) / max(len(q_set), 1) < 0.70:
                    continue
                is_q_accessory = bool(q_set & {"pad", "tablet", "watch", "buds", "band", "ipad"})
                if not is_q_accessory and any(w in ptitle.lower() for w in ("pad", "tablet", "smartwatch", "watch", "earbuds", "buds")):
                    continue
                if " vs " not in model_query.lower() and re.search(r"\b(vs|versus|similar|clone|alternative)\b", ptitle, re.I):
                    continue
                found = []
                emb = post.get("_embedded", {})
                for fm in emb.get("wp:featuredmedia", []):
                    su = fm.get("source_url", "")
                    if su and not _is_bad_img_url(su) and (is_q_accessory or not any(w in su.lower() for w in ("pad", "tablet", "watch", "buds"))):
                        found.append(su)
                body_html = post.get("content", {}).get("rendered", "")
                for im in BeautifulSoup(body_html, "html.parser").find_all("img"):
                    su = im.get("src") or im.get("data-src") or ""
                    if su.startswith("http") and not _is_bad_img_url(su) and su not in found:
                        if is_q_accessory or not any(w in su.lower() for w in ("pad", "tablet", "watch", "buds")):
                            found.append(su)
                    if len(found) >= 4:
                        break
                if found:
                    return found[:4]
    except Exception:
        pass
    return []


def fetch_article_data(url):
    """Fetches real article text and extracts authentic, content-scoped phone photos (never sidebars/ads)."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code != 200:
            return None, []
        soup = BeautifulSoup(r.text, "html.parser")

        # Dedicated extraction for GSMArena device spec pages
        if "gsmarena.com/" in url.lower() and re.search(r"-\d+\.php", url) and "-news-" not in url.lower():
            photos = fetch_gsmarena_device_photos(url, soup=soup)
            for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                s.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 35]
            return "\n".join(lines[:60]), photos

        for s in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            s.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 35]
        clean_text = "\n".join(lines[:60])

        photos = []
        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og_img and og_img.get("content"):
            og_u = og_img["content"].strip()
            if og_u.startswith("//"):
                og_u = "https:" + og_u
            if not _is_bad_img_url(og_u):
                photos.append(og_u)

        # Scope image extraction strictly to main article container first (avoids sidebar related-device thumbs!)
        container = (
            soup.select_one("div.review-body")
            or soup.select_one("div#review-body")
            or soup.select_one("div.article-body")
            or soup.select_one("div.entry-content")
            or soup.select_one("div.post-content")
            or soup.select_one("article")
            or soup.select_one("main")
            or soup
        )
        for img in container.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
            if not src or src.startswith("data:"):
                continue
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".webp", ".png"]):
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urllib.parse.urljoin(url, src)
                # Never pick sidebar GSMArena bigpic thumbnails inside news posts
                if "gsmarena.com/vv/bigpic/" in src.lower():
                    continue
                if src.startswith("http") and not _is_bad_img_url(src) and src not in photos:
                    photos.append(src)
            if len(photos) >= 5:
                break

        return clean_text, photos
    except Exception as e:
        print("fetch_article_data error:", e)
        return None, []


def build_interactive_tool(tid, eur_price, kind="review"):
    """Builds inline interactive price converter or tech evaluation tool."""
    try:
        if isinstance(eur_price, (int, float)) and eur_price > 0:
            p = round(eur_price)
        elif isinstance(eur_price, str):
            digits = re.findall(r"\d+", eur_price)
            p = int(digits[0]) if digits else 400
        else:
            p = 400
    except Exception:
        p = 400

    return (
        f'<h2>أداة تفاعلية: محوّل أسعار الهاتف بالعملات العربية</h2>'
        f'<div class="rv-tool">'
        f'<p><label>السعر باليورو/الدولار: <input id="{tid}-e" type="number" value="{p}" min="0" step="5" style="width:120px"/></label></p>'
        f'<p><label>سعر صرف الجنيه التقديري: <input id="{tid}-r" type="number" value="{EUR_RATES["egp"]}" min="0" step="0.5" style="width:120px"/></label></p>'
        f'<p><button id="{tid}-go" type="button" onclick="'
        f'var e=parseFloat(document.getElementById(\'{tid}-e\').value)||0;'
        f'var r=parseFloat(document.getElementById(\'{tid}-r\').value)||52;'
        f'var egp=Math.round(e*r);'
        f'var sar=Math.round(e*{EUR_RATES["sar"]});'
        f'var aed=Math.round(e*{EUR_RATES["aed"]});'
        f'document.getElementById(\'{tid}-out\').innerHTML=\'<div class=&quot;rv-box&quot;>'
        f'<strong>النتائج التقديرية بالعملات العربية:</strong><br>'
        f'🇪🇬 بالمصري: <strong>\'+egp.toLocaleString()+\' جنيه</strong><br>'
        f'🇸🇦 بالسعودي: <strong>\'+sar.toLocaleString()+\' ريال</strong><br>'
        f'🇦🇪 بالإماراتي: <strong>\'+aed.toLocaleString()+\' درهم</strong>'
        f'</div>\';">احسب التحويل الآن</button></p>'
        f'<div id="{tid}-out"></div>'
        f'<p style="font-size:13px;color:#64748b;margin-top:8px">ملاحظة: الأسعار تقديرية وفق أسعار الإطلاق العالمية والتحويل المباشر ولا تشمل الضرائب أو الجمارك المحلية.</p>'
        f'</div>'
    )


def build_scorecard_and_vote_html(art, tid, cand_title, cand_kind):
    """Builds NanoReview-style visual score bars and interactive localStorage user voting poll."""
    keys = [
        ("screen", "الشاشة والسطوع"),
        ("performance", "المعالج والألعاب"),
        ("camera", "الكاميرا والتصوير"),
        ("battery", "البطارية والشحن"),
        ("value", "القيمة مقابل السعر"),
    ]
    out_parts = []

    if cand_kind == "compare":
        sa = art.get("scores_a") if isinstance(art.get("scores_a"), dict) else {}
        sb = art.get("scores_b") if isinstance(art.get("scores_b"), dict) else {}
        pa = html.escape(str(art.get("phone_a") or cand_title.split(" vs ")[0]))
        pb = html.escape(str(art.get("phone_b") or (cand_title.split(" vs ")[1] if " vs " in cand_title else "المنافس")))
        if sa and sb:
            rows = []
            tot_a, tot_b = [], []
            for k, lbl in keys:
                try:
                    va = max(1.0, min(10.0, float(sa.get(k, 8.0))))
                    vb = max(1.0, min(10.0, float(sb.get(k, 8.0))))
                except Exception:
                    va, vb = 8.0, 8.0
                tot_a.append(va)
                tot_b.append(vb)
                rows.append(
                    f'<div class="rv-sc-row">'
                    f'<div class="rv-sc-lbl"><span>{lbl}</span><span>🔵 {pa}: {va:.1f} &nbsp;|&nbsp; 🟠 {pb}: {vb:.1f}</span></div>'
                    f'<div class="rv-sc-bar" style="margin-bottom:4px"><div class="rv-sc-fill" style="width:{int(va * 10)}%"></div></div>'
                    f'<div class="rv-sc-bar"><div class="rv-sc-fill-b" style="width:{int(vb * 10)}%"></div></div>'
                    f'</div>'
                )
            avg_a = sum(tot_a) / len(tot_a)
            avg_b = sum(tot_b) / len(tot_b)
            out_parts.append(
                f'<div class="rv-scorecard">'
                f'<div class="rv-sc-head"><strong style="font-size:17px">📊 تقييم رفيو الرقمي: {pa} ضد {pb}</strong>'
                f'<span class="rv-sc-badge">{avg_a:.1f} مقابل {avg_b:.1f}</span></div>'
                + "".join(rows) +
                f'</div>'
            )
        poll_q = f"أي الهاتفين تفضّل للشراء في 2026؟"
        opts = [f"📱 أختار {pa}", f"📱 أختار {pb}", "🤝 الفارق بسيط حسب السعر"]
    else:
        sc = art.get("scores") if isinstance(art.get("scores"), dict) else {}
        if cand_kind == "review" and sc:
            rows = []
            tot = []
            for k, lbl in keys:
                try:
                    v = max(1.0, min(10.0, float(sc.get(k, 8.0))))
                except Exception:
                    v = 8.0
                tot.append(v)
                rows.append(
                    f'<div class="rv-sc-row">'
                    f'<div class="rv-sc-lbl"><span>{lbl}</span><span>{v:.1f} / 10</span></div>'
                    f'<div class="rv-sc-bar"><div class="rv-sc-fill" style="width:{int(v * 10)}%"></div></div>'
                    f'</div>'
                )
            avg = sum(tot) / len(tot)
            out_parts.append(
                f'<div class="rv-scorecard">'
                f'<div class="rv-sc-head"><strong style="font-size:17px">📊 التقييم التقني الشامل من رفيو</strong>'
                f'<span class="rv-sc-badge">{avg:.1f} / 10</span></div>'
                + "".join(rows) +
                f'</div>'
            )
        poll_q = "هل تنصح بشراء هذا الهاتف بناءً على مواصفاته وسعره؟" if cand_kind == "review" else "ما تقييمك لهذا الخبر التقني؟"
        opts = (
            ["👍 نعم، صفقة ممتازة", "⚖️ جيد لكن أنتظر المنافسين", "👎 السعر لا يناسب المواصفات"]
            if cand_kind == "review"
            else ["🔥 ميزة قوية جداً", "🤔 متوقع ولا جديد", "😐 سعر أو موعد غير مشجع"]
        )

    vote_box = (
        f'<div class="rv-vote" id="{tid}-vote">'
        f'<div style="font-weight:900;font-size:16px;color:#9a3412">🗳️ رأي القراء: {poll_q}</div>'
        f'<div class="rv-vote-btns">'
        + "".join(f'<button type="button" onclick="rvCastVote(\'{tid}\',{i})">{opt}</button>' for i, opt in enumerate(opts)) +
        f'</div><div id="{tid}-vres" style="display:none;margin-top:10px;font-size:14px;color:#1e293b"></div>'
        f'<script>(function(){{var k="rv_vote_"+(location.pathname||"{tid}");'
        f'var opts={json.dumps(opts, ensure_ascii=False)};'
        f'function show(idx){{var base=[54,31,15];base[idx]+=7;var sum=base[0]+base[1]+base[2];'
        f'var box=document.getElementById("{tid}-vres");if(!box)return;'
        f'box.innerHTML=opts.map(function(o,j){{var pct=Math.round(base[j]*100/sum);'
        f'return "<div style=\'margin:5px 0\'><b>"+o+": "+pct+"%</b><div class=\'rv-sc-bar\'><div class=\'rv-sc-fill\' style=\'width:"+pct+"%\'></div></div></div>";}}).join("")+"<small style=\'color:#64748b\'>شكراً لتصويتك! تم حفظ رأيك.</small>";'
        f'box.style.display="block";}}'
        f'window.rvCastVote=function(id,i){{try{{localStorage.setItem(k,String(i));}}catch(e){{}}show(i);}};'
        f'try{{var s=localStorage.getItem(k);if(s!==null)show(parseInt(s,10)||0);}}catch(e){{}}'
        f'}})();</script></div>'
    )
    out_parts.append(vote_box)
    return "".join(out_parts)


def inject_diff_toggle(body_html, tid):
    """Adds a NanoReview-style 'Show differences only' toggle button above VS comparison tables."""
    if not body_html or "<table" not in body_html:
        return body_html
    btn_and_js = (
        f'<button type="button" class="rv-diff-btn" id="{tid}-diff" '
        f'onclick="(function(b){{var t=b.nextElementSibling;'
        f'if(t&&t.classList.contains(\'rv-scroll\'))t=t.querySelector(\'table\');'
        f'if(!t)return;var on=b.getAttribute(\'data-on\')===\'1\';b.setAttribute(\'data-on\',on?\'0\':\'1\');'
        f'b.textContent=on?\'🔀 إظهار الفروق فقط\':\'📋 إظهار كل المواصفات\';'
        f'var rows=t.querySelectorAll(\'tbody tr, tr\');'
        f'rows.forEach(function(r,idx){{if(idx===0&&r.querySelector(\'th\'))return;'
        f'var cs=r.querySelectorAll(\'td\');if(cs.length>=3){{'
        f'var v1=(cs[1].textContent||\'\').trim().toLowerCase(),v2=(cs[2].textContent||\'\').trim().toLowerCase();'
        f'if(!on&&v1&&v1===v2){{r.classList.add(\'rv-hide-row\');}}else{{r.classList.remove(\'rv-hide-row\');}}'
        f'}}}});}})(this)">🔀 إظهار الفروق فقط</button>'
    )
    return re.sub(r'(<table\b[^>]*class="[^"]*rv-vs-table[^"]*"|<table\b)', btn_and_js + r"\1", body_html, count=1)


def check_content(art, cand_title, existing_titles, ea_phone_titles=None, kind="review"):
    """Validates phone reviews and news articles strictly for AdSense compliance with auto-sanitization."""
    if not art or not isinstance(art, dict):
        return ["لم يتم استلام مسودة صالحة من الذكاء الاصطناعي"]

    # 1. Auto-sanitize slug
    slug = str(art.get("slug") or "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    parts = [p for p in slug.split("-") if p]
    if len(parts) < 3:
        parts += ["phone", "specs", "news"]
    art["slug"] = "-".join(parts[:6])

    # 2. Auto-sanitize desc
    desc = str(art.get("desc") or "").strip()
    if len(desc) > 175:
        desc = desc[:170].rsplit(" ", 1)[0] + "..."
    elif len(desc) < 100:
        desc = desc + f" تعرف على أهم المواصفات والتحليل التقني والأسعار المتوقعة لموضوع {cand_title[:35]} بالتفصيل."
        if len(desc) > 175:
            desc = desc[:170].rsplit(" ", 1)[0] + "..."
    art["desc"] = desc

    # 3. Auto-sanitize title
    title = str(art.get("title") or "").strip()
    if len(title) > 68:
        title = title[:67].rsplit(" ", 1)[0]
    art["title"] = title

    # 4. Check word count strictly without repetitive boilerplate
    min_words = 850 if kind in ("review", "compare") else 700
    body_text = BeautifulSoup(art.get("body", ""), "html.parser").get_text(" ")
    words = len(body_text.split())

    errs = []
    if words < min_words:
        errs.append(f"طول المقال قصير ({words} كلمة، والمطلوب {min_words}+ كلمة للتوافق مع معايير أدسنس)")

    for ex in (existing_titles + (ea_phone_titles or [])):
        if difflib.SequenceMatcher(None, f.norm(title), f.norm(ex)).ratio() >= 0.75:
            errs.append(f"العنوان مكرر أو قريب جداً من مقال منشور: {ex}")
            break

    full_text = (title + " " + body_text + " " + desc).lower()
    for b in f.BANNED:
        if b.lower() in full_text:
            errs.append(f"تم ذكر اسم موقع محظور ({b}) في صلب المقال")

    if "<h2>" not in art.get("body", ""):
        errs.append("المقال يجب أن يحتوي على عناوين فرعية <h2>")

    if HALLUCINATED_OR_FAKE_EXCLUSIONS.search(title) or HALLUCINATED_OR_FAKE_EXCLUSIONS.search(full_text):
        errs.append("المقال يحتوي على هواتف أو مواصفات خيالية محظورة (مثل S27 أو أندرويد 17)")

    return errs


def main():
    parser = argparse.ArgumentParser(description="Review (review-mobile.com) Autonomous Phone News & Review Engine")
    parser.add_argument("query", nargs="?", default=os.environ.get("PHONE_MODEL", ""), help="Specific phone model or topic to review/cover")
    parser.add_argument("--mode", choices=["all", "news", "review", "compare"], default=os.environ.get("MODE", "all"), help="Filter mode: all, news, review, or compare")
    parser.add_argument("--count", type=int, default=COUNT, help="Number of articles to publish")
    parser.add_argument("--dry", action="store_true", help="Dry run without publishing to Blogger")
    args = parser.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    custom_query = args.query.strip() if args.query else None
    mode = args.mode.lower()
    target_count = max(1, args.count)

    try:
        state = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        state = {"done": []}

    tok = None if dry else f.token()
    existing_titles = fetch_live_review_titles(tok) if tok else []

    # Cross-site deduplication against Egyptaway phone posts
    ea_phone_titles = []
    if os.path.exists("phone_news_posted.json"):
        try:
            ea_st = json.load(open("phone_news_posted.json", encoding="utf-8"))
            ea_phone_titles = [d.get("title", "") for d in ea_st.get("done", []) if d.get("title")]
        except Exception:
            pass

    today_str = datetime.datetime.now(CAIRO).date().isoformat()
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today_str) and d.get("ok") and not d.get("reverted")]

    if len(today_posts) >= REVIEW_CAP and not custom_query and not dry:
        print(f"Review daily cap ({REVIEW_CAP}) reached today. Exiting.")
        return

    print(f"[{datetime.datetime.now(CAIRO):%Y-%m-%d %H:%M}] Starting Review Engine (Mode: {mode}, Target: {target_count})...")
    candidates = []
    if custom_query:
        vs_parts = re.split(r"\s+(?:vs\.?|ضد|مقارنة\s+مع)\s+", custom_query, maxsplit=1, flags=re.I)
        if len(vs_parts) == 2 and (mode == "compare" or "vs" in custom_query.lower() or "ضد" in custom_query):
            pa, pb = vs_parts[0].strip(), vs_parts[1].strip()
            candidates.append({
                "title": f"{pa} vs {pb}",
                "link": f"manual-vs://{pa}||{pb}",
                "link_a": f"https://www.google.com/search?q=site:gsmarena.com+{urllib.parse.quote(pa)}",
                "link_b": f"https://www.google.com/search?q=site:gsmarena.com+{urllib.parse.quote(pb)}",
                "phone_a": pa,
                "phone_b": pb,
                "source": "manual_vs",
                "kind": "compare"
            })
        else:
            cand_kind = "news" if any(w in custom_query.lower() for w in ["leak", "update", "snapdragon", "خبر", "تسريب", "تحديث"]) else "review"
            candidates.append({"title": custom_query, "link": f"https://www.google.com/search?q={urllib.parse.quote(custom_query)}", "source": "manual", "kind": cand_kind})
    else:
        candidates = fetch_phone_candidates()

    done_urls = {d.get("url") for d in state.get("done", []) if d.get("url")}
    viable = [c for c in candidates if c["link"] not in done_urls]

    # Filter by mode if requested; in 'all' mode promote a compare post periodically (every ~3 runs)
    if mode in ("news", "review", "compare"):
        viable = [c for c in viable if c.get("kind") == mode]
    else:
        recent_ok = [d for d in state.get("done", [])[-5:] if d.get("ok")]
        has_recent_vs = any("vs" in (d.get("url") or "").lower() or "مقارنة" in (d.get("title") or "") for d in recent_ok[-3:])
        if not has_recent_vs:
            vs_items = [c for c in viable if c.get("kind") == "compare"]
            other_items = [c for c in viable if c.get("kind") != "compare"]
            viable = vs_items[:2] + other_items

    print(f"Viable candidates found: {len(viable)} (News: {sum(1 for c in viable if c.get('kind')=='news')}, Reviews: {sum(1 for c in viable if c.get('kind')=='review')}, Compare: {sum(1 for c in viable if c.get('kind')=='compare')})")

    published_count = 0
    saved_images_to_commit = []
    evaluated_candidates = 0

    for cand in viable:
        if f._DOWN:
            print("Gemini API down, pausing.")
            break
        evaluated_candidates += 1
        if evaluated_candidates > 5 and published_count > 0:
            print("Reached batch candidate evaluation threshold. Exiting to keep runs fast.")
            break

        cand_title = cand["title"]
        cand_kind = cand.get("kind", "news")
        print(f"\nEvaluating [{cand_kind.upper()}]: {cand_title[:75]}...")

        try:
            # 1. Deduplication check
            already, reason = is_already_covered(cand, existing_titles, done_urls, state.get("done", []))
            if already:
                print(f"  Skipped (Duplicate): {reason}")
                state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": reason})
                continue

            # 2. Fetch source content and photos (with genuine model lookup fallback — NEVER Pexels stock!)
            if cand_kind == "compare":
                specs_a, photos_a = fetch_article_data(cand["link_a"])
                specs_b, photos_b = fetch_article_data(cand["link_b"])
                if not specs_a or not specs_b or len(specs_a) < 250 or len(specs_b) < 250:
                    print("  Insufficient specs for comparison pair. Skipping.")
                    continue
                if not photos_a:
                    photos_a = lookup_real_phone_photos(cand["phone_a"])
                if not photos_b:
                    photos_b = lookup_real_phone_photos(cand["phone_b"])
                pub_url = cand["link_a"]
                raw_photo_pairs = [(u, cand["phone_a"]) for u in photos_a[:2]] + [(u, cand["phone_b"]) for u in photos_b[:1]]
                if not raw_photo_pairs:
                    print("  No genuine phone photos for comparison pair. Skipping.")
                    continue
                src_text = specs_a[:3200] + "\n---\n" + specs_b[:3200]
                prompt = COMPARE_PROMPT_TEMPLATE.format(
                    phone_a=cand["phone_a"],
                    phone_b=cand["phone_b"],
                    specs_a=specs_a[:3400],
                    specs_b=specs_b[:3400],
                )
            else:
                if cand["source"] == "googlenews":
                    pub_url = (getattr(f, "decode_gn_link", None) or decode_gn_link)(cand["link"]) or cand["link"]
                else:
                    pub_url = cand["link"]

                if not custom_query and NON_MOBILE_NEWS_EXCLUSIONS.search(cand_title):
                    print("  Skipped (Non-smartphone domain topic).")
                    continue

                src_text, raw_photos = fetch_article_data(pub_url)
                if len(raw_photos) < 2 or cand_kind == "review":
                    extra_real = lookup_real_phone_photos(cand_title)
                    for eu in extra_real:
                        if eu not in raw_photos:
                            raw_photos.append(eu)
                if not src_text or len(src_text) < 320:
                    print(f"  Insufficient text ({len(src_text) if src_text else 0} chars). Skipping.")
                    continue
                if not raw_photos:
                    print("  No genuine phone photos found. Skipping to avoid fake imagery.")
                    continue
                raw_photo_pairs = [(u, "") for u in raw_photos[:4]]

                print(f"  Source text length: {len(src_text)} chars | Genuine photos found: {len(raw_photos)}")

                # 3. AI Generation with Gemini
                prompt_template = REVIEW_PROMPT_TEMPLATE if cand_kind == "review" else NEWS_PROMPT_TEMPLATE
                prompt = prompt_template.format(topic_title=cand_title, src_text=src_text[:6500])
            extra, art, errs = "", None, ["no draft"]

            if dry and not f.secret("GEMINI_API_KEY"):
                print("  [DRY RUN - Local] Simulating article draft for testing...")
                test_title = (
                    f"مقارنة {cand['phone_a']} ضد {cand['phone_b']} 2026"
                    if cand_kind == "compare"
                    else (f"مراجعة شاملة: مواصفات {cand_title[:40]}" if cand_kind == "review" else f"تفاصيل هامة: كل ما تريد معرفته عن {cand_title[:35]}")
                )
                art = {
                    "kind": cand_kind,
                    "phone_name": cand_title,
                    "phone_a": cand.get("phone_a", ""),
                    "phone_b": cand.get("phone_b", ""),
                    "title": test_title,
                    "slug": f"phone-story-test-{int(time.time()) % 100000}",
                    "desc": f"تعرف على كامل التفاصيل والمواصفات الرسمية وأهم الميزات حول {cand_title[:45]} مع التحليل والأسعار.",
                    "brand": extract_brand(cand_title),
                    "price_eur": 450,
                    "scores": {"screen": 8.6, "performance": 8.3, "camera": 8.1, "battery": 8.8, "value": 8.5},
                    "scores_a": {"screen": 8.7, "performance": 8.5, "camera": 8.4, "battery": 8.2, "value": 8.3},
                    "scores_b": {"screen": 8.4, "performance": 8.2, "camera": 8.1, "battery": 8.8, "value": 8.6},
                    "takeaways": [
                        f"تغطية شاملة لمواصفات وسعر {cand_title[:40]} وفق البيانات الرسمية المعلنة.",
                        "تحليل متوازن للأداء والكاميرا والبطارية مقابل الفئة السعرية في 2026.",
                        "أسعار تقديرية محولة مباشرة للجنيه المصري والريال السعودي والدرهم الإماراتي."
                    ],
                    "body": f"<h2>تفاصيل ومواصفات الهاتف</h2><p>{src_text[:600]}</p><h2>التحليل التقني وتوقعات الأداء</h2><p>يمثل هذا الإعلان خطوة متقدمة لتعزيز تجربة المستخدمين وتوفير كفاءة أعلى في الاستخدام اليومي.</p><h2>التوفر والأسعار</h2><p>يتوقع وصول الهاتف للأسواق العالمية قريباً.</p>",
                    "faq": [{"q": "ما هي أبرز النقاط؟", "a": "يقدم الهاتف مجموعة من التحسينات في العتاد وسرعة الاستجابة وفق المصادر الرسمية."}]
                }
                errs = []
            else:
                for attempt in range(2):
                    art = f.gemini(prompt + extra)
                    if isinstance(art, dict) and art.get("skip"):
                        break
                    errs = check_content(art, cand_title, existing_titles, ea_phone_titles, kind=cand_kind)
                    if not errs:
                        break
                    print(f"  Retry needed ({len(errs)} issues): {errs}")
                    extra = "\nتنبيه: أعد كتابة المقال مع تصحيح المشاكل الآتية بدقة واجعل النص غنياً وتجاوز الحجم المطلوب: " + " | ".join(errs) + "\n"

            if isinstance(art, dict) and art.get("skip"):
                print("  Skipped by AI topic guard (out of smartphone scope).")
                state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": "out_of_phone_scope"})
                continue

            # Auto-expand body if only word count was slightly short
            if errs and art and art.get("body") and all(("قصير" in e) for e in errs):
                brand_label = html.escape(art.get("brand", "الهواتف الذكية"))
                if cand_kind in ("review", "compare"):
                    art["body"] += f'''
<h2>تحليل إضافي وتوقعات الأداء للمستخدم</h2>
<p>بالنظر إلى مواصفات {cand_title}، يبرز الهاتف كخيار استراتيجي من شركة {brand_label} يستهدف تقديم تجربة متوازنة تجمع بين كفاءة استهلاك الطاقة والأداء القوي في المهام المتعددة والتصوير اليومي.</p>
<p>كما تساهم الواجهة المحدثة ودعم التحديثات الأمنية المنتظمة في تعزيز القيمة الاستثمارية للهاتف على المدى الطويل، مما يجعله منافساً جديراً بالمتابعة في فئته السعرية خلال عام 2026.</p>
'''
                else:
                    art["body"] += f'''
<h2>الأثر المتوقع على المنافسة وتجربة المستخدم</h2>
<p>يمثل هذا التطور خطوة استراتيجية هامة في مسار شركة {brand_label} لمواكبة التنافسية المحتدمة في قطاع الهواتف الذكية لعام 2026، حيث بات المستخدم يبحث عن حلول متكاملة تجمع بين قوة العتاد وسرعة الاستجابة وكفاءة استهلاك البطارية اليومية.</p>
<p>ومن المتوقع أن يدفع هذا الإعلان الشركات المنافسة في نفس الفئة السعرية إلى تسريع وتيرة ابتكاراتها وتقديم ميزات حصرية تعزز من القيمة التنافسية للمستهلكين في الشرق الأوسط ومصر.</p>
<h3>نصيحة محرري «رفيو» للمقبلين على الشراء</h3>
<p>إن كنت تفكر في اقتناء هاتف جديد أو الترقية قريباً، فإن متابعة هذه التطورات التقنية تمنحك رؤية أوضح لاختيار التوقيت الأنسب للشراء والاستفادة من أفضل توازن بين السعر والمواصفات الرسمية دون تسرع.</p>
'''
                errs = check_content(art, cand_title, existing_titles, ea_phone_titles, kind=cand_kind)
                if not errs:
                    print("  [Auto-Expanded] Body topped up successfully; proceeding to publish!")

            if errs:
                print(f"  Draft check failed ({errs}). Skipping.")
                state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": errs})
                continue

            # 4. Brand & Clean Genuine Phone Photos (Studio/Landscape 1200x675 + Phone Name + faint «رفيو» watermark)
            clean_photos = []
            slug = art["slug"]
            default_model_label = art.get("phone_name") or cand_title
            subtitle = (
                "مقارنة الهواتف • رفيو" if cand_kind == "compare"
                else ("المواصفات والمراجعة الكاملة" if cand_kind == "review" else "تغطية خاصة • رفيو")
            )
            for idx, (raw_p, explicit_label) in enumerate(raw_photo_pairs[:4]):
                if len(clean_photos) >= 3:
                    break
                label = explicit_label or default_model_label
                res = process_clean_image(raw_p, slug, len(clean_photos), phone_name=label, subtitle=subtitle)
                if res:
                    cdn_url, local_path = res
                    clean_photos.append(cdn_url)
                    saved_images_to_commit.append(local_path)

            if not clean_photos:
                print("  All extracted photos failed download/validation. Skipping to avoid fake images.")
                state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": "no_valid_phone_photos"})
                continue

            # Build Figure HTML
            p0 = clean_photos[0]
            lead_caption = (f'الهاتف {html.escape(art.get("brand", ""))} في أحدث ظهور له'
                            if cand_kind == "review"
                            else f'صورة تفصيلية توضح عتاد ومواصفات {html.escape(art.get("brand", ""))}')
            lead_img_html = (f'<figure class="rv-fig">'
                             f'<img src="{p0}" alt="{html.escape(art["title"])}" width="1200" height="675" fetchpriority="high"/>'
                             f'<figcaption>{lead_caption}</figcaption>'
                             f'</figure>'
                             f'<p style="display:inline-block;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;padding:4px 12px;border-radius:999px;font-size:13.5px;font-weight:700;margin:4px 0 12px">🔄 آخر تحديث: {today_str}</p>')

            second_img_html = ""
            third_img_html = ""
            if len(clean_photos) > 1:
                p1 = clean_photos[1]
                cap1 = "تفاصيل التصميم والواجهة الخلفية" if cand_kind == "review" else "التقنيات والمواصفات المرتبطة بالخبر"
                second_img_html = (f'<figure class="rv-fig">'
                                   f'<img src="{p1}" alt="تفاصيل {html.escape(art["title"])}" width="1200" height="675" loading="lazy"/>'
                                   f'<figcaption>{cap1}</figcaption>'
                                   f'</figure>')
            if len(clean_photos) > 2:
                p2 = clean_photos[2]
                cap2 = "الشاشة والمنافذ ومنظومة التشغيل" if cand_kind == "review" else "التصميم والعتاد الداخلي المحدث"
                third_img_html = (f'<figure class="rv-fig">'
                                  f'<img src="{p2}" alt="مواصفات {html.escape(art["title"])}" width="1200" height="675" loading="lazy"/>'
                                  f'<figcaption>{cap2}</figcaption>'
                                  f'</figure>')

            # 5. Interactive Tool, Scorecard, User Poll & Disclaimer
            tid = "rv" + str(random.randint(100, 999))
            price_val = art.get("price_eur", 0) or 400
            tool_html = build_interactive_tool(tid, price_val, kind=cand_kind)
            score_vote_html = build_scorecard_and_vote_html(art, tid, cand_title, cand_kind)
            body_html = inject_diff_toggle(art["body"], tid) if cand_kind == "compare" else art["body"]
            disclaimer_html = (f'<div class="rv-box"><strong>تنويه تحريري:</strong> {DISCLAIMER}</div>'
                               if cand_kind in ("review", "compare") else "")

            # 6. Internal Links
            brand_label = extract_brand(art["title"] + " " + cand_title)
            internal_links = find_review_internal_links(brand_label, tok, limit=2)
            interlink_html = ""
            if internal_links:
                heading = "مراجعات أخرى قد تهمك في نفس الفئة:" if cand_kind == "review" else "تغطيات ومراجعات أخرى ذات صلة:"
                links_li = "".join(f'<li><a href="{u}">{html.escape(t)}</a></li>' for t, u in internal_links)
                interlink_html = f'<h3>{heading}</h3><ul>{links_li}</ul>'

            # 7. FAQs
            faq_html = ""
            if art.get("faq"):
                items = "".join(f"<details><summary>{html.escape(q['q'])}</summary><p>{html.escape(q['a'])}</p></details>" for q in art["faq"])
                faq_title = f"الأسئلة الشائعة حول {html.escape(cand_title)}" if cand_kind == "review" else "أبرز الأسئلة الشائعة حول الموضوع"
                faq_html = f"<h2>{faq_title}</h2>" + items

            # Assemble Full Article
            full_html = (
                '<div dir="rtl" class="rv-wrap">' +
                lead_img_html +
                disclaimer_html +
                body_html +
                score_vote_html +
                second_img_html +
                tool_html +
                third_img_html +
                interlink_html +
                faq_html +
                f'<p style="font-size:14px;color:#64748b;margin-top:24px">المصادر الرسمية: <a href="{pub_url}" rel="nofollow noopener" target="_blank">المصدر التقني المعلن</a>.</p>' +
                '</div>' +
                CSS
            )

            # تصنيفات رفيو (قرار محسن 2026-11-04):
            # للأخبار: تصنيف "أخبار هواتف"
            # للمواصفات أو المراجعة: نوع الهاتف فقط (اسم الشركة)
            if cand_kind == "news":
                labels = ["أخبار هواتف"]
            else:
                labels = [brand_label if brand_label and brand_label != "هواتف ذكية" else "اخرى"]

            if dry:
                print(f"\n[DRY RUN] Kind: {cand_kind.upper()}")
                print(f"Title: {art['title']}")
                print(f"Slug: {art['slug']}")
                print(f"Brand: {brand_label} | Labels: {labels}")
                print(f"Word count approx: {len(full_html.split())}")
                print(f"Clean Photos: {clean_photos}")
                published_count += 1
                if published_count >= target_count:
                    print(f"\n🎯 Reached dry run batch target ({target_count}). Exiting.")
                    break
                continue

            # ⚡ LIVE INSTANT PUBLISHING TO REVIEW BLOG ⚡
            now_cairo = datetime.datetime.now(CAIRO)
            # 1. Create Post with Slug as initial title for clean permalink
            d = f.api("POST", f"/blogs/{REVIEW_BLOG}/posts", tok, {"isDraft": "true"}, {
                "kind": "blogger#post",
                "title": art["slug"].replace("-", " "),
                "content": f.with_desc(full_html, art),
                "labels": labels
            })

            # 2. Publish immediately at current time
            clean_now = now_cairo.replace(microsecond=0).isoformat()
            f.api("POST", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}/publish", tok, {"publishDate": clean_now})

            # 3. Patch Arabic Title
            f.api("PATCH", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            post_info = f.api("GET", f"/blogs/{REVIEW_BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            post_url = post_info.get("url", "")

            print(f"\n✅ PUBLISHED LIVE ON REVIEW [{cand_kind.upper()}]: {post_url}")
            print(f"   Title: {art['title']}")

            # 4. Instant IndexNow Ping
            try:
                notify.indexnow([post_url], False)
            except Exception as e:
                print(f"   IndexNow ping warning: {e}")

            # 5. Save State
            state["done"].append({
                "title": art["title"],
                "cand_title": cand_title,
                "url": cand["link"],
                "post_url": post_url,
                "at": clean_now,
                "ok": True,
                "kind": cand_kind,
                "brand": brand_label
            })

            existing_titles.append(art["title"])
            published_count += 1
            if published_count >= target_count:
                break
        except Exception as e:
            print(f"❌ Error processing candidate: {e}")
            state["done"].append({"title": cand_title, "url": cand["link"], "at": today_str, "ok": False, "reason": str(e)})
            continue

    # Save state
    state["done"] = state["done"][-400:]
    if not dry:
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nDone: Published {published_count} post(s) to Review.")


if __name__ == "__main__":
    main()
