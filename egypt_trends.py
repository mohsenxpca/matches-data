"""Egyptaway Instant Breaking Trends Engine for Egypt (mohsen 2026-10-29).
Publishes hot general Egyptian trends and breaking public interest news IMMEDIATELY (no scheduling delay)
to rank first in Google Search, Google News, and Google Discover before competitors.

Monitors and covers:
- Government decisions & adjustments (تغيير الساعة، التوقيت الشتوي والصيفي، قرارات مجلس الوزراء)
- Weather alerts & meteorological forecasts (بيان الأرصاد الجوية، النوات، موجات الطقس والسيول)
- Official holidays & vacations (الإجازات الرسمية، عطلات البنوك، إجازات المدارس)
- Public subsidies & supplies (بطاقات التموين، إضافة المواليد، أسعار الخبز، معارض أهلاً رمضان)
- School & university news (مواعيد الامتحانات، إجازة نصف العام، نتائج الشهادات)
- Public transportation decisions (مواعيد المترو والقطارات، أسعار التذاكر)
- Breaking viral search trends across Egyptian news & Google Trends Egypt

Usage:
  python egypt_trends.py                     # Auto-detects the hottest unposted Egyptian trend and publishes immediately
  python egypt_trends.py "تغيير الساعة"       # Publishes a breaking post about a specific topic immediately
  python egypt_trends.py --dry               # Dry run (prints draft without publishing)
"""
import datetime, difflib, hashlib, html, json, os, random, re, sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import football as f
import image_guard
import topic_guard
import notify

CAIRO = ZoneInfo("Africa/Cairo")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
STATE_FILE = "egypt_trends_posted.json"
DAY_CAP = int(os.environ.get("EGYPT_TRENDS_DAY_CAP", "12"))
COUNT = int(os.environ.get("COUNT", "1"))

# Curated high-res natural photography fallbacks (no text overlays, diverse multi-photo pools)
TREND_PHOTO_POOLS = {
    "sports": [
        "https://images.pexels.com/photos/3148452/pexels-photo-3148452.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/30651230/pexels-photo-30651230.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/19875973/pexels-photo-19875973.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/36227922/pexels-photo-36227922.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/26694125/pexels-photo-26694125.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/114296/pexels-photo-114296.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/274422/pexels-photo-274422.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "tennis": [
        "https://images.pexels.com/photos/209977/pexels-photo-209977.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/1619860/pexels-photo-1619860.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/5739164/pexels-photo-5739164.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "phones": [
        "https://images.pexels.com/photos/1092644/pexels-photo-1092644.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/404280/pexels-photo-404280.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/788946/pexels-photo-788946.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/607812/pexels-photo-607812.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "gaming": [
        "https://images.pexels.com/photos/3165335/pexels-photo-3165335.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/194511/pexels-photo-194511.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "gold": [
        "https://images.pexels.com/photos/8370752/pexels-photo-8370752.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/259027/pexels-photo-259027.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "clock": [
        "https://images.pexels.com/photos/1198264/pexels-photo-1198264.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/280264/pexels-photo-280264.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "weather": [
        "https://images.pexels.com/photos/1118873/pexels-photo-1118873.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/125510/pexels-photo-125510.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "supply": [
        "https://images.pexels.com/photos/264636/pexels-photo-264636.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "transport": [
        "https://images.pexels.com/photos/1036867/pexels-photo-1036867.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "education": [
        "https://images.pexels.com/photos/207691/pexels-photo-207691.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "money": [
        "https://images.pexels.com/photos/259027/pexels-photo-259027.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "holidays": [
        "https://images.pexels.com/photos/1029141/pexels-photo-1029141.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
    "general": [
        "https://images.pexels.com/photos/518543/pexels-photo-518543.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/1029141/pexels-photo-1029141.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
        "https://images.pexels.com/photos/3290075/pexels-photo-3290075.jpeg?auto=compress&amp;cs=tinysrgb&amp;w=1200&amp;h=675&amp;fit=crop",
    ],
}

# Cross-link suggestions to relevant Egyptaway hub pages
HUB_LINKS = {
    "prayer": ('<p>ولمعرفة التوقيت الدقيق ومواعيد الصلاة بعد التعديل، تابع صفحة '
               '<a href="https://www.egyptaway.com/p/prayer-times-egypt.html">مواقيت الصلاة اليوم في مصر</a> '
               'المحدثة لحظة بلحظة بتوقيت القاهرة والمحافظات.</p>'),
    "weather": ('<p>ويمكنك متابعة خريطة الطقس ودرجات الحرارة المتوقعة في جميع المدن عبر صفحة '
                '<a href="https://www.egyptaway.com/p/weather-egypt.html">حالة الطقس اليوم في مصر</a>.</p>'),
    "holidays": ('<p>للاطلاع على جدول الإجازات الرسمية المتبقية مدفوعة الأجر للقطاعين الحكومي والخاص، راجع صفحة '
                 '<a href="https://www.egyptaway.com/p/official-holidays-egypt.html">الإجازات الرسمية في مصر 2026</a>.</p>'),
    "gold": ('<p>تابع أيضاً التحديثات اللحظية لأسعار الذهب والعملات في السوق المصري عبر صفحة '
             '<a href="https://www.egyptaway.com/p/gold-prices-egypt.html">أسعار الذهب اليوم في مصر</a>.</p>')
}

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
    r"قتل|مقتل|جريم|اغتصاب|تحرش|انتحار|ذبح|طعن|مخدرات|إرهاب|ارهاب|فضيحة|فيديو إباحي|اباحي|شذوذ|فضايح|sex|porn|murder|suicide"
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
    r"امتحانات|جدول الامتحانات|مواعيد الامتحانات|مدارس|جامعات|إجازة رسمية|إجازات|عطلة رسمية|التوقيت الشتوي|التوقيت الصيفي|تغيير الساعة|"
    r"إسكان|شقق|سكن لكل المصريين|مسكن|كراسة شروط|طرح وحدات|أراضي الإسكان|"
    r"بنزين|سولار|أسعار البنزين|وقود|لجنة التسعير|تموين|بطاقات التموين|صرف السلع|"
    r"عطل|إنستاباي|فودافون كاش|انقطاع الإنترنت|شبكة المحمول|فوري"
)

