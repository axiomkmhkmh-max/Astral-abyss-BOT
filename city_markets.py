# ============================================================
#  ASTRAL ABYSS — 🏮 بازارهای زنده‌ی شهر (Living City Markets)
#  (city_markets.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  هر نقشه‌ی economy.MAPS_DATA حالا یه «محله‌ی بازار» داره: ۲ تا
#  غرفه‌ی ثابت و اسم‌دار، کاملاً متفاوت از یکی‌به‌یکیِ نقشه‌های دیگه
#  (میوه‌فروشی، کبابی، خیاطی، آهنگری، عتیقه‌فروشی...) — هرکدوم با
#  شخصیتِ خاصِ خودش حرف می‌زنه.
#
#  چیزی که این بازار رو «زنده» می‌کنه: موجودیِ هر غرفه مشترکِ بینِ
#  همه‌ی بازیکن‌هاست (یه سندِ واحد تو دیتابیس) و واقعاً می‌تونه تموم
#  بشه — اگه یکی زودتر بخره، نفرِ بعدی یه ردیفِ خالی می‌بینه، تا
#  چرخه‌ی بعدیِ رفرش (REFRESH_INTERVAL). این یعنی بازار واقعاً یه
#  چیزِ مشترک و در حالِ تغییره، نه یه منوی ثابتِ تکراری.
#
#  علاوه بر این، هر غرفه یه «اعتبارِ فروشنده‌ی» شخصی به‌ازای هر بازیکن
#  داره (تعدادِ خریدها) که تخفیفِ فزاینده می‌ده، هر چرخه شانسی برای یه
#  ردیفِ «✨ ویژه» با رریتیِ بالا و موجودیِ ۱ عددی هست، و بازیکن می‌تونه
#  یه‌بار در هر چرخه چانه بزنه. رابطه با پادشاهِ همون نقشه (map_kings.py)
#  هم تخفیفِ اضافه می‌ده — این دو سیستم حالا به‌هم وصلن.
#
#  از رویِ economy.MAPS_DATA، item_system (تولیدِ آیتم/مصرفی)،
#  database.city_market_col و (اختیاری/soft) map_kings می‌خونه/می‌نویسه.
#  فیلدهای جدیدِ پلیر (vendor_rep / market_haggle) رو خودش مدیریت
#  می‌کنه، دقیقاً هم‌الگو با نحوه‌ی مدیریتِ king_favor تو map_kings.py؛
#  هیچ فیلدِ قدیمیِ دیگه‌ای رو دستکاری نمی‌کنه.
# ============================================================
from __future__ import annotations

import random
import time
import uuid

REFRESH_INTERVAL = 6 * 3600      # هر غرفه هر ۶ ساعت موجودیِ تازه می‌گیره
STOCK_SIZE_RANGE = (3, 4)
STOCK_QTY_RANGE = (2, 5)         # هر ردیف چندتا موجودیِ مشترک داره

# ─── ✨ ردیفِ ویژه — شانسِ ظاهر شدنِ یه آیتمِ کمیاب و تک‌عددی هر چرخه ──
SPECIAL_ROW_CHANCE = 0.28
SPECIAL_PRICE_MULT = 2.2

# ─── 🎖️ اعتبارِ فروشنده (Vendor Reputation) — بر اساسِ تعدادِ خریدِ
#     همون بازیکن از همون غرفه، تخفیفِ فزاینده می‌ده ────────────────
VENDOR_REP_THRESHOLD = {"newcomer": 0, "regular": 5, "trusted": 15, "vip": 35}
VENDOR_REP_LABEL = {
    "newcomer": "🆕 نوپا",
    "regular":  "🙂 مشتریِ همیشگی",
    "trusted":  "🤝 معتمد",
    "vip":      "💎 VIP",
}
VENDOR_REP_DISCOUNT = {"newcomer": 0.0, "regular": 0.05, "trusted": 0.10, "vip": 0.18}
MAX_TOTAL_DISCOUNT = 0.35  # سقفِ جمعِ همه‌ی تخفیف‌ها (اعتبار + پادشاه + چانه‌زنی)

# ─── 🎭 چانه‌زنی — یه‌بار در هر چرخه‌ی رفرش، شانسِ موفقیت بر اساسِ اعتبار ─
HAGGLE_SUCCESS_BASE = {"newcomer": 0.35, "regular": 0.5, "trusted": 0.65, "vip": 0.8}
HAGGLE_DISCOUNT = 0.12
HAGGLE_COOLDOWN = REFRESH_INTERVAL

# تخفیف/ضریب قیمت بر اساسِ نوعِ غرفه (نسبت به sell پایه‌ی آیتم)
KIND_PRICE_MULT = {
    "produce":     1.6,
    "street_food": 2.0,
    "drinks":      1.8,
    "tailor":      3.2,
    "smith":       3.4,
    "curiosities": 4.0,
}

# رتبه‌بندیِ رریتیِ گیر بر اساسِ tier نقشه — برای غرفه‌های gear (خیاطی/آهنگری/عتیقه)
RARITY_POOL_BY_MAP_TIER = {
    "common":    ["common", "uncommon", "rare"],
    "uncommon":  ["uncommon", "rare"],
    "rare":      ["rare", "epic"],
    "epic":      ["epic", "mythic"],
    "legendary": ["mythic", "legendary"],
}


