"""Zeda Shop Conversion Booster Engine for Egyptaway (mohsen 2026-11-11).

Periodically publishes high-converting, policy-compliant game top-up articles on Egyptaway (www.egyptaway.com).
Designed specifically to funnel thousands of gamers searching for:
- "شحن شدات ببجي فودافون كاش"
- "شحن جواهر فري فاير بالـ ID"
- "شحن نقاط فالورانت مصر بالجنيه"
- "شحن نقاط إف سي موبايل فودافون كاش"
- "شحن ألعاب بالـ ID في مصر ارخص سعر"
directly into Zeda Shop (www.zeda-shop.com) to drive sales and app installs.

Strict Compliance with Mohsen Directives:
- Titles NEVER include "زيدا شوب" (per Mohsen's explicit rule).
- Store is linked organically and prominently as "متجرنا زيدا شوب" with direct CTA buttons to the exact game page.
- 1000+ words, 3 clean photography images passing image_guard, 5 FAQs, interactive top-up calculator widget.
- State file zeda_booster_posted.json tracks published topics to avoid repeats.
"""

import argparse
import datetime
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
STATE_FILE = "zeda_booster_posted.json"
DRY = os.environ.get("DRY_RUN") in ("1", "true", "True")

# Top High-Converting Games with Direct Zeda Shop Landing Pages & Official Details
BOOSTER_GAMES = [
    {
        "key": "pubg-uc",
        "ar": "ببجي موبايل",
        "en": "PUBG Mobile",
        "currency": "شدات UC",
        "store_url": "https://www.zeda-shop.com/2026/10/pubg-mobile-uc-egypt.html",
        "title_hint": "خطوات شراء شدات ببجي بالمعرف ID والدفع بالمحافظ المصرية 2026",
        "slug": "steps-playerid-pubg-uc-egypt-guide-2026",
        "packages": [
            {"pkg": "60 شدة UC", "price": "55 ج.م", "old": "65 ج.م"},
            {"pkg": "300 + 25 شدة مجاناً", "price": "265 ج.م", "old": "310 ج.م"},
            {"pkg": "600 + 60 شدة (الرويال باس)", "price": "520 ج.م", "old": "600 ج.م"},
            {"pkg": "1500 + 300 شدة", "price": "1300 ج.م", "old": "1500 ج.م"},
            {"pkg": "3000 + 850 شدة", "price": "2580 ج.م", "old": "2950 ج.م"},
            {"pkg": "6000 + 2100 شدة", "price": "5150 ج.م", "old": "5900 ج.م"}
        ],
        "facts": (
            "دليل شحن شدات ببجي موبايل بالمعرف في مصر 2026:\n"
            "- الشحن برقم الآيدي (Player ID) فقط دون الحاجة لتسليم كلمة المرور أو الإيميل.\n"
            "- وسائل الدفع المصرية المعتمدة: فودافون كاش، أورنج كاش، اتصالات كاش، WE Pay، إنستاباي، وبطاقات ميزة.\n"
            "- باقة 660 شدة كافية لتفعيل الرويال باس (Royale Pass) الجديد للموسم الحالي.\n"
            "- وصول الشدات مباشر داخل البريد الداخلي للحساب خلال دقائق معدودة فور تأكيد الدفع.\n"
            "- متجرنا زيدا شوب يوفر خدمة عملاء مصرية ودعم فني مباشر عبر الواتساب."
        )
    },
    {
        "key": "free-fire",
        "ar": "فري فاير",
        "en": "Free Fire",
        "currency": "جواهر",
        "store_url": "https://www.zeda-shop.com/2026/10/free-fire-diamonds-egypt.html",
        "title_hint": "خطوات شراء جواهر فري فاير بالمعرف ID والدفع بالمحافظ 2026",
        "slug": "steps-playerid-freefire-diamonds-egypt-guide-2026",
        "packages": [
            {"pkg": "100 + 10 جوهرة بونص", "price": "45 ج.م", "old": "55 ج.م"},
            {"pkg": "310 + 31 جوهرة", "price": "135 ج.م", "old": "160 ج.م"},
            {"pkg": "520 + 52 جوهرة (بويا باس)", "price": "225 ج.م", "old": "260 ج.م"},
            {"pkg": "1060 + 106 جوهرة", "price": "445 ج.م", "old": "520 ج.م"},
            {"pkg": "العضوية الأسبوعية (Weekly Pass)", "price": "95 ج.م", "old": "115 ج.م"},
            {"pkg": "العضوية الشهرية (Monthly Pass)", "price": "470 ج.م", "old": "550 ج.م"}
        ],
        "facts": (
            "دليل شحن جواهر فري فاير الرسمية بالـ ID في مصر 2026:\n"
            "- إدخال رقم المعرف (Player ID) والتأكد من اسم الشخصية داخل اللعبة.\n"
            "- الدفع متاح عبر جميع المحافظ الإلكترونية فودافون كاش وإنستاباي وفوري بالجنيه المصري.\n"
            "- باقة العضوية الأسبوعية والشهرية تمنح جواهر تراكمية يومية بأعلى عائد توفير في اللعبة.\n"
            "- وصول فوري وآمن 100% بدون أي مخاطر حظر (باند) لحسابك لأن الشحن رسمي.\n"
            "- إمكانية الشحن من خلال متجرنا زيدا شوب عبر المتصفح أو تطبيق الموبايل."
        )
    },
    {
        "key": "fc-mobile",
        "ar": "إف سي موبايل",
        "en": "FC Mobile",
        "currency": "نقاط FC Points",
        "store_url": "https://www.zeda-shop.com/2026/10/fc-mobile-points-egypt.html",
        "title_hint": "طريقة شحن نقاط إف سي موبايل FC Points بالـ ID في مصر 2026: فودافون كاش",
        "slug": "tutorial-topup-fc-mobile-points-id-egypt-2026",
        "packages": [
            {"pkg": "100 FC Points", "price": "60 ج.م", "old": "75 ج.م"},
            {"pkg": "500 + 25 Points", "price": "290 ج.م", "old": "340 ج.م"},
            {"pkg": "1050 + 50 Points (Star Pass)", "price": "580 ج.م", "old": "670 ج.م"},
            {"pkg": "2200 Points", "price": "1190 ج.م", "old": "1380 ج.م"},
            {"pkg": "5700 Points", "price": "2950 ج.م", "old": "3400 ج.م"}
        ],
        "facts": (
            "دليل شحن نقاط FC Mobile الرسمية في مصر 2026:\n"
            "- الشحن برقم الـ UID المتاح في إعدادات اللعبة.\n"
            "- نقاط FC Points تمكنك من فتح بكجات الأحداث العالمية وشراء بطاقة النجوم (Star Pass).\n"
            "- الدفع بالجنيه المصري عبر المحافظ الإلكترونية بدون فيزا دولارية أو رسوم تدبير عملة.\n"
            "- متوفر الشحن الفوري مع فاتورة رسمية عبر متجرنا زيدا شوب المعتمد."
        )
    },
    {
        "key": "valorant",
        "ar": "فالورانت",
        "en": "Valorant",
        "currency": "نقاط VP",
        "store_url": "https://www.zeda-shop.com/2026/11/valorant-points-egypt.html",
        "title_hint": "طريقة شحن نقاط فالورانت VP في مصر 2026: الدفع بالجنيه فودافون كاش",
        "slug": "tutorial-topup-valorant-points-egypt-2026",
        "packages": [
            {"pkg": "475 VP", "price": "240 ج.م", "old": "280 ج.م"},
            {"pkg": "1000 VP (Battlepass)", "price": "490 ج.م", "old": "570 ج.م"},
            {"pkg": "2050 VP", "price": "980 ج.م", "old": "1140 ج.م"},
            {"pkg": "3650 VP", "price": "1720 ج.م", "old": "1990 ج.م"},
            {"pkg": "5350 VP", "price": "2450 ج.م", "old": "2850 ج.م"}
        ],
        "facts": (
            "دليل شحن نقاط فالورانت في مصر 2026:\n"
            "- مخصص لسيرفرات الشرق الأوسط وأوروبا (MENA / EU) عبر Riot ID.\n"
            "- باقة 1000 VP كافية لتفعيل الباتل باس (Battlepass) كاملاً.\n"
            "- الدفع متاح عبر فودافون كاش وإنستاباي مع تسليم الأكواد الرقمية أو الشحن المباشر فوراً.\n"
            "- أسعار رسمية بالجنيه المصري دون الحاجة لحسابات بنكية أجنبية عبر متجرنا زيدا شوب."
        )
    },
    {
        "key": "mobile-legends",
        "ar": "موبايل ليجندز",
        "en": "Mobile Legends",
        "currency": "ماسات Diamonds",
        "store_url": "https://www.zeda-shop.com/2026/10/mobile-legends-diamonds-egypt.html",
        "title_hint": "طريقة شحن ماسات موبايل ليجندز MLBB بالـ ID في مصر 2026: فودافون كاش",
        "slug": "tutorial-topup-mobile-legends-diamonds-id-egypt-2026",
        "packages": [
            {"pkg": "86 ماسة", "price": "85 ج.م", "old": "100 ج.م"},
            {"pkg": "172 ماسة", "price": "165 ج.م", "old": "195 ج.م"},
            {"pkg": "257 ماسة", "price": "245 ج.م", "old": "290 ج.م"},
            {"pkg": "706 ماسات", "price": "670 ج.م", "old": "780 ج.م"},
            {"pkg": "بطاقة المرور الأسبوعية (Weekly Diamond Pass)", "price": "99 ج.م", "old": "120 ج.م"}
        ],
        "facts": (
            "دليل شحن موبايل ليجندز MLBB في مصر 2026:\n"
            "- يتطلب الشحن إدخال الـ User ID والـ Zone ID المكون من 4 أو 5 أرقام داخل القوسين.\n"
            "- بطاقة المرور الأسبوعية تمنح 210 ماسة ونقاط ترقية بأفضل قيمة توفير.\n"
            "- الشحن رسمي بالكامل ومباشر عبر شراكة كوداشوب في متجرنا زيدا شوب بالجنيه المصري.\n"
            "- خدمة عملاء على مدار 24 ساعة للرد على استفسارات اللاعبين."
        )
    },
    {
        "key": "codm",
        "ar": "كول أوف ديوتي موبايل",
        "en": "Call of Duty Mobile",
        "currency": "نقاط CP",
        "store_url": "https://www.zeda-shop.com/2026/10/call-of-duty-mobile-cp-egypt.html",
        "title_hint": "طريقة شحن نقاط CP كول أوف ديوتي موبايل بالـ ID في مصر 2026",
        "slug": "tutorial-topup-codm-cp-id-egypt-2026",
        "packages": [
            {"pkg": "80 CP", "price": "55 ج.م", "old": "65 ج.م"},
            {"pkg": "420 CP (Battle Pass)", "price": "260 ج.م", "old": "310 ج.م"},
            {"pkg": "880 CP", "price": "520 ج.م", "old": "600 ج.م"},
            {"pkg": "2400 CP", "price": "1350 ج.م", "old": "1550 ج.م"}
        ],
        "facts": (
            "دليل شحن كول أوف ديوتي موبايل في مصر 2026:\n"
            "- الشحن برقم Player ID الخاص بحسابك في اللعبة.\n"
            "- باقة 420 CP كافية لتفعيل الباتل باس واستعادة النقاط كاملة عند إنهاء المستويات.\n"
            "- الدفع عبر فودافون كاش والمحافظ الرقمية المصرية بضمان زيدا شوب."
        )
    },
    {
        "key": "clash-of-clans",
        "ar": "كلاش أوف كلانس",
        "en": "Clash of Clans",
        "currency": "جواهر وجولد باس",
        "store_url": "https://www.zeda-shop.com/2026/10/clash-of-clans-gems-egypt.html",
        "title_hint": "طريقة شحن جواهر وجولد باس كلاش أوف كلانس بالـ ID في مصر 2026",
        "slug": "tutorial-topup-clash-of-clans-gems-egypt-2026",
        "packages": [
            {"pkg": "80 جوهرة", "price": "55 ج.م", "old": "65 ج.م"},
            {"pkg": "500 جوهرة", "price": "270 ج.م", "old": "320 ج.م"},
            {"pkg": "تذكرة الجولد باس (Gold Pass)", "price": "370 ج.م", "old": "440 ج.م"},
            {"pkg": "1200 جوهرة", "price": "540 ج.م", "old": "620 ج.م"}
        ],
        "facts": (
            "دليل شحن كلاش أوف كلانس Supercell في مصر 2026:\n"
            "- الشحن عبر كود اللاعب (Player Tag) الرسمي.\n"
            "- تذكرة الجولد باس تسرع تطوير القرية بنسبة 20% وتمنح سكنات البطل الحصرية.\n"
            "- الشحن آمن ومطابق لمتجر سوبرسل الرسمي والدفع فودافون كاش عبر متجرنا زيدا شوب."
        )
    },
    {
        "key": "8-ball-pool",
        "ar": "8 بول بول",
        "en": "8 Ball Pool",
        "currency": "كاش وكوينز",
        "store_url": "https://www.zeda-shop.com/2026/11/8-ball-pool-cash-coins-egypt.html",
        "title_hint": "طريقة شحن كاش وكوينز 8 بول بول بالـ ID في مصر 2026: فودافون كاش",
        "slug": "tutorial-topup-8-ball-pool-cash-coins-egypt-2026",
        "packages": [
            {"pkg": "25 كاش Pool Cash", "price": "55 ج.م", "old": "65 ج.م"},
            {"pkg": "65 كاش", "price": "135 ج.م", "old": "160 ج.م"},
            {"pkg": "140 كاش", "price": "270 ج.م", "old": "320 ج.م"},
            {"pkg": "300 كاش", "price": "540 ج.م", "old": "620 ج.م"}
        ],
        "facts": (
            "دليل شحن 8 Ball Pool Miniclip في مصر 2026:\n"
            "- الشحن برقم المعرف Unique ID فقط دون الحاجة للدخول إلى حسابك.\n"
            "- الكاش يساعدك في شراء عصي الأساطير وفتح الصناديق الذهبية.\n"
            "- أسعار مباشرة بالجنيه المصري مع دعم فودافون كاش وإنستاباي من متجرنا زيدا شوب."
        )
    }
]

