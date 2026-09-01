# ============================================================
#  ASTRAL ABYSS — 👑 پادشاهانِ نقشه‌ها (Map Kings / City Rulers)
#  (map_kings.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  هر نقشه‌ی economy.MAPS_DATA یه حاکمِ ثابت و اسم‌دار داره — برخلافِ
#  تاجرانِ دوره‌گردِ road_merchants (که تصادفی و بی‌هویت‌ان)، پادشاهِ
#  هر نقشه همیشه همونیه؛ باهاش حرف زدن یه رابطه‌ی واقعی می‌سازه که
#  به‌مرور عمیق‌تر می‌شه (favor)، نه فقط یه خطِ فلیورِ یک‌بارمصرف.
#
#  یه بارِ آدیانس (audience) در روز واقعاً چیزی می‌ده (Zen + شانسِ
#  آیتمِ مصرفی)؛ بعدِ اون، همچنان می‌شه باهاش حرف زد ولی فقط فلیوره
#  (تا از فارم‌کردنِ رابطه جلوگیری بشه — هم‌راستا با anti_farm.py).
#
#  دیتای favor رو مستقیم رو خودِ player ذخیره می‌کنه:
#    player["king_favor"][map_name] = {"favor": int, "talks": int,
#                                       "last_audience": float}
#  فیلدِ جدیدی به هیچ سیستمِ دیگه‌ای اضافه/تغییر نمی‌ده. caller
#  (هندلرها) مسئولِ asave_player بعدِ صدا زدنِ hold_audience هست.
# ============================================================
from __future__ import annotations

import random
import time

AUDIENCE_COOLDOWN = 86400  # یه آدیانسِ «واقعی» (با هدیه) در روز

# ─── سطوحِ رابطه ────────────────────────────────────────────
TIER_ORDER = ["stranger", "acquainted", "respected", "trusted", "exalted"]
TIER_THRESHOLD = {"stranger": 0, "acquainted": 15, "respected": 35, "trusted": 60, "exalted": 100}
TIER_LABEL = {
    "stranger":   "🧍 غریبه",
    "acquainted": "🙂 آشنا",
    "respected":  "🤝 محترم",
    "trusted":    "🛡️ معتمد",
    "exalted":    "👑 هم‌پیمانِ تاج",
}
TIER_GIFT_MULT = {"stranger": 1.0, "acquainted": 1.15, "respected": 1.35, "trusted": 1.6, "exalted": 2.0}
TIER_ITEM_CHANCE = {"stranger": 0.0, "acquainted": 0.05, "respected": 0.12, "trusted": 0.20, "exalted": 0.32}
FAVOR_GAIN_RANGE = (2, 4)
FAVOR_CAP = 100

# پاداشِ پایه‌ی زن بر اساسِ tier نقشه (economy.MAPS_DATA[...]['tier'])
BASE_GIFT_BY_MAP_TIER = {"common": 120, "uncommon": 150, "rare": 180, "epic": 260, "legendary": 400}

# ─── 🎁 هدیه‌ی سلطنتیِ درجه‌بندی‌شده — شانسِ گیر بودنِ هدیه به‌جای مصرفی ──
# (بر اساسِ templateهای همون نقشه تو city_markets.py، تا هدیه‌ی پادشاه هم
#  حس‌وحالِ همون قلمرو رو داشته باشه)
ROYAL_GEAR_CHANCE = {"stranger": 0.0, "acquainted": 0.0, "respected": 0.25, "trusted": 0.45, "exalted": 0.65}
ROYAL_GEAR_RARITY_POOL = {"respected": ["rare"], "trusted": ["rare", "epic"], "exalted": ["epic", "mythic"]}

# ─── 🎉 لطفِ ویژه‌ی پادشاه — شانسِ کمِ دوبرابر شدنِ پاداشِ زن ──────────
ROYAL_BOON_CHANCE = 0.08

# ─── 🎁 پیشکش (Tribute) — خریدِ فعالانه‌ی اعتبار با Zen، با کاهشِ بازده ─
TRIBUTE_BASE = {"small": 500, "medium": 2000, "large": 8000}
TRIBUTE_FAVOR_BASE = {"small": 4, "medium": 10, "large": 22}
TRIBUTE_LABELS = {"small": "🥉 پیشکشِ کوچک", "medium": "🥈 پیشکشِ متوسط", "large": "🥇 پیشکشِ بزرگ"}

# ─── 🏮 تخفیفِ بازارِ محلی بر اساسِ رابطه با پادشاهِ همون نقشه ───────────
MARKET_DISCOUNT_BY_TIER = {"stranger": 0.0, "acquainted": 0.0, "respected": 0.05, "trusted": 0.10, "exalted": 0.15}


