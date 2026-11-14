"""Bilingual intent router: text -> (registry code, arg). Typo tolerant."""
import difflib
import time

from database import col
from security import normalize_text

# intent -> (code, arg, synonyms)
RAW = {
    "casino": ("cas", "", ["کازینو", "قمار", "casino", "gamble"]),
    "bank": ("bnk", "", ["بانک", "گاوصندوق", "bank", "vault"]),
    "home": ("home", "", ["دنیای من", "جهان من", "خانه", "پنل اصلی", "پنل", "منو", "همه چیز", "همه‌چیز", "سنکا", "سِنکا", "home", "my world", "menu", "main", "everything", "senka", "panel", "start", "شروع"]),
    "profile": ("prof", "", ["پروفایل", "مشخصات", "کاراکتر من", "profile", "me", "stats", "character"]),
    "explore": ("exp", "", ["گشت", "گشت و گذار", "گشت‌وگذار", "کاوش", "explore", "patrol", "wander"]),
    "adventure": ("map", "", ["ماجراجویی", "نقشه", "مکان", "adventure", "map", "travel", "location"]),
    "bag": ("bag", "0", ["کوله", "کیف", "اینونتوری", "انبار", "bag", "inventory", "items", "backpack"]),
    "sword": ("znp", "", ["شمشیر من", "سلاح", "زانپاکتو", "دنیای درون شمشیر", "my sword", "weapon", "zanpakuto", "sword spirit"]),
    "zanpakuto": ("znp", "", ["روح شمشیر", "روح زانپاکتو", "zanpakuto spirit", "blade spirit"]),
    "race_path": ("rpath", "", ["مسیر نژاد", "تکامل نژاد", "race path", "race evolution"]),
    "kido": ("kidop", "", ["کیدو", "کیدوها", "آموزش کیدو", "باکودو", "هادو", "bakudo", "bakudō", "hado", "hadō", "kido", "kidō", "kido spells", "spells"]),
    "faction": ("fctp", "", ["سازمان", "عضویت سازمان", "گوتی ۱۳", "وندن‌رایش", "faction", "organization", "gotei 13", "espada", "wandenreich"]),
    "senkaimon": ("skm", "", ["سنکایمون", "دروازه", "پورتال", "senkaimon", "gate", "portal"]),
    "bleach_hub": ("blhub", "", ["جهان بلیچ", "سیستم های بلیچ", "bleach", "bleach systems"]),
    "racepath": ("rpath", "", ["مسیر نژاد", "تکامل نژاد", "race path", "race evolution path"]),
    "market": ("mkt", "", ["بازار", "بازارچه", "market", "shop", "store", "trade"]),
    "battle": ("bt", "", ["نبرد", "مبارزه", "جنگ", "حمله", "battle", "fight", "combat", "attack"]),
    "squad": ("gld", "", ["جوخه", "گیلد", "کلن", "squad", "guild", "clan"]),
    "ranking": ("rnk", "", ["رتبه بندی", "رتبه‌بندی", "لیدربورد", "جدول", "ranking", "leaderboard", "rank", "top"]),
    "quests": ("qst", "", ["ماموریت", "مأموریت", "ماموریت ها", "مأموریت‌ها", "کار", "quests", "quest", "missions", "tasks"]),
    "daily": ("dly", "", ["جایزه روزانه", "روزانه", "جایزه", "daily", "daily reward", "reward", "bonus"]),
    "gacha": ("gch", "", ["احضار", "گاچا", "summon", "gacha", "pull", "banner"]),
    "mini": ("mgm", "", ["مینی گیم", "مینی‌گیم", "بازی", "معما", "minigame", "mini game", "games", "puzzle", "quiz"]),
    "dungeon": ("dgn", "", ["دانجن", "سیاهچال", "زندان", "dungeon", "dungeons", "raid"]),
    "settings": ("set", "", ["تنظیمات", "زبان", "settings", "language", "options", "lang"]),
    "help": ("hlp", "", ["راهنما", "کمک", "help", "guide", "how to play", "؟", "?"]),
    "boss": ("bossinfo", "", ["باس", "باس جهانی", "boss", "world boss"]),
    "admin": ("adm", "", ["مدیریت", "ادمین", "admin", "panel admin", "dashboard"]),
    "forge": ("frg", "", ["آهنگری", "فورج", "تقویت سلاح", "forge", "smith", "blacksmith", "upgrade weapon"]),
    "party": ("pty", "0", ["تیم", "پارتی", "همراهان", "party", "team", "companions"]),
    "commands": ("cmd", "", ["دستورات", "لیست دستورات", "فرمان ها", "فرمان‌ها", "commands", "command list", "cmds", "words"]),
    "world": ("wrd", "", ["دنیا", "جهان زنده", "وضعیت دنیا", "world", "world state", "realm"]),
    "craft": ("crf", "", ["ساخت", "کرافت", "craft", "crafting", "workshop"]),
    "season": ("ssn", "", ["فصل", "season", "seasons"]),
    "chronicle": ("chr", "", ["تاریخچه", "وقایع", "chronicle", "news"]),
    "territory": ("ter", "", ["قلمرو", "territory", "land"]),
    "bounty": ("bty", "", ["باونتی", "جایزه سر", "bounty", "wanted"]),
    "gear": ("eqp", "", ["یادگار", "همراه من", "relic", "relics", "pets", "pet"]),
    "evolution": ("evo", "", ["تکامل", "evolution", "evolve"]),
    "tower": ("twr", "", ["برج", "برج روح", "tower", "soul tower", "spire"]),
    "dispatch": ("dsp", "", ["اعزام", "ماموریت اعزام", "dispatch", "send squad", "expedition"]),
    "wheel": ("whl", "", ["چرخ", "چرخ شانس", "چرخ اوراهارا", "wheel", "spin", "lucky wheel"]),
    "seat": ("sat", "", ["درجه", "درجه گوتی", "کرسی", "seat", "my seat", "gotei seat"]),
    "inner": ("inr", "", ["دنیای درون", "درون", "inner world", "inner", "spirit talk"]),
    "artifact": ("art", "", ["آرتیفکت", "آرتیفکت من", "گنجینه", "گنجینه من", "artifact", "my artifact", "treasure"]),
    "artifact_reg": ("arr", "", ["ثبت نامه آرتیفکت", "ثبت‌نامه آرتیفکت‌ها", "ثبتنامه گنجینه ها", "artifact registry", "registry"]),
    "artifact_mkt": ("axm", "0", ["بازار آرتیفکت", "artifact market", "artifact exchange", "exchange"]),
    "upgrade": ("upg", "", ["ارتقا", "ارتقای استت", "ارتقا استت", "upgrade", "upgrade stats", "stat points"]),
    "division": ("div", "", ["وابستگی", "جوخه من", "مقام", "اسپادا", "division", "allegiance", "my division"]),
    "hollow": ("hlf", "", ["هالوفیکیشن", "ویزورد شدن", "ماسک هالو", "hollowfication", "become visored", "hollow mask"]),
    "event": ("evt", "", ["رویداد", "رویداد جهانی", "event", "world event"]),
    "shop": ("shp", "0", ["فروشگاه", "اوراهارا", "فروشگاه اوراهارا", "urahara shop", "urahara", "npc shop"]),
    "listings": ("mkb", "0", ["بازار بازیکنان", "آگهی ها", "آگهی‌ها", "player market", "listings", "marketplace"]),
    "auction": ("mka", "0", ["حراج", "حراجی", "auction", "auctions", "bids"]),
    "mylistings": ("mkm", "", ["آگهی من", "آگهی های من", "آگهی‌های من", "my listings", "my ads", "my sales"]),
    "pets": ("pet", "0", ["حیوانات", "حیوان همراه", "my pets", "pets list", "companion pets"]),
    "cosmetics": ("cos", "", ["ظاهر", "کاسمتیک", "عنوان ها", "عنوان‌ها", "cosmetics", "my cosmetics", "titles"]),
    "potions": ("crp", "", ["معجون", "ساخت معجون", "potions", "craft potions", "brew"]),
    "keys": ("crk", "0", ["کلید", "ساخت کلید", "کلید دانجن", "dungeon keys", "craft keys", "keys"]),
    "towertop": ("twl", "", ["رتبه برج", "برترین برج", "برترین‌های برج", "tower top", "tower leaderboard", "tower ranks"]),
    "here": ("hre", "", ["اینجا", "اینجا کیه", "همین جا", "here", "who is here", "around me"]),
    "armor": ("crv", "", ["زره", "آبدیده", "تقویت زره", "armor", "armour", "temper armor"]),
    "pvptop": ("rnk", "pvp", ["رتبه دوئل", "برترین دوئل", "pvp top", "pvp ranking", "duel ranking"]),
    "leveltop": ("rnk", "lvl", ["رتبه سطح", "برترین سطح", "level top", "level ranking", "top levels"]),
    "consumables": ("bag", "0:u", ["مصرفی", "مصرفی ها", "مصرفی‌ها", "consumables", "my consumables", "usables"]),
    "mygear": ("bag", "0:e", ["تجهیزات من", "تجهیزات", "equipment", "my equipment", "equipment bag"]),
    "admin_world": ("adw", "", ["مدیریت دنیا", "admin world", "aworld"]),
    "admin_users": ("adu", "", ["مدیریت کاربران", "admin users", "ausers"]),
    "admin_settings": ("ads", "0", ["مدیریت تنظیمات", "admin settings", "asettings"]),
    "admin_announce": ("adc", "", ["اعلان همگانی", "announce", "admin broadcast"]),
    "admin_log": ("adl", "", ["لاگ مدیریت", "admin log", "alog"]),
    "admin_admins": ("ada", "", ["لیست ادمین ها", "لیست ادمین‌ها", "admin list", "aadmins"]),
    "duel": ("*duel", "r", ["دوئل", "دوئل رنکد", "duel", "ranked duel", "challenge"]),
    "duel_friendly": ("*duel", "f", ["دوئل دوستانه", "friendly duel", "friendly"]),
}
# one travel intent per location, so every place gets its own word and /go_<place> command
from data_races import LOCATIONS as _LOCS
for _k, _l in _LOCS.items():
    RAW["go_" + _k] = ("tr", _k, ["برو " + _l["fa"], "سفر به " + _l["fa"], "go " + _l["en"].lower(), "travel " + _k])
