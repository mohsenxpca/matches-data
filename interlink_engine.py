# -*- coding: utf-8 -*-
"""Smart Contextual Interlinker & Anchor Cleaner for Egyptaway & Review Mobile.
Fixes bad anchors, injects semantic in-text links to related live articles, and preserves Blogger layouts.
"""
import sys, os, re, json, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import blogger_api as api
from zoneinfo import ZoneInfo
import datetime as dt

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

CAIRO = ZoneInfo("Africa/Cairo")
BACKUP_DIR = Path("backups")
CACHE_DIR = Path("cache")

BLOGS = {
    "review": {
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com",
        "hubs": [
            ("https://www.review-mobile.com/p/compare-phones_01466757070.html", "أداة مقارنة الهواتف الذكية راس براس"),
            ("https://www.review-mobile.com/p/best-phone-for-budget.html", "دليل أفضل هواتف للشراء حسب الميزانية"),
            ("https://www.review-mobile.com/p/mobile-reviews-hub.html", "فهرس مراجعات ومواصفات الهواتف")
        ]
    },
    "egyptaway": {
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com",
        "hubs": [
            ("https://www.egyptaway.com/p/mobile-prices-egypt.html", "جدول أسعار الموبايلات المحدث في مصر"),
            ("https://www.egyptaway.com/p/gold-prices-egypt.html", "أسعار الذهب اليوم في مصر عيار 21"),
            ("https://www.egyptaway.com/p/currency-prices-egypt.html", "أسعار العملات والدولار في البنوك المصرية"),
            ("https://www.egyptaway.com/p/matches-today.html", "جدول مواعيد مباريات اليوم والقنوات الناقلة"),
            ("https://www.egyptaway.com/p/egyptian-league-table.html", "جدول ترتيب الدوري المصري الممتاز"),
            ("https://www.egyptaway.com/p/bank-certificates-egypt.html", "حاسبة أرباح وفوائد شهادات البنوك المصرية"),
            ("https://www.egyptaway.com/p/housing-egypt.html", "دليل طروحات الإسكان الاجتماعي وبوابة مسكن"),
            ("https://www.egyptaway.com/p/download-games.html", "دليل تحميل وتنزيل الألعاب الرسمية")
        ]
    }
}

GENERIC_BAD_ANCHORS = {
    "قواعد اللعبة", "الهاتف الجديد", "مللي أمبير", "مليون دولار", "إطلاق هاتف",
    "Snapdragon", "شاشة AMOLED", "هواتف أندرويد", "قدرات الشحن", "اتصالات e",
    "شاشة بمعدل", "عطل مفاجئ", "تحديث جديد", "في مصر", "يغير قواعد اللعبة",
    "قواعد المنافسة", "مللي أمبير وشحن", "شاشة كبيرة", "أداء قوي", "معالج قوي",
    "بطارية ضخمة", "كاميرا احترافية", "سعر منافس", "الفئة المتوسطة", "الفئة الاقتصادية"
}

TRAILING_TRIM = {"في", "من", "إلى", "على", "عن", "مع", "أو", "ثم", "هل", "ما", "كل", "إن", "أن", "بعد", "قبل", "بين", "حول"}

def clean_title_for_anchor(title):
    """Generates a clean, natural anchor text from an article title."""
    t = title.strip()
    # Remove leading junk like "تسريب..", "عاجل:", "بالأرقام:", etc.
    t = re.sub(r'^(?:تسريب|تسريبات|مفاجأة|عاجل|رسمياً|بالأرقام|تفاصيل|خاص|شاهد|تقرير|بالفيديو)[:\.\s\-]+', '', t)
    # Remove trailing questions and punctuation
    t = re.sub(r'[\.\s\-\:؟\?]+$', '', t)
    # Remove trailing filler phrases
    t = re.sub(r'[\.\s\-]+(?:التفاصيل|التفاصيل الكاملة|تعرف عليها|هل يستحق؟|ما القصة؟|كل ما تريد معرفته)$', '', t)
    t = t.strip()
    if len(t) > 55:
        # truncate gracefully at word boundary
        words = t[:55].split()
        if len(words) > 1:
            words = words[:-1]
        while words and words[-1] in TRAILING_TRIM:
            words.pop()
        t = " ".join(words)
    # Clean final punctuation
    t = re.sub(r'[\.\s\-\:؟\?]+$', '', t).strip()
    return t

