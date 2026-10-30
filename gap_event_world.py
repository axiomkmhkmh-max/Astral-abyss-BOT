# ============================================================
#  ASTRAL ABYSS — Gap Event World 🌍
# ------------------------------------------------------------
#  دیتا و منطقِ خالصِ «دنیای رویدادهای گروهیِ گپ». هیچ import ای از GAP،
#  دیتابیس یا aiogram نداره؛ فقط:
#     • economy.MAPS_DATA        (اسمِ رسمیِ نقشه‌ها و ایموجی/تایر)
#     • map_boss_pool            (اسمِ باسِ نهاییِ هر منطقه برای دانجن — اختیاری)
#  پس کاملاً قابلِ تست بدونِ ربات.
#
#  چی تو این فایله:
#     1) REGIONS         — پروفایلِ هر منطقه (عنصر، باس‌ها، دانجن‌ها، هیولاها، توصیف‌ها)
#     2) انتخابِ منطقه   — از روی player["map"] بازیکن‌های فعال (اکثریت)، وگرنه رندومِ وزنی
#     3) باس             — انتخابِ تمپلیت متناسب با منطقه + متنِ سینمایی (هشدارها/محیط)
#     4) هیولا           — فهرستِ هیولاها با عنصر/ضعف/ویژگی (evasive/armored/frenzied)
#     5) صندوق           — برچسبِ ندرت و توصیفِ محیطی
#     6) دانجن           — ۷ نوع، اتاق‌های تصادفی (۶ نوعِ برخورد)، نگهبانِ نهایی، فرمولِ موفقیت
#
#  نکته‌ی عنصرِ باس: تو boss_engine، «مقاومِ فازِ ۱» همیشه عنصرِ خودِ باسه
#  (آتشی→resist=fire، یخی→ice، ...) پس لازم نیست جدولِ جدا نگه داریم:
#     boss_element(tid) = WORLD_BOSS_TEMPLATES[tid]["phases"][0]["resist"]
# ============================================================
from __future__ import annotations

import random
import re
from typing import Callable, Optional

try:
    from economy import MAPS_DATA
except Exception:  # pragma: no cover — تست بدونِ پروژه
    MAPS_DATA = {}

try:
    from map_boss_pool import MAP_BOSS_POOL
except Exception:  # pragma: no cover
    MAP_BOSS_POOL = {}

ELEMENTS = ("fire", "ice", "lightning", "void", "holy", "nature", "arcane", "physical")
ACTIONS = {"fight": "⚔️ حمله", "guard": "🛡 دفاع", "search": "🔍 جستجو"}


