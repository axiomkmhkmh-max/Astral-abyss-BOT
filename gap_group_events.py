# ============================================================
#  ASTRAL ABYSS — Gap Group Events 👹📦🚪  (نسخه‌ی «غوطه‌وری عمیق»)
# ------------------------------------------------------------
#  رویدادهای گروهیِ گپ حالا به دنیای بازی وصلن:
#
#   🌍 منطقه‌ی رویداد — از player["map"] بازیکن‌های فعالِ گروه (اکثریت) انتخاب می‌شه؛
#                       باس، هیولا، صندوق و دانجن همه با همون منطقه هماهنگن
#                       (دره‌ی آتش → باسِ آتشی/فورج/گولمِ مذاب، قلمروی یخ → ملکه‌ی یخ/...).
#                       نه GPS، نه موقعیتِ واقعیِ گروه؛ و بازیکن مجبور نیست جابه‌جا بشه.
#   🖼 تصویر         — هر رویداد یه «صحنه»‌ی سینمایی داره (gap_event_media). عکس و متن
#                       دو پیامِ جدا ان (عکس بدونِ دکمه، متن با دکمه) چون API گپ ادیتِ
#                       پیامِ عکس‌دار رو مستند نکرده؛ اگه عکس نبود/آپلود خطا داد → فقط متن.
#   👹 باسِ گروهی    — همون boss_engine (فازها، سپر، حمله‌ی ناحیه‌ای، خشم، پاداش)
#                       + عکسِ هر فاز، اعلانِ دقیقاً-یک‌بارِ تغییرِ فاز، هشدارهای عنصری،
#                       پنجره‌ی آسیب‌پذیری بعد از شکستنِ سپر، صحنه‌ی مرگ + MVP.
#   📦 صندوق         — ۳ مرحله: کشف ← باز کردن (رزروِ امنِ اسلات) ← نمایش (عکسِ باز)
#   🐺 حمله‌ی هیولا   — ضعف/مقاومتِ عنصری، ویژگی‌های رفتاری، لیدربوردِ زنده
#   🚪 دانجن         — ۳ اتاقِ تصادفی (۶ نوع) + نگهبانِ نهایی (۳ دورِ رأی‌گیری)،
#                       پاداش بر اساسِ عملکرد و مشارکت، MVP، کشفیاتِ پنهان
#
#  دستورها (فقط تو گروه، مگه اینکه نوشته باشه):
#     /graid [force [id|منطقه]]   شروع/نمایشِ رِیدِ باسِ گروه (force فقط ادمینِ ربات)
#     /gevents [on|off]           وضعیتِ رویدادهای خودکار + منطقه‌ی غالبِ گروه
#     /gdrop <box|ambush|dungeon|boss> [منطقه]   (ادمینِ ربات) اجبارِ یه رویداد
#     /gassets                    (ادمینِ ربات) گزارشِ پوششِ آرتِ رویدادها
#
#  وصل‌کردن: bot_dual.py →  register_gap_group_events_handlers(dp)   (بدونِ تغییر)
#  تنظیماتِ عددی (فاصله‌ها، شانس‌ها، پاداش‌ها) بالای فایل تو CFG ـه.
# ============================================================
from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone

from gap_types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from gap_group_gate import is_group_msg, group_word

import boss_engine as be
import lootbox_shop as ls
import gap_event_world as gw
import gap_event_media as gm
from characters import ALL_CHARACTERS
from database import get_db, aget_player, asave_player, player_lock
from katana_system import dmg_bonus, crit_bonus, lifesteal_bonus, element_amplify_bonus
from logger import log_sync

# ─── تنظیماتِ قابل‌تغییر ─────────────────────────────────────────
CFG = {
    "tick_sec": 15,                 # (قدیمی — نگه داشته شده برای سازگاری)
    "boss_tick_sec": 5,             # واچرِ باس (سپر/ناحیه‌ای/خشم) هر چند ثانیه
    "scheduler_tick_sec": 60,       # زمان‌بندیِ رویدادهای خودکار هر چند ثانیه
    "active_window_sec": 15 * 60,   # «گروهِ فعال» = تو این بازه حداقل یه پیام
    "recent_members_sec": 2 * 3600,  # اعضای «اخیر» برای محاسبه‌ی تعدادِ بازیکن
    "region_sample_max": 12,        # برای تشخیصِ منطقه حداکثر چند بازیکنِ اخیر خونده می‌شن
    "min_recent_members": 2,        # کمتر از این → رویدادِ خودکار نمی‌یاد
    "boss_min_members": 3,          # باسِ خودکار فقط تو گروه‌های شلوغ‌تر
    "interval_min_sec": 25 * 60,    # فاصله‌ی دو رویدادِ خودکارِ یه گروه
    "interval_max_sec": 50 * 60,
    "first_delay_sec": (4 * 60, 12 * 60),  # اولین رویداد بعد از «فعال‌شدنِ» گروه
    "max_events_per_day": 10,
    # وزنِ نوعِ رویدادها
    "weights": {"box": 40, "ambush": 30, "dungeon": 20, "boss": 10},
    # صندوق
    "box_ttl_sec": 10 * 60,
    "box_party_slots": 4,           # صندوق‌های ارزون: چند نفر اول هرکدوم یه باکس
    "box_pool": [("wood_box", 40), ("bronze_box", 30), ("material_box", 12),
                 ("silver_box", 12), ("gold_box", 5), ("lucky_box", 1)],
    "box_race": {"silver_box", "gold_box", "lucky_box"},   # فقط ۱ برنده
    "box_min_level": 3,
    "box_daily_cap": 10,            # سقفِ باکسِ رایگانِ هر بازیکن در روز (کلِ گروه‌ها)
    # حمله‌ی هیولا
    "ambush_ttl_sec": 6 * 60,
    "ambush_hit_cd_sec": 4,
    "ambush_edit_gap_sec": 6,       # لیدربوردِ زنده حداکثر هر چند ثانیه یه‌بار ادیت می‌شه
    "ambush_dodge_chance": 0.15,    # ویژگیِ evasive
    "ambush_armor_mult": 0.80,      # ویژگیِ armored (کریت رد می‌کنه)
    "ambush_frenzy_hp_pct": 0.35,   # ویژگیِ frenzied: زیرِ این درصدِ HP
    "ambush_frenzy_counter": 0.25,  # شانسِ ضدحمله به حمله‌کننده
    "ambush_frenzy_dmg_pct": 0.06,  # درصدی از max_hp حمله‌کننده (حداقل HP=1)
    "ambush_weak_mult": 1.5,
    "ambush_resist_mult": 0.75,
    # دانجن
    "dungeon_join_sec": 90,
    "dungeon_room_sec": 25,
    "dungeon_max_party": 8,
    "dungeon_min_party": 2,
    "dungeon_lives": 3,
    "dungeon_random_rooms": 3,      # + یه اتاقِ نگهبانِ نهایی (۳ دور) = ساختارِ ۴ اتاقه
    "dungeon_room_images": 1,       # حداکثر چند عکسِ اتاق (به‌جز ورودی و نگهبانِ نهایی)
    "dungeon_bonus_cap": 0.18,      # سقفِ پاداشِ اضافه از کشفیات/غنیمت‌ها (+۶٪ هر کدوم)
    "dungeon_guard_save": 0.55,     # شانسِ اینکه «دفاع» تو شکست جونی ازت کم نکنه
    # باس
    "boss_hit_cd_sec": 8,
    "boss_respawn_cd_sec": 10 * 60,  # بعد از کشتنِ باس، تا رِیدِ بعدی (مثلِ نسخه‌ی تلگرام)
    "boss_ttl_sec": 2 * 3600,       # باسی که تو این مدت کشته نشه ناپدید می‌شه (بدونِ پاداش)
    "passive_retaliation": True,    # ضدحمله‌ی پایه‌ی boss_engine (مثلِ تلگرام)
    "passive_msg_min_gap_sec": 45,  # پیامِ ضدحمله حداکثر هر ۴۵ ثانیه (آسیب بی‌صدا هم اعمال می‌شه)
}

MSG_NOT_GROUP = "👥 این دستور فقط داخلِ یه **گروه** کار می‌کنه."
MSG_NEED_START = "❌ اول تو پیوی ربات /start بزن و کاراکتر بساز، بعد بیا گروه!"
ACTIONS = gw.ACTIONS

# ─── وضعیتِ درون‌حافظه‌ای ────────────────────────────────────────
# چی persist می‌شه؟ فقط چیزی که با ری‌استارت نباید گم بشه:
#   • باسِ گروهی (gap_group_bosses) — HP/فاز/مشارکت‌ها/منطقه/announced_phase
#   • تنظیمات و شمارنده‌ی روزانه (gap_group_settings) و اعضای اخیر (gap_group_members)
#   • سقفِ باکسِ روزانه رو خودِ بازیکن داره (player["gev_daily"])
# صندوق/هیولا/دانجن عمداً فقط درون‌حافظه‌ان: عمرشون چند دقیقه‌ست، پاداش فقط لحظه‌ی
# پایان داده می‌شه (پس ری‌استارت چیزی رو دوبار نمی‌ده) و دکمه‌های قدیمی «⌛ تموم شده» می‌گیرن.
_ACT: dict[int, dict[int, float]] = {}        # chat_id -> {uid: آخرین پیام}
_LAST_CHAT_MSG: dict[int, float] = {}         # chat_id -> آخرین پیامِ هر کسی
_EVENTS: dict[int, dict[str, dict]] = {}      # chat_id -> {event_id: event}
_SETTINGS: dict[int, dict] = {}               # chat_id -> تنظیمات (کش)
_LAST_DB_TOUCH: dict[tuple, float] = {}
_BOSS_LOCKS: dict[int, asyncio.Lock] = {}
_ANNOUNCE_LOCKS: dict[int, asyncio.Lock] = {}
_BOSS_CHATS: set[int] = set()                 # گروه‌هایی که باسِ زنده دارن (تا واچر هر ۵ ثانیه DB نخونه)
_PHASES_SENT: set[tuple] = set()              # (chat, spawn_time, phase) — ضدِ اعلانِ تکراریِ فاز
_LAST_PASSIVE_MSG: dict[int, float] = {}
_BG: set = set()                              # نگه‌داریِ رفرنسِ taskهای پس‌زمینه (وگرنه GC می‌شن)
_BOT = None                                   # GapBotAdapter (تو register ست می‌شه)
_SEQ = [int(time.time()) & 0xFFFFFF]


# ============================================================
#  دیتابیس (همه sync؛ با to_thread صدا زده می‌شن)
# ============================================================
def _col(name: str):
    return get_db()[name]