def extract_phone_brand_or_topic(title, labels):
    t_lower = title.lower()
    for b in ["samsung", "سامسونج", "apple", "iphone", "آيفون", "ايفون", "أبل", "ابل",
              "xiaomi", "شاومي", "redmi", "ريدمي", "poco", "بوكو", "oppo", "أوبو", "اوبو",
              "vivo", "فيفو", "iqoo", "آيكو", "honor", "هونر", "realme", "ريلمي",
              "huawei", "هواوي", "oneplus", "ون بلس", "infinix", "إنفينكس", "tecno", "تكنو",
              "motorola", "موتورولا", "pixel", "بيكسل"]:
        if b in t_lower or any(b in l.lower() for l in labels):
            return b
    # Check topic labels
    for l in labels:
        if l in ["أخبار الكورة", "الدوري المصري", "رياضة", "اقتصاد", "خدمات", "ألعاب", "أخبار تقنية"]:
            return l
    return "general"

def load_catalog(site_key):
    """Loads all live posts with their metadata and titles."""
    cache_file = CACHE_DIR / f"{site_key}.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [p for p in data if p.get("status") == "live"]
    return []

def select_related_articles(post_url, post_title, post_labels, catalog, limit=2):
    """Picks topically closest live articles to link to."""
    brand_or_topic = extract_phone_brand_or_topic(post_title, post_labels)
    candidates = []
    
    clean_purl = post_url.split("?")[0]
    
    for other in catalog:
        o_url = other.get("url", "").split("?")[0]
        if not o_url or o_url == clean_purl:
            continue
        o_title = other.get("title", "")
        o_labels = other.get("labels", [])
        o_topic = extract_phone_brand_or_topic(o_title, o_labels)
        
        score = 0
        if brand_or_topic != "general" and o_topic == brand_or_topic:
            score += 10
        # Shared labels
        shared_labels = set(post_labels) & set(o_labels)
        score += len(shared_labels) * 3
        # Recency bonus (prefer posts from 2026)
        if "2026" in o_url:
            score += 2
            
        candidates.append((score, o_url, o_title))
        
    candidates.sort(key=lambda x: -x[0])
    selected = []
    for score, u, t in candidates:
        if len(selected) >= limit:
            break
        selected.append((u, clean_title_for_anchor(t)))
    return selected

