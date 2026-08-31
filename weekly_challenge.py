# ============================================================
#  ASTRAL ABYSS RPG — Weekly Challenge (rotating competitive event)
#  (weekly_challenge.py)
# ============================================================
# هر هفته یه معیارِ رقابتیِ متفاوت و کلاس‌محایدِ فعاله (بینِ همه‌ی
# کلاس‌ها منصفانه‌ست، چون رویِ متریک‌های همیشه‌فعالِ همه‌ی بازیکنا
# حساب می‌شه، نه رویِ منابعِ مخصوصِ یه کلاس). امتیازِ هر بازیکن یعنی
# «چقدر از شروعِ این هفته اضافه کرده» — یه snapshot از مقدارِ
# لحظه‌ی شروعِ هفته گرفته می‌شه و امتیاز = مقدارِ الان منهایِ اون.
#
# ریست/چرخشِ هفتگی از همون حلقه‌ی weekly_rewards.py صدا زده می‌شه
# (همون سیکلِ ۷روزه‌ای که رده‌بندیِ کلی و فصلِ PvP رو هم ریست می‌کنه)
# — یه حلقه‌ی asyncio جدا لازم نیست.
# ============================================================
from database import system_col

CHALLENGE_TYPES = [
    {
        "id": "slayer", "emoji": "🗡", "label_fa": "شکارچیِ هفته",
        "desc_fa": "بیشترین تعدادِ دشمنِ کشته‌شده (هر نقشه‌ای)",
        "metric": lambda p: sum((p.get("kill_log") or {}).values()),
    },
    {
        "id": "duelist", "emoji": "🆚", "label_fa": "دوئلیستِ هفته",
        "desc_fa": "بیشترین پیروزیِ PvP",
        "metric": lambda p: p.get("pvp_wins", 0),
    },
    {
        "id": "gambler", "emoji": "🎰", "label_fa": "قماربازِ هفته",
        "desc_fa": "بیشترین حجمِ شرط‌بندیِ کازینو",
        "metric": lambda p: p.get("casino_total_wagered", 0),
    },
    {
        "id": "explorer", "emoji": "🗺", "label_fa": "کاوشگرِ هفته",
        "desc_fa": "بیشترین دخمه‌ی پاک‌شده",
        "metric": lambda p: (p.get("class_system_data") or {}).get("dungeons_cleared", 0),
    },
]

TOP_REWARDS_ZEN = [50_000, 25_000, 10_000]   # نفر ۱/۲/۳
PARTICIPATION_ZEN = 2_000                     # نفراتِ ۴ تا ۱۰


def _meta() -> dict:
    return system_col().find_one({"_id": "weekly_challenge_meta"}) or {"_id": "weekly_challenge_meta", "index": 0}


def get_current_challenge() -> dict:
    idx = _meta().get("index", 0)
    return CHALLENGE_TYPES[idx % len(CHALLENGE_TYPES)]


def _current_week_tag() -> str:
    return str(_meta().get("index", 0))


def ensure_baseline(player: dict) -> bool:
    """اگه بازیکن هنوز snapshotِ این هفته رو نداره (بازیکنِ جدید یا کسی
    که هفته‌ی چرخش رو از دست داده)، پایه رو همین الان می‌ذاره.
    True برمی‌گردونه اگه چیزی تغییر کرد (یعنی caller باید save کنه)."""
    tag = _current_week_tag()
    if player.get("weekly_challenge_week_id") == tag:
        return False
    challenge = get_current_challenge()
    player["weekly_challenge_week_id"] = tag
    player["weekly_challenge_snapshot"] = challenge["metric"](player)
    return True


def challenge_score(player: dict) -> int:
    tag = _current_week_tag()
    if player.get("weekly_challenge_week_id") != tag:
        return 0  # هنوز پایه‌ای براش ثبت نشده → این هفته صفر
    challenge = get_current_challenge()
    return max(0, challenge["metric"](player) - player.get("weekly_challenge_snapshot", 0))


def leaderboard_text(players: dict) -> str:
    challenge = get_current_challenge()
    ranked = sorted(players.values(), key=challenge_score, reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = [
        f"{challenge['emoji']} **چالشِ این هفته: {challenge['label_fa']}**\n"
        f"_{challenge['desc_fa']}_\n",
    ]
    if not ranked or challenge_score(ranked[0]) == 0:
        lines.append("هنوز کسی امتیازی تو این چالش نگرفته — شروع کن!")
        return "".join(lines)
    for i, p in enumerate(ranked):
        score = challenge_score(p)
        if score <= 0:
            break
        lines.append(f"{medals[i]} **{p.get('name','—')}** — {score:,} امتیاز | Lv.{p.get('level',1)}\n")
    lines.append(f"\n🎁 جایزه‌ی پایانِ هفته: نفر ۱-۳ تا {TOP_REWARDS_ZEN[0]:,} Zen، نفر ۴-۱۰ هرکدوم {PARTICIPATION_ZEN:,} Zen.")
    return "".join(lines)


def player_progress_text(player: dict) -> str:
    challenge = get_current_challenge()
    score = challenge_score(player)
    return (
        f"{challenge['emoji']} **{challenge['label_fa']}**\n"
        f"_{challenge['desc_fa']}_\n\n"
        f"📊 امتیازِ تو این هفته: **{score:,}**"
    )


# ─── چرخش/ریست هفتگی — از weekly_rewards.py صدا زده می‌شه ─────
async def rotate_and_reward(bot, players: dict) -> None:
    from database import asave_player

    old_challenge = get_current_challenge()

    # ۱) جایزه‌دادن بر اساسِ چالشِ هفته‌ای که الان داره تموم می‌شه
    ranked = [(uid_str, p) for uid_str, p in players.items() if challenge_score(p) > 0]
    ranked.sort(key=lambda kv: challenge_score(kv[1]), reverse=True)

    for i, (uid_str, p) in enumerate(ranked[:10]):
        uid = int(uid_str)
        reward = TOP_REWARDS_ZEN[i] if i < 3 else PARTICIPATION_ZEN
        p["zen"] = p.get("zen", 0) + reward
        await asave_player(uid, p)
        if i < 3:
            try:
                await bot.send_message(
                    uid,
                    f"{old_challenge['emoji']} **پایانِ چالشِ «{old_challenge['label_fa']}»!**\n"
                    f"رتبه‌ی #{i+1} شدی — {challenge_score(p):,} امتیاز.\n"
                    f"🎁 جایزه: +{reward:,} Zen"
                )
            except Exception:
                pass
            if i == 0:
                try:
                    from social_feed import broadcast_achievement
                    await broadcast_achievement(
                        f"🏁 **{p.get('name','یه بازیکن')}** قهرمانِ چالشِ «{old_challenge['emoji']} "
                        f"{old_challenge['label_fa']}» این هفته شد! ({challenge_score(p):,} امتیاز) 🎉"
                    )
                except Exception:
                    pass

    # ۲) چرخشِ چالشِ هفته‌ی بعد + ریستِ پایه‌ی همه (snapshot جدید = مقدارِ الان)
    meta = _meta()
    new_idx = meta.get("index", 0) + 1
    system_col().update_one({"_id": "weekly_challenge_meta"}, {"$set": {"index": new_idx}}, upsert=True)
    new_challenge = CHALLENGE_TYPES[new_idx % len(CHALLENGE_TYPES)]
    new_tag = str(new_idx)

    for uid_str, p in players.items():
        p["weekly_challenge_week_id"] = new_tag
        p["weekly_challenge_snapshot"] = new_challenge["metric"](p)
        await asave_player(int(uid_str), p)
