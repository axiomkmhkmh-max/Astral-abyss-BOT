# ============================================================
#  ASTRAL ABYSS — Ascension Trial Battle ⚡ (آزمونِ عروجِ واقعی)
# ------------------------------------------------------------
#  قبلاً نتیجه‌ی Trial یه random.random() بود. حالا یه نبردِ
#  مهارتیِ نوبتی با باسه، بدونِ هیچ شانسی تو نتیجه:
#
#   • باس هر دور یه «تلگراف» می‌ده (حرکتی که داره آماده می‌کنه)
#   • تو باید جوابِ درست رو بزنی: هر باس قوانینِ مخصوصِ خودش داره
#     (کدوم حرکت با کدوم جواب خنثی می‌شه) — از 📜 قوانین می‌تونی ببینی،
#     ولی تایمر هم می‌ره!
#   • هر اشتباه (یا تایم‌اوت) یه «جان» می‌گیره. جان تموم بشه = شکست.
#   • Combat Power فقط تعدادِ جان‌هات رو تعیین می‌کنه (هرچی قوی‌تر،
#     حاشیه‌ی اشتباهِ بیشتر) — نتیجه همیشه قطعیه، نه شانسی.
#
#  دنباله‌ی تلگراف‌ها هر بار فرق می‌کنه، ولی همیشه با جوابِ درست قابلِ
#  بردنه. هیچ‌چیزِ تصادفی «قبولی» رو تعیین نمی‌کنه.
#  ⚠️ تو متن‌ها از < > & استفاده نشده (parse_mode=HTML).
# ============================================================
import random
import time

GRACE_SECS = 3

# حرکت‌های باس (تلگراف)
MOVES = {
    "fire":  "🔥 باس نفسِ آتشین جمع می‌کنه",
    "sweep": "🌪 باس برای جاروکردنِ زمین آماده می‌شه",
    "grab":  "🕳 باس دستش رو برای چنگ‌زدن دراز می‌کنه",
    "bolt":  "⚡ باس انرژی‌ای دوربُرد تو شاخش جمع می‌کنه",
}
# جواب‌های بازیکن
COUNTERS = {
    "guard":   "🛡 دفاع",
    "dodge":   "💨 جاخالی",
    "strike":  "⚔️ ضدحمله",
    "reflect": "🔮 بازتاب",
}

# تنظیماتِ هر Trial: rounds، ثانیه برای هر دور، جانِ پایه، و قوانینِ باس (move → counter درست)
TRIAL_BATTLES = {
    "trial_1": {
        "boss": "نگهبانِ بیداری", "rounds": 6, "secs": 25, "base_lives": 2,
        "rules": {"fire": "guard", "sweep": "dodge", "grab": "strike", "bolt": "reflect"},
    },
    "trial_2": {
        "boss": "هیولای آشوب", "rounds": 8, "secs": 22, "base_lives": 2,
        "rules": {"fire": "dodge", "sweep": "guard", "grab": "strike", "bolt": "reflect"},
    },
    "trial_3": {
        "boss": "شوالیه‌ی سقوط", "rounds": 10, "secs": 20, "base_lives": 2,
        "rules": {"fire": "guard", "sweep": "strike", "grab": "reflect", "bolt": "dodge"},
    },
    "trial_4": {
        "boss": "فرمانروای استعلا", "rounds": 12, "secs": 18, "base_lives": 1,
        "rules": {"fire": "reflect", "sweep": "strike", "grab": "dodge", "bolt": "guard"},
    },
    "trial_5": {
        "boss": "پادشاهِ ابدیت", "rounds": 14, "secs": 15, "base_lives": 1,
        "rules": {"fire": "strike", "sweep": "reflect", "grab": "guard", "bolt": "dodge"},
    },
}


def lives_for(trial_id: str, player_cp: int, rec_cp: int) -> int:
    """تعدادِ جان‌ها: پایه + اثرِ CP (نسبت به CP توصیه‌شده). حداقل ۱، حداکثر پایه+2."""
    cfg = TRIAL_BATTLES[trial_id]
    ratio = player_cp / max(1, rec_cp)
    bonus = 0
    if ratio >= 1.5:
        bonus = 2
    elif ratio >= 1.0:
        bonus = 1
    elif ratio < 0.5:
        bonus = -1
    return max(1, cfg["base_lives"] + bonus)


def _sequence(rounds: int, rng: random.Random) -> list[str]:
    """دنباله‌ی تلگراف‌ها: هر ۴ حرکت حداقل یه بار می‌آد و هیچ حرکتی سه‌بار پشتِ‌هم تکرار نمی‌شه."""
    keys = list(MOVES)
    while True:
        seq = [rng.choice(keys) for _ in range(rounds)]
        if len(set(seq)) < len(keys):
            continue
        if any(seq[i] == seq[i + 1] == seq[i + 2] for i in range(len(seq) - 2)):
            continue
        return seq