def fix_and_interlink_post(content, post_url, post_title, post_labels, site_key, catalog_by_url, catalog):
    """Cleans bad anchors and ensures at least 2 relevant article links + 1 hub link."""
    domain = BLOGS[site_key]["domain"]
    hubs = BLOGS[site_key]["hubs"]
    
    soup = BeautifulSoup(content, "html.parser")
    modified = False
    fixes_made = []
    
    clean_post_url = post_url.split("?")[0]
    
    # 1. FIX BAD ANCHORS
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if domain in href and href != clean_post_url:
            txt = a.get_text(strip=True)
            # check if text is a bad generic anchor
            is_bad = False
            for bad in GENERIC_BAD_ANCHORS:
                if bad.lower() == txt.lower() or (len(txt) < 4 and not txt.isdigit()):
                    is_bad = True
                    break
            if is_bad:
                # Look up destination title from catalog
                dest_post = catalog_by_url.get(href)
                if dest_post:
                    better_anchor = clean_title_for_anchor(dest_post.get("title", ""))
                    if len(better_anchor) >= 5:
                        a.string = better_anchor
                        modified = True
                        fixes_made.append(f"Fixed bad anchor '{txt}' -> '{better_anchor}'")
                        
    # 2. CHECK EXISTING ARTICLE LINKS & PARAGRAPH LINKS
    existing_article_urls = set()
    existing_hub_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if domain in href and href != clean_post_url:
            if re.search(r"/\d{4}/\d{2}/", href):
                existing_article_urls.add(href)
            elif "/p/" in href:
                existing_hub_urls.add(href)

    paragraphs = soup.find_all("p")

    # 3. PROMINENT IN-CONTENT CARD AFTER PARAGRAPH 2
    # Ensure every article has a visible recommendation card right in the top 30% of the text
    has_early_rel = False
    for p in paragraphs[:4]:
        if "ea-rel-link" in p.get("class", []):
            has_early_rel = True
            break

    if not has_early_rel and len(paragraphs) >= 2:
        candidates = select_related_articles(post_url, post_title, post_labels, catalog, limit=2)
        for u, anchor_text in candidates:
            if u not in existing_article_urls and u != clean_post_url:
                callout = soup.new_tag("p", attrs={
                    "class": "ea-rel-link",
                    "style": "background:#f0f7ff;padding:12px 16px;border-right:4px solid #2563eb;border-radius:6px;margin:18px 0;font-size:15px;line-height:1.8;"
                })
                callout.append("💡 ")
                strong = soup.new_tag("strong")
                strong.string = "موضوع يهمك: "
                callout.append(strong)
                callout.append("يمكنك أيضاً قراءة ")
                new_a = soup.new_tag("a", href=u, attrs={"style": "color:#2563eb;font-weight:700;text-decoration:underline;"})
                new_a.string = anchor_text
                callout.append(new_a)
                callout.append(" لمتابعة كافة التفاصيل والتحديثات الرسمية.")
                
                # Insert directly after paragraph 2 (or 1)
                target_p = paragraphs[1] if len(paragraphs) >= 2 else paragraphs[0]
                target_p.insert_after(callout)
                existing_article_urls.add(u)
                modified = True
                fixes_made.append(f"Injected in-text card after P2: '{anchor_text}' -> {u}")
                break

    # 4. IN-TEXT KEYWORD LINKING INSIDE PARAGRAPHS (<p>)
    site_keywords = {
        "review": {
            "مقارنة الهواتف": ("https://www.review-mobile.com/p/compare-phones_01466757070.html", "أداة مقارنة الهواتف الذكية"),
            "أفضل هاتف": ("https://www.review-mobile.com/p/best-phone-for-budget.html", "دليل أفضل هواتف للشراء"),
            "أسعار الهواتف": ("https://www.review-mobile.com/p/mobile-reviews-hub.html", "فهرس مراجعات الهواتف"),
            "هواتف سامسونج": ("https://www.review-mobile.com/2026/11/samsung-galaxy-s25-ultra-leaks-specs.html", "مراجعات هواتف سامسونج"),
            "هواتف أوبو": ("https://www.review-mobile.com/2026/11/oppo-find-x9-ultra-review.html", "مراجعات هواتف أوبو"),
            "هواتف شاومي": ("https://www.review-mobile.com/2026/11/xiaomi-15-ultra-review.html", "مراجعات هواتف شاومي"),
            "هواتف فيفو": ("https://www.review-mobile.com/2026/11/vivo-x200-pro-review.html", "مراجعات هواتف فيفو"),
            "هواتف ريلمي": ("https://www.review-mobile.com/2026/11/realme-gt-7-pro-review.html", "مراجعات هواتف ريلمي"),
        },
        "egyptaway": {
            "أسعار الذهب": ("https://www.egyptaway.com/p/gold-prices-egypt.html", "أسعار الذهب اليوم في مصر"),
            "سعر الذهب": ("https://www.egyptaway.com/p/gold-prices-egypt.html", "أسعار الذهب اليوم"),
            "عيار 21": ("https://www.egyptaway.com/p/gold-prices-egypt.html", "سعر الذهب عيار 21"),
            "سعر الدولار": ("https://www.egyptaway.com/p/currency-prices-egypt.html", "أسعار الدولار والعملات اليوم"),
            "أسعار العملات": ("https://www.egyptaway.com/p/currency-prices-egypt.html", "أسعار العملات في البنوك"),
            "مباريات اليوم": ("https://www.egyptaway.com/p/matches-today.html", "جدول مباريات اليوم والقنوات الناقلة"),
            "الدوري المصري": ("https://www.egyptaway.com/p/egyptian-league-table.html", "جدول ترتيب الدوري المصري"),
            "الإسكان الاجتماعي": ("https://www.egyptaway.com/p/housing-egypt.html", "دليل طروحات الإسكان الاجتماعي"),
            "سكن لكل المصريين": ("https://www.egyptaway.com/p/housing-egypt.html", "طروحات سكن لكل المصريين"),
            "شهادات البنوك": ("https://www.egyptaway.com/p/bank-certificates-egypt.html", "حاسبة أرباح شهادات البنوك"),
            "تحميل الألعاب": ("https://www.egyptaway.com/p/download-games.html", "دليل تحميل الألعاب الرسمية"),
            "أسعار الموبايلات": ("https://www.egyptaway.com/p/mobile-prices-egypt.html", "جدول أسعار الموبايلات في مصر"),
            "ببجي موبايل": ("https://www.egyptaway.com/2026/11/pubg-free-fire-official-topup-egypt-2026.html", "شحن شدات ببجي موبايل"),
            "شحن شدات": ("https://www.egyptaway.com/2026/11/pubg-free-fire-official-topup-egypt-2026.html", "شحن شدات ببجي الرسمية"),
            "فري فاير": ("https://www.egyptaway.com/2026/11/pubg-free-fire-official-topup-egypt-2026.html", "شحن جواهر فري فاير"),
        }
    }

    linked_kws = set()
    paragraphs = soup.find_all("p")
    for p in paragraphs[1:8]:
        if len(linked_kws) >= 2:
            break
        if p.find("a") or "ea-rel-link" in p.get("class", []):
            continue
        p_text = p.get_text()
        for kw, (k_url, k_title) in site_keywords.get(site_key, {}).items():
            if kw in p_text and kw not in linked_kws and k_url != clean_post_url:
                raw_p = str(p)
                new_p_html = raw_p.replace(kw, f'<a href="{k_url}" title="{k_title}" style="color:#2563eb;font-weight:700;text-decoration:underline;">{kw}</a>', 1)
                new_p = BeautifulSoup(new_p_html, "html.parser").find("p")
                p.replace_with(new_p)
                linked_kws.add(kw)
                if k_url.startswith("http"):
                    if "/p/" in k_url:
                        existing_hub_urls.add(k_url)
                    else:
                        existing_article_urls.add(k_url)
                modified = True
                fixes_made.append(f"In-text linked keyword '{kw}' inside paragraph -> {k_url}")
                break

    # 5. IF 0 HUB LINKS, INJECT A RELEVANT HUB LINK
    if len(existing_hub_urls) == 0 and hubs:
        # Pick best hub
        topic = extract_phone_brand_or_topic(post_title, post_labels)
        best_hub = hubs[0]
        if site_key == "egyptaway":
            if any(k in post_title for k in ["ذهب", "صاغة", "عيار"]):
                best_hub = hubs[1] # gold
            elif any(k in post_title for k in ["دولار", "عملات", "صرف"]):
                best_hub = hubs[2] # currency
            elif any(k in post_title for k in ["مباراة", "دوري", "الأهلي", "الزمالك", "كورة"]):
                best_hub = hubs[3] # matches
            elif any(k in post_title for k in ["شهادة", "بنك", "فائدة"]):
                best_hub = hubs[5] # banks
            elif any(k in post_title for k in ["إسكان", "شقق", "سكن لكل المصريين"]):
                best_hub = hubs[6] # housing
            elif any(k in post_title for k in ["لعبة", "تحميل", "العاب", "شحن"]):
                best_hub = hubs[7] # games
            else:
                best_hub = hubs[0] # mobile prices
        hub_url, hub_name = best_hub
        hub_card = soup.new_tag("p", attrs={
            "class": "ea-hub-link",
            "style": "background:#f1f5f9;padding:10px 14px;border-right:4px solid #0f172a;border-radius:6px;margin:16px 0;font-size:14px;"
        })
        hub_card.append("🔍 ")
        h_strong = soup.new_tag("strong")
        h_strong.string = "خدمة مميزة: "
        hub_card.append(h_strong)
        hub_card.append("تفضل بزيارة ")
        ha = soup.new_tag("a", href=hub_url, attrs={"style": "color:#0f172a;font-weight:700;text-decoration:underline;"})
        ha.string = hub_name
        hub_card.append(ha)
        hub_card.append(" للاطلاع على الجداول والتحديثات اليومية الحية.")
        
        soup.append(hub_card)
        existing_hub_urls.add(hub_url)
        modified = True
        fixes_made.append(f"Injected service hub link: '{hub_name}' -> {hub_url}")
        
    return str(soup) if modified else None, fixes_made

