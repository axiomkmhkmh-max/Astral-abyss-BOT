# ============================================================
#  ASTRAL ABYSS — VIRAL LOOP (حلقه‌ی رشدِ ویروسی)
#  (viral_loop.py)
# ------------------------------------------------------------
#  referral_system.py فقط «ردیابی» می‌کرد (کی از کجا اومد) و bot.py
#  یه پاداشِ ثابتِ ۳۰۰ Zen به‌محضِ /start می‌داد — که هم انگیزه‌ی
#  کافی برای شیرکردن نبود، هم با اکانتِ فیک قابلِ سوءاستفاده بود.
#  این ماژول حلقه‌ی کامل رو می‌بنده:
#
#   ۱) هر بازیکن یه لینکِ دعوتِ شخصی داره:  ?start=ref_user_<uid>
#      (کارت/دوئلِ اینلاین هم همون مسیرِ قبلی رو می‌رن و همین‌جا حساب می‌شن)
#   ۲) «فعال‌سازی»: دعوت‌شده وقتی به لِوِل ACTIVATION_LEVEL برسه،
#        • خودش یه بونوسِ خوش‌آمد می‌گیره
#        • دعوت‌کننده پاداشِ اصلی رو می‌گیره
#        • و به دعوت‌شده لینکِ دعوتِ خودش داده می‌شه → حلقه بسته می‌شه 🔁
#   ۳) پله‌های تجمعی (۳ / ۵ / ۱۰ / ۲۵ / ۵۰ دعوتِ فعال)
#   ۴) ضدِ سوءاستفاده: پاداشِ اصلی فقط با «فعال‌شدنِ واقعی» (بازیِ واقعی
#      تا لِوِل N) پرداخت می‌شه + سقفِ روزانه برای هر دعوت‌کننده + هر
#      دعوت‌شده فقط یه‌بار (idempotent — با ری‌استارت دوباره پرداخت نمی‌شه).
#
#  هیچ فیلدِ جدیدی روی player نمی‌ذاره: وضعیتِ دعوت‌کننده تو کالکشنِ
#  `viral_state` و وضعیتِ هر دعوت روی همون سندِ `referrals` ذخیره می‌شه.
#  فقط Zen/XP پرداخت می‌شه (همون چیزی که پاداشِ رفرالِ قبلی هم می‌داد)،
#  پس به هیچ سیستمِ آیتم/اینونتوری‌ای وابسته نیست.
# ============================================================
import asyncio
import time
from datetime import datetime, timezone

from database import get_db, aget_player, asave_player, player_lock, system_col
from referral_system import referrals_col, user_ref_link, BOT_LINK

# ─── تنظیمات (بالانس‌ها اینجا عوض می‌شن) ────────────────────────
ACTIVATION_LEVEL = 5            # دعوت‌شده باید به این لِوِل برسه تا «فعال» حساب بشه
ACTIVATION_WINDOW_DAYS = 14     # بعد از این‌همه روز، دعوتِ فعال‌نشده منقضی می‌شه
DAILY_ACTIVATION_CAP = 10       # حداکثر پاداشِ اصلیِ قابلِ دریافت برای هر دعوت‌کننده در روز
LOOP_INTERVAL = 300             # ثانیه — هر چند وقت یه‌بار دعوت‌های در انتظار چک بشن
MAX_PER_CYCLE = 200

INVITEE_WELCOME_ZEN = 500
INVITEE_WELCOME_XP = 50
INVITER_ACTIVATION_ZEN = 1000
INVITER_ACTIVATION_XP = 60

# پله‌های تجمعی — کلیدش «تعدادِ دعوتِ فعال»ه
MILESTONES = [
    {"count": 3,  "zen": 2_000,  "xp": 150,   "label": "ماجراجوی اجتماعی"},
    {"count": 5,  "zen": 4_000,  "xp": 300,   "label": "فرمانده‌ی دسته"},
    {"count": 10, "zen": 10_000, "xp": 800,   "label": "سفیرِ آبیس"},
    {"count": 25, "zen": 30_000, "xp": 2_000, "label": "اسطوره‌ی جذب"},
    {"count": 50, "zen": 80_000, "xp": 5_000, "label": "پادشاهِ دعوت"},
]

