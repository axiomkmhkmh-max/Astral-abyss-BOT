# ============================================================
#  ASTRAL ABYSS — 🎭 خانواده‌ی بازی‌های گروهیِ سریع (Social Games)
#  (social_games.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  شش تا قابلیتِ سبک و وایرال برای گروه‌ها:
#    💀 ضایع کن   (ریپلای)  — طعنه بر اساسِ آمارِ واقعیِ بازیکن
#    🪙 شیر یا خط [مبلغ]   — کوین‌فلیپِ فوریِ ۵۰/۵۰
#    ⚔️ دوئل      (ریپلای)  — کوین‌فلیپِ نمایشی با فلیورِ جنگی
#    🔮 شانسم               — فالِ طعنه‌دارِ روزانه
#    🏷 لقب       (ریپلای)  — لقبِ تصادفیِ ۲۴ ساعته
#    🎯 قرعه / منم          — قرعه‌کشیِ ۶۰ ثانیه‌ای
#
#  state رو خودِ player doc نگه می‌داره (sg_state)؛ قرعه‌کشی‌ها
#  in-memory و per-chat هستن (۶۰ ثانیه‌ای‌ان، لازم نیست ماندگار باشن).
#  هیچ‌کدوم Zen از هیچ نمی‌سازن: شیر‌یا‌خط ۵۰/۵۰ و صفرجمعه، جایزه‌ی
#  قرعه از جیبِ خودِ شروع‌کننده می‌آد.
# ============================================================
from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from database import aget_player, asave_player, player_lock

TEHRAN = timezone(timedelta(hours=3, minutes=30))

# ─── ثابت‌ها ─────────────────────────────────────────────────
COIN_MIN = 100
COIN_MAX = 100_000
COIN_CD = 3                 # ثانیه بین دو شیر‌یا‌خط
ROAST_CD = 8                # ثانیه بین دو «ضایع کن» از یه نفر
DUEL_CD = 10
NICK_CD = 20
NICK_SEC = 24 * 3600
LOTTERY_SEC = 60
LOTTERY_GAP = 30            # فاصله‌ی بینِ دو قرعه تو یه چت
LOTTERY_PRIZE_MIN = 100
LOTTERY_PRIZE_MAX = 100_000

_cd: dict[tuple[str, int], float] = {}   # (کلید, uid) → زمانِ آزادشدن


def cooldown_left(kind: str, uid: int) -> int:
    return max(0, int(_cd.get((kind, uid), 0) - time.time() + 0.999))


def set_cooldown(kind: str, uid: int, seconds: int):
    _cd[(kind, uid)] = time.time() + seconds
    if len(_cd) > 5000:                      # جلوگیریِ رشدِ بی‌پایان
        now = time.time()
        for k in [k for k, v in _cd.items() if v < now]:
            _cd.pop(k, None)


# ─── ابزارهای متن ────────────────────────────────────────────
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize(text: str) -> str:
    """متنِ فارسی رو برای مچ‌کردن یکدست می‌کنه (ی/ک عربی، نیم‌فاصله، فاصله‌های اضافه)."""
    t = (text or "").strip()
    t = t.replace("ي", "ی").replace("ك", "ک").replace("ـ", "")
    t = t.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def clean_name(name: Optional[str]) -> str:
    """اسم‌ها رو از کاراکترهایی که فرمت‌دهیِ Markdown/HTML ربات رو می‌شکنن پاک می‌کنه."""
    n = re.sub(r"[*_`\[\]<>&]", "", name or "").strip()
    return (n[:24] or "یه ناشناس")


