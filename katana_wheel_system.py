# ============================================================
#  ASTRAL ABYSS — گردونه‌های کاتانای افسانه‌ای (Katana Gacha Wheels)
#  (katana_wheel_system.py)
# ------------------------------------------------------------
#  فایلِ کاملاً جدا و مستقل — به هیچ فایلِ قدیمی (katana_core.py،
#  katana_system.py، lootbox_shop.py) دست نمی‌زنه و چیزی رو خرابشون
#  نمی‌کنه. این یه سیستمِ گردونه/گاچای مستقل برای «کاتاناهای رلیک»ه:
#  کاتاناهایی که به کاراکترِ بازیکن وصل نیستن، خودشون یه آیتمِ سلاحِ
#  واقعیِ قابل‌اکیپ‌ان (از موتورِ item_system.generate_item ساخته
#  می‌شن، پس افیکس/دوام/امتیاز واقعی دارن و تو Combat Power حساب می‌شن).
#
#  ساختار:
#    • ۴ رتبه‌ی رلیک: اسطوره‌ای(mythic) < افسانه‌ای(legendary)
#      < میراث(legacy→ancient) < الهی(divine→astral)
#    • ~۴۰ کاتانای یکتا با اسم/ایموجی/توضیح، پخش‌شده بینِ رتبه‌ها
#    • ۹ گردونه‌ی مختلف، هرکدوم استخرِ رتبه‌ی خودش رو داره، قیمتِ
#      پایه‌ش رندوم و بالاست (طبقِ درخواستِ حسین)
#    • بسته‌های خرید ۱ / ۱۰ / ۳۰ / ۵۰ تایی (مثل بسته‌های کالاف) —
#      هرچی بسته بزرگ‌تر، تخفیفِ واحد بیشتر + تضمینِ رتبه‌ی بالاتر
#    • پیتیِ دائمی هر گردونه: هر ۵۰ کشش (جمعی، نه فقط تو یه خرید)
#      یه کاتانای «بنر»ِ اختصاصیِ همون گردونه رو تضمینی می‌ده
#    • کوپن: کدهای تخفیف/کشش‌رایگان قابل‌فعال‌سازی
# ============================================================
from __future__ import annotations
import random
import time

import item_system as itsys

# ────────────────────────────────────────────────────────────
# ۱) رتبه‌های کاتانای گردونه (Relic Tiers)
# ────────────────────────────────────────────────────────────
# ترتیب از ضعیف‌ترین به قوی‌ترین. rarity به RARITY_DATA خودِ
# item_system وصل می‌شه تا افیکس/امتیاز واقعی بگیره.
TIER_ORDER = ["mythic", "legendary", "legacy", "divine"]

TIER_INFO = {
    "mythic":    {"label": "اسطوره‌ای", "emoji": "🔥", "rarity": "mythic"},
    "legendary": {"label": "افسانه‌ای", "emoji": "🌟", "rarity": "legendary"},
    "legacy":    {"label": "میراث",     "emoji": "🐉", "rarity": "ancient"},
    "divine":    {"label": "الهی",      "emoji": "👑", "rarity": "astral"},
}


def tier_rarity(tier: str) -> str:
    return TIER_INFO.get(tier, TIER_INFO["mythic"])["rarity"]


