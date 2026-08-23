# ============================================================
#  ASTRAL ABYSS — ابیلیتیِ کاتاناهای رلیک (Relic Katana Abilities)
#  (katana_relic_abilities.py)
# ------------------------------------------------------------
#  این فایل کاملاً جدا و مستقله — به katana_wheel_system.py دست
#  نمی‌زنه، فقط از روی اسمِ آیتم (item["name"]) که همون‌جا تعریف
#  شده، ابیلیتیِ یکتاشو پیدا می‌کنه.
#
#  هر کاتانای رلیک (~۴۹ تا) یه ابیلیتیِ یکتا داره، از دو نوع:
#
#    • "passive"  → یه بونوسِ ثابت (dmg_pct/crit_pct/defense_pct/...)
#                    که دقیقاً مثلِ مُهرهای الهی/ست‌ها/هانت‌کوئست‌ها
#                    قاطیِ setb تو calc_combat می‌شه — یعنی از قبل
#                    وایرشده و نیازی به هوکِ جدید نداره.
#
#    • "proc"     → یه اثرِ فعال با شانسِ رول (ضربه‌ی اضافه/اجرا/
#                    وضعیت/جذب‌حیات) که هر حمله چک می‌شه — دقیقاً
#                    با همون الگوی kcore["special"] (کاتانای سولِ
#                    قدیمی) و pet_ability_proc.
#
#  فقط سلاحِ اکیپ‌شده (equipped["weapon"]) چک می‌شه؛ اگه اسمش تو
#  RELIC_ABILITIES نبود (یا اصلاً کاتانای رلیک نبود)، هیچ اثری
#  نداره — چیزِ قدیمی خراب نمی‌شه.
# ============================================================
from __future__ import annotations
import random