# ============================================================
#  🏮 CITY_MARKETS — ۲ غرفه‌ی ثابت به‌ازای هر نقشه
# ------------------------------------------------------------
#  هر غرفه: id/name/title/emoji/desc + kind (نوعِ کالا) +
#  greeting/item_flavor/farewell (استخرهای دیالوگ) + برای غرفه‌های
#  gear (tailor/smith/curiosities): templates (چند قالبِ آیتمِ
#  تماتیکِ خودِ همون غرفه، به‌جای قالبِ عمومیِ item_system).
# ============================================================
CITY_MARKETS: dict[str, list[dict]] = {
    "Abyssal Black Market": [
        {
            "id": "abm_streetfood", "name": "کبابیِ بی‌نام", "title": "🍢 دکه‌ی غذای مشکوک",
            "emoji": "🍢", "kind": "street_food",
            "desc": "هیچ‌کس نمی‌پرسه گوشتش از کجا اومده. طعمش خیلی خوبه که کسی واقعاً بخواد بدونه.",
            "greeting": ["«گشنه‌ای؟ نپرس چیه، فقط بخور.»", "«تازه‌ست. تازه‌تر از چیزی که فکرشو بکنی.»"],
            "item_flavor": ["«نوش‌جان. و... چیزی ندیدی، باشه؟»", "«بفرما. حساب‌مون صافه.»"],
            "farewell": ["«باز بیا. اگه هنوز زنده بودی.»"],
        },
        {
            "id": "abm_curios", "name": "پیرمردِ جعبه‌ها", "title": "🎁 دستفروشِ اشیای گمشده",
            "emoji": "🎁", "kind": "curiosities",
            "desc": "یه پتوی پر از جعبه‌های قفل‌شده جلوشه؛ می‌گه هرکدوم مالِ یکیه که دیگه برنگشت دنبالش.",
            "greeting": ["«همه‌چی یه قیمت داره. حتی چیزایی که صاحبشون فراموششون کرده.»", "«نگاه کن، ولی دست نزن تا نخری.»"],
            "item_flavor": ["«خوش به حالت. امیدوارم بهتر از صاحبِ قبلیش نگهش داری.»"],
            "farewell": ["«بازار هیچ‌وقت واقعاً بسته نمی‌شه.»"],
            "templates": [
                {"name": "حلقه‌ی صاحبِ گمشده", "emoji": "💍", "desc": "یه حلقه با یه حکاکیِ ناتموم؛ صاحبش هیچ‌وقت برنگشت دنبالش.", "slot": "ring"},
                {"name": "تعویذِ بی‌نام", "emoji": "🔮", "desc": "هیچ‌کس نمی‌دونه این تعویذ مالِ کیه — ولی هنوز گرمه.", "slot": "amulet"},
            ],
        },
    ],
    "Sands of Eternity": [
        {
            "id": "soe_produce", "name": "اُمِ‌زهرا", "title": "🍈 میوه‌فروشِ واحه",
            "emoji": "🍈", "kind": "produce",
            "desc": "زیرِ یه سایه‌بونِ رنگی، سبدهایی از خرما و انارِ واحه‌ای که فقط او آدرسش رو بلده.",
            "greeting": ["«این خرماها امروز صبح از نخل چیده شدن، پسرم. بچش!»", "«تو این گرما، شیرینیِ میوه بهترین هدیه‌ست.»", "«بیا، بشین زیرِ سایه، بعد حرف بزن.»"],
            "item_flavor": ["«نوش جونت. برکت باهات باشه.»", "«بگیر، بگیر — پول نگیرم دلم نمیاد بازم بدم.»"],
            "farewell": ["«خدا همرات، تو این شن‌ها مراقبِ خودت باش.»"],
        },
        {
            "id": "soe_tailor", "name": "یوسفِ بزاز", "title": "🧵 خیاطِ پارچه‌های شنی",
            "emoji": "🧵", "kind": "tailor",
            "desc": "پارچه‌هایی می‌بافه که گرمای صحرا رو دفع می‌کنن — می‌گه رازش تو نخِ شترمرغِ صحراییه.",
            "greeting": ["«لباسِ این صحرا با لباسِ هرجای دیگه فرق داره. بیا اندازه‌ت رو بگیرم.»", "«این پارچه از گرمای ظهر هم جون سالم به در می‌بره.»"],
            "item_flavor": ["«بپوش، ببین چقدر سبک‌تر می‌شی.»", "«این دستِ‌دوزِ خودمه. مراقبش باش.»"],
            "farewell": ["«برو، و بذار پارچه ازت محافظت کنه.»"],
            "templates": [
                {"name": "ردایِ بادِ صحرا", "emoji": "🥻", "desc": "ردایی سبک که گرمای روز رو از تنت دور نگه می‌داره.", "slot": "armor"},
                {"name": "دستکشِ نخِ شترمرغ", "emoji": "🧤", "desc": "بافته‌شده از الیافی که هیچ شنی توش گیر نمی‌کنه.", "slot": "gloves"},
                {"name": "چکمه‌ی گام‌ِ سبک", "emoji": "👢", "desc": "پاشنه‌ی پهن — رو شن فرو نمی‌ری.", "slot": "boots"},
            ],
        },
    ],
    "Holy Luminarchy": [
        {
            "id": "hl_bakery", "name": "خواهر مریانا", "title": "🍞 نانوایی مقدس",
            "emoji": "🍞", "kind": "street_food",
            "desc": "نانِ تازه‌ای می‌پزه که می‌گه با «دعا و آرد» درست می‌شه؛ بویی که تا بیرونِ کلیسا می‌پیچه.",
            "greeting": ["«نور بهت خوش‌آمد می‌گه — و این نانِ گرم هم همین‌طور.»", "«بشین، خستگیِ سفر با یه لقمه‌ی گرم کمتر می‌شه.»"],
            "item_flavor": ["«این رو با ایمان پختم. نوش‌جان.»", "«برکت باهات.»"],
            "farewell": ["«نور راهتو روشن کنه.»"],
        },
        {
            "id": "hl_tailor", "name": "برادر اُسوالد", "title": "✂️ خیاطِ ردایِ کشیشی",
            "emoji": "✂️", "kind": "tailor",
            "desc": "ردا و زره‌های سبکی می‌دوزه که می‌گه هرکدوم زیرِ یه دعای مخصوص کوک شدن.",
            "greeting": ["«اومدی برای یه ردایِ نو؟ خوبه، مالِ قبلیت رنگ باخته.»", "«هر بخیه‌ی این ردا با یه دعا همراهه.»"],
            "item_flavor": ["«بپوشش با احترام.»", "«نور از این پارچه رد می‌شه، حسش می‌کنی.»"],
            "farewell": ["«برو با آرامش.»"],
            "templates": [
                {"name": "ردایِ نورِ سپید", "emoji": "🥋", "desc": "پارچه‌ای که انگار خودش کمی می‌درخشه.", "slot": "armor"},
                {"name": "کلاهِ زائرِ مقدس", "emoji": "🎓", "desc": "کلاهی ساده، برایِ ذهنِ آرومِ زائر.", "slot": "helmet"},
            ],
        },
    ],
    "Celestial Spire": [
        {
            "id": "cs_tea", "name": "پیرِ رصدخانه", "title": "🍵 دکه‌ی چایِ ستاره‌ای",
            "emoji": "🍵", "kind": "drinks",
            "desc": "چای‌هایی دم می‌کنه که می‌گه با نورِ ستاره‌های خاص عطر گرفتن.",
            "greeting": ["«بشین. از اینجا آسمون بهتر دیده می‌شه، و چای هم بهتر می‌چسبه.»", "«این چای زیرِ نورِ فلان ستاره دم کشیده. حسش می‌کنی؟»"],
            "item_flavor": ["«بنوش، بذار ذهنت مثلِ آسمون شفاف بشه.»"],
            "farewell": ["«ستاره‌ها همرات.»"],
        },
        {
            "id": "cs_curios", "name": "دستیارِ منجم", "title": "🔭 دستفروشِ ادواتِ نجومی",
            "emoji": "🔭", "kind": "curiosities",
            "desc": "قطعاتِ عجیبی می‌فروشه که می‌گه از خرده‌ریزه‌های ستاره‌های افتاده‌ست.",
            "greeting": ["«این‌ها از آسمون افتادن. یا شایعه‌ست. یا نه.»", "«هرکدوم از این‌ها یه تکه از یه چیزِ خیلی بزرگ‌تره.»"],
            "item_flavor": ["«مراقبش باش. دیگه از این‌ها نمی‌افته.»"],
            "farewell": ["«به آسمون نگاه کن، گاهی.»"],
            "templates": [
                {"name": "حلقه‌ی خرده‌ستاره", "emoji": "💫", "desc": "حلقه‌ای سرد که همیشه یه نورِ کمرنگ داره.", "slot": "ring"},
                {"name": "طلسمِ صورتِ فلکی", "emoji": "🔮", "desc": "نقشه‌ی یه صورتِ فلکیِ فراموش‌شده روش حک شده.", "slot": "amulet"},
            ],
        },
    ],
    "Frostheim": [
        {
            "id": "fh_stew", "name": "بوریک", "title": "🍲 دیگ‌بارِ گرم‌کننده",
            "emoji": "🍲", "kind": "street_food",
            "desc": "یه دیگِ بزرگ که هیچ‌وقت خاموش نمی‌شه؛ می‌گه راز، فلفلِ یخیه.",
            "greeting": ["«سردته؟ این خورش گرمت می‌کنه، تضمینی.»", "«بشین کنارِ آتیش، دیگ داره می‌جوشه.»"],
            "item_flavor": ["«بخور تا سرما یادت بره.»"],
            "farewell": ["«گرم بمون، اونجا سرده.»"],
        },
        {
            "id": "fh_furrier", "name": "سیگرید", "title": "🧣 خزفروشِ قلمرو",
            "emoji": "🧣", "kind": "tailor",
            "desc": "پوستینِ حیواناتِ یخی رو تبدیل به لباسی می‌کنه که می‌گه گرم‌تر از هر آتیشیه.",
            "greeting": ["«این لباسِ نازک اینجا به دردت نمی‌خوره. بیا نگاه کن.»", "«از گرگِ یخی گرفتم، بهترین کیفیت.»"],
            "item_flavor": ["«بپوش، همین الان گرمترش رو حس می‌کنی.»"],
            "farewell": ["«یخ رو دستِ‌کم نگیر.»"],
            "templates": [
                {"name": "پوستینِ گرگِ یخی", "emoji": "🥋", "desc": "سنگین ولی هیچ سرمایی ازش رد نمی‌شه.", "slot": "armor"},
                {"name": "چکمه‌ی پنجه‌ی یخی", "emoji": "🥾", "desc": "رو یخ نمی‌لغزی، تضمینی.", "slot": "boots"},
            ],
        },
    ],
    "Voidbreak Wastes": [
        {
            "id": "vw_food", "name": "موجودِ بی‌نام", "title": "🍖 دکه‌ی غذای عجیب",
            "emoji": "🍖", "kind": "street_food",
            "desc": "شکلش رو نمی‌شه توصیف کرد؛ غذایی که می‌فروشه هم همین‌طور. عجیب اینه که کار می‌کنه.",
            "greeting": ["«...گشنه‌... ای؟»", "«این‌جا هیچ‌چی طبیعی نیست. غذا هم همین‌طور. بخور یا نخور.»"],
            "item_flavor": ["«...نوش... جان.»"],
            "farewell": ["«...برو... پیش از اینکه... یادت بره چرا اومدی.»"],
        },
        {
            "id": "vw_smith", "name": "آهنگرِ خلأ", "title": "⚒️ آهنگریِ فلزاتِ پوچی",
            "emoji": "⚒️", "kind": "smith",
            "desc": "با فلزی کار می‌کنه که هیچ‌جای دیگه‌ی این دنیا پیدا نمی‌شه — می‌گه از خودِ خلأ استخراجش کرده.",
            "greeting": ["«این فلز از هیچی ساخته شده. عجیبه که هنوز کار می‌کنه.»", "«هرچی بسازم، یه چیزی ازش گم می‌شه. عادت کن.»"],
            "item_flavor": ["«بگیرش، پیش از اینکه پشیمون بشم.»"],
            "farewell": ["«این‌جا نمون زیاد.»"],
            "templates": [
                {"name": "تیغه‌ی پوچی", "emoji": "🗡️", "desc": "لبه‌ای که انگار نور رو هم می‌بره.", "slot": "weapon"},
                {"name": "کلاهخودِ خلأ", "emoji": "⛑️", "desc": "از داخلش هیچ صدایی به بیرون نمی‌ره.", "slot": "helmet"},
            ],
        },
    ],
    "Azure Tides Empire": [
        {
            "id": "ate_seafood", "name": "کاپیتان مارلو", "title": "🐟 بازارِ ماهی و میوه‌ی دریایی",
            "emoji": "🐟", "kind": "produce",
            "desc": "صبح‌به‌صبح تازه‌ترین صیدِ روز رو میاره، کنارِ میوه‌های جزیره‌ای که فقط اینجا پیدا می‌شن.",
            "greeting": ["«صیدِ امروز عالیه! بیا نگاه کن.»", "«تازه از آب، هنوز بویِ دریا می‌ده.»"],
            "item_flavor": ["«نوش‌جان، دریانورد.»"],
            "farewell": ["«باد موافق!»"],
        },
        {
            "id": "ate_tailor", "name": "لیرا", "title": "🪢 خیاطیِ پارچه‌های آبی",
            "emoji": "🪢", "kind": "tailor",
            "desc": "پارچه‌هایی می‌بافه از ابریشمِ دریایی که آب رو دفع می‌کنه.",
            "greeting": ["«این پارچه هیچ‌وقت خیس نمی‌مونه. امتحانش کن.»", "«از عمقِ آبی‌ترین نقطه‌ی امپراتوری بافته شده.»"],
            "item_flavor": ["«بپوش، سبک‌تر از چیزی که فکر می‌کنی.»"],
            "farewell": ["«موج‌ها هوات رو دارن.»"],
            "templates": [
                {"name": "زرهِ موجِ آبی", "emoji": "🛡️", "desc": "زرهی سبک که رنگش با نورِ آب عوض می‌شه.", "slot": "armor"},
                {"name": "دستکشِ ابریشمِ دریایی", "emoji": "🧤", "desc": "لغزنده مثلِ آب، ولی محکم.", "slot": "gloves"},
            ],
        },
    ],
    "Stormward Archipelago": [
        {
            "id": "sa_tavern", "name": "میخانه‌ی لنگرِ شکسته", "title": "🍺 میخانه‌ی دزدانِ دریایی",
            "emoji": "🍺", "kind": "drinks",
            "desc": "پُر از دودِ پیپ و صدای خنده‌ی خشن؛ نوشیدنی‌هایی که می‌گن قبل از طوفان قوت می‌دن.",
            "greeting": ["«هوی! بیا تو، طوفون بیرون بی‌رحمه!»", "«یه گیلاس بردار، پیش از اینکه دریا صدات کنه.»"],
            "item_flavor": ["«به سلامتیِ بازمونده‌ها!»"],
            "farewell": ["«مراقبِ طوفون باش، دریانورد.»"],
        },
        {
            "id": "sa_smith", "name": "کارگاهِ لنگرسازها", "title": "⚓ آهنگریِ سلاح‌های دریایی",
            "emoji": "⚓", "kind": "smith",
            "desc": "چنگک، شمشیر و سلاح‌های ضدِ زنگ می‌سازن که سال‌ها زیرِ آبِ شور دووم میارن.",
            "greeting": ["«یه سلاحِ واقعی می‌خوای، نه؟ اومدی جای درست.»", "«فلزِ اینجا هیچ‌وقت زنگ نمی‌زنه.»"],
            "item_flavor": ["«باهاش خوب بجنگ.»"],
            "farewell": ["«لنگر بنداز، بعداً بازم بیا.»"],
            "templates": [
                {"name": "چنگکِ ناخدا", "emoji": "🪝", "desc": "هم سلاحه، هم ابزارِ بالا رفتن از عرشه.", "slot": "weapon"},
                {"name": "کلاهِ ناخداییِ فرسوده", "emoji": "🎩", "desc": "چندین طوفون رو زنده مونده.", "slot": "helmet"},
            ],
        },
    ],
    "The Sunken City": [
        {
            "id": "sc_pearls", "name": "نریسا", "title": "🦪 بازارِ صدف و مروارید",
            "emoji": "🦪", "kind": "curiosities",
            "desc": "صدف‌های نورانی و مرواریدهایی می‌فروشه که می‌گه از عمقی که آفتاب نمی‌رسه اومدن.",
            "greeting": ["«این‌ها رو از جایی آوردم که نور دیگه معنی نداره.»", "«هر مروارید یه راز نگه داشته.»"],
            "item_flavor": ["«ازش خوب مراقبت کن، کمیابه.»"],
            "farewell": ["«آب مسیرتو یادش می‌مونه.»"],
            "templates": [
                {"name": "گردنبندِ مروارید تاریک", "emoji": "📿", "desc": "مرواریدی که هیچ نوری روش نمی‌تابه.", "slot": "amulet"},
                {"name": "حلقه‌ی صدفِ غرق‌شده", "emoji": "💍", "desc": "هنوز بویِ اعماق می‌ده.", "slot": "ring"},
            ],
        },
        {
            "id": "sc_food", "name": "کلبه‌ی حبابِ هوا", "title": "🫧 دکه‌ی غذای اعماق",
            "emoji": "🫧", "kind": "street_food",
            "desc": "غذاهایی داخلِ حباب‌های هوایی سرو می‌کنه؛ نپرس چطوری هنوز گرمه زیرِ این‌همه آب.",
            "greeting": ["«نفست رو نگه‌دار، بعد بخور — هرچند شاید بشه هم‌زمان.»", "«این‌جا حتی غذا هم شناوره.»"],
            "item_flavor": ["«نوش جان، مهمونِ بالایی.»"],
            "farewell": ["«برگرد به سطح، سالم.»"],
        },
    ],
    "Verdant Vale": [
        {
            "id": "vv_fruit", "name": "میلا", "title": "🍇 میوه‌فروشیِ جنگل",
            "emoji": "🍇", "kind": "produce",
            "desc": "سبدهایی از میوه‌های وحشیِ جنگل که فقط زیرِ نورِ خاصی می‌رسن.",
            "greeting": ["«جنگل امسال سخاوتمند بود. بچش!»", "«این‌ها رو خودِ درخت‌ها بهم دادن، تقریباً.»"],
            "item_flavor": ["«نوش‌جان، فرزندِ جنگل.»"],
            "farewell": ["«جنگل بدرقه‌ت می‌کنه.»"],
        },
        {
            "id": "vv_herbs", "name": "کوهزادِ پیر", "title": "🌾 دکه‌ی معجونِ گیاهی",
            "emoji": "🌾", "kind": "drinks",
            "desc": "معجون‌هایی از گیاهانِ جنگلِ ارواح می‌سازه که می‌گه هرکدوم یه اثرِ متفاوت داره.",
            "greeting": ["«این معجون امروز تازه‌ست، هنوز داره می‌جوشه.»", "«جنگل هرچی لازم داشته باشی بهت می‌ده، اگه بلد باشی بگیری.»"],
            "item_flavor": ["«بنوش آروم، اثرش قویه.»"],
            "farewell": ["«برگ‌ها رد پاتو یادشون می‌مونه.»"],
        },
    ],
    "Emberhollow": [
        {
            "id": "eh_grill", "name": "دورگ", "title": "🔥 کبابیِ آتشین",
            "emoji": "🔥", "kind": "street_food",
            "desc": "روی سنگ‌های مذاب کباب می‌کنه؛ می‌گه هرچی تندتر، بهتر.",
            "greeting": ["«این‌جا همه‌چی داغه، غذام هم همین‌طور!»", "«اگه اشکت درنیومد، یعنی کم خوردی.»"],
            "item_flavor": ["«بخور، مردِ آتشین!»"],
            "farewell": ["«مراقبِ گدازه‌ها باش!»"],
        },
        {
            "id": "eh_smith", "name": "کارگاهِ گدازه", "title": "⚒️ آهنگریِ مذاب",
            "emoji": "⚒️", "kind": "smith",
            "desc": "مستقیم از رودخانه‌ی گدازه فلز می‌گیره؛ سلاح‌هاش هیچ‌وقت سرد نمی‌شن، انگار.",
            "greeting": ["«این فلز رو مستقیم از دلِ آتشفشون کشیدم بیرون.»", "«دستت رو نزدیک نبر، هنوز داغه.»"],
            "item_flavor": ["«باهاش بجنگ، تا وقتی سرد بشه ازش استفاده کن!»"],
            "farewell": ["«شعله‌ها همرات.»"],
            "templates": [
                {"name": "تبرِ زبانه‌ی آتش", "emoji": "🪓", "desc": "لبه‌اش هیچ‌وقت واقعاً سرد نمی‌شه.", "slot": "weapon"},
                {"name": "زرهِ گدازه‌ای", "emoji": "🛡️", "desc": "ترک‌های نارنجی روش هنوز می‌درخشن.", "slot": "armor"},
            ],
        },
    ],
    "Dragonnest Peaks": [
        {
            "id": "dp_eggs", "name": "بازارِ لانه‌داران", "title": "🥚 بازارِ محصولاتِ اژدها",
            "emoji": "🥚", "kind": "curiosities",
            "desc": "پوسته‌ی تخمِ اژدهای شکسته و فلس‌های ریخته‌شده رو می‌فروشن — با احتیاطِ زیاد.",
            "greeting": ["«این‌ها رو خودِ اژدهاها نگفتن ما برداریم، ولی زمین افتاده بودن، حساب نمی‌شه.»", "«دست نزن به اونی که هنوز گرمه!»"],
            "item_flavor": ["«ازش استفاده کن، پیش از اینکه صاحبِ اصلیش بفهمه.»"],
            "farewell": ["«برو پایین، آروم. اژدهاها صدا رو دوست ندارن.»"],
            "templates": [
                {"name": "حلقه‌ی فلسِ اژدها", "emoji": "💍", "desc": "هنوز کمی گرمه، انگار زنده‌ست.", "slot": "ring"},
                {"name": "تعویذِ پوسته‌ی تخم", "emoji": "🔮", "desc": "یه ترکِ کوچیک روش هست که هیچ‌وقت بزرگ‌تر نمی‌شه.", "slot": "amulet"},
            ],
        },
        {
            "id": "dp_tailor", "name": "کارگاهِ پوست‌کِشان", "title": "🧵 خیاطیِ پوستِ اژدها",
            "emoji": "🧵", "kind": "tailor",
            "desc": "فقط با پوستِ ریخته‌شده‌ی اژدهاها کار می‌کنه — می‌گه هیچ‌وقت به یه اژدهای زنده نزدیک نشده.",
            "greeting": ["«این پوست خودش ریخته بود، قسم می‌خورم.»", "«محکم‌ترین چیزیه که تا حالا دوختم.»"],
            "item_flavor": ["«بپوشش با احترام. یه اژدها این رو داشته.»"],
            "farewell": ["«پروازِ خوبی داشته باشی، دوپا.»"],
            "templates": [
                {"name": "زرهِ پوستِ اژدها", "emoji": "🛡️", "desc": "سبک‌تر از چیزی که به‌نظر می‌رسه، سخت‌تر از فولاد.", "slot": "armor"},
                {"name": "چکمه‌ی پنجه‌ی اژدهایی", "emoji": "🥾", "desc": "ردِ پنجه هنوز روش دیده می‌شه.", "slot": "boots"},
            ],
        },
    ],
    "Ruins of Orion-7": [
        {
            "id": "o7_auto", "name": "واحدِ سرو-۴۴", "title": "🍱 دستگاهِ خودکارِ غذا",
            "emoji": "🍱", "kind": "street_food",
            "desc": "یه ربات با بازوهای دقیق، غذا رو طبقِ فرمولی می‌سازه که دیگه هیچ‌کس یادش نیست چرا نوشته شده.",
            "greeting": ["«[سلام. وعده‌ی غذایی بر اساسِ آخرین فرمولِ ثبت‌شده آماده می‌شود.]»", "«[هشدار: طعم ممکن است بهینه نباشد. کیفیت تضمین می‌شود.]»"],
            "item_flavor": ["«[وعده تحویل داده شد. نوش جان.]»"],
            "farewell": ["«[جلسه پایان یافت.]»"],
        },
        {
            "id": "o7_parts", "name": "بازارِ خرده‌فروشانِ مکانیکی", "title": "🔩 بازارِ قطعاتِ یدکی",
            "emoji": "🔩", "kind": "curiosities",
            "desc": "قطعاتِ فلزیِ عجیبی می‌فروشن که از عمقِ خرابه‌های اوریون-۷ بیرون کشیدن.",
            "greeting": ["«[قطعاتِ ردیف‌شده. عملکردِ کامل تضمین نمی‌شود.]»", "«این‌ها هنوز کار می‌کنن. عجیبه، ولی می‌کنن.»"],
            "item_flavor": ["«[انتقالِ مالکیت انجام شد.]»"],
            "farewell": ["«[ارتباط قطع می‌شود.]»"],
            "templates": [
                {"name": "حلقه‌ی مدارِ باستانی", "emoji": "💍", "desc": "هنوز یه چراغِ کوچیک روش چشمک می‌زنه.", "slot": "ring"},
                {"name": "دستکشِ سرووموتور", "emoji": "🧤", "desc": "دستِ فلزی که کمی خودش حرکت می‌کنه.", "slot": "gloves"},
            ],
        },
    ],
    "Dreadgate Citadel": [
        {
            "id": "dc_food", "name": "آشپزِ بی‌نفس", "title": "🍷 دکه‌ی غذای ارواح",
            "emoji": "🍷", "kind": "street_food",
            "desc": "غذایی سرو می‌کنه که نه گرمه نه سرد؛ خودش می‌گه دیگه یادش نیست طعم چیه.",
            "greeting": ["«...بازم یه نفسِ گرم. بشین.»", "«اینجا کسی گشنه نمی‌مونه. فقط... زنده نمی‌مونه لزوماً.»"],
            "item_flavor": ["«نوش جان، مهمانِ زنده.»"],
            "farewell": ["«برو، پیش از اینکه فراموش کنی راه برگشت رو.»"],
        },
        {
            "id": "dc_smith", "name": "استخوان‌سازِ دژ", "title": "⚰️ آهنگریِ استخوان",
            "emoji": "⚰️", "kind": "smith",
            "desc": "سلاح‌هایی می‌سازه از استخوانی که می‌گه هرگز نمی‌شکنه — چون یه‌بار شکسته.",
            "greeting": ["«این استخوان‌ها یه‌بار جنگیدن. حالا دوباره می‌جنگن، باهات.»", "«صدای زنجیر اذیتت نکنه، کارم اینه.»"],
            "item_flavor": ["«ازش خوب استفاده کن. سزاوارِ یه زندگیِ دیگه‌ست.»"],
            "farewell": ["«زنجیرها بازت می‌ذارن — این‌بار.»"],
            "templates": [
                {"name": "تیغه‌ی استخوانِ سرکش", "emoji": "🗡️", "desc": "یه صدای خفیفِ جیغ موقعِ برخورد می‌ده.", "slot": "weapon"},
                {"name": "کلاهخودِ جمجمه‌ی فراموشی", "emoji": "💀", "desc": "چشماش خالیه، ولی حس می‌کنی نگاهت می‌کنه.", "slot": "helmet"},
            ],
        },
    ],
    "Clockwork Depths": [
        {
            "id": "cd_tea", "name": "دستگاهِ دم‌کنِ بخاری", "title": "☕ دکه‌ی چایِ بخاری",
            "emoji": "☕", "kind": "drinks",
            "desc": "با فشارِ بخار، در عرضِ چند ثانیه چای دم می‌کنه — دقیق، سریع، بدونِ خطا.",
            "greeting": ["«*فش!* چای آماده است. دمای بهینه: تضمین‌شده.»", "«یه فنجونِ دقیق، هر بار. این تفاوتِ ماست.»"],
            "item_flavor": ["«نوش جان. کارآیی: ۱۰۰٪.»"],
            "farewell": ["«*تیک-تاک.* بازگردید.»"],
        },
        {
            "id": "cd_tailor", "name": "کارگاهِ لباسِ کارآکوری", "title": "🧵 خیاطیِ چرخ‌دنده‌ای",
            "emoji": "🧵", "kind": "tailor",
            "desc": "لباس‌هایی می‌دوزه با چرخ‌دنده‌های کوچیکِ تزئینی که واقعاً می‌چرخن.",
            "greeting": ["«هر بخیه با دقتِ یه چرخ‌دنده زده شده.»", "«اندازه‌ت رو با دقتِ میلی‌متری می‌گیرم.»"],
            "item_flavor": ["«بپوش، ببین چقدر دقیقه.»"],
            "farewell": ["«*تیک-تاک.* سفرِ امن.»"],
            "templates": [
                {"name": "زرهِ چرخ‌دنده‌ای", "emoji": "🛡️", "desc": "چرخ‌دنده‌های کوچیکش موقعِ حرکت واقعاً می‌چرخن.", "slot": "armor"},
                {"name": "دستکشِ فنری", "emoji": "🧤", "desc": "با هر مشت یه صدای فنر می‌شنوی.", "slot": "gloves"},
            ],
        },
    ],
    "Throne of Oblivion": [
        {
            "id": "to_curios", "name": "آخرین دکه‌ی خاکستر", "title": "⚱️ دستفروشِ یادگارهای شاهی",
            "emoji": "⚱️", "kind": "curiosities",
            "desc": "یادگارهایی از تاجی که دیگه وجود نداره می‌فروشه — قیمتش بالاست، ولی چیزی که می‌ده، نایابه.",
            "greeting": ["«تا اینجا رسیدی. یعنی ارزششو داری که ببینی چی دارم.»", "«این‌ها آخرین یادگارهای تاجن. بعدِ این، دیگه چیزی نمونده.»"],
            "item_flavor": ["«بگیرش. سنگین‌تر از چیزیه که به‌نظر می‌رسه.»"],
            "farewell": ["«این تخت هنوز منتظرِ صاحبِ واقعیشه.»"],
            "templates": [
                {"name": "خاکسترِ تاجِ فراموشی", "emoji": "🔮", "desc": "یه مشت خاکستر که هنوز شکلِ تاج رو نگه داشته.", "slot": "relic"},
                {"name": "حلقه‌ی آخرین وارث", "emoji": "💍", "desc": "کسی که این رو داشت، دیگه اسمش یادِ کسی نیست.", "slot": "ring"},
            ],
        },
    ],
}


