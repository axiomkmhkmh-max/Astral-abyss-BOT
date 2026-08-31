# ============================================================
#  ASTRAL ABYSS RPG — Class Ascension System
#  (class_ascension_system.py)
# ============================================================
#
# سیستمِ «ارتقای کلاس»: از لولِ ۱۵ به بعد، هر کدوم از ۴ کلاسِ اصلی
# (جادوگر/ماجراجو/تاجر/درمانگر) دو مسیرِ پیشرفتِ جداگانه دارن. هر
# مسیر یه شرطِ مخصوصِ خودشو داره — نه فقط لول، بلکه یه متریکِ
# مکانیزمِ همون کلاس که از قبل تو class_system_data ثبت می‌شه
# (مثلاً تعدادِ طلسمِ ترکیبیِ جادوگر، یا تعدادِ دخمه‌ی پاک‌شده‌ی
# ماجراجو) — یعنی بازیکن با «بازی‌کردنِ» به سبکِ اون مسیر بهش
# نزدیک‌تر می‌شه، نه فقط با فارمِ لول.
#
# انتخاب دائمیه (یه‌بار برای هر کاراکتر) — دقیقاً مثلِ خودِ انتخابِ
# کلاس تو class_system.py. موقعِ ارتقا یه بونوسِ پایه‌ی یه‌بارمصرف
# (استتِ فلت) روی player["stats"] می‌شینه + یه بونوسِ پسیوِ همیشگی
# (ascension_bonus) که combat.py کنارِ بقیه‌ی بونوس‌های کلاس‌محور
# مصرفش می‌کنه.
# ============================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle

ASCENSION_MIN_LEVEL = 15

# ─── جدولِ مسیرها ────────────────────────────────────────────
# metric: کلیدی که از class_system_data خونده می‌شه (یا یکی از
# متریک‌های خاصِ زیر که lenِ یه لیستن).
LIST_LENGTH_METRICS = {
    "relics_count":  "relics_collected",
    "mercs_count":   "mercenaries_hired",
}

