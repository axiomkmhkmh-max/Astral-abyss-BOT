# ============================================================
#  ASTRAL ABYSS — Profile Card Image Generator
# ------------------------------------------------------------
#  یه کارتِ تصویریِ تیره/فانتزی از وضعیتِ بازیکن می‌سازه (سطح، عنصر،
#  کاتانا، رنکِ PvP، عنوانِ فعال...) تا بشه فرستادش/ذخیره‌ش کرد یا
#  تو گروهِ دوستان به اشتراک گذاشت. فونت DejaVu Sans همراهِ خودِ
#  پروژه باندل شده (assets/fonts) تا روی هر سروری بدونِ نیاز به فونتِ
#  سیستم‌عامل درست کار کنه — و مهم‌تر از اون، حروفِ فارسی رو درست
#  می‌چینه (نسخه‌ی مدرنِ Pillow خودش shaping/RTL رو انجام می‌ده).
# ============================================================
import os
import math
import random as _rand
from PIL import Image, ImageDraw, ImageFont, ImageFilter

_FONT_DIR = os.path.dirname(os.path.abspath(__file__))
_REGULAR = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
_BOLD    = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")

RARITY_COLORS = {
    "common":    (150, 150, 160),
    "rare":      (70, 160, 220),
    "legendary": (240, 180, 60),
    "special":   (200, 90, 230),
    "mythic":    (235, 95, 40),
}

RARITY_LABELS_FA = {
    "common": "معمولی", "rare": "کمیاب", "legendary": "افسانه‌ای",
    "special": "ویژه", "mythic": "اسطوره‌ای",
}

RARITY_LABELS_EN = {
    "common": "Common", "rare": "Rare", "legendary": "Legendary",
    "special": "Special", "mythic": "Mythic",
}

W, H = 1000, 560


import re

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]+", flags=re.UNICODE
)

def _clean(text: str) -> str:
    """ایموجی رو حذف می‌کنه (فونتِ باندل‌شده ایموجیِ رنگی رو ساپورت نمی‌کنه
    و به‌جاش باکسِ خالی نشون می‌ده) و فاصله‌های اضافه‌ی باقی‌مونده رو جمع می‌کنه."""
    return _EMOJI_RE.sub("", text).strip()


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _draw_right(draw, x_right, y, text, font, fill):
    """چون فارسی راست‌به‌چپه، متن رو با لبه‌ی راست تراز می‌کنیم."""
    w = _text_w(draw, text, font)
    draw.text((x_right - w, y), text, font=font, fill=fill)


def _fit_right(draw, x_right, y, text, font_path, size, max_width, fill, min_size=16):
    """مثلِ _draw_right ولی اگه متن خیلی طولانی باشه (اسمِ عجیب‌غریب و این‌ها)،
    اول فونت رو کوچیک‌تر می‌کنه و اگه بازم جا نشد، با «...» کوتاهش می‌کنه —
    تا از کارت بیرون نزنه."""
    font = _font(font_path, size)
    while size > min_size and _text_w(draw, text, font) > max_width:
        size -= 2
        font = _font(font_path, size)
    while _text_w(draw, text, font) > max_width and len(text) > 1:
        text = text[:-1]
        trial = text.strip() + "…"
        if _text_w(draw, trial, font) <= max_width:
            text = trial
            break
    w = _text_w(draw, text, font)
    draw.text((x_right - w, y), text, font=font, fill=fill)


def _gradient_bg(accent: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (W, H), (12, 10, 22))
    top = (18, 14, 34)
    bottom = (6, 5, 14)
    for y in range(H):
        t = y / H
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        ImageDraw.Draw(img).line([(0, y), (W, y)], fill=(r, g, b))
    # یه هاله‌ی رنگیِ ملایم از رنگِ rarity گوشه‌ی بالا-راست
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 500, -250, W + 100, 350], fill=accent)
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(120))
    img = Image.blend(img, glow, 0.35)
    return img