# ============================================================
#  توابعِ اصلی
# ============================================================
def get_stalls(map_name: str) -> list[dict]:
    return CITY_MARKETS.get(map_name, [])


def get_stall(stall_id: str) -> dict | None:
    for stalls in CITY_MARKETS.values():
        for s in stalls:
            if s["id"] == stall_id:
                return s
    return None


def _pick(pool: list[str]) -> str:
    return random.choice(pool) if pool else ""


def greeting_line(stall: dict) -> str:
    return _pick(stall.get("greeting", []))


def flavor_line(stall: dict) -> str:
    return _pick(stall.get("item_flavor", []))


def farewell_line(stall: dict) -> str:
    return _pick(stall.get("farewell", []))


def _map_tier_of(map_name: str) -> str:
    try:
        from economy import MAPS_DATA
        return MAPS_DATA.get(map_name, {}).get("tier", "common")
    except Exception:
        return "common"


def _rng_for(stall_id: str, salt: float) -> random.Random:
    return random.Random(f"{stall_id}:{int(salt)}")


def _gen_gear_row(stall: dict, map_name: str, rng: random.Random) -> dict:
    import item_system as isy
    template = dict(rng.choice(stall["templates"]))
    map_tier = _map_tier_of(map_name)
    rarities = RARITY_POOL_BY_MAP_TIER.get(map_tier, ["common", "uncommon"])
    forced = rng.choice(rarities)
    item = isy.generate_item(template, 30, forced_rarity=forced, drop_source=f"citymarket:{stall['id']}")
    price = int(item.get("sell", 100) * KIND_PRICE_MULT.get(stall["kind"], 2.5))
    return {"item": item, "price": price}


