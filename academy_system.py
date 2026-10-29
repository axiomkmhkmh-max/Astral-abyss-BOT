# ============================================================
#  ASTRAL ABYSS — Academy Arc 🎓 (فصلِ آکادمی)
# ------------------------------------------------------------
#  یه فصلِ محدود و اختیاری شبیهِ آکادمی‌های جادوگریِ ایسکای‌ها:
#  بازیکن ثبت‌نام می‌کنه، کلاس‌های درسی می‌ره (پسیوِ کول‌داون‌دار،
#  بونوسِ استتِ کوچیکِ تدریجی می‌ده)، امتیازِ آکادمی جمع می‌کنه
#  (رقابتِ دانش‌آموزی/لیدربورد)، و آخرِ هر سال یه امتحانِ نهایی
#  می‌ده. ۳ سال تمومه — فارغ‌التحصیلی یه عنوانِ دائمی می‌ده.
#
#  دیتا: player["academy"] = {
#      "enrolled": bool, "year": int, "subjects": {id:int},
#      "academy_points": int, "graduated": bool,
#  }
#  player["academy_last_class_ts"] — کول‌داونِ کلاسِ بعدی.
# ============================================================
import random
import time

ENROLL_LEVEL_REQ = 8
CLASS_COOLDOWN = 3 * 3600   # هر ۳ ساعت یه کلاس
YEARS_TOTAL = 3

SUBJECTS = {
    "combat": {"name": "⚔️ نبردِ کاربردی", "stat": "atk", "bonus_per_point": 0.6},
    "magic":  {"name": "🔮 نظریه‌ی آرکین",  "stat": "def", "bonus_per_point": 0.6},
    "lore":   {"name": "📚 تاریخِ Abyss",   "stat": "max_hp", "bonus_per_point": 2.0},
}

EXAM_REQ_PER_YEAR = {1: 15, 2: 35, 3: 60}   # مجموعِ امتیازِ سه‌تا درس، لازم برای امتحانِ اون سال

# ─── امتحانِ واقعی (بدونِ شانس) ───────────────────────────────
#  هر سال یه امتحانِ چندگزینه‌ایِ زمان‌دار: n سؤال، حدِ نصابِ pass، و secs ثانیه برای هر سؤال.
#  قبولی فقط به تعدادِ جوابِ درست بستگی داره. درس‌خوندن (امتیازِ کلاس‌ها) شرطِ ورود به امتحانه
#  و برای هر HINT_POINTS_PER امتیاز یه «راهنما» (حذفِ دو گزینه‌ی غلط) تو امتحان بهت می‌ده.
EXAM_CONFIG = {
    1: {"n": 6,  "pass": 4, "secs": 60},
    2: {"n": 8,  "pass": 6, "secs": 50},
    3: {"n": 10, "pass": 9, "secs": 45},
}
EXAM_RETAKE_COOLDOWN = 2 * 3600   # بعد از رد شدن، ۲ ساعت باید دوباره درس بخونی
EXAM_GRACE_SECS = 3               # تلورانسِ تأخیرِ شبکه‌ی تلگرام
HINT_POINTS_PER = 15
MAX_HINTS = 3

GRADUATION_TITLE = "🎓 فارغ‌التحصیلِ آکادمی"


def _academy(player: dict) -> dict:
    a = player.get("academy")
    if not a:
        a = {"enrolled": False, "year": 1, "subjects": {s: 0 for s in SUBJECTS}, "academy_points": 0, "graduated": False}
        player["academy"] = a
    return a


def can_enroll(player: dict) -> tuple[bool, str]:
    a = _academy(player)
    if a["enrolled"]:
        return False, "❌ قبلاً ثبت‌نام کردی."
    if player.get("level", 1) < ENROLL_LEVEL_REQ:
        return False, f"❌ برای ثبت‌نام باید سطح {ENROLL_LEVEL_REQ} باشی."
    return True, ""