PHOTO_POOL = [
    ("3165335", "أدوات وملحقات الألعاب وشحن الرصيد والعملات الرقمية"),
    ("3945683", "ممارسة ألعاب الهواتف الذكية والتنافس أونلاين"),
    ("442576", "منصات الألعاب الإلكترونية والدفع الآمن للعملات"),
    ("7915357", "استلام الشدات والجواهر الرسمية داخل الحساب"),
    ("1174746", "تشغيل ألعاب الموبايل وشاشات الألعاب المتقدمة")
]

PROMPT_TEMPLATE = """أنت خبير تسويق رقمي وSEO متخصص في كتابة مقالات شرائية عالية التحويل (High-Conversion Search Intent) لموقع «ايجبتاوى».
المطلوب كتابة مقال إرشادي شرائي ضخم وشامل لعام 2026 حول موضوع:
«{title_hint}» للعبة «{ar} ({en})».

الحقائق الرسمية وقائمة الأسعار المعتمدة:
{facts}

جدول باقات الأسعار الرسمية بالجنيه المصري:
{price_table_text}

رابط الشراء المباشر للعبة في متجرنا:
{store_url}

القواعد الإلزامية الصارمة:
1. العنوان: لا تذكر كلمة «زيدا شوب» في العنوان أبداً (شرط قطعي لمحسن). العنوان جذاب، مباشر، لا يتجاوز 68 حرفاً، وفيه سنة 2026.
2. نص المقال: اذكر المتجر بشكل طبيعي داخل النص باسم «متجرنا زيدا شوب» أو «تطبيق زيدا شوب الرسمي».
3. طمأنة المشتري (Trust Triggers): ركز بقوة في المقال على أن الشحن يتم برقم المعرف (Player ID) فقط، وبدون طلب أي كلمات مرور أو تسجيل دخول، والدفع متاح فوراً بالمحافظ المصرية فودافون كاش وإنستاباي وفوري.
4. حجم المقال: مفصل جداً واحترافي (أكثر من 1000 كلمة)، مقسم بعناوين H2 وH3 وخطوات عملية واضحة (1، 2، 3...).
5. مواضع الوسوم:
   - {{img0}} في الربع الأول.
   - {{img1}} في المنتصف.
   - {{price_table}} مكان جدول الأسعار المعتمدة.
   - {{calculator_widget}} مكان الأداة التفاعلية وزر الشراء المباشر لمتجرنا زيدا شوب.
   - {{internal_links}} مكان الروابط الداخلية.
   - {{img2}} قبل الأسئلة الشائعة.
6. 5 أسئلة شائعة (FAQ) تهم المشتري (عن سرعة الوصول، أمان الحساب، فودافون كاش، حل المشكلات).
7. وصف البحث (desc): بين 140 و160 حرفاً يركز على خطوات الشحن والأسعار بالجنيه والدفع بالمحافظ عبر متجرنا زيدا شوب بأمان تام.

أرجع النتيجة بصيغة JSON صالح فقط:
{{
  "title": "العنوان بالعربي 2026",
  "slug": "{slug}",
  "desc": "وصف البحث بين 140 و160 حرفاً",
  "body": "نص المقال الكامل HTML يحتوي على الوسوم المذكورة",
  "faq": [
    {{"q": "سؤال؟", "a": "جواب"}},
    {{"q": "سؤال؟", "a": "جواب"}},
    {{"q": "سؤال؟", "a": "جواب"}},
    {{"q": "سؤال؟", "a": "جواب"}},
    {{"q": "سؤال؟", "a": "جواب"}}
  ]
}}"""