ASCENSION_PATHS = {
    "wizard": [
        {
            "id": "flame_archon",
            "class": "wizard",
            "name_fa": "آرشون شعله",
            "emoji": "🔥",
            "tagline": "قدرتِ خام و انفجارِ عنصری",
            "desc": "دمیجِ طلسم‌های ترکیبی و طوفانِ ناحیه‌ای بیشتر می‌شه؛ کریت و ضریبِ دمیج به‌صورتِ دائمی بالا می‌ره.",
            "req_metric": "synergy_combos_used",
            "req_metric_val": 15,
            "req_metric_label": "طلسمِ ترکیبیِ موفق",
            "stat_bonus": {"atk": 8, "hp": 10},
            "passive": {"dmg_mult_add": 0.12, "crit_add": 0.05, "lifesteal": 0.0, "defense_pct": 0.0},
        },
        {
            "id": "ward_sentinel",
            "class": "wizard",
            "name_fa": "نگهبانِ طلسم",
            "emoji": "🛡",
            "tagline": "بقا و دفاعِ آرکین",
            "desc": "سپرِ مانا محکم‌تر می‌شه، دمیجِ ضدحمله‌ی دشمن کمتر می‌شه و بخشی از دمیجِ واردشده به‌صورتِ لایف‌استیل برمی‌گرده.",
            "req_metric": "mana_shield_charges",
            "req_metric_val": 10,
            "req_metric_label": "فعال‌سازیِ سپرِ مانا",
            "stat_bonus": {"def": 6, "hp": 25},
            "passive": {"dmg_mult_add": 0.0, "crit_add": 0.0, "lifesteal": 0.03, "defense_pct": 0.08},
        },
    ],
    "adventurer": [
        {
            "id": "shadow_hunter",
            "class": "adventurer",
            "name_fa": "شکارچیِ سایه",
            "emoji": "🗡",
            "tagline": "دمیج و ضربه‌ی بحرانیِ خالص",
            "desc": "کریت و ضریبِ دمیجِ حمله به‌صورتِ دائمی بالا می‌ره — مسیرِ کسی که بیشتر تو دخمه‌ها و نبرد می‌جنگه.",
            "req_metric": "dungeons_cleared",
            "req_metric_val": 20,
            "req_metric_label": "دخمه‌ی پاک‌شده",
            "stat_bonus": {"atk": 7, "def": 2},
            "passive": {"dmg_mult_add": 0.08, "crit_add": 0.07, "lifesteal": 0.0, "defense_pct": 0.0},
        },
        {
            "id": "mythic_seeker",
            "class": "adventurer",
            "name_fa": "گنج‌یابِ اساطیری",
            "emoji": "🗝",
            "tagline": "اکتشاف و رلیک در سطحِ افسانه‌ای",
            "desc": "شانسِ پیداکردنِ رلیک و فرارِ تله برای همیشه بیشتر می‌شه؛ کمی دمیج و دفاعِ اضافه هم می‌گیری.",
            "req_metric": "relics_count",
            "req_metric_val": 15,
            "req_metric_label": "رلیکِ جمع‌شده",
            "stat_bonus": {"def": 4, "hp": 15},
            "passive": {"dmg_mult_add": 0.03, "crit_add": 0.0, "lifesteal": 0.0, "defense_pct": 0.04,
                        "exploration_luck_add": 8, "relic_find_pct_add": 0.04},
        },
    ],
    "merchant": [
        {
            "id": "trade_baron",
            "class": "merchant",
            "name_fa": "بارونِ تجارت",
            "emoji": "💰",
            "tagline": "امپراتوریِ اقتصادی",
            "desc": "ضریبِ درآمدِ طلا برای همیشه بالاتر می‌ره (+۰.۱۵) و کمی HP اضافه می‌گیری.",
            "req_metric": "market_influence",
            "req_metric_val": 15,
            "req_metric_label": "نفوذِ بازار",
            "stat_bonus": {"hp": 15},
            "passive": {"dmg_mult_add": 0.05, "crit_add": 0.0, "lifesteal": 0.0, "defense_pct": 0.05},
            "gold_multiplier_bonus": 0.15,
        },
        {
            "id": "shadow_broker",
            "class": "merchant",
            "name_fa": "استادِ سایه‌بازار",
            "emoji": "🕶",
            "tagline": "مزدور و معاملات پشتِ‌پرده",
            "desc": "مزدورهات قوی‌تر می‌جنگن و شانسِ کریتِ خودت هم بیشتر می‌شه.",
            "req_metric": "mercs_count",
            "req_metric_val": 3,
            "req_metric_label": "مزدورِ اجیرشده",
            "stat_bonus": {"atk": 6, "def": 3},
            "passive": {"dmg_mult_add": 0.0, "crit_add": 0.05, "lifesteal": 0.04, "defense_pct": 0.0},
        },
    ],
    "healer": [
        {
            "id": "radiant_priest",
            "class": "healer",
            "name_fa": "کشیشِ نور",
            "emoji": "🌟",
            "tagline": "هیل و ساپورتِ خالص",
            "desc": "بخشِ بیشتری از دمیجِ واردشده به‌صورتِ لایف‌استیل برمی‌گرده و HP پایه‌ت بیشتر می‌شه.",
            "req_metric": "undead_purged",
            "req_metric_val": 10,
            "req_metric_label": "مردهٔ متحرکِ پاک‌شده",
            "stat_bonus": {"hp": 30},
            "passive": {"dmg_mult_add": 0.0, "crit_add": 0.0, "lifesteal": 0.06, "defense_pct": 0.03},
        },
        {
            "id": "divine_guardian",
            "class": "healer",
            "name_fa": "نگهبانِ الهی",
            "emoji": "🕊",
            "tagline": "دفاعِ الهیِ تمام‌عیار",
            "desc": "دمیجِ ضدحمله‌ی دشمن به‌طورِ محسوسی کمتر می‌شه — عملاً یه تانکِ درمانگر.",
            "req_metric": "divine_shield_charges",
            "req_metric_val": 15,
            "req_metric_label": "فعال‌سازیِ سپرِ الهی",
            "stat_bonus": {"def": 8, "hp": 20},
            "passive": {"dmg_mult_add": 0.0, "crit_add": 0.0, "lifesteal": 0.0, "defense_pct": 0.10},
        },
    ],
}