def parse_amount(raw: str) -> Optional[int]:
    """«۵۰۰»، «5,000»، «2k»، «۲ هزار» → عدد. اگه عددِ معتبر نبود None."""
    s = normalize(raw).translate(_FA_DIGITS).lower()
    s = s.replace(",", "").replace("،", "").replace("_", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(k|هزار|m|میلیون)?", s)
    if not m:
        return None
    val = float(m.group(1))
    mult = {"k": 1_000, "هزار": 1_000, "m": 1_000_000, "میلیون": 1_000_000}.get(m.group(2) or "", 1)
    val = int(val * mult)
    return val if val > 0 else None


# ─── مسیریابیِ دستورها ──────────────────────────────────────
_EXACT = {
    "ضایع کن": "roast", "ضایعش کن": "roast",
    "دوئل": "duel", "دوئل برق‌آسا": "duel", "دوئل برقاسا": "duel",
    "شانسم": "fortune", "شانسم چیه": "fortune", "شانسم چیه؟": "fortune",
    "لقب": "nick", "لقب بده": "nick",
}


def parse_command(text: str, chat_id: Optional[int] = None) -> Optional[tuple[str, str]]:
    """(دستور, آرگومان) یا None. «منم» فقط وقتی مچ می‌شه که تو همون چت قرعه‌ی فعال باشه."""
    t = normalize(text)
    if not t or len(t) > 40:
        return None
    if t in _EXACT:
        return _EXACT[t], ""
    if t == "منم":
        return ("join", "") if chat_id is not None and lottery_active(chat_id) else None
    m = re.fullmatch(r"شیر یا خط(?: (.+))?", t)
    if m:
        return "coin", (m.group(1) or "")
    m = re.fullmatch(r"قرعه(?: (.+))?", t)
    if m:
        return "lottery", (m.group(1) or "")
    return None


# ─── state روی player doc ───────────────────────────────────
def get_state(player: dict) -> dict:
    st = player.setdefault("sg_state", {})
    st.setdefault("fortune_day", None)
    st.setdefault("fortune_text", None)
    st.setdefault("nick", None)
    st.setdefault("duel_wins", 0)
    st.setdefault("duel_losses", 0)
    return st


def today_key() -> str:
    return datetime.now(TEHRAN).strftime("%Y-%m-%d")


def _week_id() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.isocalendar().year}-W{now.isocalendar().week}"


def _facts(p: dict) -> dict:
    """آمارِ واقعیِ بازیکن، یکدست‌شده — پایه‌ی ضایع‌کردن، فال و لقب."""
    zen = int(p.get("zen", 0) or 0)
    saved = int(p.get("savings_zen", 0) or 0)
    debt = int(p.get("bank_debt", 0) or 0) + int(p.get("loan_principal", 0) or 0)
    weekly = int(p.get("casino_weekly_net", 0) or 0) if p.get("casino_week_id") == _week_id() else 0
    max_hp = max(1, int(p.get("max_hp", 100) or 100))
    return {
        "zen": zen, "saved": saved, "total": zen + saved, "debt": debt,
        "kills": int(p.get("kills", 0) or 0),
        "pvp_w": int(p.get("pvp_wins", 0) or 0),
        "pvp_l": int(p.get("pvp_losses", 0) or 0),
        "deaths": int(p.get("death_count", 0) or 0),
        "level": int(p.get("level", 1) or 1),
        "streak": int(p.get("login_streak", 0) or 0),
        "weekly": weekly,
        "hp_pct": int(100 * int(p.get("hp", max_hp) or 0) / max_hp),
        "female": p.get("gender") == "female",
    }


# ─── 💀 ضایع کن ─────────────────────────────────────────────
_ROAST_GENERIC = [
    "{n} اونقدر معمولیه که حتی ضایع‌کردنش هم حوصله می‌خواد 🥱",
    "اگه بی‌حالی المپیک داشت، {n} هنوز تو مرحله‌ی ثبت‌نام بود 🏅",
    "{n} تو محفل مثل وای‌فای ضعیفه؛ همه می‌دونن هست، کسی ازش استفاده نمی‌کنه 📶",
    "شمشیرِ {n} بیشتر برای عکس گرفتنه تا جنگیدن 🗡📸",
]


