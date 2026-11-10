"""Automated Google Web Stories Generator for Egyptaway (news.egyptaway.com).
Runs on GitHub Actions (.github/workflows/stories.yml) or locally.
Pulls recent Egyptaway posts, generates 100% compliant AMP Web Stories,
updates stories_sitemap.xml and portal index.html, then commits/pushes to gh-pages branch.
"""

import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
from bs4 import BeautifulSoup
import requests

try:
    import football as f
except ImportError:
    f = None

BLOG_ID = "8325646053257070334"
SITE_DOMAIN = "www.egyptaway.com"
STORIES_DOMAIN = "news.egyptaway.com"
PUBLISHER_NAME = "ايجبتاوى"
PUBLISHER_LOGO = "https://www.egyptaway.com/favicon.ico"
DEFAULT_AUTHOR = "محسن (رئيس التحرير)"


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_posts_from_blogger(limit=10):
    """Fetch live posts using football credentials or local blogger_api."""
    if f and f.secret("BLOGGER_CLIENT_ID"):
        tok = f.token()
        res = f.api("GET", f"/blogs/{BLOG_ID}/posts", tok, {"status": "live", "maxResults": limit, "fetchBodies": "true", "fetchImages": "true"})
        return res.get("items", [])
    
    # Fallback to local blogger_api
    try:
        import blogger_api
        posts = blogger_api.list_posts(BLOG_ID)[:limit]
        full_posts = []
        for p in posts:
            full_posts.append(blogger_api.get_post(BLOG_ID, p["id"]))
        return full_posts
    except Exception as e:
        print("Error fetching via blogger_api:", e)
        return []


def extract_post_data(post: dict) -> dict:
    title = clean_text(post.get("title", ""))
    url = post.get("url", "").replace("http://", "https://")
    published = post.get("published", datetime.datetime.now(datetime.timezone.utc).isoformat())
    labels = post.get("labels", [])
    content_html = post.get("content", "")

    soup = BeautifulSoup(content_html, "html.parser")
    imgs = []
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "")
        if src and src.startswith("http"):
            imgs.append(src)
    if not imgs and post.get("images"):
        imgs = [img.get("url") for img in post["images"] if img.get("url")]

    poster_img = imgs[0] if imgs else "https://images.pexels.com/photos/3944405/pexels-photo-3944405.jpeg?auto=compress&cs=tinysrgb&w=1000"

    slug_match = re.search(r"/([^/]+)\.html", url)
    slug = slug_match.group(1) if slug_match else re.sub(r"[^a-zA-Z0-9\-]", "-", title.lower())[:40]

    paragraphs = []
    for p_tag in soup.find_all("p"):
        t = clean_text(p_tag.get_text())
        if len(t) >= 40 and not any(k in t for k in ["اضغط هنا", "اقرأ أيضا", "المصادر:", "المصدر:", "تابعنا على"]):
            paragraphs.append(t)

    category = labels[0] if labels else "أخبار عامة"

    slides = []
    hook_text = paragraphs[0] if paragraphs else "تابع تفاصيل وأهم مستجدات الخبر على منصة ايجبتاوى."
    if len(hook_text) > 170:
        hook_text = hook_text[:165].rsplit(" ", 1)[0] + "…"
    slides.append({
        "tag": category,
        "heading": "أبرز تفاصيل الخبر",
        "text": hook_text,
        "img": poster_img,
    })

    fact_text = paragraphs[1] if len(paragraphs) > 1 else hook_text
    if len(fact_text) > 170:
        fact_text = fact_text[:165].rsplit(" ", 1)[0] + "…"
    slide_2_img = imgs[1] if len(imgs) > 1 else poster_img
    slides.append({
        "tag": "تفاصيل ومستجدات",
        "heading": "حقائق وأرقام هامة",
        "text": fact_text,
        "img": slide_2_img,
    })

    if len(paragraphs) > 2:
        analysis_text = paragraphs[2]
        if len(analysis_text) > 170:
            analysis_text = analysis_text[:165].rsplit(" ", 1)[0] + "…"
        slide_3_img = imgs[2] if len(imgs) > 2 else poster_img
        slides.append({
            "tag": "تحليل وسياق",
            "heading": "ما وراء الحدث",
            "text": analysis_text,
            "img": slide_3_img,
        })

    return {
        "id": post.get("id"),
        "title": title,
        "slug": slug,
        "url": url,
        "published": published,
        "category": category,
        "poster_img": poster_img,
        "slides": slides,
    }


