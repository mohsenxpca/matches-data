"""'Result of X vs Y' posts right after big matches end (mohsen 2026-10-28), every 20 minutes on GitHub Actions (results.yml).

Uses the scores that live.yml writes into data.json every 5 minutes. A match counts as finished ~2h20m after kick-off
(extra time / delays). Only matches with a big team (football.BIG), at most 2 per run, published within minutes.
Facts given to Gemini: the final score, competition/round, the teams' previous results, next fixtures and the league table
when available; no scorers or minutes (we don't have them), so the prompt forbids them.
Env: DAY_CAP (default 30), DRY_RUN=1.
"""
import datetime, html, json, os, random
import football as f

f.DAY_CAP = int(os.environ.get("DAY_CAP") or 30)
DONE_AFTER = datetime.timedelta(minutes=140)

RESULT_PROMPT = """أنت محرر رياضي في موقع ايجبتاوى المصري. الماتش ده لسه خلصان، اكتب مقال «نتيجة المباراة» سريع ومفيد.

قواعد صارمة:
- استخدم «بيانات الماتش» تحت بس. ممنوع تخترع أسماء هدافين أو دقايق أهداف أو تشكيل أو تصريحات أو إحصائيات مش مكتوبة تحت.
- اكتب كل الأرقام بالأرقام (2-1، 21 نقطة)، مش بالحروف.
- ممنوع تذكر اسم أي موقع.
- لو معلومة مش موجودة تحت (زي آخر نتايج فريق) تجاهلها خالص، وما تكتبش إن البيانات ناقصة أو مش متاحة.
- لو النتيجة تعادل في كأس أو أدوار إقصائية، ما تقولش مين اتأهل ولا تذكر ركلات ترجيح، لأن البيانات مش فيها ده.
- العنوان لازم يبدأ بـ «نتيجة مباراة» وفيه اسم الفريقين والنتيجة.
- المحتوى: النتيجة النهائية ومين كسب أو التعادل، البطولة والجولة، معنى النتيجة للفريقين (موقفهم في الجدول لو موجود، وآخر نتايجهم المكتوبة تحت)، والماتش الجاي لكل فريق لو موجود تحت بموعده وقناته.
- الطول: الـ body من 400 لـ 650 كلمة، بعناوين h2 (من 3 لـ 5) وفقرات <p>. من غير صور ومن غير روابط.

رجّع JSON بالشكل ده بالظبط:
{{"title": "نتيجة مباراة .. أقل من 65 حرف", "kicker": "3-5 كلمات زي: الدوري المصري · الجولة 8", "slug": "3 to 6 english words with hyphens ending with result", "desc": "وصف للبحث من 140 لـ 160 حرف", "body": "<h2>..</h2><p>..</p>...", "faq": [{{"q": "نتيجة ماتش .. كام؟", "a": ".."}}, {{"q": "..", "a": ".."}}, {{"q": "..", "a": ".."}}]}}
{extra}
بيانات الماتش:
{facts}
"""


def finished(data, done, now):
    out = []
    for m in data.get("matches", []):
        if not m.get("s") or "-" not in m["s"]:
            continue
        try:
            ko = datetime.datetime.fromisoformat(f"{m['d']}T{m['t']}").replace(tzinfo=f.CAIRO)
        except Exception:
            continue
        if not (ko + DONE_AFTER <= now <= ko + datetime.timedelta(hours=12)):
            continue
        key = f"{m['d']}|{m['h']}|{m['a']}|r"
        rank = min([f.BIG.index(t) for t in (m["h"], m["a"]) if t in f.BIG] or [99])
        if key not in done and rank < 99:
            out.append((rank, key, m))
    return [(k, m) for _, k, m in sorted(out)]


