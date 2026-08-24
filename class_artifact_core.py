# ============================================================
#  ASTRAL ABYSS RPG — Class Artifact System (Staff / Cane / Ring)
#  (class_artifact_core.py)
# ============================================================
#
# این فایل دقیقاً همون معماریِ katana_core.py (روح، تایر، بیداری،
# پیوند، ظرفیت) رو برای سه کلاسِ غیر-ماجراجو پیاده می‌کنه که تا الان
# هیچ آیتمِ لول‌بندی‌شده‌ای نداشتن:
#
#   🧙‍♂️ جادوگر   → 🪄 چوب‌دستی (staff)
#   💰 تاجر      → 🦯 عصا (cane)
#   ✨ درمانگر   → 💍 انگشتر (ring)
#
# برخلافِ کاتانا که هویتش از روی characters.py (کاراکترِ ۳۵۰تایی)
# می‌اومد، این سه کلاس چنین منبعی ندارن — پس هویتِ آرتیفکت (اسم/تایر)
# اولین‌باری که get_or_assign_artifact() صدا زده بشه به‌صورتِ رندومِ
# وزن‌دار ساخته می‌شه و روی خودِ پروفایلِ بازیکن ذخیره می‌مونه (idempotent،
# یعنی بعدِ اولین بار همیشه همون آیتم برمی‌گرده).
#
# چیزی که این فایل اضافه می‌کنه:
#   • ARTIFACT_NAME_POOLS → ~۲۱ اسمِ متفاوت برای هرکلاس (۶۳ آیتمِ یکتا)
#   • TIER_BASE            → ۴ رتبه (common/rare/legendary/mythic)
#   • Awakening (۰ تا ۵)   → مثلِ کاتانا، با موادِ مخصوصِ هر کلاس
#   • Bond (۱ تا ۱۰)       → پیوند با آرتیفکت بر اساسِ تعدادِ کشته
#   • ظرفیتِ اسنس          → معادلِ «ظرفیتِ روح» کاتانا
#
# خروجیِ calc_artifact_bonus() دقیقاً هم‌شکلِ calc_katana_bonus()ه —
# تو combat.py برای wizard/merchant/healer با همون الگوی try/except
# که برای کاتانا استفاده شده وصل می‌شه (فایل ولی هیچ‌جای دیگه‌ای رو
# دست نمی‌زنه؛ فقط خودشه).
# ============================================================

import random

# ────────────────────────────────────────────────────────────
# ۰) نگاشتِ کلاس → نوعِ آرتیفکت
# ────────────────────────────────────────────────────────────

CLASS_ARTIFACT_MAP = {
    "wizard":   "staff",
    "merchant": "cane",
    "healer":   "ring",
}

ARTIFACT_META = {
    "staff": {
        "label_fa": "چوب‌دستی", "word_fa": "چوب‌دستی", "class_fa": "جادوگر",
        "emoji": "🪄", "command": "/staff", "flavor_word": "آرکین",
    },
    "cane": {
        "label_fa": "عصا", "word_fa": "عصا", "class_fa": "تاجر",
        "emoji": "🦯", "command": "/cane", "flavor_word": "بازار",
    },
    "ring": {
        "label_fa": "انگشتر", "word_fa": "انگشتر", "class_fa": "درمانگر",
        "emoji": "💍", "command": "/ring", "flavor_word": "فیض",
    },
}


def artifact_type_for_player(player: dict) -> str | None:
    return CLASS_ARTIFACT_MAP.get(player.get("class"))


# ────────────────────────────────────────────────────────────
# ۱) تایربندی — چون منبعِ rarity کاراکتر نداریم، رندومِ وزن‌دار
# ────────────────────────────────────────────────────────────

TIER_WEIGHTS = [
    ("common", 0.55),
    ("rare", 0.28),
    ("legendary", 0.13),
    ("mythic", 0.04),
]

TIER_BASE = {
    "common": {
        "emoji": "⚪", "name_fa": "معمولی", "max_awaken": 2,
        "dmg_min": 1.00, "dmg_max": 1.35,
        "success_base": 0.75, "cost_base": 600, "mat_qty_base": 2,
    },
    "rare": {
        "emoji": "💠", "name_fa": "کمیاب", "max_awaken": 3,
        "dmg_min": 1.00, "dmg_max": 1.70,
        "success_base": 0.60, "cost_base": 2200, "mat_qty_base": 3,
    },
    "legendary": {
        "emoji": "🌟", "name_fa": "افسانه‌ای", "max_awaken": 4,
        "dmg_min": 1.00, "dmg_max": 2.20,
        "success_base": 0.42, "cost_base": 7500, "mat_qty_base": 3,
    },
    "mythic": {
        "emoji": "👑", "name_fa": "جاودانه", "max_awaken": 5,
        "dmg_min": 1.00, "dmg_max": 3.20,
        "success_base": 0.28, "cost_base": 22000, "mat_qty_base": 4,
    },
}

# اثرِ ویژه‌ی هر تایر، مخصوصِ هر کلاس (فقط legendary/mythic اثرِ ویژه دارن)
SPECIAL_BY_TYPE = {
    "staff": {"legendary": "mana_overload", "mythic": "arcane_singularity"},
    "cane":  {"legendary": "golden_strike", "mythic": "market_domination"},
    "ring":  {"legendary": "grace_of_light", "mythic": "divine_ascension"},
}