def _db_get_boss(chat_id: int) -> dict | None:
    doc = _col("gap_group_bosses").find_one({"_id": chat_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


def _db_save_boss(chat_id: int, boss: dict):
    data = {k: v for k, v in boss.items() if k != "_id"}
    _col("gap_group_bosses").update_one({"_id": chat_id}, {"$set": data}, upsert=True)


def _db_mark_boss_dead(chat_id: int, killed: bool):
    upd = {"alive": False}
    if killed:
        upd["_last_killed_at"] = time.time()
    _col("gap_group_bosses").update_one({"_id": chat_id}, {"$set": upd}, upsert=True)


def _db_list_alive_bosses() -> list[dict]:
    out = []
    for doc in _col("gap_group_bosses").find({"alive": True}):
        cid = doc.pop("_id")
        doc["chat_id"] = cid
        out.append(doc)
    return out


def _db_boss_cooldown(chat_id: int) -> int:
    doc = _col("gap_group_bosses").find_one({"_id": chat_id})
    last = (doc or {}).get("_last_killed_at")
    if not last:
        return 0
    return max(0, int(last + CFG["boss_respawn_cd_sec"] - time.time()))


def _db_touch_member(chat_id: int, uid: int):
    _col("gap_group_members").update_one(
        {"_id": f"{chat_id}:{uid}"},
        {"$set": {"chat_id": chat_id, "user_id": uid, "last_seen": time.time()}}, upsert=True)


def _db_recent_members(max_age_sec: float) -> list[dict]:
    cutoff = time.time() - max_age_sec
    return list(_col("gap_group_members").find({"last_seen": {"$gte": cutoff}}))


def _db_get_settings(chat_id: int) -> dict:
    doc = _col("gap_group_settings").find_one({"_id": chat_id}) or {}
    doc.pop("_id", None)
    return doc


def _db_save_settings(chat_id: int, st: dict):
    data = {k: v for k, v in st.items() if k != "_id"}
    _col("gap_group_settings").update_one({"_id": chat_id}, {"$set": data}, upsert=True)


# ============================================================
#  کمک‌ها
# ============================================================
def _kb(rows: list[list[tuple[str, str]]] | None):
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for (t, d) in row] for row in rows])


async def _send(chat_id: int, text: str, rows=None) -> int | None:
    try:
        return await _BOT.send_message(chat_id, text, reply_markup=_kb(rows))
    except Exception as e:
        log_sync(f"🔴 gap group send failed ({chat_id}): {e}", "ERROR")
        return None


async def _edit(chat_id: int, mid: int | None, text: str, rows=None):
    if mid is None:
        return
    try:
        await _BOT.edit_message_text(text, chat_id, mid, reply_markup=_kb(rows))
    except Exception:
        pass


async def _scene(chat_id: int, text: str, rows=None, image: str | None = None, caption: str = "") -> int | None:
    """«صحنه»: اول عکس (کپشنِ کوتاه، بدونِ دکمه) بعد پیامِ متنی (با دکمه‌ها — همونی که بعداً ادیت می‌شه).
    اگه عکس نبود یا ارسالش خطا داد، فقط متن می‌ره؛ gm.send_photo_safe هیچ‌وقت exception نمی‌ده."""
    if image:
        await gm.send_photo_safe(_BOT, chat_id, image, caption)
    return await _send(chat_id, text, rows)


def _bg(coro, name: str = ""):
    """اجرای پس‌زمینه با نگه‌داریِ رفرنس و لاگِ خطا (هیچ taskای بی‌صدا نمی‌میره)."""
    async def _runner():
        try:
            await coro
        except Exception as e:  # noqa: BLE001
            log_sync(f"🔴 gap group bg task {name or ''} failed: {e}", "ERROR")
    t = asyncio.create_task(_runner())
    _BG.add(t)
    t.add_done_callback(_BG.discard)
    return t


def _is_admin(msg: Message) -> bool:
    """ادمینِ گپ: GAP_ADMIN_IDS شناسه‌ی عددیِ خودِ ادمینه؛ تو گروه، uid داخلی = -شناسه‌ی فرستنده."""
    try:
        from gap_admin_panel import GAP_ADMIN_IDS
    except Exception:
        return False
    u = msg.from_user
    return abs(int(u.id)) in GAP_ADMIN_IDS or int(getattr(u, "chat_id", 0) or 0) in GAP_ADMIN_IDS


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _eid(chat_id: int | None = None) -> str:
    """شناسه‌ی یکتای رویداد: شمارنده‌ی سراسری (که از زمان شروع می‌شه) + ۳ رقمِ رندوم.
    تو یه process هیچ‌وقت تکرار نمی‌شه، و بعد از ری‌استارت هم عملاً تصادم نداره."""
    _SEQ[0] = (_SEQ[0] + 1) & 0xFFFFFFF
    evs = _EVENTS.get(chat_id, {}) if chat_id is not None else {}
    while True:
        e = f"{_SEQ[0]:x}{random.randrange(0x1000):03x}"
        if e not in evs:
            return e
        _SEQ[0] += 1


def _boss_lock(chat_id: int) -> asyncio.Lock:
    return _BOSS_LOCKS.setdefault(chat_id, asyncio.Lock())


def _announce_lock(chat_id: int) -> asyncio.Lock:
    return _ANNOUNCE_LOCKS.setdefault(chat_id, asyncio.Lock())


def _active_uids(chat_id: int, window: float) -> list[int]:
    now = time.time()
    return [u for u, ts in _ACT.get(chat_id, {}).items() if now - ts <= window]


def _live_events(chat_id: int) -> dict[str, dict]:
    evs = _EVENTS.setdefault(chat_id, {})
    for k in [k for k, e in evs.items() if e.get("done")]:
        evs.pop(k, None)
    return evs


def _has_blocking_event(chat_id: int) -> bool:
    return any(not e.get("done") for e in _live_events(chat_id).values())


def _has_live(chat_id: int, types: tuple) -> bool:
    return any(not e.get("done") and e["type"] in types for e in _live_events(chat_id).values())


def _note_activity(msg: Message):
    if not is_group_msg(msg) or not msg.from_user:
        return
    cid, uid, now = msg.chat.id, msg.from_user.id, time.time()
    _ACT.setdefault(cid, {})[uid] = now
    _LAST_CHAT_MSG[cid] = now
    key = (cid, uid)
    if now - _LAST_DB_TOUCH.get(key, 0) > 120:     # حداکثر هر ۲ دقیقه یه نوشتن
        _LAST_DB_TOUCH[key] = now
        _bg(asyncio.to_thread(_db_touch_member, cid, uid), "touch_member")


async def _detect_region(chat_id: int) -> tuple[str | None, str]:
    """منطقه‌ی رویداد: اکثریتِ player["map"] بینِ بازیکن‌های فعالِ اخیرِ گروه.
    اطلاعاتِ قابل‌اعتماد نبود → رندومِ وزنی. (gap_event_world.pick_region)"""
    now = time.time()
    items = sorted(_ACT.get(chat_id, {}).items(), key=lambda kv: -kv[1])
    recent = [u for u, ts in items if now - ts <= CFG["recent_members_sec"]][:CFG["region_sample_max"]]
    maps: list = []
    if recent:
        got = await asyncio.gather(*(aget_player(u) for u in recent), return_exceptions=True)
        for p in got:
            if isinstance(p, dict) and p.get("character"):
                maps.append(p.get("map"))
    return gw.pick_region(maps)


# ─── محاسباتِ بازیکن ─────────────────────────────────────────────
def _compute_hit(player: dict) -> tuple[int, bool, float]:
    """همون فرمولِ ضربه‌ی رِیدِ گروهیِ تلگرام. خروجی: (raw_dmg, crit, amplify)."""
    from skill_tree import get_skill_bonuses
    from world_pulse import pulse_value
    char = ALL_CHARACTERS.get(player.get("character", ""), {})
    k_level = player.get("katana_level", 1)
    skb = get_skill_bonuses(player)
    base = char.get("base_dmg", 12)
    combo = player.get("combo", 0)
    combo_mult = 1 + combo * 0.05 + skb["dmg_pct"]
    raw = int((base + player.get("level", 1) * 2.5 + dmg_bonus(k_level) + random.randint(-3, 12)) * combo_mult)
    raw = int(raw * pulse_value("boss_dmg_mult"))
    crit_chance = max(0.0, 0.15 + crit_bonus(k_level) + skb["crit_chance"] + pulse_value("crit_add"))
    crit = random.random() < crit_chance
    if crit:
        raw = int(raw * (2.0 + skb["crit_dmg_bonus"]))
    amplify = element_amplify_bonus(k_level) + skb["elem_amp"]
    return max(1, raw), crit, amplify


def _power(player: dict) -> float:
    char = ALL_CHARACTERS.get(player.get("character", ""), {})
    return (player.get("level", 1) * 2.2 + player.get("katana_level", 1) * 1.5
            + char.get("base_dmg", 12) * 1.5)


def _grant_xp_zen(player: dict, zen: int, xp: int) -> tuple[int, bool]:
    """Zen/XP می‌ده و لول‌آپ رو (مثلِ رِیدِ تلگرام) اعمال می‌کنه. خروجی: (zen واقعی، لول‌آپ؟)"""
    from economy_engine import apply_gold_find
    from game_data import xp_for_level
    from skill_tree import grant_levelup_points, effective_max_hp
    zen = apply_gold_find(player, zen)
    player["zen"] = player.get("zen", 0) + zen
    player["xp"] = player.get("xp", 0) + xp
    old = player.get("level", 1)
    while player.get("xp", 0) >= xp_for_level(player.get("level", 1)) and player.get("level", 1) < 150:
        player["level"] += 1
        player["max_hp"] = player.get("max_hp", 100) + 10
        player["hp"] = effective_max_hp(player)
    leveled = player["level"] != old
    if leveled:
        grant_levelup_points(player, old, player["level"])
    return zen, leveled


def _grant_box(player: dict, box_id: str) -> list[str]:
    """یه باکسِ رایگان باز می‌کنه (قیمتش موقتاً اضافه و بلافاصله خرج می‌شه → بدونِ تغییرِ منطقِ lootbox_shop)."""
    box = ls.get_box(box_id)
    if not box or box["currency"] != "zen":
        return []
    player["zen"] = player.get("zen", 0) + box["price"]
    ok, _err, results = ls.open_box(player, box_id)
    if not ok:                      # نباید پیش بیاد؛ پولِ اضافه رو برگردون
        player["zen"] = max(0, player.get("zen", 0) - box["price"])
        return []
    return [r["label"] for r in results]


def _box_cap_ok(player: dict) -> bool:
    d = player.get("gev_daily") or {}
    return d.get("d") != _today() or d.get("boxes", 0) < CFG["box_daily_cap"]


def _box_cap_use(player: dict):
    d = player.get("gev_daily") or {}
    if d.get("d") != _today():
        d = {"d": _today(), "boxes": 0}
    d["boxes"] = d.get("boxes", 0) + 1
    player["gev_daily"] = d


async def _name(uid: int) -> str:
    p = await aget_player(uid)
    return (p or {}).get("name", "یه بازیکن")


async def _need_player(cb: CallbackQuery):
    """بازیکن (با کاراکتر) رو برمی‌گردونه یا خطا می‌ده."""
    p = await aget_player(cb.from_user.id)
    if not p or not p.get("character"):
        await cb.answer(MSG_NEED_START, show_alert=True)
        return None
    return p


async def _hurt(uid: int, pct: float) -> tuple[str, int] | None:
    """آسیبِ درصدی از max_hp (حداقلِ HP = ۱، مثلِ _dmg_penalty_player تلگرام). خروجی: (اسم، آسیب)."""
    async with player_lock(uid):
        p = await aget_player(uid)
        if not p:
            return None
        max_hp = p.get("max_hp", 100)
        dmg = max(1, int(max_hp * pct))
        p["hp"] = max(1, p.get("hp", max_hp) - dmg)
        await asave_player(uid, p)
    return p.get("name", "یه بازیکن"), dmg


def _pct(part: float, whole: float) -> str:
    return f"{(part / whole * 100):.0f}٪" if whole else "—"


# ============================================================
#  👹 باسِ گروهی
# ============================================================
def _boss_element(boss: dict) -> str:
    return boss.get("element") or gw.boss_element(boss.get("template_id", ""), be.WORLD_BOSS_TEMPLATES)