def _lightning_bolt(draw, x0, y0, length, angle_deg, segments, color, width=2):
    """یه خطِ زیگزاگیِ نازک شبیهِ رعد می‌کشه (برای افکتِ Mythic)."""
    x, y = x0, y0
    pts = [(x, y)]
    angle = math.radians(angle_deg)
    seg_len = length / segments
    for _ in range(segments):
        angle_j = angle + math.radians(_rand.uniform(-28, 28))
        x += seg_len * math.cos(angle_j)
        y += seg_len * math.sin(angle_j)
        pts.append((x, y))
    draw.line(pts, fill=color, width=width, joint="curve")


def _apply_rarity_fx(img: Image.Image, accent: tuple[int, int, int], rarity: str, seed=None) -> Image.Image:
    """لایه‌ی افکتِ بصریِ مخصوصِ هر رنک — روی پس‌زمینه اعمال می‌شه، قبل از نوشتنِ متن.
    seed باعث می‌شه ظاهرِ کارتِ یه پلیرِ مشخص هر بار یکسان بمونه (نه رندومِ کامل)."""
    if seed is not None:
        _rand.seed(seed)

    if rarity == "mythic":
        # هاله‌ی دوگانه‌ی آتش (نارنجی) + خلأ (بنفش تیره) از پایینِ کارت
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([-180, H - 280, 360, H + 160], fill=(230, 90, 30))
        gd.ellipse([W - 380, H - 300, W + 180, H + 160], fill=(110, 30, 190))
        glow = glow.filter(ImageFilter.GaussianBlur(95))
        img = Image.blend(img, glow, 0.5)
        draw = ImageDraw.Draw(img)
        for _ in range(3):
            _lightning_bolt(
                draw, _rand.randint(120, W - 120), -5, _rand.randint(150, 230),
                80, 6, (255, 235, 170), width=2,
            )
    elif rarity == "legendary":
        # درخشش قطریِ طلایی از دو گوشه (حسِ فویلِ متحرک/ورقِ طلا)
        sheen = Image.new("L", (W, H), 0)
        sd = ImageDraw.Draw(sheen)
        sd.polygon([(0, 0), (280, 0), (0, 280)], fill=120)
        sd.polygon([(W, H), (W - 280, H), (W, H - 280)], fill=120)
        sheen = sheen.filter(ImageFilter.GaussianBlur(45))
        gold_layer = Image.new("RGB", (W, H), (255, 220, 130))
        img = Image.composite(gold_layer, img, sheen)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([15, 15, W - 15, H - 15], radius=20, outline=(255, 225, 150), width=2)
    elif rarity == "special":
        draw = ImageDraw.Draw(img)
        for _ in range(16):
            x, y = _rand.randint(25, W - 25), _rand.randint(25, H - 25)
            r = _rand.randint(1, 3)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(225, 160, 240))
    elif rarity == "rare":
        draw = ImageDraw.Draw(img)
        for _ in range(3):
            y = _rand.randint(40, H - 40)
            draw.line([(-20, y), (W + 20, y - 60)], fill=(95, 175, 230), width=1)
    return img


