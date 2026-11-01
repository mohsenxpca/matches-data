"""Allow-list check for the trends engines (mohsen 2026-11-01).

The keyword ban lists (BANNED_TOPICS_REGEX) are Arabic and miss stories like a celebrity's Halloween party or a US tax
proposal that trend in Egypt/Saudi, so before writing, Gemini sorts the story into one of the site's sections and anything
else is skipped. Allowed (AGENTS.md, 2026-10-31): tech & phones, games, football & sports, the site's service topics
(gold, currencies, weather, prayer, trains, holidays, salaries, exams, housing, banks, fuel, outages) and money-making /
tech how-tos. If Gemini can't answer, the story is skipped too.
"""
import football as f

ALLOWED = {"tech", "phones", "games", "sports", "services", "money"}

PROMPT = """صنّف الخبر ده في قسم واحد بس من دول:
tech = تكنولوجيا وإنترنت وتطبيقات وذكاء اصطناعي
phones = موبايلات وأجهزة
games = ألعاب فيديو
sports = كورة ورياضة
services = خدمات للمواطن في مصر أو الخليج: الذهب، العملات، الطقس، الصلاة، القطارات والمترو، الإجازات الرسمية، المرتبات والمعاشات، الامتحانات والنتائج، الإسكان، البنوك، الوقود، أعطال الخدمات، تغيير الساعة
money = طرق الربح من الإنترنت وشروحات تقنية
other = أي حاجة تانية: سياسة، حكومات وانتخابات وضرايب وقوانين في دول تانية، حروب، فن وغناء ورقص ومشاهير وموضة وحفلات، جرايم وحوادث، دين، منوعات

رجّع JSON بالشكل ده بس: {{"cat": "..."}}

العنوان: {title}
النص: {text}
"""


def allowed(title, text=""):
    res = f.gemini(PROMPT.format(title=title, text=(text or "")[:1500])) or {}
    cat = str(res.get("cat", "")).strip().lower()
    if cat not in ALLOWED:
        print(f"  topic_guard: '{title[:60]}' -> {cat or 'no answer'}, skipped")
        return False
    return True