def roast_line(target: dict, name: str) -> str:
    f = _facts(target)
    c: list[str] = []
    if f["debt"] > 0:
        c += [f"{{n}} با {f['debt']:,} Zen بدهی هنوز ادای آدم‌حسابی‌ها رو درمیاره؟ بانک بیشتر از مامانش بهش زنگ می‌زنه 📞💀"] * 2
    if f["total"] < 2_000:
        c += ["بانکِ {n} از یه گدای محفل خالی‌تره 💀",
              f"{{n}} فقط {f['total']:,} Zen داره؛ تو بازار سیاه حتی بوی غذا هم بهش حساب می‌کنن 🍞"] * 2
    elif f["total"] >= 1_000_000:
        c += [f"{{n}} {f['total']:,} Zen داره و هنوز لباسش مال لول یکه؛ پولدارِ خسیس‌ترین نوعه 🦆💸"]
    if f["pvp_l"] >= 3 and f["pvp_l"] > f["pvp_w"]:
        c += [f"{{n}} {f['pvp_l']} بار تو آرنا باخته؛ آرنا براش شده خونه‌ی دوم 🏚"] * 2
    if f["pvp_w"] == 0 and f["pvp_l"] == 0:
        c += ["{n} هنوز یه بار هم پا تو آرنا نذاشته؛ شمشیرش از بس تمیزه انگار فقط عکسشو دیده 🗡"]
    if f["deaths"] >= 5:
        c += [f"{{n}} {f['deaths']} بار مرده؛ قبرستون براش کارتِ مشتریِ ثابت صادر کرده ⚰️"] * 2
    if f["kills"] < 10:
        c += [f"{{n}} با {f['kills']} تا کیل؟ مرغ‌های روستا هم بیشتر شکار می‌کنن 🐔"] * 2
    if f["level"] <= 5:
        c += [f"لولِ {f['level']}؟ اسلایم‌ها دارن به {{n}} ترحم می‌کنن 🟢"]
    if f["weekly"] < -2_000:
        c += [f"{{n}} این هفته {abs(f['weekly']):,} Zen به کازینو هدیه داده؛ صاحبش داره براش تولد می‌گیره 🎰🎂"] * 2
    if f["hp_pct"] < 30:
        c += [f"جونِ {{n}} {f['hp_pct']}٪ مونده؛ حتی نسیمِ ملایم هم تهدیدشه 🍃"]
    if f["streak"] <= 1:
        c += ["وفاداریِ {n} به این ربات از وفاداریِ گربه به صاحبش هم کمتره 🐈"]
    if not c:
        c = _ROAST_GENERIC
    return random.choice(c).replace("{n}", name)


# ─── 🪙 شیر یا خط ───────────────────────────────────────────
COIN_WIN = [
    "سکه چرخید و… شانس باهات یار شد! 🍀",
    "سکه رو هوا رقصید و رو به تو فرود اومد ✨",
    "شانسِ امشب با توئه؛ محفل داره حسودی می‌کنه 😏",
]
COIN_LOSE = [
    "سکه افتاد و Zen رفت… خداحافظ پول 👋💸",
    "سکه تو چشمات نگاه کرد و برعکس افتاد 🫠",
    "شانس امروز یه استراحتِ کوتاه کرد؛ کیف پولت پرداختش رو کرد 🕳",
]


def flip_coin(player: dict, stake: int) -> dict:
    """سکه می‌ندازه (۵۰/۵۰). باید زیر player_lock صدا زده بشه؛ ذخیره با caller."""
    if stake < COIN_MIN:
        return {"ok": False, "err": f"حداقلِ مبلغ {COIN_MIN:,} Zen هست."}
    if stake > COIN_MAX:
        return {"ok": False, "err": f"حداکثرِ مبلغ {COIN_MAX:,} Zen هست."}
    if int(player.get("zen", 0) or 0) < stake:
        return {"ok": False, "err": f"Zen کافی نداری! موجودی: {int(player.get('zen', 0) or 0):,}"}
    won = random.random() < 0.5
    player["zen"] = int(player.get("zen", 0) or 0) + (stake if won else -stake)
    return {
        "ok": True, "won": won,
        "side": "🌕 شیر" if random.random() < 0.5 else "🌑 خط",   # فقط نمایشی
        "flavor": random.choice(COIN_WIN if won else COIN_LOSE),
        "zen": player["zen"],
    }


