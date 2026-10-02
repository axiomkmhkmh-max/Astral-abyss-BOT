# ============================================================
#  ASTRAL ABYSS — 🎭 بازی‌های ریپلای‌محورِ دسته‌ی دوم (Social Games 2)
#  (social_games2.py) — منطق و دیتای خالص، بدون UI تلگرام
# ------------------------------------------------------------
#    🕵️ جیب بزن        (ریپلای) — دزدیِ کوچیکِ ریسکی بینِ بازیکن‌ها
#    💘 شیپ            (ریپلای) — درصدِ سازگاری + اسمِ زوج
#    ⚖️ محاکمه         (ریپلای) — رأی‌گیریِ ۶۰ ثانیه‌ای + لقبِ حکم
#    📊 مقایسه         (ریپلای) — کارتِ رویارویی
#    🏷 قیمتش چنده     (ریپلای) — «ارزشِ بازار» طنز
#    🎁 جعبه [مبلغ]    (ریپلای) — جعبه‌ی مرموزِ دوطرفه‌رضایتی
#    🪦 فاتحه          (ریپلای) — مرثیه‌ی طنز
#
#  اقتصاد: هر جابه‌جاییِ Zen تو این فایل صفرجمعه (از جیبِ یکی به جیبِ
#  یکی دیگه) — هیچ Zen از هیچ ساخته نمی‌شه. هر دو طرفِ جابه‌جایی
#  همیشه تحتِ player_lock (به ترتیبِ uid، ضدِدِدلاک) و با چکِ دوباره
#  موقعِ تسویه.
#  از cooldownها و ابزارهای social_games.py (نسخه‌ی اول) استفاده می‌کنه.
# ============================================================
from __future__ import annotations

import asyncio
import hashlib
import itertools
import random
import time
from typing import Awaitable, Callable, Optional

import social_games as sg
from social_games import clean_name, normalize

# ─── مسیریابیِ دستورها ──────────────────────────────────────
_EXACT = {
    "جیب بزن": "pick", "جیب بری": "pick", "جیبش رو بزن": "pick",
    "شیپ": "ship", "شیپشون کن": "ship", "شیپ کن": "ship",
    "محاکمه": "trial", "محاکمه اش کن": "trial", "محاکمش کن": "trial",
    "مقایسه": "compare", "مقایسه کن": "compare",
    "قیمتش چنده": "price", "قیمتش چند": "price", "قیمتش چنده؟": "price",
    "فاتحه": "fatiha", "فاتحه بخون": "fatiha",
}


def parse_command(text: str) -> Optional[tuple[str, str]]:
    t = normalize(text)
    if not t or len(t) > 30:
        return None
    if t in _EXACT:
        return _EXACT[t], ""
    if t == "جعبه" or t.startswith("جعبه "):
        arg = t[len("جعبه"):].strip()
        # فقط «جعبه» یا «جعبه <عدد>» — تا جمله‌هایی مثلِ «جعبه ابزار» هایجک نشن
        if arg and sg.parse_amount(arg) is None:
            return None
        return "box", arg
    return None


# ─── state روی player doc (کنارِ sg_state نسخه‌ی اول) ───────
def st2(player: dict) -> dict:
    st = player.setdefault("sg2_state", {})
    for k in ("pick_ok", "pick_fail", "stolen_total", "robbed_total", "fatiha_received", "trial_guilty", "trial_innocent"):
        st.setdefault(k, 0)
    return st


def _zen(p: dict) -> int:
    return int(p.get("zen", 0) or 0)


def lock_order(a: int, b: int) -> tuple[int, int]:
    """ترتیبِ ثابتِ قفل‌گرفتن (کوچیک‌تر اول) تا دو درخواستِ متقابل دِدلاک نشن."""
    return (a, b) if a <= b else (b, a)


# ─── 🕵️ جیب بزن ─────────────────────────────────────────────
PICK_MIN_LEVEL = 3
PICK_CD = 600               # ثانیه، به‌ازای دزد
PICK_IMMUNE = 600           # ثانیه، بعد از هر جیب‌بری روی قربانی (ضدِ لِه‌کردن)
PICK_MIN_VICTIM_ZEN = 1_000
PICK_MAX = 5_000
PICK_SUCCESS = 0.45