def _gen_consumable_row(stall: dict, rng: random.Random) -> dict:
    from item_system import generate_consumable
    item = generate_consumable(player_level=rng.randint(10, 40))
    price = max(15, int(item.get("sell", 25) * KIND_PRICE_MULT.get(stall["kind"], 1.8)))
    return {"item": item, "price": price}


def _gen_special_row(stall: dict, map_name: str, rng: random.Random) -> dict:
    """یه ردیفِ ✨ ویژه — با رریتیِ بالاترینِ ممکن برای tier نقشه، همیشه ۱ عدد."""
    map_tier = _map_tier_of(map_name)
    rarity_pool = RARITY_POOL_BY_MAP_TIER.get(map_tier, ["rare"])
    forced = rarity_pool[-1]

    if stall.get("templates"):
        import item_system as isy
        template = dict(rng.choice(stall["templates"]))
        item = isy.generate_item(template, 30, forced_rarity=forced, drop_source=f"citymarket_special:{stall['id']}")
    else:
        from item_system import generate_consumable
        item = generate_consumable(player_level=rng.randint(35, 50))

    price = int(item.get("sell", 150) * KIND_PRICE_MULT.get(stall["kind"], 2.5) * SPECIAL_PRICE_MULT)
    return {"item": item, "price": price}


