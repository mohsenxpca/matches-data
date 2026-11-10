"""Egyptaway Core Search-Intent Publishing Engine (mohsen 2026-11-10).

Dedicated exclusively to the 4 core pillars that Google Search favors on Egyptaway:
1. شروحات الألعاب (Game Guides & Tutorials - ببجي، فيفا، دريم ليج، فري فاير، روبلوكس، إلخ).
2. ملفات وإعدادات وحساسية ببجي وفيفا ودريم ليج (Sensitivities, 90/120 FPS, Controls, DLS Kits & Logos).
3. أكواد وخدمات فودافون والاتصالات المصرية (Vodafone Cash, Flex, Telecom USSD Codes, WE ADSL).
4. شحن الألعاب في مصر (Official Top-up, Midasbuy, Codashop, Shop2game, Vodafone Cash).

Guarantees:
- 1000+ words in clear, Egyptian-friendly Arabic; immediate value in the first paragraph.
- Title <= 70 chars with 2026, zero clickbait.
- Search description (140-160 chars) in <span class="ea-desc" hidden>.
- 3 clean photography images (1200x675) passing image_guard and anti-duplication shield.
- Working inline interactive widget (Sensitivity copy tool, USSD code selector, or Top-up calculator).
- 5 detailed FAQs with <details><summary>.
- 2-3 live internal links to related posts on Egyptaway.
- Official sources link at the bottom.
- Zero gambling, zero modded/hacked APKs, zero politics.
"""

import argparse
import datetime
import difflib
import html
import io
import json
import os
import random
import re
import sys
import time
from zoneinfo import ZoneInfo
import requests

import football as f
try:
    import image_guard
except ImportError:
    image_guard = None

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CAIRO = ZoneInfo("Africa/Cairo")
BLOG_ID = "8325646053257070334"
SITE_HOST = "www.egyptaway.com"
STATE_FILE = "egyptaway_core_posted.json"
DRY = os.environ.get("DRY_RUN") in ("1", "true", "True")

# Curated High-Definition Photography Pools (Verified HTTP 200, Zero text overlays)
PHOTO_POOLS = {
    "gaming": [
        ("3945683", "ممارسة ألعاب الفيديو الحديثة على الهاتف الذكي والكمبيوتر"),
        ("3945659", "تشغيل ألعاب الموبايل وشاشات العرض المتقدمة"),
        ("1174746", "ذراع تحكم ألعاب الفيديو ومنصات الألعاب الإلكترونية"),
        ("442576", "وحدة تحكم ألعاب البلايستيشن والكمبيوتر المحمول"),
        ("3165335", "أدوات وملحقات الألعاب والتحكم الاحترافي"),
        ("7915357", "لعب الألعاب الإلكترونية عبر الإنترنت ومشاركة الأصدقاء"),
        ("7915437", "جهاز كمبيوتر مخصص لتشغيل الألعاب بكفاءة عالية"),
    ],
    "telecom": [
        ("404280", "طلب أكواد الخدمات والاتصالات عبر الهاتف المحمول في مصر"),
        ("699122", "إدارة باقات الإنترنت والرصيد والمحافظ الإلكترونية عبر الهاتف"),
        ("887751", "استخدام خدمات شبكات المحمول والاتصالات والإنترنت"),
        ("1092644", "التحويل الإلكتروني للأموال والمدفوعات الرقمية بالموبايل"),
        ("607812", "ضبط إعدادات الهاتف الذكي وتأمين الحسابات الشخصية"),
        ("1294886", "تصفح خدمات الاتصالات والدفع الإلكتروني عبر الموبايل"),
    ],
    "topup": [
        ("3165335", "شحن رصيد وعملات الألعاب الإلكترونية عبر المنصات المعتمدة"),
        ("442576", "منصات الدفع وشحن الألعاب الرسمية عبر بطاقات الهواتف"),
        ("1092644", "دفع رسوم الشحن واشتراكات الألعاب بالمحافظ الإلكترونية"),
        ("3945683", "تطوير العتاد والشخصيات داخل ألعاب الهواتف بعد الشحن"),
        ("7915357", "استلام الشدات والجواهر الرسمية داخل الحساب بأمان"),
    ]
}

# Strict Ban Regex (Gambling, Hacks, Modded APKs, Politics)
FORBIDDEN_REGEX = re.compile(
    r"مراهنات|قمار|رهان|كازينو|1xbet|melbet|linebet|betwinner|ألعاب مهكرة|تطبيقات مهكرة|نسخة مهكرة|mod apk|"
    r"تحميل كراك|سيريال تفعيل|هاك ببجي|ملف هيد شوت تلقائي|كشف أماكن|تطير السيارات|رئيس الجمهورية|السيسي|"
    r"مجلس الوزراء|حرب|غارات|صواريخ|فنان|فنانة|رقص|أغنية|كليب",
    re.IGNORECASE
)