# --- NEW BLEACH VIRAL SYSTEM: plain-word group mechanics (reply-based words are handled in handlers_viral.viral_hook) ---
RAW.update({
    "bankai_word": ("bkw", "b", ["بانکای", "bankai"]),
    "shikai_word": ("bkw", "s", ["شایکای", "shikai"]),
    "mask_word": ("mkw", "", ["ماسک", "mask"]),
    "bleach_status": ("bst", "", ["وضعیت", "ریاتسو", "reiatsu", "status"]),
    "steal_hogyoku": ("hgs", "", ["دزدی", "خیانت", "betray"]),
    "wanted_list": ("wnt", "", ["لیست تحت تعقیب", "تحت تعقیب", "wanted list"]),
    "espada_board": ("esp", "", ["جدول اسپادا", "اسپادا ۰ تا ۹", "espada board"]),
})
GROUP_OK = {"duel", "duel_friendly", "boss", "battle", "kido", "help", "home", "chronicle", "commands", "event",
            "bankai_word", "shikai_word", "mask_word", "bleach_status", "steal_hogyoku", "wanted_list", "espada_board"}
_map: dict = {}
_extra_at = 0.0


def _build(extra=None):
    m = {}
    for name, (code, arg, words) in RAW.items():
        for w in words:
            m[normalize_text(w)] = (name, code, arg)
    for name, words in (extra or {}).items():
        if name in RAW:
            code, arg, _ = RAW[name]
            for w in words:
                m[normalize_text(w)] = (name, code, arg)
    return m


_map = _build()


async def refresh():
    global _map, _extra_at
    if time.monotonic() - _extra_at < 60:
        return
    _extra_at = time.monotonic()
    extra = {}
    try:
        async for d in col("intents").find({}):
            extra[d["action"]] = d.get("words", [])
    except Exception:
        pass
    _map = _build(extra)


async def resolve(text: str):
    """Return (intent name, code, arg) or None."""
    await refresh()
    n = normalize_text(text)
    if not n or len(n) > 40:
        return None
    hit = _map.get(n)
    if hit:
        return hit
    if len(n) >= 4:
        close = difflib.get_close_matches(n, list(_map.keys()), n=1, cutoff=0.84)
        if close:
            return _map[close[0]]
    return None


def word_for(intent: str) -> str:
    """First ASCII synonym of an intent (used to run /commands through the same router)."""
    for w in RAW[intent][2]:
        if w.isascii():
            return w
    return RAW[intent][2][0]