# ────────────────────────────────────────────────────────────
# ۲) رستِر کاتاناها — کلی کاتانای یکتا، پخش‌شده بینِ ۴ رتبه
# ────────────────────────────────────────────────────────────
KATANA_ROSTER = {
    "mythic": [
        {"name": "دندانِ گرگِ شب",      "emoji": "🌙", "desc": "زوزه‌ای که پیش از ضربه شنیده می‌شه."},
        {"name": "خارِ زهرآگین",        "emoji": "🥀", "desc": "بریدگیِ کوچیکش هم کافیه."},
        {"name": "شعله‌ی خاموش",        "emoji": "🕯️", "desc": "آتشی که صدا نداره، فقط خاکستر می‌ذاره."},
        {"name": "پژواکِ فولاد",        "emoji": "🔔", "desc": "هر ضربه‌ش تو گوشِ حریف تکرار می‌شه."},
        {"name": "چنگالِ توفان",        "emoji": "🌬️", "desc": "بادِ قبل از رعد، همیشه اول می‌رسه."},
        {"name": "اشکِ یخی",            "emoji": "🧊", "desc": "از دلِ یه زمستونِ فراموش‌شده تراشیده شده."},
        {"name": "نیشِ عقرب",           "emoji": "🦂", "desc": "دو بار نمی‌زنه — یه بار کافیه."},
        {"name": "سایه‌ی گمشده",        "emoji": "🌑", "desc": "هیچ‌وقت دقیقاً جایی که فکر می‌کنی نیست."},
        {"name": "پرِ کلاغِ سیاه",       "emoji": "🐦‍⬛", "desc": "خبرِ مرگ رو زودتر از خودِ مرگ می‌رسونه."},
        {"name": "خنجرِ شکسته‌بند",      "emoji": "🩹", "desc": "شکسته به دنیا اومد، ولی هیچ‌وقت نشکست."},
        {"name": "زبانه‌ی اخگر",         "emoji": "🔥", "desc": "از دلِ یه کوره‌ی خاموش، هنوز داغه."},
        {"name": "چکشِ شکسته",          "emoji": "🔩", "desc": "یه‌بار فلز رو شکل داد، حالا فقط می‌شکنه."},
        {"name": "پنجه‌ی روباهِ سفید",   "emoji": "🦊", "desc": "قبل از اینکه ببینیش، رفته."},
        {"name": "زهرِ شبنم",           "emoji": "💧", "desc": "آروم می‌شینه، آروم‌تر می‌کشه."},
        {"name": "خارِ سیاه‌چاله",       "emoji": "🕳️", "desc": "چیزی که توش بره، دیگه برنمی‌گرده."},
        {"name": "تیغِ کرمِ شب‌تاب",     "emoji": "🪱", "desc": "تو تاریکی می‌درخشه، درست قبلِ ضربه."},
    ],
    "legendary": [
        {"name": "شعله‌ی آخرالزمان",     "emoji": "☄️", "desc": "آخرین چیزی که خیلی‌ها دیدن."},
        {"name": "تیغه‌ی هزارساله",      "emoji": "⏳", "desc": "با هر جنگ، فراموش‌کارتر و تیزتر شده."},
        {"name": "خشمِ اژدهای سرخ",      "emoji": "🐲", "desc": "تو خوابِ صاحبش هم شعله می‌کشه."},
        {"name": "ندای مغاک",           "emoji": "📯", "desc": "صداش رو فقط اونی می‌شنوه که قراره بمیره."},
        {"name": "تاجِ شکسته",          "emoji": "👑", "desc": "یه‌بار پادشاهی رو انداخت — دوباره می‌تونه."},
        {"name": "برشِ ابدیت",          "emoji": "♾️", "desc": "زمان رو هم می‌بره، نه فقط گوشت رو."},
        {"name": "قلبِ توفانِ سیاه",     "emoji": "🌩️", "desc": "هر ضربه، رعدی که دیر می‌رسه ولی می‌رسه."},
        {"name": "روحِ ققنوسِ خاکستری",  "emoji": "🔥", "desc": "هربار که می‌شکنه، برنده‌تر برمی‌گرده."},
        {"name": "زوزه‌ی گرگِ سفید",     "emoji": "🐺", "desc": "بسته‌ای که دیگه وجود نداره، پشتشه."},
        {"name": "خونِ ستاره",          "emoji": "🌠", "desc": "از یه ستاره‌ی مرده، هنوز می‌درخشه."},
        {"name": "دروگرِ سایه‌ها",       "emoji": "💀", "desc": "هر جنگی که ببره، یه اسمِ دیگه به خودش اضافه می‌کنه."},
        {"name": "خشمِ کِرِمزُنِ باستانی", "emoji": "🩸", "desc": "رنگش از خونِ هزاران جنگه، نه از رنگ."},
        {"name": "شبحِ سرگردان",         "emoji": "👻", "desc": "صاحبش مرد، تیغه هنوز جنگ می‌ده."},
        {"name": "تایتانِ خفته",         "emoji": "🗿", "desc": "سنگینه، ولی هیچ‌وقت خسته نمی‌شه."},
        {"name": "نواخترِ منفجرشده",     "emoji": "💥", "desc": "یه انفجار، یه اسم، یه افسانه."},
        {"name": "غروبِ ابدی",          "emoji": "🌆", "desc": "خورشیدش هیچ‌وقت کامل غروب نمی‌کنه."},
    ],
    "legacy": [
        {"name": "میراثِ شاهِ گمشده",    "emoji": "🏰", "desc": "آخرین چیزی که از یه امپراتوری موند."},
        {"name": "شمشیرِ نسل‌های سوخته", "emoji": "🔥", "desc": "هر نسلی که دستش گرفت، یه چیزی سوزوند."},
        {"name": "پیمانِ خونِ باستانی",  "emoji": "🩸", "desc": "با خون امضا شده، با خون تمدید می‌شه."},
        {"name": "لبه‌ی حافظه‌ی گم‌شده", "emoji": "🕰️", "desc": "چیزهایی رو یادشه که هیچ‌کس دیگه یادش نیست."},
        {"name": "خشمِ آخرین ژنرال",     "emoji": "🎖️", "desc": "جنگی که هیچ‌وقت رسماً تموم نشد."},
        {"name": "تیغه‌ی تاجِ فراموش‌شده", "emoji": "👑", "desc": "برای کسی که لیاقتش رو داره منتظره."},
        {"name": "روحِ سلسله‌ی خاموش",   "emoji": "🗿", "desc": "آخرین بازمانده‌ی یه خطِ خونیِ کامل."},
        {"name": "تایتانِ باستانیِ آخر", "emoji": "⛰️", "desc": "قبل از اینکه کوه‌ها اسم داشته باشن، این بود."},
        {"name": "میراثِ آتشِ نخستین",   "emoji": "🔥", "desc": "اولین آتشی که هیچ‌وقت خاموش نشد."},
        {"name": "شمشیرِ فراموشیِ مقدس", "emoji": "📜", "desc": "نوشته‌ای که کسی جرأتِ خوندنش رو نداره."},
    ],
    "divine": [
        {"name": "دَمِ آفرینشِ نخستین",   "emoji": "🌌", "desc": "قبل از اسم‌داشتنِ دنیا، این وجود داشت."},
        {"name": "پرتوِ آخرینِ خدایان",   "emoji": "✨", "desc": "وقتی خدایان رفتن، این رو جا گذاشتن."},
        {"name": "تیغه‌ی سکوتِ ابدی",     "emoji": "🕊️", "desc": "بعد از این، دیگه چیزی برای گفتن نمی‌مونه."},
        {"name": "قلبِ کهکشانِ فروپاشیده", "emoji": "🌠", "desc": "از مرگِ یه کهکشان، تولدِ یه تیغه."},
        {"name": "ندای بی‌انتها",         "emoji": "♾️", "desc": "شروع و پایانش یه نقطه‌ست."},
        {"name": "نفسِ خالقِ نخستین",     "emoji": "🌬️", "desc": "اولین نفسی که به دنیا شکل داد."},
        {"name": "تاجِ آفرینشِ آخر",      "emoji": "👑", "desc": "چیزی که بعدش دیگه چیزی ساخته نشد."},
    ],
}