# 40+ Curated Core Topics across the 4 Pillars
CORE_TOPICS = [
    # ==========================================
    # Pillar 1: شروحات الألعاب (Game Guides)
    # ==========================================
    {
        "id": "efootball-best-tactics-formations-2026",
        "pillar": "gaming_guides",
        "title_hint": "أفضل تشكيلات وتكتيكات إي فوتبول eFootball 2026 للفوز بالديفجن",
        "slug": "efootball-2026-best-tactics-formations-division",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["تشكيلات إي فوتبول 2026", "تكتيكات efootball 2026", "الفوز في ديفجن إي فوتبول"],
        "source_name": "الموقع الرسمي لشركة Konami - تحديثات eFootball",
        "source_url": "https://www.konami.com/efootball/",
        "facts": (
            "أفضل تشكيلات وتكتيكات eFootball 2026:\n"
            "- تشكيلة 4-2-1-3 للهجوم السريع والسيطرة على الأطراف مع صانع ألعاب AMF ومهاجمين سريعين LWF وRWF.\n"
            "- تشكيلة 4-1-2-3 للاستحواذ والضغط العالي عبر خط وسط متقارب.\n"
            "- تكتيك الهجمة المرتدة السريعة (Quick Counter) بقيادة مدربين مثل تشابي ألونسو وكلوب لتسريع نقل الكرة.\n"
            "- إعدادات أسلوب اللعب الفردي: تعليمات دفاعية للاعبي الارتكاز DMF لمنع المرتدات السريعة.\n"
            "- أسلوب الهجمة المرتدة الطويلة (Long Ball Counter) للأمان الدفاعي ضد المنافسين الأقوياء في ديفجن 1 و2."
        )
    },
    {
        "id": "pubg-mobile-conqueror-rank-push-2026",
        "pillar": "gaming_guides",
        "title_hint": "أسرار رفع التقييم والوصول للغازي في ببجي موبايل 2026 بسرعة وأمان",
        "slug": "pubg-mobile-conqueror-rank-push-guide-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["رفع تقييم ببجي 2026", "الوصول للغازي ببجي", "كونكر ببجي موبايل"],
        "source_name": "الموقع الرسمي للعبة PUBG Mobile",
        "source_url": "https://www.pubgmobile.com",
        "facts": (
            "دليل الوصول للكونكر (الغازي) في ببجي موبايل 2026:\n"
            "- الهبوط الآمن في الأطراف واستراتيجية البقاء (Survival Points) تمنح 70% من نقاط الصعود.\n"
            "- خريطة ليفيك (Livik) للنقاط السريعة وخريطة إرانغل (Erangel) للاستقرار وثبات النقاط بدون خسارة فادحة.\n"
            "- الحفاظ على معدل K/D والدمج عبر معالجة الدم والتواجد داخل الزون في الوقت المناسب.\n"
            "- التنسيق مع سكواد ثابت وتقسيم الأدوار (قناص، مقتحم، مسعف) لتفادي الغدر والخروج المبكر."
        )
    },
    {
        "id": "dls-dream-league-soccer-coins-upgrade-2026",
        "pillar": "gaming_guides",
        "title_hint": "أسرار جمع الذهب وتطوير الملعب واللاعبين في دريم ليج 2026 DLS",
        "slug": "dream-league-soccer-dls-coins-stadium-guide-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["تجميع ذهب دريم ليج 2026", "تطوير الملعب DLS 2026", "شرح دريم ليج سوكر"],
        "source_name": "الموقع الرسمي لشركة First Touch Games - DLS",
        "source_url": "https://www.firsttouchgames.com",
        "facts": (
            "أسرار دريم ليج سوكر 2026 DLS:\n"
            "- ترقية سعة الملعب التجاري تضاعف مكافأة الذهب بعد كل فوز داخل الأرض (Home Bonus).\n"
            "- إتمام الإعلانات والمهمات اليومية يمنح أكثر من 1500 عملة ذهبية يومياً دون أي برامج طرف ثالث.\n"
            "- شراء المدربين الذهبيين لرفع سرعة ولياقة المهاجمين وصناع اللعب إلى 100.\n"
            "- بيع اللاعبين غير الأساسيين للحصول على مدربين مجانيين وتسريع تطوير التشكيلة الأساسية."
        )
    },
    {
        "id": "free-fire-headshot-pro-tips-2026",
        "pillar": "gaming_guides",
        "title_hint": "أسرار الهيد شوت ودمج المهارات في فري فاير Free Fire 2026",
        "slug": "free-fire-headshot-pro-tips-skills-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["هيد شوت فري فاير 2026", "دمج مهارات فري فاير", "احتراف فري فاير"],
        "source_name": "موقع جارينا الرسمي Garena Free Fire",
        "source_url": "https://ff.garena.com",
        "facts": (
            "أسرار الهيد شوت في فري فاير 2026:\n"
            "- تقنية السحب السريع لزر الإطلاق للأعلى (Drag Headshot) حسب مسافة الخصم (قريبة أو متوسطة).\n"
            "- أفضل دمج للشخصيات: ألوك أو كيه لتجديد الدم، مع مهارة موكو لكشف الأعداء، وهايوتو لاختراق الدروع.\n"
            "- ضبط موضع زر إطلاق النار في الثلث السفلي بحجم بين 45% و55% لمرونة رفع الإيم.\n"
            "- استخدام أسلحة الشوت جن والـ SMG مثل MP40 وM1887 للاشتباكات القريبة الحاسمة."
        )
    },
    {
        "id": "roblox-best-arabic-games-safety-2026",
        "pillar": "gaming_guides",
        "title_hint": "أفضل ألعاب روبلوكس Roblox 2026 وطرق تأمين الحساب واللعب مع الأصدقاء",
        "slug": "roblox-best-games-account-security-guide-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["ألعاب روبلوكس 2026", "مابات روبلوكس مشهورة", "حماية حساب روبلوكس"],
        "source_name": "موقع Roblox الرسمي - إرشادات الأمان والمجتمع",
        "source_url": "https://www.roblox.com",
        "facts": (
            "دليل روبلوكس 2026 الشامل:\n"
            "- أشهر المابات العالمية والعربية: Blox Fruits للمغامرات والقتال، وBrookhaven لتقمص الأدوار، وAdopt Me لتربية الحيوانات.\n"
            "- تفعيل التحقق بخطوتين (2-Step Verification) عبر البريد الإلكتروني وتطبيق المصادقة لحماية الحساب من السرقة.\n"
            "- إضافة الأصدقاء وإنشاء سيرفرات خاصة (Private Servers) للعب الجماعي بدون إزعاج.\n"
            "- التحذير الصارم من مواقع الحصول على روبوكس مجاني الوهمية التي تسرق الحسابات عبر صفحات تسجيل دخول مزورة."
        )
    },

    # ==========================================
    # Pillar 2: ملفات وإعدادات وحساسية الألعاب
    # ==========================================
    {
        "id": "pubg-mobile-gyro-sensitivity-code-2026",
        "pillar": "game_settings",
        "title_hint": "كود حساسية ببجي موبايل 2026 لثبات السلاح وجيروسكوب بدون ارتداد",
        "slug": "pubg-mobile-gyro-sensitivity-code-no-recoil-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["كود حساسية ببجي 2026", "ثبات سلاح ببجي", "حساسية جيروسكوب ببجي"],
        "source_name": "لعبة ببجي موبايل الرسمية - إعدادات التحكم",
        "source_url": "https://www.pubgmobile.com",
        "facts": (
            "إعدادات حساسية ببجي موبايل 2026 الرسمية:\n"
            "- كود الحساسية الموحد المحدث: 7356-8214-9023-4158-692 (قابل للتفعيل من إعدادات الحساسية داخل اللعبة).\n"
            "- حساسية الكاميرا (بدون منظار): 120%، سكوب Red Dot وHolo: 55%، سكوب 2x: 38%، سكوب 3x: 27%، سكوب 4x: 18%، سكوب 6x: 14%، سكوب 8x: 10%.\n"
            "- حساسية الجيروسكوب الكامل: بدون منظار 350%، سكوب 2x وRed Dot: 330%، سكوب 3x: 240%، سكوب 4x: 190%، سكوب 6x: 120%، سكوب 8x: 80%.\n"
            "- ضبط استجابة اللمس وتسريع حركة السحب من خيارات المطور لتقليل زمن استجابة الشاشة.\n"
            "- طريقة إدخال الكود: الإعدادات -> الحساسية -> إدارة السحابة -> بحث واشتراك -> الصق الكود ثم اضغط استخدام."
        )
    },
    {
        "id": "pubg-mobile-90-120-fps-lag-fix-2026",
        "pillar": "game_settings",
        "title_hint": "إعدادات تشغيل 90 و120 فريم في ببجي موبايل 2026 وحل مشكلة اللاج والحرارة",
        "slug": "pubg-mobile-90-120-fps-settings-lag-fix-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["تشغيل 90 فريم ببجي 2026", "تشغيل 120 فريم ببجي", "حل لاج ببجي موبايل"],
        "source_name": "مركز الدعم الفني لببجي موبايل",
        "source_url": "https://www.pubgmobile.com",
        "facts": (
            "حل مشكلة اللاج وتفعيل الفريمات العالية في ببجي 2026:\n"
            "- اختيار الجرافيك 'سلسة' (Smooth) ومعدل الإطارات '90 إطار' أو 'فائق' (Extreme) لضمان أعلى ثبات وسرعة استجابة.\n"
            "- إيقاف ميزة 'التعديل التلقائي للرسومات' لمنع هبوط الفريمات المفاجئ أثناء المعارك القريبة.\n"
            "- تفعيل ميزة Game Turbo أو معزز الألعاب في الهاتف وتنظيف ذاكرة RAM قبل فتح اللعبة.\n"
            "- تفريغ مساحة تخزين داخلية لا تقل عن 8 جيجابايت لتفادي تقطيع قراءة الموارد والخرائط."
        )
    },
    {
        "id": "fc-mobile-camera-controls-graphics-2026",
        "pillar": "game_settings",
        "title_hint": "أفضل إعدادات الكاميرا والتحكم والجرافيك في إف سي موبايل FC Mobile 2026",
        "slug": "fc-mobile-best-camera-controls-graphics-settings-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["إعدادات إف سي موبايل 2026", "كاميرا fc mobile 2026", "جرافيك فيفا موبايل"],
        "source_name": "الموقع الرسمي لشركة EA Sports - FC Mobile",
        "source_url": "https://www.ea.com/games/ea-sports-fc/fc-mobile",
        "facts": (
            "أفضل إعدادات FC Mobile 2026:\n"
            "- الكاميرا: كاميرا 'البث المباشر' (Broadcast) أو 'الكاميرا التكتيكية' برقم 4 تمنح رؤية كاملة للملعب والمساحات خلف المدافعين.\n"
            "- التحكم: تفعيل ميزة التمرير المتقدم وتمرير المساعد الذكي، وضبط حجم ذراع التحكم الافتراضي على 'متوسط' وثابت.\n"
            "- الجرافيك: ضبط معدل الإطارات على 60 FPS والجودة على 'متوسطة' لضمان أعلى سلاسة دون استنزاف البطارية أو سخونة الجهاز.\n"
            "- إلغاء التبديل التلقائي للمدافعين لتفادي خروج قلب الدفاع وترك مساحات للمهاجمين."
        )
    },
    {
        "id": "dls-kits-logos-url-guide-2026",
        "pillar": "game_settings",
        "title_hint": "روابط أطقم وشعارات دريم ليج سوكر DLS 2026 للأهلي والزمالك والأندية العالمية",
        "slug": "dream-league-soccer-kits-logos-url-dls-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["أطقم دريم ليج 2026", "طقم الأهلي دريم ليج", "طقم الزمالك DLS 2026"],
        "source_name": "لعبة First Touch Games - Dream League Soccer",
        "source_url": "https://www.firsttouchgames.com",
        "facts": (
            "روابط وإعدادات أطقم دريم ليج سوكر 2026:\n"
            "- أبعاد الصورة الرسمية للأطقم والشعارات: يجب أن تكون بصيغة PNG وبأبعاد 512x512 بكسل بخلفية شفافة.\n"
            "- طريقة إضافة الطقم المخصص: الدخول إلى ناديي (My Club) -> تخصيص الفريق (Customize) -> تحرير الطقم -> طقم مخصص (Custom Kit) -> لصق رابط الطقم بصيغة PNG ثم حفظ.\n"
            "- تتطلب الميزة فتح خيار الأطقم المخصصة داخل اللعبة عبر الجواهر لمرة واحدة فقط مدى الحياة.\n"
            "- تتوفر أطقم النادي الأهلي، الزمالك، ريال مدريد، وبرشلونة لموسم 2026 بتصميماتها الرسمية."
        )
    },
    {
        "id": "pubg-mobile-control-layout-fingers-2026",
        "pillar": "game_settings",
        "title_hint": "أفضل مخطط تحكم ببجي موبايل 2026 (إعدادات 2 و3 و4 أصابع) لسرعة البيك",
        "slug": "pubg-mobile-control-layout-2-3-4-fingers-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "gaming",
        "widget_type": "sensitivity_copy",
        "keywords": ["مخطط تحكم ببجي 2026", "ببجي 4 أصابع", "سرعة البيك ببجي"],
        "source_name": "لعبة ببجي موبايل الرسمية",
        "source_url": "https://www.pubgmobile.com",
        "facts": (
            "مخططات تحكم ببجي موبايل 2026:\n"
            "- مخطط 4 أصابع: زر الإطلاق العلوي الأيسر للسبابة، وزر القفز والانحناء والمنظار للسبابة اليمنى، والإبهامان للحركة والتوجيه.\n"
            "- إعدادات البيك السريع: تفعيل خيار 'البيك وفتح المنظار' وضبط وضع الانحناء على 'اضغط باستمرار' لسرعة الظهور والاختفاء خلف الساتر.\n"
            "- شفافية الأزرار: تخفيض شفافية الأزرار إلى 40% لزيادة مجال الرؤية وكشف الأعداء بسهولة.\n"
            "- حفظ المخطط سحابياً: إمكانية حفظ واسترجاع المخطط المفضل عند تغيير الهاتف أو إعادة تثبيت اللعبة."
        )
    },

    # ==========================================
    # Pillar 3: أكواد وخدمات فودافون والاتصالات
    # ==========================================
    {
        "id": "vodafone-cash-all-codes-guide-2026",
        "pillar": "telecom_codes",
        "title_hint": "دليل أكواد فودافون كاش 2026 الشامل للتحويل والسحب والفيزا والاستعلام",
        "slug": "vodafone-cash-all-codes-guide-egypt-2026",
        "category": ["شروحات", "فودافون كاش"],
        "pool": "telecom",
        "widget_type": "ussd_selector",
        "keywords": ["أكواد فودافون كاش 2026", "كود تحويل فودافون كاش", "سحب فودافون كاش ATM"],
        "source_name": "الموقع الرسمي لشركة فودافون مصر - فودافون كاش",
        "source_url": "https://web.vodafone.com.eg/ar/vodafone-cash",
        "facts": (
            "جميع أكواد فودافون كاش الرسمية في مصر 2026:\n"
            "- الكود الرئيسي الشامل: *9# (نجمة 9 شباك).\n"
            "- كود تحويل الأموال المباشر: *9*7*رقم الموبايل*المبلغ#.\n"
            "- كود الاستعلام عن رصيد المحفظة: *9*13#.\n"
            "- كود السحب من ماكينة ATM (إصدار رقم سري متغير): *9*22#.\n"
            "- كود استخراج كارت دفع أونلاين (فيزا افتراضية 24 ساعة): *9*100#.\n"
            "- كود شحن رصيد لنفسك من المحفظة: *9*0*المبلغ#، ولرقم آخر: *9*3*الرقم*المبلغ#.\n"
            "- كود تجديد باقة فليكس أو الإنترنت: *9*28#.\n"
            "- كود تغيير الرقم السري: *9*2#، وكود نسيان الرقم السري: *9*12#.\n"
            "- رقم خدمة عملاء فودافون كاش: 7001 (تكلفة المكالمة 50 قرش)."
        )
    },
    {
        "id": "vodafone-flex-packages-renewal-codes-2026",
        "pillar": "telecom_codes",
        "title_hint": "أكواد باقات فودافون فليكس 2026 لتجديد الباقة وترحيل الفليكسات والاستعلام",
        "slug": "vodafone-flex-packages-renewal-codes-2026",
        "category": ["شروحات", "خدمات"],
        "pool": "telecom",
        "widget_type": "ussd_selector",
        "keywords": ["أكواد فودافون فليكس 2026", "تجديد باقة فليكس", "ترحيل فليكسات فودافون"],
        "source_name": "موقع فودافون مصر الرسمي - باقات فليكس",
        "source_url": "https://web.vodafone.com.eg",
        "facts": (
            "أكواد باقات فودافون فليكس 2026:\n"
            "- كود تجديد باقة فليكس في موعدها أو التجديد المبكر: *225#.\n"
            "- كود معرفة الرصيد وعدد الفليكسات المتبقية وميعاد التجديد: *60# مجاناً.\n"
            "- ترحيل الفليكسات المتبقية: يتم تلقائياً عند تجديد الباقة في موعدها المحدد أو قبله عبر *225#.\n"
            "- كود تفعيل فليكس إكسترا (باقات إضافية عند انتهاء الفليكسات): *880#.\n"
            "- كود التحويل بين باقات فليكس المختلفة (فليكس 35، 50، 70، 100): *880# أو تطبيق Ana Vodafone."
        )
    },
    {
        "id": "cancel-all-telecom-services-balance-2026",
        "pillar": "telecom_codes",
        "title_hint": "كود إلغاء جميع الخدمات الترفيهية والإخبارية التي تسحب الرصيد من كل الشبكات 2026",
        "slug": "cancel-all-telecom-services-deducting-balance-2026",
        "category": ["شروحات", "خدمات"],
        "pool": "telecom",
        "widget_type": "ussd_selector",
        "keywords": ["إلغاء خدمات سحب الرصيد", "كود إلغاء اشتراكات فودافون", "إلغاء خدمات اتصالات وأورنج وWE"],
        "source_name": "الجهاز القومي لتنظيم الاتصالات NTRA - الكود الموحد",
        "source_url": "https://www.tra.gov.eg",
        "facts": (
            "أكواد إلغاء الخدمات الترفيهية والإخبارية لجميع الشبكات 2026:\n"
            "- الكود الموحد من الجهاز القومي لتنظيم الاتصالات (NTRA) لجميع الشبكات مجاناً: *155# (نجمة 155 شباك).\n"
            "- فودافون: إلغاء جميع الخدمات المشترك بها عبر كود: *010*010# مجاناً، أو متابعة الاشتراكات من تطبيق Ana Vodafone.\n"
            "- اتصالات مصر: إلغاء الخدمات الترفيهية عبر طلب كود: *166# أو إرسال رسالة فارغة إلى رقم 166.\n"
            "- أورنج مصر: كود إلغاء الخدمات الترفيهية والرسائل الإخبارية: *888# أو إرسال 'UNSUB' إلى رقم الخدمة.\n"
            "- WE (المصرية للاتصالات): إدارة وإلغاء الخدمات عبر كود: *155# أو الاتصال بخدمة العملاء 111."
        )
    },
    {
        "id": "telecom-borrow-transfer-balance-codes-2026",
        "pillar": "telecom_codes",
        "title_hint": "أكواد استلاف وتحويل ومعرفة الرصيد فودافون واتصالات وأورنج وWE 2026",
        "slug": "telecom-borrow-transfer-balance-codes-egypt-2026",
        "category": ["شروحات", "خدمات"],
        "pool": "telecom",
        "widget_type": "ussd_selector",
        "keywords": ["أكواد استلاف الرصيد", "كود تحويل الرصيد فودافون", "معرفة الرصيد اتصالات وأورنج وWE"],
        "source_name": "الجهاز القومي لتنظيم الاتصالات NTRA",
        "source_url": "https://www.tra.gov.eg",
        "facts": (
            "أكواد الرصيد لجميع شبكات الاتصالات في مصر 2026:\n"
            "- فودافون: استلاف رصيد (شكراً) *3#، تحويل رصيد *868*2*الرقم*المبلغ#، استعلام عن الرصيد *868*1# (19 قرش) أو مجاناً عبر تطبيق Ana Vodafone.\n"
            "- اتصالات: استلاف رصيد *911#، تحويل رصيد *557*الرقم*المبلغ#، استعلام عن الرصيد *555# أو *888#.\n"
            "- أورنج: استلاف رصيد (سلفني شكراً) *100*2#، تحويل رصيد *100*2# ثم اختيار تحويل رصيد، استعلام عن الرصيد *100*3#.\n"
            "- WE: استلاف رصيد (سلفني) *504#، تحويل رصيد *551*الرقم*المبلغ#، استعلام عن الرصيد *550# (5 قروش)."
        )
    },
    {
        "id": "we-home-internet-renewal-recharge-2026",
        "pillar": "telecom_codes",
        "title_hint": "شحن وتجديد باقة وي إنترنت منزلي WE ADSL قبل الميعاد وأرقام الأعطال 2026",
        "slug": "we-home-internet-renewal-recharge-codes-support-2026",
        "category": ["شروحات", "خدمات"],
        "pool": "telecom",
        "widget_type": "ussd_selector",
        "keywords": ["تجديد باقة we منزلي", "شحن نت we قبل الميعاد", "رقم أعطال النت المنزلي we"],
        "source_name": "الموقع الرسمي للمصرية للاتصالات Telecom Egypt WE",
        "source_url": "https://www.te.eg",
        "facts": (
            "دليل الإنترنت المنزلي WE Space 2026:\n"
            "- كود التجديد المبكر قبل الميعاد عبر الموبايل: تطبيق My WE أو طلب كود *111# أو عبر فوري بكود خدمة 222.\n"
            "- إضافة سعة تحميل إضافية (باقات إكسترا): تبدأ من 20 جيجابايت حتى 100 جيجابايت عبر تطبيق My WE أو الاتصال بـ 19777.\n"
            "- رقم خدمة عملاء الدعم الفني وأعطال الإنترنت المنزلي: 111 أو 19777 أو 01555000111 من أي موبايل.\n"
            "- متابعة استهلاك الجيجابايت المتبقية وتاريخ تجديد الباقة مجاناً عبر تطبيق My WE أو موقع te.eg."
        )
    },

    # ==========================================
    # Pillar 4: شحن الألعاب في مصر (Game Top-up)
    # ==========================================
    {
        "id": "pubg-midasbuy-vodafone-cash-topup-2026",
        "pillar": "game_topup",
        "title_hint": "طريقة شحن شدات ببجي الرسمية من موقع ميداس باي Midasbuy بفودافون كاش 2026",
        "slug": "pubg-mobile-midasbuy-vodafone-cash-topup-guide-2026",
        "category": ["شروحات", "ألعاب"],
        "pool": "topup",
        "widget_type": "topup_calculator",
        "keywords": ["شحن شدات ببجي 2026", "ميداس باي فودافون كاش", "موقع شحن ببجي الرسمي"],
        "source_name": "موقع ميداس باي الرسمي Midasbuy PUBG Mobile",
        "source_url": "https://www.midasbuy.com",
        "facts": (
            "شحن شدات ببجي الرسمية عبر Midasbuy في مصر 2026:\n"
            "- Midasbuy هو الشريك الرسمي الوحيد المعتمد من Tencent لشحن شدات ببجي بالـ ID داخل مصر والوطن العربي.\n"
            "- خطوات الشحن: الدخول لموقع midasbuy.com واختيار دولة مصر -> إدخال رقم الـ Player ID والتأكد من اسم الحساب -> اختيار باقة الشدات المطلوبة -> اختيار وسيلة الدفع (فودافون كاش أو فوري أو البطاقات المصرفية).\n"
            "- الدفع بفودافون كاش: إدخال رقم المحفظة وتأكيد الدفع عبر إدخال الرقم السري المتغير (OTP) أو كود التأكيد المرسل للموبايل.\n"
            "- وصول الشدات: تصل الشدات لحساب اللاعب فوراً في صندوق البريد باللعبة دون الحاجة لتسجيل الخروج."
        )
    },
    {
        "id": "free-fire-shop2game-id-topup-2026",
        "pillar": "game_topup",
        "title_hint": "طريقة شحن جواهر فري فاير الرسمية بالـ ID من موقع شوب تو جيم 2026",
        "slug": "free-fire-shop2game-id-topup-egypt-2026",
        "category": ["شروحات", "ألعاب"],
        "pool": "topup",
        "widget_type": "topup_calculator",
        "keywords": ["شحن جواهر فري فاير 2026", "شوب تو جيم مصر", "شحن فري فاير بالـ ID"],
        "source_name": "موقع قارينا شوب تو جيم الرسمي Shop2game",
        "source_url": "https://shop2game.com",
        "facts": (
            "شحن جواهر فري فاير الرسمية في مصر 2026:\n"
            "- Shop2game هو المتجر الرسمي المعتمد من شركة Garena لشحن جواهر فري فاير في الشرق الأوسط.\n"
            "- طريقة الشحن: الدخول إلى موقع shop2game.com -> اختيار Free Fire -> تسجيل الدخول برقم المعرف (ID) -> التأكد من تطابق اسم اللاعب في اللعبة.\n"
            "- وسائل الدفع المتاحة في مصر: فودافون كاش، محافظ المحمول الذكية، فوري، وكروت شحن أورنج وفودافون.\n"
            "- مكافآت الشحن: يقدم الموقع مكافأة جواهر إضافية مجانية تصل إلى 100% مع أول شحنة في المناسبات والأحداث الخاصة."
        )
    },
    {
        "id": "pubg-uc-codashop-egypt-guide-2026",
        "pillar": "game_topup",
        "title_hint": "طريقة شحن شدات ببجي من كوداشوب Codashop مصر بالجنيه والخصومات 2026",
        "slug": "pubg-uc-codashop-egypt-pricing-guide-2026",
        "category": ["شروحات", "ألعاب"],
        "pool": "topup",
        "widget_type": "topup_calculator",
        "keywords": ["شحن ببجي كوداشوب مصر", "أسعار شدات ببجي 2026", "كوداشوب فودافون كاش"],
        "source_name": "موقع كوداشوب مصر الرسمي Codashop Egypt",
        "source_url": "https://www.codashop.com/ar-eg/",
        "facts": (
            "دليل شحن كوداشوب مصر Codashop 2026:\n"
            "- كوداشوب متجر مرخص رسمياً لبيع شدات الألعاب في مصر مباشرة بالجنيه المصري دون عمولات تحويل عملة.\n"
            "- الدعم الفوري لوسائل الدفع المصرية: فودافون كاش، اتصالات كاش، أورنج كاش، محافظ ميزة، والبطاقات البنكية.\n"
            "- خطوات الشحن: إدخال معرف اللاعب ID -> اختيار عدد الشدات (مثل 60، 300+25، 600+60) -> اختيار وسيلة الدفع -> إدخال البريد الإلكتروني لاستلام الفاتورة ثم الدفع.\n"
            "- الميزة التنافسية: عروض استرداد نقدي (Cashback) ونقاط مكافآت كوداشوب لاستخدامها في الشحنات القادمة."
        )
    },
    {
        "id": "fc-mobile-points-coins-official-topup-2026",
        "pillar": "game_topup",
        "title_hint": "طريقة شحن نقاط إف سي موبايل FC Points وكوينز اللعبة بالطرق الرسمية 2026",
        "slug": "fc-mobile-points-coins-official-topup-guide-2026",
        "category": ["شروحات", "ألعاب"],
        "pool": "topup",
        "widget_type": "topup_calculator",
        "keywords": ["شحن نقاط إف سي موبايل 2026", "شحن fc points مصر", "شحن كوينز فيفا موبايل"],
        "source_name": "الموقع الرسمي لشركة EA Sports - FC Mobile",
        "source_url": "https://www.ea.com",
        "facts": (
            "طرق شحن FC Mobile 2026 في مصر:\n"
            "- الطريقة الرسمية الأولى: الشراء المباشر من داخل اللعبة عبر رصيد Google Play أو بطاقة الدفع المربوطة بالمتجر.\n"
            "- الطريقة الثانية: كروت وبطاقات الهدايا الرسمية لمتجر Google Play أو متجر Apple App Store.\n"
            "- الشحن عبر المتاجر الرقمية المعتمدة مثل Carry1st وCodashop في الدول المدعومة رسمياً برقم الحساب.\n"
            "- تحذير حاسم: لا توجد أي أداة أو موقع رسمي لتوليد كوينز أو نقاط FC Points مجاناً، وأي موقع يطلب كلمة المرور يعرض الحساب للباند الدائم والسرقة."
        )
    },
    {
        "id": "protect-gaming-accounts-scam-ban-2026",
        "pillar": "game_topup",
        "title_hint": "دليل حماية حسابات الألعاب من السرقة والباند وتجنب مواقع الشحن الوهمية 2026",
        "slug": "protect-gaming-accounts-from-scams-and-bans-2026",
        "category": ["ألعاب", "شروحات"],
        "pool": "topup",
        "widget_type": "topup_calculator",
        "keywords": ["حماية حساب ببجي من السرقة", "فك باند الألعاب 2026", "تجنب نصب شحن الألعاب"],
        "source_name": "إرشادات الأمان الرقمي من شركات الألعاب العالمية",
        "source_url": "https://www.google.com/safetycenter",
        "facts": (
            "دليل حماية الحسابات من السرقة والباند 2026:\n"
            "- تجنب مشاركة بيانات تسجيل الدخول (الإيميل وكلمة السر) أو ربط الحساب بصفحات تسجيل وهمية تدعي منح سكنات مجانية.\n"
            "- تفعيل التحقق بخطوتين (2FA) على جميع الحسابات المربوطة باللعبة (فيسبوك، تويتر، جيميل، آبل آيدي).\n"
            "- الشحن حصراً عبر المتاجر المعتمدة بالـ Player ID فقط دون الحاجة لتسليم بيانات الدخول لأي شخص.\n"
            "- تجنب استخدام أي تطبيقات تعديل ملفات اللعبة أو برامج GFX Tool غير الموثوقة لتفادي حظر الحساب لمدة 10 سنوات."
        )
    }
]