SPECIAL_INFO = {
    "mana_overload":       {"name_fa": "طغیانِ مانا (Legendary)",
                             "desc": "۱۵٪ شانس بازگشتِ مانا و ۲۰٪ دمیجِ اضافه در همون ضربه"},
    "arcane_singularity":  {"name_fa": "تکینگیِ آرکین (Mythic)",
                             "desc": "هر کشتن ۱۰٪ از HP دشمن رو به‌صورتِ مانا/دمیجِ فوری برمی‌گردونه"},
    "golden_strike":       {"name_fa": "ضربه‌ی زرین (Legendary)",
                             "desc": "۱۵٪ شانسِ ضربه‌ی دوبل + غنیمتِ طلای اضافه از همون حمله"},
    "market_domination":   {"name_fa": "سلطه‌ی بازار (Mythic)",
                             "desc": "هر کشتن ۱۰٪ از HP دشمن رو به‌صورتِ طلا/دمیجِ فوری برمی‌گردونه"},
    "grace_of_light":      {"name_fa": "فیضِ نور (Legendary)",
                             "desc": "۱۵٪ شانسِ ضربه‌ی دوبل که نیمی از دمیجش هم به‌صورتِ هیل برمی‌گرده"},
    "divine_ascension":    {"name_fa": "عروجِ الهی (Mythic)",
                             "desc": "هر کشتن ۱۰٪ از HP دشمن رو به‌صورتِ هیلِ فوری برمی‌گردونه"},
}

# ────────────────────────────────────────────────────────────
# ۲) بیداری (Awakening) — مهارت‌های مخصوصِ هر کلاس، مراحلِ ۱ تا ۵
# ────────────────────────────────────────────────────────────

AWAKENING_STAGE_NAMES = {
    0: "خفته 💤", 1: "بیدار 🌙", 2: "درخشان ✨",
    3: "اسطوره‌ای 🌠", 4: "فراطبیعی 🌌", 5: "جاودانه ♾️",
}

AWAKENING_SKILLS_BY_TYPE = {
    "staff": {
        1: {"key": "spark_weave",   "name": "تارِ جرقه",     "desc": "شانس ۱۲٪ ضربه‌ی طلسمیِ اضافه که مستقیم به دشمن آسیب می‌زنه"},
        2: {"key": "mana_ward",     "name": "حصارِ مانا",    "desc": "شانس ۱۰٪ برای فرار کامل از ضدحمله‌ی بعدی دشمن"},
        3: {"key": "arcane_echo",   "name": "پژواکِ آرکین",  "desc": "با هر کشتن، ۴٪ از مانای ماکزیممت فوراً بازیابی می‌شه"},
        4: {"key": "elemental_tune","name": "هم‌آواییِ عنصری","desc": "آسیب ضعف عنصری ۲۵٪ قوی‌تر می‌شه"},
        5: {"key": "void_cast",     "name": "طلسمِ خلأ",     "desc": "شانس ۸٪ برای نادیده گرفتن کامل دفاع دشمن (فقط MYTHIC)"},
    },
    "cane": {
        1: {"key": "coin_flick",    "name": "تلنگرِ سکه",    "desc": "شانس ۱۲٪ ضربه‌ی اضافه که مستقیم به دشمن آسیب می‌زنه"},
        2: {"key": "haggle_guard",  "name": "سپرِ چانه‌زنی", "desc": "شانس ۱۰٪ برای فرار کامل از ضدحمله‌ی بعدی دشمن"},
        3: {"key": "profit_margin", "name": "حاشیه‌ی سود",   "desc": "با هر کشتن، طلای اضافه به‌اندازه‌ی ۴٪ ارزشِ دشمن می‌گیری"},
        4: {"key": "market_edge",   "name": "برتریِ بازار",  "desc": "آسیب ضعف عنصری ۲۵٪ قوی‌تر می‌شه"},
        5: {"key": "monopoly",      "name": "انحصار",        "desc": "شانس ۸٪ برای نادیده گرفتن کامل دفاع دشمن (فقط MYTHIC)"},
    },
    "ring": {
        1: {"key": "blessed_edge",  "name": "لبه‌ی متبرک",   "desc": "شانس ۱۲٪ ضربه‌ی اضافه که مستقیم به دشمن آسیب می‌زنه"},
        2: {"key": "faith_ward",    "name": "حصارِ ایمان",   "desc": "شانس ۱۰٪ برای فرار کامل از ضدحمله‌ی بعدی دشمن"},
        3: {"key": "gentle_mend",   "name": "ترمیمِ ملایم",  "desc": "با هر کشتن، ۴٪ از HP ماکزیممت رو فوراً بازیابی می‌کنی"},
        4: {"key": "radiant_tune",  "name": "هم‌آواییِ نورانی","desc": "آسیب ضعف عنصری ۲۵٪ قوی‌تر می‌شه"},
        5: {"key": "sacred_touch",  "name": "لمسِ مقدس",     "desc": "شانس ۸٪ برای نادیده گرفتن کامل دفاع دشمن (فقط MYTHIC)"},
    },
}

FORGE_BREAK_ON_FAIL_AWAKEN = True

# ────────────────────────────────────────────────────────────
# ۲.۵) موادِ بیداری — مخصوصِ هر کلاس
# ────────────────────────────────────────────────────────────

AWAKEN_MATERIALS_BY_TYPE = {
    "staff": {1: "arcane_dust", 2: "mana_crystal", 3: "star_ash", 4: "comet_core", 5: "arcane_essence"},
    "cane":  {1: "trade_seal",  2: "golden_thread", 3: "silk_ledger", 4: "dragon_coin", 5: "market_essence"},
    "ring":  {1: "holy_water",  2: "blessed_thread", 3: "seraph_down", 4: "sacred_ash", 5: "divine_essence"},
}