def paths_for_class(class_id: str) -> list[dict]:
    return ASCENSION_PATHS.get(class_id, [])


def get_path(path_id: str) -> dict | None:
    for paths in ASCENSION_PATHS.values():
        for p in paths:
            if p["id"] == path_id:
                return p
    return None


def _metric_value(player: dict, metric_key: str) -> int:
    csd = player.get("class_system_data", {})
    if metric_key in LIST_LENGTH_METRICS:
        return len(csd.get(LIST_LENGTH_METRICS[metric_key], []) or [])
    return csd.get(metric_key, 0)


def current_ascension_path(player: dict) -> dict | None:
    csd = player.get("class_system_data", {})
    pid = csd.get("ascension_path")
    return get_path(pid) if pid else None


def is_ascension_unlocked(player: dict) -> bool:
    """آیا اصلاً منوی ارتقا (از لولِ ۱۵ به بعد) برای این بازیکن باز شده."""
    return player.get("level", 1) >= ASCENSION_MIN_LEVEL


def path_requirement_status(player: dict, path: dict) -> dict:
    """پیشرفتِ بازیکن نسبت به شرطِ یه مسیرِ خاص رو برمی‌گردونه."""
    level_ok = player.get("level", 1) >= ASCENSION_MIN_LEVEL
    have = _metric_value(player, path["req_metric"])
    need = path["req_metric_val"]
    metric_ok = have >= need
    return {
        "level_ok": level_ok,
        "level": player.get("level", 1),
        "metric_ok": metric_ok,
        "have": have,
        "need": need,
        "eligible": level_ok and metric_ok,
    }


def meets_requirement(player: dict, path_id: str) -> bool:
    path = get_path(path_id)
    if not path:
        return False
    return path_requirement_status(player, path)["eligible"]


def ascend(player: dict, path_id: str) -> dict:
    """ارتقای واقعی رو انجام می‌ده — فقط یه‌بار در طولِ عمرِ کاراکتر."""
    path = get_path(path_id)
    if not path:
        return {"ok": False, "msg": "❌ همچین مسیری وجود نداره."}

    if player.get("class") != path["class"]:
        return {"ok": False, "msg": "❌ این مسیرِ ارتقا مخصوصِ کلاسِ تو نیست."}

    csd = player.setdefault("class_system_data", {})
    if csd.get("ascension_path"):
        existing = get_path(csd["ascension_path"])
        name = existing["name_fa"] if existing else csd["ascension_path"]
        return {"ok": False, "msg": f"❌ تو قبلاً وارد مسیرِ «{name}» شدی — این انتخاب دائمیه."}

    status = path_requirement_status(player, path)
    if not status["level_ok"]:
        return {"ok": False, "msg": f"❌ حداقل باید لولِ {ASCENSION_MIN_LEVEL} باشی (الان لولِ {status['level']}ای)."}
    if not status["metric_ok"]:
        return {
            "ok": False,
            "msg": f"❌ هنوز شرطِ این مسیر کامل نشده: {path['req_metric_label']} — {status['have']}/{status['need']}",
        }

    # ─── اعمالِ بونوسِ فلتِ یه‌بارمصرف روی استت‌ها ────────────────
    stats = player.setdefault("stats", {})
    for key, val in path["stat_bonus"].items():
        if key == "hp":
            stats["hp"] = stats.get("hp", 0) + val
            stats["max_hp"] = stats.get("max_hp", 0) + val
        else:
            stats[key] = stats.get(key, 0) + val
    # لایه‌ی سازگاریِ hp/max_hp تاپ‌لول (طبقِ همون قراردادِ class_system.py)
    player["hp"] = player.get("hp", 0) + path["stat_bonus"].get("hp", 0)
    player["max_hp"] = player.get("max_hp", 0) + path["stat_bonus"].get("hp", 0)

    if "gold_multiplier_bonus" in path:
        csd["gold_multiplier"] = round(csd.get("gold_multiplier", 1.0) + path["gold_multiplier_bonus"], 4)

    csd["ascension_path"] = path_id

    return {"ok": True, "path": path}


