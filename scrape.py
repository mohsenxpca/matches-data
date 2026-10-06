"""Fetch Yallakora's matches center for a range of days and merge into data.json.

Runs on GitHub Actions (see .github/workflows/update.yml). Free, no Claude needed.
Usage: python3 scrape.py [days_back] [days_ahead]      (default 1 and 10)
"""
import re, sys, time, datetime, subprocess
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://www.yallakora.com/matches-center?date={m}/{d}/{y}"
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
        "Accept-Language": "ar,en;q=0.8"}
MONTHS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"]
STATUS = ("لم تبدأ", "انتهت", "جارية", "مؤجلة", "ملغاة", "الشوط", "استراحة")
ROUND = re.compile(r"^(الأسبوع|الجولة|ذهاب|عودة|دور|نصف|ربع|النهائي|المجموعة|مباراة|الدور|تحديد)")
TIME = re.compile(r"^\d{1,2}:\d\d$")

def undouble(s):
    """Yallakora prints names twice: 'الزمالكالزمالك' -> 'الزمالك'."""
    s = s.strip()
    n = len(s)
    if n % 2 == 0 and s[: n // 2] == s[n // 2:]:
        return s[: n // 2].strip()
    h = s.split()
    if len(h) % 2 == 0 and h[: len(h) // 2] == h[len(h) // 2:]:
        return " ".join(h[: len(h) // 2])
    return s

def parse_match(a):
    toks = [t.strip() for t in a.stripped_strings if t.strip()]
    # team names: prefer logo alt texts ("teamlogo X")
    alts = [re.sub(r"(?i)teamlogo", "", i.get("alt", "")).strip() for i in a.find_all("img")]
    alts = [x for x in alts if x]
    t = next((x for x in toks if TIME.match(x)), None)
    nums = [x for x in toks if re.fullmatch(r"\d{1,2}", x)]
    score = f"{nums[0]}-{nums[1]}" if len(nums) >= 2 else ""
    sc = re.search(r"(\d+)\s*-\s*(\d+)", " ".join(toks))
    if not score and sc and not re.search(r"-\s*-\s*-", " ".join(toks)):
        score = f"{sc.group(1)}-{sc.group(2)}"
    rnd = next((x for x in toks if ROUND.match(x)), "")
    status = next((x for x in toks if any(x.startswith(s) for s in STATUS)), "")
    chan = "-"
    if rnd and toks.index(rnd) > 0:
        before = [x for x in toks[: toks.index(rnd)] if not TIME.match(x)]
        if before:
            chan = before[0]
    if len(alts) >= 2:
        h, aw = undouble(alts[0]), undouble(alts[-1])
    else:
        skip = {t, rnd, status, chan, "-"}
        names = [undouble(x) for x in toks if x not in skip and not re.fullmatch(r"[\d\s:-]+", x)
                 and not ROUND.match(x) and not any(x.startswith(s) for s in STATUS) and x != "التفاصيل"]
        uniq = []
        for x in names:
            if x not in uniq:
                uniq.append(x)
        if len(uniq) < 2:
            return None
        h, aw = uniq[0], uniq[-1]
    if not t or not h or not aw or h == aw:
        return None
    if status.startswith("لم تبدأ"):
        score = ""
    return rnd, h, aw, t, chan, score or "-"

def fetch_day(day):
    r = requests.get(URL.format(m=day.month, d=day.day, y=day.year), headers=HEAD, timeout=40)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = soup.find("h1")
    head = h1.get_text(" ", strip=True) if h1 else ""
    if not re.search(rf"\b0?{day.day}\b\s*{MONTHS[day.month - 1]}\s*{day.year}", head):
        print(f"  {day}: page shows a different date ({head!r}), skipped")
        return None
    rows, league, seen = [], "", set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/tour/\d+/", href):
            txt = undouble(a.get_text(" ", strip=True))
            if txt:
                league = txt
        elif "/match/" in href and league:
            m = parse_match(a)
            if m and (m[1], m[2]) not in seen:
                seen.add((m[1], m[2]))
                rows.append(" | ".join([league, *m]))
    return rows

def main():
    back = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ahead = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    today = datetime.datetime.now(ZoneInfo("Africa/Cairo")).date()
    out, total, ok_days = [], 0, 0
    for i in range(-back, ahead + 1):
        day = today + datetime.timedelta(days=i)
        try:
            rows = fetch_day(day)
        except Exception as e:
            print(f"  {day}: fetch failed: {e}")
            rows = None
        if rows is None:
            continue
        ok_days += 1
        total += len(rows)
        print(f"  {day}: {len(rows)} matches")
        out.append(f"#{day.isoformat()}")
        out.extend(rows)
        time.sleep(2)
    open("fetched.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
    if ok_days == 0:
        sys.exit("No day could be read from Yallakora - the site may be blocking or changed its layout.")
    subprocess.run([sys.executable, "merge.py", "fetched.txt"], check=True)

if __name__ == "__main__":
    main()
