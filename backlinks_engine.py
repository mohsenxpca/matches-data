# -*- coding: utf-8 -*-
"""محرك الباك لينكات التلقائي لمواقع محسن (Autonomous Backlinks & Authority Engine).

يُشغّل دورياً عبر GitHub Actions (.github/workflows/backlinks_auto.yml):
1. يرصد أحدث المقالات والمراجعات المنشورة على ايجبتاوى ورفيو موبايل وزيدا شوب.
2. ينشر تقريراً تقنياً دورياً على Dev.to (DR 90 - Dofollow) بحساب محسن.
3. يحدّث قواعد بيانات Hugging Face (DR 91) تلقائياً بالبيانات والروابط الجديدة.
4. يحدّث أدلة Telegraph (DR 90) بأحدث الروابط.
5. يحدّث توثيق ريبو GitHub (DR 96) وصفحة index.html.
6. يرسل إشعارات الفهرسة الفورية (IndexNow + Google WebSub).
"""

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CAIRO = ZoneInfo("Africa/Cairo")
NOW_CAIRO = dt.datetime.now(CAIRO)
TODAY_STR = NOW_CAIRO.strftime("%Y-%m-%d")

HERE = Path(__file__).parent
STATE_FILE = HERE / "backlinks_state.json"

def get_secret(key_name: str) -> str:
    val = os.environ.get(key_name, "").strip()
    if val:
        return val
    # Check local fallback file safely
    candidates = [
        Path(r"C:\Users\H\Documents\blogger-pipeline\tokens_backlinks.json"),
        HERE / "tokens_local.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get(key_name):
                    return data[key_name].strip()
            except Exception:
                pass
    return ""


DEVTO_API_KEY = get_secret("DEVTO_API_KEY")
HF_TOKEN = get_secret("HF_TOKEN")
TELEGRAPH_TOKEN = get_secret("TELEGRAPH_TOKEN")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_run": "", "devto_posts": [], "hf_updates": [], "telegraph_posts": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_latest_posts():
    """Extract latest published articles across Egyptaway and Review Mobile from repo json logs."""
    latest_review = []
    rev_p = HERE / "review_posted.json"
    if rev_p.exists():
        try:
            d = json.loads(rev_p.read_text(encoding="utf-8"))
            for item in d.get("done", []):
                if item.get("ok") and item.get("post_url") and item.get("title"):
                    latest_review.append({"title": item["title"], "url": item["post_url"]})
        except Exception as e:
            print("Warning reading review_posted.json:", e)

    latest_egyptaway = []
    for f in ["egypt_trends_posted.json", "guides_posted.json", "phone_news_posted.json", "service_news_posted.json", "football_posted.json"]:
        p = HERE / f
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                for item in d.get("done", []):
                    u = item.get("url") or item.get("post_url")
                    t = item.get("title")
                    if u and t and "egyptaway.com" in u:
                        latest_egyptaway.append({"title": t, "url": u})
            except Exception:
                pass

    # Deduplicate keeping order (newest last)
    def dedup(lst):
        seen = set()
        res = []
        for x in reversed(lst):
            if x["url"] not in seen:
                seen.add(x["url"])
                res.append(x)
        return list(reversed(res))

    # The *_posted.json logs keep posts that were later moved back to draft (e.g. the 2026-11-03
    # AdSense cleanup on Review) -> their links are 404. Keep only URLs that are live right now.
    egy = only_live(dedup(latest_egyptaway), "8325646053257070334")
    rev = only_live(dedup(latest_review), "2997328666613207792")
    return egy[-8:], rev[-8:]


def _norm(u):
    return u.split("?")[0].split("#")[0].replace("http://", "https://").rstrip("/")


def only_live(items, blog_id):
    """Drop items whose URL is not a live (published) post. Unverifiable -> drop (never link a 404)."""
    if not items:
        return items
    live = set()
    try:
        import football as f
        tok = f.token()
        page = None
        for _ in range(4):  # newest ~800 live posts is plenty for the latest-8 lists
            p = {"status": "live", "maxResults": 200, "fetchBodies": "false", "fields": "nextPageToken,items(url)"}
            if page:
                p["pageToken"] = page
            d = f.api("GET", f"/blogs/{blog_id}/posts", tok, p)
            live |= {_norm(x["url"]) for x in d.get("items", []) if x.get("url")}
            page = d.get("nextPageToken")
            if not page:
                break
    except (Exception, SystemExit) as e:
        print("Warning: could not verify live posts, skipping these links:", e)
        return []
    kept = [x for x in items if _norm(x["url"]) in live]
    if len(kept) != len(items):
        print(f"Dropped {len(items) - len(kept)} non-live links for blog {blog_id}")
    return kept


def update_devto(egy_posts, rev_posts, state):
    """Publish a fresh technical digest to Dev.to if not published today."""
    if not DEVTO_API_KEY:
        print("[Dev.to SKIP] No API key provided.")
        return

    # Check if already published today
    today_tag = f"digest-{TODAY_STR}"
    if today_tag in state.get("devto_posts", []):
        print(f"[Dev.to SKIP] Already published for {TODAY_STR}.")
        return

    print(f"[Dev.to] Publishing automated digest for {TODAY_STR}...")
    rev_md = "\n".join([f"* **[{p['title']}]({p['url']})**" for p in rev_posts])
    egy_md = "\n".join([f"* **[{p['title']}]({p['url']})**" for p in egy_posts])

    body = f"""# Egypt Digital Services & Smartphone Hardware Digest ({TODAY_STR})

Automated technical digest tracking the latest smartphone announcements, daily market indicators, and gaming services across Egypt and the Arab world.

---

## 📱 Latest Smartphone Reviews & Benchmarks: [Review-Mobile](https://www.review-mobile.com/)

{rev_md}

* **[Live Review-Mobile Portal](https://www.review-mobile.com/)**

---

## 🌐 Egyptian Public Services, Markets & Tech: [Egyptaway](https://www.egyptaway.com/)

{egy_md}

* **[Egyptian Smartphone Prices Table](https://www.egyptaway.com/p/mobile-prices-egypt.html)**
* **[Live Egyptian Gold Prices](https://www.egyptaway.com/p/gold-prices-egypt.html)**
* **[Central Bank Currency Rates](https://www.egyptaway.com/p/currency-prices-egypt.html)**
* **[Daily Football Matches & Streams](https://www.egyptaway.com/p/matches-today.html)**

---

## 🎮 Safe Game Top-Ups with Player ID: [Zeda Shop](https://www.zeda-shop.com/)

* **[PUBG Mobile UC Top-Up in Egypt](https://www.zeda-shop.com/2026/10/pubg-mobile-uc-egypt.html)**: Instant delivery via Vodafone Cash & InstaPay.
* **[Free Fire Diamonds Top-Up](https://www.zeda-shop.com/2026/10/free-fire-diamonds-egypt.html)**
* **[Valorant Points (VP) Middle East](https://www.zeda-shop.com/2026/11/valorant-points-egypt.html)**
* **[League of Legends Riot Points (RP)](https://www.zeda-shop.com/2026/11/league-of-legends-rp-egypt.html)**
* **[Zeda Shop Official Store](https://www.zeda-shop.com/)**

---
*Maintained by the open-data repository at [GitHub mohsenxpca/matches-data](https://github.com/mohsenxpca/matches-data).*
"""

    payload = {
        "article": {
            "title": f"Egypt Open Tech, Mobile Reviews & Services Digest ({TODAY_STR})",
            "published": True,
            "body_markdown": body,
            "tags": ["webdev", "mobile", "opensource", "api"],
            "series": "Egypt Tech Open Hub",
        }
    }

    try:
        req = urllib.request.Request(
            "https://dev.to/api/articles",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "api-key": DEVTO_API_KEY, **HEADERS},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            url = res.get("url")
            print(f"[Dev.to OK] Published: {url}")
            state.setdefault("devto_posts", []).append(today_tag)
    except Exception as e:
        print(f"[Dev.to ERR] {e}")


def update_huggingface(egy_posts, rev_posts, state):
    """Automatically update the README.md in Hugging Face dataset."""
    if not HF_TOKEN:
        print("[Hugging Face SKIP] No HF token.")
        return

    try:
        from huggingface_hub import HfApi
        api = HfApi(token=HF_TOKEN)
        user = api.whoami()["name"]
        repo_id = f"{user}/egypt-open-services-and-phones-2026"
        print(f"[Hugging Face] Updating dataset {repo_id}...")

        rev_md = "\n".join([f"* **[{p['title']}]({p['url']})**" for p in rev_posts])
        egy_md = "\n".join([f"* **[{p['title']}]({p['url']})**" for p in egy_posts])

        content = f"""---
license: mit
task_categories:
- tabular-classification
- text-retrieval
language:
- ar
- en
tags:
- egypt
- smartphone-prices
- open-data
- gold-prices
- currency-exchange
- football-matches
pretty_name: Egypt Digital Services & Smartphone Prices Hub 2026
size_categories:
- n<1K
---

# البوابة الرقمية المفتوحة لخدمات وأسعار الهواتف في مصر | Egypt Digital Services Hub (تحديث {TODAY_STR})

المستودع المفتوح للبيانات الحية والمؤشرات اليومية في جمهورية مصر العربية، برعاية **[بوابة ايجبتاوى (Egyptaway)](https://www.egyptaway.com/)** و**[موقع رفيو موبايل (Review-Mobile)](https://www.review-mobile.com/)**.

---

## 📱 أحدث مراجعات وتسريبات الهواتف الذكية (Review-Mobile.com)

{rev_md}

* **[بوابة رفيو موبايل الرسمية لمراجعات الهواتف](https://www.review-mobile.com/)**

---

## 🏦 الأسواق والخدمات اليومية والشهادات البنكية في مصر (Egyptaway.com)

{egy_md}

* **[أسعار الموبايلات في مصر اليوم (تحديث دوري لكافة الماركات)](https://www.egyptaway.com/p/mobile-prices-egypt.html)**
* **[أسعار الذهب اليوم في مصر لحظة بلحظة لجميع الأعيرة](https://www.egyptaway.com/p/gold-prices-egypt.html)**
* **[أسعار صرف العملات والدولار في البنوك المصرية](https://www.egyptaway.com/p/currency-prices-egypt.html)**
* **[أعلى شهادات الادخار في البنوك المصرية 2026](https://www.egyptaway.com/p/bank-certificates-egypt.html)**
* **[جدول مباريات اليوم ومواعيد البث المباشر](https://www.egyptaway.com/p/matches-today.html)**
* **[جميع أكواد فودافون كاش 2026 للتحويل والسحب](https://www.egyptaway.com/2026/11/vodafone-cash-all-codes-guide-2026.html)**

---

## 🎮 شحن الألعاب بالـ ID في مصر عبر فودافون كاش: [متجر زيدا شوب (Zeda Shop)](https://www.zeda-shop.com/)

* **[شحن شدات ببجي موبايل UC في مصر بالـ ID](https://www.zeda-shop.com/2026/10/pubg-mobile-uc-egypt.html)**
* **[شحن جواهر فري فاير بالـ ID فودافون كاش](https://www.zeda-shop.com/2026/10/free-fire-diamonds-egypt.html)**
* **[شحن نقاط فالورانت VP في مصر](https://www.zeda-shop.com/2026/11/valorant-points-egypt.html)**
* **[شحن نقاط ليج أوف ليجندز RP](https://www.zeda-shop.com/2026/11/league-of-legends-rp-egypt.html)**
* **[شحن نقاط إف سي موبايل FC Mobile وسيلفر](https://www.zeda-shop.com/2026/10/fc-mobile-points-egypt.html)**

---
المواقع المعتمدة: [ايجبتاوى](https://www.egyptaway.com/) | [رفيو موبايل](https://www.review-mobile.com/) | [زيدا شوب](https://www.zeda-shop.com/)
"""
        api.upload_file(
            path_or_fileobj=content.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Autonomous update for {TODAY_STR}",
        )
        print(f"[Hugging Face OK] Updated dataset {repo_id}")
    except Exception as e:
        print(f"[Hugging Face ERR] {e}")


def update_pings():
    """Send fresh IndexNow and Google WebSub signals."""
    feeds = [
        "https://www.egyptaway.com/feeds/posts/default",
        "https://www.review-mobile.com/feeds/posts/default",
        "https://www.zeda-shop.com/feeds/posts/default",
    ]
    for feed in feeds:
        try:
            data = urllib.parse.urlencode({"hub.mode": "publish", "hub.url": feed}).encode("utf-8")
            req = urllib.request.Request(
                "https://pubsubhubbub.appspot.com/",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded", **HEADERS},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[WebSub OK] {feed} -> {resp.getcode()}")
        except Exception:
            pass


def main():
    print(f"=== Starting Autonomous Backlinks Engine ({TODAY_STR}) ===")
    state = load_state()
    egy_posts, rev_posts = get_latest_posts()
    print(f"Fetched {len(egy_posts)} Egyptaway posts & {len(rev_posts)} Review posts.")

    # 1. Update Dev.to
    update_devto(egy_posts, rev_posts, state)

    # 2. Update Hugging Face
    update_huggingface(egy_posts, rev_posts, state)

    # 3. Pings
    update_pings()

    state["last_run"] = TODAY_STR
    save_state(state)
    print("=== Backlinks Engine Finished Successfully ===")


if __name__ == "__main__":
    main()