MATERIALS_INFO_BY_TYPE = {
    "staff": {
        "arcane_dust":    {"emoji": "🔹", "name_fa": "غبارِ آرکین",   "rarity": "rare"},
        "mana_crystal":   {"emoji": "🔷", "name_fa": "کریستالِ مانا", "rarity": "epic"},
        "star_ash":       {"emoji": "🌟", "name_fa": "خاکسترِ ستاره", "rarity": "epic"},
        "comet_core":     {"emoji": "☄️", "name_fa": "هسته‌ی دنباله‌دار", "rarity": "legendary"},
        "arcane_essence": {"emoji": "💜", "name_fa": "جوهرِ آرکین",   "rarity": "legendary"},
    },
    "cane": {
        "trade_seal":     {"emoji": "🔸", "name_fa": "مُهرِ تجاری",   "rarity": "rare"},
        "golden_thread":  {"emoji": "🧵", "name_fa": "نخِ زرین",      "rarity": "epic"},
        "silk_ledger":    {"emoji": "📜", "name_fa": "دفترِ ابریشمی", "rarity": "epic"},
        "dragon_coin":    {"emoji": "🪙", "name_fa": "سکه‌ی اژدها",   "rarity": "legendary"},
        "market_essence": {"emoji": "💰", "name_fa": "جوهرِ بازار",   "rarity": "legendary"},
    },
    "ring": {
        "holy_water":     {"emoji": "💧", "name_fa": "آبِ مقدس",     "rarity": "rare"},
        "blessed_thread": {"emoji": "🧶", "name_fa": "نخِ متبرک",    "rarity": "epic"},
        "seraph_down":    {"emoji": "🪶", "name_fa": "پرِ سرافیم",   "rarity": "epic"},
        "sacred_ash":     {"emoji": "⚱️", "name_fa": "خاکسترِ مقدس", "rarity": "legendary"},
        "divine_essence": {"emoji": "✨", "name_fa": "جوهرِ الهی",   "rarity": "legendary"},
    },
}


def grant_artifact_material_item(atype: str, target_stage: int, qty: int = 1) -> list[dict]:
    """معادلِ grant_soul_shard_item ولی برای موادِ بیداریِ کلاس‌های غیر-ماجراجو.
    برای دراپ/جایزه‌ی دستی استفاده می‌شه؛ شکلِ دیکشنریِ آیتمِ بازارِ سیاه رو می‌سازه."""
    mat = AWAKEN_MATERIALS_BY_TYPE[atype][target_stage]
    info = MATERIALS_INFO_BY_TYPE[atype][mat]
    sell = {"rare": 900, "epic": 2400, "legendary": 6000}.get(info["rarity"], 500)
    return [{
        "name": mat, "emoji": info["emoji"], "type": "awaken_material",
        "sell": sell, "shop_exclusive": True,
    } for _ in range(qty)]


# ────────────────────────────────────────────────────────────
# ۳) استخرِ اسم‌ها — ~۲۱ آیتمِ یکتا برای هرکلاس (۶۳ جمعاً)
#    هر ورودی: {"name": ..., "theme": ...}  — theme فقط برای فلیورِ متنیه
# ────────────────────────────────────────────────────────────