# فقط این نوع‌ها یه «دعوت‌کننده‌ی شخصی» دارن (group منبعش یه چته، نه آدم)
PERSONAL_KINDS = ["card", "duel", "user"]

_state_lock = asyncio.Lock()   # ربات تک‌پروسه‌ست؛ برای read-modify-write روی viral_state


# ─── دسترسی به دیتا ─────────────────────────────────────────────

def viral_state_col():
    return get_db()["viral_state"]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _blank_state(uid: int) -> dict:
    return {"_id": uid, "activated": 0, "tiers_paid": [], "day": "", "day_count": 0, "total_zen": 0}


def _log(text: str, tag: str = "GROUP"):
    try:
        from logger import log_sync
        log_sync(text, tag)
    except Exception:
        pass


def _ledger(uid: int, zen: int, note: str):
    try:
        from economy_ledger import record_transaction
        record_transaction("referral_reward", uid, amount=zen, note=note)
    except Exception:
        pass


# ─── آمار برای /invite ──────────────────────────────────────────

def get_stats(uid: int) -> dict:
    """joined = همه‌ی دعوت‌ها | activated = فعال‌شده‌ها | pending = هنوز منقضی‌نشده و فعال‌نشده"""
    docs = referrals_col().find({"source": uid, "kind": {"$in": PERSONAL_KINDS}})
    now = time.time()
    window = ACTIVATION_WINDOW_DAYS * 86400
    activated = sum(1 for d in docs if d.get("activated"))
    pending = sum(1 for d in docs if not d.get("activated") and now - d.get("ts", 0) <= window)
    st = viral_state_col().find_one({"_id": uid}) or _blank_state(uid)
    return {
        "joined": len(docs),
        "activated": max(activated, st.get("activated", 0)),
        "pending": pending,
        "tiers_paid": list(st.get("tiers_paid", [])),
        "total_zen": st.get("total_zen", 0),
        "today_used": st.get("day_count", 0) if st.get("day") == _today() else 0,
    }


def next_milestone(activated: int) -> dict | None:
    for m in MILESTONES:
        if activated < m["count"]:
            return m
    return None


def top_inviters(limit: int = 10) -> list[dict]:
    pipeline = [
        {"$match": {"kind": {"$in": PERSONAL_KINDS}, "activated": True}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return referrals_col().aggregate(pipeline)


# ─── پرداخت ─────────────────────────────────────────────────────

async def _grant(uid: int, zen: int, xp: int) -> bool:
    async with player_lock(uid):
        p = await aget_player(uid)
        if not p:
            return False
        p["zen"] = p.get("zen", 0) + zen
        p["xp"] = p.get("xp", 0) + xp
        await asave_player(uid, p)
    return True


async def _safe_send(bot, uid: int, text: str, reply_markup=None):
    try:
        await bot.send_message(uid, text, reply_markup=reply_markup)
    except Exception:
        pass  # کاربر ربات رو بلاک کرده یا PV نبسته


def share_kb(uid: int):
    """کیبوردِ «بفرست برای دوستات» — لینکِ share تلگرام، بدونِ نیاز به inline mode."""
    from urllib.parse import quote
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    link = user_ref_link(uid)
    text = "🌑 بیا تو Astral Abyss — RPGِ حماسیِ تلگرام! با این لینک شروع کن و بونوسِ خوش‌آمد بگیر 🎁"
    url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(text)}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 بفرست برای دوستات", url=url)],
    ])


# ─── هسته: فعال‌سازیِ یه دعوت ───────────────────────────────────