def start_battle(player: dict, trial_id: str, player_cp: int, rec_cp: int, rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    cfg = TRIAL_BATTLES[trial_id]
    lives = lives_for(trial_id, player_cp, rec_cp)
    sess = {
        "sid": f"{rng.randrange(16**5):05x}",
        "trial": trial_id,
        "seq": _sequence(cfg["rounds"], rng),
        "i": 0,
        "lives": lives,
        "max_lives": lives,
        "hits": 0,          # جوابِ درست
        "t0": time.time(),
        "peeks": 0,
    }
    player["trial_battle"] = sess
    return sess


def _lose_round(sess: dict):
    sess["lives"] -= 1


def settle(player: dict) -> dict | None:
    """
    دورهای تایم‌اوت‌شده رو اشتباه حساب می‌کنه. اگه نبرد تموم شد
    {"done": True, "success": bool, "trial": id, "hits":, "rounds":} برمی‌گردونه (و session رو پاک می‌کنه).
    """
    sess = player.get("trial_battle")
    if not sess:
        return None
    cfg = TRIAL_BATTLES[sess["trial"]]
    now = time.time()
    n = len(sess["seq"])
    while sess["i"] < n and sess["lives"] > 0:
        deadline = sess["t0"] + cfg["secs"] + GRACE_SECS
        if now <= deadline:
            return None
        _lose_round(sess)
        sess["i"] += 1
        sess["t0"] = sess["t0"] + cfg["secs"]
    success = sess["lives"] > 0
    out = {"done": True, "success": success, "trial": sess["trial"], "hits": sess["hits"], "rounds": n,
           "lives": max(0, sess["lives"]), "max_lives": sess["max_lives"]}
    player["trial_battle"] = None
    return out


def answer(player: dict, sid: str, i: int, counter: str) -> tuple[str | None, dict | None]:
    """
    جوابِ یه دور. برمی‌گردونه (پیامِ خطا یا None, نتیجه‌ی نهایی یا None).
    نتیجه‌ی هر دور عمداً مخفی نمی‌مونه: بازیکن فوراً می‌فهمه درست بوده یا نه.
    """
    fin = settle(player)
    if fin is not None:
        return None, fin
    sess = player.get("trial_battle")
    if not sess or sess["sid"] != sid or sess["i"] != i:
        return "⚠️ این دور دیگه فعال نیست.", None
    if counter not in COUNTERS:
        return "⚠️ حرکتِ نامعتبر.", None

    cfg = TRIAL_BATTLES[sess["trial"]]
    move = sess["seq"][sess["i"]]
    correct = cfg["rules"][move] == counter
    if correct:
        sess["hits"] += 1
    else:
        _lose_round(sess)
    sess["i"] += 1
    sess["t0"] = time.time()
    sess["last"] = {"ok": correct, "move": move, "right": cfg["rules"][move]}

    n = len(sess["seq"])
    if sess["lives"] <= 0 or sess["i"] >= n:
        success = sess["lives"] > 0
        out = {"done": True, "success": success, "trial": sess["trial"], "hits": sess["hits"], "rounds": n,
               "lives": max(0, sess["lives"]), "max_lives": sess["max_lives"], "last": sess["last"]}
        player["trial_battle"] = None
        return None, out
    return None, None


def rules_text(trial_id: str) -> str:
    cfg = TRIAL_BATTLES[trial_id]
    lines = [f"{MOVES[m].split(' ', 1)[0]}→{COUNTERS[c]}" for m, c in cfg["rules"].items()]
    return " | ".join(lines)


def rules_full(trial_id: str) -> str:
    cfg = TRIAL_BATTLES[trial_id]
    lines = [f"• {MOVES[m]} ← جوابِ درست: {COUNTERS[c]}" for m, c in cfg["rules"].items()]
    return "\n".join(lines)


def briefing(trial_id: str, trial_name: str, player_cp: int, rec_cp: int) -> str:
    cfg = TRIAL_BATTLES[trial_id]
    lives = lives_for(trial_id, player_cp, rec_cp)
    return (
        f"⚡ **{trial_name}**\n"
        f"👹 باس: {cfg['boss']}\n\n"
        f"📜 **قوانینِ این باس (حفظ کن!):**\n{rules_full(trial_id)}\n\n"
        f"• {cfg['rounds']} دور، هر دور **{cfg['secs']} ثانیه** وقت داری\n"
        f"• هر اشتباه یا تایم‌اوت = یه جان از دست می‌ره\n"
        f"• ❤️ جان‌های تو: **{lives}** (Combat Power {player_cp:,} از {rec_cp:,}ی که پیشنهاد می‌شه)\n"
        f"• جان تموم بشه = شکست؛ تا آخرِ دورها زنده بمونی = قبول\n"
        f"• هیچ شانسی تو نتیجه نیست — فقط مهارتِ خودت\n"
    )


def view(player: dict) -> dict | None:
    """متنِ دورِ فعلی. اگه نبردی نیست None."""
    sess = player.get("trial_battle")
    if not sess:
        return None
    cfg = TRIAL_BATTLES[sess["trial"]]
    i = sess["i"]
    move = sess["seq"][i]
    left = max(0, int(sess["t0"] + cfg["secs"] - time.time()))
    hearts = "❤️" * sess["lives"] + "🖤" * (sess["max_lives"] - sess["lives"])
    last = sess.get("last")
    prefix = ""
    if last is not None and i > 0:
        prefix = ("✅ دورِ قبل درست بود!\n" if last["ok"] else "❌ دورِ قبل اشتباه بود!\n")
    text = (
        f"{prefix}⚡ **دورِ {i + 1}/{len(sess['seq'])}** — {cfg['boss']}\n"
        f"{hearts} | ⏱ {left} ثانیه\n\n"
        f"{MOVES[move]}!\n\nچی کار می‌کنی؟"
    )
    return {"sid": sess["sid"], "i": i, "text": text, "trial": sess["trial"]}
