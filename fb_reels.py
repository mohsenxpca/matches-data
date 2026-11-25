"""Automated Daily Facebook Page Reels Generator & Publisher for «موبايل بالعربى».

Features requested by Mohsen (2026-11-25):
1. Publishes 2 Reels per day at peak Facebook Reels viewing hours in Egypt/Arab World:
   - Slot 1 (Afternoon Peak): 14:00 - 16:30 Cairo time
   - Slot 2 (Evening Prime Peak): 20:30 - 23:00 Cairo time
2. Multi-slide vertical 9:16 (1080x1920) dynamic phone news video (~17s, 30fps, H.264 + AAC):
   - Uses clean, un-watermarked phone photos (zero 'رفيو' or third-party logos) + adaptive «موبايل بالعربى» calligraphy logo.
   - 4 professionally designed Arabic slides (Hook -> Highlight 1 -> Highlight 2 -> Provocative Debate CTA) with smooth transitions.
   - Prioritizes Samsung phones, Samsung apps & One UI updates first.
3. 100% Original Copyright-Free Synthesized Music:
   - Mathematically synthesized modern tech/lo-fi stereo music in numpy/wave (4 rotating keys/moods).
   - Zero external MP3s, zero third-party samples -> 0% chance of Facebook copyright mute or Rights Manager claim!
4. Publishes directly via Official Facebook Page Reels Graph API (/{page_id}/video_reels).

Usage:
  python fb_reels.py                                 # Auto mode (respects peak slots & 2/day cap)
  python fb_reels.py --dry --out local_test_reel.mp4 # Render a local preview MP4 without publishing
  python fb_reels.py --force                         # Publish 1 Reel immediately (bypass slot/cap)
"""
import argparse, colorsys, datetime, hashlib, html, io, json, math, os, re, shutil, subprocess, sys, tempfile, wave
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
import football as f
import fb_phones as fbp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAMP_START_DATE = datetime.date(2026, 11, 25)


def _get_daily_reel_policy(today_date):
    """Automatic 3-stage Reels ramp-up requested by Mohsen (2026-11-25):
       - Week 1 (2026-11-25 .. 2026-12-01): 2 Reels/day (Afternoon 14:00 & Evening 21:00)
       - Week 2 (2026-12-02 .. 2026-12-08): 3 Reels/day (14:00, 17:00, 21:30)
       - Week 3+ (from 2026-12-09 forever): 5 Reels/day (11:00, 14:00, 17:00, 20:00, 22:30)
    """
    days_elapsed = (today_date - RAMP_START_DATE).days
    if days_elapsed < 7:
        return 2, 240, [(13, 17), (20, 23)], "Stage 1 (Week 1: 2 Reels/day)"
    elif days_elapsed < 14:
        return 3, 165, [(12, 16), (16, 20), (20, 24)], "Stage 2 (Week 2: 3 Reels/day)"
    else:
        return 5, 130, [(10, 24)], "Stage 3 (Permanent: 5 Reels/day)"