# ─── جدولِ کامل — به‌ازای هر اسمِ کاتانا (دقیقاً همون اسمِ تو
#     katana_wheel_system.KATANA_ROSTER) یه ابیلیتی ────────────
RELIC_ABILITIES: dict[str, dict] = {

    # ───────────────── رتبه‌ی اسطوره‌ای (mythic) ─────────────────
    "دندانِ گرگِ شب": {
        "ability": "زوزه‌ی شب", "emoji": "🌙", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.18, "value": 0.35,
        "flavor": "زوزه رو شنیدی، ولی دیر شده بود",
    },
    "خارِ زهرآگین": {
        "ability": "نیشِ خار", "emoji": "🥀", "kind": "proc",
        "effect": "status", "status": "poison", "chance": 0.28,
        "flavor": "خارش زهرِ آرومی تو رگ‌های دشمن ریخت",
    },
    "شعله‌ی خاموش": {
        "ability": "خاکسترِ بی‌صدا", "emoji": "🕯️", "kind": "proc",
        "effect": "status", "status": "burn", "chance": 0.25,
        "flavor": "بدونِ هیچ صدایی، شعله زیرِ پوستش موند",
    },
    "پژواکِ فولاد": {
        "ability": "پژواکِ ضربه", "emoji": "🔔", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.20, "value": 0.30,
        "flavor": "همون ضربه یه‌بارِ دیگه تو گوشِ دشمن پیچید",
    },
    "چنگالِ توفان": {
        "ability": "بادِ پیش‌قدم", "emoji": "🌬️", "kind": "passive",
        "stat": "crit_pct", "value": 0.03,
        "flavor": "همیشه یه قدم جلوتر از ضربه‌ست",
    },
    "اشکِ یخی": {
        "ability": "سرمای فراموش‌شده", "emoji": "🧊", "kind": "proc",
        "effect": "status", "status": "freeze", "chance": 0.20,
        "flavor": "یه زمستونِ قدیمی رگ‌هاشو منجمد کرد",
    },
    "نیشِ عقرب": {
        "ability": "یه‌بار کافیه", "emoji": "🦂", "kind": "proc",
        "effect": "execute", "chance": 0.30, "value": 0.10,
        "flavor": "دیگه بارِ دومی لازم نبود",
    },
    "سایه‌ی گمشده": {
        "ability": "هیچ‌جا نیست", "emoji": "🌑", "kind": "passive",
        "stat": "counter_pct", "value": 0.05,
        "flavor": "دقیقاً جایی که فکر می‌کردی نیست",
    },
    "پرِ کلاغِ سیاه": {
        "ability": "خبرِ مرگ", "emoji": "🐦‍⬛", "kind": "proc",
        "effect": "execute", "chance": 0.22, "value": 0.14,
        "flavor": "خبر زودتر از خودِ اتفاق رسید",
    },
    "خنجرِ شکسته‌بند": {
        "ability": "شکسته ولی زنده", "emoji": "🩹", "kind": "proc",
        "effect": "lifesteal_burst", "chance": 0.30, "value": 0.20,
        "flavor": "شکست، ولی چیزی رو ازت نگرفت",
    },
    "زبانه‌ی اخگر": {
        "ability": "کوره‌ی خاموش", "emoji": "🔥", "kind": "proc",
        "effect": "status", "status": "burn", "chance": 0.26,
        "flavor": "هنوز از یه کوره‌ی سردشده داغه",
    },
    "چکشِ شکسته": {
        "ability": "شکنندگی", "emoji": "🔩", "kind": "passive",
        "stat": "crit_dmg_bonus", "value": 0.08,
        "flavor": "دیگه شکل نمی‌ده، فقط می‌شکنه",
    },
    "پنجه‌ی روباهِ سفید": {
        "ability": "قبل از دیدن", "emoji": "🦊", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.22, "value": 0.28,
        "flavor": "قبل از اینکه ببینیش رفته",
    },
    "زهرِ شبنم": {
        "ability": "نشستنِ آروم", "emoji": "💧", "kind": "proc",
        "effect": "status", "status": "poison", "chance": 0.30,
        "flavor": "آروم می‌شینه، آروم‌تر می‌کشه",
    },
    "خارِ سیاه‌چاله": {
        "ability": "بی‌بازگشت", "emoji": "🕳️", "kind": "proc",
        "effect": "true_dmg", "chance": 0.15, "value": 0.25,
        "flavor": "چیزی که توش رفت، دیگه برنگشت",
    },
    "تیغِ کرمِ شب‌تاب": {
        "ability": "درخششِ قبل از ضربه", "emoji": "🪱", "kind": "passive",
        "stat": "crit_pct", "value": 0.035,
        "flavor": "تو تاریکی می‌درخشه، درست قبلِ ضربه",
    },

    # ───────────────── رتبه‌ی افسانه‌ای (legendary) ─────────────────
    "شعله‌ی آخرالزمان": {
        "ability": "آخرین چیزی که دیدن", "emoji": "☄️", "kind": "proc",
        "effect": "status", "status": "burn", "chance": 0.32,
        "flavor": "خیلی‌ها همینو آخرین بار دیدن",
    },
    "تیغه‌ی هزارساله": {
        "ability": "هزار جنگ", "emoji": "⏳", "kind": "passive",
        "stat": "crit_dmg_bonus", "value": 0.12,
        "flavor": "با هر جنگ تیزتر شده",
    },
    "خشمِ اژدهای سرخ": {
        "ability": "شعله‌ی خواب", "emoji": "🐲", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.24, "value": 0.45,
        "flavor": "تو خوابِ صاحبش هم شعله می‌کشه",
    },
    "ندای مغاک": {
        "ability": "ندای مرگ", "emoji": "📯", "kind": "proc",
        "effect": "execute", "chance": 0.26, "value": 0.16,
        "flavor": "صداش رو فقط اونی می‌شنوه که قراره بمیره",
    },
    "تاجِ شکسته": {
        "ability": "سقوطِ دوباره", "emoji": "👑", "kind": "passive",
        "stat": "dmg_pct", "value": 0.05,
        "flavor": "یه‌بار پادشاهی رو انداخت",
    },
    "برشِ ابدیت": {
        "ability": "برشِ زمان", "emoji": "♾️", "kind": "proc",
        "effect": "true_dmg", "chance": 0.20, "value": 0.30,
        "flavor": "زمان رو هم می‌بره، نه فقط گوشت رو",
    },
    "قلبِ توفانِ سیاه": {
        "ability": "رعدِ دیررس", "emoji": "🌩️", "kind": "proc",
        "effect": "status", "status": "stun", "chance": 0.18,
        "flavor": "دیر می‌رسه، ولی می‌رسه",
    },
    "روحِ ققنوسِ خاکستری": {
        "ability": "برگشتِ برنده", "emoji": "🔥", "kind": "proc",
        "effect": "lifesteal_burst", "chance": 0.28, "value": 0.25,
        "flavor": "هربار که می‌شکنه، برنده‌تر برمی‌گرده",
    },
    "زوزه‌ی گرگِ سفید": {
        "ability": "بسته‌ی گمشده", "emoji": "🐺", "kind": "passive",
        "stat": "crit_pct", "value": 0.045,
        "flavor": "بسته‌ای که دیگه وجود نداره پشتشه",
    },
    "خونِ ستاره": {
        "ability": "درخششِ مرده", "emoji": "🌠", "kind": "passive",
        "stat": "elem_amp", "value": 0.06,
        "flavor": "از یه ستاره‌ی مرده هنوز می‌درخشه",
    },
    "دروگرِ سایه‌ها": {
        "ability": "اسمِ تازه", "emoji": "💀", "kind": "proc",
        "effect": "execute", "chance": 0.24, "value": 0.18,
        "flavor": "هر جنگی، یه اسمِ دیگه به خودش اضافه می‌کنه",
    },
    "خشمِ کِرِمزُنِ باستانی": {
        "ability": "رنگِ خون", "emoji": "🩸", "kind": "proc",
        "effect": "lifesteal_burst", "chance": 0.26, "value": 0.22,
        "flavor": "رنگش از خونِ هزاران جنگه",
    },
    "شبحِ سرگردان": {
        "ability": "جنگِ بعد از مرگ", "emoji": "👻", "kind": "passive",
        "stat": "counter_pct", "value": 0.06,
        "flavor": "صاحبش مرد، تیغه هنوز جنگ می‌ده",
    },
    "تایتانِ خفته": {
        "ability": "ضربه‌ی سنگین", "emoji": "🗿", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.16, "value": 0.55,
        "flavor": "سنگینه، ولی هیچ‌وقت خسته نمی‌شه",
    },
    "نواخترِ منفجرشده": {
        "ability": "یه انفجار", "emoji": "💥", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.20, "value": 0.42,
        "flavor": "یه انفجار، یه اسم، یه افسانه",
    },
    "غروبِ ابدی": {
        "ability": "خورشیدِ نیمه‌روشن", "emoji": "🌆", "kind": "passive",
        "stat": "lifesteal_pct", "value": 0.025,
        "flavor": "خورشیدش هیچ‌وقت کامل غروب نمی‌کنه",
    },

    # ───────────────── رتبه‌ی میراث (legacy) ─────────────────
    "میراثِ شاهِ گمشده": {
        "ability": "آخرینِ امپراتوری", "emoji": "🏰", "kind": "passive",
        "stat": "dmg_pct", "value": 0.07,
        "flavor": "آخرین چیزی که از یه امپراتوری موند",
    },
    "شمشیرِ نسل‌های سوخته": {
        "ability": "سوختنِ نسل", "emoji": "🔥", "kind": "proc",
        "effect": "status", "status": "burn", "chance": 0.36,
        "flavor": "هر نسلی که دستش گرفت، یه چیزی سوزوند",
    },
    "پیمانِ خونِ باستانی": {
        "ability": "امضای خون", "emoji": "🩸", "kind": "proc",
        "effect": "lifesteal_burst", "chance": 0.34, "value": 0.30,
        "flavor": "با خون امضا شده، با خون تمدید می‌شه",
    },
    "لبه‌ی حافظه‌ی گم‌شده": {
        "ability": "حافظه‌ی تیز", "emoji": "🕰️", "kind": "passive",
        "stat": "crit_pct", "value": 0.06,
        "flavor": "چیزهایی رو یادشه که هیچ‌کس یادش نیست",
    },
    "خشمِ آخرین ژنرال": {
        "ability": "جنگِ تمام‌نشده", "emoji": "🎖️", "kind": "passive",
        "stat": "defense_pct", "value": 0.04,
        "flavor": "جنگی که هیچ‌وقت رسماً تموم نشد",
    },
    "تیغه‌ی تاجِ فراموش‌شده": {
        "ability": "لیاقتِ تاج", "emoji": "👑", "kind": "proc",
        "effect": "execute", "chance": 0.28, "value": 0.20,
        "flavor": "برای کسی که لیاقتش رو داره منتظره",
    },
    "روحِ سلسله‌ی خاموش": {
        "ability": "خطِ خونیِ آخر", "emoji": "🗿", "kind": "proc",
        "effect": "status", "status": "stun", "chance": 0.22,
        "flavor": "آخرین بازمانده‌ی یه خطِ خونیِ کامل",
    },
    "تایتانِ باستانیِ آخر": {
        "ability": "قبل از کوه‌ها", "emoji": "⛰️", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.20, "value": 0.60,
        "flavor": "قبل از اینکه کوه‌ها اسم داشته باشن، این بود",
    },
    "میراثِ آتشِ نخستین": {
        "ability": "اولین آتش", "emoji": "🔥", "kind": "proc",
        "effect": "status", "status": "burn", "chance": 0.34,
        "flavor": "اولین آتشی که هیچ‌وقت خاموش نشد",
    },
    "شمشیرِ فراموشیِ مقدس": {
        "ability": "نوشته‌ی خطرناک", "emoji": "📜", "kind": "proc",
        "effect": "true_dmg", "chance": 0.24, "value": 0.35,
        "flavor": "نوشته‌ای که کسی جرأتِ خوندنش رو نداره",
    },

    # ───────────────── رتبه‌ی الهی (divine) ─────────────────
    "دَمِ آفرینشِ نخستین": {
        "ability": "نفسِ اول", "emoji": "🌌", "kind": "proc",
        "effect": "bonus_dmg", "chance": 0.24, "value": 0.75,
        "flavor": "قبل از اسم‌داشتنِ دنیا، این وجود داشت",
    },
    "پرتوِ آخرینِ خدایان": {
        "ability": "جامانده‌ی خدایان", "emoji": "✨", "kind": "proc",
        "effect": "execute", "chance": 0.32, "value": 0.25,
        "flavor": "وقتی خدایان رفتن، این رو جا گذاشتن",
    },
    "تیغه‌ی سکوتِ ابدی": {
        "ability": "سکوتِ آخر", "emoji": "🕊️", "kind": "proc",
        "effect": "status", "status": "stun", "chance": 0.26,
        "flavor": "بعد از این، دیگه چیزی برای گفتن نمی‌مونه",
    },
    "قلبِ کهکشانِ فروپاشیده": {
        "ability": "تولدِ تیغه", "emoji": "🌠", "kind": "proc",
        "effect": "true_dmg", "chance": 0.28, "value": 0.45,
        "flavor": "از مرگِ یه کهکشان، تولدِ یه تیغه",
    },
    "ندای بی‌انتها": {
        "ability": "شروع و پایان", "emoji": "♾️", "kind": "proc",
        "effect": "lifesteal_burst", "chance": 0.34, "value": 0.35,
        "flavor": "شروع و پایانش یه نقطه‌ست",
    },
    "نفسِ خالقِ نخستین": {
        "ability": "شکل‌دهیِ دنیا", "emoji": "🌬️", "kind": "passive",
        "stat": "dmg_pct", "value": 0.10,
        "flavor": "اولین نفسی که به دنیا شکل داد",
    },
    "تاجِ آفرینشِ آخر": {
        "ability": "آخرین ساخته", "emoji": "👑", "kind": "passive",
        "stat": "crit_dmg_bonus", "value": 0.18,
        "flavor": "چیزی که بعدش دیگه چیزی ساخته نشد",
    },
}