def _gen_stock(stall: dict, map_name: str, seed_t: float) -> list[dict]:
    rng = _rng_for(stall["id"], seed_t)
    n = rng.randint(*STOCK_SIZE_RANGE)
    rows = []
    for _ in range(n):
        if stall["kind"] in ("tailor", "smith", "curiosities") and stall.get("templates"):
            row = _gen_gear_row(stall, map_name, rng)
        else:
            row = _gen_consumable_row(stall, rng)
        rows.append({
            "row_id": uuid.uuid4().hex[:8],
            "item": row["item"],
            "price": row["price"],
            "qty_total": rng.randint(*STOCK_QTY_RANGE),
            "qty_left": None,
            "special": False,
        })

    if rng.random() < SPECIAL_ROW_CHANCE:
        srow = _gen_special_row(stall, map_name, rng)
        rows.append({
            "row_id": uuid.uuid4().hex[:8],
            "item": srow["item"],
            "price": srow["price"],
            "qty_total": 1,
            "qty_left": None,
            "special": True,
        })

    for row in rows:
        row["qty_left"] = row["qty_total"]
    return rows


def get_stock(stall_id: str, map_name: str) -> dict:
    """موجودیِ زنده‌ی این غرفه رو برمی‌گردونه؛ اگه منقضی/خالی از قبل
    نبوده، یه چرخه‌ی تازه می‌سازه. سندِ برگشتی مشترکِ بینِ همه‌ی
    بازیکن‌هاست."""
    from database import city_market_col
    col = city_market_col()
    now = time.time()
    doc = col.find_one({"_id": stall_id})
    if not doc or doc.get("expires_at", 0) <= now:
        stall = get_stall(stall_id)
        stock = _gen_stock(stall, map_name, now) if stall else []
        doc = {
            "_id": stall_id,
            "map_name": map_name,
            "spawned_at": now,
            "expires_at": now + REFRESH_INTERVAL,
            "stock": stock,
        }
        col.replace_one({"_id": stall_id}, doc, upsert=True)
    return doc