# ─── ⚔️ دوئل ────────────────────────────────────────────────
DUEL_INTRO = [
    "⚔️ {a} و {b} تیغ کشیدن... هوا سنگین شد 🗡",
    "⚔️ {a} روبه‌روی {b} ایستاد؛ سکوتِ قبل از طوفان...",
    "⚔️ چالشِ برق‌آسا! {a} در برابر {b} 🔥",
]
DUEL_RESULT = [
    "شمشیرا به هم خوردن... {w} برنده شد! ⚔️🏆",
    "جرقه پرید، خاک بلند شد... {w} ایستاده موند! 🏆",
    "یه ضربه‌ی دقیق و تمام — {w} برنده‌ست! 💥🏆",
    "{l} تلاش کرد ولی {w} یه قدم جلوتر بود! 🏆",
]


def duel_flip(a_name: str, b_name: str) -> dict:
    a_wins = random.random() < 0.5
    w, l = (a_name, b_name) if a_wins else (b_name, a_name)
    return {
        "a_wins": a_wins, "winner": w, "loser": l,
        "intro": random.choice(DUEL_INTRO).format(a=a_name, b=b_name),
        "result": random.choice(DUEL_RESULT).format(w=w, l=l),
    }


def record_duel(player: dict, won: bool):
    st = get_state(player)
    st["duel_wins" if won else "duel_losses"] += 1


# ─── 🔮 شانسم ───────────────────────────────────────────────
_FORTUNE_RANDOM = [
    "امروز یکی بهت لبخند می‌زنه؛ احتمالاً چون بهت می‌خنده 😌",
    "ستاره‌ها می‌گن امروز نقشه‌ات رو عوض نکن… چون نقشه نداری 🌠",
    "کسی که ازش بدت میاد امروز لول‌آپ می‌کنه. آماده باش 🫠",
    "اتفاقِ خوبی تو راهه — ولی تو ترافیک گیر کرده 🚗",
    "امروز یه گربه‌ی سیاه از جلوت رد می‌شه؛ ولی اون نگران‌تره تا تو 🐈‍⬛",
    "امروز هر چی بخوای می‌شه… فقط هر چی نخوای هم می‌شه 🎲",
    "جهان بهت پیام داده، ولی تو ناخونده‌ها رو بلاک کرده بودی 📵",
    "امروز بهترین روزِ تو برای ریسک‌کردنه… یا نه. ستاره‌ها هم نمی‌دونن 🤷",
]
_FORTUNE_COLORS = ["بنفشِ هاله‌ای 🟣", "سبزِ جنگلِ سایه 🟢", "قرمزِ خونین 🔴", "آبیِ آبیس 🔵", "طلاییِ زن 🟡", "سیاهِ بی‌پایان ⚫"]


def _fortune_state_line(p: dict) -> str:
    f = _facts(p)
    c: list[str] = []
    if f["hp_pct"] < 40:
        c.append(f"جونت {f['hp_pct']}٪ مونده؛ امروز با هیچ باسی شوخی نکن ❤️‍🩹")
    if f["debt"] > 0:
        c.append(f"بدهیِ {f['debt']:,} Zen هنوز رو سرته؛ امروز مدیرِ بانک خوابِ تو رو می‌بینه 🏦")
    if f["total"] >= 500_000:
        c.append("پولت زیاده ولی امروز یکی می‌خواد قرضش بگیره؛ بگو «بانک بسته‌ست» 💼")
    elif f["total"] < 2_000:
        c.append("کیف پولت خالیه؛ امروز شانس تنها چیزیه که مجانیه 🪙")
    if f["pvp_l"] > f["pvp_w"] and f["pvp_l"] >= 3:
        c.append("آرنا امروز هم منتظرته… ولی شاید امروز سمتش نرو 🏟")
    if f["pvp_w"] > f["pvp_l"] and f["pvp_w"] >= 3:
        c.append("آمارِ آرنات خوبه؛ امروز غرور اولین دشمنته 👑")
    if f["deaths"] >= 5:
        c.append(f"{f['deaths']} بار مردی؛ امروز احتیاط کن، قبرستون هنوز اسمت رو یادشه ⚰️")
    if f["weekly"] < -2_000:
        c.append("این هفته کازینو بهت لبخند نزده؛ امروز هم نزنه بهتره 🎰")
    if f["kills"] < 10:
        c.append("کیل‌هات کمه؛ امروز شاید یه اسلایمِ بی‌دفاع ازت شکست بخوره 🟢")
    if not c:
        c.append(f"لولِ {f['level']}؛ نه ضعیفی نه قوی — دقیقاً یه آدمِ معمولی 😐")
    return random.choice(c)