# نگاشتِ اسم → (tier, index) برای پیدا کردنِ سریعِ اطلاعاتِ هر کاتانا
_NAME_INDEX: dict[str, tuple[str, int]] = {}
for _tier, _list in KATANA_ROSTER.items():
    for _i, _k in enumerate(_list):
        _NAME_INDEX[_k["name"]] = (_tier, _i)


def all_katana_names(tier: str | None = None) -> list[str]:
    if tier:
        return [k["name"] for k in KATANA_ROSTER.get(tier, [])]
    return [n for lst in KATANA_ROSTER.values() for n in [k["name"] for k in lst]]


# ────────────────────────────────────────────────────────────
# ۳) گردونه‌ها (Wheels) — ۹ گردونه، قیمتِ پایه‌ی بالا و رندوم
# ────────────────────────────────────────────────────────────
# tier_pool/tier_weights: چه رتبه‌هایی با چه وزنی تو این گردونه می‌چرخن
# featured_tier: رتبه‌ی «تبلیغاتیِ» گردونه (همون که تو بسته‌ی ۱۰تایی تضمین می‌شه)
# banner: اسمِ کاتانای اختصاصیِ همین گردونه که با پیتیِ ۵۰ تضمین می‌شه
# currency: "zen" یا "shard"
WHEELS = {
    "flame_wheel": {
        "name": "گردونه‌ی شعله‌ی نیمه‌شب", "emoji": "🔥",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [72, 28],
        "featured_tier": "legendary", "banner": "شعله‌ی آخرالزمان",
        "currency": "zen", "price": 24_500,
        "desc": "اولین قدمِ ورود به دنیای کاتاناهای رلیک — ارزون‌ترینِ همه، ولی همچنان خیلی گرون.",
    },
    "frost_wheel": {
        "name": "گردونه‌ی یخِ ابدی", "emoji": "❄️",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [66, 34],
        "featured_tier": "legendary", "banner": "برشِ ابدیت",
        "currency": "zen", "price": 29_900,
        "desc": "شانسِ کمی بیشتر برای رتبه‌ی افسانه‌ای، نسبت به گردونه‌ی شعله.",
    },
    "storm_wheel": {
        "name": "گردونه‌ی خشمِ توفان", "emoji": "🌩️",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [58, 42],
        "featured_tier": "legendary", "banner": "قلبِ توفانِ سیاه",
        "currency": "zen", "price": 37_250,
        "desc": "بالاترین شانسِ افسانه‌ای بینِ گردونه‌های ردیفِ Zen.",
    },
    "shadow_wheel": {
        "name": "گردونه‌ی سایه‌های بی‌نام", "emoji": "🌑",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [78, 22],
        "featured_tier": "legendary", "banner": "زوزه‌ی گرگِ سفید",
        "currency": "zen", "price": 61_000,
        "desc": "اولین گردونه‌ای که شانسِ واقعیِ رتبه‌ی میراث داره.",
    },
    "phoenix_wheel": {
        "name": "گردونه‌ی ققنوسِ جاودان", "emoji": "🦅",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [68, 32],
        "featured_tier": "legacy", "banner": "شمشیرِ نسل‌های سوخته",
        "currency": "zen", "price": 74_800,
        "desc": "گرون‌ترین گردونه‌ی Zen — شانسِ خوبی برای میراث.",
    },
    "dragon_wheel": {
        "name": "گردونه‌ی خشمِ اژدها", "emoji": "🐉",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [55, 45],
        "featured_tier": "legacy", "banner": "پیمانِ خونِ باستانی",
        "currency": "shard", "price": 145,
        "desc": "ورودی به دنیای Echo Shard — بالاترین شانسِ میراث تا این‌جا.",
    },
    "void_wheel": {
        "name": "گردونه‌ی مغاکِ بی‌انتها", "emoji": "🕳️",
        "tier_pool": ["legacy", "divine"], "tier_weights": [74, 26],
        "featured_tier": "legacy", "banner": "روحِ سلسله‌ی خاموش",
        "currency": "shard", "price": 235,
        "desc": "اولین گردونه‌ای که واقعاً شانسِ رتبه‌ی الهی داره.",
    },
    "celestial_wheel": {
        "name": "گردونه‌ی تیغِ آسمانی", "emoji": "✨",
        "tier_pool": ["legacy", "divine"], "tier_weights": [58, 42],
        "featured_tier": "divine", "banner": "پرتوِ آخرینِ خدایان",
        "currency": "shard", "price": 320,
        "desc": "شانسِ نزدیک به نصف‌نصف بینِ میراث و الهی.",
    },
    "eternal_wheel": {
        "name": "گردونه‌ی ابدیتِ آخرین", "emoji": "👑",
        "tier_pool": ["divine"], "tier_weights": [100],
        "featured_tier": "divine", "banner": "ندای بی‌انتها",
        "currency": "shard", "price": 499,
        "desc": "گرون‌ترین و نایاب‌ترینِ همه — هر کشش، تضمینیِ رتبه‌ی الهی.",
    },

    # ─── گردونه‌های اضافه‌ی ردیفِ Zen (ارزون‌تر، تنوعِ بیشتر) ──────
    "ember_wheel": {
        "name": "گردونه‌ی زبانه‌ی اخگر", "emoji": "🕯️",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [80, 20],
        "featured_tier": "legendary", "banner": "زبانه‌ی اخگر",
        "currency": "zen", "price": 18_900,
        "desc": "ارزون‌ترینِ همه‌ی گردونه‌ها — یه شروعِ خوب برای جمع‌کردنِ کاتانای اسطوره‌ای.",
    },
    "crimson_wheel": {
        "name": "گردونه‌ی سرخِ خونین", "emoji": "🩸",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [63, 37],
        "featured_tier": "legendary", "banner": "خشمِ اژدهای سرخ",
        "currency": "zen", "price": 33_400,
        "desc": "شانسِ بالاتر از حدِ متوسط برای افسانه‌ای، قیمتِ متعادل.",
    },
    "twilight_wheel": {
        "name": "گردونه‌ی گرگ‌ومیش", "emoji": "🌆",
        "tier_pool": ["mythic", "legendary"], "tier_weights": [50, 50],
        "featured_tier": "legendary", "banner": "غروبِ ابدی",
        "currency": "zen", "price": 45_600,
        "desc": "نصف‌نصفِ کامل بینِ اسطوره‌ای و افسانه‌ای.",
    },
    "wraith_wheel": {
        "name": "گردونه‌ی روحِ سرگردان", "emoji": "👻",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [82, 18],
        "featured_tier": "legendary", "banner": "شبحِ سرگردان",
        "currency": "zen", "price": 54_200,
        "desc": "شانسِ کمِ میراث با قیمتِ پایین‌تر از گردونه‌های مشابه.",
    },
    "abyss_wheel": {
        "name": "گردونه‌ی مغاکِ فراموش‌شده", "emoji": "🌀",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [70, 30],
        "featured_tier": "legendary", "banner": "خشمِ کِرِمزُنِ باستانی",
        "currency": "zen", "price": 68_500,
        "desc": "برای اونایی که از گردونه‌ی سایه گذشتن و میراث می‌خوان.",
    },
    "reaper_wheel": {
        "name": "گردونه‌ی دروگرِ سایه‌ها", "emoji": "💀",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [50, 50],
        "featured_tier": "legacy", "banner": "دروگرِ سایه‌ها",
        "currency": "zen", "price": 82_000,
        "desc": "گرون‌ترینِ ردیفِ Zen — شانسِ نصف‌نصف برای رتبه‌ی میراث.",
    },

    # ─── گردونه‌های اضافه‌ی ردیفِ Echo Shard (نایاب‌تر) ────────────
    "titan_wheel": {
        "name": "گردونه‌ی تایتانِ خفته", "emoji": "🗿",
        "tier_pool": ["legendary", "legacy"], "tier_weights": [45, 55],
        "featured_tier": "legacy", "banner": "تایتانِ خفته",
        "currency": "shard", "price": 165,
        "desc": "بالاترین شانسِ میراث بینِ گردونه‌های Echo Shard.",
    },
    "nova_wheel": {
        "name": "گردونه‌ی نواخترِ منفجرشده", "emoji": "💥",
        "tier_pool": ["legacy", "divine"], "tier_weights": [80, 20],
        "featured_tier": "legacy", "banner": "میراثِ شاهِ گمشده",
        "currency": "shard", "price": 268,
        "desc": "شروعِ محتاطانه‌ی مسیرِ الهی — بیشترِ کشش‌ها میراثه.",
    },
    "genesis_wheel": {
        "name": "گردونه‌ی نفسِ آفرینش", "emoji": "🌬️",
        "tier_pool": ["divine"], "tier_weights": [100],
        "featured_tier": "divine", "banner": "نفسِ خالقِ نخستین",
        "currency": "shard", "price": 555,
        "desc": "دومین گردونه‌ی صددرصد الهی — بنرِ اختصاصیِ خودش رو داره.",
    },
}