def buy_row(stall_id: str, map_name: str, row_id: str) -> dict | None:
    """یه واحد از یه ردیف رو مصرف می‌کنه (qty_left--). اگه موفق بود
    یه کپیِ تازه از آیتم برمی‌گردونه که caller باید به inventory
    بازیکن اضافه کنه. اگه دیگه موجودی نمونده یا ردیف پیدا نشه، None."""
    from database import city_market_col
    doc = get_stock(stall_id, map_name)
    col = city_market_col()
    for row in doc.get("stock", []):
        if row["row_id"] == row_id:
            if row["qty_left"] <= 0:
                return None
            row["qty_left"] -= 1
            col.update_one({"_id": stall_id}, {"$set": {"stock": doc["stock"]}})
            return {"item": dict(row["item"]), "price": row["price"]}
    return None


# ============================================================
#  🎖️ اعتبارِ فروشنده — تخفیفِ شخصی بر اساسِ تاریخچه‌ی خریدِ بازیکن
# ============================================================
def _rep_map(player: dict) -> dict:
    return player.setdefault("vendor_rep", {})


def get_vendor_rep(player: dict, stall_id: str) -> dict:
    m = _rep_map(player)
    entry = m.get(stall_id)
    if not entry:
        entry = {"purchases": 0, "spent": 0, "last_haggle_attempt": 0}
        m[stall_id] = entry
    return entry