def next_match(team, data, after):
    rows = [x for x in data.get("matches", []) if team in (x["h"], x["a"]) and x["d"] > after and not x.get("s")]
    rows.sort(key=lambda x: (x["d"], x["t"]))
    if not rows:
        return "مش متاح"
    x = rows[0]
    return f"{x['h']} × {x['a']} ({x['l']}) يوم {x['d']} الساعة {x['t']} على {x.get('c') or 'قناة لم تُعلن'}"


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    data = json.load(open("data.json", encoding="utf-8"))
    try:
        state = json.load(open("results_posted.json", encoding="utf-8"))
    except Exception:
        state = {"results": []}
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()
    cands = finished(data, set(state.get("results", [])), now)[:2]
    if not cands:
        print("no finished big match to cover")
        return
    tok = f.token()  # the public feed is blocked for GitHub runners, so even a dry run reads posts via the API
    existing = [p["t"] for p in f.site_posts(tok)]
    taken = []
    if not dry:
        sched = f.api("GET", f"/blogs/{f.BLOG}/posts", tok, {"status": ["live", "scheduled"], "fetchBodies": "false",
                                                            "startDate": today + "T00:00:00+02:00", "maxResults": 60, "view": "ADMIN"})
        for it in sched.get("items", []):
            try:
                taken.append(datetime.datetime.fromisoformat(it["published"]).astimezone(f.CAIRO))
            except Exception:
                pass
        if len([t for t in taken if t.date().isoformat() == today]) >= f.DAY_CAP:
            print("daily cap reached")
            return
    when = now + datetime.timedelta(minutes=3)
    for key, m in cands:
        if f._DOWN:
            break
        facts = f.match_facts(m, data) + f"\nالنتيجة النهائية: {m['h']} {m['s']} {m['a']}" + \
            f"\nالماتش الجاي لـ {m['h']}: {next_match(m['h'], data, m['d'])}\nالماتش الجاي لـ {m['a']}: {next_match(m['a'], data, m['d'])}"
        extra, art, errs = "", None, ["no draft"]
        for _ in range(2):
            art = f.gemini(RESULT_PROMPT.format(extra=extra, facts=facts))
            errs = f.check(art, facts, facts, existing, min_words=250)
            if not errs:
                break
            print("  retry:", errs)
            extra = "\nتصحيحات لازم تتعمل في النسخة دي: " + " | ".join(errs) + "\n"
        tries = state.setdefault("tries", {})
        tries[key] = tries.get(key, 0) + 1
        if errs:
            print("RESULT SKIPPED", key, errs, "| try", tries[key])
            if tries[key] >= 3:  # give up after 3 runs (the writer model may just be busy for a while)
                state.setdefault("results", []).append(key)
            continue
        state.setdefault("results", []).append(key)
        rows = f.team_matches(m["h"] + " " + m["a"], data)
        p = f"img/{art['slug']}.jpg"
        team_tuples = [(m["h"], f.TEAM_LOGOS.get(m["h"])), (m["a"], f.TEAM_LOGOS.get(m["a"]))]
        bg_url = f.PEX.format(i=random.choice(f.IMAGES)[0])
        lead_img_url = None
        if f.make_club_logo_cover(team_tuples, bg_url, p):
            lead_img_url = f.CDN + p
        else:
            lead_img_url = bg_url
        html_out = f.build_html(art, rows, random.choice(f.IMAGES), None, (), real_img_url=lead_img_url)
        labels = ["أخبار الكورة", "نتائج المباريات"] + (["الدوري المصري"] if m["l"] == "الدوري المصري" else [])
        if dry:
            print("DRY RESULT", art["title"], "|", art["desc"])
        else:
            when = max(when, datetime.datetime.now(f.CAIRO) + datetime.timedelta(minutes=2))
            fin = f.schedule(tok, art, html_out, labels, when)
            print("RESULT SCHEDULED", when.strftime("%H:%M"), fin.get("url"), "|", art["title"])
            when += datetime.timedelta(minutes=25)
        existing.append(art["title"])
    state["results"] = state.get("results", [])[-300:]
    state["tries"] = dict(list(state.get("tries", {}).items())[-100:])
    if not dry:
        json.dump(state, open("results_posted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
