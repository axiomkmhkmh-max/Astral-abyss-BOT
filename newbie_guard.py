# ============================================================
#  ASTRAL ABYSS — Newbie Guard (حفاظتِ تازه‌کار + برچسبِ خطرِ دشمن)
# ------------------------------------------------------------
#  مشکل: پلیرِ جدید اولین بار می‌میره و بلافاصله ۲۰٪ Zen، ۵٪ XP، یه آیتم،
#  نفرینِ ۳ روزه (-۲۰٪ دمیج) و قفلِ درمانِ ۱ ساعته می‌گیره → دفعه‌ی بعد
#  ضعیف‌تر می‌جنگه و دوباره می‌میره (مارپیچِ مرگ) → حذفِ بازی.
#  راه‌حل: تا سطحِ NEWBIE_LEVEL مرگ «آموزشیه» (بدونِ هیچ جریمه‌ای) و
#  قبل از هر نبرد، خطرِ هر دشمن با رنگ نشون داده می‌شه.
# ============================================================
NEWBIE_LEVEL = 10


def is_newbie(player: dict) -> bool:
    return (player.get("level", 1) <= NEWBIE_LEVEL
            and player.get("rebirth_count", 0) == 0)


def light_death_lines(player: dict) -> list[str]:
    """جایگزینِ apply_hardcore_death_penalty برای تازه‌کارها: هیچ جریمه‌ای نیست."""
    player["hp"] = max(player.get("hp", 1), int(player.get("max_hp", 100)))
    player["death_curse_until"] = 0
    player["heal_lockout_until"] = 0
    return [
        f"🛡️ **حفاظتِ تازه‌کار** (تا سطح {NEWBIE_LEVEL}): این بار چیزی از دست ندادی — "
        "نه Zen، نه XP، نه آیتم، نه نفرین.",
        "💡 قبل از نبرد، کنارِ هر دشمن یه رنگِ خطر هست: 🟢 امن · 🟡 متوسط · 🔴 خطرناک. "
        "با ✅ پیشنهادی شروع کن.",
    ]


def danger_tag(player: dict, enemy: dict) -> tuple[str, str]:
    """(ایموجی, برچسب) — بر اساسِ اینکه HP بازیکن چند ضربه‌ی دشمن رو تحمل می‌کنه."""
    hp = max(1, int(player.get("hp", 100)))
    dmg = max(1, int(enemy.get("dmg", 1) or 1))
    hits = hp / dmg
    if hits >= 8:
        return "🟢", "امن"
    if hits >= 4:
        return "🟡", "متوسط"
    return "🔴", "خطرناک"