def _bar(draw, x, y, w, h, pct, fill, bg=(40, 38, 55)):
    pct = max(0.0, min(1.0, pct))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    if pct > 0:
        draw.rounded_rectangle([x, y, x + w * pct, y + h], radius=h // 2, fill=fill)


def generate_profile_card(player: dict, char_data: dict, out_path: str) -> str:
    from katana_core import get_katana_identity
    from game_data import xp_for_level, effective_max_level

    rarity = char_data.get("rarity", "common")
    accent = RARITY_COLORS.get(rarity, RARITY_COLORS["common"])

    img = _gradient_bg(accent)
    seed = hash((player.get("name", ""), player.get("character", ""), rarity))
    img = _apply_rarity_fx(img, accent, rarity, seed=seed)
    draw = ImageDraw.Draw(img)

    f_title   = _font(_BOLD, 44)
    f_sub     = _font(_REGULAR, 24)
    f_label   = _font(_REGULAR, 22)
    f_value   = _font(_BOLD, 24)
    f_small   = _font(_REGULAR, 18)
    f_tiny    = _font(_REGULAR, 15)
    f_big_num = _font(_BOLD, 60)

    PAD = 50

    # ─── card border, tinted with the rarity color ───
    draw.rounded_rectangle([8, 8, W - 8, H - 8], radius=24, outline=accent, width=4)

    # ─── level circle (top-left) ───
    cx, cy, r = 115, 130, 82
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=6, fill=(20, 18, 34))
    lvl_txt = str(player.get("level", 1))
    lw = _text_w(draw, lvl_txt, f_big_num)
    draw.text((cx - lw / 2, cy - 42), lvl_txt, font=f_big_num, fill=(255, 255, 255))
    lbl_w = _text_w(draw, "LEVEL", f_tiny)
    draw.text((cx - lbl_w / 2, cy + 24), "LEVEL", font=f_tiny, fill=(180, 180, 190))

    # ─── adventurer-guild rank badge (F..S / SS) — corner of the level circle ───
    from isekai_theme import rank_for_level
    rank_letter, rank_fa = rank_for_level(player.get("level", 1), player.get("rebirth_count", 0))
    badge_txt = f"RANK {rank_letter}"
    f_badge = _font(_BOLD, 17)
    bw = _text_w(draw, badge_txt, f_badge)
    bcx = cx + int(r * 0.68)
    bcy = cy + int(r * 0.68)
    pad_x = 11
    half_h = 15
    draw.rounded_rectangle(
        [bcx - bw / 2 - pad_x, bcy - half_h, bcx + bw / 2 + pad_x, bcy + half_h],
        radius=half_h, outline=accent, width=3, fill=(20, 18, 34),
    )
    draw.text((bcx - bw / 2, bcy - half_h + 4), badge_txt, font=f_badge, fill=accent)

    # ─── player name + active title (right-aligned) ───
    max_w_right = W - PAD - 260  # leave room for the level circle
    name = _clean(player.get("name", "Traveler"))
    _fit_right(draw, W - PAD, 38, name, _BOLD, 44, max_w_right, (245, 245, 250))

    titles = player.get("titles_unlocked", [])
    try:
        from divine_seals import get_seal_title
        seal_title = get_seal_title(player)
    except ImportError:
        seal_title = None
    active_title = seal_title or (_clean(titles[-1]) if titles else None)
    if active_title:
        _fit_right(draw, W - PAD, 92, active_title, _REGULAR, 24, max_w_right, accent)

    # ─── character name + rarity + gender ───
    char_name = player.get("character", "\u2014")
    rarity_label = RARITY_LABELS_EN.get(rarity, rarity.title())
    gender_label = "Female" if player.get("gender") == "female" else "Male"
    _fit_right(draw, W - PAD, 134, f"{char_name}   \u00b7   {rarity_label}   \u00b7   {gender_label}", _REGULAR, 24, max_w_right, (200, 200, 210))

    # ─── XP bar ───
    lvl = player.get("level", 1)
    xp = player.get("xp", 0)
    at_cap = lvl >= effective_max_level(player)
    next_xp = xp_for_level(lvl)
    prev_xp = xp_for_level(lvl - 1) if lvl > 1 else 0
    xp_span = next_xp - prev_xp
    xp_into = max(0, xp - prev_xp)
    xp_pct = 1.0 if at_cap or not xp_span else (xp_into / xp_span)
    y_xp = 258
    xp_label = "XP   MAX" if at_cap else f"XP   {xp_into:,} / {xp_span:,}"
    _draw_right(draw, W - PAD, y_xp - 32, xp_label, f_label, (190, 190, 200))
    _bar(draw, PAD, y_xp, W - PAD * 2, 20, xp_pct, accent)

    # ─── HP bar ───
    hp, max_hp = player.get("hp", 100), player.get("max_hp", 100)
    hp_pct = (hp / max_hp) if max_hp else 0
    y_hp = y_xp + 52
    _draw_right(draw, W - PAD, y_hp - 32, f"HP   {hp:,} / {max_hp:,}", f_label, (190, 190, 200))
    _bar(draw, PAD, y_hp, W - PAD * 2, 20, hp_pct, (215, 80, 80))

    # ─── divider ───
    y_div = y_hp + 46
    draw.line([(PAD, y_div), (W - PAD, y_div)], fill=(255, 255, 255, 30))
    draw.line([(PAD, y_div), (W - PAD, y_div)], fill=tuple(min(255, c + 15) for c in (30, 28, 45)))

    # ─── stats grid (2 columns) ───
    ident = get_katana_identity(char_name)
    katana_name = _clean(ident.get("name", char_data.get("katana", "\u2014")))
    stage = player.get("katana_awakening", 0)

    stats_left = [
        ("Element", char_data.get("element", "\u2014")),
        ("Katana", f"{katana_name} (Awakening {stage})"),
        ("Zen", f"{player.get('zen', 0):,}"),
    ]
    stats_right = [
        ("Kills", str(player.get("kills", 0))),
        ("PvP Wins", str(player.get("pvp_wins", 0))),
        ("Rank Points", str(player.get("pvp_points", 0))),
    ]

    y0 = y_div + 24
    col_w = (W - PAD * 2) / 2
    for i, (label, value) in enumerate(stats_left):
        y = y0 + i * 42
        draw.text((PAD, y), label, font=f_label, fill=(150, 150, 165))
        _fit_right(draw, PAD + col_w - 20, y, str(value), _BOLD, 24, col_w - 150, (235, 235, 240))
    for i, (label, value) in enumerate(stats_right):
        y = y0 + i * 42
        x_right = PAD + col_w * 2
        _draw_right(draw, x_right, y, value, f_value, (235, 235, 240))
        vw = _text_w(draw, value, f_value)
        _draw_right(draw, x_right - vw - 20, y + 2, label, f_label, (150, 150, 165))

    # ─── watermark ───
    wm = "ASTRAL ABYSS"
    wm_font = _font(_BOLD, 18)
    draw.text((PAD, H - 42), wm, font=wm_font, fill=(95, 93, 108))

    img.save(out_path, "PNG")
    return out_path

    img.save(out_path, "PNG")
    return out_path