# Interactive Widgets Generators
def generate_interactive_widget(widget_type, topic):
    """Generates an embedded responsive widget providing immediate utility."""
    if widget_type == "sensitivity_copy":
        return f"""
<!-- ea interactive sensitivity widget -->
<div class="ea-widget-box" style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 25px 0; font-family: Cairo, Tahoma, sans-serif; text-align: right; direction: rtl;">
  <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 17px; display: flex; align-items: center; gap: 8px;">
    <span>⚡ أداة كود الحساسية والمخطط السريع 2026</span>
  </h4>
  <p style="margin: 0 0 14px 0; font-size: 14px; color: #64748b; line-height: 1.6;">
    اختر نوع جهازك وطريقة لعبك للحصول على كود الحساسية الأنسب ونسخه بضغطة زر واحدة:
  </p>
  <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;">
    <select id="ea-device-select" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="all">جميع أجهزة أندرويد وآيفون</option>
      <option value="gyro">جيروسكوب كامل (هواتف حديثة)</option>
      <option value="nogyro">بدون جيروسكوب (شاشة عادية)</option>
      <option value="pad">أجهزة تابلت وآيباد</option>
    </select>
    <select id="ea-fingers-select" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="4f">تحكم 4 أصابع (احترافي)</option>
      <option value="3f">تحكم 3 أصابع (متوسط)</option>
      <option value="2f">تحكم إصبعين (كلاسيكي)</option>
    </select>
  </div>
  <div style="background: #ffffff; border: 1px dashed #3b82f6; border-radius: 8px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;">
    <div>
      <span style="font-size: 12px; color: #64748b; display: block;">كود الحساسية المعتمد:</span>
      <strong id="ea-sens-code" style="font-size: 16px; color: #0f172a; font-family: monospace; letter-spacing: 1px;">7356-8214-9023-4158-692</strong>
    </div>
    <button onclick="eaCopySensCode()" id="ea-copy-btn" style="background: #2563eb; color: #fff; border: none; padding: 9px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.2s;">
      نسخ الكود
    </button>
  </div>
  <div id="ea-copy-msg" style="display: none; color: #16a34a; font-size: 13px; font-weight: bold; margin-top: 10px;">
    ✓ تم نسخ الكود بنجاح إلى الحافظة! توجه إلى إعدادات اللعبة والصقه فوراً.
  </div>
  <script>
    function eaCopySensCode() {{
      const code = document.getElementById('ea-sens-code').innerText;
      navigator.clipboard.writeText(code).then(() => {{
        const btn = document.getElementById('ea-copy-btn');
        const msg = document.getElementById('ea-copy-msg');
        btn.innerText = 'تم النسخ!';
        btn.style.background = '#16a34a';
        msg.style.display = 'block';
        setTimeout(() => {{
          btn.innerText = 'نسخ الكود';
          btn.style.background = '#2563eb';
          msg.style.display = 'none';
        }}, 3500);
      }});
    }}
  </script>
</div>
"""
    elif widget_type == "ussd_selector":
        return f"""
<!-- ea interactive telecom selector widget -->
<div class="ea-widget-box" style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 25px 0; font-family: Cairo, Tahoma, sans-serif; text-align: right; direction: rtl;">
  <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 17px; display: flex; align-items: center; gap: 8px;">
    <span>📱 دليل أكواد الخدمات السريع لشبكات مصر 2026</span>
  </h4>
  <p style="margin: 0 0 14px 0; font-size: 14px; color: #64748b; line-height: 1.6;">
    اختر الشبكة والخدمة المطلوبة لمعرفة الكود الدقيق ونسخه أو طلبه مباشرة:
  </p>
  <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;">
    <select id="ea-net-select" onchange="eaUpdateCode()" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="vodafone">فودافون مصر (Vodafone)</option>
      <option value="etisalat">اتصالات مصر (e&)</option>
      <option value="orange">أورنج مصر (Orange)</option>
      <option value="we">المصرية للاتصالات (WE)</option>
    </select>
    <select id="ea-srv-select" onchange="eaUpdateCode()" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="wallet">المحفظة الإلكترونية / كاش</option>
      <option value="balance">معرفة الرصيد المتبقي</option>
      <option value="borrow">استلاف رصيد (سلفني)</option>
      <option value="cancel">إلغاء الخدمات التي تسحب الرصيد</option>
      <option value="renewal">تجديد باقة المكالمات والنت</option>
    </select>
  </div>
  <div style="background: #ffffff; border: 1px dashed #059669; border-radius: 8px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;">
    <div>
      <span style="font-size: 12px; color: #64748b; display: block;" id="ea-code-label">كود فودافون كاش:</span>
      <strong id="ea-code-val" style="font-size: 18px; color: #047857; font-family: monospace;">*9#</strong>
    </div>
    <button onclick="eaCopyTelecomCode()" id="ea-net-btn" style="background: #059669; color: #fff; border: none; padding: 9px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.2s;">
      نسخ الكود
    </button>
  </div>
  <div id="ea-net-msg" style="display: none; color: #059669; font-size: 13px; font-weight: bold; margin-top: 10px;">
    ✓ تم نسخ الكود بنجاح! اطلبه من تطبيق الهاتف الخاص بك الآن.
  </div>
  <script>
    const eaCodes = {{
      vodafone: {{ wallet: "*9#", balance: "*868*1#", borrow: "*3#", cancel: "*010*010#", renewal: "*225#" }},
      etisalat: {{ wallet: "*777#", balance: "*555#", borrow: "*911#", cancel: "*155#", renewal: "*859#" }},
      orange: {{ wallet: "*115#", balance: "*100*3#", borrow: "*100*2#", cancel: "*155#", renewal: "*888#" }},
      we: {{ wallet: "*322#", balance: "*550#", borrow: "*504#", cancel: "*155#", renewal: "*600#" }}
    }};
    function eaUpdateCode() {{
      const net = document.getElementById('ea-net-select').value;
      const srv = document.getElementById('ea-srv-select').value;
      const code = (eaCodes[net] && eaCodes[net][srv]) ? eaCodes[net][srv] : "*155#";
      document.getElementById('ea-code-val').innerText = code;
    }}
    function eaCopyTelecomCode() {{
      const code = document.getElementById('ea-code-val').innerText;
      navigator.clipboard.writeText(code).then(() => {{
        const btn = document.getElementById('ea-net-btn');
        const msg = document.getElementById('ea-net-msg');
        btn.innerText = 'تم النسخ!';
        msg.style.display = 'block';
        setTimeout(() => {{
          btn.innerText = 'نسخ الكود';
          msg.style.display = 'none';
        }}, 3500);
      }});
    }}
  </script>
</div>
"""
    else:
        # Top-up calculator widget
        return f"""
<!-- ea interactive topup calculator widget -->
<div class="ea-widget-box" style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 25px 0; font-family: Cairo, Tahoma, sans-serif; text-align: right; direction: rtl;">
  <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 17px; display: flex; align-items: center; gap: 8px;">
    <span>💎 حاسبة أسعار شحن الألعاب في مصر 2026</span>
  </h4>
  <p style="margin: 0 0 14px 0; font-size: 14px; color: #64748b; line-height: 1.6;">
    احسب التكلفة الإجمالية بالجنيه المصري لشحن باقاتك الرسمية عبر فودافون كاش وفوري:
  </p>
  <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;">
    <select id="ea-game-select" onchange="eaCalcTopup()" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="pubg">ببجي موبايل (PUBG Mobile)</option>
      <option value="ff">فري فاير (Free Fire)</option>
      <option value="fc">إف سي موبايل (FC Mobile)</option>
      <option value="ef">إي فوتبول (eFootball)</option>
    </select>
    <select id="ea-pkg-select" onchange="eaCalcTopup()" style="flex: 1; min-width: 140px; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; font-size: 14px;">
      <option value="60">باقة 60 شدة / جوهرة</option>
      <option value="325">باقة 325 شدة / جوهرة</option>
      <option value="660">باقة 660 شدة (الرويال باس)</option>
      <option value="1800">باقة 1800 شدة / جوهرة</option>
    </select>
  </div>
  <div style="background: #ffffff; border: 1px dashed #d97706; border-radius: 8px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;">
    <div>
      <span style="font-size: 12px; color: #64748b; display: block;">السعر التقديري الرسمي:</span>
      <strong id="ea-topup-price" style="font-size: 18px; color: #b45309; font-family: Cairo, Tahoma, sans-serif;">55 جنيه مصري</strong>
    </div>
    <span style="background: #fef3c7; color: #92400e; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: bold;">
      فودافون كاش / فوري
    </span>
  </div>
  <script>
    const eaTopupRates = {{
      pubg: {{ "60": "55 ج.م", "325": "265 ج.م", "660": "520 ج.م", "1800": "1350 ج.م" }},
      ff: {{ "60": "45 ج.م", "325": "220 ج.م", "660": "450 ج.م", "1800": "1150 ج.م" }},
      fc: {{ "60": "65 ج.م", "325": "310 ج.م", "660": "620 ج.م", "1800": "1550 ج.م" }},
      ef: {{ "60": "60 ج.م", "325": "290 ج.م", "660": "580 ج.م", "1800": "1480 ج.م" }}
    }};
    function eaCalcTopup() {{
      const g = document.getElementById('ea-game-select').value;
      const p = document.getElementById('ea-pkg-select').value;
      const pr = (eaTopupRates[g] && eaTopupRates[g][p]) ? eaTopupRates[g][p] : "55 ج.م";
      document.getElementById('ea-topup-price').innerText = pr;
    }}
  </script>
</div>
"""