def _find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def synthesize_copyright_free_music(out_wav_path, duration_sec=17.5, seed_str="default"):
    """Synthesizes a 100% original, royalty-free, zero-copyright modern tech/lo-fi stereo music track."""
    sr = 44100
    n = int(sr * duration_sec)
    t = np.linspace(0.0, duration_sec, n, endpoint=False, dtype=np.float32)

    # 4 distinct chord progressions (frequencies in Hz) so every Reel sounds fresh
    progressions = [
        # Deep Modern Tech (A minor: Am - F - C - G)
        [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)],
        # Smooth Synth Chill (D minor: Dm - Bb - F - C)
        [(146.83, 220.0, 261.63), (116.54, 174.61, 233.08), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63)],
        # Crisp Digital Pulse (E minor: Em - C - G - D)
        [(164.81, 246.94, 329.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66), (146.83, 220.0, 293.66)],
        # Sleek Ambient Lo-Fi (C minor: Cm - Ab - Eb - Bb)
        [(130.81, 155.56, 196.0), (103.83, 155.56, 207.65), (155.56, 196.0, 233.08), (116.54, 174.61, 233.08)],
    ]
    seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    chords = progressions[seed_int % len(progressions)]
    bpm = [104, 108, 112, 100][seed_int % 4]
    beat_dur = 60.0 / bpm
    bar_dur = beat_dur * 4.0

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    # 1. Warm Stereo Pad Chords + Sub-Bass
    total_bars = int(math.ceil(duration_sec / bar_dur))
    for bar in range(total_bars):
        chord = chords[bar % len(chords)]
        start_s = int(bar * bar_dur * sr)
        end_s = min(n, int((bar + 1) * bar_dur * sr))
        if start_s >= n:
            break
        seg_len = end_s - start_s
        tt = np.linspace(0.0, seg_len / sr, seg_len, endpoint=False, dtype=np.float32)
        # Smooth chord envelope
        atk = min(seg_len, int(0.18 * sr))
        rel = min(seg_len, int(0.25 * sr))
        env = np.ones(seg_len, dtype=np.float32)
        if atk > 0:
            env[:atk] = np.linspace(0.0, 1.0, atk, dtype=np.float32)
        if rel > 0:
            env[-rel:] *= np.linspace(1.0, 0.0, rel, dtype=np.float32)

        pad_l = np.zeros(seg_len, dtype=np.float32)
        pad_r = np.zeros(seg_len, dtype=np.float32)
        for idx, freq in enumerate(chord):
            # Subtle stereo detune for rich studio width
            pad_l += 0.14 * np.sin(2.0 * np.pi * (freq * 0.9985) * tt) + 0.04 * np.sin(2.0 * np.pi * (freq * 2.0) * tt)
            pad_r += 0.14 * np.sin(2.0 * np.pi * (freq * 1.0015) * tt) + 0.04 * np.sin(2.0 * np.pi * (freq * 2.0) * tt)
        # Deep sub-bass (root note octave down)
        bass_f = chord[0] * 0.5
        bass = 0.22 * np.sin(2.0 * np.pi * bass_f * tt) * np.exp(-0.6 * tt)
        left[start_s:end_s] += (pad_l + bass) * env
        right[start_s:end_s] += (pad_r + bass) * env

        # 2. Soft Modern Pluck Arpeggio (8th notes)
        step_dur = beat_dur * 0.5
        for step in range(8):
            s_idx = start_s + int(step * step_dur * sr)
            e_idx = min(n, s_idx + int(step_dur * 1.15 * sr))
            if s_idx >= n or e_idx <= s_idx:
                continue
            p_len = e_idx - s_idx
            pt = np.linspace(0.0, p_len / sr, p_len, endpoint=False, dtype=np.float32)
            note_f = chord[step % len(chord)] * (2.0 if step % 4 == 3 else 1.0)
            pluck = 0.11 * (np.sin(2.0 * np.pi * note_f * pt) + 0.35 * np.sin(4.0 * np.pi * note_f * pt)) * np.exp(-9.0 * pt)
            pan = 0.35 if (step % 2 == 0) else 0.65
            left[s_idx:e_idx] += pluck * (1.0 - pan * 0.5)
            right[s_idx:e_idx] += pluck * (0.5 + pan * 0.5)

    # 3. Clean Modern Kick & Soft Hi-Hat Pulse
    rng = np.random.default_rng(seed_int)
    total_beats = int(duration_sec / beat_dur)
    for b in range(total_beats):
        # Kick on beats 0 and 2 (and soft ghost on 2.5)
        if b % 2 == 0:
            ks = int(b * beat_dur * sr)
            ke = min(n, ks + int(0.14 * sr))
            if ks < n and ke > ks:
                kt = np.linspace(0.0, (ke - ks) / sr, ke - ks, endpoint=False, dtype=np.float32)
                f_sweep = 115.0 * np.exp(-26.0 * kt) + 46.0
                kick = 0.30 * np.sin(2.0 * np.pi * np.cumsum(f_sweep) / sr) * np.exp(-16.0 * kt)
                left[ks:ke] += kick
                right[ks:ke] += kick
        # Soft hi-hat on off-beats
        hs = int((b + 0.5) * beat_dur * sr)
        he = min(n, hs + int(0.045 * sr))
        if hs < n and he > hs:
            ht = np.linspace(0.0, (he - hs) / sr, he - hs, endpoint=False, dtype=np.float32)
            noise = rng.standard_normal(he - hs).astype(np.float32)
            # High-pass approximation via first difference
            hp = np.diff(noise, prepend=0.0)
            hat = 0.045 * hp * np.exp(-65.0 * ht)
            left[hs:he] += hat
            right[hs:he] += hat

    # Master gentle fade-in (0.8s) and fade-out (1.6s) + soft limiter
    fi = min(n, int(0.8 * sr))
    fo = min(n, int(1.6 * sr))
    if fi > 0:
        ramp_in = np.linspace(0.0, 1.0, fi, dtype=np.float32)
        left[:fi] *= ramp_in
        right[:fi] *= ramp_in
    if fo > 0:
        ramp_out = np.linspace(1.0, 0.0, fo, dtype=np.float32)
        left[-fo:] *= ramp_out
        right[-fo:] *= ramp_out

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-5)
    scale = 0.82 / peak
    stereo = np.stack([left * scale, right * scale], axis=1)
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)

    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return out_wav_path