def enroll(player: dict) -> tuple[bool, str]:
    ok, err = can_enroll(player)
    if not ok:
        return False, err
    a = _academy(player)
    a["enrolled"] = True
    return True, (
        "🎓 **به آکادمی خوش اومدی!**\n\n"
        "سه سالِ سخت در پیشه — سه تا درس، امتحانِ پایانِ هر سال، و اگه دووم بیاری، "
        "یه عنوانِ دائمی که همیشه همراهته."
    )


def can_attend_class(player: dict) -> tuple[bool, int]:
    last = player.get("academy_last_class_ts", 0)
    remaining = CLASS_COOLDOWN - (time.time() - last)
    return remaining <= 0, max(0, int(remaining))


def attend_class(player: dict, subject_id: str) -> tuple[bool, str]:
    a = _academy(player)
    if not a["enrolled"]:
        return False, "❌ اول باید تو آکادمی ثبت‌نام کنی."
    if a["graduated"]:
        return False, "❌ قبلاً فارغ‌التحصیل شدی — دیگه کلاسی نمونده."
    if subject_id not in SUBJECTS:
        return False, "❌ درسِ نامعتبر."
    ok, remaining = can_attend_class(player)
    if not ok:
        mins = remaining // 60
        return False, f"⏳ خسته‌ای — {mins} دقیقه‌ی دیگه دوباره سرِ کلاس برگرد."

    subj = SUBJECTS[subject_id]
    gained = random.randint(2, 5)
    a["subjects"][subject_id] = a["subjects"].get(subject_id, 0) + gained
    a["academy_points"] = a.get("academy_points", 0) + gained
    player["academy_last_class_ts"] = time.time()

    stat_gain = round(gained * subj["bonus_per_point"], 1)
    stats = player.setdefault("stats", {})
    stat_key = subj["stat"]
    stats[stat_key] = stats.get(stat_key, 0) + stat_gain
    if stat_key == "max_hp":
        player["max_hp"] = player.get("max_hp", 100) + stat_gain
        player["hp"] = player.get("hp", player["max_hp"]) + stat_gain
        stats["hp"] = stats.get("hp", stats.get("max_hp", 100)) + stat_gain

    return True, (
        f"📖 سرِ کلاسِ {subj['name']} حاضر شدی.\n"
        f"+{gained} امتیازِ {subj['name']} | +{stat_gain} {stat_key}"
    )


def exam_progress(player: dict) -> tuple[int, int]:
    a = _academy(player)
    total = sum(a["subjects"].values())
    req = EXAM_REQ_PER_YEAR.get(a["year"], 999)
    return total, req


def exam_cfg(player: dict) -> dict:
    return EXAM_CONFIG.get(_academy(player)["year"], EXAM_CONFIG[3])


def exam_retake_remaining(player: dict) -> int:
    return max(0, int(_academy(player).get("exam_retry_ts", 0) - time.time()))


def can_take_exam(player: dict) -> tuple[bool, str]:
    a = _academy(player)
    if not a["enrolled"]:
        return False, "❌ اول باید ثبت‌نام کنی."
    if a["graduated"]:
        return False, "❌ قبلاً فارغ‌التحصیل شدی."
    if a.get("exam"):          # امتحانِ نیمه‌کاره رو می‌شه ادامه داد
        return True, ""
    total, req = exam_progress(player)
    if total < req:
        return False, f"❌ هنوز آماده نیستی — {total}/{req} امتیازِ لازم."
    rem = exam_retake_remaining(player)
    if rem > 0:
        return False, f"⏳ رد شدی — {rem // 60} دقیقه‌ی دیگه می‌تونی دوباره امتحان بدی. تا اون موقع درس بخون!"
    return True, ""


