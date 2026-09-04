# ============================================================
#  ASTRAL ABYSS — 🎡 چرخِ شانسِ روزانه (Daily Fortune Wheel)
#  (daily_wheel.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  یه اکشنِ رایگان و روزانه: هر بازیکن یه‌بار در روز (به‌وقتِ UTC)
#  می‌تونه چرخ رو بچرخونه. جوایز از یه کیسه‌ی کوچیکِ زن تا جکپاتِ
#  گیرِ افسانه‌ای رو پوشش می‌دن — هیچ‌وقت دست‌خالی برنمی‌گردی، فقط
#  گاهی خیلی بیشتر می‌بری. اسپین‌های پشتِ‌سرهم (بدونِ جاافتادن یه
#  روز) یه «استریک» می‌سازن که هم پاداشِ زن رو زیاد می‌کنه هم تو
#  روزهای نشونه (۳/۷/۱۴/۳۰) یه پاداشِ اضافه‌ی مخصوص می‌ده.
#
#  از item_system (تولیدِ آیتم/مصرفی) می‌خونه؛ فیلدِ جدیدِ پلیر
#  (daily_wheel) رو خودش مدیریت می‌کنه، هیچ فیلدِ قدیمیِ دیگه‌ای رو
#  دستکاری نمی‌کنه.
# ============================================================
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# ─── ⚙️ تنظیمات ─────────────────────────────────────────────
STREAK_BONUS_PER_DAY = 0.04      # هر روزِ استریک، ۴٪ به پاداشِ زن اضافه می‌کنه
MAX_STREAK_BONUS = 0.60          # سقفِ بونوسِ استریک: ۶۰٪ (۱۵ روز)
MILESTONE_DAYS = (3, 7, 14, 30, 60, 100)

ZEN_BASE_PER_LEVEL = 12          # پایه‌ی زن به‌ازای هر لولِ بازیکن

# ─── 🎡 بخش‌های چرخ (وزن، نوع، جزئیات) ──────────────────────
WHEEL_SEGMENTS: list[dict] = [
    {"key": "zen_small",  "weight": 30, "type": "zen", "mult": (0.8, 1.3),  "label": "💰 کیسه‌ی زن"},
    {"key": "zen_medium", "weight": 20, "type": "zen", "mult": (1.6, 2.4),  "label": "💰💰 کیسه‌ی بزرگ‌تر"},
    {"key": "consumable", "weight": 18, "type": "consumable",               "label": "🧪 جعبه‌ی مصرفی"},
    {"key": "gear_common","weight": 14, "type": "gear", "rarity_pool": ["common", "uncommon"], "label": "📦 جعبه‌ی گیر"},
    {"key": "zen_big",    "weight": 8,  "type": "zen", "mult": (3.0, 5.0),  "label": "💎 گنجِ غیرمنتظره"},
    {"key": "gear_rare",  "weight": 7,  "type": "gear", "rarity_pool": ["rare", "epic"], "label": "✨ جعبه‌ی نایاب"},
    {"key": "gear_myth",  "weight": 3,  "type": "gear", "rarity_pool": ["mythic", "legendary"], "label": "🌟 جکپاتِ افسانه‌ای"},
]

MILESTONE_REWARD_BASE_ZEN = 500  # ضربدرِ شماره‌ی نشونه (روزِ ۷ => ۳۵۰۰ زن پایه)

WIN_REACTIONS = {
    "gear_myth": [
        "🌟 چرخ برای یه لحظه از حرکت وایساد... انگار خودشم شوکه شده بود.",
        "✨ نورِ طلاییِ چرخ تا چند ثانیه رو صورتت موند.",
    ],
    "gear_rare": [
        "✨ چرخ یه چرخشِ اضافه زد، انگار مطمئن می‌خواست بشه.",
    ],
    "zen_big": [
        "💎 صدای جرینگِ سکه‌ها بلندتر از همیشه بود.",
    ],
}