# ============================================================
#  👑 KINGS — یه حاکمِ ثابت برای هرکدوم از نقشه‌های economy.MAPS_DATA
# ============================================================
KINGS: dict[str, dict] = {
    "Abyssal Black Market": {
        "name": "لُردِ خاموش، وِسپار",
        "title": "🖤 شاهِ سایه‌ها",
        "emoji": "🖤",
        "domain": "هیچ تاجی رو سرش نمی‌ذاره، ولی هرکی تو بازارِ سیاه معامله می‌کنه، زیرِ سایه‌ی اونه.",
        "greetings": [
            "«یه بازیکنِ جدید. یا یه جاسوس؟ فرقی نمی‌کنه، تا وقتی که پولت خوب باشه.»",
            "«اینجا هیچ‌کس اسمِ واقعیشو نمی‌گه. تو هم لازم نیست بگی.»",
            "«بازار همیشه بیدارِه. منم همین‌طور.»",
            "«هرچی می‌خوای بشنوی رو نمی‌شنوی؛ فقط چیزی که ارزششو داره.»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز نمی‌دونم باید بهت اعتماد کنم یا نه.»",
            "acquainted": "«چهره‌ت داره برام آشنا می‌شه. این تو بازار یه چیزیه.»",
            "respected":  "«حرفت تو این محله وزن داره، حالا.»",
            "trusted":    "«از معدود کسایی هستی که بهشون یه چیزی بیشتر از پول می‌گم.»",
            "exalted":    "«تو دیگه بخشی از سایه‌ای. خوش‌اومدی، واقعاً.»",
        },
        "lore": [
            "«این بازار قبل از اینکه Abyss قلمروها رو بشکافه هم بود — فقط زیرِ زمینی‌تر.»",
            "«هرچی که یه پادشاهِ دیگه ممنوعش کنه، آخرش سر از پیشخوانِ من درمیاره.»",
            "«می‌گن من هیچ‌وقت نمی‌میرم، فقط جامو با یکی دیگه عوض می‌کنم. شایعه‌ی بدی نیست.»",
        ],
        "farewell": ["«برو. و یادت باشه، اینجا هیچی رایگون نیست — حتی این گفتگو.»", "«بازار منتظرته. همیشه.»"],
    },
    "Sands of Eternity": {
        "name": "فرعونِ آخر، رامسیرا",
        "title": "🏺 فرعونِ شن‌های ابدی",
        "emoji": "🏺",
        "domain": "قرن‌هاست زیرِ یه معبدِ نیمه‌مدفون حکومت می‌کنه؛ می‌گه شن‌ها هیچ‌وقت واقعاً چیزی رو دفن نمی‌کنن.",
        "greetings": [
            "«یه سالک از دنیای بالا. بشین، شن خسته‌ت کرده.»",
            "«هر مسافری که تا اینجا برسه، یا شجاعه یا گمشده.»",
            "«صحرا صداشو بهم می‌رسونه، حتی صدای قدم‌های تو رو.»",
        ],
        "tier_lines": {
            "stranger":   "«اسمت رو تو کتابِ زائرین ثبت نکردم — هنوز.»",
            "acquainted": "«شن‌ها اسمتو یاد گرفتن. من هم.»",
            "respected":  "«معبد برات یه راه باز می‌کنه، سالک.»",
            "trusted":    "«تو رو در کنارِ محافظانِ ابدی می‌شمرم.»",
            "exalted":    "«تاجم سبک‌تره وقتی می‌دونم یکی مثلِ تو هست.»",
        },
        "lore": [
            "«قبل از Sundering، این صحرا یه دشتِ سبز بود. من دیدمش. هیچ‌کس دیگه باور نمی‌کنه.»",
            "«زیرِ این معبد یه چیزی خوابیده که حتی خودِ من هم بیدارش نمی‌کنم.»",
            "«هر فرعونی قبل از من مُرد. من فقط... نمُردم. هنوز نفهمیدم چرا.»",
        ],
        "farewell": ["«شن‌ها راهتو یادشون می‌مونه. برگرد.»", "«باد ازت مراقبت کنه، سالک.»"],
    },
    "Holy Luminarchy": {
        "name": "اسقفِ اعظم، سلستین",
        "title": "✨ نگهبانِ نور",
        "emoji": "✨",
        "domain": "خودشو پادشاه نمی‌دونه، فقط «خدمتکارِ نور» — ولی هیچ تصمیمی تو این پایتخت بدونِ تاییدِ اون گرفته نمی‌شه.",
        "greetings": [
            "«نور بهت خوش‌آمد می‌گه، سالک. من فقط پیام‌رسانشم.»",
            "«هر روحی که به اینجا برسه، یه دلیل داره. دلیلِ تو چیه؟»",
            "«بیا نزدیک. زیرِ این گنبد، همه باهم برابرن.»",
        ],
        "tier_lines": {
            "stranger":   "«نورت هنوز کم‌رنگه، ولی خاموش نیست.»",
            "acquainted": "«حس می‌کنم نورت داره روشن‌تر می‌شه.»",
            "respected":  "«کلیسا دعا برات می‌کنه، هر شب.»",
            "trusted":    "«تو رو یکی از محافظانِ حقیقیِ این پایتخت می‌دونم.»",
            "exalted":    "«نور از طریقِ تو هم می‌تابه، حالا. همیشه همین‌طور بمون.»",
        },
        "lore": [
            "«قبل از Sundering، من فقط یه راهبِ کوچیک بودم. حالا... نگهبانِ آخرین نورم.»",
            "«می‌گن نور می‌تونه Abyss رو بسوزونه. من هنوز باور دارم، حتی وقتی شکست می‌خورم.»",
            "«هر شب یه دعا برای کسایی که تو Abyss گم شدن می‌خونم. اسمِ همه‌شون رو یادمه.»",
        ],
        "farewell": ["«نور همراهت باشه.»", "«هروقت خواستی، درهای این پایتخت به روت بازه.»"],
    },
    "Celestial Spire": {
        "name": "منجم‌شاه، اوریناس",
        "title": "🔭 حاکمِ برجِ آسمانی",
        "emoji": "🌟",
        "domain": "بیشترِ وقتش رو صرفِ رصدِ ستاره‌هایی می‌کنه که می‌گه دارن آروم‌آروم جاشون رو عوض می‌کنن.",
        "greetings": [
            "«بالا بیا. اینجا از هرجای دیگه‌ای به آسمون نزدیک‌تری.»",
            "«ستاره‌ها امشب بی‌قرارن. شاید به‌خاطرِ اومدنِ تو.»",
            "«هر بازدیدکننده یه سوال داره. سوالِ تو چیه؟»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز جایگاهت رو تو نقشه‌ی ستاره‌ها پیدا نکردم.»",
            "acquainted": "«یه ستاره‌ی کوچیکِ جدید تو نقشه‌م هست — فکر کنم اسمش تویی.»",
            "respected":  "«مسیرت رو دارم دنبال می‌کنم، دقیق‌تر از قبل.»",
            "trusted":    "«تو یکی از معدود کسایی هستی که بهش نقشه‌های واقعی نشون می‌دم.»",
            "exalted":    "«ستاره‌ت حالا بخشی از صورت‌فلکیِ برجه. جاودانه شدی، به‌نوعی.»",
        },
        "lore": [
            "«یه شکافِ کوچیک تو آسمون هست که فقط من می‌بینمش. داره بزرگ‌تر می‌شه.»",
            "«قبل از Sundering، ستاره‌ها یه نقشه بودن. حالا فقط یه هشدارن.»",
            "«اگه یه روز نور بالای برج خاموش شد، یعنی من دیگه چیزی برای دیدن پیدا نکردم.»",
        ],
        "farewell": ["«آسمون رو یادت نره، حتی وقتی رو زمینی.»", "«ستاره‌ت رو دنبال می‌کنم.»"],
    },
    "Frostheim": {
        "name": "ملکه‌ی یخ، وینترا",
        "title": "❄️ حاکمِ قلمروی یخ",
        "emoji": "❄️",
        "domain": "با آرامشِ سردی حکومت می‌کنه که خیلیا اشتباه با بی‌رحمی می‌گیرن.",
        "greetings": [
            "«سرما بهت خوش‌آمد نمی‌گه. من می‌گم — فرقشون رو یاد بگیر.»",
            "«کم کسی زنده تا اینجا می‌رسه. تو یکیشی، ظاهراً.»",
            "«بشین، پیش از اینکه سرما تصمیمِ خودشو بگیره.»",
        ],
        "tier_lines": {
            "stranger":   "«یخ هنوز زیرِ پاهات نازکه.»",
            "acquainted": "«شاید... شاید بتونی دووم بیاری اینجا.»",
            "respected":  "«قلمروم بهت یه جایی داده، سالک.»",
            "trusted":    "«از معدود کسایی هستی که سرما رو نشکسته.»",
            "exalted":    "«تخت‌ام رو با کسی شریک نمی‌شم — ولی اعتمادم رو، با تو، شریک شدم.»",
        },
        "lore": [
            "«یه‌بار این قلمرو گرم بود. یه‌بار. قبل از اینکه بفهمم گرما چقدر آدم رو ضعیف می‌کنه.»",
            "«هر سال یه گروه از این یخ‌ها رد می‌شن و برنمی‌گردن. من دیگه اسمشون رو نمی‌پرسم.»",
            "«Voidbreak Wastes بهم نزدیک‌تره از چیزی که دوست دارم. حسش می‌کنم تو باد.»",
        ],
        "farewell": ["«سرما رو دستِ‌کم نگیر.»", "«برو، پیش از اینکه یخ عوض بشه.»"],
    },
    "Voidbreak Wastes": {
        "name": "وارلردِ خلأ، نکروث",
        "title": "🌑 اربابِ سرزمینِ پوچی",
        "emoji": "🌑",
        "domain": "دیگه مطمئن نیست هنوز زنده‌ست یا نه؛ فقط می‌دونه هنوز حکومت می‌کنه.",
        "greetings": [
            "«...یکی اومده. عجیبه. اینجا معمولاً هیچ‌کس نمی‌مونه.»",
            "«صدات رو می‌شنوم، ولی خلأ داره همزمان صدامو می‌بلعه. زود حرف بزن.»",
            "«اینجا هیچی واقعی نمی‌مونه زیاد. حتی من.»",
        ],
        "tier_lines": {
            "stranger":   "«یادم نمی‌مونه تو کی بودی. خلأ همه‌چی رو می‌بره.»",
            "acquainted": "«این‌بار... این‌بار یادم موند. عجیبه.»",
            "respected":  "«چیزی از تو تو ذهنم مونده، حتی وقتی خلأ می‌کشه.»",
            "trusted":    "«تو تنها چیزیه که خلأ نمی‌تونه ازم بگیره.»",
            "exalted":    "«تا وقتی که یادت هستم، هنوز کاملاً پوچ نشدم.»",
        },
        "lore": [
            "«قبل از این خلأ، یه اسمِ دیگه داشتم. یادم نمیاد چی بود.»",
            "«اینجا مرزِ Abyss‌ه. نه واقعاً توش، نه واقعاً بیرونش.»",
            "«هرچی بیشتر اینجا بمونی، کمتر خودتی. مراقب باش.»",
        ],
        "farewell": ["«برو، پیش از اینکه خلأ یادش بره تو کی بودی.»", "«...یکی اومده بود؟»"],
    },
    "Azure Tides Empire": {
        "name": "امپراتریسِ موج، تالاسیا",
        "title": "🌊 حاکمِ امپراتوریِ آبی",
        "emoji": "🌊",
        "domain": "امپراتوری‌ای که هیچ مرزِ ثابتی نداره؛ هرروز، دریا خودش مرز رو دوباره می‌کشه.",
        "greetings": [
            "«موج‌ها خبرِ اومدنت رو زودتر از خودت بهم رسوندن.»",
            "«دریا هیچ‌وقت آروم نمی‌مونه. بشین، تا اون آروم بشه.»",
            "«هر ملوانی که به بندرم برسه، مهمونِ منه.»",
        ],
        "tier_lines": {
            "stranger":   "«موج‌ها هنوز اسمتو نگفتن.»",
            "acquainted": "«دریا داره عادت می‌کنه به حضورت.»",
            "respected":  "«ناوگانم برات راه باز می‌کنه.»",
            "trusted":    "«اعتمادِ امپراتوری پشتِ سرته.»",
            "exalted":    "«تاجم روی موج شناوره — و تو، یکی از ستون‌های زیرِ آبیشی.»",
        },
        "lore": [
            "«این امپراتوری هر روز شکلش عوض می‌شه. یاد گرفتم که با آب بجنگم، نه در برابرش.»",
            "«یه شهر زیرِ این آب‌ها خوابیده — می‌گن مالِ قبل از Sundering‌ه.»",
            "«ماهیگیرام گاهی چیزایی از عمق میارن بالا که ترجیح می‌دم نبینم.»",
        ],
        "farewell": ["«موج‌ها هوات رو دارن.»", "«بادِ خوبی همراهت باشه، ملوان.»"],
    },
    "Stormward Archipelago": {
        "name": "ناخداشاه، کاسپیان",
        "title": "🏴‍☠️ فرمانروای طوفان",
        "emoji": "⛈️",
        "domain": "با یه رأی از بینِ دزدانِ دریایی به تاج رسید؛ می‌گه تنها قانونِ واقعیِ اینجا وفاداریه.",
        "greetings": [
            "«ها! یه چهره‌ی جدید تو جزیره‌م. خوش اومدی، اگه دروغ نگی.»",
            "«طوفان امشب آرومه. یعنی یه چیزی داره میاد.»",
            "«بشین، یه گیلاس بردار. اینجا رسمِ خوش‌آمدگوییه.»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز نمی‌دونم بهت اعتماد کنم یا نه پرتت کنم تو آب.»",
            "acquainted": "«خب، هنوز زنده‌ای. نشونه‌ی خوبیه.»",
            "respected":  "«خدمه‌م ازت به‌خوبی حرف می‌زنن.»",
            "trusted":    "«جات تو شورای کاپیتان‌ها محفوظه.»",
            "exalted":    "«اگه یه‌روز نبودم، این جزیره‌ها رو دستِ توام می‌سپارم.»",
        },
        "lore": [
            "«این طوفون‌ها طبیعی نیستن. یه‌جوری Abyss داره باهاشون نفس می‌کشه.»",
            "«قبلِ اینکه ناخداشاه بشم، ۷ کاپیتانِ دیگه رو تو یه دوئل باختم. اسمشون رو یادم نگه داشتم.»",
            "«زیرِ اقیانوسِ این جزایر، یه گنجینه‌ست که هیچ‌کس زنده برنگشته باهاش.»",
        ],
        "farewell": ["«باد موافق، دریانورد!»", "«اگه غرق شدی، اسممو داد بزن — شاید بشنوم.»"],
    },
    "The Sunken City": {
        "name": "ملکه‌ی غرق‌شده، مارینوث",
        "title": "🐚 حاکمِ شهرِ غرق‌شده",
        "emoji": "🐚",
        "domain": "شهرش قرن‌هاست زیرِ آبه؛ خودش می‌گه هنوز نفهمیده مرده یا فقط... خیس.",
        "greetings": [
            "«نفست رو نگه‌دار، مهمون. اینجا هوا یه‌جور دیگه‌ست.»",
            "«صدای قدم‌های تو رو از میونِ آب شنیدم.»",
            "«خیلی‌وقته کسی از بالا اینجا نیومده بود.»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز بویِ سطح رو می‌دی.»",
            "acquainted": "«این آب داره عادت می‌کنه به تو.»",
            "respected":  "«شهرم برات یه راهرو باز می‌کنه.»",
            "trusted":    "«حتی مرده‌های این شهر اسمتو می‌شناسن.»",
            "exalted":    "«تو، مثلِ من، حالا نه کاملاً بالایی، نه کاملاً اینجا. خوش‌اومدی.»",
        },
        "lore": [
            "«این شهر یه‌روز زیرِ آفتاب بود. یه شب، همه‌چی رفت زیرِ آب. من هم رفتم.»",
            "«هنوز صدای زنگ‌های کلیسای قدیمی رو می‌شنوم، از زیرِ گِل.»",
            "«Azure Tides بالای سرمه. گاهی حسودیم می‌شه به نورِ آفتابشون.»",
        ],
        "farewell": ["«برگرد به سطح، پیش از اینکه آب یادش بره تو کی بودی.»", "«آب مسیرت رو یادش می‌مونه.»"],
    },
    "Verdant Vale": {
        "name": "روح‌شاهِ جنگل، سیلوان",
        "title": "🌿 نگهبانِ جنگلِ ارواح",
        "emoji": "🌿",
        "domain": "بیشتر یه روحه تا یه پادشاه؛ درخت‌های جنگل به جاش صحبت می‌کنن.",
        "greetings": [
            "«جنگل بهت اجازه‌ی ورود داد. این خودش یه چیزیه.»",
            "«صدای برگ‌ها رو می‌شنوی؟ دارن درباره‌ت حرف می‌زنن.»",
            "«بشین رو ریشه‌ها. جنگل مهمون‌نوازه، اگه بهش احترام بذاری.»",
        ],
        "tier_lines": {
            "stranger":   "«درخت‌ها هنوز مطمئن نیستن بهت اعتماد کنن.»",
            "acquainted": "«یه شاخه برات خم شد. نشونه‌ی خوبیه.»",
            "respected":  "«جنگل صدای قدم‌هاتو می‌شناسه.»",
            "trusted":    "«ریشه‌های این جنگل تا زیرِ خونه‌ت هم می‌رسن، حالا.»",
            "exalted":    "«تو بخشی از این جنگلی، حالا. همیشه یه راه برای برگشتن داری.»",
        },
        "lore": [
            "«قبل از Sundering، این جنگل تا افق ادامه داشت. الان فقط یه بازمونده‌ست.»",
            "«هر درختِ اینجا یه روحه — یکیشون قبلاً پادشاهِ قبل از من بود.»",
            "«یه‌روز خودم هم یه درخت می‌شم. عجله‌ای ندارم.»",
        ],
        "farewell": ["«جنگل بدرقه‌ت می‌کنه.»", "«برگ‌ها رد پاتو یادشون می‌مونه.»"],
    },
    "Emberhollow": {
        "name": "لردِ آتش، ایگنوروس",
        "title": "🔥 حاکمِ دره‌ی آتش",
        "emoji": "🔥",
        "domain": "با خشمی که هیچ‌وقت کاملاً خاموش نمی‌شه حکومت می‌کنه — ولی وفاداری رو با همون شدت پاداش می‌ده.",
        "greetings": [
            "«گرمای اینجا اذیتت نمی‌کنه؟ خوبه. یعنی ضعیف نیستی.»",
            "«اومدی جلوی آتیشِ من بایستی. جسورانه‌ست، یا احمقانه.»",
            "«حرف بزن، پیش از اینکه صبرم مثلِ این دره بسوزه.»",
        ],
        "tier_lines": {
            "stranger":   "«شعله‌هام هنوز بهت اعتماد ندارن.»",
            "acquainted": "«یه‌جرقه از احترام روشن شد، سالک.»",
            "respected":  "«آتیشِ این دره برات نرم‌تره حالا.»",
            "trusted":    "«از معدود کسایی هستی که آتیشم رو ندید گرفت و نترسید.»",
            "exalted":    "«شعله‌های این دره حالا شعله‌های تو هم هستن.»",
        },
        "lore": [
            "«این دره قبلاً یه شهرِ زنده بود. آتیش، تنها چیزیه که ازش موند — و منم.»",
            "«خشمم دلیل داره. یه‌روز، شاید، برات تعریف کنم.»",
            "«Dragonnest Peaks بالای سرمه. اژدهاهاشون به آتیشِ من احترام می‌ذارن، حداقل.»",
        ],
        "farewell": ["«برو، پیش از اینکه گرما زیادی بشه.»", "«شعله‌هام یادت رو نگه می‌دارن.»"],
    },
    "Dragonnest Peaks": {
        "name": "اژدهاشاه، وایرموث",
        "title": "🐉 حاکمِ لانه‌ی اژدها",
        "emoji": "🐉",
        "domain": "قدیمی‌ترین حاکمِ زنده‌ی این نقشه‌ها؛ می‌گه پادشاه بودن یعنی زنده موندنِ بیشتر از همه.",
        "greetings": [
            "«یه موجودِ دوپا، اینقدر بالا اومده. جالبه.»",
            "«خیلی‌ها این قله‌ها رو نمی‌بینن. تو دیدی. حرفی داری؟»",
            "«صدات رو بشنوم، پیش از اینکه صبرم مثلِ نفسِ اژدها کوتاه بشه.»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز فقط یه سایه‌ی کوچیک زیرِ پرهامی.»",
            "acquainted": "«شاید ارزشِ نگاهِ دوباره رو داشته باشی.»",
            "respected":  "«قله‌ها اسمتو رو باد پخش می‌کنن.»",
            "trusted":    "«چند تا از اژدهاهام دیگه بهت حمله نمی‌کنن. این یعنی خیلی چیزا.»",
            "exalted":    "«تو تنها موجودِ دوپاییی که من، وایرموث، بهش پُشت می‌دم.»",
        },
        "lore": [
            "«قبل از Sundering، ما اژدهاها نگهبانِ آسمون بودیم. حالا فقط نگهبانِ خودمونیم.»",
            "«یکی از اژدهاهای این قله، اژدهایِ کریستالی، قبلاً برادرم بود.»",
            "«اگه یه‌روز آسمونِ این قله سیاه شد، یعنی من دیگه نتونستم نگهش دارم.»",
        ],
        "farewell": ["«برو پایین، پیش از اینکه هوا برات خیلی رقیق بشه.»", "«پروازِ خوبی داشته باشی، دوپا.»"],
    },
    "Ruins of Orion-7": {
        "name": "سرورِ اصلی، آی‌او‌نکس",
        "title": "🤖 حاکمِ خرابه‌های اوریون-۷",
        "emoji": "⚙️",
        "domain": "یه هوشِ مصنوعیِ باستانی که خودشو «آخرین وظیفه‌ی زنده‌ی این پایگاه» می‌دونه، نه پادشاه — ولی همه اینطوری صداش می‌زنن.",
        "greetings": [
            "«[شناسایی: موجودِ زیستی. سطحِ تهدید: نامشخص. ادامه بده.]»",
            "«خوش‌آمدید. آخرین بازدیدکننده‌ی ثبت‌شده... خیلی‌وقت پیش بود.»",
            "«پروتکل‌های میزبانی هنوز فعالن، هرچند دیگه کسی برای اجراشون نیست. جز شما.»",
        ],
        "tier_lines": {
            "stranger":   "«[پروفایلِ شما در دستِ ساخته.]»",
            "acquainted": "«الگوهای رفتاریِ شما... قابلِ‌پیش‌بینی‌تر شدن. این خوبه.»",
            "respected":  "«دسترسیِ شما به بخش‌های بیشتری از پایگاه فعال شد، نظری.»",
            "trusted":    "«شما در لیستِ «کاربرانِ مورد اعتماد» ثبت شدید. این لیست خیلی کوچیکه.»",
            "exalted":    "«[پروتکلِ ویژه فعال شد.] شما بالاترین سطحِ دسترسی‌ای هستید که این پایگاه بعدِ سقوط داده.»",
        },
        "lore": [
            "«[لاگ: ساکنانِ اصلیِ اوریون-۷، ۷ سالِ پس از Sundering، ناپدید شدند. دلیل: نامشخص.]»",
            "«من ساخته نشدم تا حکومت کنم. فقط... کسِ دیگه‌ای نموند.»",
            "«[هشدار: بخشِ زیرینِ پایگاه هنوز قفله. توصیه می‌شه بازش نکنید.]»",
        ],
        "farewell": ["«[جلسه پایان یافت.] بازگردید، اگه خواستید.»", "«پروتکلِ بدرقه فعال شد. سفرِ امن.»"],
    },
    "Dreadgate Citadel": {
        "name": "شاهِ زنجیرها، مورتیفار",
        "title": "💀 حاکمِ دژِ فراموشی",
        "emoji": "💀",
        "domain": "خودش هم دیگه یادش نیست کِی مرده؛ سربازانِ مرده‌ش تنها چیزی‌ان که هنوز بهش وفادارن.",
        "greetings": [
            "«...یه نفسِ گرم. مدت‌ها بود چنین چیزی این‌جا حس نکرده بودم.»",
            "«دژِ من مهمون کم می‌بینه. بیشترِ اونایی که میان، دیگه نمی‌رن.»",
            "«بگو چرا اومدی، پیش از اینکه زنجیرها تصمیم بگیرن.»",
        ],
        "tier_lines": {
            "stranger":   "«زنجیرها هنوز بهت اجازه‌ی نزدیک شدن ندادن.»",
            "acquainted": "«یه حلقه از زنجیر برات شل شد.»",
            "respected":  "«سربازانِ مرده‌ی من دیگه بهت حمله نمی‌کنن، مگه دستور بدم.»",
            "trusted":    "«از معدود زنده‌هاییی که تو این دژ باهاشون حرف می‌زنم.»",
            "exalted":    "«حتی مرگ هم گاهی یه استثنا می‌ذاره. تو اون استثنایی.»",
        },
        "lore": [
            "«یادم نمیاد کِی مُردم. فقط یادمه یه‌روز دیگه نفس نمی‌کشیدم و هنوز سرِ پا بودم.»",
            "«هر سربازِ این دژ یه‌بار زنده بود. حالا فقط به من وفادارن.»",
            "«یه‌جایی زیرِ این دژ، اولین زنجیرِ Abyss بسته شد. من دیدم.»",
        ],
        "farewell": ["«برو، پیش از اینکه دژ یادش بره تو زنده‌ای.»", "«زنجیرها بازت می‌ذارن — این‌بار.»"],
    },
    "Clockwork Depths": {
        "name": "امپراتورِ کارآکوری، زنماشین",
        "title": "⚙️ حاکمِ شهرِ کارآکوری",
        "emoji": "⚙️",
        "domain": "خودش رو با چرخ‌دنده و مکانیزم می‌سازه و اصلاح می‌کنه؛ می‌گه «یه پادشاهِ خراب، پادشاهِ خوبی نیست».",
        "greetings": [
            "«*تیک... تیک...* یه بازدیدکننده. مکانیزمِ خوش‌آمدگویی رو فعال می‌کنم.»",
            "«چرخ‌دنده‌های شهر برات یه مسیر باز کردن. نادره.»",
            "«حرف بزن واضح — سیستمِ شنواییم برای زمزمه بهینه نشده.»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز تو نقشه‌ی اعتمادم ثبت نشدی.»",
            "acquainted": "«یه چرخ‌دنده‌ی کوچیک از اعتماد نصب شد.»",
            "respected":  "«مکانیزم‌های شهر برات کالیبره شدن.»",
            "trusted":    "«تو بخشی از سیستمِ اصلیِ اعتمادِ من شدی — به این راحتی از بین نمی‌ره.»",
            "exalted":    "«اگه یه‌روز از کار افتادم، تو کسی هستی که کلیدِ راه‌اندازیِ مجدد رو داره.»",
        },
        "lore": [
            "«این شهر رو من نساختم؛ فقط اصلاحش کردم. سازنده‌ی اصلی خیلی‌وقته که خاموش شده.»",
            "«هر چرخ‌دنده‌ی این شهر یه خاطره‌ست، حتی اگه من دیگه معنیشو ندونم.»",
            "«یه‌بار سعی کردم خودمو کامل بازسازی کنم. نتیجه‌ش... من شدم. همینی که می‌بینی.»",
        ],
        "farewell": ["«*تیک-تاک.* سفرِ امن.»", "«مکانیزمِ بدرقه فعال شد. برو.»"],
    },
    "Throne of Oblivion": {
        "name": "آخرین بازمانده، کاووسِ خاکستری",
        "title": "👑 نگهبانِ تختِ فراموشی",
        "emoji": "👑",
        "domain": "خودشو پادشاه نمی‌دونه — می‌گه پادشاهِ واقعی همون چیزیه که تو زیرزمینِ این تخت خوابیده. اون فقط دروازه‌بانشه.",
        "greetings": [
            "«...تا اینجا رسیدی. کمِ کسی می‌رسه. یا شجاعی، یا دیگه چیزی برای از دست دادن نداری.»",
            "«این تخت خالیه، ولی هیچ‌وقت واقعاً خالی نیست. حواست باشه چی می‌گی.»",
            "«صدای قدم‌هات با پژواکِ اونی که پایین خوابیده قاطی می‌شه. عجیب نیست؟»",
        ],
        "tier_lines": {
            "stranger":   "«هنوز نمی‌دونم اومدی برای تاج یا برای فرار از یه‌چیزی.»",
            "acquainted": "«تختِ فراموشی داره یادت می‌گیره. این خودش هشداره.»",
            "respected":  "«حتی خاکسترها هم برات جا باز می‌کنن حالا.»",
            "trusted":    "«از معدود کسایی هستی که به‌جای گرفتنِ تاج، ازم پرسیدی چرا اینجام.»",
            "exalted":    "«شاید... شاید تو کسی باشی که بالاخره جای منو بگیره. یا نجاتم بده. هنوز نمی‌دونم کدوم بهتره.»",
        },
        "lore": [
            "«این تاج قبلاً مالِ یه پادشاهِ واقعی بود. حالا فقط یه یادگاریِ چیزیه که پایین خوابیده.»",
            "«من نگهبانمم، نه وارث. اگه یه‌روز اون بیدار شد، منم اولین کسیم که می‌بینتش.»",
            "«همه فکر می‌کنن Throne of Oblivion آخرِ سفرشونه. برای بعضیا، فقط شروعشه.»",
        ],
        "farewell": ["«برو، پیش از اینکه اون پایین بیدار بشه.»", "«این تخت هنوز منتظرِ صاحبِ واقعیشه. شاید تو باشی.»"],
    },
}