# ============================================================
#  1) منطقه‌ها
# ============================================================
# کلیدها دقیقاً همون کلیدهای economy.MAPS_DATA / player["map"] ان.
# bosses/dungeons/monsters = {id: وزن}. idهایی که تو پروژه نباشن خودکار فیلتر می‌شن.
REGIONS: dict[str, dict] = {
    "Emberhollow": {
        "fa": "دره‌ی آتش", "emoji": "🔥", "element": "fire", "weight": 2.5, "ref_power": 70,
        "bosses": {"pyrothrax": 5, "infernus_warlord": 4, "solisara_phoenix": 3},
        "dungeons": {"ancient_forge": 5, "bone_crypt": 2},
        "monsters": {"magma_golem": 5, "skeleton_warrior": 2, "stone_golem": 2},
        "env": ["هوا از گرما می‌لرزه و بوی گوگرد همه‌جا پیچیده.",
                "رودخانه‌های گدازه از لابه‌لای صخره‌های سیاه می‌گذرن.",
                "خاکسترِ داغ مثل برف از آسمونِ سرخ می‌باره."],
        "chest": ["یه صندوقِ نیمه‌ذوب‌شده بینِ سنگ‌های مذاب برق می‌زنه",
                  "زیرِ لایه‌ی خاکسترِ داغ یه صندوقِ آهنی پیدا شد",
                  "کنارِ دهانه‌ی یه آتشفشانِ خاموش یه صندوقِ دوده‌گرفته افتاده"],
    },
    "Dragonnest Peaks": {
        "fa": "لانه‌ی اژدها", "emoji": "🐉", "element": "fire", "weight": 1.0, "ref_power": 100,
        "bosses": {"pyrothrax": 4, "solisara_phoenix": 4, "infernus_warlord": 2},
        "dungeons": {"ancient_forge": 3, "abandoned_tower": 3, "bone_crypt": 2},
        "monsters": {"magma_golem": 3, "stone_golem": 3, "armored_ancient": 2},
        "env": ["استخوانِ غول‌پیکرِ اژدهایون روی قله‌ها پراکنده‌ست.",
                "بالِ سایه‌ها از بالای سرتون رد می‌شه و زمین می‌لرزه."],
        "chest": ["لای استخوانای یه اژدهای باستانی یه صندوقِ سنگین پیدا شد",
                  "روی یه تاقچه‌ی صخره‌ای، تویِ لانه‌ی خالیِ یه اژدها، صندوقی برق می‌زنه"],
    },
    "Frostheim": {
        "fa": "قلمروی یخ", "emoji": "❄️", "element": "ice", "weight": 2.5, "ref_power": 70,
        "bosses": {"glacies_regina": 6, "glaciovorn_leviathan": 3},
        "dungeons": {"bone_crypt": 3, "abandoned_tower": 3, "spider_cave": 1},
        "monsters": {"frost_wolf": 5, "skeleton_warrior": 2, "stone_golem": 2},
        "env": ["کولاکِ برف دیدِ همه‌جا رو بسته و نَفَس‌ها بخار می‌شن.",
                "ستون‌های یخیِ غول‌پیکر زیرِ نورِ کمرنگ می‌درخشن.",
                "سکوتِ سنگینِ برف فقط با صدای ترک‌خوردنِ یخ شکسته می‌شه."],
        "chest": ["یه صندوقِ باستانی تویِ یه بلوکِ یخیِ شفاف حبس شده بود که تازه ترک خورد",
                  "زیرِ لایه‌ی برف گوشه‌ی یه صندوقِ یخ‌زده پیدا شد",
                  "تویِ یه غارِ یخی، صندوقی با نقش‌های سرمازده برق می‌زنه"],
    },
    "Voidbreak Wastes": {
        "fa": "سرزمینِ پوچی", "emoji": "🌑", "element": "void", "weight": 2.0, "ref_power": 100,
        "bosses": {"abyss_sovereign": 4, "obscura_veil_empress": 4, "astral_devourer": 3, "nyx_absolute": 1},
        "dungeons": {"shadow_labyrinth": 4, "bone_crypt": 3, "forgotten_cathedral": 1},
        "monsters": {"abyss_ghost": 5, "shadow_wolf": 3, "skeleton_warrior": 2},
        "env": ["آسمون ترک برداشته و از شکاف‌هاش تاریکیِ کیهانی چکه می‌کنه.",
                "واقعیت اینجا خم می‌شه و سایه‌ها بدونِ نور حرکت می‌کنن.",
                "زمزمه‌هایی بی‌صاحب از دلِ خرابه‌های سیاه میاد."],
        "chest": ["از شکافِ واقعیت یه صندوقِ تاریک بیرون افتاد و هنوز دودِ سیاه ازش بلنده",
                  "لای خرابه‌های پژمرده یه صندوقِ نفرین‌شده با نقش‌های عجیب پیدا شد",
                  "یه صندوقِ سیاه وسطِ هیچ‌جا شناوره و آهسته می‌چرخه"],
    },
    "Throne of Oblivion": {
        "fa": "تختِ فراموشی", "emoji": "👑", "element": "void", "weight": 0.5, "ref_power": 140,
        "bosses": {"nyx_absolute": 4, "thanotep_reaper": 3, "abyss_sovereign": 2},
        "dungeons": {"shadow_labyrinth": 3, "bone_crypt": 3, "forgotten_cathedral": 2},
        "monsters": {"abyss_ghost": 4, "skeleton_warrior": 4, "armored_ancient": 2},
        "env": ["تاجی بی‌صاحب بالای یه تختِ ترک‌خورده معلقه.",
                "سایه‌ی پادشاهانِ فراموش‌شده روی دیوارها می‌لغزه."],
        "chest": ["کنارِ پله‌های تختِ شکسته یه صندوقِ شاهیِ خاک‌گرفته مونده"],
    },
    "Dreadgate Citadel": {
        "fa": "دژِ فراموشی", "emoji": "💀", "element": "void", "weight": 1.0, "ref_power": 100,
        "bosses": {"thanotep_reaper": 4, "infernus_warlord": 3, "obscura_veil_empress": 2},
        "dungeons": {"bone_crypt": 4, "abandoned_tower": 3, "shadow_labyrinth": 2},
        "monsters": {"skeleton_warrior": 5, "armored_ancient": 3, "abyss_ghost": 2},
        "env": ["دروازه‌های آهنیِ دژ با ناله‌ی بلندی روی لولاهاشون می‌چرخن.",
                "پرچم‌های پاره‌پوره‌ی لشکری که هیچ‌وقت برنگشت می‌لرزن."],
        "chest": ["پشتِ یه سنگرِ شکسته یه صندوقِ جنگیِ مهروموم‌شده پیدا شد"],
    },
    "Verdant Vale": {
        "fa": "جنگلِ ارواح", "emoji": "🌿", "element": "nature", "weight": 3.0, "ref_power": 40,
        "bosses": {"sylvanroot_ancient": 5, "korvexia_venom_queen": 3, "umbra_matriarch": 3},
        "dungeons": {"spider_cave": 4, "abandoned_tower": 2, "sunken_temple": 1},
        "monsters": {"shadow_wolf": 3, "cave_spider": 3, "swamp_beast": 3, "stone_golem": 1},
        "env": ["نورِ سبزِ ملایمی از لابه‌لای شاخه‌های کهن می‌تابه.",
                "ریشه‌های غول‌پیکر مثلِ رگ‌های زنده زیرِ زمین می‌لولن.",
                "مهِ نقره‌ای بینِ درخت‌ها آهسته جابه‌جا می‌شه."],
        "chest": ["بینِ ریشه‌های یه درختِ کهن یه صندوقِ خزه‌بسته پیدا شد",
                  "یه صندوقِ چوبیِ پوشیده از پیچک وسطِ یه چمنزارِ پنهان افتاده",
                  "زیرِ یه قارچِ غول‌پیکرِ درخشان صندوقی نیمه‌دفن شده بود"],
    },
    "Celestial Spire": {
        "fa": "برجِ آسمانی", "emoji": "🏰", "element": "holy", "weight": 2.0, "ref_power": 70,
        "bosses": {"celestine_guardian": 4, "seraphine_ordo": 4, "astral_cartographer": 3},
        "dungeons": {"forgotten_cathedral": 4, "abandoned_tower": 4},
        "monsters": {"celestial_sentinel": 5, "armored_ancient": 3, "stone_golem": 1},
        "env": ["نورِ ستاره‌ها از سقفِ شکسته‌ی برج روی زمین می‌ریزه.",
                "پل‌های معلق بینِ ابرها آروم می‌لرزن و آسمون بی‌نهایت نزدیکه.",
                "زنگ‌های نامرئیِ معبد هر چند لحظه یه‌بار به صدا درمیان."],
        "chest": ["روی یه پلِ معلق، صندوقی با هاله‌ی طلاییِ ملایم نشسته",
                  "از دلِ یه ابرِ نورانی یه صندوقِ مقدس پایین اومد",
                  "لای ستون‌های مرمرینِ یه معبدِ آسمانی یه صندوقِ باستانی برق می‌زنه"],
    },
    "Holy Luminarchy": {
        "fa": "پایتختِ نور", "emoji": "✨", "element": "holy", "weight": 1.5, "ref_power": 55,
        "bosses": {"seraphine_ordo": 4, "celestine_guardian": 4},
        "dungeons": {"forgotten_cathedral": 5, "abandoned_tower": 2},
        "monsters": {"celestial_sentinel": 4, "armored_ancient": 3, "skeleton_warrior": 1},
        "env": ["گنبدهای طلاییِ شهر زیرِ نورِ صبح می‌درخشن.",
                "سرودِ دوردستِ کشیش‌ها از کلیسای بزرگ میاد."],
        "chest": ["پشتِ یه ستونِ کلیسا یه صندوقِ هدیه‌ی زائران جا مونده"],
    },
    "Stormward Archipelago": {
        "fa": "جزایرِ طوفانی", "emoji": "⛈️", "element": "lightning", "weight": 1.5, "ref_power": 70,
        "bosses": {"tempestas_rex": 5, "voltarion_titan": 4},
        "dungeons": {"sunken_temple": 3, "abandoned_tower": 3, "ancient_forge": 1},
        "monsters": {"storm_wraith": 5, "tide_horror": 3, "shadow_wolf": 1},
        "env": ["رعد و برق مدام آسمونِ سیاه رو می‌شکافه.",
                "موج‌های غول‌پیکر به صخره‌ها می‌کوبن و کف‌شون تا سینه‌تون می‌پاشه."],
        "chest": ["صاعقه تازه یه صندوقِ سوخته رو از دلِ ماسه‌ها بیرون انداخته",
                  "روی یه صخره‌ی مرطوب، صندوقی با جرقه‌های آبی می‌لرزه"],
    },
    "Azure Tides Empire": {
        "fa": "امپراتوریِ آبی", "emoji": "🌊", "element": "ice", "weight": 2.0, "ref_power": 40,
        "bosses": {"glaciovorn_leviathan": 5, "tempestas_rex": 2},
        "dungeons": {"sunken_temple": 5, "spider_cave": 1},
        "monsters": {"tide_horror": 5, "swamp_beast": 2, "storm_wraith": 1},
        "env": ["نمکِ دریا هوا رو سنگین کرده و موج‌ها آروم می‌کوبن.",
                "بندرِ قدیمیِ امپراتوری زیرِ مهِ آبی خوابیده."],
        "chest": ["موج یه صندوقِ صدف‌نشین رو روی ساحل انداخت",
                  "کنارِ یه کشتیِ نیمه‌غرق، صندوقی با زنجیرِ زنگ‌زده افتاده"],
    },
    "The Sunken City": {
        "fa": "شهرِ غرق‌شده", "emoji": "🐚", "element": "arcane", "weight": 1.5, "ref_power": 70,
        "bosses": {"glaciovorn_leviathan": 5, "obscura_veil_empress": 2},
        "dungeons": {"sunken_temple": 6},
        "monsters": {"tide_horror": 5, "swamp_beast": 2, "abyss_ghost": 1},
        "env": ["ستون‌های آتلانتیسی زیرِ نورِ سبزِ مرجان‌ها موج می‌زنن.",
                "حباب‌های نورانی از دلِ خرابه‌ها بالا میان."],
        "chest": ["بینِ مرجان‌های درخشان یه صندوقِ دریایی برق می‌زنه"],
    },
    "Sands of Eternity": {
        "fa": "صحرای جاودان", "emoji": "🏜️", "element": "physical", "weight": 2.0, "ref_power": 40,
        "bosses": {"terra_behemoth": 5, "thanotep_reaper": 3, "solisara_phoenix": 2},
        "dungeons": {"bone_crypt": 3, "forgotten_cathedral": 2, "abandoned_tower": 2},
        "monsters": {"stone_golem": 4, "skeleton_warrior": 3, "armored_ancient": 2},
        "env": ["گردبادِ شن مثلِ مارِ عظیمی روی تپه‌ها می‌پیچه.",
                "خورشیدِ بی‌رحم استخوان‌های سفیدِ کاروان‌های گمشده رو می‌سوزونه."],
        "chest": ["شن‌های جابه‌جا شده یه صندوقِ طلاکوبِ نیمه‌دفن رو نشون دادن",
                  "کنارِ یه واحه‌ی خشک‌شده یه صندوقِ کاروانی جا مونده"],
    },
    "Ruins of Orion-7": {
        "fa": "خرابه‌های اوریون-۷", "emoji": "🏚️", "element": "physical", "weight": 1.5, "ref_power": 70,
        "bosses": {"ferrum_juggernaut": 4, "astral_cartographer": 4},
        "dungeons": {"ancient_forge": 3, "abandoned_tower": 3, "shadow_labyrinth": 1},
        "monsters": {"armored_ancient": 4, "stone_golem": 3, "storm_wraith": 1},
        "env": ["چراغ‌های قدیمیِ ویرانه هنوز سوسو می‌زنن.",
                "ماشین‌های زنگ‌زده‌ی تمدنِ گمشده با صدای فلزی ناله می‌کنن."],
        "chest": ["تویِ یه انبارِ فلزیِ باز‌شده یه کانتینرِ مهروموم‌شده پیدا شد"],
    },
    "Clockwork Depths": {
        "fa": "شهرِ کارآکوری", "emoji": "⚙️", "element": "physical", "weight": 1.5, "ref_power": 70,
        "bosses": {"ferrum_juggernaut": 5, "voltarion_titan": 3},
        "dungeons": {"ancient_forge": 5, "shadow_labyrinth": 1, "abandoned_tower": 1},
        "monsters": {"armored_ancient": 3, "stone_golem": 3, "magma_golem": 2},
        "env": ["چرخ‌دنده‌های غول‌پیکر بالای سرتون آروم می‌چرخن.",
                "بخارِ داغ از لوله‌های قدیمی فوران می‌کنه."],
        "chest": ["بینِ چرخ‌دنده‌های ازکارافتاده یه صندوقِ برنجیِ ساعت‌خورده پیدا شد"],
    },
}