# ─── لیست استت‌های passiveِ مجازی (همون‌هایی که calc_combat می‌شناسه) ───
_VALID_PASSIVE_STATS = {
    "dmg_pct", "crit_pct", "crit_dmg_bonus", "lifesteal_pct",
    "defense_pct", "counter_pct", "elem_amp",
}


def _equipped_relic_weapon(player: dict) -> dict | None:
    """سلاحِ اکیپ‌شده رو برمی‌گردونه، فقط اگه واقعاً کاتانای رلیکِ
    گردونه (katana_relic=True) باشه و تو جدولِ بالا تعریف شده باشه."""
    eq = player.get("equipped") or {}
    weapon = eq.get("weapon")
    if not weapon or not weapon.get("katana_relic"):
        return None
    if weapon.get("name") not in RELIC_ABILITIES:
        return None
    return weapon


def get_relic_ability_info(item: dict) -> dict | None:
    """برای نمایش تو کارتِ آیتم (format_item_card) — خودِ آیتم رو می‌گیره،
    نه پلیر رو."""
    if not item or not item.get("katana_relic"):
        return None
    return RELIC_ABILITIES.get(item.get("name"))


def get_relic_passive_bonus_stats(player: dict) -> dict:
    """بونوسِ passiveِ کاتانای رلیکِ اکیپ‌شده — دقیقاً همون کلیدهایی
    که calc_combat تو setb می‌خونه. اگه کاتانای اکیپ‌شده proc باشه
    (نه passive) یا اصلاً رلیک نباشه، دیکشنری خالی برمی‌گرده."""
    weapon = _equipped_relic_weapon(player)
    if not weapon:
        return {}
    ability = RELIC_ABILITIES.get(weapon["name"])
    if not ability or ability.get("kind") != "passive":
        return {}
    stat = ability.get("stat")
    if stat not in _VALID_PASSIVE_STATS:
        return {}
    return {stat: ability.get("value", 0)}