def draw_fortune(player: dict, name: str) -> tuple[bool, str]:
    """(جدید؟, متن). روزی یه‌بار؛ دفعه‌ی دوم همون فالِ قبلی رو برمی‌گردونه. ذخیره با caller."""
    st = get_state(player)
    day = today_key()
    if st["fortune_day"] == day and st["fortune_text"]:
        return False, st["fortune_text"]
    text = (
        f"🔮 **فالِ امروزِ {name}**\n\n"
        f"📊 {_fortune_state_line(player)}\n"
        f"🌌 {random.choice(_FORTUNE_RANDOM)}\n\n"
        f"🔢 عددِ شانس: **{random.randint(1, 99)}**\n"
        f"🎨 رنگِ شانس: {random.choice(_FORTUNE_COLORS)}"
    )
    st["fortune_day"], st["fortune_text"] = day, text
    return True, text


# ─── 🏷 لقب ─────────────────────────────────────────────────
# (حالتِ پایه, حالتِ مؤنث یا None)
_NICKS_GENERIC = [
    ("🐌 لاکپشتِ محفل", None), ("👑 شاهِ ضرر", "👑 ملکه‌ی ضرر"), ("🦆 اردکِ سیاه", None),
    ("🍞 نونِ‌خشکِ محفل", None), ("🧌 غولِ تنبل", "🧌 غولِ تنبل"), ("🐸 قورباغه‌ی شانسی", None),
    ("🎭 دلقکِ دربار", None), ("🐈 گربه‌ی ولگرد", None), ("🧙 جادوگرِ کم‌حوصله", None),
    ("🥔 سیب‌زمینیِ جنگجو", None), ("🦥 تنبلِ افسانه‌ای", None), ("🕳 چاهِ بی‌ته", None),
    ("🔔 زنگوله‌ی گروه", None), ("🍉 هندوانه‌ی بی‌جنگ", None), ("🤡 دلقکِ ارشد", None),
]


def _nick_pool(p: dict) -> list[tuple[str, Optional[str]]]:
    f = _facts(p)
    pool: list[tuple[str, Optional[str]]] = []
    if f["pvp_l"] > f["pvp_w"] and f["pvp_l"] >= 3:
        pool.append(("🥀 مهمانِ همیشگیِ آرنا", None))
    if f["deaths"] >= 5:
        pool.append(("⚰️ مشتریِ ثابتِ قبرستان", None))
    if f["total"] < 2_000:
        pool.append(("🪙 گدای محفل", None))
    if f["total"] >= 500_000:
        pool.append(("💰 قارونِ محفل", None))
    if f["kills"] >= 200:
        pool.append(("🗡 قصابِ محفل", None))
    if f["weekly"] < -2_000:
        pool.append(("🎰 هدیه‌دهنده‌ی کازینو", None))
    if f["debt"] > 0:
        pool.append(("📞 مشتریِ ویژه‌ی بانک", None))
    return pool


def give_nick(target: dict, giver_name: str) -> dict:
    """لقبِ ۲۴ ساعته. اگه ۵۰٪ شانس خورد از آمارِ واقعی، وگرنه از لیستِ عمومی. ذخیره با caller."""
    st = get_state(target)
    pool = _nick_pool(target)
    base, fem = random.choice(pool if pool and random.random() < 0.5 else _NICKS_GENERIC)
    label = fem if (fem and target.get("gender") == "female") else base
    had_old = bool(nick_label(target))
    st["nick"] = {"label": label, "until": time.time() + NICK_SEC, "by": giver_name}
    return {"label": label, "replaced": had_old}


def nick_label(player: dict) -> Optional[str]:
    n = (player.get("sg_state") or {}).get("nick")
    if n and n.get("until", 0) > time.time():
        return n.get("label")
    return None