def _day_id(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _yesterday_id() -> str:
    return _day_id(datetime.now(timezone.utc) - timedelta(days=1))


def _weighted_choice(rng: random.Random, options: list[dict]) -> dict:
    weights = [o["weight"] for o in options]
    return rng.choices(options, weights=weights, k=1)[0]


def get_state(player: dict) -> dict:
    return player.setdefault("daily_wheel", {
        "day_id": "", "streak": 0, "best_streak": 0, "total_spins": 0,
    })


def can_spin(player: dict) -> bool:
    dw = get_state(player)
    return dw.get("day_id") != _day_id()


def time_until_reset() -> str:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    secs = int((tomorrow - now).total_seconds())
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return f"{h} ساعت و {m} دقیقه"


def _all_gear_templates() -> list[dict]:
    """پُولِ عمومیِ قالب‌های گیر — از رویِ همه‌ی غرفه‌های بازارِ محلیِ
    همه‌ی شهرها جمع می‌شه (city_markets.py) تا داده‌ی تکراری نسازیم."""
    import city_markets as cmkt
    pool = []
    for stalls in cmkt.CITY_MARKETS.values():
        for stall in stalls:
            pool.extend(stall.get("templates", []))
    return pool


def _build_gear_reward(rarity_pool: list[str], player_level: int, rng: random.Random) -> dict:
    import item_system as isy
    templates = _all_gear_templates()
    rarity = rng.choice(rarity_pool)
    if templates:
        template = dict(rng.choice(templates))
    else:
        template = {"name": "جایزه‌ی چرخِ شانس", "emoji": "🎁", "desc": "یه یادگاریِ چرخِ شانس."}
    item = isy.generate_item(template, player_level, forced_rarity=rarity, drop_source="daily_wheel")
    return item


def _build_reward(seg: dict, player: dict, streak_bonus: float, rng: random.Random) -> dict:
    level = max(1, player.get("level", 1))
    if seg["type"] == "zen":
        lo, hi = seg["mult"]
        base = ZEN_BASE_PER_LEVEL * level * rng.uniform(lo, hi)
        zen = max(20, int(base * (1 + streak_bonus)))
        return {"type": "zen", "amount": zen, "label": seg["label"]}

    if seg["type"] == "consumable":
        from item_system import generate_consumable
        item = generate_consumable(player_level=level)
        return {"type": "item", "item": item, "label": seg["label"]}

    if seg["type"] == "gear":
        item = _build_gear_reward(seg["rarity_pool"], level, rng)
        return {"type": "item", "item": item, "label": seg["label"]}

    return {"type": "zen", "amount": 20, "label": "🎁 هدیه"}


def _milestone_reward(streak_days: int, player: dict, rng: random.Random) -> dict:
    level = max(1, player.get("level", 1))
    idx = MILESTONE_DAYS.index(streak_days) if streak_days in MILESTONE_DAYS else 0
    zen = MILESTONE_REWARD_BASE_ZEN * (idx + 1) + streak_days * level
    item = _build_gear_reward(["rare", "epic"] if idx < 3 else ["epic", "mythic"], level, rng)
    return {"zen": zen, "item": item, "streak_days": streak_days}


def spin(player: dict) -> dict:
    """یه‌بار چرخ رو می‌چرخونه؛ پاداش رو مستقیماً به player اضافه
    می‌کنه (caller باید بعدش asave_player صدا بزنه). اگه امروز قبلاً
    اسپین کرده، {"ok": False, "reason": "already_spun"} برمی‌گردونه."""
    dw = get_state(player)
    today = _day_id()
    if dw.get("day_id") == today:
        return {"ok": False, "reason": "already_spun"}

    if dw.get("day_id") == _yesterday_id():
        dw["streak"] += 1
    else:
        dw["streak"] = 1
    dw["best_streak"] = max(dw.get("best_streak", 0), dw["streak"])
    dw["total_spins"] = dw.get("total_spins", 0) + 1
    dw["day_id"] = today

    rng = random.Random()
    streak_bonus = min(MAX_STREAK_BONUS, dw["streak"] * STREAK_BONUS_PER_DAY)
    seg = _weighted_choice(rng, WHEEL_SEGMENTS)
    reward = _build_reward(seg, player, streak_bonus, rng)
    _apply_reward(player, reward)

    milestone_reward = None
    if dw["streak"] in MILESTONE_DAYS:
        milestone_reward = _milestone_reward(dw["streak"], player, rng)
        player["zen"] = player.get("zen", 0) + milestone_reward["zen"]
        player.setdefault("inventory", []).append(milestone_reward["item"])

    reaction = None
    pool = WIN_REACTIONS.get(seg["key"])
    if pool:
        reaction = rng.choice(pool)

    return {
        "ok": True,
        "segment": seg,
        "reward": reward,
        "streak": dw["streak"],
        "streak_bonus": streak_bonus,
        "milestone_reward": milestone_reward,
        "reaction": reaction,
    }


def _apply_reward(player: dict, reward: dict):
    if reward["type"] == "zen":
        player["zen"] = player.get("zen", 0) + reward["amount"]
    elif reward["type"] == "item":
        player.setdefault("inventory", []).append(reward["item"])