ARTIFACT_NAME_POOLS = {
    "staff": {
        "common": [
            {"name": "چوبِ بلوطِ کهنه", "theme": "خاک"},
            {"name": "عصای شاگردِ مکتب", "theme": "آرکین"},
            {"name": "چوب‌دستیِ خیزرانی", "theme": "باد"},
            {"name": "میله‌ی بلوطِ سوخته", "theme": "آتش"},
            {"name": "چوب‌دستیِ کریستالِ کدر", "theme": "یخ"},
            {"name": "عصای چوبِ گردو", "theme": "خاک"},
            {"name": "چوب‌دستیِ نویسِ اول", "theme": "آرکین"},
            {"name": "میله‌ی سرووِ رونی", "theme": "برق"},
        ],
        "rare": [
            {"name": "چوب‌دستیِ شعله‌ی آبی", "theme": "آتش"},
            {"name": "عصای بلورِ یخی", "theme": "یخ"},
            {"name": "چوب‌دستیِ رعدِ نوجوان", "theme": "برق"},
            {"name": "میله‌ی غبارِ ستاره", "theme": "کیهان"},
            {"name": "چوب‌دستیِ زمردِ سبز", "theme": "زهر"},
            {"name": "عصای مِه‌آلودِ گرگ", "theme": "سایه"},
        ],
        "legendary": [
            {"name": "چوب‌دستیِ فرمانروای طوفان", "theme": "برق"},
            {"name": "عصای خاکسترِ ققنوس", "theme": "آتش"},
            {"name": "چوب‌دستیِ قلبِ کهکشان", "theme": "کیهان"},
            {"name": "میله‌ی انجمادِ ابدی", "theme": "یخ"},
        ],
        "mythic": [
            {"name": "چوب‌دستیِ تکینگیِ آرکین", "theme": "خلأ"},
            {"name": "عصای خالقِ واقعیت", "theme": "کیهان"},
            {"name": "چوب‌دستیِ پژواکِ آفرینش", "theme": "نور"},
        ],
    },
    "cane": {
        "common": [
            {"name": "عصای چوبیِ بازارچه", "theme": "خاک"},
            {"name": "عصای دسته‌برنجی", "theme": "طلا"},
            {"name": "چوب‌دستیِ کاروان‌سرا", "theme": "خاک"},
            {"name": "عصای سفرِ جاده‌ابریشم", "theme": "باد"},
            {"name": "عصای میخِ آهنی", "theme": "فولاد"},
            {"name": "عصای بلوطِ حسابدار", "theme": "خاک"},
            {"name": "عصای دسته‌چوبیِ رهگذر", "theme": "خاک"},
            {"name": "عصای زنگوله‌دارِ دوره‌گرد", "theme": "باد"},
        ],
        "rare": [
            {"name": "عصای سرِ نقره‌ای", "theme": "نقره"},
            {"name": "عصای مُهرِ اتاقِ بازرگانی", "theme": "طلا"},
            {"name": "عصای طلاییِ کاروان‌سالار", "theme": "طلا"},
            {"name": "عصای عاجِ دلال", "theme": "عاج"},
            {"name": "عصای جواهرنشانِ بندری", "theme": "الماس"},
            {"name": "عصای سکه‌ریزِ صرافی", "theme": "طلا"},
        ],
        "legendary": [
            {"name": "عصای پادشاهِ تجارت", "theme": "طلا"},
            {"name": "عصای فرمانِ اتاقِ بازرگانی", "theme": "طلا"},
            {"name": "عصای اژدهایِ سکه", "theme": "اژدها"},
            {"name": "عصای امپراتوریِ کاروان", "theme": "طلا"},
        ],
        "mythic": [
            {"name": "عصای سلطانِ بازارهای جهان", "theme": "طلا"},
            {"name": "عصای بانکِ آبیس", "theme": "خلأ"},
            {"name": "عصای انحصارِ ابدی", "theme": "طلا"},
        ],
    },
    "ring": {
        "common": [
            {"name": "انگشترِ نقره‌ی ساده", "theme": "نور"},
            {"name": "انگشترِ استخوانیِ زائر", "theme": "خاک"},
            {"name": "انگشترِ چوبیِ راهب", "theme": "خاک"},
            {"name": "انگشترِ مسیِ معبد", "theme": "مس"},
            {"name": "انگشترِ سنگِ ماه", "theme": "نور"},
            {"name": "انگشترِ رشته‌نخِ متبرک", "theme": "نور"},
            {"name": "انگشترِ بلورِ کوچک", "theme": "یخ"},
            {"name": "انگشترِ عاجِ راهبه", "theme": "عاج"},
        ],
        "rare": [
            {"name": "انگشترِ نورِ سپیده‌دم", "theme": "نور"},
            {"name": "انگشترِ اشکِ فرشته", "theme": "نور"},
            {"name": "انگشترِ بلورِ شفا", "theme": "آب"},
            {"name": "انگشترِ زمردِ زندگی", "theme": "زهر"},
            {"name": "انگشترِ طلاییِ کلیسا", "theme": "طلا"},
            {"name": "انگشترِ پرِ کبوتر", "theme": "باد"},
        ],
        "legendary": [
            {"name": "انگشترِ فیضِ سرافیم", "theme": "نور"},
            {"name": "انگشترِ قلبِ معبد", "theme": "نور"},
            {"name": "انگشترِ ققنوسِ سپید", "theme": "آتش"},
            {"name": "انگشترِ عهدِ ابدی", "theme": "نور"},
        ],
        "mythic": [
            {"name": "انگشترِ عروجِ الهی", "theme": "نور"},
            {"name": "انگشترِ خالقِ حیات", "theme": "نور"},
            {"name": "انگشترِ فیضِ بی‌کران", "theme": "نور"},
        ],
    },
}

# ─── فلیورِ اختصاصیِ چندتا آیتمِ پرچم‌دار (Legendary/Mythic) ──────
ARTIFACT_SOULS = {
    "چوب‌دستیِ تکینگیِ آرکین": {
        "personality": "بی‌کران، پرمعما، فراسویِ فهم",
        "greeting": ["واقعیت فقط یه معادله‌ست... و من حلش می‌کنم."],
        "attack_lines": ["فروپاشیِ آرکین!", "معادله‌ت رو حل کردم!"],
        "kill_lines": ["به تکینگی پیوستی."],
        "death_lines": ["فروپاشی موقتیه... دوباره باز می‌سازیم."],
    },
    "عصای سلطانِ بازارهای جهان": {
        "personality": "مغرور، حسابگر، بی‌رحمِ متین",
        "greeting": ["هر جنگ، یه معامله‌ست."],
        "attack_lines": ["قیمتت رو تعیین کردم!", "سودِ من، ضررِ توئه!"],
        "kill_lines": ["دارایی‌ت مصادره شد."],
        "death_lines": ["ورشکستگی موقتیه، بازار همیشه برمی‌گرده."],
    },
    "انگشترِ عروجِ الهی": {
        "personality": "آرام، بخشنده، غیرقابلِ خم‌شدن",
        "greeting": ["نور از من می‌گذره، نه از منه."],
        "attack_lines": ["نورِ پاک‌کننده!", "فیض جاری می‌شه!"],
        "kill_lines": ["به آرامش رسیدی."],
        "death_lines": ["نور خاموش نمی‌شه، فقط منتظر می‌مونه."],
    },
}

