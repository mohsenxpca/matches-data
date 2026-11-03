# -*- coding: utf-8 -*-
"""محرك الأرشفة اليومي الشامل (Daily Indexing & Crawl Acceleration Engine).

يُشغّل يومياً عبر GitHub Actions (.github/workflows/indexing.yml) في التوقيت الذهبي لعناكب جوجل (04:30 فجراً بتوقيت القاهرة / 02:30 UTC):
1. يجلب المقالات المنشورة حديثاً (آخر 14 يوم) من مدونتي Egyptaway و Review.
2. يرسل جميع الروابط فوراً إلى بروتوكول IndexNow API (Bing, Yandex, Seznam, Naver).
3. يربط المقالات الجديدة بمقالات قديمة مؤرشفة وقوية (Contextual Interlinking Boost) لجذب عناكب Googlebot فوراً وفهرستها بدون تدخل يدوي.
4. يُرسل إشعار Ping لخرائط المواقع (Sitemaps و News Sitemap) لمحركات البحث.
5. يحفظ تقرير الأرشفة اليومي وملفات الدفعات في الريبو.

البيئات والمتغيرات السرية المطلوبة في GitHub Secrets:
BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN
"""

import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CAIRO = ZoneInfo("Africa/Cairo")
NOW_CAIRO = dt.datetime.now(CAIRO)
TODAY = NOW_CAIRO.strftime("%Y-%m-%d")

SITES = {
    "egyptaway": {
        "blog_id": "8325646053257070334",
        "domain": "www.egyptaway.com",
        "host": "https://www.egyptaway.com",
        "indexnow_key": "e3b3e2ee8cd741f59f1b91e73c0f9090",
        "sitemap": "https://www.egyptaway.com/sitemap.xml",
        "news_sitemap": "https://www.egyptaway.com/news-sitemap.xml",
    },
    "review": {
        "blog_id": "2997328666613207792",
        "domain": "www.review-mobile.com",
        "host": "https://www.review-mobile.com",
        "indexnow_key": "e3b3e2ee8cd741f59f1b91e73c0f9090",
        "sitemap": "https://www.review-mobile.com/sitemap.xml",
        "news_sitemap": None,
    }
}


def secret(name):
    return os.environ.get(name, "").strip().strip(",").strip().strip('"').strip("'").strip()


def get_blogger_token():
    cid = secret("BLOGGER_CLIENT_ID")
    csec = secret("BLOGGER_CLIENT_SECRET")
    rtok = secret("BLOGGER_REFRESH_TOKEN")

    if cid and csec and rtok:
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": csec,
                "refresh_token": rtok,
                "grant_type": "refresh_token"
            },
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["access_token"]
        print(f"Warning: OAuth refresh failed with status {r.status_code}: {r.text[:120]}")

    for candidate in [
        r"C:\Users\H\Documents\blogger-pipeline\token.json",
        os.path.join(os.path.dirname(__file__), "token.json"),
        os.path.join(os.path.dirname(__file__), "..", "blogger-pipeline", "token.json")
    ]:
        if os.path.exists(candidate):
            try:
                data = json.load(open(candidate, "r", encoding="utf-8"))
                if "access_token" in data:
                    return data["access_token"]
            except Exception:
                pass

    sys.exit("Error: Could not obtain Blogger API access token. Provide BLOGGER_* secrets.")


_TOKEN_CACHE = {}


def blogger_call(method, path, params=None, body=None):
    tok = _TOKEN_CACHE.get("token")
    if not tok:
        tok = get_blogger_token()
        _TOKEN_CACHE["token"] = tok

    for attempt in range(3):
        try:
            r = requests.request(
                method,
                "https://www.googleapis.com/blogger/v3" + path,
                params=params,
                json=body,
                headers={"Authorization": "Bearer " + tok},
                timeout=60
            )
            if r.status_code == 401 and attempt == 0:
                tok = get_blogger_token()
                _TOKEN_CACHE["token"] = tok
                continue
            return r
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def fetch_live_posts(blog_id, max_posts=150):
    posts = []
    page_token = None
    while len(posts) < max_posts:
        params = {"maxResults": 50, "status": ["live"], "fetchBodies": "true", "view": "ADMIN"}
        if page_token:
            params["pageToken"] = page_token
        res = blogger_call("GET", f"/blogs/{blog_id}/posts", params=params)
        if res.status_code != 200:
            print(f"Blogger fetch error {res.status_code}: {res.text[:100]}")
            break
        items = res.json().get("items", [])
        if not items:
            break
        posts.extend(items)
        page_token = res.json().get("nextPageToken")
        if not page_token:
            break
    return posts


def submit_indexnow(site_cfg, urls):
    if not urls:
        return {}
    payload = {
        "host": site_cfg["domain"],
        "key": site_cfg["indexnow_key"],
        "keyLocation": f"https://{site_cfg['domain']}/{site_cfg['indexnow_key']}.txt",
        "urlList": urls
    }
    results = {}
    for endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
        try:
            r = requests.post(endpoint, json=payload, timeout=30)
            results[endpoint] = r.status_code
        except Exception as e:
            results[endpoint] = str(e)
    return results


def ping_sitemaps(site_cfg):
    sitemaps = [site_cfg["sitemap"]]
    if site_cfg.get("news_sitemap"):
        sitemaps.append(site_cfg["news_sitemap"])

    results = {}
    for sm in sitemaps:
        g_url = f"https://www.google.com/ping?sitemap={urllib.parse.quote(sm)}"
        b_url = f"https://www.bing.com/ping?sitemap={urllib.parse.quote(sm)}"
        try:
            rg = requests.get(g_url, timeout=15)
            results[f"google_{sm}"] = rg.status_code
        except Exception as e:
            results[f"google_{sm}"] = str(e)
        try:
            rb = requests.get(b_url, timeout=15)
            results[f"bing_{sm}"] = rb.status_code
        except Exception as e:
            results[f"bing_{sm}"] = str(e)
    return results