def ascension_bonus(player: dict) -> dict:
    """بونوسِ پسیوِ همیشگیِ مسیرِ انتخاب‌شده — combat.py این‌رو کنارِ
    بقیه‌ی بونوس‌های کلاس‌محور جمع می‌زنه. اگه هنوز ارتقا نگرفته، همه صفره."""
    default = {"dmg_mult_add": 0.0, "crit_add": 0.0, "lifesteal": 0.0, "defense_pct": 0.0}
    path = current_ascension_path(player)
    if not path:
        return default
    out = dict(default)
    out.update(path.get("passive", {}))
    return out


# ─── متن‌ها و کیبوردها ───────────────────────────────────────
def ascension_status_text(player: dict) -> str:
    cls = player.get("class")
    if cls not in ASCENSION_PATHS:
        return "❌ این بخش فقط برای جادوگر/ماجراجو/تاجر/درمانگره."

    current = current_ascension_path(player)
    if current:
        lines = [
            f"{current['emoji']} **مسیرِ ارتقای تو: {current['name_fa']}**",
            f"_{current['tagline']}_\n",
            f"{current['desc']}",
        ]
        return "\n".join(lines)

    if not is_ascension_unlocked(player):
        return (
            f"🔒 **ارتقای کلاس از لولِ {ASCENSION_MIN_LEVEL} باز می‌شه.**\n"
            f"الان لولِ {player.get('level',1)}ای — با بالارفتنِ لول و بازی به سبکِ خودت، "
            f"شرطِ یکی از دو مسیر رو کامل کن و انتخاب کن."
        )

    lines = [f"⚜️ **دو مسیرِ ارتقای کلاسِ تو — یه انتخابِ دائمی:**\n"]
    for path in paths_for_class(cls):
        st = path_requirement_status(player, path)
        mark = "✅" if st["eligible"] else "🔒"
        lines.append(
            f"{mark} {path['emoji']} **{path['name_fa']}** — {path['tagline']}\n"
            f"   {path['desc']}\n"
            f"   شرط: {path['req_metric_label']} — {st['have']}/{st['need']}\n"
        )
    return "\n".join(lines)


def ascension_kb(player: dict) -> InlineKeyboardMarkup | None:
    cls = player.get("class")
    if cls not in ASCENSION_PATHS:
        return None
    if current_ascension_path(player):
        return None
    if not is_ascension_unlocked(player):
        return None

    rows = []
    for path in paths_for_class(cls):
        st = path_requirement_status(player, path)
        prefix = "✅" if st["eligible"] else "🔒"
        rows.append([InlineKeyboardButton(
            text=f"{prefix} {path['emoji']} {path['name_fa']}",
            callback_data=f"asc_view:{path['id']}",
            style=ButtonStyle.PRIMARY,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ascension_confirm_kb(path_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید و ارتقا (دائمیه!)", callback_data=f"asc_confirm:{path_id}",
                              style=ButtonStyle.PRIMARY),
        InlineKeyboardButton(text="🔙 برگشت", callback_data="asc_back", style=ButtonStyle.DANGER),
    ]])
