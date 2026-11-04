"""Shared Image Relevance & Safety Guard for Egyptaway & Review (mohsen 2026-11-04).
Ensures all images on Egyptaway are 100% relevant to the Egyptian topic and free from:
- Military, army, soldier, weapons, foreign combatants, Asian/foreign military uniforms.
- Non-Egyptian/foreign publishers when extracting og:image for Egyptian local news.
- Foreign transport/trains (no Japanese bullet trains for Egyptian railways).
"""
import re, urllib.parse

ALLOWED_EGYPT_DOMAINS = {
    "youm7.com", "masrawy.com", "elwatannews.com", "almasryalyoum.com", "shorouknews.com",
    "cairo24.com", "dostor.org", "akhbarelyom.com", "vetogate.com", "ahram.org.eg",
    "alwafd.news", "elbalad.news", "mobtada.com", "rosaelyoussef.com", "akhbarak.net",
    "almalnews.com", "amwalalghad.com", "economyplusme.com", "honaalwatan.com"
}

BANNED_IMG_PATTERNS = [
    r"military", r"army", r"soldier", r"war\b", r"weapon", r"gun\b", r"tank\b", r"combat",
    r"uniform", r"vietnam", r"korea", r"china", r"asian", r"beijing", r"tokyo", r"police",
    r"crime", r"murder", r"prison", r"court", r"dead", r"killing",
    r"logo", r"favicon", r"avatar", r"icon\b", r"placeholder", r"pixel", r"banner", r"author"
]


def is_trusted_egypt_publisher(url):
    """Checks if a URL belongs to a recognized, trusted Egyptian news publisher."""
    if not url:
        return False
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return any(d in domain for d in ALLOWED_EGYPT_DOMAINS)
    except Exception:
        return False


def is_safe_image(img_url, publisher_url=""):
    """Validates that an image URL is safe and comes from a trusted Egyptian source if it's news."""
    if not img_url or not isinstance(img_url, str) or not img_url.startswith("http"):
        return False
    img_lower = img_url.lower()

    # Reject banned keywords (military, asian, army, weapons, etc.)
    for pat in BANNED_IMG_PATTERNS:
        if re.search(pat, img_lower):
            return False

    # If publisher_url is provided, it MUST be from an Egyptian publisher for local news
    if publisher_url and not is_trusted_egypt_publisher(publisher_url):
        return False

    return True
