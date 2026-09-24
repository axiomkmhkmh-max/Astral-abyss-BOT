# ============================================================
#  ASTRAL ABYSS — GROUP PLAY (بازیِ گروهی)
#  (group_play.py)
# ------------------------------------------------------------
#  group_system/group_handlers الان باسِ گروهی، /gtop و /gduel دارن؛
#  ولی گروه فقط وقتی یه نفر /graid بزنه «زنده‌ست». این ماژول دو تا
#  چیز اضافه می‌کنه که خودِ گروه رو به یه رقابت/بازیِ دائمی تبدیل می‌کنه:
#
#   ۱) 📦 صندوقِ گنج: وقتی تو گروه گفت‌وگوی واقعی جریان داره (چند نفر،
#      چند پیام، تو چند دقیقه‌ی اخیر)، ربات یه صندوق می‌ندازه؛ اولین
#      ۳ نفری که دکمه رو بزنن جایزه می‌گیرن. (کول‌داونِ ۴۵ دقیقه‌ای،
#      سقفِ ۶ صندوق در روز برای هر گروه — اسپم‌نشدن)
#   ۲) 🏆 رقابتِ هفتگیِ گروه‌ها: هر گروه امتیاز جمع می‌کنه (هر برداشتنِ
#      صندوق +۲، شکستِ باسِ گروهی +۲۰ و به‌ازای هر شرکت‌کننده +۲).
#      هر هفته ۳ گروهِ برتر (با حداقل ۳ عضوِ فعال) به همه‌ی اعضای فعال‌شون
#      Zen می‌دن → انگیزه‌ی اینکه هر عضو دوستانش رو به گروه/ربات بیاره.
#
#  هیچ فیلدی روی player اضافه نمی‌شه. کالکشن‌ها: group_play_state
#  (به‌ازای چت) و group_scores (به‌ازای هفته+چت). عضویتِ گروه از همون
#  group_members (group_system.touch_group_member) خونده می‌شه.
# ============================================================
import asyncio
import random
import secrets
import time
from collections import deque

from database import get_db, aget_player, asave_player, player_lock, system_col

# ─── تنظیمات صندوق ──────────────────────────────────────────────
CHEST_WINDOW = 600            # ثانیه — پنجره‌ی سنجشِ فعالیت
CHEST_MIN_MSGS = 15
CHEST_MIN_USERS = 3
CHEST_MIN_PLAYERS = 2         # حداقل چند نفر از فعال‌ها باید بازیکنِ ثبت‌نام‌شده باشن
CHEST_COOLDOWN = 45 * 60
CHEST_DAILY_CAP = 6
CHEST_TTL = 180
CHEST_SLOTS = 3
CHEST_BASE = [800, 500, 300]  # Zen برای نفرِ اول/دوم/سوم
CHEST_LEVEL_BONUS = 15        # + سطح × این
CHEST_LEVEL_CAP = 100
CHEST_CLAIMS_PER_USER_DAILY = 10

# ─── تنظیماتِ رقابتِ هفتگی ──────────────────────────────────────
SCORE_PER_CLAIM = 2
BOSS_KILL_SCORE = 20
BOSS_PER_CONTRIBUTOR = 2
BOSS_CONTRIBUTOR_CAP = 10
MIN_GROUP_MEMBERS = 3         # عضوِ فعالِ ۷ روزِ اخیر برای واردشدن به جدول/جایزه
MIN_SCORE_FOR_PRIZE = 5
WEEK_PRIZES = [3000, 2000, 1000]
MAX_PAID_PER_GROUP = 100
LOOP_INTERVAL = 3600

_acts: dict[int, deque] = {}
_chat_locks: dict[int, asyncio.Lock] = {}
_skip_until: dict[int, float] = {}
_chests: dict[str, dict] = {}
_claims_day: dict[int, tuple[int, int]] = {}
_tasks: set = set()


# ─── دیتا / ابزار ───────────────────────────────────────────────

def state_col():
    return get_db()["group_play_state"]


def scores_col():
    return get_db()["group_scores"]


def _members_col():
    from group_system import group_members_col
    return group_members_col()