def run_interlinking_boost(site_key, live_posts):
    """ربط أحدث مقالات الموقع بمقالات قديمة مؤرشفة لجذب عناكب جوجل فوراً."""
    two_days_ago = (NOW_CAIRO - dt.timedelta(days=2)).isoformat()
    four_days_ago = (NOW_CAIRO - dt.timedelta(days=4)).isoformat()

    # المقالات الجديدة التي تحتاج تعزيز أرشفة
    fresh_targets = [p for p in live_posts if p.get("published", "") >= two_days_ago][:10]
    # المقالات القديمة المؤرشفة كمرشحين للربط
    older_cands = [p for p in live_posts if four_days_ago >= p.get("published", "") >= "2026-09-01"]

    if not fresh_targets or not older_cands:
        print(f"[{site_key}] لا توجد مقالات كافية لعملية الربط التلقائي.")
        return 0

    blog_id = SITES[site_key]["blog_id"]
    injected_count = 0

    for target in fresh_targets:
        target_url = target.get("url", "")
        target_title = target.get("title", "")
        if not target_url or not target_title:
            continue

        linked_to_target = 0
        for cand in older_cands:
            if linked_to_target >= 2:
                break

            cand_content = cand.get("content", "")
            if target_url in cand_content or target["id"] == cand["id"]:
                continue

            # التحقق من وجود كلمات دلالية مشتركة
            cand_labels = set(cand.get("labels", []))
            target_labels = set(target.get("labels", []))
            if cand_labels and target_labels and not (cand_labels & target_labels):
                continue

            line = f'<p>اقرأ أيضًا: <a href="{target_url}">{target_title}</a></p>'
            # إدراج قبل الأسئلة الشائعة أو المصادر أو في نهاية المقال
            m = re.search(r"<h[23][^>]*>\s*(?:ال)?أسئلة شائعة", cand_content)
            if m:
                new_html = cand_content[:m.start()] + line + "\n" + cand_content[m.start():]
            else:
                new_html = cand_content + "\n" + line

            res = blogger_call("PATCH", f"/blogs/{blog_id}/posts/{cand['id']}", body={"content": new_html})
            if res.status_code == 200:
                print(f"   ✓ [{site_key}] تم ربط ({target_title[:35]}) جوه ({cand.get('title', '')[:35]})")
                linked_to_target += 1
                injected_count += 1
                cand["content"] = new_html
                time.sleep(1)

    return injected_count


def main():
    print(f"=======================================================")
    print(f"  بدء محرك الأرشفة اليومي الشامل (Google & Bing & Yandex)")
    print(f"  التاريخ: {TODAY} | التوقيت: {NOW_CAIRO.strftime('%H:%M')} بتوقيت القاهرة")
    print(f"=======================================================\n")

    summary_lines = [
        f"# تقرير الأرشفة اليومي الشامل — {TODAY}\n",
        f"- **تاريخ وتوقيت التشغيل:** {TODAY} الساعة {NOW_CAIRO.strftime('%H:%M')} (توقيت القاهرة)",
        f"- **الهدف:** تسريع زحف وفهرسة مقالات اليوم والأمس في محركات البحث (Google, Bing, Yandex).\n"
    ]

    for site_key, cfg in SITES.items():
        print(f"--- معالجة موقع {site_key.upper()} ({cfg['domain']}) ---")
        posts = fetch_live_posts(cfg["blog_id"], max_posts=150)
        print(f"تم جلب {len(posts)} مقال منشور من Blogger.")

        recent_posts = [p for p in posts if p.get("published", "")[:10] >= (NOW_CAIRO - dt.timedelta(days=14)).strftime("%Y-%m-%d")]
        recent_urls = [p["url"] for p in recent_posts if p.get("url")]
        print(f"عدد مقالات آخر 14 يوم: {len(recent_urls)} مقال.")

        # 1. IndexNow
        indexnow_res = submit_indexnow(cfg, recent_urls)
        print(f"نتائج IndexNow: {indexnow_res}")

        # 2. Ping Sitemaps
        ping_res = ping_sitemaps(cfg)
        print(f"نتائج Sitemap Ping: {ping_res}")

        # 3. Interlinking Boost
        boost_count = run_interlinking_boost(site_key, posts)
        print(f"عدد الروابط الداخلية المعززة للأرشفة: {boost_count} رابط.")

        summary_lines.append(f"## موقع {site_key.upper()} ({cfg['domain']})")
        summary_lines.append(f"- إجمالي المقالات المفحوصة: {len(posts)} مقال (منها {len(recent_urls)} مقال خلال آخر 14 يوم).")
        summary_lines.append(f"- إرسال IndexNow API: {indexnow_res}")
        summary_lines.append(f"- روابط تعزيز الزحف الداخلي (Interlinks): تم إنشاء {boost_count} رابط جديد لربط المقالات غير المؤرشفة.")
        summary_lines.append(f"- إشعارات خرائط الموقع (Sitemaps Ping): {ping_res}\n")

    # حفظ التقرير في الريبو
    report_path = os.path.join(os.path.dirname(__file__), "indexing_summary.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print("\n=== اكتمل تشغيل محرك الأرشفة اليومي بنجاح! ===")


if __name__ == "__main__":
    main()