async def _payout_inviter(bot, doc: dict) -> bool:
    """پاداشِ اصلیِ دعوت‌کننده (+ پله‌های تجمعی). idempotent و با سقفِ روزانه.
    اگه سقف پر باشه، دعوت «در انتظار» می‌مونه و حلقه فردا دوباره امتحانش می‌کنه."""
    invitee, inviter = doc["_id"], doc["source"]

    inviter_player = await aget_player(inviter)
    if not inviter_player:
        # دعوت‌کننده دیگه وجود نداره — هیچ‌وقت پرداخت نشه، ولی هر دور هم چک نشه
        await referrals_col().aupdate_one({"_id": invitee}, {"$set": {"inviter_paid": True, "inviter_skipped": True}})
        return False

    async with _state_lock:
        st = await viral_state_col().afind_one({"_id": inviter}) or _blank_state(inviter)
        today = _today()
        if st.get("day") != today:
            st["day"], st["day_count"] = today, 0
        if st["day_count"] >= DAILY_ACTIVATION_CAP:
            return False  # در انتظارِ فردا

        claim = await referrals_col().aupdate_one(
            {"_id": invitee, "inviter_paid": {"$ne": True}}, {"$set": {"inviter_paid": True}}
        )
        if claim.modified_count != 1:
            return False  # جای دیگه‌ای قبلاً پرداخت شده

        st["day_count"] += 1
        st["activated"] = st.get("activated", 0) + 1
        new_tiers = [m for m in MILESTONES
                     if st["activated"] >= m["count"] and m["count"] not in st["tiers_paid"]]
        st["tiers_paid"] = list(st["tiers_paid"]) + [m["count"] for m in new_tiers]

        zen = INVITER_ACTIVATION_ZEN + sum(m["zen"] for m in new_tiers)
        xp = INVITER_ACTIVATION_XP + sum(m["xp"] for m in new_tiers)
        st["total_zen"] = st.get("total_zen", 0) + zen
        await viral_state_col().areplace_one({"_id": inviter}, st, upsert=True)

    await _grant(inviter, zen, xp)
    _ledger(inviter, zen, f"viral_loop activation invitee={invitee}")

    invitee_player = await aget_player(invitee)
    friend = (invitee_player or {}).get("name") or "یکی از دوستات"
    lines = [
        f"🔥 **{friend}** (که تو دعوتش کردی) به لِوِل {ACTIVATION_LEVEL} رسید!",
        f"💰 +{INVITER_ACTIVATION_ZEN:,} Zen | ✨ +{INVITER_ACTIVATION_XP} XP",
    ]
    for m in new_tiers:
        lines.append(f"\n🏆 **پله‌ی «{m['label']}» باز شد!** ({m['count']} دعوتِ فعال)\n"
                     f"💰 +{m['zen']:,} Zen | ✨ +{m['xp']:,} XP")
    nxt = next_milestone(st["activated"])
    if nxt:
        lines.append(f"\n🎯 تا پله‌ی بعدی: {st['activated']}/{nxt['count']} — /invite")
    await _safe_send(bot, inviter, "\n".join(lines), reply_markup=share_kb(inviter))
    _log(f"🔁 **VIRAL ACTIVATION**\n👤 دعوت‌کننده: `{inviter}`\n🆕 دعوت‌شده: `{invitee}`\n"
         f"💰 {zen:,} Zen | فعال‌ها: {st['activated']}")
    return True