def today_num() -> int:
    return int(time.time() // 86400)


def current_week() -> int:
    """هفته از دوشنبه (UTC) شروع می‌شه: روزِ ۰ epoch پنجشنبه بوده."""
    return (today_num() + 3) // 7


def _log(text: str, tag: str = "GROUP"):
    try:
        from logger import log_sync
        log_sync(text, tag)
    except Exception:
        pass


def _ledger(uid: int, zen: int, note: str):
    try:
        from economy_ledger import record_transaction
        record_transaction("group_reward", uid, amount=zen, note=note)
    except Exception:
        pass


def _spawn(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _lock(chat_id: int) -> asyncio.Lock:
    lk = _chat_locks.get(chat_id)
    if lk is None:
        lk = _chat_locks[chat_id] = asyncio.Lock()
    return lk


async def _grant(uid: int, zen: int) -> bool:
    async with player_lock(uid):
        p = await aget_player(uid)
        if not p:
            return False
        p["zen"] = p.get("zen", 0) + zen
        await asave_player(uid, p)
    return True


def _invite_row(chat_id: int):
    from aiogram.types import InlineKeyboardButton
    from referral_system import group_ref_link
    return [InlineKeyboardButton(text="🎮 منم می‌خوام بازی کنم", url=group_ref_link(chat_id))]


# ─── امتیازِ گروه ───────────────────────────────────────────────

def add_score_sync(chat_id: int, pts: int, title: str | None = None):
    w = current_week()
    upd = {"$inc": {"score": pts}, "$set": {"chat_id": chat_id, "week": w}}
    if title:
        upd["$set"]["title"] = title
    scores_col().update_one({"_id": f"{w}:{chat_id}"}, upd, upsert=True)


async def add_score(chat_id: int, pts: int, title: str | None = None):
    try:
        await asyncio.to_thread(add_score_sync, chat_id, pts, title)
    except Exception as e:
        _log(f"🔴 group_play add_score error: {e}", "ERROR")


async def on_boss_killed(chat_id: int, contributors: int, title: str | None = None):
    """از group_handlers بعدِ شکستِ باسِ گروهی صدا زده می‌شه."""
    pts = BOSS_KILL_SCORE + BOSS_PER_CONTRIBUTOR * min(contributors, BOSS_CONTRIBUTOR_CAP)
    await add_score(chat_id, pts, title)


def _active_members(chat_id: int, days: int = 7) -> list[int]:
    cutoff = time.time() - days * 86400
    return [d["user_id"] for d in _members_col().find({"chat_id": chat_id, "last_seen": {"$gte": cutoff}})]


def _eligible(chat_id: int) -> bool:
    cutoff = time.time() - 7 * 86400
    return _members_col().count_documents({"chat_id": chat_id, "last_seen": {"$gte": cutoff}}) >= MIN_GROUP_MEMBERS


def weekly_board(week: int | None = None, limit: int = 10) -> list[dict]:
    """گروه‌های واجدِ شرایط، مرتب‌شده بر اساسِ امتیازِ هفته."""
    w = current_week() if week is None else week
    docs = sorted(scores_col().find({"week": w}), key=lambda d: -d.get("score", 0))
    out = []
    for d in docs:
        if d.get("score", 0) <= 0:
            continue
        if _eligible(d["chat_id"]):
            out.append(d)
        if len(out) >= limit:
            break
    return out


def rank_of(chat_id: int, week: int | None = None) -> tuple[int | None, int]:
    """(رتبه یا None، امتیاز) برای یه گروه تو هفته‌ی جاری."""
    w = current_week() if week is None else week
    board = weekly_board(w, limit=1000)
    for i, d in enumerate(board, 1):
        if d["chat_id"] == chat_id:
            return i, d.get("score", 0)
    doc = scores_col().find_one({"_id": f"{w}:{chat_id}"})
    return None, (doc or {}).get("score", 0)


# ─── صندوقِ گنج ─────────────────────────────────────────────────

async def record_activity(bot, chat_id: int, uid: int, title: str | None):
    now = time.time()
    dq = _acts.setdefault(chat_id, deque())
    dq.append((now, uid))
    while dq and now - dq[0][0] > CHEST_WINDOW:
        dq.popleft()
    if len(dq) < CHEST_MIN_MSGS:
        return
    users = {u for _, u in dq}
    if len(users) < CHEST_MIN_USERS or _skip_until.get(chat_id, 0) > now:
        return
    await maybe_drop(bot, chat_id, title, users)


async def maybe_drop(bot, chat_id: int, title: str | None, users: set[int], force: bool = False) -> bool:
    async with _lock(chat_id):
        now, today = time.time(), today_num()
        st = await state_col().afind_one({"_id": chat_id}) or {"_id": chat_id, "last_drop": 0, "day": -1, "drops": 0}
        if not force:
            if now - st["last_drop"] < CHEST_COOLDOWN:
                _skip_until[chat_id] = st["last_drop"] + CHEST_COOLDOWN
                return False
            if st["day"] == today and st["drops"] >= CHEST_DAILY_CAP:
                _skip_until[chat_id] = (today + 1) * 86400
                return False
            reg = 0
            for u in list(users)[:12]:
                p = await aget_player(u)
                if p and p.get("class"):
                    reg += 1
            if reg < CHEST_MIN_PLAYERS:
                _skip_until[chat_id] = now + 120  # چند دقیقه‌ی دیگه دوباره چک کن
                return False

        st["drops"] = st["drops"] + 1 if st["day"] == today else 1
        st["day"], st["last_drop"] = today, now
        if title:
            st["title"] = title
        await state_col().areplace_one({"_id": chat_id}, st, upsert=True)
        _skip_until[chat_id] = now + CHEST_COOLDOWN
        _acts.pop(chat_id, None)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    drop_id = secrets.token_hex(3)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 باز کن!", callback_data=f"gchest:{chat_id}:{drop_id}")],
        _invite_row(chat_id),
    ])
    try:
        sent = await bot.send_message(
            chat_id,
            f"📦 **صندوقِ گنجِ Abyss ظاهر شد!**\n"
            f"گروهتون داغه 🔥 — اولین **{CHEST_SLOTS} نفری** که بازش کنن جایزه می‌گیرن!\n"
            f"⏱ {CHEST_TTL // 60} دقیقه وقت دارید.",
            reply_markup=kb,
        )
    except Exception as e:
        _log(f"🟡 group_play: نتونستم صندوق بفرستم ({chat_id}): {e}", "GROUP")
        return False

    key = f"{chat_id}:{drop_id}"
    _chests[key] = {"chat_id": chat_id, "msg_id": sent.message_id, "claimed": [], "lines": [],
                    "closed": False, "lock": asyncio.Lock(), "title": title}
    _spawn(_expire(bot, key))
    _log(f"📦 **CHEST DROP**\n📍 چت: `{chat_id}`")
    return True