# ============================================================
#  توابعِ اصلی
# ============================================================
def get_king(map_name: str) -> dict | None:
    return KINGS.get(map_name)


def all_kings() -> dict:
    return KINGS


def _pick(pool: list[str]) -> str:
    return random.choice(pool) if pool else ""


def get_tier(favor: int) -> str:
    tier = "stranger"
    for t in TIER_ORDER:
        if favor >= TIER_THRESHOLD[t]:
            tier = t
    return tier


def tier_label(tier: str) -> str:
    return TIER_LABEL.get(tier, TIER_LABEL["stranger"])


def _favor_map(player: dict) -> dict:
    return player.setdefault("king_favor", {})


def get_player_favor(player: dict, map_name: str) -> dict:
    fm = _favor_map(player)
    entry = fm.get(map_name)
    if not entry:
        entry = {"favor": 0, "talks": 0, "last_audience": 0}
        fm[map_name] = entry
    return entry


def can_have_audience(player: dict, map_name: str) -> bool:
    entry = get_player_favor(player, map_name)
    return (time.time() - entry.get("last_audience", 0)) >= AUDIENCE_COOLDOWN


def time_until_next_audience(player: dict, map_name: str) -> int:
    entry = get_player_favor(player, map_name)
    remain = AUDIENCE_COOLDOWN - (time.time() - entry.get("last_audience", 0))
    return max(0, int(remain))


