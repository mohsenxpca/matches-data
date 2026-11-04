"""Egyptaway labels picked from the article itself (mohsen 2026-11-04).

The engines used to label posts with keyword regexes ("لاعب" or "نتيجة" made anything a football story, "تحديث" made
anything a phone story) and with labels that are no longer on the site ("العاب", "طقس", "شهادات البنوك"...). Now every
post gets exactly one of the site's 13 sections, chosen by Gemini Flash-Lite from the title and the opening text, plus
the menu labels the theme reads (اندرويد, الذكاء الاصطناعى, أخبار الكورة) when the article is about them.
The labels the engine passes are only a hint: they are used as the fallback when Gemini doesn't answer.
"""
import html
import re

import football as f

SECTIONS = {
    "هواتف": "موبايلات وتابلت وساعات وسماعات: إطلاق، تسريبات، مواصفات، أسعار، تحديثات One UI/iOS لهاتف معين",
    "ألعاب": "ألعاب فيديو موبايل/PC/كونسول: تحميل لعبة، أخبار استوديوهات، تحديثات لعبة، إعدادات لعبة",
    "تطبيقات": "تطبيق أو منصة معينة وميزاتها الجديدة: واتساب، فيسبوك، جيميل، كروم، تروكولر",
    "شروحات": "خطوات عملية: إزاي تعمل حاجة على الموبايل أو الكمبيوتر، حل مشكلة، أكواد، إعدادات",
    "شحن الألعاب": "شحن شدات/جواهر/UC/CP لعبة بالـ ID أو فودافون كاش، مواقع الشحن، أسعار الباقات",
    "الربح": "طرق كسب فلوس: الربح من الإنترنت، يوتيوب وتيك توك، ألعاب وتطبيقات بتكسب فلوس، العمل الحر",
    "رياضة": "كرة قدم ورياضة: مباريات، نتايج، مواعيد، لاعبين، مدربين، انتقالات، أندية، بطولات",
    "أخبار": "أخبار عامة: حوادث، أعطال الخدمات (واتساب/فيسبوك/الشبكات واقعة)، طقس دول تانية، أحداث",
    "تقنية": "تكنولوجيا عامة: ذكاء اصطناعي، أمن سيبراني واختراقات، كمبيوتر وويندوز، إنترنت، شركات التقنية",
    "خدمات": "خدمات للمواطن في مصر والخليج: الطقس والأرصاد، الصلاة، القطارات والمترو، الإسكان، البنزين، الكهرباء، "
              "التموين، المرتبات والمعاشات، الامتحانات والتعليم، الإجازات، تغيير الساعة، أرقام خدمة العملاء",
    "وظائف": "وظائف ومسابقات وتوظيف وتأشيرات عمل ورواتب مهن، السيرة الذاتية والمقابلات",
    "منوعات": "أي حاجة مش في الأقسام دي: ألغاز، سيارات، تسوق، لايف ستايل، قصص غريبة",
    "اقتصاد": "أي حاجة ليها علاقة بالأموال كأخبار وأرقام: الذهب والدولار والعملات، البنوك والشهادات والفائدة، "
              "البورصة والأسهم، الموازنة والضرائب والتضخم، أسعار الوقود عالميًا",
}

# Old labels the engines still pass -> the section they belong to (used when Gemini doesn't answer).
HINTS = {
    "العاب": "ألعاب", "أخبار الألعاب": "ألعاب", "عروض الألعاب": "ألعاب",
    "أخبار الكورة": "رياضة", "الدوري المصري": "رياضة", "دوري روشن": "رياضة", "مواعيد المباريات": "رياضة",
    "نتائج المباريات": "رياضة",
    "طقس": "خدمات", "توقيت": "خدمات", "تعليم": "خدمات", "قطارات": "خدمات", "تموين": "خدمات", "مرتبات": "خدمات",
    "إسكان": "خدمات", "أسعار البنزين": "خدمات", "تنسيق الكليات والمدارس": "خدمات", "فودافون كاش": "شروحات",
    "شهادات البنوك": "اقتصاد", "أسعار الذهب": "اقتصاد", "أسعار العملات": "اقتصاد", "أسعار الذهب والعملات": "اقتصاد",
    "وظائف وتأشيرات": "وظائف", "أعطال وتوقف الخدمات": "أخبار", "أسعار الموبايلات": "هواتف", "شؤون الخليج": "منوعات",
}

# Labels the theme reads: the top menu links to اندرويد and الذكاء الاصطناعى, and the matches page news box reads
# أخبار الكورة (theme/matches_news_block.html in blogger-pipeline).
ANDROID = re.compile(r"أندرويد|اندرويد|android", re.I)
AI = re.compile(r"ذكاء ا?ل?اصطناع|الذكاء الصناع|\bAI\b|ChatGPT|Gemini|جيميني|\bGPT|OpenAI|NotebookLM|Copilot|Claude", re.I)
NOT_FOOTBALL = re.compile(r"جمباز|سباحة|فورمولا|تنس|كرة السلة|كرة اليد|أولمبياد|ملاكمة|مصارعة")

PROMPT = """إنت محرر في موقع ايجبتاوى. اختار قسم واحد بس للمقال ده من الأقسام دي، حسب موضوعه الأساسي (مش حسب كلمة جت فيه):
{sections}

أمثلة: «إصابة لاعب بيراميدز» = رياضة. «ألعاب بتكسب فلوس فودافون كاش» = الربح. «شحن شدات ببجي» = شحن الألعاب.
«تحميل لعبة» = ألعاب. «البنك الأهلي يرفع عائد الشهادة» = اقتصاد. «عطل واتساب في مصر» = أخبار.
«إزاي تفعل ميزة في سامسونج» = شروحات. «تسريب مواصفات Galaxy» = هواتف. «حالة الطقس غدًا في مصر» = خدمات.

رجّع JSON بالشكل ده بس: {{"section": "..."}}

العنوان: {title}
النص: {text}
"""


def _text(html_out):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_out or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _from_hint(hint):
    for h in hint:
        if h in SECTIONS:
            return h
    for h in hint:
        if h in HINTS:
            return HINTS[h]
    return "أخبار"


def pick(title, html_out="", hint=()):
    """[section, + menu labels] for an Egyptaway post. hint = the labels the engine would have used."""
    if isinstance(hint, str):
        hint = [hint]
    hint = list(hint or [])
    text = _text(html_out)[:1500]
    section = None
    down = f._DOWN  # a failed label call shouldn't stop the engine's next article
    try:
        res = f.gemini(PROMPT.format(sections="\n".join(f"{k} = {v}" for k, v in SECTIONS.items()),
                                     title=title, text=text)) or {}
        section = str(res.get("section", "")).strip()
    except Exception as e:  # noqa: BLE001 — a failed label call must never stop a post
        print("  labeler: gemini failed:", type(e).__name__)
    f._DOWN = down
    if section not in SECTIONS:
        section = _from_hint(hint)
        print(f"  labeler: fallback -> {section}")
    labels = [section]
    head = title + " " + text[:600]
    if ANDROID.search(head):
        labels.append("اندرويد")
    if AI.search(head):
        labels.append("الذكاء الاصطناعى")
    if section == "رياضة" and not NOT_FOOTBALL.search(title):
        labels.append("أخبار الكورة")
    print(f"  labeler: {title[:60]} -> {' + '.join(labels)}")
    return labels
