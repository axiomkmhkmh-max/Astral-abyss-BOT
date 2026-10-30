# ============================================================
#  ASTRAL ABYSS — Gap Group Events 👹📦🚪
# ------------------------------------------------------------
#  تا الان باس/دانجن/باکس تو گپ فقط تو چتِ خصوصی بود و گروه‌ها هیچ
#  محتوایی نداشتن (رِیدِ گروهی فقط نسخه‌ی تلگرام داشت). این فایل
#  گروه‌های گپ رو زنده می‌کنه:
#
#   👹 باسِ گروهی  — /graid (یا کلمه‌ی «باس گروه»): همون موتورِ boss_engine
#                    (فازها، سپر، حمله‌ی ناحیه‌ای، خشم، پاداش‌ها) + باکسِ جایزه
#   📦 صندوقِ اسرارآمیز — خودکار وسطِ گروه می‌افته؛ اولین‌ها بازش می‌کنن
#   🐺 حمله‌ی هیولا — یه هیولا ظاهر می‌شه و گروه دسته‌جمعی می‌زنتش
#   🚪 دروازه‌ی دانجن — چندنفره: ورود، ۴ اتاق، رأی‌گیریِ تاکتیک (حمله/دفاع/
#                      جستجو)، لوتِ مشترک و باکس
#
#  رویدادها خودکارن، ولی فقط تو گروه‌هایی که فعالن (چند نفر تو چند دقیقه‌ی
#  اخیر پیام داده)، با فاصله‌ی چند دقیقه‌ای و سقفِ روزانه — اسپم نمی‌شه.
#
#  دستورها (فقط تو گروه):
#     /graid [force]     شروع/نمایشِ رِیدِ باسِ گروه (force فقط ادمینِ ربات)
#     /gevents           وضعیتِ رویدادهای خودکارِ گروه  (on/off فقط ادمینِ ربات)
#     /gdrop <نوع>       (ادمینِ ربات) اجبارِ یه رویداد: box|ambush|dungeon|boss
#
#  وصل‌کردن: bot_dual.py →  register_gap_group_events_handlers(dp)
#  نکته: تنظیماتِ عددی (فاصله‌ها، شانس‌ها، پاداش‌ها) بالای فایل تو CFG ـه.
# ============================================================
from __future__ import annotations

import asyncio
import math
import random
import time
from datetime import datetime, timezone

from gap_types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from gap_group_gate import is_group_msg, group_word

import boss_engine as be
import lootbox_shop as ls
from characters import ALL_CHARACTERS
from database import get_db, aget_player, asave_player, player_lock
from katana_system import dmg_bonus, crit_bonus, lifesteal_bonus, element_amplify_bonus
from logger import log_sync

# ─── تنظیماتِ قابل‌تغییر ─────────────────────────────────────────
CFG = {
    "tick_sec": 15,                 # هر چند ثانیه واچر (باس + زمان‌بندی) یه دور می‌زنه
    "active_window_sec": 15 * 60,   # «گروهِ فعال» = تو این بازه حداقل یه پیام
    "recent_members_sec": 2 * 3600,  # اعضای «اخیر» برای محاسبه‌ی تعدادِ بازیکن
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
    # دانجن
    "dungeon_join_sec": 90,
    "dungeon_room_sec": 25,
    "dungeon_max_party": 8,
    "dungeon_min_party": 2,
    # باس
    "boss_hit_cd_sec": 8,
    "boss_respawn_cd_sec": 10 * 60,  # بعد از کشتنِ باس، تا رِیدِ بعدی (مثلِ نسخه‌ی تلگرام)
    "boss_ttl_sec": 2 * 3600,       # باسی که تو این مدت کشته نشه ناپدید می‌شه (بدونِ پاداش)
}

MSG_NOT_GROUP = "👥 این دستور فقط داخلِ یه **گروه** کار می‌کنه."
MSG_NEED_START = "❌ اول تو پیوی ربات /start بزن و کاراکتر بساز، بعد بیا گروه!"

