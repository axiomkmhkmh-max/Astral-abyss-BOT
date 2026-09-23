# ============================================================
#  ASTRAL ABYSS — SOCIAL RETENTION (نگه‌داشتنِ بازیکن با دوستان)
#  (social_retention.py)
# ------------------------------------------------------------
#  استریکِ ورودِ روزانه (bot.py → grant_daily_login) بازیکن رو «تنها»
#  نگه می‌داره. این ماژول دلیلِ اجتماعی اضافه می‌کنه:
#
#   ۱) 🔥 استریکِ دوتایی: هر جفت‌دوست که هر دو تو یه روزِ (UTC) سر بزنن
#      استریکِ مشترکشون +۱ می‌شه. پله‌ها (۳/۷/۱۴/۳۰/۶۰/۱۰۰ روز) به هر دو
#      Zen می‌دن — هر پله برای هر جفت فقط یه‌بار در کل.
#   ۲) ⏰ یادآوریِ «استریک داره می‌پره» — روزی یه‌بار، عصر، فقط به کسی که
#      امروز هنوز نیومده.
#   ۳) 👋 «بیدارش کن»: به دوستِ غایب پوک بفرست؛ اگه تا ۲۴ ساعت برگرده،
#      تو یه پاداشِ کوچیک می‌گیری.
#   ۴) 🎁 بازگشت: کسی که ≥ COMEBACK_DAYS روز نبوده، موقعِ برگشت بونوس
#      می‌گیره (پیش‌ازش هم یه‌بار پیامِ «دلمون برات تنگ شده» می‌ره).
#
#  ردیابیِ فعالیت با یه outer-middleware انجام می‌شه که هر بازیکن رو
#  روزی حداکثر یه‌بار پردازش می‌کنه (بقیه‌ش فقط یه چکِ حافظه‌ایه) —
#  هیچ فیلدی روی player اضافه نمی‌شه و هیچ هندلرِ موجودی عوض نمی‌شه.
#  کالکشن‌ها: `retention_state` (به‌ازای uid) و `friend_streaks`.
#  روزها همون قراردادِ grant_daily_login: int(time.time() // 86400).
# ============================================================
import asyncio
import time
from datetime import datetime, timezone

from database import get_db, aget_player, asave_player, player_lock, system_col

# ─── تنظیمات ────────────────────────────────────────────────────
PAIR_MILESTONES = {3: 500, 7: 1_500, 14: 4_000, 30: 10_000, 60: 25_000, 100: 50_000}

COMEBACK_DAYS = 3            # غیبتِ حداقلی برای بونوسِ بازگشت
COMEBACK_PER_DAY = 200       # Zen به‌ازای هر روزِ غیبت
COMEBACK_MAX_DAYS = 10       # سقفِ روزهای حساب‌شده (=> حداکثر ۲٬۰۰۰ Zen)
COMEBACK_COOLDOWN_DAYS = 7   # بونوسِ بازگشت حداکثر هفته‌ای یه‌بار
WINBACK_MAX_LAPSE = 30       # به کسی که بیشتر از این غایبه، دیگه پیام نمی‌دیم

POKE_REWARD = 200
POKE_WINDOW = 24 * 3600
POKES_SENT_DAILY_CAP = 10
POKE_PAID_DAILY_CAP = 5

NUDGE_HOUR_UTC = 15          # ≈ ۱۸:۳۰ تهران
LOOP_INTERVAL = 3600
MAX_DM_PER_RUN = 400

_seen_today: dict[int, int] = {}     # uid → روزی که پردازش شده (کش حافظه‌ای)
_touch_lock = asyncio.Lock()
_state_lock = asyncio.Lock()


# ─── دیتا ───────────────────────────────────────────────────────

def state_col():
    return get_db()["retention_state"]


def pairs_col():
    return get_db()["friend_streaks"]


