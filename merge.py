"""Merge freshly fetched Yallakora matches into data.json.

Usage: python3 merge.py fetched.txt

fetched.txt holds one block per day:
    #2026-10-11
    الدوري المصري | الأسبوع السادس | الزمالك | الأهلي | 20:00 | beIN SPORTS 1 | 2-1
Columns: league | round | home | away | time (Cairo, HH:MM) | channel or - | score "home-away" or -
A day block replaces that day's matches when it has at least 60% as many matches as before;
smaller blocks only update/add matches (protects against a partial fetch).
A day block with no match lines is ignored (an empty fetch never wipes a day).
"""
import json, re, sys, datetime

ORD = {"الأول":1,"الأولى":1,"الثاني":2,"الثانية":2,"الثالث":3,"الثالثة":3,"الرابع":4,"الرابعة":4,"الخامس":5,"الخامسة":5,
       "السادس":6,"السادسة":6,"السابع":7,"السابعة":7,"الثامن":8,"الثامنة":8,"التاسع":9,"التاسعة":9,"العاشر":10,"العاشرة":10,
       "الحادي عشر":11,"الثاني عشر":12,"الثالث عشر":13,"الرابع عشر":14,"الخامس عشر":15,"السادس عشر":16,
       "السابع عشر":17,"الثامن عشر":18,"التاسع عشر":19,"العشرون":20,"الحادي والعشرون":21,"الثاني والعشرون":22,
       "الثالث والعشرون":23,"الرابع والعشرون":24,"الخامس والعشرون":25,"السادس والعشرون":26,"السابع والعشرون":27,
       "الثامن والعشرون":28,"التاسع والعشرون":29,"الثلاثون":30,"الحادي والثلاثون":31,"الثاني والثلاثون":32,
       "الثالث والثلاثون":33,"الرابع والثلاثون":34,"الخامس والثلاثون":35,"السادس والثلاثون":36,"السابع والثلاثون":37,"الثامن والثلاثون":38}

NAMES = {
 "أبو قير للاسمدة":"أبو قير للأسمدة","ر.سانتاندير":"راسينج سانتاندير","ايوبسبور":"أيوب سبور",
 "غازي عنتاب بي.بي.كي":"غازي عنتاب","اسبانيول":"إسبانيول","اتلتيكو مدريد":"أتلتيكو مدريد",
 "اشبيلية":"إشبيلية","الانتاج الحربي":"الإنتاج الحربي","اوكسير":"أوكسير","جل فيسنتي":"جيل فيسنتي",
 "لافيينا أف سي":"لافيينا إف سي","تيم اف سي":"تيم إف سي","آ. فرانكفورت":"آينتراخت فرانكفورت",
 "الترجى الرياضي":"الترجي الرياضي","الافريقي التونسي":"الأفريقي التونسي","يانج افريكانز":"يانج أفريكانز",
 "اسكو كارا":"أسكو كارا","أس مانيما يونيون":"مانيما يونيون","ويليت":"ويلييت","السويحلي الرياضي":"السويحلي",
 "كانيمي ويريورز":"كانيمي ووريورز","بريميرو دي اوجوستو":"بريميرو دي أوجوستو","نادي نيوم":"نيوم",
 "زد زد":"زد","زدزد":"زد","أسيك أبيدجان":"أسيك أبيدجان","إسكتلندا":"اسكتلندا","حسنية اغادير":"حسنية أكادير",
 "النجم الساحلى":"النجم الساحلي",
}

def name(s):
    s = re.sub(r"[ـ‏‎]", "", s).strip().replace("نادى ", "نادي ")
    s = re.sub(r"\s+", " ", s)
    return NAMES.get(s, s)

def rnd(r):
    r = re.sub(r"\s+", " ", r.strip())
    m = re.match(r"^(الأسبوع|الجولة) (.+)$", r)
    if m and m.group(2) in ORD:
        return f"{m.group(1)} {ORD[m.group(2)]}"
    return r.replace("ال 32", "الـ32").replace("الـ 32", "الـ32").replace("ال 16", "الـ16").replace("الـ 16", "الـ16")

def score(s):
    s = s.strip().replace(" ", "").replace(":", "-")
    return s if re.match(r"^\d+-\d+$", s) else ""

def parse(path):
    days, day = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            day = line[1:].strip()[:10]
            days.setdefault(day, [])
            continue
        p = [x.strip() for x in line.split("|")]
        if day is None or len(p) < 5:
            continue
        p += ["-"] * (7 - len(p))
        l, r, h, a, t, c, s = p[:7]
        h, a = name(h), name(a)
        if not re.match(r"^\d{1,2}:\d\d$", t) or not h or not a:
            continue
        t = t.zfill(5)
        if c in ("-", "", h, a):
            c = "لم تُعلن"
        days[day].append({"d": day, "t": t, "l": l, "r": rnd(r), "h": h, "a": a, "c": c, "s": score(s)})
    return days

def main():
    data = json.load(open("data.json", encoding="utf-8"))
    fetched = parse(sys.argv[1])
    old = {}
    for m in data["matches"]:
        old.setdefault(m["d"], []).append(m)
    changed = []
    for day, ms in fetched.items():
        if not ms:
            continue
        prev = {(m["h"], m["a"]): m for m in old.get(day, [])}
        for m in ms:
            p = prev.get((m["h"], m["a"]))
            if p:
                if m["c"] == "لم تُعلن" and p.get("c") not in (None, "", "لم تُعلن"):
                    m["c"] = p["c"]        # keep a channel we already knew
                if not m["s"] and p.get("s"):
                    m["s"] = p["s"]        # keep a result we already knew
        prev_list = old.get(day, [])
        if len(ms) >= len(prev_list) * 0.6:
            old[day] = ms                       # full refresh of the day (drops postponed matches)
        else:                                   # looks like a partial fetch: update/add only, drop nothing
            keys = {(m["h"], m["a"]) for m in ms}
            old[day] = [m for m in prev_list if (m["h"], m["a"]) not in keys] + ms
        changed.append(day)
    out = sorted((m for ms in old.values() for m in ms), key=lambda m: (m["d"], m["t"]))
    if out == data["matches"]:
        print("no changes")
        return
    data["matches"] = out
    data["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("updated days:", ", ".join(sorted(changed)) or "none", "| total matches:", len(out))

if __name__ == "__main__":
    main()