def vendor_rep_tier(purchases: int) -> str:
    tier = "newcomer"
    for t, threshold in VENDOR_REP_THRESHOLD.items():
        if purchases >= threshold:
            tier = t
    return tier


def vendor_rep_label(tier: str) -> str:
    return VENDOR_REP_LABEL.get(tier, VENDOR_REP_LABEL["newcomer"])


def record_purchase(player: dict, stall_id: str, price: int) -> dict:
    """caller بعدِ خریدِ موفق این رو صدا بزنه تا اعتبارِ فروشنده آپدیت بشه."""
    entry = get_vendor_rep(player, stall_id)
    entry["purchases"] += 1
    entry["spent"] += price
    return entry


def _king_discount(player: dict, map_name: str) -> float:
    try:
        import map_kings as mk
        return mk.market_discount_mult(player, map_name)
    except Exception:
        return 0.0


def _haggle_discount(player: dict, stall_id: str) -> float:
    hg = player.get("market_haggle", {}).get(stall_id)
    if hg and hg.get("expires_at", 0) > time.time():
        return hg.get("discount", 0.0)
    return 0.0


def total_discount(player: dict, stall_id: str, map_name: str) -> float:
    """جمعِ همه‌ی تخفیف‌های این بازیکن رو این غرفه: اعتبارِ فروشنده +
    رابطه با پادشاهِ نقشه + چانه‌زنیِ موفقِ این چرخه (سقف: MAX_TOTAL_DISCOUNT)."""
    rep = get_vendor_rep(player, stall_id)
    tier = vendor_rep_tier(rep["purchases"])
    rep_disc = VENDOR_REP_DISCOUNT.get(tier, 0.0)
    king_disc = _king_discount(player, map_name)
    haggle_disc = _haggle_discount(player, stall_id)
    return min(MAX_TOTAL_DISCOUNT, rep_disc + king_disc + haggle_disc)