def render_amp_story(data: dict) -> str:
    title = html.escape(data["title"])
    category = html.escape(data["category"])
    url = data["url"]
    slug = data["slug"]
    story_canonical = f"https://{STORIES_DOMAIN}/{slug}/"
    poster_img = data["poster_img"]
    published = data["published"]

    pages_html = []
    # 1. Cover
    pages_html.append(f"""    <!-- Cover Page -->
    <amp-story-page id="cover-page">
      <amp-story-grid-layer template="fill">
        <amp-img src="{poster_img}" width="720" height="1280" layout="responsive" alt="{title}"></amp-img>
      </amp-story-grid-layer>
      <amp-story-grid-layer template="vertical" class="layer-overlay">
        <span class="story-tag">{category}</span>
        <h1 class="story-title">{title}</h1>
        <p class="story-sub">ملخص شامل وأبرز النقاط والحقائق خطوة بخطوة</p>
      </amp-story-grid-layer>
    </amp-story-page>""")

    # 2. Slides
    for idx, slide in enumerate(data["slides"], start=1):
        s_tag = html.escape(slide["tag"])
        s_head = html.escape(slide["heading"])
        s_text = html.escape(slide["text"])
        s_img = slide["img"]
        pages_html.append(f"""    <!-- Content Page {idx} -->
    <amp-story-page id="slide-page-{idx}">
      <amp-story-grid-layer template="fill">
        <amp-img src="{s_img}" width="720" height="1280" layout="responsive" alt="{s_head}"></amp-img>
      </amp-story-grid-layer>
      <amp-story-grid-layer template="vertical" class="layer-overlay">
        <span class="story-tag">{s_tag}</span>
        <h2 class="story-heading">{s_head}</h2>
        <p class="story-text">{s_text}</p>
      </amp-story-grid-layer>
    </amp-story-page>""")

    # 3. Final Outlink
    pages_html.append(f"""    <!-- Final Outlink Page -->
    <amp-story-page id="final-page">
      <amp-story-grid-layer template="fill">
        <amp-img src="{poster_img}" width="720" height="1280" layout="responsive" alt="اقرأ المقال كاملاً"></amp-img>
      </amp-story-grid-layer>
      <amp-story-grid-layer template="vertical" class="layer-overlay">
        <span class="story-tag">التغطية الكاملة</span>
        <h2 class="story-heading">اقرأ التقرير الكامل على ايجبتاوى</h2>
        <p class="story-text">للاطلاع على كافة التفاصيل والمستجدات وتحديثات الخبر اضغط على الرابط بالأسفل.</p>
      </amp-story-grid-layer>
      <amp-story-page-outlink layout="nodisplay">
        <a href="{url}" title="اقرأ المقال كاملاً">اضغط لمتابعة التقرير كاملاً على ايجبتاوى</a>
      </amp-story-page-outlink>
    </amp-story-page>""")

    pages_body = "\n\n".join(pages_html)

    schema_ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "mainEntityOfPage": story_canonical,
        "headline": data["title"],
        "image": [poster_img],
        "datePublished": published,
        "dateModified": published,
        "author": {
            "@type": "Person",
            "name": DEFAULT_AUTHOR,
        },
        "publisher": {
            "@type": "Organization",
            "name": PUBLISHER_NAME,
            "logo": {
                "@type": "ImageObject",
                "url": PUBLISHER_LOGO,
            },
        },
    }
    schema_str = json.dumps(schema_ld, ensure_ascii=False, indent=2)

    return f"""<!doctype html>
<html ⚡ lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>{title} | ستوريز ايجبتاوى</title>
  <link rel="canonical" href="{story_canonical}">
  <meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
  <script async src="https://cdn.ampproject.org/v0.js"></script>
  <script async custom-element="amp-story" src="https://cdn.ampproject.org/v0/amp-story-1.0.js"></script>
  <style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
  <style amp-custom>
    amp-story {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #ffffff;
    }}
    amp-story-page {{
      background-color: #0b1329;
    }}
    .layer-overlay {{
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(180deg, rgba(11,19,41,0.15) 0%, rgba(11,19,41,0.7) 50%, rgba(11,19,41,0.96) 100%);
      padding: 24px 20px;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      box-sizing: border-box;
    }}
    .story-tag {{
      align-self: flex-start;
      background: #eab308;
      color: #0b1329;
      font-weight: 800;
      font-size: 13px;
      padding: 4px 14px;
      border-radius: 20px;
      margin-bottom: 12px;
      letter-spacing: 0.3px;
    }}
    .story-title {{
      font-size: 23px;
      font-weight: 800;
      line-height: 1.35;
      margin: 0 0 10px 0;
      color: #ffffff;
      text-shadow: 0 2px 4px rgba(0,0,0,0.6);
    }}
    .story-heading {{
      font-size: 21px;
      font-weight: 700;
      line-height: 1.35;
      margin: 0 0 10px 0;
      color: #ffffff;
      text-shadow: 0 2px 4px rgba(0,0,0,0.6);
    }}
    .story-sub {{
      font-size: 15px;
      line-height: 1.5;
      color: #cbd5e1;
      margin: 0;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }}
    .story-text {{
      font-size: 15.5px;
      line-height: 1.6;
      color: #e2e8f0;
      margin: 0;
      text-shadow: 0 1px 3px rgba(0,0,0,0.8);
    }}
  </style>
  <script type="application/ld+json">
{schema_str}
  </script>
</head>
<body>
  <amp-story standalone
    title="{title}"
    publisher="{PUBLISHER_NAME}"
    publisher-logo-src="{PUBLISHER_LOGO}"
    poster-portrait-src="{poster_img}">
{pages_body}
  </amp-story>
</body>
</html>"""