async def process_referral(bot, doc: dict) -> bool:
    """اگه دعوت‌شده به لِوِلِ فعال‌سازی رسیده باشه، فعالش می‌کنه (فقط یه‌بار).
    True یعنی همین الان فعال شد."""
    invitee = doc["_id"]
    p = await aget_player(invitee)
    if not p or not p.get("class") or p.get("level", 1) < ACTIVATION_LEVEL:
        return False

    claim = await referrals_col().aupdate_one(
        {"_id": invitee, "activated": {"$ne": True}},
        {"$set": {"activated": True, "activated_at": time.time()}},
    )
    if claim.modified_count != 1:
        return False  # قبلاً فعال شده (مثلاً دورِ قبلیِ حلقه)

    # ۱) بونوسِ خوش‌آمدِ خودِ دعوت‌شده + بستنِ حلقه (لینکِ خودش)
    await _grant(invitee, INVITEE_WELCOME_ZEN, INVITEE_WELCOME_XP)
    _ledger(invitee, INVITEE_WELCOME_ZEN, "viral_loop invitee welcome")
    await _safe_send(
        bot, invitee,
        f"🎁 **بونوسِ خوش‌آمد!** به لِوِل {ACTIVATION_LEVEL} رسیدی و این هدیه‌ی دوستت بود:\n"
        f"💰 +{INVITEE_WELCOME_ZEN} Zen | ✨ +{INVITEE_WELCOME_XP} XP\n\n"
        f"🔁 حالا نوبتِ توئه! برای هر دوستی که با لینکِ تو به لِوِل {ACTIVATION_LEVEL} برسه "
        f"**{INVITER_ACTIVATION_ZEN:,} Zen** می‌گیری — و پله‌های بزرگ‌تر تا **{MILESTONES[-1]['zen']:,} Zen**.\n"
        f"لینکت: {user_ref_link(invitee)}\n/invite",
        reply_markup=share_kb(invitee),
    )

    # ۲) پاداشِ دعوت‌کننده (اگه سقفِ روزانه پر باشه، pending می‌مونه)
    doc = await referrals_col().afind_one({"_id": invitee}) or doc
    await _payout_inviter(bot, doc)
    return True


# ─── حلقه‌ی پس‌زمینه ────────────────────────────────────────────

async def _get_since() -> float:
    """زمانِ اولین اجرای این سیستم. دعوت‌های قبل از اون (که با سیستمِ قدیمی پرداخت
    شدن) عطفِ‌به‌ماسبق پرداخت نمی‌شن — تا روزِ دیپلوی یهو پرداختِ گروهی نشه."""
    doc = await system_col().afind_one({"_id": "viral_loop_since"})
    if doc and doc.get("ts"):
        return float(doc["ts"])
    now = time.time()
    await system_col().aupdate_one({"_id": "viral_loop_since"}, {"$set": {"ts": now}}, upsert=True)
    return now


async def run_once(bot) -> int:
    since = await _get_since()
    now = time.time()
    floor = max(since, now - ACTIVATION_WINDOW_DAYS * 86400)
    activated_now = 0

    # الف) دعوت‌های فعال‌نشده → چکِ لِوِلِ دعوت‌شده
    pending = await referrals_col().afind({
        "kind": {"$in": PERSONAL_KINDS}, "activated": {"$ne": True}, "ts": {"$gte": floor},
    })
    for doc in pending[:MAX_PER_CYCLE]:
        try:
            if await process_referral(bot, doc):
                activated_now += 1
        except Exception as e:
            _log(f"🔴 viral_loop process_referral error: {e}", "ERROR")
        await asyncio.sleep(0.05)

    # ب) دعوت‌های فعال‌شده‌ای که پاداشِ دعوت‌کننده‌شون به‌خاطرِ سقفِ روزانه مونده
    stuck = await referrals_col().afind({
        "kind": {"$in": PERSONAL_KINDS}, "activated": True,
        "inviter_paid": {"$ne": True}, "ts": {"$gte": since},
    })
    for doc in stuck[:MAX_PER_CYCLE]:
        try:
            await _payout_inviter(bot, doc)
        except Exception as e:
            _log(f"🔴 viral_loop payout error: {e}", "ERROR")
        await asyncio.sleep(0.05)
    return activated_now


async def viral_loop_loop(bot):
    await asyncio.sleep(30)  # بذار ربات کامل بالا بیاد
    while True:
        try:
            await run_once(bot)
        except Exception as e:
            _log(f"🔴 viral_loop cycle error: {e}", "ERROR")
        await asyncio.sleep(LOOP_INTERVAL)