PICK_OK_LINES = [
    "دستش یه لحظه تو جیبِ {v} لغزید و {a} Zen رو هوا شد 🫳💨",
    "{t} با مهارتِ یه گربه‌ی ولگرد کیسه‌ی {v} رو سبک کرد 🐈‍⬛",
    "تا {v} برگرده، {t} غیبش زده بود… با {a} Zen 🏃",
]
PICK_FAIL_LINES = [
    "{v} دستِ {t} رو تو جیبش گرفت! جریمه‌ی شرمندگی: {a} Zen 😳",
    "نگهبان دیدش! {t} باید {a} Zen غرامت بده 🚨",
    "{t} پاش به بند خورد و کیف خودش افتاد… {a} Zen به {v} رسید 🫠",
]


def check_pick(thief: dict, victim: dict) -> Optional[str]:
    """None یعنی مجازه، وگرنه دلیلِ رد."""
    if int(thief.get("level", 1) or 1) < PICK_MIN_LEVEL:
        return f"برای جیب‌بری حداقل لولِ {PICK_MIN_LEVEL} می‌خوای."
    if int(victim.get("level", 1) or 1) < PICK_MIN_LEVEL:
        return "این یکی تازه‌واردِ زیرِ حمایتِ محفله؛ دست‌بزن نداره 🛡"
    if _zen(victim) < PICK_MIN_VICTIM_ZEN:
        return "جیبش خالی‌تر از اون چیزیه که ارزشِ ریسک داشته باشه 🕳"
    if _zen(thief) < 200:
        return "حداقل ۲۰۰ Zen با خودت داشته باش تا اگه گیر افتادی جریمه بدی."
    return None


def do_pick(thief: dict, victim: dict, t_name: str, v_name: str) -> dict:
    """جابه‌جایی رو انجام می‌ده (باید زیرِ هر دو قفل و بعد از check_pick باشه). ذخیره با caller."""
    amount = max(50, min(PICK_MAX, int(_zen(victim) * random.uniform(0.03, 0.08))))
    if random.random() < PICK_SUCCESS:
        amount = min(amount, _zen(victim))
        thief["zen"] = _zen(thief) + amount
        victim["zen"] = _zen(victim) - amount
        st2(thief)["pick_ok"] += 1
        st2(thief)["stolen_total"] += amount
        st2(victim)["robbed_total"] += amount
        return {"won": True, "amount": amount,
                "line": random.choice(PICK_OK_LINES).format(t=t_name, v=v_name, a=f"{amount:,}")}
    fine = min(amount, _zen(thief))
    thief["zen"] = _zen(thief) - fine
    victim["zen"] = _zen(victim) + fine
    st2(thief)["pick_fail"] += 1
    return {"won": False, "amount": fine,
            "line": random.choice(PICK_FAIL_LINES).format(t=t_name, v=v_name, a=f"{fine:,}")}


# ─── 💘 شیپ ─────────────────────────────────────────────────
# سازگاریِ کلاس‌ها (۰ تا ۱۰۰)
_CLASS_COMPAT = {
    frozenset({"healer", "adventurer"}): 90,
    frozenset({"wizard", "merchant"}): 75,
    frozenset({"healer", "wizard"}): 80,
    frozenset({"adventurer", "merchant"}): 65,
    frozenset({"adventurer", "wizard"}): 55,
    frozenset({"healer", "merchant"}): 60,
    frozenset({"healer"}): 70, frozenset({"wizard"}): 60,
    frozenset({"adventurer"}): 50, frozenset({"merchant"}): 45,
}

SHIP_TIERS = [
    (90, "💞 سرنوشت! عروسی رو همین امشب بگیرین"),
    (75, "💖 عاشقِ هم‌ان، فقط هنوز نمی‌دونن"),
    (60, "💘 جرقه هست؛ یه ماجراجوییِ مشترک کافیه"),
    (40, "🤝 دوستیِ خوب… ولی اونقدرام جدی نیست"),
    (20, "😬 فقط تو یه مهمونیِ شلوغ کنار هم دووم میارن"),
    (0,  "💔 حتی نقشه‌ی ستاره‌ها هم گفتن «نه»"),
]