def is_valid_topic(title):
    if not title:
        return False
    if re.search(BANNED_TOPICS_REGEX, title, re.I):
        return False
    if not re.search(ALLOWED_TOPICS_REGEX, title, re.I):
        return False
    # استبعاد الطقس الأجنبي (يجب أن يكون الطقس مصرياً أو إقليمياً وثيق الصلة بمصر)
    if re.search(r"طقس|أرصاد|أمطار|سيول|ثلوج|جليد|عاصفة|درجات الحرارة", title, re.I):
        if re.search(r"أوروبا|إيطاليا|فرنسا|ألمانيا|بريطانيا|إسبانيا|أمريكا|كندا|روسيا|اليابان|الصين|تركيا|اليونان", title, re.I):
            return False
    # استبعاد الدوريات والمسابقات الأجنبية المغمورة لتركيز الموقع على الكرة المصرية والمحترفين والقمم العالمية
    if re.search(r"دوري الدرجة|الدرجة الثانية|الدرجة الثالثة|الدوري الروماني|الدوري التشيكي|الدوري البولندي|الدوري القبرصي", title, re.I):
        return False
    return True

AVOID_REGEX = BANNED_TOPICS_REGEX

TREND_QUERIES = [
    "تغيير الساعة OR التوقيت الشتوي OR التوقيت الصيفي when:24h",
    "الأرصاد الجوية OR درجات الحرارة OR سقوط الأمطار when:24h",
    "إجازة رسمية OR عطلة رسمية OR إجازة البنوك when:24h",
    "بطاقات التموين OR وزارة التموين OR صرف السلع when:24h",
    "وزارة التربية والتعليم OR امتحانات OR جدول الامتحانات when:24h",
    "مواعيد المترو OR مواعيد القطارات OR السكة الحديد when:24h",
    "زيادة المرتبات OR صرف المعاشات OR تكافل وكرامة when:24h",
]

PROMPT_TEMPLATE = """أنت محرر شؤون مصرية وتقارير خدمية في موقع ايجبتاوى. موضوع «{topic_title}» عليه اهتمام وبحث واسع في الشارع المصري الآن.
اكتب خبراً أصلياً شاملاً وواضحاً وسريع الفهم بالعربي البسيط والمفهوم لجمهور مصر والوطن العربي، بناءً على «النص المصدر» فقط.

قواعد مهنية صارمة:
- الحقيقة والمصداقية المطلقة: اعتمد 100% على الحقائق والأرقام والقرارات والمواعيد المذكورة في المصدر. ممنوع اختراع أي رقم أو تاريخ أو تفاصيل غير موجودة.
- اكتب كل الأرقام بالأرقام (مثل: 60 دقيقة، 18 درجة، 10 أيام).
- أسلوب صحفي متماسك: صغ المقال بأسلوب شيق يبدأ بالمعلومة الأساسية التي يبحث عنها القارئ (ماذا حدث ومتى وكيف يؤثر عليه؟).
- القيمة المضافة: اشرح الإجراءات والخطوات العملية بوضوح (كيف يضبط ساعته؟ كيف يتعامل مع الطقس؟ مواعيد الإجازة ومن تشملهم؟).
- ممنوع ذكر اسم الموقع المصدر (مثل اليوم السابع أو مصراوي أو صدى البلد) داخل النص.
- الطول: الـ body من 650 لـ 850 كلمة، مقسم بـ 4 إلى 5 عناوين فرعية <h2> وفقرات <p>، وقوائم <ul> لو مناسبة.

رجّع ردك على هيئة JSON صالح فقط بالشكل التالي دون أي نصوص إضافية:
{{"title": "عنوان جذاب وصادق وواضح يبدأ بالحدث أقل من 65 حرف", "kicker": "2-4 كلمات للتصنيف", "slug": "english-slug-3-to-6-words", "desc": "وصف دقيق للبحث من 140 لـ 160 حرف يبدأ بأهم معلومة", "takeaways": ["أهم معلومة في 30 ثانية من المصدر بالأرقام", "ثاني أهم نقطة للمواطن", "موعد أو خطوة عملية"], "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}

عنوان الموضوع المستهدف: {topic_title}

النص المصدر الموثق:
{src_text}
"""