# ─── وضعیتِ درون‌حافظه‌ای ────────────────────────────────────────
_ACT: dict[int, dict[int, float]] = {}        # chat_id -> {uid: آخرین پیام}
_LAST_CHAT_MSG: dict[int, float] = {}         # chat_id -> آخرین پیامِ هر کسی
_EVENTS: dict[int, dict[str, dict]] = {}      # chat_id -> {event_id: event}
_SETTINGS: dict[int, dict] = {}               # chat_id -> تنظیمات (کش)
_LAST_DB_TOUCH: dict[tuple, float] = {}
_BOSS_LOCKS: dict[int, asyncio.Lock] = {}
_BOT = None                                   # GapBotAdapter (تو register ست می‌شه)


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


def _eid() -> str:
    return f"{random.randrange(16**5):05x}"


def _boss_lock(chat_id: int) -> asyncio.Lock:
    return _BOSS_LOCKS.setdefault(chat_id, asyncio.Lock())


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


def _note_activity(msg: Message):
    if not is_group_msg(msg) or not msg.from_user:
        return
    cid, uid, now = msg.chat.id, msg.from_user.id, time.time()
    _ACT.setdefault(cid, {})[uid] = now
    _LAST_CHAT_MSG[cid] = now
    key = (cid, uid)
    if now - _LAST_DB_TOUCH.get(key, 0) > 120:     # حداکثر هر ۲ دقیقه یه نوشتن
        _LAST_DB_TOUCH[key] = now
        asyncio.create_task(asyncio.to_thread(_db_touch_member, cid, uid))


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


# ============================================================
#  👹 باسِ گروهی
# ============================================================
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


async def _spawn_boss(chat_id: int, template_id: str | None = None, auto: bool = False) -> dict:
    if not template_id or template_id not in be.WORLD_BOSS_TEMPLATES:
        template_id = random.choice(list(be.WORLD_BOSS_TEMPLATES.keys()))
    boss = be.spawn_boss(template_id, chat_id)
    boss["gap"] = True
    boss["auto"] = auto
    await asyncio.to_thread(_db_save_boss, chat_id, boss)
    log_sync(f"👥👹 **GAP GROUP BOSS** {'(auto) ' if auto else ''}{boss['name']}\n📍 چت: `{chat_id}`", "GROUP")
    return boss


async def cmd_graid(msg: Message):
    if not is_group_msg(msg):
        return await msg.answer(MSG_NOT_GROUP)
    chat_id, uid = msg.chat.id, msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("character"):
        return await msg.answer(MSG_NEED_START)
    parts = (msg.text or "").split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else None

    async with _boss_lock(chat_id):
        boss = await asyncio.to_thread(_db_get_boss, chat_id)
        if arg == "force":
            if not _is_admin(msg):
                return await msg.answer("❌ فقط ادمینِ ربات می‌تونه رِید رو force کنه!")
            boss = await _spawn_boss(chat_id)
            return await msg.answer("🛠 ادمین رِید رو دوباره شروع کرد!\n\n" + await _boss_status(boss),
                                    reply_markup=_kb(_boss_rows(chat_id, boss)))
        if boss and boss.get("alive"):
            be.tick_shield_regen(boss)
            await asyncio.to_thread(_db_save_boss, chat_id, boss)
            return await msg.answer(await _boss_status(boss), reply_markup=_kb(_boss_rows(chat_id, boss)))
        cd = await asyncio.to_thread(_db_boss_cooldown, chat_id)
        if cd > 0:
            m, s = divmod(cd, 60)
            return await msg.answer(f"😴 باسِ قبلیِ این گروه تازه شکست خورده — {m} دقیقه و {s} ثانیه تا رِیدِ بعدی صبر کن.")
        tid = arg if arg and arg in be.WORLD_BOSS_TEMPLATES else None
        boss = await _spawn_boss(chat_id, tid)
    await msg.answer("👥 **رِیدِ باسِ این گروه شروع شد!**\nهرکی تو گروه هست می‌تونه با دکمه‌ی زیر بزنتش.\n\n"
                     + await _boss_status(boss), reply_markup=_kb(_boss_rows(chat_id, boss)))