def link_new_live_post(site_key, new_post):
    """Automatically called whenever a post is published LIVE.
    1. Ensures new_post has internal links (if not, fixes it).
    2. Reciprocal linking: picks 2 older relevant posts and adds a contextual link pointing to new_post.
    """
    if site_key not in BLOGS:
        return
    blog_id = BLOGS[site_key]["blog_id"]
    new_url = new_post.get("url", "").split("?")[0]
    new_title = new_post.get("title", "")
    new_labels = new_post.get("labels", [])
    new_pid = new_post.get("id")
    
    print(f"\n[Smart Interlinker] Processing new live post: {new_title[:50]}...")
    catalog = load_catalog(site_key)
    catalog_by_url = {p.get("url", "").split("?")[0]: p for p in catalog}
    
    # 1. Verify and fix links in the new post itself if needed
    new_content = new_post.get("content", "")
    fixed_html, fixes = fix_and_interlink_post(new_content, new_url, new_title, new_labels, site_key, catalog_by_url, catalog)
    if fixed_html:
        try:
            api.update_post(blog_id, new_pid, content=fixed_html)
            print("  ✓ Ensured internal links inside the new post itself.")
        except Exception as e:
            print("  Warning updating new post links:", e)
            
    # 2. Reciprocal linking: inject link to new_post in 2 older related posts
    new_anchor = clean_title_for_anchor(new_title)
    related = select_related_articles(new_url, new_title, new_labels, catalog, limit=2)
    
    for r_url, r_title in related:
        try:
            path = urllib.parse.urlparse(r_url).path
            old_post = api.call("GET", f"/blogs/{blog_id}/posts/bypath", {"path": path})
            if not old_post or not old_post.get("id"):
                continue
            old_pid = old_post["id"]
            old_content = old_post.get("content", "")
            
            # check if old post already links to new_url
            if new_url in old_content:
                continue
                
            old_soup = BeautifulSoup(old_content, "html.parser")
            callout = old_soup.new_tag("p", attrs={
                "class": "ea-rel-link",
                "style": "background:#f8fafc;padding:12px 16px;border-right:4px solid #2563eb;border-radius:6px;margin:18px 0;font-size:15px;line-height:1.75;"
            })
            callout.append("💡 ")
            strong = old_soup.new_tag("strong")
            strong.string = "موضوعات ذات صلة: "
            callout.append(strong)
            callout.append("يمكنك أيضاً قراءة ")
            new_a = old_soup.new_tag("a", href=new_url, attrs={"style": "color:#2563eb;font-weight:700;text-decoration:underline;"})
            new_a.string = new_anchor
            callout.append(new_a)
            callout.append(" لمتابعة كافة التفاصيل والتحديثات الرسمية.")
            
            insert_target = old_soup.find("details") or old_soup.find("h3", string=re.compile(r"أسئلة شائعة|المصادر|الأسئلة الشائعة"))
            if insert_target:
                insert_target.insert_before(callout)
            else:
                old_soup.append(callout)
                
            api.update_post(blog_id, old_pid, content=str(old_soup))
            print(f"  ✓ Added reciprocal backlink in: {old_post.get('title')[:45]}")
        except Exception as e:
            print(f"  Warning reciprocal linking {r_url}: {e}")