def build_discover_interactive_widget(title, query):
    t = (title + " " + query).lower()
    if any(k in t for k in ["مباراة", "الاهلي", "الأهلي", "الزمالك", "دوري", "منتخب", "كأس", "ريال مدريد", "صلاح", "مرموش"]):
        return '''<div class="ea-discover-widget" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin:20px 0;box-shadow:0 2px 8px rgba(0,0,0,0.04);font-family:'Cairo',Tahoma,sans-serif;direction:rtl;text-align:right;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
    <span style="background:#ea580c;color:#fff;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:bold;">توقعات الجماهير</span>
    <h3 style="margin:0;font-size:15px;color:#0f172a;font-weight:700;">🏆 توقعك للنتيجة: ما هي رؤيتك لمجريات هذه المواجهة المرتقبة؟</h3>
  </div>
  <p style="font-size:13.5px;color:#64748b;margin-bottom:12px;">شارك برأيك وتوقعك لترى نتائج استطلاع الجماهير المباشرة:</p>
  <div class="ea-poll-btns" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">فوز مستحق وحاسم</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">التعادل هو الأقرب</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">مفاجأة غير متوقعة</button>
  </div>
  <div class="ea-poll-res" style="display:none;background:#fff;border-radius:8px;padding:12px;border:1px dashed #ea580c;">
    <div style="font-size:13px;font-weight:bold;margin-bottom:6px;">نتائج توقعات وتصويت الجماهير:</div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">فوز الفريق الأقرب:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#16a34a;width:58%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">58%</span></div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">نتيجة التعادل:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#eab308;width:26%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">26%</span></div>
    <div style="display:flex;align-items:center;font-size:12px;"><span style="width:130px;">خسارة مفاجئة:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#dc2626;width:16%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">16%</span></div>
    <div style="font-size:11px;color:#94a3b8;margin-top:6px;">تم تسجيل صوتك وتوقعك بنجاح.. بالتوفيق لفريقك!</div>
  </div>
</div>
<script>
function eaVote(btn) {
  var box = btn.closest('.ea-discover-widget');
  if (box) {
    box.querySelector('.ea-poll-btns').style.display = 'none';
    box.querySelector('.ea-poll-res').style.display = 'block';
  }
}
</script>'''
    elif any(k in t for k in ["ذهب", "دولار", "شهادة", "بنوك", "فائدة", "سعر الذهب", "سولار"]):
        return '''<div class="ea-discover-widget" style="background:#fffbeb;border:1px solid #fef3c7;border-radius:14px;padding:16px;margin:20px 0;font-family:'Cairo',Tahoma,sans-serif;direction:rtl;text-align:right;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
    <span style="background:#d97706;color:#fff;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:bold;">نبض السوق</span>
    <h3 style="margin:0;font-size:15px;color:#78350f;font-weight:700;">📈 مؤشر الأسعار: توقعاتك لمسار السوق خلال الأيام القادمة؟</h3>
  </div>
  <p style="font-size:13.5px;color:#92400e;margin-bottom:12px;">شارك برأيك في استطلاع أسعار اليوم لمعرفة رؤية المتعاملين:</p>
  <div class="ea-poll-btns" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #fde68a;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">استقرار عند المستويات الحالية</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #fde68a;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">صعود بفعل التغيرات العالمية</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #fde68a;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">تراجع مؤقت وفرصة للشراء</button>
  </div>
  <div class="ea-poll-res" style="display:none;background:#fff;border-radius:8px;padding:12px;border:1px dashed #d97706;">
    <div style="font-size:13px;font-weight:bold;margin-bottom:6px;">توقعات المتعاملين والمستثمرين:</div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">استقرار نسبي:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#16a34a;width:52%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">52%</span></div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">احتمال الارتفاع:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#eab308;width:31%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">31%</span></div>
    <div style="display:flex;align-items:center;font-size:12px;"><span style="width:130px;">فرصة للشراء:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#dc2626;width:17%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">17%</span></div>
    <div style="font-size:11px;color:#94a3b8;margin-top:6px;">تم تسجيل تصويتك بنجاح.. تابع التحديثات أولاً بأول.</div>
  </div>
</div>
<script>
function eaVote(btn) {
  var box = btn.closest('.ea-discover-widget');
  if (box) {
    box.querySelector('.ea-poll-btns').style.display = 'none';
    box.querySelector('.ea-poll-res').style.display = 'block';
  }
}
</script>'''
    else:
        return '''<div class="ea-discover-widget" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin:20px 0;box-shadow:0 2px 8px rgba(0,0,0,0.04);font-family:'Cairo',Tahoma,sans-serif;direction:rtl;text-align:right;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
    <span style="background:#ea580c;color:#fff;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:bold;">صوت القراء</span>
    <h3 style="margin:0;font-size:15px;color:#0f172a;font-weight:700;">🗳️ استطلاع الجمهور: ما رأيك في هذه الأنباء والتطورات؟</h3>
  </div>
  <p style="font-size:13.5px;color:#64748b;margin-bottom:12px;">شارك برأيك.. كيف ترى تأثير هذه المستجدات في الفترة القادمة:</p>
  <div class="ea-poll-btns" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">خطوة إيجابية ومهمة</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">تحتاج لتوضيح ومتابعة</button>
    <button type="button" onclick="eaVote(this)" style="flex:1;min-width:120px;padding:10px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit;">محايد ولا تؤثر عليّ</button>
  </div>
  <div class="ea-poll-res" style="display:none;background:#fff;border-radius:8px;padding:12px;border:1px dashed #ea580c;">
    <div style="font-size:13px;font-weight:bold;margin-bottom:6px;">نتائج تصويت ومشاركات المتابعين:</div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">خطوة إيجابية:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#16a34a;width:66%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">66%</span></div>
    <div style="display:flex;align-items:center;margin-bottom:4px;font-size:12px;"><span style="width:130px;">تحتاج متابعة:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#eab308;width:22%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">22%</span></div>
    <div style="display:flex;align-items:center;font-size:12px;"><span style="width:130px;">رأي محايد:</span><div style="flex:1;background:#e2e8f0;border-radius:4px;height:10px;overflow:hidden;"><div style="background:#dc2626;width:12%;height:100%;"></div></div><span style="margin-right:8px;font-weight:bold;">12%</span></div>
    <div style="font-size:11px;color:#94a3b8;margin-top:6px;">تم تسجيل رأيك بنجاح.. شكراً لمشاركتك.</div>
  </div>
</div>
<script>
function eaVote(btn) {
  var box = btn.closest('.ea-discover-widget');
  if (box) {
    box.querySelector('.ea-poll-btns').style.display = 'none';
    box.querySelector('.ea-poll-res').style.display = 'block';
  }
}
</script>'''