async def _boss_hit(cb: CallbackQuery):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    player = await _need_player(cb)
    if not player:
        return
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
            await _send(chat_id, f"🎉 **{pname}** توی همین رِید رسید به سطح **{player['level']}**!")
        if res.get("phase_enter_msg"):
            await _send(chat_id, res["phase_enter_msg"])

        if res["boss_killed"]:
            await asyncio.to_thread(_db_mark_boss_dead, chat_id, True)
            await _boss_killed(chat_id, boss, pname, dmg, crit, zen_gain)
            return await cb.answer("💀 باس رو کشتی!")
        await asyncio.to_thread(_db_save_boss, chat_id, boss)
    await cb.answer(f"💥 {dmg:,} دمیج زدی!" + (" کریت! 💥" if crit else "") + f" +{zen_gain:,} Zen")


async def _boss_killed(chat_id: int, boss: dict, last_name: str, last_dmg: int, crit: bool, zen_gain: int):
    rewards, speed_kill = be.distribute_rewards(boss, is_weekly_featured=False)
    # پاداش‌های باکسِ گروهی: MVP نقره‌ای، پرتلاش‌ها برنزی، بقیه چوبی
    ranked = sorted(boss.get("contributors", {}).items(),
                    key=lambda kv: -(kv[1].get("dmg", 0) + kv[1].get("shield_dmg", 0)))
    box_lines = []
    for rank, (suid, c) in enumerate(ranked):
        ruid = int(suid)
        box_id = "silver_box" if rank == 0 else ("bronze_box" if c.get("hits", 0) >= 5 else "wood_box")
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

    async def _lookup(u):
        return await _name(int(u))
    summary = await be.build_kill_summary(boss, rewards, speed_kill, _lookup)
    extra = ("\n\n🎁 **باکسِ جایزه (بالاترین‌ها):**\n" + "\n".join(box_lines)) if box_lines else ""
    await _send(chat_id, f"💥 {last_name} ضربه‌ی آخر رو زد ({last_dmg:,})!\n\n{summary}{extra}")
    log_sync(f"👥👹 **GAP GROUP RAID CLEARED**\n📍 `{chat_id}`\n🏷️ {boss['name']}\n👥 {len(boss.get('contributors', {}))} نفر", "GROUP")


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


async def _boss_watcher_tick():
    """سپر/حمله‌ی ناحیه‌ای/خشم رو حتی وقتی کسی نمی‌زنه به‌روز نگه می‌داره + ناپدیدیِ باسِ قدیمی."""
    for boss in await asyncio.to_thread(_db_list_alive_bosses):
        chat_id = boss["chat_id"]
        async with _boss_lock(chat_id):
            fresh = await asyncio.to_thread(_db_get_boss, chat_id)
            if not fresh or not fresh.get("alive"):
                continue
            boss = fresh
            if time.time() - boss.get("spawn_time", time.time()) > CFG["boss_ttl_sec"]:
                await asyncio.to_thread(_db_mark_boss_dead, chat_id, False)
                await _send(chat_id, f"🌫 **{boss['name']}** از کسالت به تاریکی برگشت... (کسی نکشتش)\nبا /graid یکی دیگه صدا کنین.")
                continue
            changed = be.tick_shield_regen(boss)
            area_msg = be.tick_area_attack(boss)
            enrage_msg = be.tick_enrage(boss)
            if area_msg or enrage_msg:
                changed = True
                await _send(chat_id, area_msg or enrage_msg, _boss_rows(chat_id, boss))
            if changed:
                await asyncio.to_thread(_db_save_boss, chat_id, boss)