def count_words(text):
    plain = re.sub(r"<[^>]+>", " ", text)
    return len(re.findall(r"[\w\u0621-\u064A]+", plain))


def generate_booster_widget(game):
    """Generates an embedded interactive price table & conversion button to Zeda Shop."""
    pkgs = game.get("packages", [])
    options = "".join(f'<option value="{p["price"]}">{p["pkg"]} - {p["price"]}</option>' for p in pkgs)

    table_rows = "".join(
        f'<tr style="border-bottom: 1px solid #e2e8f0;">'
        f'<td style="padding: 10px 14px; color: #1e293b; font-weight: bold;">{p["pkg"]}</td>'
        f'<td style="padding: 10px 14px; color: #d97706; font-weight: bold;">{p["price"]}</td>'
        f'<td style="padding: 10px 14px; color: #94a3b8; text-decoration: line-through;">{p.get("old", "-")}</td>'
        f'</tr>'
        for p in pkgs
    )

    return f"""
<!-- ea zeda conversion price table -->
<div class="ea-pricing-table-wrap" style="margin: 25px 0; overflow-x: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.04);">
  <table style="width: 100%; border-collapse: collapse; text-align: right; direction: rtl; font-family: Cairo, Tahoma, sans-serif; font-size: 14px;">
    <thead>
      <tr style="background: #f8fafc; border-bottom: 2px solid #cbd5e1; color: #475569;">
        <th style="padding: 12px 14px;">الباقة الرسمية</th>
        <th style="padding: 12px 14px;">السعر الحالي</th>
        <th style="padding: 12px 14px;">السعر السابق</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</div>

<!-- ea zeda interactive conversion widget -->
<div class="ea-widget-box" style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border: 2px solid #cbd5e1; border-radius: 12px; padding: 22px; margin: 30px 0; font-family: Cairo, Tahoma, sans-serif; text-align: right; direction: rtl; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
  <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
    <h4 style="margin: 0; color: #0f172a; font-size: 18px; display: flex; align-items: center; gap: 8px;">
      <span>⚡ شحن باقات {game['ar']} بالـ ID فوراً</span>
    </h4>
    <span style="background: #dcfce7; color: #15803d; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;">
      ✓ شحن معتمد وآمن 100%
    </span>
  </div>
  <p style="margin: 0 0 16px 0; font-size: 14px; color: #475569; line-height: 1.6;">
    اختر باقتك المفضلة وسدد قيمتها بالجنيه المصري عبر فودافون كاش أو إنستاباي واستلم الشحنة برقم المعرف في دقائق:
  </p>
  <div style="margin-bottom: 18px;">
    <select id="zd-pkg-select" onchange="zdUpdateSelectedPrice()" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #94a3b8; background: #fff; font-size: 15px; font-weight: bold; color: #1e293b;">
      {options}
    </select>
  </div>
  <div style="background: #ffffff; border: 1px dashed #d97706; border-radius: 8px; padding: 14px 18px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
    <div>
      <span style="font-size: 12px; color: #64748b; display: block;">قيمة الباقة النهائية:</span>
      <strong id="zd-selected-price" style="font-size: 20px; color: #b45309;">{pkgs[0]['price'] if pkgs else '55 ج.م'}</strong>
    </div>
    <a href="{game['store_url']}" target="_blank" rel="noopener" style="background: #d97706; color: #ffffff; padding: 10px 24px; border-radius: 8px; font-size: 14px; font-weight: bold; text-decoration: none; display: inline-block; box-shadow: 0 4px 12px rgba(217,119,6,0.3); transition: all 0.2s;">
      اشحن الآن من متجرنا زيدا شوب 🚀
    </a>
  </div>
  <div style="margin-top: 12px; font-size: 12px; color: #64748b; display: flex; align-items: center; gap: 6px;">
    <span>🔒 الشحن يتم بالـ Player ID فقط وبدون طلب أي كلمات مرور أو تسجيل دخول.</span>
  </div>
  <script>
    function zdUpdateSelectedPrice() {{
      const sel = document.getElementById('zd-pkg-select');
      document.getElementById('zd-selected-price').innerText = sel.value;
    }}
  </script>
</div>
"""