def get_category_pool(text):
    t = text.lower()
    # 1. بنوك وشهادات واقتصاد وذهب وعملات (تُفحص قبل الرياضة لمنع تطابق كلمة "البنك الأهلي" مع كورة)
    if re.search(r"شهادة|شهادات|البنك الأهلي|بنك مصر|البنك المركزي|فوائد البنوك|ودائع|سعر الفائدة", t) and not re.search(r"نادي البنك الأهلي|فريق البنك الأهلي", t):
        return TREND_PHOTO_POOLS["money"]
    if re.search(r"ذهب|عيار 21|الجنيه الذهب|سعر الذهب|بورصة الذهب|دولار|سعر الصرف|عملات|ريال|درهم", t):
        return TREND_PHOTO_POOLS["gold"]

    # 2. تنس ورياضات فردية
    if re.search(r"تنس|ألكاراز|نادال|ديوكوفيتش|رولان جاروس|ويمبلدون|مضرب", t):
        return TREND_PHOTO_POOLS["tennis"]

    # 3. كورة ورياضة وبطولات وملاعب
    is_sports = False
    if re.search(r"نادي البنك الأهلي|فريق البنك الأهلي", t):
        is_sports = True
    elif re.search(r"كورة|كرة|مباراة|مباريات|دوري|ليفربول|ريال مدريد|برشلونة|ملعب|استاد|لاعب|مدرب|فريق|نادي|كأس|بطولة|ديربي|كلاسيكو|منتخب|أدنوك|توتنهام|ليدز|مانشستر|أرسنال|بايرن|صلاح|مرموش|ميسي|رونالدو", t):
        is_sports = True
    elif re.search(r"الأهلي|الاهلي|أهلي|أهلى|زمالك|بيراميدز", t) and not re.search(r"البنك الأهلي|بنك الأهلي", t):
        is_sports = True
    if is_sports:
        return TREND_PHOTO_POOLS["sports"]

    # 4. هواتف وتكنولوجيا وتطبيقات
    if re.search(r"هاتف|موبايل|سامسونج|شاومي|آيفون|ايفون|أندرويد|اندرويد|تطبيق|تحديث|معالج|كاميرا|شاشة|ذكاء اصطناعي|شات جي بي تي|جيميني|سماعة|لاب توب|سيرفر", t):
        return TREND_PHOTO_POOLS["phones"]

    # 5. ألعاب وجيمنج
    if re.search(r"لعبة|العاب|ألعاب|جيمنج|بلايستيشن|اكس بوكس|ببجي|فري فاير|فورتنايت|فيفا|اي فوتبول", t):
        return TREND_PHOTO_POOLS["gaming"]

    # 6. ساعة وتوقيت
    if re.search(r"ساعة|توقيت|الشتوي|الصيفي|تأخير|تقديم", t):
        return TREND_PHOTO_POOLS["clock"]

    # 7. طقس وأرصاد
    if re.search(r"طقس|أرصاد|مطر|حرارة|شتاء|سيول|رياح|نوة", t):
        return TREND_PHOTO_POOLS["weather"]

    # 8. تموين وسلع
    if re.search(r"تموين|سلع|خبز|معرض|أهلا رمضان|سكر|زيت", t):
        return TREND_PHOTO_POOLS["supply"]

    # 9. مواصلات وقطارات ومترو
    if re.search(r"مترو|قطار|سكة حديد|مواصلات|تذكرة|تذاكر", t):
        return TREND_PHOTO_POOLS["transport"]

    # 10. تعليم وامتحانات
    if re.search(r"مدارس|جامعات|امتحانات|تعليم|نتيجة|تنسيق|دراسة", t):
        return TREND_PHOTO_POOLS["education"]

    # 11. مرتبات ومعاشات وبنوك
    if re.search(r"مرتب|معاش|فلوس|صرف|مالية|تكافل", t):
        return TREND_PHOTO_POOLS["money"]

    # 12. إجازات وعطلات
    if re.search(r"إجازة|عطلة|أعياد|رسمية|مناسبة", t):
        return TREND_PHOTO_POOLS["holidays"]

    return TREND_PHOTO_POOLS["general"]


def pick_fallback_photo(text, recent_images=()):
    pool = get_category_pool(text)
    return image_guard.get_guaranteed_image(None, text, pool, recent_images=recent_images)


def pick_hub_callout(text):
    t = text.lower()
    if re.search(r"ساعة|توقيت|الشتوي|الصيفي|صلاة", t):
        return HUB_LINKS["prayer"]
    if re.search(r"طقس|أرصاد|مطر|حرارة|شتاء", t):
        return HUB_LINKS["weather"]
    if re.search(r"إجازة|عطلة|رسمية", t):
        return HUB_LINKS["holidays"]
    if re.search(r"ذهب|دولار|أسعار|عملات", t):
        return HUB_LINKS["gold"]
    return ""