def _make_slide_variants(base_im, extra_ims):
    """Creates 4 distinct clean phone image frames (using extra article images if available, or smart zoom crops)."""
    frames = [base_im.convert("RGB")]
    for ex in extra_ims:
        if ex is not None and len(frames) < 4:
            frames.append(ex.convert("RGB"))

    w, h = base_im.size
    # Fill up to 4 frames with tasteful dynamic zoom/pan perspectives of the clean hero photo
    crops = [
        (int(w * 0.08), int(h * 0.04), int(w * 0.92), int(h * 0.96)),  # Centered detail zoom
        (int(w * 0.14), int(h * 0.08), int(w * 0.96), int(h * 0.92)),  # Right-shifted camera focus
        (int(w * 0.04), int(h * 0.08), int(w * 0.86), int(h * 0.92)),  # Left-shifted sleek crop
    ]
    c_idx = 0
    while len(frames) < 4:
        box = crops[c_idx % len(crops)]
        frames.append(ImageOps.fit(base_im.crop(box), (1200, 675), method=Image.Resampling.LANCZOS))
        c_idx += 1
    return frames[:4]


def _draw_logo_top(canvas, logo_rgb, top_y=105, wm_h=142):
    if not os.path.exists(fbp.WM_MASK_PATH):
        return
    W = canvas.width
    wm_orig = Image.open(fbp.WM_MASK_PATH).convert("RGBA")
    wm_w = int(wm_orig.width * (wm_h / wm_orig.height))
    wm_mask = wm_orig.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
    alpha = np.array(wm_mask)[:, :, 3].astype(np.float32) * 0.96

    sh_arr = np.zeros((wm_h, wm_w, 4), dtype=np.uint8)
    sh_arr[:, :, 0], sh_arr[:, :, 1], sh_arr[:, :, 2] = (6, 10, 18)
    sh_arr[:, :, 3] = np.clip(alpha * 0.85, 0, 255).astype(np.uint8)
    sh_im = Image.fromarray(sh_arr).filter(ImageFilter.GaussianBlur(5))

    fg_arr = np.zeros((wm_h, wm_w, 4), dtype=np.uint8)
    fg_arr[:, :, 0], fg_arr[:, :, 1], fg_arr[:, :, 2] = logo_rgb
    fg_arr[:, :, 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    fg_im = Image.fromarray(fg_arr)

    lx = (W - wm_w) // 2
    canvas.alpha_composite(sh_im, (lx + 2, top_y + 3))
    canvas.alpha_composite(fg_im, (lx, top_y))


def _render_reel_slide(photo_im, accent_rgb, logo_rgb, badge_text, main_text, sub_lines, slide_idx, is_outro=False):
    """Renders a single 1080x1920 vertical Reel slide with crisp Arabic typography and zero watermarks."""
    W, H = 1080, 1920
    bg = ImageOps.fit(photo_im.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(48))
    bg = ImageEnhance.Brightness(bg).enhance(0.32)
    bg = ImageEnhance.Color(bg).enhance(1.18)
    canvas = bg.convert("RGBA")

    # Vertical gradient overlay
    grad = np.zeros((H, W, 4), dtype=np.uint8)
    for yy in range(H):
        t = abs((yy / float(H)) - 0.36)
        grad[yy, :, 0] = 8
        grad[yy, :, 1] = 12
        grad[yy, :, 2] = 22
        grad[yy, :, 3] = int(min(205, 80 + t * 155))
    canvas = Image.alpha_composite(canvas, Image.fromarray(grad))

    _draw_logo_top(canvas, logo_rgb, top_y=115, wm_h=142)

    # Progress indicator dots at top (slide 1..4)
    d = ImageDraw.Draw(canvas)
    dot_y = 285
    bar_w, gap = 190, 18
    total_w = 4 * bar_w + 3 * gap
    sx = (W - total_w) // 2
    for i in range(4):
        col = (*accent_rgb, 240) if i <= slide_idx else (255, 255, 255, 65)
        d.rounded_rectangle((sx + i * (bar_w + gap), dot_y, sx + i * (bar_w + gap) + bar_w, dot_y + 8), radius=4, fill=col)

    # Rounded Hero Phone Photo Card
    card_w, card_h = 980, 565
    hero = ImageOps.fit(photo_im.convert("RGB"), (card_w, card_h), method=Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=36, fill=255)
    hero.putalpha(mask)

    hx, hy = (W - card_w) // 2, 330
    sh_card = Image.new("RGBA", (card_w + 60, card_h + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sh_card).rounded_rectangle((30, 30, card_w + 30, card_h + 30), radius=36, fill=(0, 0, 0, 160))
    sh_card = sh_card.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(sh_card, (hx - 30, hy - 20))
    canvas.alpha_composite(hero, (hx, hy))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((hx, hy, hx + card_w, hy + card_h), radius=36, outline=(*accent_rgb, 130), width=3)

    # Lower Glassmorphism Text Card (keeps safe bottom margin above Reels UI controls: y=950..1620)
    bx1, by1, bx2, by2 = 52, 955, W - 52, 1620
    d.rounded_rectangle((bx1, by1, bx2, by2), radius=40, fill=(10, 16, 28, 205), outline=(*accent_rgb, 105), width=2)

    # Top-right category badge pill inside card
    f_badge = fbp._load_ar_font(28, bold=True)
    bw = fbp._ar_textlength(d, badge_text, f_badge)
    pill_w = min(560, int(bw) + 56)
    acc_lum = 0.299 * accent_rgb[0] + 0.587 * accent_rgb[1] + 0.114 * accent_rgb[2]
    badge_ink = (10, 16, 28, 255) if acc_lum > 145 else (255, 255, 255, 255)
    d.rounded_rectangle((bx2 - 44 - pill_w, by1 + 38, bx2 - 44, by1 + 92), radius=27, fill=(*accent_rgb, 240))
    fbp._draw_ar_text(d, (bx2 - 44 - pill_w + (pill_w - bw) / 2, by1 + 48), badge_text, f_badge, badge_ink)

    # Main headline/point text
    f_main = fbp._load_ar_font(46 if not is_outro else 44, bold=True)
    main_lines = fbp._wrap_ar_lines(d, main_text, f_main, max_w=(bx2 - bx1 - 96), max_lines=3)
    ty = by1 + 128
    for ln in main_lines:
        tw = fbp._ar_textlength(d, ln, f_main)
        fbp._draw_ar_text(d, (bx2 - 48 - tw, ty), ln, f_main, (255, 255, 255, 255))
        ty += 70

    # Sub-lines / details
    if sub_lines:
        ty += 14
        d.line([(bx1 + 48, ty), (bx2 - 48, ty)], fill=(255, 255, 255, 40), width=2)
        ty += 28
        f_sub = fbp._load_ar_font(33, bold=False)
        for s_txt in sub_lines[:2]:
            s_lines = fbp._wrap_ar_lines(d, s_txt, f_sub, max_w=(bx2 - bx1 - 125), max_lines=2)
            if not s_lines:
                continue
            d.ellipse((bx2 - 66, ty + 16, bx2 - 50, ty + 32), fill=(*accent_rgb, 245))
            for sl in s_lines:
                tw = fbp._ar_textlength(d, sl, f_sub)
                fbp._draw_ar_text(d, (bx2 - 82 - tw, ty), sl, f_sub, (226, 232, 240, 245))
                ty += 50
            ty += 16
            if ty > by2 - 60:
                break

    return canvas.convert("RGB")


def build_reel_mp4(title, url, image_url, content, out_mp4_path):
    """Builds a ~17s 1080x1920 30fps MP4 Facebook Reel with 4 animated slides + copyright-free music."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        print("❌ ffmpeg not found; cannot build Reel MP4.")
        return False

    clean_title = html.unescape(title or "").strip()
    clean_url = (url or "").replace("http://", "https://").strip()
    base_im = fbp.resolve_clean_base_image(clean_url, image_url, content=content, title=clean_title)
    if base_im is None:
        print("❌ Could not resolve clean phone image for Reel.")
        return False

    # Try fetching up to 2 extra images from the article body if clean
    extra_ims = []
    for m_u in re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', content or "", flags=re.I)[1:3]:
        u2 = html.unescape(m_u)
        if "review-" not in u2.lower():
            try:
                r = requests.get(u2, headers=fbp.UA, timeout=15)
                if r.status_code == 200 and len(r.content) > 5000:
                    extra_ims.append(fbp._format_raw_phone_image_1200x675(Image.open(io.BytesIO(r.content)), src_url=u2))
            except Exception:
                pass

    frames = _make_slide_variants(base_im, extra_ims)
    bullets, paras, specs = fbp._extract_clean_article_facts(clean_title, content)
    is_sam = bool(fbp.SAMSUNG_RX.search(clean_title))

    dom_h = fbp._get_dominant_hue(base_im)
    if dom_h is not None:
        ar, ag, ab = colorsys.hsv_to_rgb(dom_h, 0.54, 0.98)
        accent_rgb = (int(ar * 255), int(ag * 255), int(ab * 255))
        lr, lg, lb = colorsys.hsv_to_rgb(dom_h, 0.24, 1.0)
        logo_rgb = (int(lr * 255), int(lg * 255), int(lb * 255))
    else:
        accent_rgb = (56, 189, 248)
        logo_rgb = (248, 250, 255)

    # Prepare text content for the 4 slides
    badge1 = "أخبار سامسونج" if is_sam else "أخبار الهواتف"
    pt1 = bullets[0] if len(bullets) > 0 else (paras[0][:100] + "…" if paras else clean_title)
    pt2 = bullets[1] if len(bullets) > 1 else (specs[0] if specs else (paras[1][:100] + "…" if len(paras) > 1 else "تابع التفاصيل والمواصفات"))
    pt3_sub = specs[:2] if specs else (bullets[2:3] if len(bullets) > 2 else ["أحدث تطورات عالم الموبايلات 2026"])

    q_idx = int(hashlib.md5(clean_title.encode("utf-8")).hexdigest(), 16) % len(fbp.ENGAGEMENT_QUESTIONS)
    outro_q = re.sub(r"[👇🤔💬🔥]", "", fbp.ENGAGEMENT_QUESTIONS[q_idx]).strip()

    slides_cfg = [
        (frames[0], badge1, clean_title, [pt1[:95]], False),
        (frames[1], "أهم التفاصيل", pt1[:95], [pt2[:95]], False),
        (frames[2], "المواصفات والأرقام", pt2[:95], [s[:85] for s in pt3_sub], False),
        (frames[3], "شاركنا رأيك", outro_q[:100], ["اكتب رأيك في التعليقات وتابع صفحة موبايل بالعربى"], True),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        slide_paths = []
        for idx, (ph, bdg, main_t, subs, is_out) in enumerate(slides_cfg):
            im_s = _render_reel_slide(ph, accent_rgb, logo_rgb, bdg, main_t, subs, idx, is_outro=is_out)
            sp = os.path.join(tmp, f"slide_{idx}.jpg")
            im_s.save(sp, format="JPEG", quality=93)
            slide_paths.append(sp)

        # Synthesize 100% copyright-free stereo music (17.2s)
        wav_path = os.path.join(tmp, "music.wav")
        synthesize_copyright_free_music(wav_path, duration_sec=17.2, seed_str=clean_title)

        # Build MP4 with smooth crossfades (each slide 4.6s, 0.5s xfade -> 4*4.6 - 3*0.5 = 16.9s)
        cmd = [
            ffmpeg, "-y",
            "-loop", "1", "-t", "4.6", "-i", slide_paths[0],
            "-loop", "1", "-t", "4.6", "-i", slide_paths[1],
            "-loop", "1", "-t", "4.6", "-i", slide_paths[2],
            "-loop", "1", "-t", "4.6", "-i", slide_paths[3],
            "-i", wav_path,
            "-filter_complex",
            "[0:v]scale=1080:1920,setsar=1,fps=30[v0];"
            "[1:v]scale=1080:1920,setsar=1,fps=30[v1];"
            "[2:v]scale=1080:1920,setsar=1,fps=30[v2];"
            "[3:v]scale=1080:1920,setsar=1,fps=30[v3];"
            "[v0][v1]xfade=transition=slideleft:duration=0.5:offset=4.1[vx1];"
            "[vx1][v2]xfade=transition=fade:duration=0.5:offset=8.2[vx2];"
            "[vx2][v3]xfade=transition=slideleft:duration=0.5:offset=12.3,format=yuv420p[vout]",
            "-map", "[vout]", "-map", "4:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
            out_mp4_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0 or not os.path.exists(out_mp4_path) or os.path.getsize(out_mp4_path) < 50000:
            print("❌ ffmpeg Reel build failed:", res.stderr[-400:])
            return False
        print(f"🎬 Built 9:16 Reel MP4 ({os.path.getsize(out_mp4_path)//1024} KB): {out_mp4_path}")
        return True


def _can_post_reel_now(state, now, force=False, dry=False):
    cap, min_gap, peak_windows, stage_label = _get_daily_reel_policy(now.date())
    if force:
        return True, f"forced ({stage_label})"
    today = now.date().isoformat()
    today_reels = [r for r in state.get("fb_reels", []) if r.get("date") == today]
    if len(today_reels) >= cap:
        return False, f"daily reels cap reached ({len(today_reels)}/{cap} today - {stage_label})"

    if not dry:
        in_peak = any(lo <= now.hour < hi for lo, hi in peak_windows)
        if not in_peak:
            return False, f"outside Reels peak hours (Cairo {now.hour}:00; {stage_label})"
        if today_reels:
            last_at_str = today_reels[-1].get("at")
            if last_at_str:
                try:
                    last_at = datetime.datetime.fromisoformat(last_at_str)
                    if last_at.tzinfo is None:
                        last_at = last_at.replace(tzinfo=f.CAIRO)
                    elapsed = (now - last_at).total_seconds() / 60.0
                    if elapsed < min_gap:
                        return False, f"last Reel was {int(elapsed)}m ago (waiting {min_gap}m - {stage_label})"
                except Exception:
                    pass
    return True, f"ok ({len(today_reels) + 1}/{cap} today - {stage_label})"


def upload_and_publish_reel(mp4_path, description, tok, page):
    """Publishes an MP4 as a Facebook Page Reel using the official 3-step Graph API /{page_id}/video_reels."""
    with open(mp4_path, "rb") as fp:
        mp4_bytes = fp.read()

    # Step 1: Initialize Reel upload session
    r1 = requests.post(
        f"https://graph.facebook.com/{page}/video_reels",
        data={"upload_phase": "start", "access_token": tok},
        timeout=30
    )
    if not r1.ok or not r1.json().get("video_id"):
        print(f"❌ Reel start failed ({r1.status_code}): {r1.text[:200]}")
        return None
    video_id = r1.json()["video_id"]
    upload_url = r1.json().get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{video_id}"

    # Step 2: Upload MP4 binary
    r2 = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {tok}",
            "offset": "0",
            "file_size": str(len(mp4_bytes)),
            "Content-Type": "application/octet-stream"
        },
        data=mp4_bytes,
        timeout=120
    )
    if not r2.ok:
        print(f"❌ Reel binary upload failed ({r2.status_code}): {r2.text[:200]}")
        return None

    # Step 3: Publish Reel
    r3 = requests.post(
        f"https://graph.facebook.com/{page}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": description,
            "access_token": tok
        },
        timeout=40
    )
    if r3.ok and r3.json().get("success", True):
        print(f"✅ Facebook Reel Published! video_id={video_id}")
        return video_id
    print(f"❌ Reel finish failed ({r3.status_code}): {r3.text[:200]}")
    return None


def run_daily_reels(dry=False, force=False, lookback_hours=120, out_mp4=""):
    state = fbp.load_state()
    state.setdefault("fb_reels", [])
    now = datetime.datetime.now(f.CAIRO)
    today = now.date().isoformat()

    allowed, reason = _can_post_reel_now(state, now, force=force, dry=dry)
    if not allowed:
        print(f"Facebook Reels: skipping ({reason}).")
        return False

    done_reel_urls = {r.get("url") for r in state.get("fb_reels", []) if r.get("url")}
    since = (now - datetime.timedelta(hours=lookback_hours)).isoformat(timespec="seconds")
    tok_blogger = f.token()

    candidates = []
    for blog_id, site_name in [(fbp.REVIEW_BLOG, "Review"), (fbp.EA_BLOG, "Egyptaway")]:
        try:
            res = f.api("GET", f"/blogs/{blog_id}/posts", tok_blogger, {
                "status": "live", "startDate": since, "maxResults": 40,
                "fetchBodies": "true", "fetchImages": "true"
            })
            items = res.get("items", []) if isinstance(res, dict) else []
            for p in items:
                u = (p.get("url") or "").replace("http://", "https://")
                if not u or u in done_reel_urls:
                    continue
                if fbp.is_phone_post(p, blog_id=blog_id):
                    candidates.append((1 if fbp.is_samsung_post(p) else 0, p.get("published", ""), p))
        except Exception as ex:
            print(f"Facebook Reels scan warning ({site_name}): {ex}")

    if not candidates:
        print("Facebook Reels: no unposted phone article candidates found.")
        return False

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    is_sam, _, p = candidates[0]
    clean_title = html.unescape(p["title"]).strip()
    clean_url = p["url"].replace("http://", "https://")
    img = fbp.first_image(p.get("content"), post=p)
    print(f"Facebook Reel selected (Samsung={bool(is_sam)}): {clean_title}")

    # Viral no-link caption for the Reel
    caption = fbp.build_native_nolink_caption(clean_title, p.get("content"))
    if "#ريلز" not in caption:
        caption = caption.strip() + " #ريلز"

    target_mp4 = out_mp4 or os.path.join(tempfile.gettempdir(), "mobile_belaraby_reel.mp4")
    ok_build = build_reel_mp4(clean_title, clean_url, img, p.get("content"), target_mp4)
    if not ok_build:
        return False

    tok_fb, page = fbp.get_fb_credentials()
    if dry:
        print(f"[DRY FB REEL] Ready to publish to Page ({page}):")
        print(f"  MP4    : {target_mp4}")
        print("  Caption:\n" + "\n".join("    " + ln for ln in caption.splitlines()))
        return True

    if not tok_fb or not page:
        print("Facebook Reels: missing FB_PAGE_TOKEN / FB_PAGE_ID.")
        return False

    vid = upload_and_publish_reel(target_mp4, caption, tok_fb, page)
    if vid:
        state["fb_reels"].append({
            "date": today,
            "url": clean_url,
            "title": clean_title,
            "at": now.isoformat(timespec="seconds"),
            "video_id": vid
        })
        state["fb_reels"] = state["fb_reels"][-200:]
        fbp.save_state(state)
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Daily 2x Facebook Page Reels Generator (Copyright-Free Music + Peak Hours)")
    ap.add_argument("--dry", action="store_true", help="Render MP4 preview without uploading")
    ap.add_argument("--force", action="store_true", help="Publish 1 Reel immediately (bypass peak hours / daily cap)")
    ap.add_argument("--out", default="", help="Optional output path for the generated MP4")
    ap.add_argument("--hours", type=int, default=120, help="Lookback window in hours")
    args = ap.parse_args()

    dry = args.dry or os.environ.get("DRY_RUN") == "1"
    force = args.force or os.environ.get("FORCE") == "1"
    run_daily_reels(dry=dry, force=force, lookback_hours=args.hours, out_mp4=args.out)


if __name__ == "__main__":
    main()