def ship_name(a: str, b: str) -> str:
    """اسمِ ترکیبیِ زوج: نیمه‌ی اولِ اسمِ اول + نیمه‌ی دومِ اسمِ دوم."""
    a, b = a.strip() or "؟", b.strip() or "؟"
    ha = a[: max(1, (len(a) + 1) // 2)]
    hb = b[len(b) // 2:] or b[-1:]
    return ha + hb


def ship_percent(uid_a: int, uid_b: int, pa: Optional[dict], pb: Optional[dict], day: str) -> int:
    """درصدِ سازگاری — برای یه زوج تو یه روز همیشه یکسانه (اسپم‌کردن جواب رو عوض نمی‌کنه)."""
    lo, hi = sorted((uid_a, uid_b))
    h = int(hashlib.sha256(f"{lo}:{hi}:{day}".encode()).hexdigest()[:8], 16)
    base = h % 101
    ca = (pa or {}).get("class")
    cb = (pb or {}).get("class")
    compat = _CLASS_COMPAT.get(frozenset({ca, cb}), 55) if ca and cb else 55
    la = int((pa or {}).get("level", 1) or 1)
    lb = int((pb or {}).get("level", 1) or 1)
    closeness = max(0, 100 - abs(la - lb) * 4)
    return max(1, min(100, round(0.5 * base + 0.3 * compat + 0.2 * closeness)))


def ship_verdict(pct: int) -> str:
    for th, line in SHIP_TIERS:
        if pct >= th:
            return line
    return SHIP_TIERS[-1][1]


def ship_bar(pct: int) -> str:
    n = round(pct / 10)
    return "❤️" * n + "🖤" * (10 - n)


# ─── 📊 مقایسه ──────────────────────────────────────────────
def _power(p: dict) -> int:
    try:
        from combat_power import calculate_combat_power
        return int(calculate_combat_power(p))
    except Exception:
        return 0


def _row_stats(p: dict) -> dict:
    f = sg._facts(p)
    return {
        "power": _power(p), "level": f["level"], "wealth": f["total"] - f["debt"],
        "kills": f["kills"], "pvp": f["pvp_w"], "deaths": f["deaths"],
        "duels": int((p.get("sg_state") or {}).get("duel_wins", 0)),
    }


# (کلید, برچسب, بیشتر بهتره؟)
_CMP_ROWS = [
    ("power", "⚡ قدرتِ رزمی", True), ("level", "⭐ لول", True), ("wealth", "💰 دارایی خالص", True),
    ("kills", "💀 کیل", True), ("pvp", "🆚 بردِ آرنا", True),
    ("duels", "⚔️ بردِ دوئل", True), ("deaths", "⚰️ مرگ (کمتر=بهتر)", False),
]


def compare_card(pa: dict, pb: dict, na: str, nb: str) -> str:
    sa, sb = _row_stats(pa), _row_stats(pb)
    wa = wb = 0
    lines = [f"📊 **رویارویی: {na} ⚔️ {nb}**", ""]
    for key, label, higher in _CMP_ROWS:
        va, vb = sa[key], sb[key]
        if key == "power" and va == vb == 0:
            continue
        if va == vb:
            mark_a = mark_b = ""
        elif (va > vb) == higher:
            mark_a, mark_b = " ✅", ""
            wa += 1
        else:
            mark_a, mark_b = "", " ✅"
            wb += 1
        lines.append(f"{label}: **{va:,}**{mark_a}  ◀️  **{vb:,}**{mark_b}")
    lines.append("")
    if wa == wb:
        lines.append("🤝 **مساویِ مساوی!** باید تو دوئل حلش کنین.")
    else:
        w, n = (na, wa) if wa > wb else (nb, wb)
        lines.append(f"🏆 **برنده: {w}** ({n} از {wa + wb} دسته)")
    return "\n".join(lines)


# ─── 🏷 قیمتش چنده ──────────────────────────────────────────
_PRICE_LADDER = [
    (1, "یه نونِ خشک و یه نگاهِ ترحم‌آمیز 🍞"),
    (50, "یه جفت جورابِ بی‌جفت 🧦"),
    (200, "یه گاوِ لاغرِ بازارِ روز 🐄"),
    (1_000, "یه شمشیرِ زنگ‌زده + یه شانسِ کوچیک 🗡"),
    (5_000, "یه مرکبِ نیمه‌جون 🐴"),
    (20_000, "یه خونه‌ی کوچیک تو حومه‌ی محفل 🏚"),
    (100_000, "یه قلعه‌ی نیمه‌ساز 🏰"),
    (10**12, "یه شهرِ کامل با مالیاتش 👑"),
]
_PRICE_VERDICT = [
    "اینو کارشناسِ رسمیِ بازار سیاه تأیید کرده 🧐",
    "با تخفیفِ ویژه‌ی «چون رفیقی»! 😏",
    "قیمتِ نهایی — قابل‌چانه‌زنی نیست 🔒",
    "مالیات و کارمزد جداست 🧾",
]


def market_value(p: dict) -> int:
    f = sg._facts(p)
    return int(f["total"] * 0.05 + f["level"] * 40 + f["kills"] * 4 + f["pvp_w"] * 80
               - f["deaths"] * 25 - f["debt"] * 0.3)


def price_text(p: dict, name: str) -> str:
    v = market_value(p)
    if v <= 0:
        return (f"🏷 **ارزشِ بازارِ {name}:** منفی! 📉\n"
                "بدهی و مرگ‌هاش ازش بیشتره؛ بازار حاضره خودش پول بده تا نخرتش 💀\n\n"
                f"{random.choice(_PRICE_VERDICT)}")
    thing = next(txt for th, txt in reversed(_PRICE_LADDER) if v >= th)
    return (f"🏷 **ارزشِ بازارِ {name}:** {v:,} Zen\n"
            f"معادلِ: {thing}\n\n{random.choice(_PRICE_VERDICT)}")


# ─── 🪦 فاتحه ───────────────────────────────────────────────
_FATIHA_BASE = [
    "اینجا خوابیده {n}؛ مردی که همیشه می‌گفت «این دفعه فرق می‌کنه»… و نکرد 🕯",
    "{n}، شمشیرت رو بالا ببر؛ حتی اگه از دور بیاد… ما حواسمون بهت هست 🪦",
    "یه دقیقه سکوت برای {n}؛ خدا رحمتش کنه، یا رحمتشون کنه 🙏",
    "{n} رفت… ولی لینکِ کیف‌پولش هنوز همینجاست 💸🕯",
]


def fatiha_text(p: dict, name: str) -> str:
    f = sg._facts(p)
    extra = []
    if f["deaths"] >= 3:
        extra.append(f"{f['deaths']} بار مُرد و {f['deaths']} بار برگشت؛ قبرستون براش اشتراکِ سالانه صادر کرده ⚰️")
    if f["hp_pct"] < 30:
        extra.append(f"جونش {f['hp_pct']}٪ مونده؛ فاتحه رو پیش‌پرداخت می‌خونیم، چون احتمالِ مرگش بالاست 🩸")
    if f["total"] < 2_000:
        extra.append("تنها ارثش یه کیفِ خالیه… که اونم قرضِ کسیه 👛")
    if f["kills"] < 10:
        extra.append("تو عمرش یه مرغ هم نکشت؛ شاید همین نجاتش ندهد 🐔")
    body = random.choice(_FATIHA_BASE).replace("{n}", name)
    if extra:
        body += "\n\n" + random.choice(extra)
    return f"🪦 **فاتحه برای {name}**\n\n{body}\n\n🤲 الفاتحه…"


def record_fatiha(p: dict):
    st2(p)["fatiha_received"] += 1


# ─── ⚖️ محاکمه ──────────────────────────────────────────────
TRIAL_SEC = 60
TRIAL_MIN_VOTES = 2
_CRIMES_GENERIC = [
    "دزدیدنِ آخرین تکه‌ی نونِ محفل 🍞", "ترک‌کردنِ رِید درست وقتی باس ۱٪ مونده بود 🏃",
    "نفرینِ بی‌دلیلِ دوستانِ بی‌گناه 🩸", "پخشِ شایعه‌ی «ربات بن‌م می‌کنه» 📢",
    "حمله به یه اسلایمِ بی‌دفاع 🟢", "فروشِ سیب‌زمینیِ پوسیده به عنوانِ آیتمِ اسطوره‌ای 🥔",
]
GUILTY_NICKS = ["⚖️ محکومِ محفل", "🔗 زندانیِ فصل", "🧑‍⚖️ مجرمِ ثبت‌شده", "⛓ در بندِ محفل"]
INNOCENT_NICKS = ["😇 بی‌گناهِ محفل", "🕊 تبرئه‌شده", "🛡 دادگاه‌پسند", "✨ پاک‌دامن"]


def pick_crime(p: Optional[dict]) -> str:
    f = sg._facts(p or {})
    c = []
    if f["debt"] > 0:
        c.append("فرار از پرداختِ بدهیِ بانکی 🏦")
    if f["deaths"] >= 5:
        c.append("تکرارِ مرگ برای خرابِ‌کردنِ آمارِ تیمی ⚰️")
    if f["weekly"] < -2_000:
        c.append("پولشویی به نفعِ کازینو 🎰")
    if f["pvp_l"] > f["pvp_w"] and f["pvp_l"] >= 3:
        c.append("اشغالِ دائمیِ تخت‌های آرنا 🏟")
    return random.choice(c + _CRIMES_GENERIC)


_TRIALS: dict[int, dict] = {}                 # trial_id → state
_TRIAL_BY_CHAT: dict[int, int] = {}           # chat_id → trial_id فعال
_trial_seq = itertools.count(1)
_tasks: set = set()


def trial_create(chat_id: int, judge_uid: int, def_uid: int, def_name: str, crime: str) -> Optional[int]:
    if chat_id in _TRIAL_BY_CHAT:
        return None
    tid = next(_trial_seq)
    _TRIALS[tid] = {"chat": chat_id, "judge": judge_uid, "def": def_uid, "def_name": def_name,
                    "crime": crime, "votes": {}, "msg_id": None, "done": False}
    _TRIAL_BY_CHAT[chat_id] = tid
    return tid


def trial_get(tid: int) -> Optional[dict]:
    t = _TRIALS.get(tid)
    return t if t and not t["done"] else None


def trial_active_in(chat_id: int) -> bool:
    return chat_id in _TRIAL_BY_CHAT


def trial_vote(tid: int, uid: int, guilty: bool) -> str:
    """'ok' | 'dup' | 'defendant' | 'closed'"""
    t = trial_get(tid)
    if not t:
        return "closed"
    if uid == t["def"]:
        return "defendant"
    if uid in t["votes"]:
        return "dup"
    t["votes"][uid] = guilty
    return "ok"


def trial_verdict(tid: int) -> dict:
    t = _TRIALS.get(tid)
    g = sum(1 for v in t["votes"].values() if v)
    i = len(t["votes"]) - g
    if len(t["votes"]) < TRIAL_MIN_VOTES:
        verdict = "dismissed"
    elif g > i:
        verdict = "guilty"
    elif i > g:
        verdict = "innocent"
    else:
        verdict = "tie"
    return {"verdict": verdict, "guilty": g, "innocent": i, "def": t["def"],
            "def_name": t["def_name"], "crime": t["crime"]}


def verdict_nick(verdict: str) -> Optional[str]:
    if verdict == "guilty":
        return random.choice(GUILTY_NICKS)
    if verdict == "innocent":
        return random.choice(INNOCENT_NICKS)
    return None


def apply_verdict_nick(player: dict, label: str, by: str):
    """لقبِ ۲۴ ساعته با همون ساختارِ «لقب» نسخه‌ی اول (تا /status و نمایشِ اسم یکی باشه)."""
    st = sg.get_state(player)
    st["nick"] = {"label": label, "until": time.time() + sg.NICK_SEC, "by": by}


def verdict_text(r: dict, label: Optional[str]) -> str:
    head = f"⚖️ **حکمِ دادگاه — {r['def_name']}**\n📜 اتهام: {r['crime']}\n\n🗳 رأی‌ها: ⚖️ گناهکار **{r['guilty']}** | 😇 بی‌گناه **{r['innocent']}**\n\n"
    if r["verdict"] == "dismissed":
        return head + f"🪑 رأیِ کافی (حداقل {TRIAL_MIN_VOTES} نفر) جمع نشد؛ **پرونده مختومه شد.**"
    if r["verdict"] == "tie":
        return head + "⚖️ رأی‌ها مساوی شد؛ قاضی هم شونه بالا انداخت — **تبرئه به نفعِ متهم.** 🤷"
    if r["verdict"] == "guilty":
        return head + f"🔨 **گناهکار شناخته شد!**\n🏷 حکم: لقبِ «{label}» تا ۲۴ ساعت"
    return head + f"🕊 **بی‌گناه شناخته شد!**\n🏷 جایزه: لقبِ «{label}» تا ۲۴ ساعت"


async def _end_trial(tid: int, finish: Callable[[dict, Optional[str]], Awaitable[None]]):
    t = _TRIALS.get(tid)
    if not t or t["done"]:
        return
    t["done"] = True
    try:
        r = trial_verdict(tid)
        label = verdict_nick(r["verdict"])
        await finish(r, label)
    finally:
        _TRIAL_BY_CHAT.pop(t["chat"], None)
        _TRIALS.pop(tid, None)


def schedule_trial_end(tid: int, finish, seconds: int = TRIAL_SEC):
    async def _runner():
        try:
            await asyncio.sleep(seconds)
            await _end_trial(tid, finish)
        except Exception:
            t = _TRIALS.pop(tid, None)
            if t:
                _TRIAL_BY_CHAT.pop(t["chat"], None)
            raise
    task = asyncio.create_task(_runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ─── 🎁 جعبه‌ی مرموز ────────────────────────────────────────
BOX_MIN = 100
BOX_MAX = 20_000
BOX_SEC = 90
BOX_CD = 20

_BOXES: dict[int, dict] = {}                  # box_id → state
_BOX_BY_SENDER: dict[tuple[int, int], int] = {}   # (chat, sender) → box_id
_box_seq = itertools.count(1)


def box_create(chat_id: int, sender: int, target: int, s_name: str, t_name: str, stake: int) -> Optional[int]:
    if (chat_id, sender) in _BOX_BY_SENDER:
        return None
    bid = next(_box_seq)
    _BOXES[bid] = {"chat": chat_id, "sender": sender, "target": target, "s_name": s_name,
                   "t_name": t_name, "stake": stake, "msg_id": None, "done": False}
    _BOX_BY_SENDER[(chat_id, sender)] = bid
    return bid


def box_get(bid: int) -> Optional[dict]:
    b = _BOXES.get(bid)
    return b if b and not b["done"] else None


def box_close(bid: int) -> Optional[dict]:
    """بستنِ اتمیکِ جعبه (فقط یه بار موفق می‌شه — ضدِ دوبار-کلیک)."""
    b = _BOXES.get(bid)
    if not b or b["done"]:
        return None
    b["done"] = True
    _BOX_BY_SENDER.pop((b["chat"], b["sender"]), None)
    _BOXES.pop(bid, None)
    return b


BOX_LUCKY = [
    "🎁 جعبه باز شد و از درونش طلا ریخت! {t} برنده شد 🌟",
    "✨ نورِ طلایی! جعبه برای {t} مهربون بود 🍀",
]
BOX_BOMB = [
    "💥 بوووم! جعبه ترکید و کیفِ {t} رو سوزوند 🔥",
    "🕷 از جعبه یه عنکبوتِ دزد پرید بیرون و از جیبِ {t} Zen کش رفت 😱",
]
BOX_EMPTY = ["🕳 جعبه خالی بود؛ نه برد، نه باخت… فقط یه حسِ عجیب 🫥"]


def settle_box(sender: dict, target: dict, stake: int, s_name: str, t_name: str) -> dict:
    """۴۷٫۵٪ target می‌بره (از sender)، ۴۷٫۵٪ می‌ترکه (از target به sender)، ۵٪ خالی.
    صفرجمع و بی‌طرف. باید زیرِ هر دو قفل صدا زده بشه؛ ذخیره با caller."""
    r = random.random()
    if r < 0.05:
        return {"kind": "empty", "text": random.choice(BOX_EMPTY)}
    if r < 0.525:
        sender["zen"] = _zen(sender) - stake
        target["zen"] = _zen(target) + stake
        return {"kind": "lucky", "text": random.choice(BOX_LUCKY).format(t=t_name) + f"\n💰 {stake:,} Zen از جیبِ {s_name} به {t_name} رسید"}
    sender["zen"] = _zen(sender) + stake
    target["zen"] = _zen(target) - stake
    return {"kind": "bomb", "text": random.choice(BOX_BOMB).format(t=t_name) + f"\n💸 {stake:,} Zen از {t_name} به {s_name} رسید"}


def schedule_box_expiry(bid: int, on_expire: Callable[[dict], Awaitable[None]], seconds: int = BOX_SEC):
    async def _runner():
        await asyncio.sleep(seconds)
        b = box_close(bid)        # اگه قبلاً باز/رد شده، None می‌ده و کاری نمی‌کنیم
        if b:
            await on_expire(b)
    task = asyncio.create_task(_runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