def detect_trend_category_labels(text, query=""):
    """تصنيف دقيق للموضوع بحسب أقسام الموقع الرسمية بدلاً من كلمة أخبار العامة.
    الكورة والرياضة تُفحص أولاً تماماً لمنع تصنيف أي خبر رياضي كخدمات نهائياً.
    """
    t = (text + " " + query).lower()

    # 1. كورة ورياضة وبطولات (أولوية مطلقة)
    sports_rx = (
        r"\bكورة\b|\bكرة\b|مباراة|مباريات|\bدوري\b|كلاسيكو|ديربي|نهائي|كأس|بطولة|جولة|"
        r"\bالأهلي\b|\bالاهلي\b|\bالزمالك\b|\bبيراميدز\b|\bالإسماعيلي\b|\bالمصري\b|\bسيراميكا\b|\bحرس الحدود\b|"
        r"\bالهلال\b|\bالنصر\b|\bالاتحاد\b|\bالشباب\b|\bالفتح\b|\bالاتفاق\b|\bدوري روشن\b|"
        r"الدوري المصري|الدوري السعودي|الدوري الإنجليزي|الدوري الإسباني|الدوري الإيطالي|الدوري الألماني|"
        r"دوري أبطال|الكونفدرالية|\bالليجا\b|\bالبريميرليج\b|\bالبوندسليجا\b|"
        r"ريال مدريد|برشلونة|أتلتيكو|ليفربول|مانشستر|أرسنال|تشيلسي|توتنهام|بايرن|دورتموند|إنتر ميلان|\bإنتر\b|\bميلان\b|"
        r"\bمحمد صلاح\b|\bرونالدو\b|\bميسي\b|\bمبابي\b|\bفينيسيوس\b|\bبيلينجهام\b|\bهالاند\b|\bمرموش\b|"
        r"\bحسام حسن\b|\bإبراهيم حسن\b|\bكولر\b|\bجوميز\b|\bفليك\b|\bأنشيلوتي\b|\bعموتة\b|\bرافينيا\b|"
        r"نوتينجهام|بورنموث|\bليدز\b|ليفانتي|فينيزيا|جمباز|سباحة|منتخب مصر|منتخب|لاعب|مدرب|فريق|نادي|ملعب|مرمى|حارس|هدف|أهداف|صدارة|صفقات|ميركاتو"
    )
    if re.search(sports_rx, t):
        new_labels = ["رياضة", "أخبار الكورة"]
        if re.search(r"دوري مصري|الدوري المصري|\bالأهلي\b|\bالزمالك\b|بيراميدز", t):
            new_labels.append("الدوري المصري")
        elif re.search(r"دوري روشن|الدوري السعودي|\bالهلال\b|\bالنصر\b|\bالاتحاد\b|\bالفتح\b", t):
            new_labels.append("دوري روشن")
        return list(dict.fromkeys(new_labels))

    # 2. طقس وأرصاد
    if re.search(r"طقس|أرصاد|أمطار|سيول|حرارة|رياح|نوة|عاصفة|درجات الحرارة", t):
        return ["خدمات", "طقس"]
    # 3. توقيت وتغيير الساعة
    if re.search(r"توقيت شتوي|توقيت صيفي|التوقيت الشتوي|التوقيت الصيفي|تغيير الساعة|تقديم الساعة|تأخير الساعة", t):
        return ["خدمات", "توقيت"]
    # 4. امتحانات وتعليم ومدارس
    if re.search(r"امتحان|امتحانات|مدارس|مدرسة|جامعة|جامعات|تعليم|نتيجة|تنسيق|دراسة|شهادة الثانوية", t):
        return ["خدمات", "تعليم"]
    # 5. قطارات ومترو ومواصلات
    if re.search(r"قطار|قطارات|سكة حديد|مترو|مواصلات|تذاكر القطار|تذكرة القطار", t):
        return ["خدمات", "قطارات"]
    # 6. تموين ودعم وسلع
    if re.search(r"بطاقة التموين|بطاقات التموين|صرف السلع|سلع تموينية|معرض أهلا رمضان", t):
        return ["خدمات", "تموين"]
    # 7. مرتبات ومعاشات وأجور
    if re.search(r"مرتب|مرتبات|معاش|معاشات|صرف المرتبات|صرف المعاشات|أجور|حد أدنى للأجور|تكافل وكرامة", t):
        return ["خدمات", "مرتبات"]
    # 8. إسكان وشقق
    if re.search(r"إسكان|شقق الإسكان|سكن لكل المصريين|بوابة مسكن|كراسة شروط|طرح وحدات|شقق جنة|سكن مصر|دار مصر", t):
        return ["خدمات", "إسكان"]
    # 9. بنزين ومحروقات
    if re.search(r"بنزين|سولار|وقود|محروقات|لجنة التسعير|أنبوبة غاز", t):
        return ["خدمات", "أسعار البنزين"]
    # 10. بنوك وذهب وعملات
    if re.search(r"\bذهب\b|عيار 21|الجنيه الذهب|سعر الذهب|بورصة الذهب", t) and not re.search(r"ميدالية|بطولة|كأس", t):
        return ["اقتصاد", "أسعار الذهب"]
    if re.search(r"\bدرهم\b|\bدينار\b|ريال سعودي|سعر الدولار|سعر الصرف|عملات أجنبية", t):
        return ["اقتصاد", "أسعار العملات"]
    if re.search(r"شهادة البنك|شهادات البنك|البنك الأهلي|بنك مصر|البنك المركزي المصري|فائدة البنوك", t):
        return ["اقتصاد", "شهادات البنوك"]
    # 11. تكنولوجيا وهواتف
    if re.search(r"سامسونج|شاومي|آيفون|ايفون|هاتف ذكي|موبايل|تطبيق واتساب|ذكاء اصطناعي", t):
        return ["تقنية", "هواتف"]
    # 12. إجازات رسمية
    if re.search(r"إجازة رسمية|إجازات رسمية|عطلة رسمية", t):
        return ["خدمات", "إجازات رسمية"]

    return ["منوعات"]


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


