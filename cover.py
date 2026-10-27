"""Draw a news cover (1200x675) with the teams' logos and names, in Egyptaway's colors.

make_cover(teams, kicker, out_path) -> True if drawn. teams: list of (name, logo_url) — 1 or 2 items.
Needs Pillow, arabic-reshaper, python-bidi and the Noto Kufi Arabic font (has the Arabic presentation forms the reshaper outputs; Cairo does not) (downloaded once to fonts/).
"""
import io, os
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

W, H = 1200, 675
NAVY, NAVY2, GOLD, ORANGE = (31, 42, 68), (47, 63, 102), (245, 158, 11), (234, 88, 12)
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/notokufiarabic/NotoKufiArabic%5Bwght%5D.ttf"
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoKufiArabic.ttf")


def font(size, weight="Bold"):
    if not os.path.exists(FONT):
        os.makedirs(os.path.dirname(FONT), exist_ok=True)
        open(FONT, "wb").write(requests.get(FONT_URL, timeout=60).content)
    f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.BASIC)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def ar(t):
    return get_display(arabic_reshaper.reshape(t))


def fit(draw, text, max_w, size, weight="Bold"):
    while size > 18:
        f = font(size, weight)
        if draw.textlength(ar(text), font=f) <= max_w:
            return f
        size -= 2
    return font(size, weight)


def logo(url, size):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGBA")
    # white / near-white background -> transparent so it sits nicely on the white disc
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            p = px[x, y]
            if p[0] > 245 and p[1] > 245 and p[2] > 245:
                px[x, y] = (255, 255, 255, 0)
    im.thumbnail((size, size), Image.LANCZOS)
    if im.width < size and im.height < size:  # small logos: upscale gently
        k = size / max(im.width, im.height)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    return im


def disc(img, cx, cy, r, lg):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - r, cy - r + 10, cx + r, cy + r + 10), fill=(0, 0, 0, 110))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r - 7, cy - r - 7, cx + r + 7, cy + r + 7), fill=GOLD)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255))
    if lg is not None:
        img.alpha_composite(lg, (cx - lg.width // 2, cy - lg.height // 2))


def make_cover(teams, kicker, out_path):
    teams = [t for t in teams if t and t[0]][:2]
    if not teams:
        return False
    img = Image.new("RGBA", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(H):  # vertical gradient
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(NAVY[i] * (1 - k) + NAVY2[i] * k) for i in range(3)))
    # pitch lines, very faint
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    o.ellipse((W // 2 - 170, H // 2 - 170, W // 2 + 170, H // 2 + 170), outline=(255, 255, 255, 28), width=4)
    o.line([(W // 2, 0), (W // 2, H)], fill=(255, 255, 255, 28), width=4)
    img.alpha_composite(over)
    # top strip
    d.rectangle((0, 0, W, 64), fill=GOLD)
    d.rectangle((0, 58, W, 64), fill=ORANGE)
    f = fit(d, kicker, W - 80, 34)
    d.text((W // 2, 32), ar(kicker), font=f, fill=NAVY, anchor="mm")
    logos = []
    for name, url in teams:
        try:
            logos.append(logo(url, 190) if url else None)
        except Exception:
            logos.append(None)
    cy = 330
    if len(teams) == 2:
        xs = [W - 300, 300]  # right = first team (RTL)
        for (name, _), lg, x in zip(teams, logos, xs):
            disc(img, x, cy, 135, lg)
            f = fit(d, name, 420, 54)
            d.text((x, cy + 205), ar(name), font=f, fill=(255, 255, 255), anchor="mm")
        d.text((W // 2, cy), "VS", font=font(84, "Black"), fill=GOLD, anchor="mm")
    else:
        disc(img, W // 2, cy - 10, 150, logos[0])
        f = fit(d, teams[0][0], 800, 62)
        d.text((W // 2, cy + 205), ar(teams[0][0]), font=f, fill=(255, 255, 255), anchor="mm")
    # brand
    d.text((W - 30, H - 26), ar("ايجبتاوى"), font=font(30), fill=GOLD, anchor="rm")
    img.convert("RGB").save(out_path, "JPEG", quality=86, optimize=True, progressive=True)
    return True