def discounted_price(player: dict, stall_id: str, map_name: str, base_price: int) -> int:
    disc = total_discount(player, stall_id, map_name)
    if disc <= 0:
        return base_price
    return max(1, int(round(base_price * (1 - disc))))


def try_haggle(player: dict, stall_id: str, map_name: str) -> dict:
    """یه‌بار تلاش برای چانه‌زنی در هر چرخه‌ی رفرش. موفقیت، یه تخفیفِ
    شخصیِ موقت (تا رفرشِ بعدی) رو این غرفه فعال می‌کنه."""
    stall = get_stall(stall_id)
    if not stall:
        return {"ok": False, "reason": "no_stall"}

    rep = get_vendor_rep(player, stall_id)
    now = time.time()
    if now - rep.get("last_haggle_attempt", 0) < HAGGLE_COOLDOWN:
        return {"ok": False, "reason": "cooldown", "stall": stall}

    rep["last_haggle_attempt"] = now
    tier = vendor_rep_tier(rep["purchases"])
    chance = HAGGLE_SUCCESS_BASE.get(tier, 0.35)
    success = random.random() < chance

    if success:
        hg_map = player.setdefault("market_haggle", {})
        hg_map[stall_id] = {"discount": HAGGLE_DISCOUNT, "expires_at": now + HAGGLE_COOLDOWN}

    return {"ok": True, "success": success, "chance": chance, "stall": stall, "tier": tier}