def build_all(output_dir="out_stories", count=10):
    os.makedirs(output_dir, exist_ok=True)
    posts = fetch_posts_from_blogger(limit=count)
    print(f"Fetched {len(posts)} posts for stories generation...")

    urls = []
    stories = []

    for post in posts:
        try:
            data = extract_post_data(post)
            slug = data["slug"]
            story_dir = os.path.join(output_dir, slug)
            os.makedirs(story_dir, exist_ok=True)
            html_code = render_amp_story(data)
            with open(os.path.join(story_dir, "index.html"), "w", encoding="utf-8") as sf:
                sf.write(html_code)

            lastmod = data["published"][:10]
            stories.append({"slug": slug, "title": data["title"], "poster": data["poster_img"], "tag": data["category"], "lastmod": lastmod})
            urls.append(f"""  <url>
    <loc>https://{STORIES_DOMAIN}/{slug}/</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""")
            print(f"Story created: {data['title'][:50]} -> /{slug}/")
        except Exception as e:
            print("Error generating story for post:", e)

    # 1. Sitemap
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"\n".join(urls)}
</urlset>"""
    with open(os.path.join(output_dir, "stories_sitemap.xml"), "w", encoding="utf-8") as f_sm:
        f_sm.write(sitemap_content)

    # 2. robots.txt
    with open(os.path.join(output_dir, "robots.txt"), "w", encoding="utf-8") as f_rb:
        f_rb.write(f"User-agent: *\nAllow: /\n\nSitemap: https://{STORIES_DOMAIN}/stories_sitemap.xml\n")

    # 3. CNAME & .nojekyll
    with open(os.path.join(output_dir, "CNAME"), "w", encoding="utf-8") as f_cn:
        f_cn.write(STORIES_DOMAIN + "\n")
    with open(os.path.join(output_dir, ".nojekyll"), "w", encoding="utf-8") as f_nj:
        f_nj.write("")

    # 4. Portal Homepage
    cards_html = []
    for s in stories:
        cards_html.append(f"""      <a href="/{s['slug']}/" class="story-card">
        <div class="card-bg" style="background-image: url('{s['poster']}');"></div>
        <div class="card-overlay">
          <span class="card-tag">{s['tag']}</span>
          <h2 class="card-title">{s['title']}</h2>
          <span class="card-date">{s['lastmod']}</span>
        </div>
      </a>""")

    portal_html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>قصص ايجبتاوى المرئية | Google Web Stories</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://{STORIES_DOMAIN}/">
  <link rel="icon" href="{PUBLISHER_LOGO}">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #0b1329;
      color: #ffffff;
      padding: 20px 15px 40px;
    }}
    .header {{ text-align: center; margin-bottom: 30px; padding: 10px 0; }}
    .logo-badge {{ display: inline-block; background: #eab308; color: #0b1329; font-weight: 800; font-size: 13px; padding: 4px 16px; border-radius: 20px; margin-bottom: 10px; }}
    h1 {{ font-size: 26px; font-weight: 800; color: #ffffff; margin-bottom: 8px; }}
    p.sub {{ color: #94a3b8; font-size: 15px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 15px; max-width: 900px; margin: 0 auto; }}
    @media(min-width: 600px) {{ .grid {{ grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }} }}
    .story-card {{ position: relative; display: block; height: 320px; border-radius: 16px; overflow: hidden; text-decoration: none; box-shadow: 0 4px 15px rgba(0,0,0,0.4); transition: transform 0.25s ease, box-shadow 0.25s ease; border: 1px solid rgba(255,255,255,0.08); }}
    .story-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(234, 179, 8, 0.25); }}
    .card-bg {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-size: cover; background-position: center; }}
    .card-overlay {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(180deg, rgba(11,19,41,0.1) 0%, rgba(11,19,41,0.5) 40%, rgba(11,19,41,0.96) 100%); padding: 16px; display: flex; flex-direction: column; justify-content: flex-end; }}
    .card-tag {{ align-self: flex-start; background: #eab308; color: #0b1329; font-weight: 700; font-size: 11px; padding: 3px 10px; border-radius: 12px; margin-bottom: 8px; }}
    .card-title {{ font-size: 15px; font-weight: 700; line-height: 1.35; color: #ffffff; margin-bottom: 6px; }}
    .card-date {{ font-size: 11px; color: #94a3b8; }}
    .footer {{ text-align: center; margin-top: 40px; color: #64748b; font-size: 13px; }}
    .footer a {{ color: #eab308; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="header">
    <span class="logo-badge">ايجبتاوى ستوريز</span>
    <h1>قصص الويب الإخبارية والتفاعلية</h1>
    <p class="sub">تابع أحدث الأخبار والتغطيات البصرية بتنسيق Google Web Stories</p>
  </div>
  <div class="grid">
{"\n".join(cards_html)}
  </div>
  <div class="footer">
    <p>جميع الحقوق محفوظة &copy; 2026 <a href="https://{SITE_DOMAIN}/">ايجبتاوى</a></p>
  </div>
</body>
</html>"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f_idx:
        f_idx.write(portal_html)

    # 5. Legacy news.egyptaway.com Redirects + Smart 404.html
    here_dir = os.path.dirname(os.path.abspath(__file__))
    red_path = os.path.join(here_dir, "news_redirects.json")
    red_count = 0
    if os.path.exists(red_path):
        try:
            with open(red_path, "r", encoding="utf-8") as rf:
                rmap = json.load(rf)
            for old_pth, target_url in rmap.items():
                rel_pth = old_pth.lstrip("/")
                if not rel_pth.endswith(".html") or " " in rel_pth:
                    continue
                full_dest = os.path.join(output_dir, *rel_pth.split("/"))
                os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                r_html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>جاري التحويل إلى ايجبتاوى...</title>
  <link rel="canonical" href="{target_url}">
  <meta name="robots" content="noindex, follow">
  <meta http-equiv="refresh" content="0; url={target_url}">
  <script>window.location.replace("{target_url}");</script>
</head>
<body>
  <p>تم نقل الصفحة إلى: <a href="{target_url}">{target_url}</a></p>
</body>
</html>"""
                with open(full_dest, "w", encoding="utf-8") as wf:
                    wf.write(r_html)
                red_count += 1
        except Exception as e:
            print("Error writing legacy news redirects:", e)

    fallback_404 = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>ايجبتاوى</title>
  <link rel="canonical" href="https://{SITE_DOMAIN}/">
  <meta name="robots" content="noindex, follow">
  <meta http-equiv="refresh" content="0; url=https://{SITE_DOMAIN}/">
  <script>window.location.replace("https://{SITE_DOMAIN}/");</script>
</head>
<body>
  <p>جاري التحويل إلى <a href="https://{SITE_DOMAIN}/">ايجبتاوى</a>...</p>
</body>
</html>"""
    with open(os.path.join(output_dir, "404.html"), "w", encoding="utf-8") as f_404:
        f_404.write(fallback_404)

    print(f"Generated {len(stories)} stories, {red_count} legacy redirects, 404.html, sitemap, and portal homepage in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--out", type=str, default="out_stories")
    args = parser.parse_args()
    build_all(output_dir=args.out, count=args.count)
