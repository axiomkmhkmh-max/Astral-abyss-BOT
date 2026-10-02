# ============================================================
#  ASTRAL ABYSS — 🕳 غارتِ محفلِ سایه (Shadow Cabal Heist)
#  (shadow_cabal.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  یه فعالیتِ گروهی (تنها یا با پارتنرِ تیم): مهرِ یه محفلِ سایه رو
#  می‌شکنی، هرچی می‌تونی غارت می‌کنی، ولی هر آیتمی که برمی‌داری
#  «زنگِ خطر»ِ محفل رو بالا می‌بره — اگه قبل از رسیدنِ نگهبان‌ها فرار
#  نکنی، نصفِ غنیمت رو از دست می‌دی و برای مدتی «نشان‌دار» می‌شی.
#
#  طراحیِ عمدی: این «زنگِ خطر» کاملاً جدا و محلیِ همین فعالیته و به
#  گیجِ فسادِ جهانی (world_pulse) دست نمی‌زنه — فقط از فلیورش الهام
#  گرفته. رتبه‌ی بازارِ سیاه (bm_reputation) اگه بازیکن داشته باشه
#  به‌عنوانِ یه بونوسِ نرم (کاهشِ شانسِ گیرافتادن) استفاده می‌شه، ولی
#  هیچ‌وقت شرط نیست — همه‌ی کلاس‌ها می‌تونن انجامش بدن.
# ============================================================
from __future__ import annotations

import random
import time

LEVEL_REQUIRED = 8
COOLDOWN_SEC = 4 * 3600          # هر ۴ ساعت یه‌بار می‌شه شروع کرد
MARKED_SEC = 2 * 3600            # اگه گیر بیفتی، ۲ ساعت «نشان‌دار» می‌مونی
MAX_GRABS = 5                    # سقفِ تعدادِ برداشتن تو یه غارت
SEAL_OPTIONS = 3                 # تعدادِ نشانه‌های مهر (پازلِ ساده)

ALARM_ON_WRONG_SEAL = 15
ALARM_ON_CORRECT_SEAL = 5
ALARM_PER_GRAB = (12, 22)        # رنجِ رندومِ افزایشِ زنگِ خطر به‌ازای هر برداشتن

PARTNER_CATCH_REDUCTION = 8      # درصد — پارتنر مثلِ دیده‌بان عمل می‌کنه
REP_GAIN_ON_SUCCESS = 2

SIGIL_LABELS = ["🔺 نشانه‌ی الف", "🔷 نشانه‌ی ب", "⭐ نشانه‌ی ج"]

FLAVOR_ENTER = [
    "یه نشانه‌ی کم‌رنگِ سایه رو دیوارِ یه دخمه‌ی متروکه پیدا کردی...",
    "زمزمه‌ای از پشتِ یه در قدیمی می‌شنوی — یه محفلِ سایه اینجا مخفی شده.",
    "بوی گَردِ کهنه و جادوی سیاه از یه شکافِ دیوار میاد.",
]
FLAVOR_WRONG = [
    "نشانه سرد می‌مونه — انتخابِ اشتباه. یه چیزی تو تاریکی تکون خورد.",
    "مهر روشن نمی‌شه. صدای قدم‌های دوری به گوش می‌رسه.",
]
FLAVOR_CORRECT = "نشانه گرم می‌شه و مهر با یه صدای خفه باز می‌شه..."
FLAVOR_CAUGHT = "🚨 نگهبان‌های محفل رسیدن! نصفِ غنیمت جا موند و رَدَت رو زدن."
FLAVOR_ESCAPED = "🌙 درست قبل از رسیدنِ نگهبان‌ها، از سایه‌ها خارج شدی — غنیمت کاملاً مالِ توئه."


def get_state(player: dict) -> dict:
    return player.setdefault("shadow_cabal", {
        "last_run": 0, "marked_until": 0, "total_runs": 0, "total_success": 0,
        "session": None,
    })


def cooldown_remaining(player: dict) -> int:
    st = get_state(player)
    left = st["last_run"] + COOLDOWN_SEC - time.time()
    return max(0, int(left))


def marked_remaining(player: dict) -> int:
    st = get_state(player)
    left = st["marked_until"] - time.time()
    return max(0, int(left))