def display_name(player: dict, fallback: str = "—") -> str:
    """اسمِ بازیکن + لقبِ فعالش (اگه داشت). برای نمایش تو پیام‌ها."""
    name = clean_name(player.get("name") or fallback)
    lab = nick_label(player)
    return f"{lab} {name}" if lab else name


# ─── 🎯 قرعه‌ی برق‌آسا ──────────────────────────────────────
_LOTTERIES: dict[int, dict] = {}
_LOTTERY_LAST_END: dict[int, float] = {}
_tasks: set = set()


def lottery_active(chat_id: int) -> bool:
    return chat_id in _LOTTERIES


def lottery_gap_left(chat_id: int) -> int:
    return max(0, int(_LOTTERY_LAST_END.get(chat_id, 0) + LOTTERY_GAP - time.time() + 0.999))


def lottery_create(chat_id: int, starter_uid: int, starter_name: str, prize: int) -> bool:
    if chat_id in _LOTTERIES:
        return False
    _LOTTERIES[chat_id] = {
        "starter": starter_uid, "starter_name": starter_name, "prize": prize,
        "entrants": {}, "ends_at": time.time() + LOTTERY_SEC,
    }
    return True


def lottery_join(chat_id: int, uid: int, name: str) -> str:
    """'joined' | 'already' | 'none'"""
    lot = _LOTTERIES.get(chat_id)
    if not lot:
        return "none"
    if uid in lot["entrants"]:
        return "already"
    lot["entrants"][uid] = name
    return "joined"


def lottery_info(chat_id: int) -> Optional[dict]:
    return _LOTTERIES.get(chat_id)


async def _finish_lottery(chat_id: int, send: Callable[[str], Awaitable[None]]):
    lot = _LOTTERIES.get(chat_id)
    if not lot:
        return
    try:
        entrants: dict[int, str] = lot["entrants"]
        prize = lot["prize"]
        if not entrants:
            await send("🎯 **قرعه تموم شد** — هیچ‌کس نیومد! 🦗\nیه‌بار دیگه امتحان کنین.")
            return

        winner_uid = random.choice(list(entrants))
        winner_name = entrants[winner_uid]
        paid_line = ""
        if prize > 0:
            starter = lot["starter"]
            async with player_lock(starter):
                sp = await aget_player(starter)
                if not sp or int(sp.get("zen", 0) or 0) < prize:
                    paid_line = f"\n\n⚠️ شروع‌کننده تا آخرِ قرعه Zen کافی نداشت؛ جایزه‌ی {prize:,} Zen پرداخت نشد."
                    prize = 0
                elif winner_uid != starter:
                    sp["zen"] = int(sp["zen"]) - prize
                    await asave_player(starter, sp)
            if prize > 0 and winner_uid != starter:
                async with player_lock(winner_uid):
                    wp = await aget_player(winner_uid)
                    if wp:
                        wp["zen"] = int(wp.get("zen", 0) or 0) + prize
                        await asave_player(winner_uid, wp)
                paid_line = f"\n\n💰 جایزه: **{prize:,} Zen** (از جیبِ {lot['starter_name']}) به حسابش ریخته شد!"
            elif prize > 0:
                paid_line = "\n\n💰 برنده خودِ شروع‌کننده بود؛ جایزه سرِ جاش موند 😂"

        await send(
            f"🎯 **قرعه تموم شد!**\n\n"
            f"👥 شرکت‌کننده‌ها: {len(entrants)} نفر\n"
            f"🏆 برنده: **{winner_name}**{paid_line}"
        )
    finally:
        _LOTTERIES.pop(chat_id, None)
        _LOTTERY_LAST_END[chat_id] = time.time()


def schedule_lottery_end(chat_id: int, send: Callable[[str], Awaitable[None]], seconds: int = LOTTERY_SEC):
    async def _runner():
        try:
            await asyncio.sleep(seconds)
            await _finish_lottery(chat_id, send)
        except Exception:
            _LOTTERIES.pop(chat_id, None)     # هیچ‌وقت چت رو قفل نکن
            _LOTTERY_LAST_END[chat_id] = time.time()
            raise
    t = asyncio.create_task(_runner())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