async def _finalize(bot, key: str):
    ch = _chests.get(key)
    if not ch or ch["closed"]:
        return
    ch["closed"] = True
    from aiogram.types import InlineKeyboardMarkup
    body = "\n".join(ch["lines"]) if ch["lines"] else "کسی باز نکرد… 😴"
    try:
        await bot.edit_message_text(
            f"📦 **صندوق بسته شد!**\n{body}",
            chat_id=ch["chat_id"], message_id=ch["msg_id"],
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[_invite_row(ch["chat_id"])]),
        )
    except Exception:
        pass
    _spawn(_forget(key))


async def _forget(key: str):
    await asyncio.sleep(60)  # کمی نگهش دار تا دکمه‌ی دیرکرده «تموم شده» بگیره نه خطا
    _chests.pop(key, None)


async def _expire(bot, key: str):
    await asyncio.sleep(CHEST_TTL)
    await _finalize(bot, key)


async def claim_chest(bot, chat_id: int, drop_id: str, uid: int) -> tuple[bool, str]:
    """(موفق؟، پیامِ toast) — منطقِ کاملِ برداشتنِ صندوق."""
    key = f"{chat_id}:{drop_id}"
    ch = _chests.get(key)
    if not ch or ch["closed"]:
        return False, "⌛ این صندوق تموم شده."
    if uid in ch["claimed"]:
        return False, "✅ تو قبلاً این صندوق رو برداشتی."
    player = await aget_player(uid)
    if not player or not player.get("class"):
        return False, "❗️ اول تو خصوصیِ ربات /start بزن و کاراکترت رو بساز!"
    day, cnt = _claims_day.get(uid, (-1, 0))
    today = today_num()
    if day == today and cnt >= CHEST_CLAIMS_PER_USER_DAILY:
        return False, f"⏳ امروز حداکثر {CHEST_CLAIMS_PER_USER_DAILY} صندوق می‌تونی برداری."

    async with ch["lock"]:
        if ch["closed"] or len(ch["claimed"]) >= CHEST_SLOTS:
            return False, "⚡ دیر رسیدی — جایزه‌ها تموم شد!"
        rank = len(ch["claimed"])
        ch["claimed"].append(uid)
        zen = CHEST_BASE[rank] + min(player.get("level", 1), CHEST_LEVEL_CAP) * CHEST_LEVEL_BONUS
        ch["lines"].append(f"{['🥇', '🥈', '🥉'][rank]} {player.get('name', '—')} → 💰 {zen:,} Zen")
        full = len(ch["claimed"]) >= CHEST_SLOTS
    _claims_day[uid] = (today, cnt + 1 if day == today else 1)

    await _grant(uid, zen)
    _ledger(uid, zen, f"chest {key} rank={rank + 1}")
    await add_score(chat_id, SCORE_PER_CLAIM, ch.get("title"))

    if full:
        await _finalize(bot, key)
    else:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            await bot.edit_message_text(
                "📦 **صندوقِ گنج در حالِ باز شدنه!**\n" + "\n".join(ch["lines"]) +
                f"\n\nهنوز {CHEST_SLOTS - len(ch['claimed'])} جایزه مونده — زود باش!",
                chat_id=chat_id, message_id=ch["msg_id"],
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 باز کن!", callback_data=f"gchest:{chat_id}:{drop_id}")],
                    _invite_row(chat_id),
                ]),
            )
        except Exception:
            pass
    return True, f"🎁 رتبه‌ی {rank + 1}! +{zen:,} Zen"