def roll_relic_proc(player: dict, enemy: dict, result: dict) -> str | None:
    """بعد از محاسبه‌ی دمیجِ اصلی صدا زده می‌شه (دقیقاً مثلِ الگوی
    kcore['special'] / pet_ability_proc). result رو مستقیم تغییر
    می‌ده (dmg/lifesteal_heal) و enemy['_status'] رو در صورتِ نیاز
    ست می‌کنه. خروجی: متنِ لاگ برای نمایش، یا None اگه هیچ‌چی رول نشد."""
    if result.get("miss") or result.get("dmg", 0) <= 0:
        return None
    weapon = _equipped_relic_weapon(player)
    if not weapon:
        return None
    ability = RELIC_ABILITIES.get(weapon["name"])
    if not ability or ability.get("kind") != "proc":
        return None
    if random.random() >= ability.get("chance", 0):
        return None

    effect = ability["effect"]
    tag = f"{ability['emoji']} **{weapon['name']} — {ability['ability']}**"

    if effect == "bonus_dmg":
        bonus = max(1, int(result["dmg"] * ability["value"]))
        result["dmg"] += bonus
        return f"{tag}: +{bonus} آسیبِ اضافه ({ability['flavor']})"

    if effect == "true_dmg":
        # دمیجِ خام، مستقل از دفاع/زره — یه ضریبِ کوچیک از دمیجِ خودِ ضربه.
        bonus = max(1, int(result["dmg"] * ability["value"]))
        result["dmg"] += bonus
        return f"{tag}: {bonus} آسیبِ خالص ({ability['flavor']})"

    if effect == "lifesteal_burst":
        heal = max(1, int(result["dmg"] * ability["value"]))
        result["lifesteal_heal"] = result.get("lifesteal_heal", 0) + heal
        return f"{tag}: +{heal} HP ({ability['flavor']})"

    if effect == "execute":
        # اگه دشمن بعدِ این ضربه زیرِ درصدِ آستانه بمونه، ضربه‌ی
        # پایان‌دهنده می‌زنه (کارِ واقعیِ کشتن رو خودِ handler انجام
        # می‌ده، اینجا فقط دمیجِ کافی برای رسوندنش به صفر اضافه می‌شه).
        max_hp = enemy.get("max_hp", enemy.get("hp", 1))
        remaining = enemy.get("hp", 0) - result["dmg"]
        if 0 < remaining <= max_hp * ability["value"]:
            result["dmg"] += remaining
            return f"{tag}: ضربه‌ی پایان‌دهنده! ({ability['flavor']})"
        return None

    if effect == "status":
        # اگه دشمن از قبل یه وضعیتِ فعال داره، رویِ هم سوار نمی‌کنیم.
        if enemy.get("_status") and enemy["_status"].get("turns_left", 0) > 0:
            return None
        from combat import STATUSES  # فقط داخل تابع، تا importِ حلقوی پیش نیاد
        skey = ability["status"]
        sdef = STATUSES.get(skey)
        if not sdef:
            return None
        enemy["_status"] = {"key": skey, "turns_left": sdef["turns"]}
        return f"{tag}: دشمن دچار **{sdef['name']}** شد! ({ability['flavor']})"

    return None