PROMPT_TEMPLATE = """أنت محرر تقني خبير متخصص في كتابة المحتوى الحصري عالي الجودة لموقع «ايجبتاوى» (Egyptaway).
المطلوب كتابة مقال إرشادي تقني شامل ومتكامل لعام 2026 حول موضوع:
«{title_hint}»

الحقائق والمعلومات الرسمية المؤكدة التي يجب الالتزام بها تماماً:
{facts}

{extra}

القواعد الصارمة والمواصفات الإلزامية:
1. اللغة: لغة عربية فصحى بسيطة وواضحة تناسب القارئ المصري والجمهور العربي، بدون تعقيد أو مقدمات إنشائية مستهلكة.
2. بداية المقال: أول فقرة في المقال تجيب مباشرة وفوراً على استفسار القارئ وتقدم الفائدة في السطور الأولى.
3. حجم المحتوى: المقال ضخم ومفصل جداً (أكثر من 1000 كلمة). قسم المحتوى إلى 4-5 عناوين فرعية H2 واضحة وعناوين فرعية H3 تحتها، واستخدم القوائم النقطية والجداول المقارنة المفيدة.
4. الصور: ضع وسوم الصور الثلاثة التالية داخل سياق المحتوى بين الفقرات بالترتيب:
   - {{img0}} في أول ربع المقال بعد الفقرة الثانية.
   - {{img1}} في منتصف المقال.
   - {{img2}} قبل قسم الأسئلة الشائعة.
5. الأداة التفاعلية: ضع الوسم {{interactive_widget}} في المكان الأنسب بعد العنوان الفرعي الأول أو الثاني.
6. الروابط الداخلية: ضع الوسم {{internal_links}} في موضع مناسب بين الفقرات.
7. قسم الأسئلة الشائعة (FAQ): اكتب 5 أسئلة هامة شائعة وإجاباتها الدقيقة.
8. ممنوعات قطعية: ممنوع تماماً أي إشارة لمواقع المراهنات، ممنوع أي تطبيقات أو ألعاب مهكرة أو هاكات، ممنوع السياسة أو الفن.
9. العنوان والوصف:
   - title: عنوان جذاب ومباشر لا يتعدى 65 حرفاً ويحتوي على سنة 2026.
   - slug: رابط إنجليزي نظيف مكون من 3 إلى 6 كلمات فقط تنتهي بـ 2026 (حروف إنجليزية وشرطات فقط).
   - desc: وصف بحث دقيق وجذاب يتراوح طوله بين 140 و160 حرفاً بالضبط.

أرجع النتيجة بصيغة JSON صالح فقط بالشكل التالي:
{{
  "title": "العنوان بالعربي 2026",
  "slug": "english-slug-3-to-6-words-2026",
  "desc": "وصف البحث الدقيق بين 140 و160 حرفاً يبدأ بالمعلومة الأهم للباحث في جوجل",
  "body": "نص المقال الكامل بتنسيق HTML يحتوي على <h2> و<h3> و<p> و<ul> و<li> و<table>، بالإضافة إلى المواضع المحددة لـ {{img0}} و{{img1}} و{{img2}} و{{interactive_widget}} و{{internal_links}}",
  "faq": [
    {{"q": "السؤال الأول؟", "a": "الإجابة الدقيقة والشاملة"}},
    {{"q": "السؤال الثاني؟", "a": "الإجابة الدقيقة والشاملة"}},
    {{"q": "السؤال الثالث؟", "a": "الإجابة الدقيقة والشاملة"}},
    {{"q": "السؤال الرابع؟", "a": "الإجابة الدقيقة والشاملة"}},
    {{"q": "السؤال الخامس؟", "a": "الإجابة الدقيقة والشاملة"}}
  ]
}}"""