# ─── پوسترِ «تحتِ تعقیب» برای باسِ هفته ─────────────────────────
PW, PH = 800, 1000

def generate_boss_wanted_poster(boss_name: str, boss_title: str, total_hp: int,
                                 exclusive_item: str, bonus_zen: int, out_path: str) -> str:
    # پس‌زمینه‌ی گرم/کاغذیِ تیره (حسِ پوسترِ قدیمی)
    bg_top, bg_bottom = (58, 38, 22), (28, 16, 10)
    img = Image.new("RGB", (PW, PH), bg_bottom)
    for y in range(PH):
        t = y / PH
        r = int(bg_top[0] + (bg_bottom[0] - bg_top[0]) * t)
        g = int(bg_top[1] + (bg_bottom[1] - bg_top[1]) * t)
        b = int(bg_top[2] + (bg_bottom[2] - bg_top[2]) * t)
        ImageDraw.Draw(img).line([(0, y), (PW, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)
    gold = (210, 170, 90)
    red  = (190, 60, 50)

    # کادرِ دوتایی (حسِ پوسترِ رسمی)
    draw.rectangle([20, 20, PW - 20, PH - 20], outline=gold, width=6)
    draw.rectangle([32, 32, PW - 32, PH - 32], outline=gold, width=2)

    f_stamp   = _font(_BOLD, 46)
    f_name    = _font(_BOLD, 54)
    f_title   = _font(_REGULAR, 28)
    f_label   = _font(_REGULAR, 24)
    f_value   = _font(_BOLD, 30)
    f_footer  = _font(_REGULAR, 20)

    def _center(text, font, y, fill, max_w=PW - 140):
        text = _clean(text)
        size = font.size
        fnt = font
        while size > 16 and _text_w(draw, text, fnt) > max_w:
            size -= 2
            fnt = _font(font.path, size)
        w = _text_w(draw, text, fnt)
        draw.text(((PW - w) / 2, y), text, font=fnt, fill=fill)
        return fnt

    # مهرِ «تحتِ تعقیب»
    _center("تحت تعقیب", f_stamp, 70, red)
    draw.line([(PW/2 - 160, 135), (PW/2 + 160, 135)], fill=red, width=3)

    # دایره‌ی جای «تصویر» باس (چون پرتره‌ی واقعی نداریم، یه نمادِ هندسی می‌ذاریم)
    cx, cy, r = PW // 2, 290, 130
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=gold, width=5, fill=(20, 14, 10))
    draw.ellipse([cx - r + 20, cy - r + 20, cx + r - 20, cy + r - 20], outline=(90, 60, 40), width=2)

    _center(boss_name, f_name, 460, (250, 240, 220))
    _center(boss_title, f_title, 525, (200, 180, 150))

    y = 610
    draw.line([(60, y), (PW - 60, y)], fill=(90, 60, 40), width=2)
    y += 30
    _center(f"❤ HP کل: {total_hp:,}", f_value, y, gold); y += 55
    _center("جایزه‌ی اختصاصیِ این هفته:", f_label, y, (200, 180, 150)); y += 38
    _center(exclusive_item, f_value, y, (250, 240, 220)); y += 50
    _center(f"+ {bonus_zen:,} Zen اضافه برای نفرِ اولِ دمیج", f_label, y, gold); y += 60

    _center("فقط تا آخرِ همین هفته در دسترسه!", f_footer, PH - 90, (170, 150, 120))

    wm = "ASTRAL ABYSS"
    ww = _text_w(draw, wm, _font(_BOLD, 18))
    draw.text(((PW - ww) / 2, PH - 50), wm, font=_font(_BOLD, 18), fill=(120, 100, 70))

    img.save(out_path, "PNG")
    return out_path
# برای لحظاتِ خاص: تک‌نفره کشتنِ باسِ جهانی، ارتقاءِ رنکِ PvP، رسیدن
# به یه سطحِ مهم و امثالِ اون — یه کارتِ کوچیک‌تر و نمایشی‌تر از کارتِ
# پروفایلِ کامل، مناسبِ فرستادن تو گروه به‌عنوانِ «یادبود».
MW, MH = 1000, 420

def generate_moment_card(player_name: str, headline: str, subtitle: str,
                          out_path: str, accent: tuple[int, int, int] = (240, 180, 60),
                          footer: str = "") -> str:
    img = Image.new("RGB", (MW, MH), (10, 8, 18))
    for y in range(MH):
        t = y / MH
        top, bottom = (22, 16, 34), (6, 5, 12)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        ImageDraw.Draw(img).line([(0, y), (MW, y)], fill=(r, g, b))
    glow = Image.new("RGB", (MW, MH), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([MW // 2 - 400, -200, MW // 2 + 400, 300], fill=accent)
    from PIL import ImageFilter
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    img = Image.blend(img, glow, 0.4)

    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, MW - 8, MH - 8], radius=24, outline=accent, width=4)

    f_headline = _font(_BOLD, 52)
    f_name     = _font(_BOLD, 40)
    f_sub      = _font(_REGULAR, 28)
    f_footer   = _font(_REGULAR, 20)

    headline = _clean(headline)
    name     = _clean(player_name)
    subtitle = _clean(subtitle)

    def _center(text, font, y, fill, max_w=MW - 100):
        size = font.size
        fnt = font
        while size > 18 and _text_w(draw, text, fnt) > max_w:
            size -= 2
            fnt = _font(font.path, size)
        w = _text_w(draw, text, fnt)
        draw.text(((MW - w) / 2, y), text, font=fnt, fill=fill)

    _center(headline, f_headline, 70, accent)
    _center(name, f_name, 150, (245, 245, 250))
    _center(subtitle, f_sub, 220, (200, 200, 210))

    if footer:
        _center(_clean(footer), f_footer, MH - 70, (150, 150, 165))

    wm = "ASTRAL ABYSS"
    ww = _text_w(draw, wm, _font(_BOLD, 18))
    draw.text(((MW - ww) / 2, MH - 40), wm, font=_font(_BOLD, 18), fill=(90, 88, 105))

    img.save(out_path, "PNG")
    return out_path


def _center_generic(draw, text, font, width, y, fill, x_offset=0):
    text = _clean(text)
    w = draw.textbbox((0, 0), text, font=font)[2]
    draw.text((x_offset + (width - w) / 2, y), text, font=font, fill=fill)


# ─── Daily Login Calendar ─────────────────────────────────────
CW, CH = 1000, 420
DAILY_REWARDS_FOR_CALENDAR = [200, 300, 400, 500, 700, 900, 1500]  # Day 1..7


def generate_login_calendar(streak: int, out_path: str) -> str:
    """streak: number of consecutive login days (1-based). Current day in the
    7-day cycle = ((streak-1) % 7) + 1."""
    accent = (110, 210, 170)
    img = Image.new("RGB", (CW, CH), (10, 9, 18))
    for y in range(CH):
        t = y / CH
        top, bottom = (19, 24, 30), (8, 7, 15)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        ImageDraw.Draw(img).line([(0, y), (CW, y)], fill=(r, g, b))

    # soft glow top-center, matches the accent
    glow = Image.new("RGB", (CW, CH), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([CW // 2 - 420, -220, CW // 2 + 420, 220], fill=accent)
    glow = glow.filter(ImageFilter.GaussianBlur(130))
    img = Image.blend(img, glow, 0.22)

    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, CW - 8, CH - 8], radius=24, outline=accent, width=4)

    f_head    = _font(_BOLD, 40)
    f_sub     = _font(_REGULAR, 20)
    f_day     = _font(_BOLD, 24)
    f_zen_num = _font(_BOLD, 24)
    f_zen_lbl = _font(_REGULAR, 18)
    f_status  = _font(_BOLD, 18)

    _center_generic(draw, "DAILY LOGIN REWARDS", f_head, CW, 34, (245, 245, 250))
    current_day = ((streak - 1) % 7) + 1
    _center_generic(draw, f"Streak: {streak} day{'s' if streak != 1 else ''}", f_sub, CW, 82, accent)

    n = 7
    box_w = 110
    gap = 20
    total_w = n * box_w + (n - 1) * gap
    x0 = (CW - total_w) // 2
    y0 = 135
    box_h = 190

    for i in range(n):
        day_num = i + 1
        x = x0 + i * (box_w + gap)
        done = day_num < current_day
        is_today = day_num == current_day

        if is_today:
            fill, outline, owidth = (24, 48, 40), accent, 3
        elif done:
            fill, outline, owidth = (24, 26, 24), (85, 115, 100), 2
        else:
            fill, outline, owidth = (20, 19, 30), (55, 53, 68), 2
        draw.rounded_rectangle([x, y0, x + box_w, y0 + box_h], radius=16, fill=fill, outline=outline, width=owidth)

        if is_today:
            draw.rounded_rectangle([x, y0, x + box_w, y0 + 34], radius=16, fill=accent)
            draw.rectangle([x, y0 + 18, x + box_w, y0 + 34], fill=accent)
            _center_generic(draw, "TODAY", f_status, box_w, y0 + 8, (10, 25, 20), x_offset=x)
            body_y = y0 + 46
        else:
            body_y = y0 + 20

        label_color = (235, 235, 240) if (is_today or done) else (140, 140, 155)
        _center_generic(draw, f"Day {day_num}", f_day, box_w, body_y, label_color, x_offset=x)

        zen = DAILY_REWARDS_FOR_CALENDAR[i]
        num_color = accent if is_today else ((210, 210, 220) if done else (120, 120, 135))
        _center_generic(draw, f"{zen:,}", f_zen_num, box_w, body_y + 46, num_color, x_offset=x)
        _center_generic(draw, "Zen", f_zen_lbl, box_w, body_y + 76, (150, 150, 165), x_offset=x)

        if done:
            _center_generic(draw, "\u2713 Claimed", f_status, box_w, y0 + box_h - 32, (120, 190, 150), x_offset=x)

    wm = "ASTRAL ABYSS"
    ww = _text_w(draw, wm, _font(_BOLD, 18))
    draw.text(((CW - ww) / 2, CH - 42), wm, font=_font(_BOLD, 18), fill=(95, 93, 108))

    img.save(out_path, "PNG")
    return out_path