# ─── جایزه‌ی هفتگیِ گروه‌ها ─────────────────────────────────────

async def run_weekly_payout(bot, week: int) -> int:
    """۳ گروهِ برترِ هفته‌ی `week` رو جایزه می‌ده (به اعضای فعالِ ۷ روزِ اخیر)."""
    board = await asyncio.to_thread(weekly_board, week, 10)
    board = [d for d in board if d.get("score", 0) >= MIN_SCORE_FOR_PRIZE][:len(WEEK_PRIZES)]
    paid_total = 0
    for i, d in enumerate(board):
        chat_id, prize = d["chat_id"], WEEK_PRIZES[i]
        members = await asyncio.to_thread(_active_members, chat_id)
        paid = 0
        for uid in members[:MAX_PAID_PER_GROUP]:
            p = await aget_player(uid)
            if not p or not p.get("class"):
                continue
            if await _grant(uid, prize):
                _ledger(uid, prize, f"group week {week} rank={i + 1}")
                paid += 1
        paid_total += paid
        try:
            await bot.send_message(
                chat_id,
                f"🏆 **گروهِ شما هفته‌ی گذشته رتبه‌ی {i + 1} بین گروه‌های Astral Abyss شد!**\n"
                f"⭐ امتیاز: {d.get('score', 0)}\n"
                f"💰 {prize:,} Zen به هر یک از {paid} عضوِ فعال داده شد.\n\n"
                f"دوستانتون رو بیارید تا هفته‌ی بعد اول بشید! 👇",
                reply_markup=_invite_markup(chat_id),
            )
        except Exception:
            pass
        _log(f"🏆 **GROUP WEEK PAYOUT**\n📍 چت: `{chat_id}` | رتبه {i + 1} | {paid} نفر × {prize:,} Zen")
        await asyncio.sleep(0.2)
    return paid_total


def _invite_markup(chat_id: int):
    from aiogram.types import InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[_invite_row(chat_id)])


async def group_play_loop(bot):
    await asyncio.sleep(60)
    while True:
        try:
            week = current_week()
            doc = await system_col().afind_one({"_id": "group_play_paid_week"})
            if doc is None:
                # اولین اجرا: فقط علامت بذار، جایزه‌ی هفته‌ی قبل (که رقابتش وجود نداشت) نده
                await system_col().aupdate_one({"_id": "group_play_paid_week"}, {"$set": {"week": week}}, upsert=True)
            elif doc.get("week", week) < week:
                await system_col().aupdate_one({"_id": "group_play_paid_week"}, {"$set": {"week": week}}, upsert=True)
                await run_weekly_payout(bot, week - 1)
        except Exception as e:
            _log(f"🔴 group_play_loop error: {e}", "ERROR")
        await asyncio.sleep(LOOP_INTERVAL)


# ─── متنِ /groups ───────────────────────────────────────────────

async def build_board_text(chat_id: int | None) -> str:
    w = current_week()
    board = await asyncio.to_thread(weekly_board, w, 10)
    lines = ["🏆 **برترین گروه‌های این هفته**", ""]
    if not board:
        lines.append("هنوز گروهی امتیاز نگرفته — با گپ‌زدن و باز کردنِ صندوق‌ها اول شید! 📦")
    medals = ["🥇", "🥈", "🥉"]
    for i, d in enumerate(board):
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} {d.get('title') or 'گروهِ بی‌نام'} — ⭐ {d.get('score', 0)}")
    if chat_id is not None:
        rank, score = await asyncio.to_thread(rank_of, chat_id, w)
        mine = f"رتبه‌ی {rank}" if rank else "هنوز تو جدول نیست (حداقل ۳ عضوِ فعال + امتیاز لازمه)"
        lines += ["", f"📍 گروهِ شما: {mine} — ⭐ {score}"]
    days_left = 7 - ((today_num() + 3) % 7)
    lines += [
        "",
        f"🎁 جایزه‌ی هفتگی (تا {days_left} روز دیگه): رتبه‌ی ۱ → {WEEK_PRIZES[0]:,} Zen | ۲ → {WEEK_PRIZES[1]:,} | ۳ → {WEEK_PRIZES[2]:,} برای هر عضوِ فعال",
        f"⭐ امتیاز: هر صندوق +{SCORE_PER_CLAIM} | شکستِ باسِ گروهی (/graid) +{BOSS_KILL_SCORE} و +{BOSS_PER_CONTRIBUTOR} به‌ازای هر شرکت‌کننده",
    ]
    return "\n".join(lines)