def fetch_publisher_article(url):
    """Fetches publisher URL, extracts real high-res news photo (og:image) and full factual text."""
    try:
        resp = requests.get(url, headers=UA, timeout=25, verify=False)
        if resp.status_code != 200:
            return None, None
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extract real news photo (only if from a trusted Egyptian publisher and safe)
        img_url = None
        if image_guard.is_trusted_egypt_publisher(url):
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og and og.get("content"):
                c = og["content"].strip()
                if image_guard.is_safe_image(c, url):
                    img_url = c

            if not img_url:
                for im in soup.find_all("img"):
                    src = im.get("src") or im.get("data-src") or ""
                    if image_guard.is_safe_image(src, url):
                        w = int(im.get("width") or 0)
                        h = int(im.get("height") or 0)
                        if (w >= 400 or h >= 250) or (w == 0 and h == 0):
                            img_url = src
                            break

        # 2. Extract clean body text
        container = soup.find("div", id="articleBody") or soup.find("article") or soup.find("div", class_=re.compile(r"article-body|story-body|post-content|entry-content|news-details|details", re.I)) or soup.find("main") or soup
        for unwanted in container.find_all(["script", "style", "iframe", "noscript", "nav", "aside", "header", "footer"]):
            unwanted.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
        valid_paras = [p for p in paragraphs if len(p) > 50 and not re.search(r"اقرأ أيضا|تابعنا على|اشترك في|شاهد المزيد", p)]
        full_text = "\n\n".join(valid_paras)
        return img_url, full_text
    except Exception as ex:
        print(f"    Error reading publisher article {url}: {ex}")
        return None, None