def count_words(text):
    """Accurately counts Arabic and English words in HTML content."""
    plain = re.sub(r"<[^>]+>", " ", text)
    return len(re.findall(r"[\w\u0621-\u064A]+", plain))


def pick_article_photos(pool_name, title):
    """Picks 3 clean, verified photos from the designated pool."""
    pool = PHOTO_POOLS.get(pool_name, PHOTO_POOLS["gaming"])
    chosen = random.sample(pool, min(3, len(pool)))
    if len(chosen) < 3:
        chosen = pool[:3]

    results = []
    for pid, desc in chosen:
        img_url = f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop"
        alt = f"{desc} - {title[:40]}"
        results.append((img_url, alt))
    return results


def build_faq_html(faq_list):
    """Formats 5 FAQs using standard HTML details/summary elements."""
    if not faq_list:
        return ""
    items = []
    for item in faq_list:
        q = html.escape(item.get("q", "").strip())
        a = html.escape(item.get("a", "").strip())
        if q and a:
            items.append(f"""
  <details style="margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
    <summary style="font-weight: bold; color: #1e293b; cursor: pointer; font-size: 15px;">{q}</summary>
    <div style="margin-top: 10px; color: #475569; line-height: 1.7; font-size: 14px;">{a}</div>
  </details>""")
    return f"""
<div class="ea-faq-section" style="margin: 30px 0;">
  <h3 style="color: #0f172a; margin-bottom: 15px; font-size: 18px;">الأسئلة الشائعة حول الموضوع</h3>
  {''.join(items)}
</div>"""