def today_num() -> int:
    return int(time.time() // 86400)


def pair_key(a: int, b: int) -> str:
    lo, hi = sorted((int(a), int(b)))
    return f"{lo}:{hi}"


def _log(text: str, tag: str = "GROUP"):
    try:
        from logger import log_sync
        log_sync(text, tag)
    except Exception:
        pass


def _ledger(uid: int, zen: int, note: str):
    try:
        from economy_ledger import record_transaction
        record_transaction("retention_reward", uid, amount=zen, note=note)
    except Exception:
        pass


async def _grant(uid: int, zen: int) -> bool:
    async with player_lock(uid):
        p = await aget_player(uid)
        if not p:
            return False
        p["zen"] = p.get("zen", 0) + zen
        await asave_player(uid, p)
    return True


async def _dm(bot, uid: int, text: str, reply_markup=None) -> bool:
    try:
        await bot.send_message(uid, text, reply_markup=reply_markup)
        return True
    except Exception:
        return False  # بلاک کرده یا PV نبسته


async def _name(uid: int) -> str:
    p = await aget_player(uid)
    return (p or {}).get("name") or "یکی از دوستات"


# ─── ۱) استریکِ دوتایی ──────────────────────────────────────────

async def advance_pair(bot, a: int, b: int) -> int | None:
    """اگه امروز برای این جفت حساب نشده باشه، استریک رو یکی زیاد می‌کنه.
    idempotent (last_day). مقدارِ جدیدِ استریک رو برمی‌گردونه یا None."""
    today = today_num()
    key = pair_key(a, b)
    milestone_reached = None
    async with _state_lock:
        doc = await pairs_col().afind_one({"_id": key})
        if doc is None:
            lo, hi = sorted((int(a), int(b)))
            doc = {"_id": key, "a": lo, "b": hi, "streak": 0, "best": 0,
                   "last_day": -1, "nudged_day": -1, "paid": []}
        if doc["last_day"] == today:
            return None
        doc["streak"] = doc["streak"] + 1 if doc["last_day"] == today - 1 else 1
        doc["best"] = max(doc.get("best", 0), doc["streak"])
        doc["last_day"] = today
        if doc["streak"] in PAIR_MILESTONES and doc["streak"] not in doc.get("paid", []):
            doc["paid"] = list(doc.get("paid", [])) + [doc["streak"]]
            milestone_reached = doc["streak"]
        await pairs_col().areplace_one({"_id": key}, doc, upsert=True)

    if milestone_reached:
        zen = PAIR_MILESTONES[milestone_reached]
        for me, other in ((a, b), (b, a)):
            if await _grant(me, zen):
                _ledger(me, zen, f"pair_streak {milestone_reached} with {other}")
                await _dm(bot, me,
                          f"🔥 **استریکِ {milestone_reached} روزه با {await _name(other)}!**\n"
                          f"💰 +{zen:,} Zen برای هر دوتاتون. ادامه بدید! /streaks")
    return doc["streak"]


# ─── ردیابیِ فعالیت (اولین اکشنِ هر روز) ────────────────────────

async def touch(bot, uid: int):
    today = today_num()
    if _seen_today.get(uid) == today:
        return
    async with _touch_lock:
        if _seen_today.get(uid) == today:
            return
        _seen_today[uid] = today

    player = await aget_player(uid)
    if not player or not player.get("class"):
        _seen_today.pop(uid, None)  # هنوز ثبت‌نام کامل نشده؛ بعداً دوباره
        return

    st = await state_col().afind_one({"_id": uid}) or {"_id": uid}
    prev_day = st.get("last_day", -1)
    if prev_day == today:
        return
    st["last_day"] = today

    # ── بازگشت بعد از غیبت
    gap = today - prev_day if prev_day >= 0 else 0
    if (gap >= COMEBACK_DAYS
            and today - st.get("comeback_day", -999) >= COMEBACK_COOLDOWN_DAYS):
        zen = min(gap, COMEBACK_MAX_DAYS) * COMEBACK_PER_DAY
        st["comeback_day"] = today
        if await _grant(uid, zen):
            _ledger(uid, zen, f"comeback gap={gap}d")
            await _dm(bot, uid, f"🎁 **خوش برگشتی!** {gap} روز نبودی.\n💰 بونوسِ بازگشت: +{zen:,} Zen")

    # ── پوک‌هایی که دوستان برام فرستادن → پاداش به پوک‌کننده
    pokes = st.pop("pokes", {}) or {}
    now = time.time()
    for poker_s, info in pokes.items():
        if now - info.get("ts", 0) <= POKE_WINDOW:
            await _pay_poker(bot, int(poker_s), uid)

    await state_col().areplace_one({"_id": uid}, st, upsert=True)

    # ── استریکِ دوتایی با دوستانی که امروز فعال بودن
    friends = [f for f in (player.get("friends") or []) if isinstance(f, int)]
    if friends:
        docs = await state_col().afind({"_id": {"$in": friends}, "last_day": today})
        for d in docs:
            await advance_pair(bot, uid, d["_id"])


async def _pay_poker(bot, poker: int, returned: int):
    today = today_num()
    async with _state_lock:
        ps = await state_col().afind_one({"_id": poker}) or {"_id": poker}
        if ps.get("paid_day") != today:
            ps["paid_day"], ps["paid_count"] = today, 0
        if ps["paid_count"] >= POKE_PAID_DAILY_CAP:
            return
        ps["paid_count"] += 1
        await state_col().areplace_one({"_id": poker}, ps, upsert=True)
    if await _grant(poker, POKE_REWARD):
        _ledger(poker, POKE_REWARD, f"poke returned {returned}")
        await _dm(bot, poker, f"🎉 **{await _name(returned)}** به‌خاطرِ پوکِ تو برگشت!\n💰 +{POKE_REWARD} Zen")


# ─── ۳) پوک ─────────────────────────────────────────────────────

async def poke(bot, uid: int, target: int) -> str:
    """پیامِ نتیجه (برای toast) رو برمی‌گردونه."""
    today = today_num()
    me = await aget_player(uid)
    if not me or target not in (me.get("friends") or []):
        return "❌ این بازیکن تو لیستِ دوستات نیست."
    async with _state_lock:
        ps = await state_col().afind_one({"_id": uid}) or {"_id": uid}
        ts_ = await state_col().afind_one({"_id": target}) or {"_id": target}
        if ts_.get("last_day") == today:
            return "✅ اون امروز خودش فعال بوده!"
        if ps.get("poke_day") != today:
            ps["poke_day"], ps["poke_count"] = today, 0
        if ps["poke_count"] >= POKES_SENT_DAILY_CAP:
            return f"⏳ امروز حداکثر {POKES_SENT_DAILY_CAP} پوک می‌تونی بفرستی."
        pokes = ts_.setdefault("pokes", {})
        last = pokes.get(str(uid))
        if last and last.get("day") == today:
            return "👋 امروز قبلاً بیدارش کردی."
        pokes[str(uid)] = {"ts": time.time(), "day": today}
        ps["poke_count"] += 1
        await state_col().areplace_one({"_id": uid}, ps, upsert=True)
        await state_col().areplace_one({"_id": target}, ts_, upsert=True)
    ok = await _dm(bot, target,
                   f"👋 **{me.get('name', 'یکی از دوستات')}** داره منتظرته! یه سر به Astral Abyss بزن.\n"
                   f"/start   |   /streaks")
    return "👋 پوک فرستاده شد!" if ok else "👋 ثبت شد ولی نتونستم بهش پیام بدم."


# ─── ۲ و ۴) حلقه‌ی روزانه: یادآوری + دلتنگی ─────────────────────

async def run_daily(bot) -> dict:
    today = today_num()
    sent = 0

    # الف) استریکِ در خطر: دیروز فعال بودن، امروز هنوز کامل نشده
    at_risk = await pairs_col().afind({"last_day": today - 1, "streak": {"$gte": 2}})
    for doc in at_risk:
        if doc.get("nudged_day") == today or sent >= MAX_DM_PER_RUN:
            continue
        await pairs_col().aupdate_one({"_id": doc["_id"]}, {"$set": {"nudged_day": today}})
        for me, other in ((doc["a"], doc["b"]), (doc["b"], doc["a"])):
            st = await state_col().afind_one({"_id": me}) or {}
            if st.get("last_day") == today:
                continue  # این یکی امروز اومده
            other_st = await state_col().afind_one({"_id": other}) or {}
            waiting = " و اون امروز اومده و منتظرته" if other_st.get("last_day") == today else ""
            if await _dm(bot, me,
                         f"⏰ استریکِ **{doc['streak']} روزه**‌ت با **{await _name(other)}** امروز در خطره{waiting}!\n"
                         f"یه سر به ربات بزن تا نپره. /streaks"):
                sent += 1
            await asyncio.sleep(0.05)

    # ب) دلتنگی: ۳ تا ۳۰ روز غایب، یه‌بار برای هر غیبت
    lapsed = await state_col().afind({
        "last_day": {"$lte": today - COMEBACK_DAYS, "$gte": today - WINBACK_MAX_LAPSE},
    })
    for st in lapsed:
        if sent >= MAX_DM_PER_RUN:
            break
        if st.get("winback_for") == st["last_day"]:
            continue
        gap = today - st["last_day"]
        bonus = min(gap, COMEBACK_MAX_DAYS) * COMEBACK_PER_DAY
        await state_col().aupdate_one({"_id": st["_id"]}, {"$set": {"winback_for": st["last_day"]}})
        if await _dm(bot, st["_id"],
                     f"🌑 {gap} روزه از Abyss دور موندی... دوستات منتظرتن!\n"
                     f"برگرد و **{bonus:,} Zen** بونوسِ بازگشت بگیر. /start"):
            sent += 1
        await asyncio.sleep(0.05)

    _log(f"⏰ **RETENTION DAILY**\nپیام‌های ارسالی: {sent}")
    return {"sent": sent}


async def retention_loop(bot):
    await asyncio.sleep(45)
    while True:
        try:
            now = datetime.now(timezone.utc)
            today = today_num()
            if now.hour >= NUDGE_HOUR_UTC:
                doc = await system_col().afind_one({"_id": "retention_nudge_day"})
                if not doc or doc.get("day") != today:
                    await system_col().aupdate_one({"_id": "retention_nudge_day"}, {"$set": {"day": today}}, upsert=True)
                    await run_daily(bot)
        except Exception as e:
            _log(f"🔴 retention_loop error: {e}", "ERROR")
        await asyncio.sleep(LOOP_INTERVAL)


# ─── نمایش برای /streaks ────────────────────────────────────────

async def build_overview(uid: int) -> tuple[str, list[int]]:
    """(متن، لیستِ دوستانِ غایبِ امروز برای دکمه‌ی پوک)"""
    today = today_num()
    me = await aget_player(uid) or {}
    friends = [f for f in (me.get("friends") or []) if isinstance(f, int)]
    lines = [f"🔥 **استریکِ ورودِ تو:** {me.get('login_streak', 0)} روز", ""]
    if not friends:
        lines.append("👥 هنوز دوستی نداری. با /addfriend یکی رو اضافه کن تا استریکِ دوتایی بسازید!")
        return "\n".join(lines), []

    keys = [pair_key(uid, f) for f in friends]
    pairs = {d["_id"]: d for d in await pairs_col().afind({"_id": {"$in": keys}})}
    states = {d["_id"]: d for d in await state_col().afind({"_id": {"$in": friends}})}

    rows = []
    for f in friends:
        pd = pairs.get(pair_key(uid, f)) or {}
        streak = pd.get("streak", 0) if pd.get("last_day", -1) >= today - 1 else 0  # شکسته؟ صفر
        last = (states.get(f) or {}).get("last_day", -1)
        rows.append((streak, f, last))
    rows.sort(key=lambda r: (-r[0], -r[2]))

    lines.append("👥 **استریکِ دوتایی با دوستان:**")
    inactive = []
    for streak, f, last in rows[:12]:
        if last == today:
            status = "✅ امروز فعال"
        elif last >= 0:
            status = f"💤 {today - last} روز غایب"
            inactive.append(f)
        else:
            status = "— هنوز ردیابی نشده"
            inactive.append(f)
        lines.append(f"{'🔥' if streak else '▫️'} {streak} روز — **{await _name(f)}** ({status})")
    nxt = [m for m in sorted(PAIR_MILESTONES) if m > max((r[0] for r in rows), default=0)]
    if nxt:
        lines.append(f"\n🎯 پله‌ی بعدی: {nxt[0]} روز → 💰 {PAIR_MILESTONES[nxt[0]]:,} Zen برای هر دو")
    lines.append("\n💡 هر روز که هر دو سر بزنید استریک +۱ می‌شه. دوستِ غایب رو بیدار کن 👇")
    return "\n".join(lines), inactive[:6]