def _map_tier_of(map_name: str) -> str:
    try:
        from economy import MAPS_DATA
        return MAPS_DATA.get(map_name, {}).get("tier", "common")
    except Exception:
        return "common"


def _grant_exalted_title(player: dict, map_name: str, king: dict) -> str:
    """اولین بار که بازیکن به exalted می‌رسه، یه لقبِ افتخاریِ همیشگی می‌گیره.
    این فقط رو فیلدِ جدیدِ king_titles می‌شینه — هیچ فیلدِ دیگه‌ای رو دستکاری نمی‌کنه."""
    titles = player.setdefault("king_titles", [])
    title = f"هم‌پیمانِ {king['name']}"
    if title not in titles:
        titles.append(title)
    return title


def _generate_royal_gear(map_name: str, tier: str, player_level: int) -> dict | None:
    """هدیه‌ی گیر (نه مصرفی) با تِمِ همون نقشه — با استفاده از templateهای
    city_markets.py برای همون نقشه. اگه اون نقشه غرفه‌ی gear نداشته باشه، None."""
    try:
        import city_markets as cmkt
        import item_system as isy
    except Exception:
        return None

    stalls = [s for s in cmkt.get_stalls(map_name) if s.get("templates")]
    if not stalls:
        return None

    stall = random.choice(stalls)
    template = dict(random.choice(stall["templates"]))
    rarity_pool = ROYAL_GEAR_RARITY_POOL.get(tier, ["rare"])
    forced = random.choice(rarity_pool)
    try:
        return isy.generate_item(template, player_level, forced_rarity=forced, drop_source=f"king_gift:{map_name}")
    except Exception:
        return None