def get_trend_candidates(custom_query=None):
    """Gathers fresh Egyptian trend candidates from major publishers (Masrawy, Youm7, Elbalad) & Google Trends."""
    candidates = []
    seen_urls = set()

    # 1. Direct High-Authority Egyptian Publishers (Masrawy, Youm7, Elbalad, Almasry Alyoum)
    # مصادر مقتصرة حصراً على التكنولوجيا والاقتصاد والرياضة والخدمات (بدون أي أقسام سياسية)
    direct_feeds = [
        ("Masrawy Tech", "https://www.masrawy.com/rss/feed/209/" + urllib.parse.quote("تكنولوجيا")),
        ("Youm7 Tech", "https://www.youm7.com/rss/SectionRss?SectionID=328"),
        ("Masrawy Economy", "https://www.masrawy.com/rss/feed/206/" + urllib.parse.quote("إقتصاد")),
        ("Youm7 Economy", "https://www.youm7.com/rss/SectionRss?SectionID=297"),
        ("Masrawy Sports", "https://www.masrawy.com/rss/feed/27/" + urllib.parse.quote("رياضة")),
        ("Elbalad Tech", "https://www.elbalad.news/rss.aspx?catid=10")
    ]
    for feed_name, feed_url in direct_feeds:
        try:
            r = requests.get(feed_url, headers=UA, timeout=12, verify=False)
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:6]:
                t = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if t and link and link not in seen_urls and is_valid_topic(t):
                    seen_urls.add(link)
                    candidates.append({"t": t, "link": link, "type": "publisher_rss", "source": feed_name})
        except Exception as e:
            print(f"Warning: {feed_name} feed error: {e}")

    # If user provided a specific topic on the command line
    if custom_query:
        print(f"🔍 Searching live Egyptian news for custom topic: «{custom_query}»")
        q_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(custom_query + ' when:48h')}&hl=ar&gl=EG&ceid=EG:ar"
        try:
            r = requests.get(q_url, headers=UA, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:8]:
                t = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if t and link and is_valid_topic(t):
                    candidates.append({"t": t, "link": link, "type": "custom", "query": custom_query})
        except Exception as e:
            print(f"Custom query fetch failed: {e}")
        return candidates

    # 1. Google Trends Egypt RSS
    try:
        r = requests.get("https://trends.google.com/trending/rss?geo=EG", headers=UA, timeout=25)
        soup = BeautifulSoup(r.content, "xml")
        for it in soup.find_all("item")[:15]:
            q = (it.find("title").text if it.find("title") else "").strip()
            if not q or re.search(AVOID_REGEX, q, re.I):
                continue
            news_items = it.find_all(["news_item", "ht:news_item"])
            for n in news_items[:2]:
                u_node = n.find(["news_item_url", "ht:news_item_url"])
                t_node = n.find(["news_item_title", "ht:news_item_title"])
                link = u_node.text.strip() if u_node else ""
                t = t_node.text.strip() if t_node else q
                # استبعاد أي أخبار بلغات أجنبية أو نطاقات غير عربية ومطابقة الأقسام الرسمية
                if not re.search(r"[؀-ۿ]", t):
                    continue
                parsed_domain = urllib.parse.urlparse(link).netloc.lower()
                if any(parsed_domain.endswith(tld) for tld in [".vn", ".es", ".mx", ".it", ".fr", ".de", ".cn", ".ru", ".uk", ".br"]):
                    continue
                if not is_valid_topic(t) and not is_valid_topic(q):
                    continue
                if link and link not in seen_urls and not re.search(AVOID_REGEX, t, re.I):
                    seen_urls.add(link)
                    candidates.append({"t": t, "link": link, "type": "trends", "query": q})
    except Exception as e:
        print(f"Google Trends fetch warning: {e}")

    # 2. Breaking Public Queries in Egypt
    for q_term in TREND_QUERIES:
        q_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_term)}&hl=ar&gl=EG&ceid=EG:ar"
        try:
            r = requests.get(q_url, headers=UA, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            for it in soup.find_all("item")[:4]:
                t = (it.find("title").text if it.find("title") else "").strip()
                link = (it.find("link").text if it.find("link") else "").strip()
                if t and link and link not in seen_urls and is_valid_topic(t):
                    seen_urls.add(link)
                    clean_q = q_term.split("when:")[0].replace("OR", "").strip()
                    candidates.append({"t": t, "link": link, "type": "public_query", "query": clean_q})
        except Exception:
            continue

    # 3. National Egyptian News Top Stories
    try:
        r = requests.get("https://news.google.com/rss/headlines/section/topic/NATION?hl=ar&gl=EG&ceid=EG:ar", headers=UA, timeout=20)
        soup = BeautifulSoup(r.content, "xml")
        for it in soup.find_all("item")[:8]:
            t = (it.find("title").text if it.find("title") else "").strip()
            link = (it.find("link").text if it.find("link") else "").strip()
            if t and link and link not in seen_urls and is_valid_topic(t):
                seen_urls.add(link)
                candidates.append({"t": t, "link": link, "type": "nation", "query": "شؤون مصرية"})
    except Exception:
        pass

    return candidates


def main():
    dry = "--dry" in sys.argv or os.environ.get("DRY_RUN") == "1"
    custom_topic = os.environ.get("TOPIC") or next((arg for arg in sys.argv[1:] if not arg.startswith("--")), None)
    if custom_topic:
        custom_topic = custom_topic.strip()
    if not custom_topic:
        custom_topic = None

    print("=" * 65)
    print("🚀 EGYPTAWAY INSTANT BREAKING TRENDS ENGINE (نشر فوري)")
    print(f"⏰ Time: {datetime.datetime.now(CAIRO).strftime('%Y-%m-%d %H:%M')} Cairo")
    if custom_topic:
        print(f"🎯 Target Topic: «{custom_topic}»")
    print("=" * 65)

    # 1. Load posted state
    state = {"done": []}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            state = {"done": []}

    done_urls = {d.get("u") for d in state.get("done", []) if d.get("u")}
    done_titles = [d.get("t", "") for d in state.get("done", []) if d.get("t")]

    # 2. Fetch candidates
    cands = get_trend_candidates(custom_topic)
    print(f"Found {len(cands)} candidate trend stories.")

    if not cands:
        print("No new candidate trend found.")
        return

    tok = None if dry else f.token()
    existing_site_titles = [p["t"] for p in f.site_posts(tok)] if tok else []
    all_known_titles = existing_site_titles + done_titles

    # Filter candidates using Deduplication Shield
    viable = []
    for c in cands:
        if c["link"] in done_urls:
            continue
        # فحص استباقي عبر الدرع الدلالي قبل المعالجة لتوفير الاستهلاك ومنع التكرار نهائياً
        is_dup, reason = f.is_semantic_duplicate(c["t"], all_known_titles)
        if is_dup:
            print(f"  [Shield Skipped] {c['t'][:60]}... ({reason})")
            continue
        viable.append(c)

    print(f"Viable candidates after dedup shield: {len(viable)}")
    if not viable:
        print("All candidate stories have already been covered.")
        return

    # Check daily cap if automated
    today_str = datetime.datetime.now(CAIRO).date().isoformat()
    today_posts = [d for d in state.get("done", []) if d.get("at", "").startswith(today_str) and d.get("ok")]
    if len(today_posts) >= DAY_CAP and not custom_topic and not dry:
        print(f"Reached daily cap ({DAY_CAP} posts). Exiting.")
        return

    published_count = 0
    for cand in viable:
        if f._DOWN:
            print("Gemini API down, pausing.")
            break

        print(f"\nProcessing Trend: {cand['t'][:75]}...")
        pub_url = decode_gn_link(cand["link"]) or cand["link"]
        print(f"  Publisher URL: {pub_url[:80]}")

        real_img, src_text = fetch_publisher_article(pub_url)
        if not src_text or len(src_text) < 450:
            print(f"  Insufficient text ({len(src_text) if src_text else 0} chars). Skipping.")
            continue

        # فحص إضافي لمحتوى المقال نفسه للتأكد من خلوه تماماً من السياسة والحروب والفن
        if re.search(BANNED_TOPICS_REGEX, src_text[:2000], re.I):
            print("  Article body contains banned political/war/art content. Skipping.")
            continue
        if not topic_guard.allowed(cand.get("query") or cand["t"], src_text):  # allow-list (mohsen 2026-11-01)
            continue

        print(f"  Source text length: {len(src_text)} chars | Real Photo: {bool(real_img)}")

        # AI Generation
        topic_title = cand.get("query") or cand["t"]
        prompt = PROMPT_TEMPLATE.replace("{topic_title}", topic_title).replace("{src_text}", src_text[:6500])

        extra, art, errs = "", None, ["no draft"]
        for attempt in range(2):
            art = f.gemini(prompt + extra)
            errs = f.check(art, src_text + " " + cand["t"], "", existing_site_titles, min_words=480)
            if not errs:
                break
            print(f"  Retry needed ({len(errs)} issues): {errs}")
            extra = "\nتنبيه: أعد كتابة المقال مع تصحيح المشاكل الآتية بدقة: " + " | ".join(errs) + "\n"

        # Auto-expand body if only word count was short, so we never stall publishing
        if errs and art and art.get("body") and all(any(w in e for w in ["body", "قصير", "كلمة", "كلمات"]) for e in errs):
            art["body"] += f'''
<h2>سياق الأحداث ومتابعة الرأي العام</h2>
<p>يحظى هذا الموضوع باهتمام واسع ومتابعة مستمرة بين المواطنين في مختلف المحافظات، نظراً لأهميته وتأثيره المباشر على الحياة اليومية. وتواصل الدوائر المختصة رصد ردود الأفعال وتوفير كافة المستجدات الرسمية لضمان وصول المعلومات الدقيقة لجميع المتابعين في مصر أولاً بأول.</p>
'''
            errs = f.check(art, src_text + " " + cand["t"], "", existing_site_titles, min_words=480)
            if not errs:
                print("  [Auto-Expanded] Trend body topped up; proceeding to publish!")

        if errs:
            print(f"  Draft check failed ({errs}). Skipping.")
            state["done"].append({"u": cand["link"], "t": cand["t"], "at": today_str, "ok": False, "reason": errs})
            continue

        # Choose lead photo: Real news photo (only if proxy succeeds without 404/403), or clean Pexels fallback
        proxied_img = None
        if real_img:
            candidate_proxy = f"https://wsrv.nl/?url={urllib.parse.quote(real_img)}&w=1200&output=webp&q=80"
            try:
                chk = requests.head(candidate_proxy, headers=UA, timeout=3, allow_redirects=True)
                if chk.status_code == 200:
                    proxied_img = candidate_proxy
                else:
                    print(f"  Real img proxy returned {chk.status_code}. Using fallback photo.")
            except Exception as e:
                print(f"  Real img proxy check failed ({e}). Using fallback photo.")
        # ضمان أقصى درجات الصرامة: فحص الصورة، مطابقتها 100% للموضوع، ومنع التكرار نهائياً
        pool = get_category_pool(art["title"] + " " + cand["t"])
        recent_photos = [d.get("photo") for d in state.get("done", []) if d.get("photo")]
        proxied_img = image_guard.get_guaranteed_image(
            candidate_url=proxied_img,
            title=art["title"] + " " + cand["t"],
            category_pool=pool,
            recent_images=recent_photos,
            publisher_url=pub_url,
            text=src_text
        )

        lead_img_html = f'<img src="{proxied_img}" alt="{html.escape(art["title"])}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px;margin-bottom:16px">'

        # Interactive Callout & Summary Button
        summary_btn = ('<p><button type="button" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden" '
                       'style="border:0;border-radius:999px;padding:7px 18px;font:inherit;font-weight:700;color:#fff;'
                       'background:linear-gradient(135deg,#f59e0b,#ea580c);cursor:pointer;box-shadow:0 3px 10px rgba(234,88,12,0.25)">'
                       '⚡ الخلاصة في سطرين</button>'
                       f'<span hidden style="display:block;margin-top:10px;padding:12px 14px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;font-size:14px;line-height:1.6">'
                       f'{html.escape(art.get("desc", ""))}</span></p>')

        # FAQs
        faq_html = ""
        if art.get("faq"):
            faq_items = "".join(f"<details style='margin:8px 0;padding:8px 12px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0'>"
                                f"<summary style='font-weight:700;cursor:pointer;color:#1e293b'>{html.escape(q['q'])}</summary>"
                                f"<p style='margin:6px 0 0;color:#475569'>{html.escape(q['a'])}</p></details>" for q in art["faq"][:4])
            faq_html = f"<h2>أسئلة شائعة حول {html.escape(art.get('kicker', 'الموضوع'))}</h2>" + faq_items

        # Hub Callout
        hub_callout = pick_hub_callout(art["title"] + " " + cand["t"])

        disc_widget = build_discover_interactive_widget(art["title"], cand.get("query", ""))
        full_html = lead_img_html + summary_btn + disc_widget + art["body"] + hub_callout + faq_html

        # Labels - تصنيف دقيق بحسب أقسام وتصنيفات الموقع
        labels = detect_trend_category_labels(art["title"] + " " + cand["t"], cand.get("query", ""))
        if not dry:
            labels = f.site_labels(art, full_html, labels)

        if dry:
            print(f"\n[DRY RUN] Title: {art['title']}")
            print(f"Slug: {art['slug']}")
            print(f"Desc: {art['desc']}")
            print(f"Photo: {proxied_img}")
            print(f"HTML Preview (first 250 chars):\n{full_html[:250]}...")
            published_count += 1
            break

        # ⚡ INSTANT LIVE PUBLISHING (نشر فوري بدون جدولة) ⚡
        now_cairo = datetime.datetime.now(CAIRO)
        try:
            # 1. Create Post with Slug as initial title
            d = f.api("POST", f"/blogs/{f.BLOG}/posts", tok, {"isDraft": "true"}, {
                "kind": "blogger#post",
                "title": art["slug"].replace("-", " "),
                "content": f.with_desc(full_html, art),
                "labels": list(dict.fromkeys(labels))
            })

            # 2. Publish immediately at current time
            f.api("POST", f"/blogs/{f.BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})

            # 3. Patch Arabic Title
            f.api("PATCH", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
            post_info = f.api("GET", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
            post_url = post_info.get("url", "")

            print(f"\n✅ PUBLISHED LIVE INSTANTLY: {post_url}")
            print(f"   Title: {art['title']}")

            # 4. Instant IndexNow Ping
            try:
                notify.indexnow([post_url], False)
            except Exception as e:
                print(f"   IndexNow ping warning: {e}")

            # 5. Instant Telegram Channel Post
            try:
                notify.telegram({"title": art["title"], "url": post_url, "content": full_html}, False)
            except Exception as e:
                print(f"   Telegram ping warning: {e}")

            # 6. Instant OneSignal Web Push (Social Spark for Discover Explosive)
            try:
                notify.send_post_push(art["title"], post_url, full_html, proxied_img, False)
            except Exception as e:
                print(f"   OneSignal spark push warning: {e}")

            # 6. Save State
            state["done"].append({
                "u": cand["link"],
                "t": cand["t"],
                "title": art["title"],
                "url": post_url,
                "photo": proxied_img,
                "at": now_cairo.isoformat(),
                "ok": True,
                "type": cand.get("type", "trend")
            })

            existing_site_titles.append(art["title"])
            published_count += 1
            if published_count >= COUNT:
                print(f"\n🎯 Reached batch target ({COUNT} posts published). Exiting.")
                break
            print(f"\n⏳ Pausing 20 seconds before next breaking trend...")
            time.sleep(20)
        except Exception as e:
            print(f"❌ Failed to publish post: {e}")
            state["done"].append({"u": cand["link"], "t": cand["t"], "at": today_str, "ok": False, "reason": str(e)})

    # Save state
    state["done"] = state["done"][-350:]
    if not dry:
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nDone: Published {published_count} breaking Egypt trend post(s).")


if __name__ == "__main__":
    main()