DEFAULT_SOUL_TEMPLATES_BY_TYPE = {
    "staff": {
        "greeting": ["{name} تو دستته... انرژیش رو حس می‌کنی؟"],
        "attack_lines": ["طلسمِ {theme}!", "{name} می‌درخشه!", "ضربه‌ای از جنسِ {theme}!"],
        "kill_lines": ["{name} یه قربانیِ دیگه گرفت.", "آرکینِ {theme} سیر نمی‌شه."],
        "death_lines": ["{name} کنارت می‌مونه... همیشه.", "چوب‌دستی صبر می‌کنه تا دوباره بلندش کنی."],
    },
    "cane": {
        "greeting": ["{name} تو دستته... وزنِ قدرتش رو حس می‌کنی؟"],
        "attack_lines": ["ضربه‌ی {theme}!", "{name} معامله می‌کنه!", "چانه‌زنیِ خشن!"],
        "kill_lines": ["{name} یه معامله‌ی دیگه بست.", "بازارِ {theme} همیشه برنده‌ست."],
        "death_lines": ["{name} کنارت می‌مونه... همیشه.", "عصا صبر می‌کنه تا دوباره بلندش کنی."],
    },
    "ring": {
        "greeting": ["{name} رو دستته... گرماش رو حس می‌کنی؟"],
        "attack_lines": ["فیضِ {theme}!", "{name} می‌درخشه!", "لمسی از جنسِ {theme}!"],
        "kill_lines": ["{name} روحی دیگه رو آرام کرد.", "فیضِ {theme} تمومی نداره."],
        "death_lines": ["{name} کنارت می‌مونه... همیشه.", "انگشتر صبر می‌کنه تا دوباره بپوشیش."],
    },
}


def get_artifact_soul(player: dict) -> dict:
    ident = get_or_assign_artifact(player)
    if not ident:
        return {}
    name = ident["name"]
    soul = ARTIFACT_SOULS.get(name)
    if soul:
        result = dict(soul)
    else:
        tmpl = DEFAULT_SOUL_TEMPLATES_BY_TYPE[ident["type"]]
        result = {k: [s.format(name=name, theme=ident["theme"]) for s in v] for k, v in tmpl.items()}
        result["personality"] = f"روحِ {ident['theme']}، هنوز کاملاً شناخته‌نشده"
    result.update(ident)
    return result


def artifact_talk(player: dict, event: str) -> str:
    """event: 'greeting' | 'attack' | 'kill' | 'death'"""
    soul = get_artifact_soul(player)
    if not soul:
        return ""
    key_map = {"greeting": "greeting", "attack": "attack_lines", "kill": "kill_lines", "death": "death_lines"}
    lines = soul.get(key_map.get(event, "attack_lines"), [])
    return random.choice(lines) if lines else ""


# ────────────────────────────────────────────────────────────
# ۴) هویت‌سازیِ آرتیفکت — اولین‌بار رندوم، بعدش همیشه ثابت
# ────────────────────────────────────────────────────────────

def _roll_tier() -> str:
    r = random.random()
    acc = 0.0
    for tier, w in TIER_WEIGHTS:
        acc += w
        if r <= acc:
            return tier
    return "common"


def _roll_name(atype: str, tier: str) -> dict:
    pool = ARTIFACT_NAME_POOLS[atype][tier]
    return random.choice(pool)


def get_or_assign_artifact(player: dict) -> dict | None:
    """هویتِ آرتیفکتِ بازیکن رو برمی‌گردونه؛ اگه هنوز نداره (اولین صدا زدن)
    یکی رندومِ وزن‌دار می‌سازه و رو خودِ پروفایل ذخیره می‌کنه (idempotent).
    برای کلاس‌های ماجراجو/آواتارِ آبیس (که کاتانا دارن) None برمی‌گردونه."""
    atype = artifact_type_for_player(player)
    if not atype:
        return None

    if player.get("artifact_type") == atype and player.get("artifact_name"):
        return {
            "type": atype, "name": player["artifact_name"],
            "theme": player.get("artifact_theme", ""),
            "tier": player.get("artifact_tier", "common"),
        }

    tier = _roll_tier()
    entry = _roll_name(atype, tier)
    player["artifact_type"] = atype
    player["artifact_tier"] = tier
    player["artifact_name"] = entry["name"]
    player["artifact_theme"] = entry["theme"]
    player.setdefault("artifact_awakening", 0)
    player.setdefault("artifact_bond", 0)
    player.setdefault("artifact_bond_level", 1)
    player.setdefault("artifact_kills", 0)
    player.setdefault("artifact_deaths", 0)
    sync_artifact_capacity(player)

    return {"type": atype, "name": entry["name"], "theme": entry["theme"], "tier": tier}


# ────────────────────────────────────────────────────────────
# ۵) محاسباتِ بیداری (همون فرمول‌های katana_core.py)
# ────────────────────────────────────────────────────────────

def dmg_multiplier_for_stage(tier: str, stage: int) -> float:
    cfg = TIER_BASE[tier]
    if stage <= 0:
        return 1.0
    frac = stage / cfg["max_awaken"]
    return round(cfg["dmg_min"] + (cfg["dmg_max"] - cfg["dmg_min"]) * frac, 3)


def unlocked_skills(atype: str, tier: str, stage: int) -> list[dict]:
    cap = min(stage, TIER_BASE[tier]["max_awaken"])
    skills = AWAKENING_SKILLS_BY_TYPE[atype]
    return [skills[s] for s in range(1, cap + 1)]


def awaken_cost(tier: str, target_stage: int) -> int:
    cfg = TIER_BASE[tier]
    return int(cfg["cost_base"] * (target_stage ** 1.7))


def awaken_material_need(atype: str, tier: str, target_stage: int) -> tuple[str, int]:
    cfg = TIER_BASE[tier]
    mat = AWAKEN_MATERIALS_BY_TYPE[atype][target_stage]
    qty = (cfg["mat_qty_base"] + target_stage) * 3
    return mat, qty


def awaken_success_chance(tier: str, target_stage: int) -> float:
    cfg = TIER_BASE[tier]
    chance = cfg["success_base"] - (target_stage - 1) * 0.11
    chance = max(0.12, chance) * 0.5
    return round(min(0.40, chance), 3)