def _boss_rows(chat_id: int, boss: dict) -> list:
    rows = [[("⚔️ ضربه به باس!", "gev:b:hit")]]
    if boss.get("mechanic") == "area" and boss.get("area_active"):
        rows.append([("🛡 دفاع کن!", "gev:b:def")])
    rows.append([("🔄 وضعیت", "gev:b:st")])
    return rows


async def _boss_status(boss: dict) -> str:
    text = be.build_status_text(boss)
    top = sorted(((int(u), c.get("dmg", 0) + c.get("shield_dmg", 0))
                  for u, c in boss.get("contributors", {}).items()), key=lambda x: -x[1])[:3]
    if not top:
        return text
    medals = ["🥇", "🥈", "🥉"]
    lines = ["", "📊 **بیشترین دمیج تا الان:**"]
    for i, (u, d) in enumerate(top):
        lines.append(f"{medals[i]} {await _name(u)}: {d:,}")
    return text + "\n" + "\n".join(lines)


async def _spawn_boss(chat_id: int, template_id: str | None = None, auto: bool = False,
                      region: str | None = None) -> dict:
    """باس رو می‌سازه و تو DB ذخیره می‌کنه (اعلانِ سینمایی جداست: _announce_boss_spawn)."""
    if region is None:
        region, _how = await _detect_region(chat_id)
    if not template_id or template_id not in be.WORLD_BOSS_TEMPLATES:
        template_id = gw.pick_boss_template(region, be.WORLD_BOSS_TEMPLATES)
    boss = be.spawn_boss(template_id, chat_id)
    boss["gap"] = True
    boss["auto"] = auto
    boss["region"] = region
    boss["element"] = gw.boss_element(template_id, be.WORLD_BOSS_TEMPLATES)
    boss["announced_phase"] = 0
    # فیلدهای «چسبنده» از باسِ قبلیِ همین گروه ($set پاک‌شون نمی‌کنه)
    boss["shield_regen_at"] = 0
    boss["passive_retaliation_next_at"] = 0
    await asyncio.to_thread(_db_save_boss, chat_id, boss)
    _BOSS_CHATS.add(chat_id)
    log_sync(f"👥👹 **GAP GROUP BOSS** {'(auto) ' if auto else ''}{boss['name']}\n📍 چت: `{chat_id}`\n🌍 {region}", "GROUP")
    return boss


async def _announce_boss_spawn(chat_id: int, boss: dict, prefix: str = ""):
    tid = boss["template_id"]
    tpl = be.WORLD_BOSS_TEMPLATES[tid]
    element = _boss_element(boss)
    region = boss.get("region")
    n, label = gw.threat_level(tpl["total_hp"])
    phase0 = tpl["phases"][0]
    try:
        p1 = phase0["enter_msg"].format(weak=be.element_tag(phase0["weak"]))
    except Exception:
        p1 = ""
    text = (
        f"{prefix}{tpl.get('intro', '')}\n\n"
        f"{gw.region_label(region)} — {gw.region_env_line(region)}\n\n"
        f"📜 **مشخصاتِ باس**\n"
        f"❤️ HP: {tpl['total_hp']:,}  |  ☠️ تهدید: {gw.threat_bar(n)} ({label})\n"
        f"🧬 عنصر: {be.element_tag(element)}\n\n"
        f"{await _boss_status(boss)}"
        + (f"\n\n{p1}" if p1 else "")
    )
    image = gm.boss_image(tid, boss.get("phase_index", 0), element, chat_id)
    async with _announce_lock(chat_id):
        await _scene(chat_id, text, _boss_rows(chat_id, boss), image,
                     f"{boss['name']} — {gw.region_label(region)}")


async def _announce_phase(chat_id: int, boss: dict, enter_msg: str):
    """اعلانِ تغییرِ فاز — دقیقاً یک‌بار (کلیدِ chat/spawn_time/phase)."""
    key = (chat_id, boss.get("spawn_time"), boss.get("phase_index"))
    if key in _PHASES_SENT:
        return
    _PHASES_SENT.add(key)
    if len(_PHASES_SENT) > 2000:
        _PHASES_SENT.clear()
        _PHASES_SENT.add(key)
    tid = boss["template_id"]
    element = _boss_element(boss)
    idx = boss.get("phase_index", 0)
    phase = be.WORLD_BOSS_TEMPLATES[tid]["phases"][idx]
    env = gw.phase_env_line(element, idx, boss["name"])
    pct = be.overall_hp_pct(boss)
    text = (
        f"{enter_msg}\n\n"
        + (f"{env}\n\n" if env else "")
        + f"⚔️ ضعف: {be.element_tag(phase['weak'])}  |  🛡 مقاوم به: {be.element_tag(phase['resist'])}\n"
        + f"🔴 HP کلیِ باقی‌مانده: {pct:.1f}٪"
    )
    image = gm.boss_image(tid, idx, element, chat_id)
    async with _announce_lock(chat_id):
        await _scene(chat_id, text, _boss_rows(chat_id, boss), image, f"🔔 {phase['name']} — {boss['name']}")


async def cmd_graid(msg: Message):
    if not is_group_msg(msg):
        return await msg.answer(MSG_NOT_GROUP)
    chat_id, uid = msg.chat.id, msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("character"):
        return await msg.answer(MSG_NEED_START)
    parts = (msg.text or "").split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else None
    args = arg.split() if arg else []

    spawned = None
    prefix = ""
    async with _boss_lock(chat_id):
        boss = await asyncio.to_thread(_db_get_boss, chat_id)
        if args and args[0] == "force":
            if not _is_admin(msg):
                return await msg.answer("❌ فقط ادمینِ ربات می‌تونه رِید رو force کنه!")
            tid = region = None
            if len(args) > 1:
                region = gw.normalize_region(" ".join(args[1:]))
                tid = args[1] if args[1] in be.WORLD_BOSS_TEMPLATES else None
                if tid:
                    region = None
            spawned = await _spawn_boss(chat_id, tid, region=region)
            prefix = "🛠 ادمین رِید رو دوباره شروع کرد!\n\n"
        elif boss and boss.get("alive"):
            be.tick_shield_regen(boss)
            await asyncio.to_thread(_db_save_boss, chat_id, boss)
            return await msg.answer(await _boss_status(boss), reply_markup=_kb(_boss_rows(chat_id, boss)))
        else:
            cd = await asyncio.to_thread(_db_boss_cooldown, chat_id)
            if cd > 0:
                m, s = divmod(cd, 60)
                return await msg.answer(f"😴 باسِ قبلیِ این گروه تازه شکست خورد — {m} دقیقه و {s} ثانیه تا رِیدِ بعدی صبر کن.")
            if _has_live(chat_id, ("dungeon", "ambush")):
                return await msg.answer("🚧 الان یه رویدادِ دیگه (دانجن/حمله‌ی هیولا) تو گروه فعاله؛ اول اون تموم بشه.")
            tid = arg if arg and arg in be.WORLD_BOSS_TEMPLATES else None
            spawned = await _spawn_boss(chat_id, tid)
            prefix = "👥 **رِیدِ باسِ این گروه شروع شد!**\nهرکی تو گروه هست می‌تونه با دکمه‌ی زیر بزنتش.\n\n"
    _bg(_announce_boss_spawn(chat_id, spawned, prefix), "boss_spawn")