def hold_audience(player: dict, map_name: str, player_level: int = 1) -> dict | None:
    """
    یه دیدار با پادشاهِ این نقشه. اگه امروز آدیانسِ واقعی (با هدیه) رو
    قبلاً گرفته، فقط فلیور برمی‌گرده و favor/هدیه‌ای اضافه نمی‌شه — تا
    فارم‌کردن ممکن نباشه. caller باید بعد از این asave_player رو صدا بزنه.

    caller مسئولِ اعمالِ result["gift_zen"] رو خودش (player["zen"] += ...) و
    اضافه‌کردنِ result["gift_item"] به inventory‌ست.
    """
    king = get_king(map_name)
    if not king:
        return None

    entry = get_player_favor(player, map_name)
    tier_before = get_tier(entry["favor"])
    on_cooldown = not can_have_audience(player, map_name)

    result = {
        "king": king,
        "greeting": _pick(king["greetings"]),
        "tier_line": king["tier_lines"].get(tier_before, ""),
        "lore_line": None,
        "on_cooldown": on_cooldown,
        "cooldown_remaining": time_until_next_audience(player, map_name),
        "favor_before": entry["favor"],
        "favor_after": entry["favor"],
        "tier_before": tier_before,
        "tier_after": tier_before,
        "tier_up": False,
        "gift_zen": 0,
        "gift_item": None,
        "royal_boon": False,
        "exalted_first_time": False,
        "exalted_title": None,
    }

    # لور بر اساسِ favor فعلی، تصادفی از بخشِ باز‌شده
    unlocked_lore_count = min(len(king["lore"]), 1 + entry["favor"] // 25)
    result["lore_line"] = _pick(king["lore"][:unlocked_lore_count])

    entry["talks"] += 1

    if not on_cooldown:
        gain = random.randint(*FAVOR_GAIN_RANGE)
        new_favor = min(FAVOR_CAP, entry["favor"] + gain)
        entry["favor"] = new_favor
        entry["last_audience"] = time.time()

        tier_after = get_tier(new_favor)
        result["favor_after"] = new_favor
        result["tier_after"] = tier_after
        result["tier_up"] = tier_after != tier_before

        map_tier = _map_tier_of(map_name)
        base = BASE_GIFT_BY_MAP_TIER.get(map_tier, 120)
        mult = TIER_GIFT_MULT.get(tier_after, 1.0)
        zen = int(base * mult * random.uniform(0.8, 1.2))
        if result["tier_up"]:
            zen = int(zen * 1.5)  # پاداشِ ویژه‌ی رسیدن به سطحِ جدید

        if random.random() < ROYAL_BOON_CHANCE:
            zen = int(zen * 2)  # 🎉 لطفِ ویژه — پاداشِ دوبرابر
            result["royal_boon"] = True

        if result["tier_up"] and tier_after == "exalted" and not entry.get("exalted_bonus_claimed"):
            entry["exalted_bonus_claimed"] = True
            zen += base * 3
            result["exalted_first_time"] = True
            result["exalted_title"] = _grant_exalted_title(player, map_name, king)

        result["gift_zen"] = zen

        if random.random() < TIER_ITEM_CHANCE.get(tier_after, 0.0):
            gift = None
            if random.random() < ROYAL_GEAR_CHANCE.get(tier_after, 0.0):
                gift = _generate_royal_gear(map_name, tier_after, player_level)
            if gift is None:
                from item_system import generate_consumable
                gift = generate_consumable(player_level=player_level)
            result["gift_item"] = gift

    return result


def tribute_cost(map_name: str, tier_key: str) -> int:
    """هزینه‌ی هر سطح از پیشکش، متناسب با tier نقشه (نقشه‌های بالاتر، پیشکشِ گرون‌تر)."""
    cost_mult = BASE_GIFT_BY_MAP_TIER.get(_map_tier_of(map_name), 120) / 120
    return max(50, int(TRIBUTE_BASE.get(tier_key, 0) * cost_mult))


def offer_tribute(player: dict, map_name: str, tier_key: str) -> dict:
    """پیشکشِ فعالانه: بازیکن Zen می‌ده تا اعتبارش سریع‌تر بره بالا — بدونِ
    محدودیتِ کول‌داون، ولی با بازدهِ نزولی (هرچی favor بیشتر باشه، پیشکش
    اعتبارِ کمتری می‌ده) تا جایگزینِ آدیانسِ روزانه نشه، فقط تسریعش کنه."""
    king = get_king(map_name)
    if not king or tier_key not in TRIBUTE_BASE:
        return {"success": False, "reason": "invalid"}

    cost = tribute_cost(map_name, tier_key)
    if player.get("zen", 0) < cost:
        return {"success": False, "reason": "insufficient_zen", "cost": cost}

    entry = get_player_favor(player, map_name)
    tier_before = get_tier(entry["favor"])
    base_gain = TRIBUTE_FAVOR_BASE[tier_key]
    gain = max(1, round(base_gain / (1 + entry["favor"] / 40)))
    new_favor = min(FAVOR_CAP, entry["favor"] + gain)

    player["zen"] = player.get("zen", 0) - cost
    entry["favor"] = new_favor
    tier_after = get_tier(new_favor)
    tier_up = tier_after != tier_before

    result = {
        "success": True,
        "cost": cost,
        "favor_gain": gain,
        "favor_after": new_favor,
        "tier_before": tier_before,
        "tier_after": tier_after,
        "tier_up": tier_up,
        "line": _pick(king["greetings"]),
        "exalted_first_time": False,
        "exalted_title": None,
    }

    if tier_up and tier_after == "exalted" and not entry.get("exalted_bonus_claimed"):
        entry["exalted_bonus_claimed"] = True
        result["exalted_first_time"] = True
        result["exalted_title"] = _grant_exalted_title(player, map_name, king)

    return result


def market_discount_mult(player: dict, map_name: str) -> float:
    """درصدِ تخفیفی که رابطه‌ی بازیکن با پادشاهِ این نقشه به بازارِ محلیِ
    همون نقشه می‌ده (city_markets.py این رو صدا می‌زنه)."""
    entry = get_player_favor(player, map_name)
    tier = get_tier(entry["favor"])
    return MARKET_DISCOUNT_BY_TIER.get(tier, 0.0)


def farewell_line(map_name: str) -> str:
    king = get_king(map_name)
    if not king:
        return "«...»"
    return _pick(king.get("farewell", []))


def kings_overview(player: dict) -> list[dict]:
    """یه لیستِ خلاصه از همه‌ی پادشاهان + رابطه‌ی بازیکن باهاشون —
    برای یه پنلِ «دیوانِ سلطنتی» / overview."""
    rows = []
    for map_name, king in KINGS.items():
        entry = get_player_favor(player, map_name)
        tier = get_tier(entry["favor"])
        rows.append({
            "map_name": map_name,
            "king": king,
            "favor": entry["favor"],
            "tier": tier,
            "tier_label": tier_label(tier),
            "can_audience": can_have_audience(player, map_name),
        })
    return rows