WHEEL_ORDER = [
    "flame_wheel", "ember_wheel", "frost_wheel", "crimson_wheel", "storm_wheel",
    "twilight_wheel", "shadow_wheel", "wraith_wheel", "phoenix_wheel", "abyss_wheel",
    "reaper_wheel", "dragon_wheel", "titan_wheel", "void_wheel", "nova_wheel",
    "celestial_wheel", "genesis_wheel", "eternal_wheel",
]

# ─── بسته‌های خرید (مثلِ کالاف: ۱ → ۱۰ → ۳۰ → ۵۰) ────────────
BUNDLE_SIZES = [1, 10, 30, 50]
BUNDLE_PRICE_MULT = {1: 1.0, 10: 9.35, 30: 26.4, 50: 41.5}   # هرچی بزرگ‌تر، تخفیفِ واحد بیشتر
BUNDLE_MIN_FEATURED = {1: 0, 10: 1, 30: 3, 50: 0}  # حداقلِ تضمینیِ featured_tier در بسته (۵۰ خودش بنر تضمینی داره)

# پیتیِ سخت: بعد از این تعداد کشش بدون رسیدنِ به featured_tier، کشش بعدی
# اجباراً از featured_tier رول می‌شه.
HARD_PITY_THRESHOLD = 35
# پیتیِ بنر: هر چند کشش (جمعِ کل، نه فقط یه خرید)، کاتانای بنرِ همون گردونه
# تضمینی داده می‌شه.
BANNER_PITY_INTERVAL = 50


