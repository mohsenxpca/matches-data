"""Refuse post HTML whose <div>s don't balance before it reaches Blogger.

An extra </div> in a post closes the theme's article/main wrapper early, so the sidebar
drops under the post (Review, 2026-11-04: raw quotes inside an onclick leaked a </div>).
football.api() calls check() on every post create/update, so every engine is covered.
"""
from html.parser import HTMLParser


class _Divs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.low = 0

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "div":
            self.depth -= 1
            self.low = min(self.low, self.depth)


def problem(html):
    """'' when the HTML is safe for the theme, else a short reason."""
    p = _Divs()
    p.feed(html or "")
    p.close()
    if p.low < 0:
        return "extra </div> closes the theme layout (check quotes inside onclick/attributes)"
    if p.depth > 0:
        return f"{p.depth} <div> left open"
    return ""


def check(body, path=""):
    if not isinstance(body, dict) or "/posts" not in path or not body.get("content"):
        return
    why = problem(body["content"])
    if why:
        raise RuntimeError(f"html_guard: refused to send broken post HTML ({why}): {body.get('title', '')[:80]}")