def exam_intro_text(player: dict) -> str:
    a = _academy(player)
    cfg = exam_cfg(player)
    total, _ = exam_progress(player)
    hints = min(MAX_HINTS, total // HINT_POINTS_PER)
    return (
        f"📝 **امتحانِ پایانیِ سالِ {a['year']}**\n\n"
        f"• {cfg['n']} سؤالِ چهارگزینه‌ای از سه درس: نبرد ⚔️، جادو 🔮، تاریخِ Abyss 📚\n"
        f"• برای قبولی حداقل **{cfg['pass']} از {cfg['n']}** جوابِ درست لازمه\n"
        f"• هر سؤال **{cfg['secs']} ثانیه** وقت داره — جوابِ دیرهنگام غلط حساب می‌شه\n"
        f"• 💡 تعدادِ راهنماهات (هر کدوم دو گزینه‌ی غلط رو حذف می‌کنه): **{hints}**\n"
        f"• نتیجه فقط به جوابِ درست بستگی داره — شانسی تو کار نیست\n"
        f"• رد بشی، {EXAM_RETAKE_COOLDOWN // 3600} ساعت باید صبر کنی و سؤال‌ها عوض می‌شن\n"
        f"• وسطِ امتحان نمی‌تونی ولش کنی: وقت می‌گذره و سؤال‌های جواب‌نداده غلط حساب می‌شن\n\n"
        f"آماده‌ای؟"
    )


def start_exam(player: dict) -> tuple[bool, str]:
    """امتحانِ جدید رو شروع می‌کنه (یا اگه نیمه‌کاره هست همون رو نگه می‌داره)."""
    ok, err = can_take_exam(player)
    if not ok:
        return False, err
    a = _academy(player)
    if a.get("exam"):
        return True, ""
    from academy_exam import build_questions
    cfg = exam_cfg(player)
    total, _ = exam_progress(player)
    qs = build_questions(a["year"], cfg["n"])
    now = time.time()
    qs[0]["t0"] = now
    a["exam"] = {
        "sid": f"{random.randrange(16**5):05x}",
        "year": a["year"],
        "qs": qs,
        "i": 0,
        "hints": min(MAX_HINTS, total // HINT_POINTS_PER),
    }
    return True, ""


def _finalize(player: dict) -> tuple[bool, str]:
    res = _finalize_inner(player)
    _academy(player)["exam_result"] = {"passed": res[0], "text": res[1]}
    return res


def _finalize_inner(player: dict) -> tuple[bool, str]:
    a = _academy(player)
    ex = a["exam"]
    cfg = EXAM_CONFIG.get(ex["year"], EXAM_CONFIG[3])
    qs = ex["qs"]
    correct = sum(1 for q in qs if q.get("g") == q["a"])
    a["exam"] = None
    passed = correct >= cfg["pass"]

    per = {}
    for q in qs:
        c, t = per.get(q["s"], (0, 0))
        per[q["s"]] = (c + (1 if q.get("g") == q["a"] else 0), t + 1)
    breakdown = " | ".join(f"{SUBJECTS[s]['name']}: {c}/{t}" for s, (c, t) in per.items())
    score_line = f"🎯 نمره: **{correct}/{cfg['n']}** (حدِ نصاب: {cfg['pass']})\n{breakdown}"

    if not passed:
        a["exam_retry_ts"] = time.time() + EXAM_RETAKE_COOLDOWN
        weakest = min(per.items(), key=lambda kv: kv[1][0] / kv[1][1])[0]
        return False, (
            f"📝 **امتحانِ سالِ {ex['year']} رو رد شدی...**\n\n{score_line}\n\n"
            f"ضعیف‌ترین درسِت: {SUBJECTS[weakest]['name']}. "
            f"{EXAM_RETAKE_COOLDOWN // 3600} ساعت دیگه می‌تونی با سؤال‌های جدید دوباره امتحان بدی."
        )

    a["exam_retry_ts"] = 0
    a["subjects"] = {s: 0 for s in SUBJECTS}  # امتیازها برای سالِ بعد صفر می‌شن
    if a["year"] >= YEARS_TOTAL:
        a["graduated"] = True
        titles = player.setdefault("titles_unlocked", [])
        if GRADUATION_TITLE not in titles:
            titles.append(GRADUATION_TITLE)
        bonus_hp = 100
        player["max_hp"] = player.get("max_hp", 100) + bonus_hp
        player["hp"] = player.get("hp", player["max_hp"]) + bonus_hp
        stats = player.setdefault("stats", {})
        stats["max_hp"] = stats.get("max_hp", 100) + bonus_hp
        stats["hp"] = stats.get("hp", stats.get("max_hp", 100)) + bonus_hp
        return True, (
            f"🎉 **قبول شدی! و فارغ‌التحصیل شدی!** 🎓\n\n{score_line}\n\n"
            f"عنوانِ «{GRADUATION_TITLE}» بهت داده شد.\n"
            f"❤️ +{bonus_hp} HP دائمی به‌عنوانِ هدیه‌ی فارغ‌التحصیلی."
        )

    a["year"] += 1
    return True, (
        f"✅ **امتحانِ سالِ {a['year']-1} رو قبول شدی!**\n\n{score_line}\n\n"
        f"حالا وارد سالِ {a['year']} شدی — امتحانش سخت‌تره."
    )


def _settle(player: dict) -> tuple[bool, str] | None:
    """سؤال‌هایی که وقتشون تموم شده رو غلط حساب می‌کنه؛ اگه امتحان تموم شد نتیجه رو برمی‌گردونه."""
    a = _academy(player)
    ex = a.get("exam")
    if not ex:
        return None
    cfg = EXAM_CONFIG.get(ex["year"], EXAM_CONFIG[3])
    now = time.time()
    qs = ex["qs"]
    while ex["i"] < len(qs):
        q = qs[ex["i"]]
        deadline = q["t0"] + cfg["secs"] + EXAM_GRACE_SECS
        if now <= deadline:
            return None
        q["g"] = -1  # تایم‌اوت
        ex["i"] += 1
        if ex["i"] < len(qs):
            qs[ex["i"]]["t0"] = q["t0"] + cfg["secs"]  # ساعتِ سؤالِ بعدی از لحظه‌ی تموم شدنِ این یکی
    return _finalize(player)


def pending_result(player: dict) -> dict | None:
    """نتیجه‌ی امتحانی که تموم شده ولی هنوز به بازیکن نشون داده نشده (یه بار مصرف). ممکنه player رو تغییر بده."""
    _settle(player)
    return _academy(player).pop("exam_result", None)


def exam_view(player: dict) -> dict:
    """
    وضعیتِ فعلیِ امتحان برای رندر:
      {"kind": "none"} | {"kind": "result", "passed": bool, "text": str}
      | {"kind": "question", "sid", "qi", "text", "options": [(idx,label)], "hints": int, "can_hint": bool}
    ممکنه player رو تغییر بده (تایم‌اوت/پایان) — caller باید save کنه.
    """
    _settle(player)
    res = pending_result(player)
    if res is not None:
        return {"kind": "result", "passed": res["passed"], "text": res["text"]}
    a = _academy(player)
    ex = a.get("exam")
    if not ex:
        return {"kind": "none"}
    cfg = EXAM_CONFIG.get(ex["year"], EXAM_CONFIG[3])
    qi = ex["i"]
    q = ex["qs"][qi]
    left = max(0, int(q["t0"] + cfg["secs"] - time.time()))
    answered = sum(1 for x in ex["qs"] if x.get("g") is not None)
    options = [(i, o) for i, o in enumerate(q["o"]) if i not in q["hid"]]
    lines = [
        f"📝 **امتحانِ سالِ {ex['year']} — سؤالِ {qi + 1}/{len(ex['qs'])}**",
        f"⏱ {left} ثانیه‌ی دیگه | 💡 راهنما: {ex['hints']} | پاسخ‌داده‌شده: {answered}",
        f"{SUBJECTS[q['s']]['name']}\n",
        q["t"] + "\n",
    ]
    for n, (_, label) in enumerate(options, start=1):
        lines.append(f"{n}) {label}")
    return {
        "kind": "question", "sid": ex["sid"], "qi": qi, "text": "\n".join(lines),
        "options": options, "hints": ex["hints"], "can_hint": ex["hints"] > 0 and not q["hid"],
    }


def submit_answer(player: dict, sid: str, qi: int, opt: int) -> str | None:
    """جوابِ یه سؤال رو ثبت می‌کنه. اگه دکمه‌ی قدیمی/تکراری بود پیامِ خطا برمی‌گردونه، وگرنه None."""
    _settle(player)
    ex = _academy(player).get("exam")
    if not ex or ex["sid"] != sid or ex["i"] != qi:
        return "⚠️ این سؤال دیگه فعال نیست."
    q = ex["qs"][qi]
    if opt < 0 or opt >= len(q["o"]) or opt in q["hid"]:
        return "⚠️ گزینه‌ی نامعتبر."
    q["g"] = opt
    ex["i"] += 1
    if ex["i"] < len(ex["qs"]):
        ex["qs"][ex["i"]]["t0"] = time.time()
    else:
        ex["done"] = True
    return None


def use_hint(player: dict, sid: str, qi: int) -> str:
    _settle(player)
    ex = _academy(player).get("exam")
    if not ex or ex["sid"] != sid or ex["i"] != qi:
        return "⚠️ این سؤال دیگه فعال نیست."
    q = ex["qs"][qi]
    if q["hid"]:
        return "💡 برای این سؤال راهنما گرفتی."
    if ex["hints"] <= 0:
        return "💡 راهنما نداری."
    wrong = [i for i in range(len(q["o"])) if i != q["a"]]
    q["hid"] = random.sample(wrong, 2)
    ex["hints"] -= 1
    return "💡 دو گزینه‌ی غلط حذف شد."


def academy_power_bonus(player: dict) -> float:
    """سهمِ گذروندنِ سال‌های آکادمی برای Combat Power."""
    a = player.get("academy")
    if not a:
        return 0.0
    return (a.get("year", 1) - 1) * 60 + (150 if a.get("graduated") else 0)


def top_students(all_players_dict: dict, limit: int = 10) -> list[tuple[str, dict]]:
    ranked = [
        (uid, p) for uid, p in all_players_dict.items()
        if p.get("academy", {}).get("enrolled")
    ]
    ranked.sort(key=lambda kv: kv[1]["academy"].get("academy_points", 0), reverse=True)
    return ranked[:limit]


def status_text(player: dict) -> str:
    a = _academy(player)
    if not a["enrolled"]:
        req_ok, msg = can_enroll(player)
        return (
            "🎓 **آکادمی**\n\n"
            "یه فصلِ محدود — سه سالِ درس و امتحان، با یه عنوانِ دائمی در انتها.\n\n"
            + (f"✅ می‌تونی ثبت‌نام کنی!" if req_ok else msg)
        )
    if a["graduated"]:
        return f"🎓 **فارغ‌التحصیلِ آکادمی هستی!**\n\nمجموعِ امتیازِ کسب‌شده: {a['academy_points']:,}"

    total, req = exam_progress(player)
    lines = [
        f"🎓 **آکادمی — سالِ {a['year']}/{YEARS_TOTAL}**\n",
        f"📊 پیشرفتِ امتحان: {total}/{req}",
    ]
    for sid, s in SUBJECTS.items():
        lines.append(f"  {s['name']}: {a['subjects'].get(sid,0)}")
    cfg = exam_cfg(player)
    lines.append(f"📝 امتحان: {cfg['n']} سؤال، قبولی با {cfg['pass']} جوابِ درست")
    rem = exam_retake_remaining(player)
    if a.get("exam"):
        lines.append("⚠️ یه امتحانِ نیمه‌کاره داری — بزن «امتحان بده» تا ادامه بدی.")
    elif rem > 0:
        lines.append(f"⏳ امتحانِ مجدد تا {rem // 60} دقیقه‌ی دیگه")
    lines.append(f"\n🏆 امتیازِ کلِ آکادمی: {a['academy_points']:,}")
    return "\n".join(lines)
