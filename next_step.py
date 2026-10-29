# ============================================================
#  ASTRAL ABYSS — Next Step (راهنمای «الان چیکار کنم؟»)
# ------------------------------------------------------------
#  برای هر پلیر، تو هر لولی، دقیقاً «یک» کارِ پیشنهادی برمی‌گردونه.
#  خروجی: {"text": str, "action": key|None}
#  action ∈ attack|loot|story|hunt|ascend|heal|rest|status|None
# ============================================================
from __future__ import annotations


_FA = {"boss": "باس جهانی", "bounty": "شکار جایزه", "underground": "زیرزمین", "guilds": "گیلد",
       "team": "تیم", "pvp": "PvP", "trade": "معامله", "track": "ردیابی", "auction": "حراج",
       "casino": "کازینو", "shop": "مغازه", "contracts": "قراردادها", "house": "خانه",
       "mentor": "استاد", "exchange": "تبادل"}


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def suggest(player: dict) -> dict:
    import onboarding
    lvl = int(player.get("level", 1) or 1)

    # ۱) تیوتوریال
    if onboarding.is_in_tutorial(player):
        act = "loot" if player.get("tutorial_step") in (onboarding.STEP_FIRST_LOOT, onboarding.STEP_AWAIT_LOOT) else "attack"
        return {"text": onboarding.resume_text(player).replace("🧭 ", ""), "action": act}

    # ۲) HP پایین
    def _hp_low():
        from skill_tree import effective_max_hp
        return player.get("hp", 1) < 0.35 * effective_max_hp(player)
    if _try(_hp_low, False):
        locked = _try(lambda: __import__("combat_handlers").heal_locked(player), False)
        if locked:
            return {"text": "❤️ HP پایینه و درمان موقتاً قفله — کمی صبر کن، بعد دوباره بجنگ.", "action": None}
        return {"text": "❤️ HP پایینه — اول درمان شو، بعد بجنگ.", "action": "heal"}

    # ۳) خستگی
    if _try(lambda: __import__("combat_handlers").fatigue_level(player), 0) >= 1:
        return {"text": "😓 خسته‌ای (آمارت کم شده) — ۳۰ دقیقه استراحت کن.", "action": "rest"}

    # ۴) فصلِ جدیدِ داستان
    ch = _try(lambda: __import__("quest_engine").story_new_chapter_available(player))
    if ch:
        return {"text": f"📖 فصلِ جدیدِ داستان باز شده: «{ch['title']}». داستان بهت می‌گه بعدش کجا بری.",
                "action": "story"}

    # ۵) پاداشِ کوئستِ شکار آماده‌ست
    def _hunt():
        from hunt_questline import hunt_progress
        for q in hunt_progress(player):
            if q["claimable"]:
                return q
        return None
    hq = _try(_hunt)
    if hq:
        return {"text": f"🏹 پاداشِ «{hq['title']}» آماده‌ی دریافته!", "action": "hunt"}

    # ۶) آزمونِ صعود (معمولاً همون چیزیه که پلیرِ لولِ بالا بهش گیر می‌کنه)
    def _trial():
        import world_tiers as wt
        tid = wt.next_trial_for_player(player)
        if not tid:
            return None
        ok, why = wt.can_attempt_trial(player, tid)
        return wt.ASCENSION_TRIALS[tid]["name"], ok, why
    tr = _try(_trial)
    if tr:
        name, ok, why = tr
        if ok:
            return {"text": f"🌟 {name} آماده‌ست! رد کردنش تیرِ بعدیِ دنیا (مپ‌ها و دشمن‌های جدید) رو باز می‌کنه.",
                    "action": "ascend"}
        return {"text": f"🌟 {name}: {why}", "action": "status"}

    # ۷) نزدیک‌ترین قابلیتِ قفل
    def _unlock():
        from level_gate import LEVEL_REQUIREMENTS
        nxt = sorted((r, k) for k, r in LEVEL_REQUIREMENTS.items() if r > lvl)
        return nxt[0] if nxt else None
    un = _try(_unlock)

    # ۸) کوئستِ شکارِ در حال انجام
    def _hunt_hint():
        from hunt_questline import next_hunt_hint
        return next_hunt_hint(player)
    hh = _try(_hunt_hint)

    if lvl < 20 and un:
        r, k = un
        k = _FA.get(k, k)
        return {"text": f"⚔️ بجنگ و لول بگیر — {r - lvl} لول دیگه «{k}» باز می‌شه." + (f"\n{hh}" if hh else ""),
                "action": "attack"}
    if hh:
        return {"text": hh, "action": "attack"}
    return {"text": "🗺 لوت کن و بجنگ تا برای آزمونِ بعدی قوی‌تر بشی — «وضعیت» نشون می‌ده چقدر مونده.",
            "action": "loot"}