def run_interlinker(site_key, limit=100, confirm=False):
    blog_id = BLOGS[site_key]["blog_id"]
    domain = BLOGS[site_key]["domain"]
    
    print(f"\n=======================================================")
    print(f"Smart Interlinker for {site_key} ({domain})")
    print(f"Mode: {'CONFIRM (Updating Blogger Live)' if confirm else 'DRY RUN (Preview Only)'}")
    print(f"Targeting: up to {limit} posts")
    print(f"=======================================================")
    
    catalog = load_catalog(site_key)
    catalog_by_url = {p.get("url", "").split("?")[0]: p for p in catalog}
    print(f"Loaded {len(catalog)} live posts in catalog.")
    
    # Fetch posts with bodies
    posts = []
    page_token = None
    while len(posts) < limit:
        params = {
            "status": ["live"],
            "maxResults": min(100, limit - len(posts)),
            "fetchBodies": "true",
            "view": "ADMIN"
        }
        if page_token: params["pageToken"] = page_token
        res = api.call("GET", f"/blogs/{blog_id}/posts", params)
        items = res.get("items", [])
        if not items: break
        posts.extend(items)
        page_token = res.get("nextPageToken")
        if not page_token: break
        
    print(f"Fetched {len(posts)} posts from Blogger for evaluation.")
    
    # Backup before any modification
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today_str = dt.datetime.now(CAIRO).strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"interlink_backup_{site_key}_{today_str}.json"
    
    backups = []
    updated_posts = []
    
    for p in posts:
        pid = p["id"]
        purl = p.get("url", "").split("?")[0]
        ptitle = p.get("title", "")
        plabels = p.get("labels", [])
        pcontent = p.get("content", "")
        
        new_html, fixes = fix_and_interlink_post(pcontent, purl, ptitle, plabels, site_key, catalog_by_url, catalog)
        if not new_html or not fixes:
            continue
            
        print(f"\n[+] {ptitle[:60]} ({purl})")
        for f in fixes:
            print(f"    • {f}")
            
        backups.append({
            "id": pid,
            "url": purl,
            "title": ptitle,
            "content": pcontent,
            "published": p.get("published")
        })
        
        if confirm:
            try:
                res = api.update_post(blog_id, pid, content=new_html)
                if res.get("id"):
                    print("      ✓ Updated successfully on Blogger!")
                    updated_posts.append((pid, purl, ptitle, fixes))
                time.sleep(0.5)
            except Exception as e:
                print(f"      ❌ Error updating on Blogger: {e}")
        else:
            updated_posts.append((pid, purl, ptitle, fixes))
            
    if backups and confirm:
        with open(backup_file, "w", encoding="utf-8") as bf:
            json.dump(backups, bf, ensure_ascii=False, indent=2)
        print(f"\nSaved backup of {len(backups)} modified posts to: {backup_file}")
        
    print(f"\nSummary for {site_key}:")
    print(f"Evaluated: {len(posts)} posts")
    print(f"Modified/Updated: {len(updated_posts)} posts")
    return updated_posts

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Smart Interlinker for Egyptaway & Review")
    parser.add_argument("--site", choices=["review", "egyptaway", "all"], default="review")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    
    sites = ["review", "egyptaway"] if args.site == "all" else [args.site]
    for s in sites:
        run_interlinker(s, limit=args.limit, confirm=args.confirm)