def attempt_awaken_artifact(player: dict, inventory: dict, gold: int, use_protection: bool = False) -> dict:
    """معادلِ attempt_awaken تو katana_core.py — فقط محاسبه و نتیجه رو
    برمی‌گردونه؛ کم‌کردنِ واقعیِ طلا/مواد کارِ هندلره."""
    ident = get_or_assign_artifact(player)
    if not ident:
        return {"success": False, "message": "❌ کلاسِ تو آرتیفکتِ لول‌بندی‌شده نداره."}

    atype, tier = ident["type"], ident["tier"]
    meta = ARTIFACT_META[atype]
    cfg = TIER_BASE[tier]
    current_stage = player.get("artifact_awakening", 0)

    if current_stage >= cfg["max_awaken"]:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": None, "material_spent": 0, "chance": 0.0, "protection_used": False,
                "message": f"{meta['emoji']} {ident['name']} به اوج بیداری خودش رسیده! ({cfg['max_awaken']}/{cfg['max_awaken']})"}

    target = current_stage + 1
    cost = awaken_cost(tier, target)
    mat, qty = awaken_material_need(atype, tier, target)
    chance = awaken_success_chance(tier, target)

    if gold < cost:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": f"💰 طلای کافی نداری! به {cost:,} Zen نیاز داری."}

    if inventory.get(mat, 0) < qty:
        info = MATERIALS_INFO_BY_TYPE[atype][mat]
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": f"📦 مواد کافی نداری! به {qty}x {info['emoji']} {info['name_fa']} نیاز داری."}

    if use_protection and inventory.get("protection_scroll", 0) < 1:
        return {"success": False, "new_stage": current_stage, "gold_spent": 0,
                "material": mat, "material_spent": 0, "chance": chance, "protection_used": False,
                "message": "🛡️ طومار محافظت نداری!"}

    success = random.random() < chance
    new_stage = current_stage
    protection_used = False

    if success:
        new_stage = target
        skill = AWAKENING_SKILLS_BY_TYPE[atype][target]
        message = (f"✨ **بیداری موفق!** {ident['name']} وارد مرحله‌ی "
                   f"«{AWAKENING_STAGE_NAMES[target]}» شد.\n"
                   f"🆕 مهارت جدید: **{skill['name']}** — {skill['desc']}")
    else:
        if use_protection:
            protection_used = True
            message = "🛡️ بیداری شکست خورد، ولی طومار محافظت مانع پس‌رفت شد."
        elif FORGE_BREAK_ON_FAIL_AWAKEN and current_stage > 0:
            new_stage = current_stage - 1
            message = (f"💥 بیداری شکست خورد! {meta['word_fa']} آشفته شد و یک مرحله پس‌رفت کرد "
                       f"→ «{AWAKENING_STAGE_NAMES[new_stage]}».")
        else:
            message = "💥 بیداری شکست خورد. طلا و مواد از دست رفت ولی مرحله حفظ شد."

    return {
        "success": success, "new_stage": new_stage, "gold_spent": cost,
        "material": mat, "material_spent": qty, "chance": chance,
        "protection_used": protection_used, "message": message,
    }


# ────────────────────────────────────────────────────────────
# ۶) پیوند (Bond) — سطح ۱ تا ۱۰، بر اساسِ تعدادِ کشته
# ────────────────────────────────────────────────────────────

BOND_KILLS_PER_LEVEL = 50
BOND_MAX_LEVEL = 10

BOND_PERKS = {
    3:  {"lifesteal": 0.05},
    5:  {"awaken_echo": True},
    7:  {"crit": 0.10},
    9:  {"hidden_skill": True, "dmg_mult": 0.08},
    10: {"soulbound": True},
}

BOND_LEVEL_DESC = {
    1: "شروع پیوند — آرتیفکت تازه بیدار شده",
    3: "+۵٪ لایف‌استیل — آرتیفکت شروع به اعتماد کردن بهت می‌کنه",
    5: "اثر ویژه‌ی تایر با شانس کم فعال می‌شه (پیش از بیداری کامل)",
    7: "+۱۰٪ شانس کریتیکال — هماهنگی کامل با آرتیفکت",
    9: "مهارت مخفی باز شد: +۸٪ آسیب کلی",
    10: "🔗 پیوند ابدی — آرتیفکت جاودانه شد و از این به بعد هیچ‌وقت با مرگت آسیب نمی‌بینه",
}