_NORM = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())  # noqa: E731
_REGION_BY_NORM = {_NORM(k): k for k in REGIONS}


def normalize_region(name: Optional[str]) -> Optional[str]:
    """«EmberHollow» / «Voidbreak Wastes» / «VoidBreak Wastes» → کلیدِ رسمیِ REGIONS (یا None)."""
    return _REGION_BY_NORM.get(_NORM(name))


def region_label(region: Optional[str]) -> str:
    r = REGIONS.get(region or "")
    return f"{r['emoji']} {r['fa']}" if r else "🌍 دنیای آبیس"


def region_element(region: Optional[str]) -> str:
    return REGIONS.get(region or "", {}).get("element", "arcane")


def region_ref_power(region: Optional[str]) -> float:
    return float(REGIONS.get(region or "", {}).get("ref_power", 60))


def pick_region(maps: list, rng: random.Random | None = None) -> tuple[Optional[str], str]:
    """منطقه‌ی رویداد رو از لیستِ player["map"]‌ِ بازیکن‌های فعال انتخاب می‌کنه.

    خروجی: (region_key, how)    how ∈ {"majority", "tie", "weighted"}
      • اکثریتِ ساده بینِ نقشه‌هایی که تو REGIONS تعریف شدن (نقشه‌ی ناشناخته/بازارِ سیاه شمرده نمی‌شه)
      • تساوی → رندوم بینِ مساوی‌ها
      • هیچ اطلاعاتِ قابل‌اعتمادی نبود → رندومِ وزنی (وزنِ کمِ منطقه‌های سنگین/نادر)
    هیچ‌وقت از GPS یا موقعیتِ واقعیِ گروه استفاده نمی‌کنه."""
    rng = rng or random
    counts: dict[str, int] = {}
    for m in maps:
        k = normalize_region(m)
        if k:
            counts[k] = counts.get(k, 0) + 1
    if counts:
        top = max(counts.values())
        winners = sorted(k for k, c in counts.items() if c == top)
        return (winners[0], "majority") if len(winners) == 1 else (rng.choice(winners), "tie")
    keys = list(REGIONS.keys())
    return rng.choices(keys, weights=[REGIONS[k]["weight"] for k in keys], k=1)[0], "weighted"


def region_env_line(region: Optional[str], rng: random.Random | None = None) -> str:
    rng = rng or random
    r = REGIONS.get(region or "")
    return rng.choice(r["env"]) if r and r.get("env") else ""


# ============================================================
#  2) باس
# ============================================================
def boss_element(tid: str, templates: dict) -> str:
    """عنصرِ خودِ باس = مقاومِ فازِ ۱ (طبقِ طراحیِ boss_engine). نمونه: pyrothrax → fire."""
    tpl = templates.get(tid) or {}
    try:
        return tpl["phases"][0]["resist"]
    except Exception:
        return "arcane"


