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


# ═══════════════════════════════════════════════════════════════
#  بازشدنِ تدریجیِ مبارزه (ساده‌سازی)
# ═══════════════════════════════════════════════════════════════
# هر نوعِ حمله از چه سطحی باز می‌شه — قبلش اصلاً تو پنل دیده نمی‌شه.
ATTACK_UNLOCK = {"quick": 1, "heavy": 5, "element": 10, "combo": 10, "ultimate": 15, "parry": 15}
EXTRAS_LEVEL = 10        # استنس/راهنما/آمار/کوئست/قدرت‌های کلاس تو پنلِ حمله
AUTO_PICK_LEVEL = 10     # زیرِ این سطح، امن‌ترین دشمن خودکار انتخاب می‌شه
MENU_MIN_LEVEL = 5       # زیرِ این سطح منوی اصلی فقط ۳ دکمه داره


def attack_unlocked(player: dict, key: str) -> bool:
    return player.get("level", 1) >= ATTACK_UNLOCK.get(key, 1)


def show_extras(player: dict) -> bool:
    return player.get("level", 1) >= EXTRAS_LEVEL


def auto_pick(player: dict) -> bool:
    return player.get("level", 1) < AUTO_PICK_LEVEL


def safest_index(enemies: list) -> int:
    return min(range(len(enemies)), key=lambda k: enemies[k].get("dmg", 0)) if enemies else -1


# ═══════════════════════════════════════════════════════════════
#  جریمه‌ی مرگِ ساده (برای همه‌ی بازیکن‌های غیرتازه‌کار)
# ═══════════════════════════════════════════════════════════════
SIMPLE_DEATH_ZEN_PCT = 0.10


def simple_death_lines(player: dict, mult: float = 1.0) -> list[str]:
    """یه قانونِ واحد: ۱۰٪ Zen. بدونِ نفرین، جراحتِ دائمی، قفلِ درمان، افتادنِ سطح،
    از دست رفتنِ آیتم یا نابودیِ کاراکتر."""
    zen = int(player.get("zen", 0))
    lost = int(zen * min(1.0, SIMPLE_DEATH_ZEN_PCT * mult))
    player["zen"] = zen - lost
    player["death_count"] = player.get("death_count", 0) + 1   # فقط آمار
    player["death_curse_until"] = 0
    player["heal_lockout_until"] = 0
    return [f"💸 مجازاتِ مرگ: -{lost:,} Zen ({int(SIMPLE_DEATH_ZEN_PCT*100*mult)}٪)" if lost
            else "💸 چیزی برای از دست دادن نداشتی — این بار رایگان!"]


# ═══════════════════════════════════════════════════════════════
#  کارتِ معرفیِ قابلیتِ جدید موقعِ لول‌آپ
# ═══════════════════════════════════════════════════════════════
_UNLOCK_CARDS = {
    5:  "⚔️ **حمله‌ی قوی** + 👹 **باس جهانی** + 🆚 **PvP** + 👥 **تیم**",
    10: "🏰 **گیلد** + 🌀 **حمله‌ی عنصری/کومبو** + 🎭 **استنس‌ها** + انتخابِ دستیِ دشمن",
    12: "🛒 **مغازه/حراجی** + 🏠 **ملک شخصی**",
    15: "☄️ **ضربه‌ی نهایی** + 🛡️ **پری** + 🌀 **شکاف Abyss**",
}


def unlock_note(old_level: int, new_level: int) -> str:
    out = [txt for lv, txt in _UNLOCK_CARDS.items() if old_level < lv <= new_level]
    if not out:
        return ""
    return "\n\n🔓 **چیزِ جدید باز شد:** " + " | ".join(out)