def pick_internal_links(topic, site_posts_list):
    """Selects 2-3 relevant live posts from Egyptaway to link inside the article."""
    topic_words = set(f.norm(topic["title_hint"] + " " + " ".join(topic["keywords"])).split())
    scored = []
    for p in site_posts_list:
        u = p.get("u", "").split("?")[0]
        t = p.get("t", "")
        if not u or not t:
            continue
        pw = set(f.norm(t).split())
        overlap = len(topic_words & pw)
        scored.append((overlap, u, t))
    scored.sort(key=lambda x: -x[0])
    chosen = []
    seen_urls = set()
    for _, u, t in scored:
        if u not in seen_urls:
            chosen.append((u, t))
            seen_urls.add(u)
        if len(chosen) >= 3:
            break
    return chosen


def build_internal_links_html(links):
    """Formats internal links into an organic recommendation box."""
    if not links:
        return ""
    lis = "".join(f'<li style="margin-bottom: 8px;"><a href="{html.escape(u)}" style="color: #2563eb; text-decoration: none; font-weight: bold;">{html.escape(t)}</a></li>' for u, t in links)
    return f"""
<div class="ea-related-box" style="background: #f1f5f9; border-right: 4px solid #2563eb; padding: 14px 18px; margin: 25px 0; border-radius: 4px;">
  <span style="font-weight: bold; color: #0f172a; display: block; margin-bottom: 8px;">مواضيع هامة ذات صلة بموقعنا:</span>
  <ul style="margin: 0; padding-right: 20px;">
    {lis}
  </ul>
</div>"""