def threat_level(total_hp: int) -> tuple[int, str]:
    n = max(1, min(5, 1 + (int(total_hp) - 8000) // 2500))
    label = ["", "پایین", "متوسط", "بالا", "خیلی بالا", "مرگبار"][n]
    return n, label


def threat_bar(n: int) -> str:
    return "☠️" * n + "▫️" * (5 - n)


def pick_boss_template(region: Optional[str], templates: dict,
                       rng: random.Random | None = None, exclude: set | None = None) -> str:
    """تمپلیتِ باس رو متناسب با منطقه انتخاب می‌کنه؛ idهای ناموجود تو boss_engine حذف می‌شن.
    اگه استخرِ منطقه خالی بود، از بینِ همه‌ی تمپلیت‌ها (با وزنِ برابر) می‌گیره."""
    rng = rng or random
    exclude = exclude or set()
    pool = {t: w for t, w in (REGIONS.get(region or "", {}).get("bosses") or {}).items()
            if t in templates and t not in exclude}
    if not pool:
        pool = {t: 1 for t in templates if t not in exclude} or {t: 1 for t in templates}
    ids, ws = zip(*pool.items())
    return rng.choices(ids, weights=ws, k=1)[0]


# هر عنصر: توصیفِ محیط تو فاز ۲/۳، هشدارهای حمله‌ی ناحیه‌ای، خشم، و صحنه‌ی مرگ
ELEMENT_FX: dict[str, dict] = {
    "fire": {
        "env2": "🌋 زمین ترک خورد و گدازه از شکاف‌ها بیرون می‌زنه!",
        "env3": "🔥 کلِ منطقه داره می‌سوزه — هوا از گرما می‌لرزه!",
        "warn": ["🔥 **{boss} نفسِ آتشین رو جمع می‌کنه!** سنگ‌ها دارن سرخ می‌شن...",
                 "☄️ **از آسمون شهاب می‌باره!** {boss} تمرکز کرده...",
                 "🌋 **زمین زیرِ پاتون داره می‌ترکه!** {boss} موجِ گدازه رو آماده می‌کنه..."],
        "enrage": "🔥 **{boss} در آتشِ خشمش می‌سوزه!**",
        "death": ["🔥 شعله‌های {boss} آروم‌آروم خاموش شد و فقط خاکستر موند...",
                  "🌋 {boss} با غرشِ آخرش توی گدازه فرو رفت!"],
    },
    "ice": {
        "env2": "🌨 کولاکی بی‌رحم شروع شد و یخ زیرِ پاتون ترک می‌خوره!",
        "env3": "🧊 همه‌چی دور و برتون یخ می‌بنده — نَفَس‌ها هم منجمد می‌شن!",
        "warn": ["❄️ **{boss} هوا رو سرد می‌کنه!** یخ داره روی زمین پخش می‌شه...",
                 "🌨 **بهمنی در راهه!** {boss} صدای غرشِ برف رو بلند کرد...",
                 "🧊 **تیرهای یخی دورِ {boss} شکل می‌گیرن!** آماده‌ی پرتاب‌ان..."],
        "enrage": "🧊 **{boss} با خشمِ یخبندان می‌غره!**",
        "death": ["🧊 بدنِ {boss} ترک خورد و مثلِ بلور فرو ریخت...",
                  "❄️ کولاک آروم شد؛ {boss} دیگه نیست."],
    },
    "lightning": {
        "env2": "⚡ ابرهای سیاه جمع شدن و رعد و برق دور و برتون می‌کوبه!",
        "env3": "🌩 توفانِ مطلق! زمین مدام تحتِ حمله‌ی صاعقه‌هاست!",
        "warn": ["⚡ **{boss} داره بار الکتریکی جمع می‌کنه!** موهای تنتون سیخ شده...",
                 "🌩 **ابرها دارن شکافته می‌شن!** {boss} صاعقه رو نشونه رفته...",
                 "⛈ **قوس‌های برق دورِ {boss} می‌رقصن!** فقط یه لحظه وقت دارین..."],
        "enrage": "⚡ **{boss} در توفانِ خشمش گم شده!**",
        "death": ["⚡ آخرین جرقه‌ی {boss} آسمون رو روشن کرد و خاموش شد!",
                  "🌩 توفان فرو نشست؛ {boss} روی زمین افتاد."],
    },
    "void": {
        "env2": "🌑 واقعیت اطرافتون داره خم می‌شه و سایه‌ها زنده می‌شن!",
        "env3": "🕳 خلأ از همه‌طرف می‌بلعه — نور هم داره محو می‌شه!",
        "warn": ["🌑 **{boss} خلأ رو فرا می‌خونه!** نور داره دور می‌شه...",
                 "🕳 **شکافی تو واقعیت باز شد!** {boss} داره موجِ نیستی رو جمع می‌کنه...",
                 "🖤 **سایه‌ها دورِ پاهاتون حلقه می‌زنن!** {boss} آماده‌ی ضربه‌ست..."],
        "enrage": "🖤 **{boss} در تاریکیِ خشمش فرو رفته!**",
        "death": ["🌑 {boss} در خودش فرو ریخت و تاریکی آروم شد...",
                  "🕳 شکافِ خلأ بسته شد؛ {boss} دیگه نیست."],
    },
    "holy": {
        "env2": "✨ نورِ خیره‌کننده‌ای از آسمون می‌تابه و هوا داره می‌درخشه!",
        "env3": "🌟 داوریِ نهایی! ستون‌های نور از آسمون فرود میان!",
        "warn": ["✨ **{boss} نورِ مقدس رو جمع می‌کنه!** چشم‌ها دارن می‌سوزن...",
                 "🌟 **ستونی از نور در راهه!** {boss} داوری رو آماده کرده...",
                 "🪽 **بال‌های {boss} باز شد!** پرتوی کورکننده‌ای می‌ریزه..."],
        "enrage": "🌟 **{boss} با خشمِ مقدسش می‌درخشه!**",
        "death": ["✨ نورِ {boss} آروم‌آروم کم‌رنگ شد و محو گشت...",
                  "🌟 {boss} با یه درخششِ آخر به آسمون برگشت."],
    },
    "nature": {
        "env2": "🌿 ریشه‌ها از زمین بیرون می‌زنن و جنگل داره زنده می‌شه!",
        "env3": "🌳 جنگل خشمگینه — هر شاخه و ریشه‌ای می‌خواد شما رو بگیره!",
        "warn": ["🌿 **ریشه‌ها دارن زیرِ زمین می‌لولن!** {boss} موج رو آماده می‌کنه...",
                 "🍃 **هوا پر از اسپور و سمه!** {boss} نفسِ زهرآلود می‌گیره...",
                 "🕸 **تارها از همه‌طرف کشیده می‌شن!** {boss} داره شکار می‌کنه..."],
        "enrage": "🌳 **{boss} در خشمِ جنگل ریشه‌دوانده!**",
        "death": ["🌿 {boss} با ناله‌ی کهنی روی زمین افتاد و ریشه‌هاش خشکید...",
                  "🍃 جنگل آروم شد؛ {boss} دیگه نیست."],
    },
    "arcane": {
        "env2": "🔮 فضا داره پاره می‌شه و انرژیِ کیهانی دور و برتون می‌چرخه!",
        "env3": "🌌 جاذبه از کار افتاده — همه‌چی داره به‌هم می‌ریزه!",
        "warn": ["🔮 **{boss} انرژیِ کیهانی جمع می‌کنه!** فضا داره موج می‌زنه...",
                 "🌌 **شکافی تو فضا باز شد!** {boss} داره حمله رو آماده می‌کنه...",
                 "💫 **ستاره‌ها دارن می‌لرزن!** {boss} موجِ آرکین رو رها می‌کنه..."],
        "enrage": "🌌 **{boss} در جنونِ کیهانی فرو رفته!**",
        "death": ["🔮 {boss} در یه انفجارِ بی‌صدا از انرژی پخش شد...",
                  "🌌 شکاف‌ها بسته شد؛ {boss} دیگه نیست."],
    },
    "physical": {
        "env2": "⚙️ زمین زیرِ ضربه‌های سنگینِ {boss} می‌لرزه و سنگ‌ها پرت می‌شن!",
        "env3": "💥 اطراف داره ویران می‌شه — {boss} دیگه هیچی رو نگه نمی‌داره!",
        "warn": ["⚙️ **{boss} آماده‌ی ضربه‌ی سنگینه!** زمین داره می‌لرزه...",
                 "💥 **{boss} پاهاش رو به زمین می‌کوبه!** موجِ شوک در راهه...",
                 "🗿 **{boss} داره سنگ‌ها رو بلند می‌کنه!** زود پناه بگیرید..."],
        "enrage": "💥 **{boss} در خشمی خرد‌کننده فرو رفته!**",
        "death": ["⚙️ {boss} فرو ریخت و زمین یه لحظه ساکت شد...",
                  "💥 {boss} با ضربه‌ی آخر روی زمین افتاد!"],
    },
}


def element_fx(element: str) -> dict:
    return ELEMENT_FX.get(element) or ELEMENT_FX["arcane"]


def phase_env_line(element: str, phase_index: int, boss_name: str) -> str:
    """توصیفِ تغییرِ محیط تو فازِ ۲ و ۳ (فازِ ۱ نداره)."""
    fx = element_fx(element)
    key = "env2" if phase_index == 1 else "env3" if phase_index >= 2 else None
    return fx[key].replace("{boss}", boss_name) if key else ""


def area_warning(element: str, boss_name: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    return rng.choice(element_fx(element)["warn"]).replace("{boss}", boss_name)


def death_line(element: str, boss_name: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    return rng.choice(element_fx(element)["death"]).replace("{boss}", boss_name)


# ============================================================
#  3) هیولا (حمله‌ی ناگهانی)
# ============================================================
# traits:  evasive = ۱۵٪ جاخالی   |  armored = ۲۰٪ دمیجِ کمتر (کریت می‌شکنه)
#          frenzied = زیرِ ۳۵٪ HP خشمگین می‌شه و گاهی به حمله‌کننده ضدحمله می‌زنه
MONSTERS: dict[str, dict] = {
    "shadow_wolf":       {"name": "🐺 گرگِ سایه", "element": "void", "weak": "holy", "resist": "void",
                          "traits": ["evasive"],
                          "flavor": ["از تاریکیِ کنارِ گروه پرید بیرون!", "چشم‌های سرخش بینِ تاریکی برق زد!"]},
    "skeleton_warrior":  {"name": "💀 جنگجوی اسکلتی", "element": "void", "weak": "holy", "resist": "void",
                          "traits": ["armored"],
                          "flavor": ["استخوان‌هاش رو به هم می‌کوبه و میاد طرفتون!", "از دلِ خاک بلند شد و شمشیرِ زنگ‌زده‌ش رو کشید!"]},
    "stone_golem":       {"name": "🗿 گولمِ سنگی", "element": "physical", "weak": "lightning", "resist": "physical",
                          "traits": ["armored"],
                          "flavor": ["زمین زیرِ پاش می‌لرزه!", "از دلِ صخره‌ها بلند شد و مشت‌هاش رو بالا برد!"]},
    "abyss_ghost":       {"name": "👻 روحِ آبیس", "element": "void", "weak": "holy", "resist": "physical",
                          "traits": ["evasive", "frenzied"],
                          "flavor": ["از دیوار رد شد و وسطِ گروه سبز شد!", "ناله‌ی سردی تو هوا پیچید و سایه‌ای ظاهر شد!"]},
    "cave_spider":       {"name": "🕷 عنکبوتِ غارنشین", "element": "nature", "weak": "fire", "resist": "nature",
                          "traits": ["frenzied"],
                          "flavor": ["از سقف آویزون شد!", "تارهایی از تاریکی افتاد و هشت‌چشم برق زد!"]},
    "swamp_beast":       {"name": "🧟 غولِ باتلاق", "element": "nature", "weak": "fire", "resist": "nature",
                          "traits": ["armored"],
                          "flavor": ["بوی گند و غرشش همه‌جا پیچید!", "از دلِ گل‌ولای بلند شد و دهنش پر از جلبکه!"]},
    "armored_ancient":   {"name": "🛡 جنگجوی زره‌پوشِ باستانی", "element": "physical", "weak": "lightning", "resist": "physical",
                          "traits": ["armored", "frenzied"],
                          "flavor": ["زرهِ باستانیش با هر قدم صدای رعد می‌ده!", "تیغه‌ی غول‌پیکرش رو کشید و خیره شد بهتون!"]},
    "magma_golem":       {"name": "🌋 گولمِ مذاب", "element": "fire", "weak": "ice", "resist": "fire",
                          "traits": ["armored"],
                          "flavor": ["گدازه از شکاف‌های بدنش می‌چکه!", "زمینِ زیرِ پاش سرخ شد و دود بلند کرد!"]},
    "frost_wolf":        {"name": "🐺 گرگِ یخی", "element": "ice", "weak": "fire", "resist": "ice",
                          "traits": ["evasive"],
                          "flavor": ["از دلِ کولاک پرید بیرون!", "نفسش بخارِ یخی تو هوا ساخت و دندون نشون داد!"]},
    "storm_wraith":      {"name": "⛈ شبحِ طوفان", "element": "lightning", "weak": "nature", "resist": "lightning",
                          "traits": ["evasive"],
                          "flavor": ["با یه صاعقه وسطِ گروه فرود اومد!", "ابر سیاه شد و شبحی از دلش بیرون اومد!"]},
    "celestial_sentinel": {"name": "✨ نگهبانِ سماوی", "element": "holy", "weak": "void", "resist": "holy",
                           "traits": ["armored"],
                           "flavor": ["نورِ طلاییِ چشم‌هاش مسیرتون رو بست!", "از دلِ ستون‌های مرمر بیدار شد و نیزه‌ش رو بالا برد!"]},
    "tide_horror":       {"name": "🐙 هیولای مدّ", "element": "arcane", "weak": "lightning", "resist": "arcane",
                          "traits": ["frenzied"],
                          "flavor": ["از دلِ آب بلند شد و بازوهاش همه‌جا رو گرفت!", "موجی بلند شد و چشمِ غول‌پیکری ازش بیرون زد!"]},
}


def pick_monster(region: Optional[str], rng: random.Random | None = None,
                 has_art: Callable[[str], bool] | None = None) -> str:
    """هیولا رو بر اساسِ منطقه انتخاب می‌کنه. اگه عکسِ هیولا تو assets باشه وزنش ×۲
    (تا تا وقتی همه‌ی آرت‌ها آماده نشدن، رویدادها سینمایی‌تر باشن) — ولی هیولایی که
    به منطقه‌ش نمی‌خوره هیچ‌وقت انتخاب نمی‌شه."""
    rng = rng or random
    pool = {m: w for m, w in (REGIONS.get(region or "", {}).get("monsters") or {}).items() if m in MONSTERS}
    if not pool:
        pool = {m: 1 for m in MONSTERS}
    ids = list(pool)
    ws = []
    for m in ids:
        w = float(pool[m])
        if has_art and has_art(m):
            w *= 2.0
        ws.append(w)
    return rng.choices(ids, weights=ws, k=1)[0]


def monster_hp(n_active: int) -> int:
    """HP با تعدادِ بازیکنِ فعال می‌ره بالا (همون فرمولِ قبلی؛ سقفِ ۸ نفر)."""
    n = max(1, min(8, int(n_active)))
    return 500 + 220 * n


# ============================================================
#  4) صندوق
# ============================================================
CHEST_META: dict[str, dict] = {
    "wood_box":     {"asset": "wood",      "alt": None,   "fa": "معمولی",      "emoji": "⚪", "stars": 1},
    "bronze_box":   {"asset": "bronze",    "alt": None,   "fa": "کمیاب",       "emoji": "🟤", "stars": 2},
    "material_box": {"asset": "material",  "alt": "wood", "fa": "معمولی (متریال)", "emoji": "🌾", "stars": 1},
    "silver_box":   {"asset": "silver",    "alt": None,   "fa": "نادر",        "emoji": "⚪", "stars": 3},
    "gold_box":     {"asset": "gold",      "alt": None,   "fa": "حماسی",       "emoji": "🟡", "stars": 4},
    "lucky_box":    {"asset": "legendary", "alt": None,   "fa": "افسانه‌ای",    "emoji": "🍀", "stars": 5},
}


def chest_meta(box_id: str) -> dict:
    return CHEST_META.get(box_id) or {"asset": box_id.replace("_box", ""), "alt": None, "fa": "مرموز", "emoji": "📦", "stars": 1}


def chest_discovery_line(region: Optional[str], rng: random.Random | None = None) -> str:
    rng = rng or random
    r = REGIONS.get(region or "")
    if r and r.get("chest"):
        return rng.choice(r["chest"]) + "."
    return "یه صندوقِ اسرارآمیز وسطِ گروه افتاد."


# ============================================================
#  5) دانجن
# ============================================================
DUNGEON_TYPES: dict[str, dict] = {
    "bone_crypt": {
        "names": ["دخمه‌ی استخوان‌ها", "سردابِ شاهانِ مرده", "گورستانِ زیرزمینی"],
        "element": "void",
        "foe": ["اسکلت‌های مسلح", "جنگجوهای نیمه‌پوسیده", "استخوان‌خوارهای سایه‌دار"],
        "elite": ["شوالیه‌ی بی‌سر", "فرمانده‌ی استخوان‌ها"],
        "hazard": ["مه‌ی سرد و سمی از تابوت‌ها بلند می‌شه", "کفِ راهرو پر از استخوانِ لغزنده و گودال‌های پنهانه"],
        "trap": ["سنگ‌فرش‌های پر از تیرکِ پنهان", "تیغه‌های زنگ‌زده‌ی دیواری"],
        "treasure": ["تابوتی با جواهراتِ شاهی", "گنجینه‌ی یه پادشاهِ مرده"],
        "explore": ["نقش‌های عجیبی روی دیوارِ دخمه حک شده", "راهروی باریکی از پشتِ یه تابوتِ جابه‌جاشده پیدا شد"],
        "finds": ["طلسمِ استخوانیِ نیمه‌سوخته", "کیسه‌ی سکه‌های قدیمی", "نقشه‌ی یه تونلِ مخفی"],
        "guardian": ["پادشاهِ دخمه", "نگهبانِ ابدیِ استخوان‌ها"],
    },
    "forgotten_cathedral": {
        "names": ["کلیسای جامعِ فراموش‌شده", "کاتدرالِ زیرِ خاک", "معبدِ سکوت"],
        "element": "holy",
        "foe": ["نگهبانانِ سنگی‌شده", "ارواحِ کشیشان", "مجسمه‌های زنده"],
        "elite": ["اسقفِ سقوط‌کرده", "نگهبانِ بالدار"],
        "hazard": ["شیشه‌های رنگیِ سقف دارن فرو می‌ریزن", "نورِ خیره‌کننده‌ای از گنبد می‌تابه و چشم‌ها رو می‌سوزونه"],
        "trap": ["صفحه‌های مقدسِ فشارخور", "ناقوسِ بزرگی که با یه لمس می‌افته"],
        "treasure": ["جعبه‌ی تبرکاتِ کشیشان", "صندوقِ نذورِ باستانی"],
        "explore": ["طومارهای نیمه‌سوخته روی محرابه", "راهرویی پشتِ ارگِ بزرگ باز شده"],
        "finds": ["شمعدانِ طلایی", "طومارِ دعای فراموش‌شده", "یه تکه از شیشه‌ی رنگیِ جادویی"],
        "guardian": ["اسقفِ بی‌زمان", "نگهبانِ محرابِ آخر"],
    },
    "spider_cave": {
        "names": ["غارِ هزارچشم", "لانه‌ی تارِ سیاه", "غارِ تارتنک‌ها"],
        "element": "nature",
        "foe": ["عنکبوت‌های غارنشین", "نوزادهای تارتن", "عنکبوت‌های سمی"],
        "elite": ["عنکبوتِ شکارچیِ غول‌پیکر", "نگهبانِ تخم‌ها"],
        "hazard": ["تارهای چسبناک همه‌جا رو گرفته", "گازِ سمیِ قارچ‌ها فضا رو پر کرده"],
        "trap": ["تارهایی که به زنگوله‌های پنهان وصلن", "دامِ تارِ آویزون از سقف"],
        "treasure": ["پیله‌ای که یه صندوق توشه", "کیسه‌ی گنجِ یه شکارچیِ قدیمی تو تارها"],
        "explore": ["راهی بینِ پیله‌های بزرگ باز شده", "ردِ پاهای تازه روی تارهاست"],
        "finds": ["کیسه‌ی سکه‌ی گیرکرده تو تار", "تخمِ نادرِ درخشان", "تیرِ زهرآلودِ دست‌ساز"],
        "guardian": ["ملکه‌ی تارها", "مادرِ هزارچشم"],
    },
    "sunken_temple": {
        "names": ["معبدِ زیرِ آب", "پرستشگاهِ غرق‌شده", "معبدِ مرجانی"],
        "element": "arcane",
        "foe": ["نگهبانانِ مرجانی", "ماهی‌های ارواح", "خرچنگ‌های سنگی"],
        "elite": ["نگهبانِ سه‌شاخه‌دار", "خرچنگِ ارشدِ معبد"],
        "hazard": ["آب داره سریع بالا میاد", "جریانِ شدیدِ آب راهرو رو می‌کَنه"],
        "trap": ["دریچه‌های مخفیِ آب", "ستون‌های لغزنده‌ی پوشیده از جلبک"],
        "treasure": ["صندوقِ مرجانیِ مهروموم‌شده", "ظرفِ گوهرهای دریایی"],
        "explore": ["دالانی پشتِ مجسمه‌ی خدای دریا باز شده", "نقش‌های درخشانی روی دیوارِ معبد"],
        "finds": ["مرواریدِ سیاه", "نقشه‌ی دریایی کهنه", "تکه‌ای از مجسمه‌ی طلاییِ خدا"],
        "guardian": ["لویاتانِ معبد", "نگهبانِ مرواریدِ سیاه"],
    },
    "abandoned_tower": {
        "names": ["برجِ شکسته", "برجِ متروکِ جادوگران", "دیده‌بانیِ فراموش‌شده"],
        "element": "arcane",
        "foe": ["نگهبانانِ زره‌پوش", "گارگویل‌های سنگی", "جادوگرانِ مرده"],
        "elite": ["جادوگرِ ارشدِ فراموش‌شده", "فرماندهِ برج"],
        "hazard": ["پله‌ها زیرِ پاتون فرو می‌ریزه", "باد سرد از شکاف‌ها می‌پیچه و سقف داره می‌ریزه"],
        "trap": ["پله‌های مکانیکیِ فعال", "طلسم‌های محافظ روی در"],
        "treasure": ["کتابخونه‌ی جادوگرِ برج", "گاوصندوقِ آهنیِ فرمانده"],
        "explore": ["پله‌ی مخفی‌ای پشتِ یه قفسه‌ی کتاب باز شده", "تلسکوپِ قدیمی نقشه‌ای رو نشون می‌ده"],
        "finds": ["کتابِ جادوی نیمه‌سوخته", "کلیدِ برنجیِ عجیب", "کریستالِ نورانی"],
        "guardian": ["نگهبانِ قله", "جادوگرِ تاجدار"],
    },
    "shadow_labyrinth": {
        "names": ["هزارتوی سایه‌ها", "تونلِ سایه‌ها", "هزارتوی بی‌پایان"],
        "element": "void",
        "foe": ["سایه‌های خزنده", "گرگ‌های تاریکی", "پژواک‌های ناقصِ آدم‌ها"],
        "elite": ["ردیابِ سایه‌ها", "ارباب مسیرهای گمشده"],
        "hazard": ["دیوارها دارن جابه‌جا می‌شن", "تاریکی‌ای که نورِ مشعل رو می‌بلعه"],
        "trap": ["آینه‌های فریب‌دهنده", "دیوارهای متحرکِ قاتل"],
        "treasure": ["صندوقی که از سایه ساخته شده", "گنجی که تو هزارتو گم شده بود"],
        "explore": ["مسیری که روی دیوار با گچ علامت‌گذاری شده", "صدایی از دوردست‌ها شما رو صدا می‌زنه"],
        "finds": ["نقشه‌ی ناتمامِ هزارتو", "فانوسِ بی‌نورِ جادویی", "سکه‌ی سایه‌ای"],
        "guardian": ["مینوتورِ سایه", "فرمانروای هزارتو"],
    },
    "ancient_forge": {
        "names": ["کارگاهِ متروکِ آهنگران", "کوره‌ی دفن‌شده‌ی باستانی", "آهنگریِ زیرزمینی"],
        "element": "fire",
        "foe": ["گولم‌های آهنی", "آهنگرهای زنده‌ی مرده", "جرقه‌های جان‌گرفته"],
        "elite": ["استادِ آهنگرِ مذاب", "گولمِ سرِ کوره"],
        "hazard": ["گدازه از شکاف‌های کف بالا میاد", "بخارِ داغ از لوله‌ها فوران می‌کنه"],
        "trap": ["چکش‌های خودکارِ آهنین", "سنگ‌های داغِ فشاری"],
        "treasure": ["صندوقِ فولادیِ آهنگرِ بزرگ", "شمش‌های نایابِ آماده‌ی ریخته‌گری"],
        "explore": ["دالانی پشتِ کوره‌ی خاموش باز شده", "آتشی هنوز تو یه کوره‌ی دورافتاده زنده‌ست"],
        "finds": ["شمشِ فولادِ نایاب", "نقشه‌ی یه سلاحِ افسانه‌ای", "چکشِ کوچکِ جادویی"],
        "guardian": ["جاگرنات کوره", "نگهبانِ آتشِ ابدی"],
    },
}

REGION_DEFAULT_DUNGEON = {"bone_crypt": 2, "forgotten_cathedral": 1, "spider_cave": 1,
                          "sunken_temple": 1, "abandoned_tower": 1, "shadow_labyrinth": 1, "ancient_forge": 1}


def pick_dungeon(region: Optional[str], rng: random.Random | None = None) -> tuple[str, str]:
    """(dungeon_type, نام). نوعِ دانجن با منطقه‌ی رویداد می‌خونه (فورج تو دره‌ی آتش، معبدِ غرق‌شده تو دریا...)."""
    rng = rng or random
    pool = {t: w for t, w in (REGIONS.get(region or "", {}).get("dungeons") or {}).items() if t in DUNGEON_TYPES}
    pool = pool or REGION_DEFAULT_DUNGEON
    ids, ws = zip(*pool.items())
    dtype = rng.choices(ids, weights=ws, k=1)[0]
    return dtype, rng.choice(DUNGEON_TYPES[dtype]["names"])


def guardian_for(region: Optional[str], dtype: str, rng: random.Random | None = None) -> tuple[str, str]:
    """نگهبانِ نهاییِ دانجن: اگه map_boss_pool برای منطقه «harbinger» داشت از همون (اسم/لقبِ واقعیِ بازی)،
    وگرنه از فهرستِ نوعِ دانجن. خروجی: (اسمِ نمایشی با ایموجی، لقب)."""
    rng = rng or random
    for e in MAP_BOSS_POOL.get(region or "", []):
        if e.get("tier") == "harbinger":
            return f"{e.get('emoji', '👑')} {e['name']}", e.get("epithet", "")
    names = DUNGEON_TYPES.get(dtype, DUNGEON_TYPES["bone_crypt"])["guardian"]
    return f"👑 {rng.choice(names)}", "نگهبانِ اتاقِ آخر"


# ─── اتاق‌ها ────────────────────────────────────────────────
ROOM_TYPES: dict[str, dict] = {
    "combat":   {"emoji": "⚔️", "fa": "نبرد",          "w": 3.0, "diff": 0.00},
    "trap":     {"emoji": "🕳", "fa": "تله",           "w": 2.0, "diff": 0.00},
    "explore":  {"emoji": "🧭", "fa": "کاوش",          "w": 2.0, "diff": 0.00},
    "treasure": {"emoji": "💰", "fa": "گنج",           "w": 1.5, "diff": 0.00},
    "elite":    {"emoji": "💀", "fa": "هیولای قدرتمند", "w": 1.2, "diff": 0.08},
    "hazard":   {"emoji": "☣️", "fa": "خطرِ محیطی",    "w": 2.0, "diff": 0.03},
}

# هر الگو: (متن، بهترین، قابل‌قبول). عمداً «بهترین» تو الگوهای مختلفِ یه نوع فرق می‌کنه
# تا جوابِ درست هر بار همون گزینه‌ی اول نباشه.
_ROOM_TEMPLATES: dict[str, list] = {
    "combat": [
        ("{foe} راهتون رو بسته و آماده‌ی حمله‌ست!", "fight", "guard"),
        ("{foe} از دو طرف محاصره‌تون می‌کنن؛ جایی برای عقب‌نشینی نیست!", "guard", "fight"),
        ("{foe} هنوز متوجه‌تون نشدن و دارن گشت می‌زنن...", "search", "fight"),
    ],
    "trap": [
        ("{trap} — صدای تیک‌تیکِ یه مکانیزم میاد...", "search", "guard"),
        ("{trap} ناگهان فعال شد و همه‌چی داره فرو می‌ریزه!", "guard", "search"),
        ("یه مکانیزمِ زنگ‌زده با اهرم‌های کلفت راهتون رو بسته؛ شاید بشه خرابش کرد!", "fight", "search"),
    ],
    "explore": [
        ("{explore}.", "search", "guard"),
        ("راهرو دو شاخه می‌شه و از یکی‌شون صدای غرش میاد...", "guard", "search"),
        ("ردِ پاهای تازه روی زمینه؛ کسی یا چیزی قبل از شما اینجا بوده...", "search", "fight"),
    ],
    "treasure": [
        ("{treasure} وسطِ اتاقه؛ همه‌چی آرومه... زیادی آروم.", "search", "guard"),
        ("{treasure}؛ ولی از داخلش صدای خرناسه میاد — می‌میکه!", "fight", "guard"),
        ("{treasure} زیرِ سقفی که هر لحظه خاک می‌ریزه افتاده.", "guard", "search"),
    ],
    "elite": [
        ("{elite} با نگاهی خونین جلوتونه — از موجودات معمولی خیلی قوی‌تره!", "guard", "fight"),
        ("{elite} از قبل منتظرتون بود و حمله رو شروع می‌کنه!", "fight", "guard"),
        ("{elite} یه نقطه‌ضعفِ پنهان داره؛ دنبالِ شکافِ زره‌ش بگردین...", "search", "fight"),
    ],
    "hazard": [
        ("{hazard}!", "guard", "search"),
        ("{hazard} و مسیرِ امن معلوم نیست!", "search", "guard"),
        ("{hazard}؛ باید یه‌جوری از میونش رد بشین!", "fight", "guard"),
    ],
}

_OK_TEXT = {
    "combat":   {"fight": "⚔️ ضربه‌ها دقیق نشست و دشمن‌ها عقب نشستن!", "guard": "🛡 دفاعِ محکم دشمن رو خسته کرد.", "search": "🔍 نقطه‌ضعفشون رو پیدا کردین!"},
    "trap":     {"search": "🔍 مکانیزم رو پیدا کردین و از کار انداختینش!", "guard": "🛡 سپرها رو بالا گرفتین و تله روتون اثری نذاشت.", "fight": "⚔️ مکانیزم رو خرد کردین!"},
    "explore":  {"search": "🔍 مسیرِ درست رو پیدا کردین!", "guard": "🛡 محتاطانه پیش رفتین و همه‌چی امن بود.", "fight": "⚔️ هرچی سد کرده بود کنار زدین."},
    "treasure": {"search": "🔍 با دقت بازش کردین و گنج مالِ شماست!", "guard": "🛡 سقف رو نگه داشتین و گنج رو بیرون کشیدین!", "fight": "⚔️ میمیک رو کشتین و گنجش رو برداشتین!"},
    "elite":    {"fight": "⚔️ قوی‌ترین ضربه رو زدین و غول به زانو افتاد!", "guard": "🛡 ضربه‌هاش رو جذب کردین و بعد پس‌زدینش!", "search": "🔍 نقطه‌ضعفِ زره‌ش رو پیدا کردین و کارش تموم شد!"},
    "hazard":   {"guard": "🛡 دسته با هم جمع شد و خطر رو رد کردین.", "search": "🔍 مسیرِ امن رو پیدا کردین!", "fight": "⚔️ راهی از میون خطر باز کردین!"},
}
_FAIL_TEXT = {
    "combat":   "💥 دشمن‌ها زدنتون و عقب‌نشینی کردین!",
    "trap":     "💥 تله فعال شد و دسته آسیب دید!",
    "explore":  "💥 تو مسیرِ اشتباه افتادین و کلی وقت و جون از دست دادین!",
    "treasure": "💥 گنج یه دام بود و آسیب خوردین!",
    "elite":    "💥 هیولا دسته رو درهم کوبید!",
    "hazard":   "💥 خطر شما رو غافلگیر کرد!",
}


def room_fail_text(rtype: str) -> str:
    return _FAIL_TEXT.get(rtype, "💥 اتاق رو با زور رد کردین و آسیب دیدین!")


def room_ok_text(rtype: str, action: str) -> str:
    return _OK_TEXT.get(rtype, {}).get(action, "✅ موفق شدین!")


def make_room(dtype: str, rtype: str, rng: random.Random | None = None) -> dict:
    rng = rng or random
    v = DUNGEON_TYPES.get(dtype, DUNGEON_TYPES["bone_crypt"])
    meta = ROOM_TYPES[rtype]
    text, best, ok = rng.choice(_ROOM_TEMPLATES[rtype])
    text = text.format(
        foe=rng.choice(v["foe"]), elite=rng.choice(v["elite"]), hazard=rng.choice(v["hazard"]),
        trap=rng.choice(v["trap"]), treasure=rng.choice(v["treasure"]), explore=rng.choice(v["explore"]))
    return {"type": rtype, "emoji": meta["emoji"], "label": meta["fa"], "text": text,
            "best": best, "ok": ok, "diff": meta["diff"]}


def plan_rooms(dtype: str, rng: random.Random | None = None, n: int = 3) -> list[dict]:
    """n اتاقِ تصادفی (اتاقِ آخر همیشه نگهبانِ نهاییه و جدا مدیریت می‌شه).
    قانون‌ها: دو اتاقِ هم‌نوعِ پشت‌سرهم نه، حداکثر یه اتاقِ گنج و یه اتاقِ قدرتمند."""
    rng = rng or random
    rooms: list[dict] = []
    for _ in range(n):
        weights = {}
        for t, m in ROOM_TYPES.items():
            if rooms and rooms[-1]["type"] == t:
                continue
            if t in ("treasure", "elite") and any(r["type"] == t for r in rooms):
                continue
            weights[t] = m["w"]
        ts, ws = zip(*weights.items())
        rooms.append(make_room(dtype, rng.choices(ts, weights=ws, k=1)[0], rng))
    return rooms


# ─── نگهبانِ نهایی: ۳ دورِ رأی‌گیری (جایگزینِ سبکِ یه موتورِ نبردِ کامل) ───
_FINAL_ROUNDS = [
    [("🛡 **{boss}** زره‌ی سنگینش رو بالا گرفته — ضربه‌ی معمولی خراشی هم روش نمی‌ندازه!", "search", "fight"),
     ("🪞 **{boss}** هر ضربه‌ای رو بازتاب می‌ده؛ باید یه شکافِ پنهان پیدا کرد!", "search", "guard")],
    [("🌊 **{boss}** داره یه ضربه‌ی ناحیه‌ایِ ویرانگر آماده می‌کنه — همه‌ی دسته تو خطره!", "guard", "search"),
     ("⚡ **{boss}** با یه حمله‌ی سریع همه رو محاصره کرد — فقط جمع‌شدن کنار هم نجات می‌ده!", "guard", "fight")],
    [("💢 **{boss}** خشمگینه و با تمامِ توان حمله می‌کنه — آخرین فرصتتونه!", "fight", "guard"),
     ("🔥 **{boss}** زخمیه و دیوانه‌وار می‌کوبه؛ یه ضربه‌ی کاری تمومش می‌کنه!", "fight", "search")],
]


def final_round(round_index: int, boss_name: str, rng: random.Random | None = None) -> dict:
    rng = rng or random
    text, best, ok = rng.choice(_FINAL_ROUNDS[max(0, min(2, round_index))])
    return {"type": "final", "emoji": "👑", "label": f"نگهبانِ نهایی — دورِ {round_index + 1}",
            "text": text.replace("{boss}", boss_name), "best": best, "ok": ok, "diff": 0.10}


# ─── رأی‌گیری و فرمولِ موفقیت ────────────────────────────────
def tally_votes(votes: dict, rng: random.Random | None = None) -> tuple[Optional[str], dict, bool]:
    """(انتخابِ دسته، شمارش، اجماع؟). اجماع = حداقل ۷۵٪ رأی‌ها یکی بودن (و حداقل ۲ رأی)."""
    rng = rng or random
    tally: dict[str, int] = {}
    for a in votes.values():
        tally[a] = tally.get(a, 0) + 1
    if not tally:
        return None, tally, False
    top = max(tally.values())
    choice = rng.choice(sorted(a for a, c in tally.items() if c == top))
    consensus = len(votes) >= 2 and top / len(votes) >= 0.75
    return choice, tally, consensus


def success_chance(room: dict, choice: Optional[str], n: int, avg_power: float, ref_power: float,
                   consensus: bool) -> float:
    """احتمالِ موفقیتِ یه اتاق. ساده و قابل‌فهم:
        بهترین گزینه ۸۵٪ | گزینه‌ی قابل‌قبول ۶۲٪ | بد ۳۲٪ | هیچ‌کس رأی نداد ۲۵٪
        + تیم‌ورک (هر نفرِ بیشتر از ۲ تا: +۱٫۵٪، سقف +۹٪)
        + قدرتِ دسته نسبت به منطقه (±۱۰٪) + اجماع (+۴٪)
        − سختیِ اتاق (قدرتمند −۸٪، نگهبان −۱۰٪، خطرِ محیطی −۳٪)"""
    if choice is None:
        base = 0.25
    elif choice == room["best"]:
        base = 0.85
    elif choice == room.get("ok"):
        base = 0.62
    else:
        base = 0.32
    team = min(0.09, 0.015 * max(0, n - 2))
    strength = 0.0
    if ref_power > 0 and avg_power > 0:
        strength = max(-0.10, min(0.10, (avg_power / ref_power - 1.0) * 0.12))
    cons = 0.04 if consensus else 0.0
    p = base + team + strength + cons - room.get("diff", 0.0)
    return max(0.08, min(0.95, p))


def vote_bar(tally: dict) -> str:
    parts = [f"{ACTIONS[a]} {tally[a]}" for a in ("fight", "guard", "search") if tally.get(a)]
    return " | ".join(parts) if parts else "—"


def lives_bar(lives: int, total: int = 3) -> str:
    return "❤️" * max(0, lives) + "🖤" * max(0, total - max(0, lives))