def can_start(player: dict) -> tuple[bool, str]:
    if player.get("level", 1) < LEVEL_REQUIRED:
        return False, f"❌ برای غارتِ محفلِ سایه به سطح {LEVEL_REQUIRED} نیاز داری."
    if marked_remaining(player) > 0:
        m = marked_remaining(player)
        return False, f"🔖 نگهبان‌ها هنوز حواسشون بهته — {m // 60} دقیقه‌ی دیگه صبر کن."
    if get_state(player).get("session"):
        return False, "⏳ یه غارتِ نیمه‌تموم داری — اول اونو تموم کن."
    cd = cooldown_remaining(player)
    if cd > 0:
        h, m = divmod(cd // 60, 60)
        return False, f"⏳ محفل‌ها هنوز مراقبن — {h} ساعت و {m} دقیقه‌ی دیگه دوباره امتحان کن."
    return True, ""


def start_heist(player: dict, partner_uid: int | None = None) -> dict:
    """یه جلسه‌ی جدید می‌سازه و رو خودِ player می‌شینه. برمی‌گردونه: session dict."""
    st = get_state(player)
    answer = random.randrange(SEAL_OPTIONS)
    session = {
        "started_at": time.time(),
        "stage": "seal",
        "seal_answer": answer,
        "seal_tries": [],
        "alarm": 0,
        "grabs": 0,
        "loot": [],          # لیستِ آیتم‌های تولیدشده (dict)
        "zen": 0,
        "partner_uid": partner_uid,
    }
    st["session"] = session
    st["last_run"] = time.time()
    st["total_runs"] = st.get("total_runs", 0) + 1
    return session


def try_seal(player: dict, choice_idx: int) -> dict:
    """یه انتخاب رو تست می‌کنه. برمی‌گردونه: {"correct": bool, "alarm": int, "done_tries": [...]}"""
    st = get_state(player)
    session = st["session"]
    session["seal_tries"].append(choice_idx)
    correct = (choice_idx == session["seal_answer"])
    if correct:
        session["alarm"] = min(100, session["alarm"] + ALARM_ON_CORRECT_SEAL)
        session["stage"] = "looting"
    else:
        session["alarm"] = min(100, session["alarm"] + ALARM_ON_WRONG_SEAL)
    return {"correct": correct, "alarm": session["alarm"], "tried": session["seal_tries"]}


def grab_loot(player: dict) -> dict:
    """یه برداشتنِ جدید: هم لوت تولید می‌کنه هم زنگِ خطر رو بالا می‌بره.
    برمی‌گردونه: {"item": dict|None, "zen": int, "alarm": int, "forced": bool, "grabs": int}"""
    from economy import roll_loot

    st = get_state(player)
    session = st["session"]
    session["grabs"] += 1

    zen_gain = random.randint(20, 45) * max(1, player.get("level", 1) // 2)
    session["zen"] += zen_gain

    loot = roll_loot(player.get("map", "Abyssal Black Market"), count=1, player_level=player.get("level", 1))
    item = loot[0] if loot else None
    if item:
        session["loot"].append(item)

    session["alarm"] = min(100, session["alarm"] + random.randint(*ALARM_PER_GRAB))
    forced = session["alarm"] >= 100 or session["grabs"] >= MAX_GRABS

    return {"item": item, "zen": zen_gain, "alarm": session["alarm"], "forced": forced, "grabs": session["grabs"]}


def resolve_escape(player: dict) -> dict:
    """جلسه رو می‌بنده و نتیجه‌ی نهایی رو تعیین می‌کنه (فرار موفق یا گیرافتادن).
    غنیمت/زن رو مستقیم به player اعمال می‌کنه. برمی‌گردونه دیکشنریِ نتیجه."""
    from item_system import merge_into_inventory

    st = get_state(player)
    session = st["session"]
    alarm = session["alarm"]

    try:
        from black_market_reputation import heat_reduction
        rep_reduction = heat_reduction(player) * 100  # 0..35 تقریباً
    except Exception:
        rep_reduction = 0.0

    partner_bonus = PARTNER_CATCH_REDUCTION if session.get("partner_uid") else 0
    catch_chance = max(0, alarm - rep_reduction - partner_bonus)
    caught = random.uniform(0, 100) < catch_chance

    loot = session["loot"]
    zen = session["zen"]

    if caught:
        keep_n = len(loot) // 2
        kept_loot = random.sample(loot, keep_n) if keep_n else []
        kept_zen = zen // 2
        st["marked_until"] = time.time() + MARKED_SEC
    else:
        kept_loot = loot
        kept_zen = zen
        st["total_success"] = st.get("total_success", 0) + 1
        player["bm_reputation"] = min(100, player.get("bm_reputation", 0) + REP_GAIN_ON_SUCCESS)

    for it in kept_loot:
        merge_into_inventory(player.setdefault("inventory", []), it)
    player["zen"] = player.get("zen", 0) + kept_zen

    partner_uid = session.get("partner_uid")
    st["session"] = None

    return {
        "caught": caught, "catch_chance": round(catch_chance, 1),
        "kept_loot": kept_loot, "kept_zen": kept_zen,
        "lost_loot": len(loot) - len(kept_loot), "lost_zen": zen - kept_zen,
        "partner_uid": partner_uid, "grabs": session["grabs"],
    }


def grant_partner_reward(partner_player: dict, kept_zen: int, got_loot: bool) -> dict:
    """پارتنر همون مقدار زن رو می‌گیره + (اگه غارت موفق بود) یه آیتمِ *مستقلِ*
    تازه‌تولیدشده (نه همون آبجکتِ بازیکنِ اصلی — تا آیدیِ آیتم تکراری نشه)."""
    from economy import roll_loot

    partner_player["zen"] = partner_player.get("zen", 0) + kept_zen
    item = None
    if got_loot:
        loot = roll_loot(partner_player.get("map", "Abyssal Black Market"), count=1,
                          player_level=partner_player.get("level", 1))
        if loot:
            from item_system import merge_into_inventory
            item = loot[0]
            merge_into_inventory(partner_player.setdefault("inventory", []), item)
    return {"zen": kept_zen, "item": item}