def bond_level_from_xp(xp: int) -> int:
    return min(BOND_MAX_LEVEL, 1 + max(0, xp) // BOND_KILLS_PER_LEVEL)


def bond_xp_for_level(level: int) -> int:
    return (level - 1) * BOND_KILLS_PER_LEVEL


def get_bond_bonus(bond_level: int) -> dict:
    out = {"lifesteal": 0.0, "crit": 0.0, "dmg_mult": 0.0,
           "awaken_echo": False, "hidden_skill": False, "soulbound": False}
    for lvl, perk in BOND_PERKS.items():
        if bond_level >= lvl:
            for k, v in perk.items():
                if isinstance(v, bool):
                    out[k] = out[k] or v
                else:
                    out[k] = out.get(k, 0) + v
    return out


def add_artifact_bond_xp(player: dict, amount: int = 1) -> dict:
    """بعدِ هر کشتن صدا زده می‌شه. برای کلاس‌هایی که آرتیفکت ندارن (ماجراجو/
    آواتارِ آبیس) بی‌اثره — امن برای صدا زدنِ بدونِ شرط، مثلِ add_bond_xp کاتانا."""
    ident = get_or_assign_artifact(player)
    if not ident:
        return {"leveled": False, "new_level": 0, "old_level": 0}

    old_xp = player.get("artifact_bond", 0)
    old_level = bond_level_from_xp(old_xp)
    new_xp = old_xp + amount
    new_level = bond_level_from_xp(new_xp)
    player["artifact_bond"] = new_xp
    player["artifact_bond_level"] = new_level
    sync_artifact_capacity(player)
    return {"leveled": new_level > old_level, "new_level": new_level, "old_level": old_level}


def apply_artifact_death_penalty(player: dict) -> dict:
    """بعدِ مرگِ بازیکن صدا زده می‌شه؛ ۱۵٪ Bond XP از دست میره مگر سطح ۱۰."""
    ident = get_or_assign_artifact(player)
    if not ident:
        return {"xp_lost": 0, "soulbound": False, "message": ""}

    bond_level = player.get("artifact_bond_level", 1)
    player["artifact_deaths"] = player.get("artifact_deaths", 0) + 1
    if bond_level >= BOND_MAX_LEVEL:
        return {"xp_lost": 0, "soulbound": True,
                "message": f"🔗 {ident['name']} جاودانه‌ست — با مرگت آسیب نمی‌بینه."}
    xp = player.get("artifact_bond", 0)
    lost = int(xp * 0.15)
    player["artifact_bond"] = max(0, xp - lost)
    player["artifact_bond_level"] = bond_level_from_xp(player["artifact_bond"])
    return {"xp_lost": lost, "soulbound": False,
            "message": f"💔 مرگت به {ident['name']} آسیب زد. -{lost} Bond XP" if lost > 0 else "آرتیفکت سالم موند."}


# ────────────────────────────────────────────────────────────
# ۷) ظرفیتِ اسنس (معادلِ ظرفیتِ روحِ کاتانا)
# ────────────────────────────────────────────────────────────

CAPACITY_BASE = {"common": 100, "rare": 180, "legendary": 300, "mythic": 500}
CAPACITY_TIER_CAP = {"common": 300, "rare": 560, "legendary": 940, "mythic": 1600}
CAPACITY_MAX_DMG_BONUS = 0.30


def max_artifact_capacity(tier: str, stage: int, bond_level: int) -> int:
    base = CAPACITY_BASE.get(tier, CAPACITY_BASE["common"])
    stage_bonus = stage * (base * 0.20)
    bond_bonus = max(0, bond_level - 1) * (base * 0.06)
    return int(base + stage_bonus + bond_bonus)


def artifact_capacity_dmg_bonus(capacity: int, tier: str) -> float:
    tier_cap = CAPACITY_TIER_CAP.get(tier, CAPACITY_TIER_CAP["common"])
    frac = min(1.0, capacity / tier_cap) if tier_cap else 0.0
    return round(frac * CAPACITY_MAX_DMG_BONUS, 3)


def sync_artifact_capacity(player: dict) -> int:
    atype = player.get("artifact_type")
    tier = player.get("artifact_tier", "common")
    if not atype:
        return 0
    stage = player.get("artifact_awakening", 0)
    bond_level = player.get("artifact_bond_level", bond_level_from_xp(player.get("artifact_bond", 0)))
    cap = max_artifact_capacity(tier, stage, bond_level)
    player["artifact_capacity"] = cap
    return cap


# ────────────────────────────────────────────────────────────
# ۸) بونوسِ نهایی برای نبرد — combat.py این رو صدا می‌زنه
# ────────────────────────────────────────────────────────────

def calc_artifact_bonus(player: dict) -> dict:
    """خروجی هم‌شکلِ calc_katana_bonus()ه؛ تو combat.py برای wizard/merchant/
    healer با همون الگوی try/except که برای کاتانا استفاده شده merge می‌شه:

        try:
            from class_artifact_core import calc_artifact_bonus
            acore = calc_artifact_bonus(player)
            class_crit_add     += acore["crit"]
            class_lifesteal    += acore["lifesteal"]
            class_dmg_mult_add += (acore["dmg_mult"] - 1.0) + acore["dmg_mult_flat"]
        except Exception as e:
            log_sync(f"⚠️ خطا تو آرتیفکتِ کلاس: {e}", "ERROR")
    """
    ident = get_or_assign_artifact(player)
    if not ident:
        return {"tier": None, "dmg_mult": 1.0, "crit": 0.0, "lifesteal": 0.0,
                "dmg_mult_flat": 0.0, "special": None, "special_active": False,
                "special_chance": 0.0, "skills": {}}

    atype, tier = ident["type"], ident["tier"]
    stage = player.get("artifact_awakening", 0)

    dmg_mult = dmg_multiplier_for_stage(tier, stage)
    bond_level = player.get("artifact_bond_level", bond_level_from_xp(player.get("artifact_bond", 0)))
    bond_bonus = get_bond_bonus(bond_level)

    special = SPECIAL_BY_TYPE[atype].get(tier)
    max_awaken = TIER_BASE[tier]["max_awaken"]
    stage_maxed = stage >= max_awaken
    special_active = stage_maxed or (bond_bonus["awaken_echo"] and stage >= 1)
    special_chance = 1.0 if stage_maxed else (0.15 if bond_bonus["awaken_echo"] else 0.0)

    capacity = player.get("artifact_capacity")
    if capacity is None:
        capacity = max_artifact_capacity(tier, stage, bond_level)
    cap_bonus = artifact_capacity_dmg_bonus(capacity, tier)

    return {
        "type": atype,
        "tier": tier,
        "tier_emoji": TIER_BASE[tier]["emoji"],
        "dmg_mult": dmg_mult,
        "crit": bond_bonus["crit"],
        "lifesteal": bond_bonus["lifesteal"],
        "dmg_mult_flat": bond_bonus["dmg_mult"] + cap_bonus,
        "capacity": capacity,
        "capacity_bonus": cap_bonus,
        "special": special,
        "special_active": special_active,
        "special_chance": special_chance,
        "skills": {s["key"]: True for s in unlocked_skills(atype, tier, stage)},
    }


# ────────────────────────────────────────────────────────────
# ۹) نمایشِ کامل برای /staff ، /cane ، /ring
# ────────────────────────────────────────────────────────────

def display_artifact_full(player: dict) -> str:
    from economy import bz_to_display

    ident = get_or_assign_artifact(player)
    if not ident:
        return "❌ کلاسِ تو آرتیفکتِ لول‌بندی‌شده نداره (فقط جادوگر/تاجر/درمانگر)."

    atype, tier = ident["type"], ident["tier"]
    meta = ARTIFACT_META[atype]
    soul = get_artifact_soul(player)
    cfg = TIER_BASE[tier]

    stage = player.get("artifact_awakening", 0)
    bond_xp = player.get("artifact_bond", 0)
    bond_level = player.get("artifact_bond_level", bond_level_from_xp(bond_xp))
    kills = player.get("artifact_kills", 0)
    deaths = player.get("artifact_deaths", 0)

    ab = calc_artifact_bonus(player)

    lines = []
    lines.append(f"{meta['emoji']} **{ident['name']}** {ab['tier_emoji']}")
    lines.append(f"_{soul.get('personality','')}_")
    lines.append(f"🎭 «{artifact_talk(player, 'greeting')}»")
    lines.append("")
    lines.append(f"👤 کلاس: {meta['class_fa']} | نوع: {meta['word_fa']}")
    lines.append(f"🏷️ رتبه: **{cfg['name_fa'].upper()}** ({tier})")
    lines.append(f"🌀 گرایش: {ident['theme']}")
    lines.append(f"💤 بیداری: **{AWAKENING_STAGE_NAMES.get(stage,'؟')}** ({stage}/{cfg['max_awaken']})")
    lines.append(f"🔮 ظرفیتِ اسنس: **{ab['capacity']}** (+{int(ab['capacity_bonus']*100)}٪ آسیب اضافه)")
    lines.append(f"⚔️ بونوس آسیب فعلی: ×{ab['dmg_mult']}")

    if stage > 0:
        skills = unlocked_skills(atype, tier, stage)
        if skills:
            lines.append("🧬 مهارت‌های باز شده:")
            for s in skills:
                lines.append(f"   • **{s['name']}** — {s['desc']}")

    special = SPECIAL_BY_TYPE[atype].get(tier)
    if special:
        info = SPECIAL_INFO[special]
        state = "🟢 فعال" if ab["special_active"] else (f"🟡 شانس {int(ab['special_chance']*100)}٪" if ab["special_chance"] else "🔴 هنوز باز نشده")
        lines.append(f"✨ اثر ویژه‌ی تایر: {info['name_fa']} — {state}")
        lines.append(f"   {info['desc']}")

    lines.append("")
    lines.append(f"🔗 پیوند: سطح **{bond_level}/{BOND_MAX_LEVEL}** ({bond_xp} XP)")
    if bond_level < BOND_MAX_LEVEL:
        next_need = bond_xp_for_level(bond_level + 1) - bond_xp
        lines.append(f"   تا سطح بعد: {max(0,next_need)} کشته‌ی دیگه")
    lines.append(f"   {BOND_LEVEL_DESC.get(bond_level, '')}")
    if ab["crit"] or ab["lifesteal"] or ab["dmg_mult_flat"]:
        extras = []
        if ab["crit"]: extras.append(f"+{int(ab['crit']*100)}٪ کریت")
        if ab["lifesteal"]: extras.append(f"+{int(ab['lifesteal']*100)}٪ لایف‌استیل")
        if ab["dmg_mult_flat"]: extras.append(f"+{int(ab['dmg_mult_flat']*100)}٪ آسیب کلی")
        lines.append(f"   بونوس پیوند: {', '.join(extras)}")

    lines.append("")
    lines.append(f"💀 کشته‌ها با این {meta['word_fa']}: {kills}")
    lines.append(f"⚰️ مرگ‌های همراه این {meta['word_fa']}: {deaths}")

    if stage < cfg["max_awaken"]:
        target = stage + 1
        cost = awaken_cost(tier, target)
        mat, qty = awaken_material_need(atype, tier, target)
        chance = awaken_success_chance(tier, target)
        info = MATERIALS_INFO_BY_TYPE[atype][mat]
        lines.append("")
        lines.append(f"➡️ **بیداری بعدی → {AWAKENING_STAGE_NAMES[target]}**")
        lines.append(f"   💰 هزینه: {bz_to_display(cost)}")
        lines.append(f"   📦 نیاز: {qty}x {info['emoji']} {info['name_fa']}")
        lines.append(f"   🎲 شانس موفقیت: {int(chance*100)}٪")
        next_cap = max_artifact_capacity(tier, target, bond_level)
        lines.append(f"   🔮 ظرفیتِ اسنس بعدِ بیداری: {ab['capacity']} → **{next_cap}**")
        lines.append(f"   از دستور {meta['command']}_awaken برای تلاش استفاده کن.")
    else:
        lines.append("")
        lines.append(f"🏆 این {meta['word_fa']} به اوج بیداریِ رتبه‌ش رسیده!")

    return "\n".join(lines)