# ============================================================
#  📦 صندوقِ اسرارآمیز
# ============================================================
def _pick_box() -> str:
    ids, weights = zip(*CFG["box_pool"])
    return random.choices(ids, weights=weights, k=1)[0]


async def _spawn_box(chat_id: int, box_id: str | None = None) -> dict:
    box_id = box_id or _pick_box()
    box = ls.get_box(box_id)
    race = box_id in CFG["box_race"]
    eid = _eid()
    ev = {"type": "box", "id": eid, "box_id": box_id, "race": race, "claimed": [],
          "slots": 1 if race else CFG["box_party_slots"], "expires": time.time() + CFG["box_ttl_sec"],
          "done": False, "mid": None}
    _live_events(chat_id)[eid] = ev
    how = ("⚡ **فقط یه نفر** می‌تونه بازش کنه — سریع باش!" if race
           else f"🎁 به **{ev['slots']} نفرِ اول** هرکدوم یه باکس می‌رسه!")
    ev["mid"] = await _send(
        chat_id,
        f"📦 **یه صندوقِ اسرارآمیز وسطِ گروه افتاد!**\n\n{box['emoji']} {box['name']}\n{how}",
        [[("🔓 بازش کن!", f"gev:x:{eid}")]])
    return ev


async def _box_claim(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "box" or ev["done"]:
        return await cb.answer("⌛ این صندوق دیگه نیست.", show_alert=True)
    if uid in ev["claimed"]:
        return await cb.answer("😏 تو قبلاً بازش کردی!", show_alert=True)
    if len(ev["claimed"]) >= ev["slots"]:
        return await cb.answer("😢 دیر رسیدی — صندوق خالی شد!", show_alert=True)
    player = await _need_player(cb)
    if not player:
        return
    if player.get("level", 1) < CFG["box_min_level"]:
        return await cb.answer(f"🔒 برای باز کردنِ صندوق حداقل سطح {CFG['box_min_level']} لازمه.", show_alert=True)

    ev["claimed"].append(uid)       # قبل از await رزرو می‌کنیم تا دو نفر هم‌زمان اسلات رو نگیرن
    try:
        async with player_lock(uid):
            player = await aget_player(uid)
            if not _box_cap_ok(player):
                ev["claimed"].remove(uid)
                return await cb.answer(f"📦 سقفِ {CFG['box_daily_cap']} باکسِ رایگانِ امروزت پر شده. فردا بیا!", show_alert=True)
            got = _grant_box(player, ev["box_id"])
            if not got:
                ev["claimed"].remove(uid)
                return await cb.answer("❌ صندوق خراب بود!", show_alert=True)
            _box_cap_use(player)
            await asave_player(uid, player)
    except Exception:
        if uid in ev["claimed"]:
            ev["claimed"].remove(uid)
        raise
    box = ls.get_box(ev["box_id"])
    pname = player.get("name", "یه بازیکن")
    await _send(chat_id, f"🎉 **{pname}** {box['emoji']} {box['name']} رو باز کرد:\n" + "\n".join(f"• {g}" for g in got))
    await cb.answer("🎁 باز شد!")
    if len(ev["claimed"]) >= ev["slots"]:
        ev["done"] = True
        await _edit(chat_id, ev["mid"], f"📦 {box['emoji']} {box['name']} — صاحب پیدا کرد. 🎉")


# ============================================================
#  🐺 حمله‌ی هیولا
# ============================================================
AMBUSH_MONSTERS = [
    ("🐺 گرگِ سایه", "از تاریکیِ کنارِ گروه پرید بیرون!"),
    ("💀 اسکلتِ سرگردان", "استخوان‌هاش رو به هم می‌کوبه و میاد طرفتون!"),
    ("🗿 گولمِ سنگی", "زمین زیر پاش می‌لرزه!"),
    ("👻 روحِ شبِ سیاه", "از دیوار رد شد و وسطِ گروه سبز شد!"),
    ("🐗 گرازِ آبیس", "خرناسه می‌کشه و پاهاش رو به زمین می‌کوبه!"),
    ("🕷 عنکبوتِ غارنشین", "از سقف آویزون شد!"),
    ("🧟 غولِ باتلاق", "بوی گند و غرشش همه‌جا پیچید!"),
]


async def _spawn_ambush(chat_id: int) -> dict:
    n_active = max(1, min(8, len(_active_uids(chat_id, CFG["recent_members_sec"]))))
    hp = 500 + 220 * n_active
    name, flavor = random.choice(AMBUSH_MONSTERS)
    eid = _eid()
    ev = {"type": "ambush", "id": eid, "name": name, "hp": hp, "max_hp": hp, "hitters": {},
          "last_hit": {}, "expires": time.time() + CFG["ambush_ttl_sec"], "done": False, "mid": None}
    _live_events(chat_id)[eid] = ev
    ev["mid"] = await _send(chat_id, f"⚠️ **حمله‌ی هیولا!**\n\n{name} {flavor}\n❤️ {hp:,} HP\n\n"
                                      "همه با هم بزنینش!", [[("⚔️ حمله!", f"gev:a:{eid}")]])
    return ev


async def _ambush_hit(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "ambush" or ev["done"]:
        return await cb.answer("⌛ هیولا رفته یا کشته شده.", show_alert=True)
    now = time.time()
    since = now - ev["last_hit"].get(uid, 0)
    if since < CFG["ambush_hit_cd_sec"]:
        return await cb.answer(f"⏳ {int(CFG['ambush_hit_cd_sec'] - since) + 1} ثانیه صبر کن!", show_alert=True)
    player = await _need_player(cb)
    if not player:
        return
    ev["last_hit"][uid] = now
    raw, crit, _amp = _compute_hit(player)
    dmg = min(raw, ev["hp"])
    ev["hp"] -= dmg
    ev["hitters"][uid] = ev["hitters"].get(uid, 0) + dmg
    killed = ev["hp"] <= 0
    if killed:
        ev["done"] = True
    await cb.answer(f"💥 {dmg:,} دمیج!" + (" کریت!" if crit else "") + (f" | ❤️ {max(0, ev['hp']):,} مونده" if not killed else ""))
    if killed:
        await _ambush_victory(chat_id, ev, uid)


async def _ambush_victory(chat_id: int, ev: dict, killer_uid: int):
    hitters = ev["hitters"]
    total = sum(hitters.values()) or 1
    pool_zen = 700 + 300 * len(hitters)
    pool_xp = 250 + 120 * len(hitters)
    lines = [f"🏆 **{ev['name']} شکست خورد!**", f"👥 {len(hitters)} نفر شرکت کردن", ""]
    for uid, dmg in sorted(hitters.items(), key=lambda kv: -kv[1]):
        share = dmg / total
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
            await asave_player(uid, p)
        lines.append(f"• {p.get('name', '—')}: {dmg:,} دمیج → +{zen:,} Zen{extra}" + (" 🎉 لول‌آپ!" if leveled else ""))
    await _edit(chat_id, ev["mid"], f"⚔️ {ev['name']} — کشته شد ✅")
    await _send(chat_id, "\n".join(lines[:14]))


# ============================================================
#  🚪 دروازه‌ی دانجن (چندنفره)
# ============================================================
DUNGEON_NAMES = ["دخمه‌ی استخوان‌ها", "سردابِ فراموش‌شده", "غارِ هزارچشم", "معبدِ زیرِ آب",
                 "برجِ شکسته", "تونلِ سایه‌ها", "کارگاهِ متروکِ آهنگران"]
ACTIONS = {"fight": "⚔️ حمله", "guard": "🛡 دفاع", "search": "🔍 جستجو"}
ROOM_POOL = [
    ("🐺 گله‌ای از گرگ‌های سایه جلوی راهتونه و دندون نشون می‌دن!", "fight"),
    ("🦴 اسکلت‌های مسلح از دیوارها بیرون می‌ان — آماده‌ی نبردن!", "fight"),
    ("🕳 کفِ راهرو پر از سنگ‌فرش‌های مشکوکه؛ صدای تیک‌تیکِ یه مکانیزم میاد...", "search"),
    ("📜 روی دیوار نقش‌ها و حروفِ عجیبی حک شده؛ شاید رازی توشه...", "search"),
    ("🛡 یه نگهبانِ زره‌پوش با نیزه‌ی بلند راه رو بسته و ضربه‌اش رو آماده کرده!", "guard"),
    ("🔥 اژدهای کوچیکی نفسِ آتشین می‌کشه — همین الان شعله می‌زنه!", "guard"),
    ("🌫 مه‌ی بنفشی از شکاف‌ها نشت می‌کنه؛ هیچی رو نمی‌بینین...", "search"),
    ("🗿 گولمِ سنگیِ غولی از خواب بیدار شد و مشت‌هاش رو بالا می‌بره!", "guard"),
]


async def _spawn_dungeon(chat_id: int) -> dict:
    eid = _eid()
    ev = {"type": "dungeon", "id": eid, "name": random.choice(DUNGEON_NAMES), "party": [],
          "votes": {}, "room": -1, "phase": "join", "mid": None, "done": False,
          "expires": time.time() + CFG["dungeon_join_sec"] + 600}
    _live_events(chat_id)[eid] = ev
    ev["mid"] = await _send(
        chat_id,
        f"🚪 **دروازه‌ی «{ev['name']}» وسطِ گروه باز شد!**\n\n"
        f"👥 دسته‌جمعی وارد شین: ۴ اتاق، ‌هر اتاق یه تاکتیکِ درست داره و با **رأی‌گیری** انتخاب می‌شه.\n"
        f"⏳ {CFG['dungeon_join_sec']} ثانیه وقت دارین | حداقل {CFG['dungeon_min_party']} نفر",
        [[("🚪 وارد می‌شم!", f"gev:d:{eid}:join")]])
    asyncio.create_task(_run_dungeon(chat_id, ev))
    return ev


async def _dungeon_join(cb: CallbackQuery, eid: str):
    chat_id, uid = cb.message.chat.id, cb.from_user.id
    ev = _live_events(chat_id).get(eid)
    if not ev or ev["type"] != "dungeon" or ev["done"] or ev["phase"] != "join":
        return await cb.answer("⌛ ثبت‌نامِ این دروازه تموم شده.", show_alert=True)
    if uid in ev["party"]:
        return await cb.answer("✅ تو قبلاً ثبت‌نام کردی!", show_alert=True)
    if len(ev["party"]) >= CFG["dungeon_max_party"]:
        return await cb.answer("😢 ظرفیتِ گروه پر شد!", show_alert=True)
    if not await _need_player(cb):
        return
    ev["party"].append(uid)
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


async def _run_dungeon(chat_id: int, ev: dict):
    try:
        await asyncio.sleep(CFG["dungeon_join_sec"])
        party = list(ev["party"])
        if len(party) < CFG["dungeon_min_party"]:
            ev["done"] = True
            await _edit(chat_id, ev["mid"], f"🚪 «{ev['name']}» بسته شد — کافی نفر نیومد ({len(party)}/{CFG['dungeon_min_party']}).")
            return
        ev["phase"] = "room"
        players = {}
        for u in party:
            p = await aget_player(u)
            if p:
                players[u] = p
        party = [u for u in party if u in players]
        n = len(party)
        names = {u: players[u].get("name", "—") for u in party}
        powers = {u: _power(players[u]) for u in party}
        team_bonus = 1 + min(0.4, 0.08 * (n - 2))
        rooms = random.sample(ROOM_POOL, 4)
        lives = 3
        await _edit(chat_id, ev["mid"], f"🚪 «{ev['name']}» — دسته‌ی {n} نفره وارد شد!")
        await _send(chat_id, "⚔️ **ورود!** " + "، ".join(names.values()) + f"\n❤️ جان‌های دسته: {lives}")

        for i, (text, best) in enumerate(rooms):
            ev["room"], ev["votes"] = i, {}
            rows = [[(ACTIONS[a], f"gev:d:{ev['id']}:{i}:{a}") for a in ("fight", "guard", "search")]]
            mid = await _send(chat_id, f"🚪 **اتاقِ {i + 1} از 4**\n\n{text}\n\n🗳 تاکتیک چیه؟ ({CFG['dungeon_room_sec']} ثانیه)", rows)
            waited = 0
            while waited < CFG["dungeon_room_sec"] and len(ev["votes"]) < n:
                await asyncio.sleep(1)
                waited += 1
            tally: dict[str, int] = {}
            for a in ev["votes"].values():
                tally[a] = tally.get(a, 0) + 1
            if tally:
                top = max(tally.values())
                choice = random.choice([a for a, c in tally.items() if c == top])
                mult = 1.30 if choice == best else 0.85
                picked = f"رأیِ دسته: {ACTIONS[choice]}"
            else:
                choice, mult, picked = None, 0.80, "هیچ‌کس رأی نداد!"
            eff = sum(powers.values()) * mult * team_bonus * random.uniform(0.95, 1.05)
            need = sum(powers.values()) * (0.85 + 0.10 * i)
            ok = eff >= need
            if not ok:
                lives -= 1
            verdict = ("✅ موفق شدین!" if ok else f"💥 اتاق رو با زور رد کردین و ضربه خوردین! (❤️ {max(0, lives)} مونده)")
            hint = "" if choice == best else f"\n💡 تاکتیکِ درست: {ACTIONS[best]}"
            await _edit(chat_id, mid, f"🚪 **اتاقِ {i + 1} از 4**\n\n{text}\n\n{picked}\n{verdict}{hint}")
            if lives <= 0:
                break
            await asyncio.sleep(2)

        await _dungeon_finish(chat_id, ev, party, lives)
    except Exception as e:
        log_sync(f"🔴 gap dungeon error: {e}", "ERROR")
    finally:
        ev["done"] = True


async def _dungeon_finish(chat_id: int, ev: dict, party: list[int], lives: int):
    if lives <= 0:
        lines = [f"💀 **«{ev['name']}» دسته رو شکست داد!**", "تسلیمِ دلداری: هرکس مقداری Zen گرفت."]
        for u in party:
            async with player_lock(u):
                p = await aget_player(u)
                if p:
                    _grant_xp_zen(p, 60 + p.get("level", 1) * 2, 20)
                    await asave_player(u, p)
        return await _send(chat_id, "\n".join(lines))
    tier = {3: [25, 35, 28, 12], 2: [35, 40, 20, 5], 1: [55, 35, 10, 0]}[lives]
    boxes = ["wood_box", "bronze_box", "silver_box", "gold_box"]
    size_mult = 1 + min(0.5, 0.1 * (len(party) - 2))
    lines = [f"🏆 **«{ev['name']}» فتح شد!** ❤️ {lives}/3", ""]
    for u in party:
        async with player_lock(u):
            p = await aget_player(u)
            if not p:
                continue
            f = (0.6 + 0.2 * lives) * size_mult
            zen, leveled = _grant_xp_zen(p, int((350 + p.get("level", 1) * 6) * f), int((140 + p.get("level", 1) * 4) * f))
            line = f"• {p.get('name', '—')}: +{zen:,} Zen"
            if _box_cap_ok(p):
                bid = random.choices(boxes, weights=tier, k=1)[0]
                got = _grant_box(p, bid)
                if got:
                    _box_cap_use(p)
                    b = ls.get_box(bid)
                    line += f" | {b['emoji']} {b['name']} ({got[0]})"
            await asave_player(u, p)
        lines.append(line + (" 🎉 لول‌آپ!" if leveled else ""))
    await _send(chat_id, "\n".join(lines[:14]))


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
        if len(recent) < CFG["min_recent_members"] or _has_blocking_event(chat_id):
            continue
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
        await _fire_event(chat_id, kind)
        st["count"] += 1
        st["next_at"] = now + random.uniform(CFG["interval_min_sec"], CFG["interval_max_sec"])
        await _save_settings(chat_id)


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


async def _fire_event(chat_id: int, kind: str):
    try:
        if kind == "box":
            await _spawn_box(chat_id)
        elif kind == "ambush":
            await _spawn_ambush(chat_id)
        elif kind == "dungeon":
            await _spawn_dungeon(chat_id)
        elif kind == "boss":
            async with _boss_lock(chat_id):
                boss = await _spawn_boss(chat_id, auto=True)
            await _send(chat_id, "👹 **یه باسِ خودکار وسطِ گروه ظاهر شد!**\n\n" + await _boss_status(boss),
                        _boss_rows(chat_id, boss))
    except Exception as e:
        log_sync(f"🔴 gap group event ({kind}) failed in {chat_id}: {e}", "ERROR")


async def _main_loop():
    # بعد از ری‌استارت، اعضای اخیر رو از DB برمی‌گردونیم تا گروه‌ها دوباره «فعال» حساب بشن
    try:
        now = time.time()
        for d in await asyncio.to_thread(_db_recent_members, CFG["recent_members_sec"]):
            _ACT.setdefault(d["chat_id"], {})[d["user_id"]] = d.get("last_seen", now)
    except Exception as e:
        log_sync(f"🟠 gap group events: activity reload failed: {e}", "ERROR")
    ticks = 0
    while True:
        try:
            await _boss_watcher_tick()
            ticks += 1
            if ticks % max(1, 60 // CFG["tick_sec"]) == 0:           # زمان‌بندی هر ~۶۰ ثانیه
                await _scheduler_tick()
        except Exception as e:
            log_sync(f"🔴 gap group events loop error: {e}", "ERROR")
        await asyncio.sleep(CFG["tick_sec"])


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
    await msg.answer(
        f"🎲 **رویدادهای گروه**: {'✅ روشن' if st.get('enabled', True) else '⛔ خاموش'}\n"
        f"👥 اعضای فعالِ اخیر: {recent} (حداقلِ لازم: {CFG['min_recent_members']})\n"
        f"📅 رویدادهای امروز: {st.get('count', 0) if st.get('day') == _today() else 0}/{CFG['max_events_per_day']}\n"
        + (f"⏳ رویدادِ بعدی تقریباً {left // 60 + 1} دقیقه‌ی دیگه\n" if left else "")
        + "\n📦 صندوقِ اسرارآمیز | 🐺 حمله‌ی هیولا | 🚪 دروازه‌ی دانجن | 👹 باس\n"
          "هر لحظه با /graid باسِ گروه رو صدا کن!")


async def cmd_gdrop(msg: Message):
    if not _is_admin(msg):
        return
    if not is_group_msg(msg):
        return await msg.answer(MSG_NOT_GROUP)
    parts = (msg.text or "").split(maxsplit=1)
    kind = parts[1].strip().lower() if len(parts) > 1 else ""
    if kind not in ("box", "ambush", "dungeon", "boss"):
        return await msg.answer("📝 استفاده: `/gdrop box|ambush|dungeon|boss`")
    await _fire_event(msg.chat.id, kind)


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
    dp.register_callback(on_callback, data_startswith="gev:")

    # ثبتِ فعالیتِ گروه‌ها (بدونِ دستکاریِ gap_dispatcher): قبل از هر پیامِ متنی صدا زده می‌شه
    orig = dp._dispatch_message

    async def _wrapped(msg, text):
        try:
            _note_activity(msg)
        except Exception:
            pass
        return await orig(msg, text)
    dp._dispatch_message = _wrapped

    asyncio.create_task(_main_loop())