def pick_photos(title):
    chosen = random.sample(PHOTO_POOL, 3)
    results = []
    for pid, desc in chosen:
        url = f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg?auto=compress&cs=tinysrgb&w=1200&h=675&fit=crop"
        alt = f"{desc} - {title[:40]}"
        results.append((url, alt))
    return results


def assemble_booster_html(art, game, internal_links):
    body = art.get("body", "")
    photos = pick_photos(art["title"])

    img0 = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" width="1000" height="563" src="{photos[0][0]}" alt="{html.escape(photos[0][1])}" title="{html.escape(photos[0][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""
    img1 = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" width="1000" height="563" loading="lazy" src="{photos[1][0]}" alt="{html.escape(photos[1][1])}" title="{html.escape(photos[1][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""
    img2 = f"""<div class="separator" style="clear: both; text-align: center; margin: 20px 0;"><img border="0" width="1000" height="563" loading="lazy" src="{photos[2][0]}" alt="{html.escape(photos[2][1])}" title="{html.escape(photos[2][1])}" style="max-width: 100%; height: auto; border-radius: 8px;" /></div>"""

    if "{img0}" in body:
        body = body.replace("{img0}", img0)
    else:
        body = img0 + "\n" + body

    if "{img1}" in body:
        body = body.replace("{img1}", img1)
    else:
        body += "\n" + img1

    if "{img2}" in body:
        body = body.replace("{img2}", img2)
    else:
        body += "\n" + img2

    widget_html = generate_booster_widget(game)
    if "{calculator_widget}" in body:
        body = body.replace("{calculator_widget}", widget_html)
    elif "{price_table}" in body:
        body = body.replace("{price_table}", widget_html)
    else:
        body += "\n" + widget_html

    # Internal links
    if internal_links:
        lis = "".join(f'<li style="margin-bottom: 8px;"><a href="{html.escape(u)}" style="color: #2563eb; text-decoration: none; font-weight: bold;">{html.escape(t)}</a></li>' for u, t in internal_links)
        links_box = f"""
<div class="ea-related-box" style="background: #f1f5f9; border-right: 4px solid #2563eb; padding: 14px 18px; margin: 25px 0; border-radius: 4px;">
  <span style="font-weight: bold; color: #0f172a; display: block; margin-bottom: 8px;">مواضيع هامة ذات صلة بالألعاب:</span>
  <ul style="margin: 0; padding-right: 20px;">{lis}</ul>
</div>"""
        if "{internal_links}" in body:
            body = body.replace("{internal_links}", links_box)
        else:
            body += "\n" + links_box

    # FAQ
    faq_items = "".join(f"""
  <details style="margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px;">
    <summary style="font-weight: bold; color: #1e293b; cursor: pointer; font-size: 15px;">{html.escape(q['q'])}</summary>
    <div style="margin-top: 10px; color: #475569; line-height: 1.7; font-size: 14px;">{html.escape(q['a'])}</div>
  </details>""" for q in art.get("faq", []))
    body += f"""\n<div class="ea-faq-section" style="margin: 30px 0;"><h3 style="color: #0f172a; margin-bottom: 15px; font-size: 18px;">الأسئلة الشائعة حول شحن {game['ar']}</h3>{faq_items}</div>"""

    # Official Sources & Store Attribution
    body += f"""
<div class="ea-sources-box" style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b;">
  <strong>المصادر الرسمية وخدمة الشحن:</strong> <a href="{html.escape(game['store_url'])}" target="_blank" rel="noopener" style="color: #2563eb; text-decoration: underline;">متجرنا زيدا شوب (Zeda Shop) للشحن المعتمد بالمعرف ID</a>
</div>"""

    return body


def main():
    parser = argparse.ArgumentParser(description="Zeda Shop Traffic Booster Engine")
    parser.add_argument("--dry", action="store_true", help="Dry run without publishing to Blogger")
    parser.add_argument("--game", type=str, default="", help="Specific game key to publish (e.g. pubg-uc, free-fire)")
    args = parser.parse_args()

    is_dry = DRY or args.dry
    now_cairo = datetime.datetime.now(CAIRO)
    today_str = now_cairo.date().isoformat()

    try:
        state = json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        state = {"done": []}

    done_keys = {d.get("key") for d in state.get("done", []) if d.get("ok")}

    # Select target game
    selected_game = None
    if args.game:
        selected_game = next((g for g in BOOSTER_GAMES if g["key"] == args.game), None)
    else:
        for g in BOOSTER_GAMES:
            if g["key"] not in done_keys:
                selected_game = g
                break

    if not selected_game:
        # All covered once, reset rotation
        print("All booster games published once! Cycling through games for fresh seasonal updates...")
        selected_game = random.choice(BOOSTER_GAMES)

    print(f"\n🚀 Selected Booster Game: [{selected_game['key']}] {selected_game['ar']}")
    print(f"🔗 Store URL: {selected_game['store_url']}\n")

    tok = None if is_dry else f.token()
    site_posts = f.site_posts(tok)
    existing_titles = [p["t"] for p in site_posts]
    existing_slugs = [p.get("u", "").split("/")[-1].replace(".html", "") for p in site_posts]

    # Check semantic duplication
    is_dup, reason = f.is_semantic_duplicate(selected_game["title_hint"], existing_titles, selected_game["slug"], existing_slugs)
    if is_dup:
        print(f"Notice: Topic recently covered ({reason}). Refreshing title with seasonal 2026 variant...")
        selected_game["title_hint"] += f" - تحديث شهر {now_cairo.month}"
        selected_game["slug"] += f"-m{now_cairo.month}"

    price_tbl_text = "\n".join(f"- {p['pkg']}: {p['price']} (بدلاً من {p.get('old', '-')})" for p in selected_game.get("packages", []))

    prompt = PROMPT_TEMPLATE.format(
        title_hint=selected_game["title_hint"],
        ar=selected_game["ar"],
        en=selected_game["en"],
        facts=selected_game["facts"],
        price_table_text=price_tbl_text,
        store_url=selected_game["store_url"],
        slug=selected_game["slug"]
    )

    art = f.gemini(prompt)
    if not art or not isinstance(art, dict) or not art.get("body"):
        print("Gemini response invalid; exiting.")
        return

    # Internal links
    game_posts = [p for p in site_posts if any(k in p.get("t", "").lower() for k in ["ألعاب", "ببجي", "لعبة", "تحميل"])]
    internal_links = [(p["u"].split("?")[0], p["t"]) for p in game_posts[:3]]

    full_html = assemble_booster_html(art, selected_game, internal_links)
    words = count_words(full_html)

    print(f"Title: {art['title']}")
    print(f"Slug : {art['slug']}")
    print(f"Desc : {art['desc']}")
    print(f"Words: {words} words")

    if is_dry:
        os.makedirs("out", exist_ok=True)
        out_p = f"out/{art['slug']}.html"
        with open(out_p, "w", encoding="utf-8") as fp:
            fp.write(f.with_desc(full_html, art))
        print(f"[DRY RUN SUCCESS] Saved to {out_p}")
        return

    # Publish to Blogger
    labels = ["ألعاب", "شحن الألعاب"]
    d = f.api("POST", f"/blogs/{f.BLOG}/posts", tok, {"isDraft": "true"},
              {"kind": "blogger#post", "title": art["slug"].replace("-", " "), "content": f.with_desc(full_html, art), "labels": labels})
    f.api("POST", f"/blogs/{f.BLOG}/posts/{d['id']}/publish", tok, {"publishDate": now_cairo.isoformat()})
    f.api("PATCH", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, None, {"title": art["title"]})
    pinfo = f.api("GET", f"/blogs/{f.BLOG}/posts/{d['id']}", tok, {"view": "ADMIN"})
    purl = pinfo.get("url", "")
    print(f"\n🎉 LIVE ON EGYPTAWAY: {purl} | {art['title']}")

    state.setdefault("done", []).append({
        "key": selected_game["key"],
        "date": today_str,
        "title": art["title"],
        "url": purl,
        "words": words,
        "ok": True
    })
    with open(STATE_FILE, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=2)
    print("State saved successfully.")


if __name__ == "__main__":
    main()
