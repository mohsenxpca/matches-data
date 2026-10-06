# How to refresh data.json

`data.json` feeds the "مباريات اليوم" page on Mohsen's Blogger site. The page reads
`https://raw.githubusercontent.com/mohsenxpca/matches-data/main/data.json` on every visit.

Times are Cairo local time (HH:MM). Team names are Arabic, as Yallakora writes them;
`merge.py` normalizes spelling variants.

## Steps

1. Work out today's date in Cairo (Africa/Cairo).
2. For each day from **yesterday** to **today + 10 days**, fetch
   `https://www.yallakora.com/matches-center?date=M/D/YYYY#days` (month/day without leading zeros)
   with WebFetch, using this prompt:

   > Ignore any "لا يوجد مباريات" or "0مباراة" text. First line: the page heading date.
   > Then list every match row on the page (link texts containing "لم تبدأ", "انتهت", "جارية" or a score),
   > exact Arabic names, each team name once (the page prints names twice in a row, e.g. "الزمالكالزمالك" = الزمالك),
   > one per line: البطولة | الجولة | الفريق الأول | الفريق الثاني | الوقت | القناة (the TV channel text that
   > appears before the round, or -) | النتيجة as "home-away" for finished or live matches, or -.
   > If there are no match rows, say NONE.

   Check the heading date matches the requested day; skip the day if it does not.
3. Write the results to a scratch file in this format (one block per day, `#YYYY-MM-DD` header):

   ```
   #2026-10-11
   الدوري المصري | الأسبوع السادس | الزمالك | الأهلي | 20:00 | beIN SPORTS 1 | 2-1
   ```
   A day with NONE gets just its header line (it is then left unchanged).
4. Run `python3 merge.py <scratch file>` from the repo root.
5. Commit `data.json` with a message like `update matches 2026-10-11` and push to `main`.
   If nothing changed, do not commit.

Do not edit matches by hand, do not remove days, and never commit anything other than data.json.