async def _boss_hit(cb: CallbackQuery):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    player = await _need_player(cb)
    if not player:
        return
    post: list = []
    notes: list[str] = []
    async with _boss_lock(chat_id):
        boss = await asyncio.to_thread(_db_get_boss, chat_id)
        if not boss or not boss.get("alive"):
            return await cb.answer("😴 الان تو این گروه هیچ رِیدی فعال نیست. با /graid یکی شروع کن!", show_alert=True)
        now = time.time()
        async with player_lock(uid):
            player = await aget_player(uid)
            since = now - player.get("last_gap_graid_hit", 0)
            if since < CFG["boss_hit_cd_sec"]:
                return await cb.answer(f"⏳ {int(CFG['boss_hit_cd_sec'] - since) + 1} ثانیه صبر کن!", show_alert=True)
            be.tick_shield_regen(boss)
            raw, crit, amplify = _compute_hit(player)
            res = be.process_attack(boss, uid, player.get("character", ""), raw, amplify_bonus=amplify)
            ls_pct = lifesteal_bonus(player.get("katana_level", 1))
            if ls_pct > 0 and (res["hp_dmg"] > 0 or res["shield_dmg"] > 0):
                heal = int((res["hp_dmg"] + res["shield_dmg"]) * ls_pct)
                player["hp"] = min(player.get("max_hp", 100), player.get("hp", 100) + heal)
            player["last_gap_graid_hit"] = now
            player["combo"] = player.get("combo", 0) + 1
            zen_gain, leveled = _grant_xp_zen(
                player, random.randint(15, 40) + player.get("level", 1) // 2,
                random.randint(12, 25) + player.get("level", 1) // 3)
            await asave_player(uid, player)
        dmg = res["hp_dmg"] + res["shield_dmg"]
        pname = player.get("name", "یه بازیکن")

        if leveled:
            post.append(_send(chat_id, f"🎉 **{pname}** توی همین رِید رسید به سطح **{player['level']}**!"))

        if res["boss_killed"]:
            await asyncio.to_thread(_db_mark_boss_dead, chat_id, True)   # اول مرگ ثبت می‌شه → پاداش فقط یک‌بار
            _BOSS_CHATS.discard(chat_id)
            data = None
            try:
                data = await _boss_rewards(chat_id, boss)
            except Exception as e:  # noqa: BLE001
                log_sync(f"🔴 gap boss rewards failed ({chat_id}): {e}", "ERROR")
                post.append(_send(chat_id, "⚠️ مشکلی تو توزیعِ جایزه‌های باس پیش اومد — به ادمین گزارش شد."))
            if data is not None:
                post.append(_announce_boss_death(chat_id, boss, pname, dmg, crit, data))
            for c in post:
                _bg(c, "boss_kill_post")
            return await cb.answer("💀 باس رو کشتی!")

        if res.get("phase_enter_msg"):
            boss["announced_phase"] = boss.get("phase_index", 0)         # ذخیره می‌شه → بعد از ری‌استارت تکرار نمی‌شه
            post.append(_announce_phase(chat_id, boss, res["phase_enter_msg"]))
        elif res.get("shield_broken"):
            regen = be.WORLD_BOSS_TEMPLATES[boss["template_id"]]["phases"][boss["phase_index"]].get("shield_regen_sec", 30)
            post.append(_send(chat_id, f"💥 **سپرِ {boss['name']} شکست!** تا حدودِ {regen} ثانیه آسیبِ واقعی می‌خوره — همین الان بزنینش!",
                              _boss_rows(chat_id, boss)))
        await asyncio.to_thread(_db_save_boss, chat_id, boss)
    for c in post:
        _bg(c, "boss_hit_post")
    if res.get("shield_broken"):
        notes.append("🛡 سپر شکست!")
    if res.get("mult", 1.0) > 1.0:
        notes.append("نقطه‌ضعف!")
    elif res.get("mult", 1.0) < 1.0:
        notes.append("مقاوم بود")
    await cb.answer(f"💥 {dmg:,} دمیج زدی!" + (" کریت! 💥" if crit else "")
                    + (" " + " ".join(notes) if notes else "") + f" +{zen_gain:,} Zen")


async def _boss_rewards(chat_id: int, boss: dict) -> dict:
    """پاداش‌ها رو (یک‌بار) اعمال می‌کنه — همون محاسباتِ boss_engine — و دیتای نمایش رو برمی‌گردونه.
    خطای یه بازیکن بقیه رو نمی‌خوابونه."""
    rewards, speed_kill = be.distribute_rewards(boss, is_weekly_featured=False)
    # پاداش‌های باکسِ گروهی: MVP نقره‌ای، پرتلاش‌ها برنزی، بقیه چوبی
    ranked = sorted(boss.get("contributors", {}).items(),
                    key=lambda kv: -(kv[1].get("dmg", 0) + kv[1].get("shield_dmg", 0)))
    box_lines = []
    for rank, (suid, c) in enumerate(ranked):
        ruid = int(suid)
        box_id = "silver_box" if rank == 0 else ("bronze_box" if c.get("hits", 0) >= 5 else "wood_box")
        try:
            async with player_lock(ruid):
                rp = await aget_player(ruid)
                if not rp:
                    continue
                r = rewards.get(ruid) or rewards.get(suid)
                if r:
                    rp["zen"] = rp.get("zen", 0) + r["zen"]
                    if r.get("titles"):
                        rp.setdefault("boss_titles", []).extend(r["titles"])
                    if r.get("items"):
                        rp.setdefault("inventory", []).extend(r["items"])
                got = _grant_box(rp, box_id) if _box_cap_ok(rp) else []
                if got:
                    _box_cap_use(rp)
                    if rank < 3:
                        b = ls.get_box(box_id)
                        box_lines.append(f"{b['emoji']} {rp.get('name', '—')}: {b['name']} → {got[0]}")
                await asave_player(ruid, rp)
        except Exception as e:  # noqa: BLE001
            log_sync(f"🔴 gap boss reward failed for {ruid}: {e}", "ERROR")
    log_sync(f"👥👹 **GAP GROUP RAID CLEARED**\n📍 `{chat_id}`\n🏷️ {boss['name']}\n👥 {len(boss.get('contributors', {}))} نفر", "GROUP")
    return {"rewards": rewards, "speed_kill": speed_kill, "box_lines": box_lines, "ranked": ranked}


async def _announce_boss_death(chat_id: int, boss: dict, last_name: str, last_dmg: int, crit: bool, data: dict):
    async with _announce_lock(chat_id):
        element = _boss_element(boss)
        ranked = data["ranked"]
        total = sum(c.get("dmg", 0) + c.get("shield_dmg", 0) for _u, c in ranked)
        elapsed = int(time.time() - boss.get("spawn_time", time.time()))
        mm, ss = divmod(max(0, elapsed), 60)
        head = [gw.death_line(element, boss["name"]),
                f"💥 {last_name} ضربه‌ی آخر رو زد ({last_dmg:,})!" + (" 💥 کریتیکال!" if crit else "")]
        if ranked:
            top_uid, top_c = ranked[0]
            top_dmg = top_c.get("dmg", 0) + top_c.get("shield_dmg", 0)
            head.append(f"\n🏆 **MVP: {await _name(int(top_uid))}** — {top_dmg:,} دمیج ({_pct(top_dmg, total)} از کلِ نبرد)")
        head.append(f"👥 {len(ranked)} شرکت‌کننده  |  ⚔️ {total:,} دمیجِ مجموع  |  ⏱ {mm}:{ss:02d}")
        summary = await be.build_kill_summary(boss, data["rewards"], data["speed_kill"], _name)
        extra = ("\n\n🎁 **باکسِ جایزه (بالاترین‌ها):**\n" + "\n".join(data["box_lines"])) if data["box_lines"] else ""
        text = "\n".join(head) + "\n\n" + summary + extra
        image = gm.boss_defeated_image(boss["template_id"], element, chat_id)
        if image:
            await gm.send_photo_safe(_BOT, chat_id, image, f"💀 {boss['name']} شکست خورد!")
        if len(text) > 3500:                # پیامِ خیلی بلند → دو تکه
            await _send(chat_id, "\n".join(head))
            await _send(chat_id, summary + extra)
        else:
            await _send(chat_id, text)


async def _boss_defend(cb: CallbackQuery):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    if not await _need_player(cb):
        return
    async with _boss_lock(chat_id):
        boss = await asyncio.to_thread(_db_get_boss, chat_id)
        if not boss or not boss.get("alive"):
            return await cb.answer("😴 رِیدِ فعالی نیست.", show_alert=True)
        if boss.get("mechanic") != "area" or not boss.get("area_active"):
            return await cb.answer("🛡 الان چیزی برای دفاع نیست.", show_alert=True)
        be.register_area_defense(boss, uid)
        await asyncio.to_thread(_db_save_boss, chat_id, boss)
    await cb.answer("🛡 دفاع ثبت شد! امن موندی.")


async def _boss_status_cb(cb: CallbackQuery):
    chat_id = cb.message.chat.id
    boss = await asyncio.to_thread(_db_get_boss, chat_id)
    if not boss or not boss.get("alive"):
        return await cb.answer("😴 رِیدِ فعالی نیست.", show_alert=True)
    be.tick_shield_regen(boss)
    await cb.answer()
    await _send(chat_id, await _boss_status(boss), _boss_rows(chat_id, boss))


async def _boss_watch_one(chat_id: int):
    """یه دورِ واچر برای یه گروه. اول state تحتِ قفل تغییر و ذخیره می‌شه، بعد (بیرونِ قفل) پیام‌ها و آسیب‌ها."""
    sends: list[tuple] = []          # (text, rows)
    area_victims: list[tuple[int, float]] = []
    enrage_victim: int | None = None
    passive_victim: int | None = None
    announce_enrage_start = False
    resolved_area = False
    element = "arcane"
    expired_name = None
    async with _boss_lock(chat_id):
        boss = await asyncio.to_thread(_db_get_boss, chat_id)
        if not boss or not boss.get("alive"):
            _BOSS_CHATS.discard(chat_id)
            return
        if time.time() - boss.get("spawn_time", time.time()) > CFG["boss_ttl_sec"]:
            await asyncio.to_thread(_db_mark_boss_dead, chat_id, False)
            _BOSS_CHATS.discard(chat_id)
            expired_name = boss["name"]
        else:
            element = _boss_element(boss)
            changed = False
            # 🛡 شارژِ مجددِ سپر (پایانِ پنجره‌ی آسیب‌پذیری)
            if be.tick_shield_regen(boss):
                changed = True
                sends.append((f"🛡 **سپرِ {boss['name']} دوباره شکل گرفت!** باید دوباره بشکنیدش.", _boss_rows(chat_id, boss)))
            # 🌊 حمله‌ی ناحیه‌ای: open → هشدارِ عنصری + دکمه‌ی دفاع | resolve → آسیب به دفاع‌نکرده‌ها
            act = be.tick_area_attack(boss)
            if act == "open":
                changed = True
                phase = be.WORLD_BOSS_TEMPLATES[boss["template_id"]]["phases"][boss["phase_index"]]
                sends.append((f"{gw.area_warning(element, boss['name'])}\n⏳ {phase['area_window_sec']} ثانیه فرصت داری «🛡 دفاع کن» رو بزنی وگرنه آسیب می‌بینی!",
                              _boss_rows(chat_id, boss)))
            elif act == "resolve":
                changed = True
                resolved_area = True
                area_victims = be.resolve_area_attack(boss)
            # 💢 خشم
            eact = be.tick_enrage(boss)
            if eact == "start":
                changed = True
                announce_enrage_start = True
            elif eact == "tick":
                changed = True
                enrage_victim = be.pick_random_contributor(boss)
            # 👹 ضدحمله‌ی پایه
            if CFG["passive_retaliation"]:
                before = boss.get("passive_retaliation_next_at", 0)
                passive_victim = be.tick_passive_retaliation(boss)
                if boss.get("passive_retaliation_next_at", 0) != before:
                    changed = True
            if changed:
                await asyncio.to_thread(_db_save_boss, chat_id, boss)

    if expired_name:
        await _send(chat_id, f"🌫 **{expired_name}** از کسالت به تاریکی برگشت... (کسی نکشتش)\nبا /graid یکی دیگه صدا کنین.")
        return
    for text, rows in sends:
        await _send(chat_id, text, rows)
    if resolved_area:
        names = []
        for puid, pct in area_victims:
            r = await _hurt(puid, pct)
            if r:
                names.append(f"{r[0]} (-{r[1]} HP)")
        await _send(chat_id, ("💥 **حمله‌ی ناحیه‌ای فرود اومد!**\nآسیب‌دیده‌ها: " + "، ".join(names)) if names
                    else "🛡 همه دفاع کردن! کسی آسیب ندید.")
    if announce_enrage_start:
        await _send(chat_id, gw.element_fx(element)["enrage"].replace("{boss}", boss["name"])
                    + "\nاز الان هر چند ثانیه به یکی آسیب می‌زنه!")
    if enrage_victim:
        r = await _hurt(enrage_victim, be.enrage_dmg_pct(boss))
        if r:
            await _send(chat_id, f"💢 {boss['name']} خشمگین به **{r[0]}** {r[1]} آسیب زد!")
    if passive_victim:
        r = await _hurt(passive_victim, be.PASSIVE_RETALIATION_DMG_PCT)
        now = time.time()
        if r and now - _LAST_PASSIVE_MSG.get(chat_id, 0) >= CFG["passive_msg_min_gap_sec"]:
            _LAST_PASSIVE_MSG[chat_id] = now
            await _send(chat_id, f"👹 **{boss['name']}** ضدحمله زد! به **{r[0]}** {r[1]} آسیب خورد!")


async def _boss_watcher_tick():
    """سپر/حمله‌ی ناحیه‌ای/خشم/ضدحمله رو حتی وقتی کسی نمی‌زنه به‌روز نگه می‌داره + ناپدیدیِ باسِ قدیمی.
    (قبلاً خروجیِ tick_area_attack/tick_enrage — «open/resolve/start/tick» — به‌جای پیام تو گروه
    فرستاده می‌شد و پنجره‌ی ناحیه‌ای هیچ‌وقت resolve نمی‌شد؛ اینجا درست پیاده شده.)"""
    for chat_id in list(_BOSS_CHATS):
        try:
            await _boss_watch_one(chat_id)
        except Exception as e:  # noqa: BLE001
            log_sync(f"🔴 gap boss watcher error ({chat_id}): {e}", "ERROR")


# ============================================================
#  📦 صندوقِ اسرارآمیز
# ============================================================
def _pick_box() -> str:
    ids, weights = zip(*CFG["box_pool"])
    return random.choices(ids, weights=weights, k=1)[0]


async def _spawn_box(chat_id: int, box_id: str | None = None, region: str | None = None) -> dict:
    if region is None:
        region, _ = await _detect_region(chat_id)
    box_id = box_id or _pick_box()
    box = ls.get_box(box_id)
    meta = gw.chest_meta(box_id)
    race = box_id in CFG["box_race"]
    eid = _eid(chat_id)
    ev = {"type": "box", "id": eid, "box_id": box_id, "race": race, "claimed": [], "pending": set(),
          "slots": 1 if race else CFG["box_party_slots"], "expires": time.time() + CFG["box_ttl_sec"],
          "done": False, "mid": None, "revealed": False, "region": region}
    _live_events(chat_id)[eid] = ev              # قبل از هر await ثبت می‌شه → رویدادِ هم‌زمان نمی‌یاد
    how = ("⚡ **فقط یه نفر** می‌تونه بازش کنه — سریع باش!" if race
           else f"🎁 به **{ev['slots']} نفرِ اول** هرکدوم یه باکس می‌رسه!")
    banner = "✨✨✨ **کشفِ نادر!** ✨✨✨\n" if meta["stars"] >= 4 else ""
    text = (
        f"{banner}📦 **{gw.chest_discovery_line(region)}**\n"
        f"{gw.region_label(region)}\n\n"
        f"{box['emoji']} **{box['name']}**\n"
        f"🏷 ندرت: {meta['emoji']} **{meta['fa']}** {'⭐' * meta['stars']}\n"
        f"{how}\n"
        f"⏳ {CFG['box_ttl_sec'] // 60} دقیقه وقت داره"
    )
    image = gm.chest_image(box_id, False, chat_id)
    ev["mid"] = await _scene(chat_id, text, [[("🔓 بازش کن!", f"gev:x:{eid}")]], image,
                             f"📦 {box['name']} — {meta['fa']}")
    return ev


async def _box_claim(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "box" or ev["done"] or time.time() > ev["expires"]:
        return await cb.answer("⌛ این صندوق دیگه نیست.", show_alert=True)
    if uid in ev["claimed"] or uid in ev["pending"]:
        return await cb.answer("😏 تو قبلاً بازش کردی!", show_alert=True)
    if len(ev["claimed"]) + len(ev["pending"]) >= ev["slots"]:
        return await cb.answer("😢 دیر رسیدی — صندوق خالی شد!", show_alert=True)
    # ⚠️ رزروِ اسلات همین‌جا و *قبل از هر await* انجام می‌شه تا کلیکِ هم‌زمان دو نفر
    # (مخصوصاً تو صندوق‌های «فقط ۱ برنده») هیچ‌وقت از ظرفیت رد نشه.
    ev["pending"].add(uid)
    ok = False
    got: list[str] = []
    player = None
    try:
        player = await aget_player(uid)
        if not player or not player.get("character"):
            return await cb.answer(MSG_NEED_START, show_alert=True)
        if player.get("level", 1) < CFG["box_min_level"]:
            return await cb.answer(f"🔒 برای باز کردنِ صندوق حداقل سطح {CFG['box_min_level']} لازمه.", show_alert=True)
        async with player_lock(uid):
            player = await aget_player(uid)
            if not _box_cap_ok(player):
                return await cb.answer(f"📦 سقفِ {CFG['box_daily_cap']} باکسِ رایگانِ امروزت پر شده. فردا بیا!", show_alert=True)
            got = _grant_box(player, ev["box_id"])
            if not got:
                return await cb.answer("❌ صندوق خراب بود!", show_alert=True)
            _box_cap_use(player)
            await asave_player(uid, player)
        ok = True
    finally:
        ev["pending"].discard(uid)
        if ok:
            ev["claimed"].append(uid)
    await cb.answer("🎁 باز شد!")
    first_reveal = not ev["revealed"]
    ev["revealed"] = True
    if len(ev["claimed"]) >= ev["slots"]:
        ev["done"] = True
    _bg(_box_reveal(chat_id, ev, player.get("name", "یه بازیکن"), got, first_reveal), "box_reveal")


async def _box_reveal(chat_id: int, ev: dict, pname: str, got: list[str], first: bool):
    box = ls.get_box(ev["box_id"])
    meta = gw.chest_meta(ev["box_id"])
    rare = meta["stars"] >= 4
    lines = []
    if rare:
        lines.append("🌟🌟 **کشفِ بی‌نظیر!** 🌟🌟")
    lines.append(f"🎉 **{pname}** {box['emoji']} {box['name']} ({meta['emoji']} {meta['fa']}) رو باز کرد:")
    lines += [f"• {g}" for g in got]
    if first:
        image = gm.chest_image(ev["box_id"], True, chat_id)
        if image:
            await gm.send_photo_safe(_BOT, chat_id, image, f"🎁 {pname} — {box['name']}")
    await _send(chat_id, "\n".join(lines))
    if ev["done"]:
        await _edit(chat_id, ev["mid"], f"📦 {box['emoji']} {box['name']} — صاحب پیدا کرد. 🎉")


# ============================================================
#  🐺 حمله‌ی هیولا
# ============================================================
_TRAIT_FA = {
    "evasive": "💨 چابک — گاهی جاخالی می‌ده",
    "armored": "🛡 زره‌دار — دمیجِ عادی کمتر می‌گیره (کریت زره رو می‌شکنه)",
    "frenzied": "🩸 خشمگین‌شونده — وقتی جونش کم شد ضدحمله می‌زنه",
}


async def _spawn_ambush(chat_id: int, region: str | None = None) -> dict:
    if region is None:
        region, _ = await _detect_region(chat_id)
    key = gw.pick_monster(region, has_art=gm.has_monster_art)
    m = gw.MONSTERS[key]
    n_active = len(_active_uids(chat_id, CFG["recent_members_sec"]))
    hp = gw.monster_hp(n_active)
    eid = _eid(chat_id)
    ev = {"type": "ambush", "id": eid, "key": key, "name": m["name"], "hp": hp, "max_hp": hp, "hitters": {},
          "names": {}, "last_hit": {}, "traits": list(m["traits"]), "weak": m["weak"], "resist": m["resist"],
          "frenzy_on": False, "last_edit": 0.0, "rewarded": False, "region": region,
          "expires": time.time() + CFG["ambush_ttl_sec"], "done": False, "mid": None}
    _live_events(chat_id)[eid] = ev
    ev["text0"] = (
        f"⚠️ **حمله‌ی هیولا!**  {gw.region_label(region)}\n\n"
        f"{m['name']} {random.choice(m['flavor'])}\n"
        f"❤️ {hp:,} HP\n"
        f"⚔️ ضعف: {be.element_tag(m['weak'])}  |  🛡 مقاوم به: {be.element_tag(m['resist'])}\n"
        + "\n".join(_TRAIT_FA[t] for t in m["traits"]) + "\n\n"
        f"همه با هم بزنینش! ⏳ {CFG['ambush_ttl_sec'] // 60} دقیقه وقت دارین")
    image = gm.monster_image(key, chat_id)
    ev["mid"] = await _scene(chat_id, ev["text0"], [[("⚔️ حمله!", f"gev:a:{eid}")]], image,
                             f"⚠️ {m['name']} — {gw.region_label(region)}")
    return ev


def _ambush_board(ev: dict, top: int = 5) -> str:
    ranked = sorted(ev["hitters"].items(), key=lambda kv: -kv[1])[:top]
    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    return "\n".join(f"{medals[i]} {ev['names'].get(u, '—')}: {d:,}" for i, (u, d) in enumerate(ranked))


async def _ambush_refresh(chat_id: int, ev: dict):
    """لیدربوردِ زنده: متنِ پیامِ هیولا (نه عکس) رو ادیت می‌کنه — حداکثر هر چند ثانیه یه‌بار."""
    if ev["done"] or not ev["hitters"]:
        return
    text = (f"{ev['name']} — {gw.region_label(ev.get('region'))}\n"
            f"❤️ {max(0, ev['hp']):,}/{ev['max_hp']:,}\n{be.hp_bar(max(0, ev['hp']), ev['max_hp'], 12)}\n"
            + ("🩸 **خشمگینه!**\n" if ev["frenzy_on"] else "")
            + f"\n📊 **بیشترین دمیج:**\n{_ambush_board(ev)}")
    await _edit(chat_id, ev["mid"], text, [[("⚔️ حمله!", f"gev:a:{ev['id']}")]])


async def _ambush_hit(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "ambush" or ev["done"]:
        return await cb.answer("⌛ هیولا رفته یا کشته شده.", show_alert=True)
    now = time.time()
    since = now - ev["last_hit"].get(uid, 0)
    if since < CFG["ambush_hit_cd_sec"]:
        return await cb.answer(f"⏳ {int(CFG['ambush_hit_cd_sec'] - since) + 1} ثانیه صبر کن!", show_alert=True)
    ev["last_hit"][uid] = now            # قبل از await: دابل‌کلیک نمی‌تونه کولداون رو دور بزنه
    player = await _need_player(cb)
    if not player:
        ev["last_hit"].pop(uid, None)
        return
    if ev["done"]:
        return await cb.answer("⌛ هیولا رفته یا کشته شده.", show_alert=True)
    ev["names"][uid] = player.get("name", "یه بازیکن")

    # ─── از اینجا تا تعیینِ killed بدونِ await → دو ضربه‌ی هم‌زمان هیچ‌وقت هر دو ضربه‌ی آخر نمی‌شن ───
    traits = ev["traits"]
    if "evasive" in traits and random.random() < CFG["ambush_dodge_chance"]:
        return await cb.answer(f"💨 {ev['name']} جاخالی داد!")
    raw, crit, _amp = _compute_hit(player)
    mult = 1.0
    elem = be.get_char_element(player.get("character", ""))
    tags = []
    if elem == ev["weak"]:
        mult *= CFG["ambush_weak_mult"]
        tags.append("نقطه‌ضعف!")
    elif elem == ev["resist"]:
        mult *= CFG["ambush_resist_mult"]
        tags.append("مقاوم بود")
    if "armored" in traits and not crit:
        mult *= CFG["ambush_armor_mult"]
    dmg = min(max(1, int(raw * mult)), ev["hp"])
    ev["hp"] -= dmg
    ev["hitters"][uid] = ev["hitters"].get(uid, 0) + dmg
    killed = ev["hp"] <= 0
    if killed:
        ev["done"] = True
    frenzy_started = (not killed and "frenzied" in traits and not ev["frenzy_on"]
                      and ev["hp"] <= ev["max_hp"] * CFG["ambush_frenzy_hp_pct"])
    if frenzy_started:
        ev["frenzy_on"] = True
    counter = (not killed and "frenzied" in traits and ev["frenzy_on"]
               and random.random() < CFG["ambush_frenzy_counter"])
    # ───────────────────────────────────────────────────────────────────────────

    extra = ""
    if counter:
        r = await _hurt(uid, CFG["ambush_frenzy_dmg_pct"])
        if r:
            extra = f" | 🩸 ضدحمله: -{r[1]} HP"
    await cb.answer(f"💥 {dmg:,} دمیج!" + (" کریت!" if crit else "")
                    + (f" ({' '.join(tags)})" if tags else "")
                    + (f" | ❤️ {max(0, ev['hp']):,} مونده" if not killed else "") + extra)
    if frenzy_started:
        _bg(_send(chat_id, f"🩸 **{ev['name']} خشمگین شد!** از این به بعد ممکنه به حمله‌کننده‌ها ضدحمله بزنه!"), "frenzy")
    if killed:
        _bg(_ambush_victory(chat_id, ev, uid), "ambush_victory")
    elif now - ev["last_edit"] >= CFG["ambush_edit_gap_sec"]:
        ev["last_edit"] = now
        _bg(_ambush_refresh(chat_id, ev), "ambush_refresh")


async def _ambush_victory(chat_id: int, ev: dict, killer_uid: int):
    if ev["rewarded"]:
        return
    ev["rewarded"] = True                 # ضدِ پاداشِ دوباره
    hitters = ev["hitters"]
    total = sum(hitters.values()) or 1
    pool_zen = 700 + 300 * len(hitters)
    pool_xp = 250 + 120 * len(hitters)
    mvp_uid = max(hitters, key=hitters.get) if hitters else None
    lines = [f"🏆 **{ev['name']} شکست خورد!**", f"👥 {len(hitters)} نفر شرکت کردن",
             f"⭐ ضربه‌ی آخر: {ev['names'].get(killer_uid, '—')}", ""]
    for uid, dmg in sorted(hitters.items(), key=lambda kv: -kv[1]):
        share = dmg / total
        try:
            async with player_lock(uid):
                p = await aget_player(uid)
                if not p:
                    continue
                zen, leveled = _grant_xp_zen(p, 60 + int(pool_zen * share), 25 + int(pool_xp * share))
                extra = ""
                if uid == killer_uid and _box_cap_ok(p):          # ضربه‌ی آخر: یه باکسِ برنزی
                    got = _grant_box(p, "bronze_box")
                    if got:
                        _box_cap_use(p)
                        extra = f" + 🥉 ({got[0]})"
                elif uid == mvp_uid and uid != killer_uid and _box_cap_ok(p):   # MVP دمیج: یه باکسِ چوبی
                    got = _grant_box(p, "wood_box")
                    if got:
                        _box_cap_use(p)
                        extra = f" + 🪵 ({got[0]})"
                await asave_player(uid, p)
        except Exception as e:  # noqa: BLE001
            log_sync(f"🔴 gap ambush reward failed for {uid}: {e}", "ERROR")
            continue
        tag = " 👑 MVP" if uid == mvp_uid else ""
        lines.append(f"• {p.get('name', '—')}: {dmg:,} دمیج ({_pct(dmg, total)}) → +{zen:,} Zen{extra}{tag}"
                     + (" 🎉 لول‌آپ!" if leveled else ""))
    await _edit(chat_id, ev["mid"], f"⚔️ {ev['name']} — کشته شد ✅")
    await _send(chat_id, "\n".join(lines[:16]))


# ============================================================
#  🚪 دروازه‌ی دانجن (چندنفره)
# ============================================================
async def _spawn_dungeon(chat_id: int, region: str | None = None) -> dict:
    if region is None:
        region, _ = await _detect_region(chat_id)
    dtype, dname = gw.pick_dungeon(region)
    eid = _eid(chat_id)
    ev = {"type": "dungeon", "id": eid, "dtype": dtype, "name": dname, "region": region, "party": [],
          "names": {}, "votes": {}, "room": -1, "phase": "join", "mid": None, "done": False, "dirty": False,
          "expires": time.time() + CFG["dungeon_join_sec"] + 900}
    _live_events(chat_id)[eid] = ev
    ev["join_rows"] = [[("🚪 وارد می‌شم!", f"gev:d:{eid}:join")]]
    ev["mid"] = await _scene(chat_id, _dungeon_entry_text(ev), ev["join_rows"], gm.dungeon_image(dtype, chat_id),
                             f"🚪 {dname} — {gw.region_label(region)}")
    _bg(_run_dungeon(chat_id, ev), "dungeon_run")
    return ev


def _dungeon_entry_text(ev: dict, left: int | None = None) -> str:
    names = "، ".join(ev["names"].get(u, "—") for u in ev["party"]) or "—"
    return (
        f"🚪 **دروازه‌ی «{ev['name']}» باز شد!**\n"
        f"📍 {gw.region_label(ev['region'])}\n\n"
        f"👥 دسته‌جمعی وارد شین! ۳ اتاقِ تصادفی (نبرد، تله، کاوش، گنج، هیولای قدرتمند، خطرِ محیطی) "
        f"و آخرش یه **نگهبانِ نهایی**.\n"
        f"🗳 هر اتاق یه تاکتیکِ بهتر داره: حمله / دفاع / جستجو — با **رأی‌گیری** تصمیم می‌گیرین.\n"
        f"👥 پیشنهادی: ۴ تا ۶ نفر (حداقل {CFG['dungeon_min_party']}، حداکثر {CFG['dungeon_max_party']})\n"
        f"⏳ {left if left is not None else CFG['dungeon_join_sec']} ثانیه وقت دارین\n\n"
        f"✅ ثبت‌نام‌شده‌ها ({len(ev['party'])}/{CFG['dungeon_max_party']}): {names}"
    )


async def _dungeon_join(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "dungeon" or ev["done"] or ev["phase"] != "join":
        return await cb.answer("⌛ ثبت‌نامِ این دروازه تموم شده.", show_alert=True)
    if uid in ev["party"]:
        return await cb.answer("✅ تو قبلاً ثبت‌نام کردی!", show_alert=True)
    if len(ev["party"]) >= CFG["dungeon_max_party"]:
        return await cb.answer("😢 ظرفیتِ گروه پر شد!", show_alert=True)
    p = await _need_player(cb)
    if not p:
        return
    if uid in ev["party"] or len(ev["party"]) >= CFG["dungeon_max_party"] or ev["phase"] != "join":
        return await cb.answer("⌛ ثبت‌نام بسته شد.", show_alert=True)      # بعد از await دوباره چک (ظرفیت/زمان)
    ev["party"].append(uid)
    ev["names"][uid] = p.get("name", "یه بازیکن")
    ev["dirty"] = True
    await cb.answer(f"🚪 وارد شدی! ({len(ev['party'])} نفر)")


async def _dungeon_vote(cb: CallbackQuery, eid: str, room: int, action: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "dungeon" or ev["done"] or ev["phase"] != "room" or ev["room"] != room:
        return await cb.answer("⌛ این رأی‌گیری تموم شده.", show_alert=True)
    if uid not in ev["party"]:
        return await cb.answer("❌ تو تو این دسته نیستی!", show_alert=True)
    if action not in ACTIONS:
        return await cb.answer()
    ev["votes"][uid] = action
    await cb.answer(f"🗳 رأی دادی: {ACTIONS[action]}")


def _roster(ev: dict, party: list[int]) -> str:
    return "، ".join(ev["names"].get(u, "—") for u in party)


async def _vote_round(chat_id: int, ev: dict, idx: int, text: str, party: list[int]) -> tuple[int | None, dict]:
    """یه دورِ رأی‌گیری: پیام + دکمه‌ها، صبر تا همه رأی بدن (یا تایمر)، بعد بستنِ رأی‌گیری."""
    eid = ev["id"]
    rows = [[(ACTIONS[a], f"gev:d:{eid}:{idx}:{a}") for a in ("fight", "guard", "search")]]
    ev["room"], ev["votes"] = idx, {}
    mid = await _send(chat_id, text, rows)
    waited = 0
    while waited < CFG["dungeon_room_sec"] and len(ev["votes"]) < len(party):
        await asyncio.sleep(1)
        waited += 1
    ev["room"] = -1                                 # رأی‌گیری بسته شد (کلیکِ دیرهنگام → «⌛»)
    return mid, dict(ev["votes"])


def _play_round(room: dict, votes: dict, st: dict, ev: dict, n: int, avg_power: float, ref: float) -> dict:
    """حلِ یه دور (اتاق یا دورِ نگهبان). خالص — بدونِ I/O. نتیجه: dict با ok/choice/tally/lines/lives_lost."""
    choice, tally, consensus = gw.tally_votes(votes)
    for u, a in votes.items():
        s = st["per"].setdefault(u, {"votes": 0, "best": 0})
        s["votes"] += 1
        if a == room["best"]:
            s["best"] += 1
    p = gw.success_chance(room, choice, n, avg_power, ref, consensus)
    p = min(0.95, p + st["next_bonus"])
    st["next_bonus"] = 0.0
    ok = random.random() < p
    lines: list[str] = []
    lives_lost = 0
    finds = DUNGEON_FINDS(ev["dtype"])
    rtype = room["type"]
    if ok:
        lines.append(gw.room_ok_text(rtype, choice or "guard"))
        # ⚔️ غنیمتِ دشمن
        if choice == "fight" and rtype in ("combat", "elite") and random.random() < (0.6 if rtype == "elite" else 0.35):
            if st["bonus"] < CFG["dungeon_bonus_cap"]:
                st["bonus"] += 0.06
                it = random.choice(finds)
                st["finds"].append(it)
                lines.append(f"🩸 دشمن چیزی از خودش جا گذاشت: **{it}**")
        # 🔍 کشفِ پنهان
        if choice == "search" and rtype in ("explore", "trap", "treasure"):
            if rtype == "treasure" or random.random() < (0.7 if room["best"] == "search" else 0.35):
                if st["bonus"] < CFG["dungeon_bonus_cap"]:
                    st["bonus"] += 0.06
                    it = random.choice(finds)
                    st["finds"].append(it)
                    lines.append(f"✨ کشفِ پنهان: **{it}**")
            if rtype in ("explore", "trap") and random.random() < 0.30:
                st["next_bonus"] = 0.06
                lines.append("🧭 یه مسیرِ میان‌بر/اطلاعاتِ مفید پیدا کردین — دورِ بعدی راحت‌تره!")
        elif rtype == "treasure" and choice in ("fight", "guard") and random.random() < 0.5:
            if st["bonus"] < CFG["dungeon_bonus_cap"]:
                st["bonus"] += 0.06
                it = random.choice(finds)
                st["finds"].append(it)
                lines.append(f"💰 از گنج یه چیزِ ارزشمند بیرون کشیدین: **{it}**")
    else:
        lines.append(gw.room_fail_text(rtype))
        if choice == "guard" and random.random() < CFG["dungeon_guard_save"]:
            lines.append("🛡 دفاعِ دسته از بدترین ضربه جلوگیری کرد — جونی از دست نرفت!")
        else:
            lives_lost = 1
    return {"ok": ok, "choice": choice, "tally": tally, "lines": lines, "lives_lost": lives_lost,
            "p": p, "consensus": consensus}


def DUNGEON_FINDS(dtype: str) -> list[str]:
    return gw.DUNGEON_TYPES.get(dtype, gw.DUNGEON_TYPES["bone_crypt"])["finds"]


async def _run_dungeon(chat_id: int, ev: dict):
    try:
        # ─── ثبت‌نام (اگه ظرفیت پر شد زودتر شروع می‌شه) ───
        waited = 0
        while waited < CFG["dungeon_join_sec"] and len(ev["party"]) < CFG["dungeon_max_party"]:
            await asyncio.sleep(1)
            waited += 1
            if ev["dirty"] and waited % 3 == 0:
                ev["dirty"] = False
                await _edit(chat_id, ev["mid"], _dungeon_entry_text(ev, CFG["dungeon_join_sec"] - waited), ev["join_rows"])
        ev["phase"] = "closing"
        party = list(ev["party"])
        if len(party) < CFG["dungeon_min_party"]:
            ev["done"] = True
            await _edit(chat_id, ev["mid"], f"🚪 «{ev['name']}» بسته شد — کافی نفر نیومد ({len(party)}/{CFG['dungeon_min_party']}).")
            return
        players = {}
        for u in party:
            p = await aget_player(u)
            if p:
                players[u] = p
        party = [u for u in party if u in players]
        n = len(party)
        if n < CFG["dungeon_min_party"]:
            ev["done"] = True
            await _edit(chat_id, ev["mid"], f"🚪 «{ev['name']}» بسته شد — کافی بازیکنِ معتبر نبود.")
            return
        for u in party:
            ev["names"][u] = players[u].get("name", "—")
        avg_power = sum(_power(players[u]) for u in party) / n
        region, dtype = ev["region"], ev["dtype"]
        ref = gw.region_ref_power(region)
        guardian, epithet = gw.guardian_for(region, dtype)
        rooms = gw.plan_rooms(dtype, n=CFG["dungeon_random_rooms"])
        st = {"lives": CFG["dungeon_lives"], "rooms_ok": 0, "rooms_total": 0, "final_ok": False, "final_wins": 0,
              "bonus": 0.0, "next_bonus": 0.0, "finds": [], "per": {}, "rounds": 0, "failed_at": None}
        ev["phase"] = "room"
        await _edit(chat_id, ev["mid"], f"🚪 «{ev['name']}» — دسته‌ی {n} نفره وارد شد!")
        await _send(chat_id, f"⚔️ **ورود!** {_roster(ev, party)}\n{gw.lives_bar(st['lives'], CFG['dungeon_lives'])} جان‌های دسته: {st['lives']}\n"
                             f"📍 {gw.region_label(region)}")
        room_imgs = CFG["dungeon_room_images"]

        # ─── اتاق‌های تصادفی ───
        for i, room in enumerate(rooms):
            if room_imgs > 0 and room["type"] in ("elite", "hazard", "treasure"):
                img = gm.dungeon_room_image(dtype, chat_id)
                if img and await gm.send_photo_safe(_BOT, chat_id, img, f"{room['emoji']} {room['label']} — {ev['name']}"):
                    room_imgs -= 1
            head = (f"🚪 **اتاقِ {i + 1} از 4** — {room['emoji']} {room['label']}\n"
                    f"{gw.lives_bar(st['lives'], CFG['dungeon_lives'])}  |  ✅ موفق: {st['rooms_ok']}\n\n{room['text']}\n\n"
                    f"🗳 تاکتیک چیه؟ ({CFG['dungeon_room_sec']} ثانیه)")
            mid, votes = await _vote_round(chat_id, ev, i, head, party)
            res = _play_round(room, votes, st, ev, n, avg_power, ref)
            st["rooms_total"] += 1
            st["rounds"] += 1
            st["lives"] -= res["lives_lost"]
            if res["ok"]:
                st["rooms_ok"] += 1
            picked = (f"🗳 رأی‌ها: {gw.vote_bar(res['tally'])} → **{ACTIONS[res['choice']]}**" if res["choice"]
                      else "🗳 هیچ‌کس رأی نداد!")
            verdict = "✅ **موفق شدین!**" if res["ok"] else (
                f"💥 **شکست!** {gw.lives_bar(st['lives'], CFG['dungeon_lives'])} ({max(0, st['lives'])} جان مونده)"
                if res["lives_lost"] else "⚠️ **شکست، ولی جونی از دست نرفت.**")
            hint = "" if res["choice"] == room["best"] else f"\n💡 تاکتیکِ بهتر: {ACTIONS[room['best']]}"
            await _edit(chat_id, mid, f"🚪 **اتاقِ {i + 1} از 4** — {room['emoji']} {room['label']}\n\n{room['text']}\n\n"
                                      f"{picked}\n{verdict}\n" + "\n".join(res["lines"]) + hint)
            if st["lives"] <= 0:
                st["failed_at"] = i + 1
                break
            await asyncio.sleep(2)

        # ─── نگهبانِ نهایی (اتاقِ ۴): ۳ دورِ رأی‌گیری، حداقل ۲ دورِ موفق لازمه ───
        if st["lives"] > 0:
            await asyncio.sleep(1)
            intro = (f"👑 **اتاقِ ۴ از ۴ — نگهبانِ نهایی!**\n\n{guardian}" + (f" — _{epithet}_" if epithet else "") +
                     f"\nاین‌جا آخرِ خطه. **۳ دور** نبرده؛ حداقل **۲ دور** رو باید ببرین.\n"
                     f"{gw.lives_bar(st['lives'], CFG['dungeon_lives'])}  |  ✅ اتاق‌های موفق: {st['rooms_ok']}/{st['rooms_total']}")
            fimg = gm.dungeon_final_image(dtype, chat_id)
            await _scene(chat_id, intro, None, fimg, f"👑 {guardian} — {ev['name']}")
            await asyncio.sleep(2)
            g_hp = 3
            for r in range(3):
                room = gw.final_round(r, guardian)
                head = (f"👑 **نگهبانِ نهایی — دورِ {r + 1} از 3**\n"
                        f"{'🟥' * g_hp}{'⬛' * (3 - g_hp)}  |  {gw.lives_bar(st['lives'], CFG['dungeon_lives'])}\n\n"
                        f"{room['text']}\n\n🗳 تاکتیک چیه؟ ({CFG['dungeon_room_sec']} ثانیه)")
                mid, votes = await _vote_round(chat_id, ev, CFG["dungeon_random_rooms"] + r, head, party)
                res = _play_round(room, votes, st, ev, n, avg_power, ref)
                st["rounds"] += 1
                st["lives"] -= res["lives_lost"]
                if res["ok"]:
                    st["final_wins"] += 1
                    g_hp -= 1
                picked = (f"🗳 رأی‌ها: {gw.vote_bar(res['tally'])} → **{ACTIONS[res['choice']]}**" if res["choice"]
                          else "🗳 هیچ‌کس رأی نداد!")
                verdict = "✅ **ضربه‌ی کاری خورد!**" if res["ok"] else (
                    f"💥 **نگهبان برگشت!** {gw.lives_bar(st['lives'], CFG['dungeon_lives'])}"
                    if res["lives_lost"] else "⚠️ **نگهبان برگشت، ولی دسته ایستاد.**")
                hint = "" if res["choice"] == room["best"] else f"\n💡 تاکتیکِ بهتر: {ACTIONS[room['best']]}"
                await _edit(chat_id, mid, f"👑 **نگهبانِ نهایی — دورِ {r + 1} از 3**\n\n{room['text']}\n\n"
                                          f"{picked}\n{verdict}\n" + "\n".join(res["lines"]) + hint)
                if st["lives"] <= 0:
                    st["failed_at"] = 4
                    break
                if st["final_wins"] >= 2:
                    break                      # نگهبان شکست خورد
                if (r + 1) - st["final_wins"] >= 2:
                    break                      # دو دور باخته‌ین → دیگه نمی‌شه ۲ از ۳ برد
                await asyncio.sleep(2)
            st["final_ok"] = st["lives"] > 0 and st["final_wins"] >= 2
            if not st["final_ok"] and st["failed_at"] is None:
                st["failed_at"] = 4
        await _dungeon_finish(chat_id, ev, party, st, guardian)
    except Exception as e:  # noqa: BLE001
        log_sync(f"🔴 gap dungeon error: {e}", "ERROR")
        try:
            await _send(chat_id, f"⚠️ دروازه‌ی «{ev['name']}» به‌خاطر یه مشکلِ فنی بسته شد. (جایزه‌ای کم یا زیاد نشد)")
        except Exception:
            pass
    finally:
        ev["room"] = -1
        ev["done"] = True


def _dungeon_perf(st: dict) -> float:
    """امتیازِ عملکرد ۰..۱: اتاق‌های موفق + جان‌های باقی‌مانده + شکستِ نگهبان."""
    rooms = st["rooms_ok"] / max(1, CFG["dungeon_random_rooms"])
    lives = max(0, st["lives"]) / max(1, CFG["dungeon_lives"])
    return 0.5 * rooms + 0.3 * lives + 0.2 * (1.0 if st["final_ok"] else 0.0)


async def _dungeon_finish(chat_id: int, ev: dict, party: list[int], st: dict, guardian: str):
    total_rounds = max(1, st["rounds"])
    # MVP: هر رأی ۱ امتیاز + هر رأیِ هم‌راستا با بهترین تاکتیک ۳ امتیاز اضافه
    scores = {u: 3 * st["per"].get(u, {}).get("best", 0) + st["per"].get(u, {}).get("votes", 0) for u in party}
    mvp = max(party, key=lambda u: (scores[u], u)) if party and max(scores.values(), default=0) > 0 else None
    finds_txt = ("\n🔍 **کشفیاتِ پنهان:** " + "، ".join(st["finds"])) if st["finds"] else ""
    perf = _dungeon_perf(st)
    size_mult = 1 + min(0.5, 0.1 * (len(party) - 2))
    bonus = 1 + min(CFG["dungeon_bonus_cap"], st["bonus"])
    success = st["final_ok"] and st["lives"] > 0
    if success:
        head = [f"🏆 **«{ev['name']}» فتح شد!** {guardian} شکست خورد.",
                f"{gw.lives_bar(st['lives'], CFG['dungeon_lives'])} | ✅ اتاق‌ها: {st['rooms_ok']}/{st['rooms_total']} | 👑 نگهبان: {st['final_wins']}/3 دور"]
    else:
        where = "نگهبانِ نهایی" if st["failed_at"] == 4 else f"اتاقِ {st['failed_at']}"
        head = [f"💀 **«{ev['name']}» دسته رو شکست داد!** (تو {where})",
                f"✅ اتاق‌های موفق: {st['rooms_ok']}/{st['rooms_total']}"]
    lines = head + [finds_txt] if finds_txt else head
    if mvp is not None:
        lines.append(f"\n🌟 **MVP دسته: {ev['names'].get(mvp, '—')}** — {st['per'].get(mvp, {}).get('best', 0)} تاکتیکِ درست از {st['per'].get(mvp, {}).get('votes', 0)} رأی")
    lines.append("")
    boxes = ["wood_box", "bronze_box", "silver_box", "gold_box"]
    tier = {3: [25, 35, 28, 12], 2: [35, 40, 20, 5], 1: [55, 35, 10, 0]}.get(max(1, min(3, st["lives"])), [55, 35, 10, 0])
    shift = min(len(st["finds"]), 3) * 6               # هر کشفِ پنهان: ۶ امتیاز از چوبی به نقره‌ای
    move = min(shift, tier[0])
    tier = [tier[0] - move, tier[1], tier[2] + move, tier[3]]
    for u in party:
        try:
            async with player_lock(u):
                p = await aget_player(u)
                if not p:
                    continue
                part = 0.6 + 0.4 * min(1.0, st["per"].get(u, {}).get("votes", 0) / total_rounds)   # مشارکت
                mvp_mult = 1.15 if u == mvp else 1.0
                lvl = p.get("level", 1)
                line = ""
                if success:
                    f = (0.35 + 0.85 * perf) * size_mult * part * bonus * mvp_mult
                    zen, leveled = _grant_xp_zen(p, int((350 + lvl * 6) * f), int((140 + lvl * 4) * f))
                    line = f"• {p.get('name', '—')}: +{zen:,} Zen"
                    if _box_cap_ok(p):
                        bid = random.choices(boxes, weights=tier, k=1)[0]
                        got = _grant_box(p, bid)
                        if got:
                            _box_cap_use(p)
                            b = ls.get_box(bid)
                            line += f" | {b['emoji']} {b['name']} ({got[0]})"
                else:
                    # دلداری: متناسب با پیشرفت (بدونِ باکس)
                    zen, leveled = _grant_xp_zen(p, int((60 + lvl * 2 + 40 * st["rooms_ok"]) * part),
                                                 20 + 10 * st["rooms_ok"])
                    line = f"• {p.get('name', '—')}: +{zen:,} Zen (دلداری)"
                await asave_player(u, p)
        except Exception as e:  # noqa: BLE001
            log_sync(f"🔴 gap dungeon reward failed for {u}: {e}", "ERROR")
            continue
        if u == mvp:
            line += " 🌟"
        if part < 1.0:
            line += f" ({int(part * 100)}٪ سهم — مشارکتِ کمتر)"
        lines.append(line + (" 🎉 لول‌آپ!" if leveled else ""))
    await _send(chat_id, "\n".join(lines[:22]))
    log_sync(f"👥🚪 **GAP DUNGEON {'CLEARED' if success else 'FAILED'}**\n📍 `{chat_id}`\n🏷 {ev['name']} ({ev['region']})\n👥 {len(party)} نفر | ❤️ {st['lives']} | ✅ {st['rooms_ok']}/{st['rooms_total']}", "GROUP")


# ============================================================
#  ⏱ زمان‌بندیِ خودکار
# ============================================================
async def _get_settings(chat_id: int) -> dict:
    st = _SETTINGS.get(chat_id)
    if st is None:
        st = await asyncio.to_thread(_db_get_settings, chat_id)
        st.setdefault("enabled", True)
        _SETTINGS[chat_id] = st
    return st


async def _save_settings(chat_id: int):
    await asyncio.to_thread(_db_save_settings, chat_id, _SETTINGS[chat_id])


def _expire_events(chat_id: int, now: float) -> list[dict]:
    out = []
    for ev in list(_live_events(chat_id).values()):
        if not ev["done"] and ev["type"] in ("box", "ambush") and now > ev["expires"]:
            ev["done"] = True
            out.append(ev)
    return out


async def _scheduler_tick():
    now = time.time()
    # باس‌های زنده‌ای که شاید (مثلاً با ری‌استارت/ادمین) از _BOSS_CHATS جا مونده باشن
    try:
        for b in await asyncio.to_thread(_db_list_alive_bosses):
            _BOSS_CHATS.add(b["chat_id"])
    except Exception as e:  # noqa: BLE001
        log_sync(f"🟠 gap boss reconcile failed: {e}", "ERROR")
    for chat_id in list(_ACT.keys()):
        for ev in _expire_events(chat_id, now):                       # صندوق/هیولای بی‌صاحب
            if ev["type"] == "box":
                await _edit(chat_id, ev["mid"], "📦 صندوق ناپدید شد... کسی بازش نکرد 😴" if not ev["claimed"]
                            else "📦 صندوق ناپدید شد.")
            else:
                await _edit(chat_id, ev["mid"], f"💨 {ev['name']} فرار کرد!")
        st = await _get_settings(chat_id)
        if not st.get("enabled", True):
            continue
        if now - _LAST_CHAT_MSG.get(chat_id, 0) > CFG["active_window_sec"]:
            continue                                                  # گروه الان ساکته
        recent = _active_uids(chat_id, CFG["recent_members_sec"])
        if len(recent) < CFG["min_recent_members"] or _has_blocking_event(chat_id) or chat_id in _BOSS_CHATS:
            continue                                                  # رِیدِ باس یا رویدادِ دیگه → رویدادِ جدید نه
        if st.get("day") != _today():
            st["day"], st["count"] = _today(), 0
        if st["count"] >= CFG["max_events_per_day"]:
            continue
        if st.get("next_at") is None:
            st["next_at"] = now + random.uniform(*CFG["first_delay_sec"])
            await _save_settings(chat_id)
            continue
        if now < st["next_at"]:
            continue
        kind = await _pick_event_kind(chat_id, len(recent))
        st["count"] += 1
        st["next_at"] = now + random.uniform(CFG["interval_min_sec"], CFG["interval_max_sec"])
        await _save_settings(chat_id)
        _bg(_fire_event(chat_id, kind), f"fire_{kind}")               # ارسالِ عکس/متن نباید حلقه‌ی اصلی رو معطل کنه


async def _pick_event_kind(chat_id: int, n_recent: int) -> str:
    w = dict(CFG["weights"])
    boss = await asyncio.to_thread(_db_get_boss, chat_id)
    cd = await asyncio.to_thread(_db_boss_cooldown, chat_id)
    if n_recent < CFG["boss_min_members"] or (boss and boss.get("alive")) or cd > 0:
        w.pop("boss", None)
    if n_recent < CFG["dungeon_min_party"]:
        w.pop("dungeon", None)
    kinds, weights = zip(*w.items())
    return random.choices(kinds, weights=weights, k=1)[0]


async def _fire_event(chat_id: int, kind: str, region: str | None = None):
    try:
        if region is None:
            region, _how = await _detect_region(chat_id)
        if kind == "box":
            await _spawn_box(chat_id, region=region)
        elif kind == "ambush":
            await _spawn_ambush(chat_id, region=region)
        elif kind == "dungeon":
            await _spawn_dungeon(chat_id, region=region)
        elif kind == "boss":
            async with _boss_lock(chat_id):
                boss = await _spawn_boss(chat_id, auto=True, region=region)
            await _announce_boss_spawn(chat_id, boss, "👹 **یه باسِ خودکار وسطِ گروه ظاهر شد!**\n\n")
    except Exception as e:
        log_sync(f"🔴 gap group event ({kind}) failed in {chat_id}: {e}", "ERROR")


async def _main_loop():
    # بعد از ری‌استارت، اعضای اخیر و باس‌های زنده رو از DB برمی‌گردونیم
    try:
        now = time.time()
        for d in await asyncio.to_thread(_db_recent_members, CFG["recent_members_sec"]):
            _ACT.setdefault(d["chat_id"], {})[d["user_id"]] = d.get("last_seen", now)
    except Exception as e:
        log_sync(f"🟠 gap group events: activity reload failed: {e}", "ERROR")
    try:
        for b in await asyncio.to_thread(_db_list_alive_bosses):
            _BOSS_CHATS.add(b["chat_id"])
    except Exception as e:
        log_sync(f"🟠 gap group events: boss reload failed: {e}", "ERROR")
    last_sched = time.monotonic()
    while True:
        try:
            await _boss_watcher_tick()
            if time.monotonic() - last_sched >= CFG["scheduler_tick_sec"]:
                last_sched = time.monotonic()
                await _scheduler_tick()
        except Exception as e:
            log_sync(f"🔴 gap group events loop error: {e}", "ERROR")
        await asyncio.sleep(CFG["boss_tick_sec"])


# ============================================================
#  دستورها و کال‌بک‌ها
# ============================================================
async def cmd_gevents(msg: Message):
    if not is_group_msg(msg):
        return await msg.answer(MSG_NOT_GROUP)
    chat_id = msg.chat.id
    st = await _get_settings(chat_id)
    parts = (msg.text or "").split(maxsplit=1)
    arg = parts[1].strip().lower() if len(parts) > 1 else ""
    if arg in ("on", "off"):
        if not _is_admin(msg):
            return await msg.answer("❌ فقط ادمینِ ربات می‌تونه رویدادها رو روشن/خاموش کنه.")
        st["enabled"] = arg == "on"
        await _save_settings(chat_id)
    recent = len(_active_uids(chat_id, CFG["recent_members_sec"]))
    left = max(0, int(st.get("next_at", 0) - time.time()))
    region, how = await _detect_region(chat_id)
    how_fa = {"majority": "اکثریتِ بازیکن‌ها", "tie": "قرعه بینِ مساوی‌ها", "weighted": "اطلاعاتِ موقعیت نبود — تصادفی"}[how]
    await msg.answer(
        f"🎲 **رویدادهای گروه**: {'✅ روشن' if st.get('enabled', True) else '⛔ خاموش'}\n"
        f"👥 اعضای فعالِ اخیر: {recent} (حداقلِ لازم: {CFG['min_recent_members']})\n"
        f"📅 رویدادهای امروز: {st.get('count', 0) if st.get('day') == _today() else 0}/{CFG['max_events_per_day']}\n"
        f"🌍 منطقه‌ی فعلیِ رویدادها: {gw.region_label(region)} ({how_fa})\n"
        + (f"⏳ رویدادِ بعدی تقریباً {left // 60 + 1} دقیقه‌ی دیگه\n" if left else "")
        + "\n📦 صندوقِ اسرارآمیز | 🐺 حمله‌ی هیولا | 🚪 دروازه‌ی دانجن | 👹 باس\n"
          "هر لحظه با /graid باسِ گروه رو صدا کن!")


async def cmd_gdrop(msg: Message):
    if not _is_admin(msg):
        return
    if not is_group_msg(msg):
        return await msg.answer(MSG_NOT_GROUP)
    parts = (msg.text or "").split(maxsplit=2)
    kind = parts[1].strip().lower() if len(parts) > 1 else ""
    if kind not in ("box", "ambush", "dungeon", "boss"):
        return await msg.answer("📝 استفاده: `/gdrop box|ambush|dungeon|boss [منطقه]`")
    region = gw.normalize_region(parts[2]) if len(parts) > 2 else None
    _bg(_fire_event(msg.chat.id, kind, region), "gdrop")


async def cmd_gassets(msg: Message):
    if not _is_admin(msg):
        return
    gm.reset_cache()
    cov = gm.coverage(be.WORLD_BOSS_TEMPLATES)
    names = {"bosses": "👹 باس (فازها)", "bosses_defeated": "💀 باسِ شکست‌خورده (اختیاری)",
             "bosses_generic": "🧬 جایگزینِ عنصری (اختیاری)", "boxes": "📦 صندوق", "dungeons": "🚪 ورودیِ دانجن",
             "dungeon_rooms": "🏚 اتاقِ دانجن (اختیاری)", "dungeon_final": "👑 نگهبانِ نهایی", "monsters": "🐺 هیولا"}
    s = gm.stats()
    lines = [f"🖼 **پوششِ آرتِ رویدادها** (`{s['root']}`)", ""]
    for cat, (have, tot) in cov.items():
        lines.append(f"{names.get(cat, cat)}: {have}/{tot}")
    lines.append(f"\n📤 ارسال‌شده: {s['sent']} | ❌ خطا: {s['failed']} | ⏭ ردشده: {s['skipped']} | فایل‌های ایندکس‌شده: {s['indexed']}")
    await msg.answer("\n".join(lines))


async def on_callback(cb: CallbackQuery):
    parts = (cb.data or "").split(":")
    try:
        if parts[1] == "b":
            if parts[2] == "hit":
                return await _boss_hit(cb)
            if parts[2] == "def":
                return await _boss_defend(cb)
            return await _boss_status_cb(cb)
        if parts[1] == "x":
            return await _box_claim(cb, parts[2])
        if parts[1] == "a":
            return await _ambush_hit(cb, parts[2])
        if parts[1] == "d":
            if parts[3] == "join":
                return await _dungeon_join(cb, parts[2])
            return await _dungeon_vote(cb, parts[2], int(parts[3]), parts[4])
    except Exception as e:
        log_sync(f"🔴 gap group event callback error ({cb.data}): {e}", "ERROR")
        try:
            await cb.answer("⚠️ یه مشکلی پیش اومد، دوباره امتحان کن.", show_alert=True)
        except Exception:
            pass


def register_gap_group_events_handlers(dp):
    """تو bot_dual.py → register_gap_group_events_handlers(dp)"""
    global _BOT
    _BOT = dp.bot

    dp.register_message(cmd_graid, commands=["graid"])
    dp.register_message(group_word(cmd_graid, "/graid"), text=["باس گروه", "رید گروه"])
    dp.register_message(cmd_gevents, commands=["gevents"])
    dp.register_message(cmd_gdrop, commands=["gdrop"])
    dp.register_message(cmd_gassets, commands=["gassets"])
    dp.register_callback(on_callback, data_startswith="gev:")

    # ثبتِ فعالیتِ گروه‌ها (بدونِ دستکاریِ gap_dispatcher): قبل از هر پیامِ متنی صدا زده می‌شه
    if not getattr(dp, "_gev_wrapped", False):
        orig = dp._dispatch_message

        async def _wrapped(msg, text):
            try:
                _note_activity(msg)
            except Exception:
                pass
            return await orig(msg, text)
        dp._dispatch_message = _wrapped
        dp._gev_wrapped = True

    _bg(_main_loop(), "main_loop")