def get_wheel(wheel_id: str) -> dict | None:
    return WHEELS.get(wheel_id)


def bundle_price(wheel: dict, size: int) -> int:
    mult = BUNDLE_PRICE_MULT.get(size, size)
    return int(wheel["price"] * mult)


def currency_balance(player: dict, currency: str) -> int:
    return player.get("zen", 0) if currency == "zen" else player.get("rift_shards", 0)


def currency_label(currency: str) -> str:
    return "Zen" if currency == "zen" else "Echo Shard 🔹"


# ────────────────────────────────────────────────────────────
# ۴) گردونه‌ی روزانه — هر روز یه گردونه‌ی «ویژه‌ی امروز» با تخفیف
# ────────────────────────────────────────────────────────────
DAILY_DISCOUNT = 0.20          # ۲۰٪ تخفیف روی خریدِ تکی از گردونه‌ی امروز
DAILY_BANNER_BONUS = 0.30      # ۳۰٪ کاهشِ نیازِ پیتیِ بنر برای گردونه‌ی امروز


def get_daily_wheel_id(day_index: int | None = None) -> str:
    """گردونه‌ای که امروز featured/ویژه‌ست. day_index رو معمولاً از
    int(time.time() // 86400) می‌گیریم تا هر ۲۴ ساعت عوض بشه."""
    if day_index is None:
        day_index = int(time.time() // 86400)
    return WHEEL_ORDER[day_index % len(WHEEL_ORDER)]


def is_daily_wheel(wheel_id: str) -> bool:
    return wheel_id == get_daily_wheel_id()


def daily_effective_price(wheel_id: str, wheel: dict, size: int) -> int:
    price = bundle_price(wheel, size)
    if size == 1 and is_daily_wheel(wheel_id):
        price = int(price * (1 - DAILY_DISCOUNT))
    return price


# ────────────────────────────────────────────────────────────
# ۵) کوپن‌ها
# ────────────────────────────────────────────────────────────
COUPONS = {
    "KATANA10":   {"type": "discount",  "value": 0.10, "desc": "۱۰٪ تخفیف روی خریدِ بعدیِ یه گردونه"},
    "KATANA25VIP": {"type": "discount", "value": 0.25, "desc": "۲۵٪ تخفیفِ ویژه (محدود)"},
    "DRAGONGIFT": {"type": "free_pull", "value": 1,    "desc": "۱ کششِ رایگان روی هر گردونه‌ای"},
    "LEGACYFREE": {"type": "free_pull", "value": 3,    "desc": "۳ کششِ رایگان — هدیه‌ی ویژه"},
}


def redeem_coupon(player: dict, code: str) -> tuple[bool, str]:
    code = (code or "").strip().upper()
    coupon = COUPONS.get(code)
    if not coupon:
        return False, "❌ این کد معتبر نیست."
    redeemed = player.setdefault("katana_wheel_redeemed_coupons", [])
    if code in redeemed:
        return False, "⚠️ این کد رو قبلاً استفاده کردی."
    redeemed.append(code)

    if coupon["type"] == "discount":
        player["katana_wheel_discount"] = coupon["value"]
        return True, f"✅ کدِ تخفیف فعال شد! {int(coupon['value']*100)}٪ روی خریدِ بعدیِ گردونه."
    else:
        player["katana_wheel_free_pulls"] = player.get("katana_wheel_free_pulls", 0) + coupon["value"]
        return True, f"✅ {coupon['value']} کششِ رایگان به حسابت اضافه شد!"


def _consume_discount(player: dict, price: int) -> int:
    disc = player.get("katana_wheel_discount", 0)
    if disc:
        price = int(price * (1 - disc))
        player["katana_wheel_discount"] = 0
    return price


def _consume_free_pulls(player: dict, size: int) -> int:
    """هرچقدر کششِ رایگان داشته باشه از size کم می‌کنه؛ خروجی: تعدادِ کششِ
    باقی‌مونده که واقعاً باید پول‌شون پرداخت بشه."""
    free = player.get("katana_wheel_free_pulls", 0)
    if free <= 0:
        return size
    used = min(free, size)
    player["katana_wheel_free_pulls"] = free - used
    return size - used


# ────────────────────────────────────────────────────────────
# ۶) پیتی/تاریخچه — state هر بازیکن به‌ازای هر گردونه
# ────────────────────────────────────────────────────────────
def _wheel_state(player: dict, wheel_id: str) -> dict:
    states = player.setdefault("katana_wheel_state", {})
    st = states.setdefault(wheel_id, {"total_pulls": 0, "since_featured": 0, "since_banner": 0})
    return st


# ────────────────────────────────────────────────────────────
# ۷) رول یه کاتانای تکی
# ────────────────────────────────────────────────────────────
def _roll_tier(wheel: dict) -> str:
    return random.choices(wheel["tier_pool"], weights=wheel["tier_weights"], k=1)[0]


def _make_katana_item(tier: str, name: str, player_level: int, wheel_id: str) -> dict:
    tier_name, idx = _NAME_INDEX.get(name, (tier, None))
    tpl_base = KATANA_ROSTER[tier_name][idx] if idx is not None else {"name": name, "emoji": "🗡️", "desc": ""}
    template = {
        "name": tpl_base["name"], "emoji": tpl_base["emoji"], "desc": tpl_base["desc"],
        "slot": "weapon",
    }
    item = itsys.generate_item(
        template, player_level, forced_rarity=tier_rarity(tier),
        drop_source=f"katana_wheel:{wheel_id}",
    )
    item["katana_relic"] = True
    item["relic_tier"] = tier
    return item


def _roll_single(wheel: dict, wheel_id: str, player_level: int, force_tier: str | None = None,
                  force_name: str | None = None) -> dict:
    if force_name:
        tier = _NAME_INDEX.get(force_name, (force_tier or wheel["tier_pool"][0], None))[0]
        return _make_katana_item(tier, force_name, player_level, wheel_id)
    tier = force_tier or _roll_tier(wheel)
    name = random.choice(all_katana_names(tier))
    return _make_katana_item(tier, name, player_level, wheel_id)


# ────────────────────────────────────────────────────────────
# ۸) خریدِ یه بسته (۱/۱۰/۳۰/۵۰) — تابعِ اصلی که هندلر صداش می‌زنه
# ────────────────────────────────────────────────────────────
def pull_wheel(player: dict, wheel_id: str, size: int) -> tuple[bool, str, list[dict], dict]:
    """
    خروجی: (ok, error_msg, results[], meta)
    results: لیستِ آیتم‌های کامل (از item_system) که به inventory اضافه شدن
    meta: {"price_paid":..., "free_used":..., "banner_hit": bool, "discount_applied": bool}
    """
    wheel = WHEELS.get(wheel_id)
    if not wheel:
        return False, "❌ این گردونه پیدا نشد.", [], {}
    if size not in BUNDLE_SIZES:
        return False, "❌ اندازه‌ی بسته نامعتبره.", [], {}

    player_level = player.get("level", 1)
    currency = wheel["currency"]

    payable_count = _consume_free_pulls(player, size)
    free_used = size - payable_count

    price = daily_effective_price(wheel_id, wheel, size) if payable_count == size else bundle_price(wheel, size)
    # اگه بخشی رایگان بود، فقط هزینه‌ی نسبیِ همون تعداد رو حساب کن
    if payable_count and payable_count != size:
        price = int(bundle_price(wheel, size) * (payable_count / size))
    elif payable_count == 0:
        price = 0

    discount_applied = False
    if price > 0 and player.get("katana_wheel_discount", 0):
        price = _consume_discount(player, price)
        discount_applied = True

    if price > 0 and currency_balance(player, currency) < price:
        have = currency_balance(player, currency)
        # کششِ رایگانِ مصرف‌شده رو برگردون چون خرید انجام نشد
        if free_used:
            player["katana_wheel_free_pulls"] = player.get("katana_wheel_free_pulls", 0) + free_used
        return False, (
            f"❌ {currency_label(currency)} کافی نداری!\n"
            f"لازم: {price:,} | داری: {have:,}"
        ), [], {}

    if price > 0:
        if currency == "zen":
            player["zen"] -= price
        else:
            player["rift_shards"] = player.get("rift_shards", 0) - price

    st = _wheel_state(player, wheel_id)
    inv = player.setdefault("inventory", [])
    results: list[dict] = []
    banner_hit = False
    featured = wheel["featured_tier"]
    min_featured_needed = BUNDLE_MIN_FEATURED.get(size, 0)
    featured_count = 0

    banner_target = BANNER_PITY_INTERVAL
    if is_daily_wheel(wheel_id):
        banner_target = max(5, int(BANNER_PITY_INTERVAL * (1 - DAILY_BANNER_BONUS)))

    for i in range(size):
        st["total_pulls"] += 1
        st["since_featured"] += 1
        st["since_banner"] += 1

        force_tier = None
        force_name = None

        # بسته‌ی ۵۰تایی همیشه آخرین کشش‌ش رو به‌عنوانِ بنرِ تضمینی می‌ده
        if size == 50 and i == size - 1:
            force_name = wheel["banner"]
        elif st["since_banner"] >= banner_target:
            force_name = wheel["banner"]
        elif st["since_featured"] >= HARD_PITY_THRESHOLD:
            force_tier = featured
        elif i == size - 1 and featured_count < min_featured_needed:
            force_tier = featured

        item = _roll_single(wheel, wheel_id, player_level, force_tier=force_tier, force_name=force_name)
        inv.append(item)

        rolled_tier = item.get("relic_tier", featured)
        if rolled_tier == featured or TIER_ORDER.index(rolled_tier) >= TIER_ORDER.index(featured):
            featured_count += 1
            st["since_featured"] = 0
        if force_name == wheel["banner"] or item["name"] == wheel["banner"]:
            banner_hit = True
            st["since_banner"] = 0

        rlabel = TIER_INFO[rolled_tier]["label"]
        results.append({
            "name": item["name"], "emoji": item["emoji"], "tier": rolled_tier,
            "label": f"{TIER_INFO[rolled_tier]['emoji']} {item['name']} ({rlabel}) — {item['sell']:,} Zen",
            "is_banner": item["name"] == wheel["banner"],
        })

    meta = {
        "price_paid": price, "currency": currency, "free_used": free_used,
        "banner_hit": banner_hit, "discount_applied": discount_applied,
    }
    return True, "", results, meta