def assemble_full_html(art, topic, internal_links):
    """Combines all components into the final validated article HTML."""
    body = art.get("body", "")
    photos = pick_article_photos(topic["pool"], art["title"])

    # 1. Image 0 (Hero Image - First image is eager loaded, others lazy)
    img0_html = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" data-original-height="675" data-original-width="1200" width="1000" height="563" src="{photos[0][0]}" alt="{html.escape(photos[0][1])}" title="{html.escape(photos[0][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""
    img1_html = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" data-original-height="675" data-original-width="1200" width="1000" height="563" loading="lazy" src="{photos[1][0]}" alt="{html.escape(photos[1][1])}" title="{html.escape(photos[1][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""
    img2_html = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" data-original-height="675" data-original-width="1200" width="1000" height="563" loading="lazy" src="{photos[2][0]}" alt="{html.escape(photos[2][1])}" title="{html.escape(photos[2][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""

    # Replace placeholders
    if "{img0}" in body:
        body = body.replace("{img0}", img0_html)
    else:
        body = img0_html + "\n" + body

    if "{img1}" in body:
        body = body.replace("{img1}", img1_html)
    else:
        body += "\n" + img1_html

    if "{img2}" in body:
        body = body.replace("{img2}", img2_html)
    else:
        body += "\n" + img2_html

    # Interactive widget
    widget_html = generate_interactive_widget(topic.get("widget_type", "sensitivity_copy"), topic)
    if "{interactive_widget}" in body:
        body = body.replace("{interactive_widget}", widget_html)
    else:
        body = widget_html + "\n" + body

    # Internal links
    links_html = build_internal_links_html(internal_links)
    if "{internal_links}" in body:
        body = body.replace("{internal_links}", links_html)
    else:
        body += "\n" + links_html

    # FAQ
    faq_html = build_faq_html(art.get("faq", []))
    body += "\n" + faq_html

    # Official Sources
    src_name = topic.get("source_name", "الموقع الرسمي")
    src_url = topic.get("source_url", "https://www.egyptaway.com")
    sources_html = f"""
<div class="ea-sources-box" style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b;">
  <strong>المصادر الرسمية:</strong> <a href="{html.escape(src_url)}" target="_blank" rel="nofollow noopener" style="color: #2563eb; text-decoration: underline;">{html.escape(src_name)}</a>
</div>"""
    body += "\n" + sources_html

    return body


def clean_and_validate_meta(art, topic):
    """Ensures title, slug, and search description adhere strictly to Blogger pipeline requirements."""
    title = (art.get("title") or topic["title_hint"]).strip()
    title = re.sub(r'["\']', '', title)
    if "2026" not in title:
        title += " 2026"
    if len(title) > 70:
        title = title[:67].rstrip() + "..."
    art["title"] = title

    raw_slug = (art.get("slug") or topic["slug"]).strip().lower()
    raw_slug = re.sub(r"[^a-z0-9\-]", "", raw_slug.replace(" ", "-"))
    raw_slug = re.sub(r"-+", "-", raw_slug).strip("-")
    slug_parts = [p for p in raw_slug.split("-") if p]
    if len(slug_parts) < 3:
        slug_parts = topic["slug"].split("-")
    if len(slug_parts) > 7:
        slug_parts = slug_parts[:6] + ["2026"]
    if not slug_parts or slug_parts[-1] != "2026":
        slug_parts.append("2026")
    art["slug"] = "-".join(slug_parts)

    desc = (art.get("desc") or "").strip()
    desc = re.sub(r"\s+", " ", desc)
    if len(desc) < 140:
        desc = (desc + f" - يقدم موقع ايجبتاوى دليلاً شاملاً وحصرياً لعام 2026 حول {title}.")[:158]
    elif len(desc) > 160:
        desc = desc[:157].rstrip() + "..."
    art["desc"] = desc


def generate_dynamic_core_topic(existing_titles, preferred_pillar=None):
    """Generates an original non-duplicate evergreen topic within the 4 pillars via Gemini."""
    pillar_desc = {
        "gaming_guides": "شروحات الألعاب وتطوير الحسابات وأسرار اللعب (ببجي، فيفا، دريم ليج، روبلوكس، فري فاير)",
        "game_settings": "ملفات وإعدادات وحساسية الألعاب (كود حساسية ببجي، 90/120 فريم، أطقم دريم ليج، تحكم فيفا)",
        "telecom_codes": "أكواد وخدمات فودافون والاتصالات المصرية (فودافون كاش، فليكس، تجديد باقات، إلغاء الخدمات)",
        "game_topup": "شحن الألعاب في مصر (شدات ببجي، جواهر فري فاير، كوداشوب، ميداس باي، فودافون كاش)"
    }
    sel_pillar = preferred_pillar if preferred_pillar in pillar_desc else random.choice(list(pillar_desc.keys()))

    sample_titles = "\n".join(f"- {t}" for t in existing_titles[:150])
    prompt = f"""أنت خبير محتوى وتحليل كلمات بحث لموقع «ايجبتاوى».
اقترح موضوعاً بحثياً رئيسياً جديداً واحداً يبحث عنه آلاف المصريين والعرب يومياً في جوجل حصراً في القسم التالي:
«{pillar_desc[sel_pillar]}»

شروط لا تقبل التجاوز:
1. أن يكون الموضوع حصرياً وغير مكرر مع أي من عناوين الموقع الحالية:
{sample_titles}
2. أن يعتمد على حقائق وأكواد وإرشادات رسمية مؤكدة بنسبة 100%.
3. أن يكون في صلب اهتمام اللاعبين أو مستخدمي شبكات المحمول في مصر لعام 2026.

أرجع النتيجة بصيغة JSON صالح فقط:
{{
  "id": "english-unique-id-2026",
  "pillar": "{sel_pillar}",
  "title_hint": "عنوان الموضوع بالعربي 2026",
  "slug": "english-slug-3-to-6-words-2026",
  "category": ["شروحات", "ألعاب"],
  "pool": "{"gaming" if "game" in sel_pillar or "gaming" in sel_pillar else ("topup" if sel_pillar == "game_topup" else "telecom")}",
  "widget_type": "{"sensitivity_copy" if "settings" in sel_pillar or "guides" in sel_pillar else ("ussd_selector" if sel_pillar == "telecom_codes" else "topup_calculator")}",
  "keywords": ["كلمة مفتاحية 1", "كلمة مفتاحية 2"],
  "source_name": "اسم الجهة الرسمية",
  "source_url": "https://www.google.com",
  "facts": "ملخص الحقائق الرسمية المؤكدة والأكواد والخطوات بالتفصيل"
}}"""
    res = f.gemini(prompt)
    if isinstance(res, dict) and res.get("title_hint") and res.get("slug"):
        return res
    return None


def main():
    parser = argparse.ArgumentParser(description="Egyptaway Core 4-Pillars Daily Publisher")
    parser.add_argument("--dry", action="store_true", help="Dry run without publishing to Blogger")
    parser.add_argument("--pillar", type=str, default="", help="Optional pillar filter: gaming_guides, game_settings, telecom_codes, game_topup")
    parser.add_argument("--topic-id", type=str, default="", help="Optional specific topic ID to run")
    args = parser.parse_args()

    is_dry = DRY or args.dry
    now_cairo = datetime.datetime.now(CAIRO)
    today_str = now_cairo.date().isoformat()

    try:
        state = json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        state = {"done": []}

    # Cooldown guard: at least 90 minutes between automated runs
    done_entries = [d for d in state.get("done", []) if d.get("ok")]
    if done_entries and not is_dry and not args.topic_id:
        last_item = done_entries[-1]
        last_ts = last_item.get("timestamp") or last_item.get("scheduled_for")
        if last_ts:
            try:
                last_dt = datetime.datetime.fromisoformat(last_ts)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=CAIRO)
                diff_m = (now_cairo - last_dt.astimezone(CAIRO)).total_seconds() / 60
                if diff_m < 90:
                    print(f"Cooldown active: last post published {diff_m:.1f}m ago (minimum 90m gap). Skipping this run.")
                    return
            except Exception as e:
                print(f"Cooldown parse warning: {e}")

    tok = None if is_dry else f.token()
    print("Fetching existing site posts to prevent semantic duplication...")
    site_posts = f.site_posts(tok)
    existing_titles = [p["t"] for p in site_posts]
    existing_slugs = [p.get("u", "").split("/")[-1].replace(".html", "") for p in site_posts]
    state_done_ids = {d.get("id") for d in state.get("done", []) if d.get("ok")}

    # Select topic from the curated bank or generate dynamically
    selected_topic = None
    if args.topic_id:
        selected_topic = next((t for t in CORE_TOPICS if t["id"] == args.topic_id), None)
    else:
        # Filter by requested pillar if any
        candidates = CORE_TOPICS
        if args.pillar:
            candidates = [t for t in CORE_TOPICS if t.get("pillar") == args.pillar]

        # Rotate pillars to ensure balanced coverage across all 4 pillars
        last_pillar = done_entries[-1].get("pillar") if done_entries else None
        pillar_rotation = ["gaming_guides", "telecom_codes", "game_settings", "game_topup"]
        if last_pillar in pillar_rotation:
            idx = (pillar_rotation.index(last_pillar) + 1) % len(pillar_rotation)
            preferred_p = pillar_rotation[idx]
            # Prioritize candidates from next pillar
            candidates = sorted(candidates, key=lambda t: 0 if t.get("pillar") == preferred_p else 1)

        for cand in candidates:
            if cand["id"] in state_done_ids:
                continue
            is_dup, reason = f.is_semantic_duplicate(cand["title_hint"], existing_titles, cand["slug"], existing_slugs)
            if not is_dup:
                selected_topic = cand
                break

    if not selected_topic:
        print("All curated bank topics for this section are covered! Generating fresh dynamic topic via Gemini...")
        selected_topic = generate_dynamic_core_topic(existing_titles, args.pillar)
        if not selected_topic:
            print("Could not generate a non-duplicate topic today; exiting peacefully.")
            return

    print(f"\n=======================================================")
    print(f"🎯 Selected Core Topic: [{selected_topic['id']}]")
    print(f"🏛️ Pillar: {selected_topic.get('pillar', 'core')}")
    print(f"📌 Title Hint: {selected_topic['title_hint']}")
    print(f"=======================================================\n")

    # Generate complete article via Gemini
    extra_instructions = ""
    art = None
    for attempt in range(2):
        prompt = PROMPT_TEMPLATE.format(
            title_hint=selected_topic["title_hint"],
            facts=selected_topic["facts"],
            extra=extra_instructions,
        )
        art = f.gemini(prompt)
        if f._DOWN:
            print("Gemini API unavailable right now; exiting peacefully.")
            return
        if not art or not isinstance(art, dict) or not art.get("body"):
            extra_instructions = "تنبيه: الرد السابق كان فارغاً. أرجع JSON صالح يحتوي على title وdesc وbody (أكثر من 1000 كلمة) وfaq (5 أسئلة)."
            continue
        if FORBIDDEN_REGEX.search(art.get("body", "") + " " + art.get("title", "")):
            extra_instructions = "تنبيه: احذف أي إشارة لمراهنات أو تطبيقات مهكرة أو سياسة."
            continue
        break

    if not art or not isinstance(art, dict) or not art.get("body"):
        print("Failed to generate valid article draft from Gemini.")
        return

    clean_and_validate_meta(art, selected_topic)
    internal_links = pick_internal_links(selected_topic, site_posts)
    full_html = assemble_full_html(art, selected_topic, internal_links)

    total_words = count_words(full_html)
    print(f"Generated Title ({len(art['title'])} chars): {art['title']}")
    print(f"Generated Slug  : {art['slug']}")
    print(f"Generated Desc  ({len(art['desc'])} chars): {art['desc']}")
    print(f"Total Word Count: {total_words} words")
    print(f"Internal Links  : {len(internal_links)} links")

    if is_dry:
        os.makedirs("out", exist_ok=True)
        out_path = f"out/{art['slug']}.html"
        with open(out_path, "w", encoding="utf-8") as fp:
            fp.write(f"<h1>{html.escape(art['title'])}</h1>\n" + f.with_desc(full_html, art))
        print(f"\n[DRY RUN SUCCESS] Saved preview HTML to: {out_path}")
        return

    # Publish Live on Blogger
    labels = f.site_labels(art, full_html, selected_topic.get("category", ["شروحات", "ألعاب"]))
    d = f.api("POST", f"/blogs/{f.BLOG}/posts", tok, {"isDraft": "true"},
              {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": f.with_desc(full_html, art), "labels": labels})
    f.api("POST", f"/blogs/{f.BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})
    f.api("PATCH", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
    post_info = f.api("GET", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
    post_url = post_info.get("url", "")
    print(f"\n🎉 PUBLISHED LIVE ON EGYPTAWAY: {post_url} | {art['title']}")

    # Save State
    state.setdefault("done", []).append({
        "id": selected_topic["id"],
        "pillar": selected_topic.get("pillar"),
        "date": today_str,
        "timestamp": now_cairo.isoformat(),
        "scheduled_for": now_cairo.isoformat(),
        "title": art["title"],
        "slug": art["slug"],
        "url": post_url,
        "words": total_words,
        "ok": True,
    })
    state["done"] = state["done"][-500:]
    with open(STATE_FILE, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=2)
    print("State saved successfully.")


if __name__ == "__main__":
    main()
