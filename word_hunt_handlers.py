# ============================================================
#  ASTRAL ABYSS — Word Hunt (شکار با کلمه)
# ------------------------------------------------------------
#  فقط توی گروه‌ها/سوپرگروه‌ها. ۹ کلمه‌ی محرک، ۴ سطحِ نتیجه، سینرژیِ
#  کلاس، ریسکِ واقعیِ HP — و این نسخه دیگه یه جزیره‌ی جدا نیست:
#  مستقیم به سیستم‌های خودِ بازی وصله:
#
#   ⚡ World Pulse   → اگه ضربانِ فعالِ جهان (world_pulse.py) روی XP/Zen
#                       اثر بذاره (مثلاً «طنینِ آبیس» یا «فسادِ گسترش‌یابنده»)،
#                       دقیقاً همون ضریب اینجا هم اعمال می‌شه + اسمِ
#                       ضربان تو پیام نشون داده می‌شه.
#   🏛 Guild Perks   → پرک‌های گیلد (zen_gain_pct/xp_gain_pct) و بافِ
#                       جنگِ گیلدها (get_war_xp_buff) — دقیقاً همون
#                       چیزی که mob_combat موقعِ شکارِ عادی حساب می‌کنه.
#   🐾 Pet XP        → همراهِ فعال هم از هر شکار سهم می‌گیره (add_pet_xp)؛
#                       اگه لول‌آپ/تکامل کنه همینجا نشون داده می‌شه.
#   🏅 Achievements  → بعد از هر شکار check_achievements صدا زده می‌شه؛
#                       عنوانِ جدید (اگه باز شد) همینجا اعلام می‌شه.
#   👑 Titles        → تو بنرِ افسانه‌ای، به‌جای اسمِ خام، عنوانِ فعالِ
#                       بازیکن (get_active_title) نشون داده می‌شه، اگه داشته باشه.
#
#  سطح‌های نتیجه: ❌ شکست (فقط کمین/نفوذ، کمی HP هم می‌گیره) →
#  ⚪ عادی → 💥 خوب (کریت) → 🌟 افسانه‌ای (نادر، بنرِ گروهی).
#
#  کلمه‌ها + سینرژیِ کلاس:
#     شکار (متعادل) · حمله (Zen-heavy) · کمین[Adventurer] (ریسکی)
#     غارت[Merchant] (بیشترین آیتم) · ردیابی (کم‌ریسک) · رصد[Healer] (امن‌ترین)
#     نفوذ[Wizard] (پرریسک/پرسود) · تسخیر (اولتیمیت، کول‌داون ۳۰د)
#     محاصره (اولتیمیتِ دوم، کول‌داون ۴۵د)
#
#  + Streak (کمبوی پشتِ‌سرِهم) + مایل‌استونِ تعداد دفعاتِ هر کلمه
#    (۱۰/۵۰/۱۰۰/۲۵۰ بار → فقط یه پیامِ افتخاری، بدون تاثیرِ عددی).
#
#  همه‌چی هماهنگ با anti_farm.py (سقفِ روزانه، لاگِ مشکوک) — دقیقاً
#  همون مسیری که mob_combat می‌ره.
#
#  نصب: از قبل تو bot.py وصل شده. فقط همین فایل رو ویرایش کن.
# ============================================================
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from database import aget_player, asave_player
from logger import log_sync

# ─── سینرژیِ کلاس: word → class_id ────────────────────────────
CLASS_SYNERGY = {
    "کمین": "adventurer",
    "غارت": "merchant",
    "رصد": "healer",
    "نفوذ": "wizard",
}
SYNERGY_BONUS_MULT = 1.25
SYNERGY_FAIL_MULT = 0.5

MILESTONES = [10, 50, 100, 250, 500]

# ─── تنظیمات هر کلمه ─────────────────────────────────────────
WORD_ACTIONS = {
    "شکار": {
        "xp": (4, 9), "zen": (15, 35),
        "crit_chance": 0.12, "legendary_chance": 0.010,
        "fail_chance": 0.0, "item_chance": 0.03, "equip_chance": 0.0,
        "flavors": [
            "🏹 یه سایه رو تو تاریکی زدی!",
            "🗡 ضربه‌ی سریع — یه موجود ضعیف رو زمین زدی.",
            "🌑 یه چیزی تو Abyss تکون خورد... و دیگه تکون نمی‌خوره.",
            "⚔️ شکار موفق. یه قدم به جلو.",
            "🩸 خون روی خاک — شکار انجام شد.",
            "🐾 ردِ پا رو گم کردی ولی خودِ شکار رو نه.",
            "🌫 از دلِ مه یه شکارِ کوچیک بیرون کشیدی.",
        ],
    },
    "حمله": {
        "xp": (2, 5), "zen": (22, 45),
        "crit_chance": 0.10, "legendary_chance": 0.008,
        "fail_chance": 0.0, "item_chance": 0.02, "equip_chance": 0.0,
        "flavors": [
            "💢 یورشِ ناگهانی — طرف مقابل حتی نفهمید چی شد.",
            "🔥 حمله‌ی مستقیم، بدونِ رحم.",
            "⚡️ یه ضربه‌ی خشن که فقط غنیمت مهمه، نه تجربه.",
            "🗡 حمله‌ی خونین برای سود سریع.",
            "💥 خاک به پا شد؛ کیفت سنگین‌تر شد.",
            "🩸 حمله‌ای که فقط یه چیز می‌خواست: غنیمت.",
        ],
    },
    "کمین": {
        "xp": (7, 14), "zen": (8, 20),
        "crit_chance": 0.22, "legendary_chance": 0.018,
        "fail_chance": 0.12, "item_chance": 0.05, "equip_chance": 0.0,
        "flavors": [
            "🌑 تو سایه منتظر موندی... و لحظه‌ی درست رسید.",
            "🕸 کمینِ بی‌صدا — طعمه حتی متوجه نشد.",
            "🎯 صبر کردی، ضربه زدی، رفتی.",
            "🌙 شبانه، بی‌صدا، مؤثر.",
            "🦉 یه کمینِ حرفه‌ای — کارِ یه شکارچیِ واقعی.",
        ],
        "fail_flavors": [
            "🙈 صبر کردی ولی طعمه بو برد و فرار کرد.",
            "😮‍💨 کمین لو رفت — دست‌خالی موندی.",
            "🥀 این‌بار شانس باهات نبود؛ کمین شکست خورد.",
        ],
        "fail_hp_pct": (0.02, 0.05),
    },
    "غارت": {
        "xp": (1, 4), "zen": (10, 20),
        "crit_chance": 0.08, "legendary_chance": 0.010,
        "fail_chance": 0.0, "item_chance": 0.12, "equip_chance": 0.0,
        "flavors": [
            "🎒 یه کوله‌ی رهاشده رو گشتی و چیزی پیدا کردی.",
            "📦 غنیمتِ کوچیک ولی همیشه یه‌چیزی هست.",
            "🗝 قفلِ یه صندوقچه‌ی کوچیک رو باز کردی.",
            "🕳 تو خرابه‌ها دنبالِ باقی‌مونده گشتی.",
            "💼 دستِ خالی برنگشتی.",
            "🏺 یه ظرفِ قدیمی، پر از چیزهای کوچیک ولی باارزش.",
        ],
    },
    "ردیابی": {
        "xp": (5, 8), "zen": (12, 18),
        "crit_chance": 0.06, "legendary_chance": 0.005,
        "fail_chance": 0.0, "item_chance": 0.04, "equip_chance": 0.0,
        "flavors": [
            "🧭 ردِ پا رو دنبال کردی، دقیق و بی‌عجله.",
            "👣 ردیابیِ حرفه‌ای — نتیجه‌ی تضمینی.",
            "🗺 مسیر رو خوب خوندی.",
            "🔍 با دقت گشتی، با دقت هم پیدا کردی.",
        ],
    },
    "رصد": {
        "xp": (2, 4), "zen": (5, 10),
        "crit_chance": 0.04, "legendary_chance": 0.002,
        "fail_chance": 0.0, "item_chance": 0.01, "equip_chance": 0.0,
        "flavors": [
            "👁 از دور دیدی، یادداشت کردی، برگشتی.",
            "🔭 رصدِ آروم ولی مطمئن.",
            "🌫 چیزِ خاصی نبود، ولی هر تجربه‌ای حساب می‌شه.",
            "🧊 یه رصدِ ساده، بدون ریسک.",
        ],
    },
    "نفوذ": {
        "xp": (8, 16), "zen": (25, 55),
        "crit_chance": 0.18, "legendary_chance": 0.022,
        "fail_chance": 0.18, "item_chance": 0.06, "equip_chance": 0.03,
        "flavors": [
            "🕶 از لای سایه‌ها رد شدی، کسی ندید.",
            "🗝 نفوذِ خاموش — غنیمتِ بزرگ، بدونِ سروصدا.",
            "🌘 عمیق‌تر از همیشه پیش رفتی.",
            "🖤 نفوذِ خطرناک ولی به‌شدت پرسود.",
        ],
        "fail_flavors": [
            "🚨 لو رفتی و مجبور شدی فرار کنی — دست‌خالی.",
            "😰 نفوذ شکست خورد؛ به‌سختی جون سالم به در بردی.",
            "🔒 دری که دنبالش بودی قفل موند.",
        ],
        "fail_hp_pct": (0.04, 0.08),
    },
    "تسخیر": {
        "xp": (20, 35), "zen": (80, 150),
        "crit_chance": 0.15, "legendary_chance": 0.05,
        "fail_chance": 0.0, "item_chance": 0.15, "equip_chance": 0.10,
        "special_cooldown": 1800,
        "flavors": [
            "👑 تسخیرِ کامل — این یکی بزرگ بود.",
            "🏴 پرچمت رو زدی؛ اینجا مالِ توئه.",
            "⚜️ یه فتحِ واقعی، نه یه شکارِ ساده.",
        ],
    },
    "محاصره": {
        "xp": (30, 50), "zen": (120, 220),
        "crit_chance": 0.15, "legendary_chance": 0.08,
        "fail_chance": 0.0, "item_chance": 0.18, "equip_chance": 0.15,
        "special_cooldown": 2700,
        "flavors": [
            "🏰 دیوارها فرو ریختن — محاصره به ثمر نشست.",
            "🔥 شهر افتاد. غنیمتِ بی‌سابقه.",
            "🐺 یه محاصره‌ی تمام‌عیار — کسی جلودارت نبود.",
        ],
    },
}

TRIGGER_WORDS = set(WORD_ACTIONS.keys())

COOLDOWN_SECONDS = 8
CRIT_MULT = 2.0
LEGENDARY_MULT = 5.0

LEGENDARY_BANNERS = [
    "🌟━━━━━━━━━━━━━━━━━━━━🌟\n     ✨ **نتیجه‌ی افسانه‌ای!** ✨\n🌟━━━━━━━━━━━━━━━━━━━━🌟",
    "👑━━━━━━━━━━━━━━━━━━━━👑\n   یه لحظه‌ی به‌یادموندنی تو Abyss\n👑━━━━━━━━━━━━━━━━━━━━👑",
]
LEGENDARY_FLAVORS = [
    "چیزی که خیلی به‌ندرت پیش میاد.",
    "انگار خودِ Abyss طرفِ تو بود.",
    "یه غنیمتِ کاملاً استثنایی.",
]

STREAK_WINDOW = 20
STREAK_STEP = 0.04
STREAK_CAP_STEPS = 8

_hunt_state: dict[int, dict] = {}
_special_cd: dict[tuple, float] = {}


def _normalize(text: str) -> str:
    return (text or "").strip()


def _fmt_remaining(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m} دقیقه و {s} ثانیه" if m else f"{s} ثانیه"


async def handle_word_hunt(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    word = _normalize(message.text)
    action = WORD_ACTIONS.get(word)
    if not action:
        return

    uid = message.from_user.id
    now = time.time()

    special_cd = action.get("special_cooldown")
    if special_cd:
        last_special = _special_cd.get((uid, word), 0)
        remaining = special_cd - (now - last_special)
        if remaining > 0:
            try:
                await message.reply(f"⏳ «{word}» هنوز آماده نیست — {_fmt_remaining(remaining)} دیگه صبر کن.")
            except Exception:
                pass
            return

    state = _hunt_state.get(uid, {"t": 0, "streak": 0})
    remaining = COOLDOWN_SECONDS - (now - state["t"])
    if remaining > 0:
        return

    player = await aget_player(uid)
    if not player:
        return

    if special_cd:
        _special_cd[(uid, word)] = now

    if now - state["t"] <= STREAK_WINDOW:
        streak = min(state["streak"] + 1, STREAK_CAP_STEPS)
    else:
        streak = 1
    _hunt_state[uid] = {"t": now, "streak": streak}
    streak_mult = 1 + (streak - 1) * STREAK_STEP

    import anti_farm as af
    from guild_system import get_perk
    import async_bridge as bridge

    # ─── سینرژیِ کلاس ─────────────────────────────────────────
    is_synergy = CLASS_SYNERGY.get(word) == player.get("class")
    synergy_mult = SYNERGY_BONUS_MULT if is_synergy else 1.0
    fail_chance = action.get("fail_chance", 0) * (SYNERGY_FAIL_MULT if is_synergy else 1.0)

    # ─── نتیجه ────────────────────────────────────────────────
    roll = random.random()
    legendary_chance = action.get("legendary_chance", 0)
    crit_chance = action.get("crit_chance", 0)
    if roll < fail_chance:
        tier = "fail"
    elif roll < fail_chance + legendary_chance:
        tier = "legendary"
    elif roll < fail_chance + legendary_chance + crit_chance:
        tier = "crit"
    else:
        tier = "normal"

    xp_gain = random.randint(*action["xp"])
    zen_gain = random.randint(*action["zen"])

    if tier == "fail":
        xp_gain = max(1, int(xp_gain * 0.15))
        zen_gain = max(1, int(zen_gain * 0.15))
    elif tier == "crit":
        xp_gain = int(xp_gain * CRIT_MULT)
        zen_gain = int(zen_gain * CRIT_MULT)
    elif tier == "legendary":
        xp_gain = int(xp_gain * LEGENDARY_MULT)
        zen_gain = int(zen_gain * LEGENDARY_MULT)

    # ─── پرکِ گیلد + بافِ جنگِ گیلدها (دقیقاً مثلِ mob_combat) ────
    guild_zen_bonus = af.cap_bonus(get_perk(player, "zen_gain_pct"))
    guild_xp_bonus = af.cap_bonus(get_perk(player, "xp_gain_pct") + await bridge.guild_system.get_war_xp_buff(player))

    # ─── World Pulse (ضربانِ زنده‌ی جهان) ───────────────────────
    pulse_xp_mult = await bridge.world_pulse.pulse_value("xp_mult")
    pulse_zen_mult = await bridge.world_pulse.pulse_value("zen_mult")
    active_pulse = await bridge.world_pulse.get_active_pulse()

    xp_gain = int(xp_gain * streak_mult * synergy_mult * (1 + guild_xp_bonus) * pulse_xp_mult)
    zen_gain = int(zen_gain * streak_mult * synergy_mult * (1 + guild_zen_bonus) * pulse_zen_mult)

    zen_gain = max(1, int(zen_gain * af.daily_mult(player, "zen")))
    xp_gain = max(1, int(xp_gain * af.daily_mult(player, "xp")))

    player["xp"] = player.get("xp", 0) + xp_gain
    player["zen"] = player.get("zen", 0) + zen_gain

    # ─── ریسکِ واقعی: شکست تو کلمه‌های خطرناک کمی HP می‌گیره ────
    hp_lost = 0
    if tier == "fail" and "fail_hp_pct" in action:
        pct = random.uniform(*action["fail_hp_pct"])
        max_hp = player.get("max_hp", player.get("hp", 100))
        hp_lost = max(1, int(max_hp * pct))
        player["hp"] = max(1, player.get("hp", max_hp) - hp_lost)

    # ─── آیتم/تجهیزات ─────────────────────────────────────────
    got_item = None
    if tier != "fail":
        mult = 2 if tier == "legendary" else 1
        equip_chance = action.get("equip_chance", 0) * mult
        item_chance = action.get("item_chance", 0) * mult
        if equip_chance and random.random() < equip_chance:
            from item_system import generate_random_equipment
            got_item = generate_random_equipment(player.get("level", 1), drop_source=f"word_hunt:{word}")
            player.setdefault("inventory", []).append(got_item)
        elif random.random() < item_chance:
            from item_system import generate_consumable
            got_item = generate_consumable(player.get("level", 1))
            player.setdefault("inventory", []).append(got_item)

    # ─── سهمِ همراه (Pet) از XP — دقیقاً مثلِ مبارزه‌ی معمولی ────
    from pet_system import add_pet_xp
    pet_levelup = add_pet_xp(player, xp_gain)

    # ─── شمارشگرِ مایل‌استون (فقط افتخاری، بدون اثرِ عددی) ──────
    counts = player.setdefault("word_hunt_counts", {})
    counts[word] = counts.get(word, 0) + 1
    milestone_hit = counts[word] if counts[word] in MILESTONES else None

    af.register_daily_gain(player, "zen", zen_gain)
    af.register_daily_gain(player, "xp", xp_gain)
    af.log_if_suspicious(uid, player.get("name", "—"), zen_gain, xp_gain, f"word_hunt:{word}:{tier}")
    af.register_action_time(player, uid, player.get("name", "—"), "word_hunt")

    from bot import level_up_check
    player, leveled = level_up_check(player)

    from achievements import check_achievements
    new_titles = check_achievements(player)

    await asave_player(uid, player)

    # ─── متن پاسخ ─────────────────────────────────────────────
    if tier == "fail":
        line = random.choice(action.get("fail_flavors", ["😮‍💨 این‌بار جواب نداد."]))
    else:
        line = random.choice(action["flavors"])

    tag = " 💥 **ضربه‌ی خوب!**" if tier == "crit" else ""
    synergy_txt = " 🔮" if is_synergy else ""
    streak_txt = f" 🔗 x{streak}" if streak > 1 and tier != "fail" else ""

    body = f"{line}{tag}{synergy_txt}\n✨ +{xp_gain} XP | 💰 +{zen_gain} BZ{streak_txt}"

    if active_pulse and (pulse_xp_mult != 1 or pulse_zen_mult != 1):
        body += f"\n⚡ ضربانِ فعال: {active_pulse.get('name','?')}"
    if hp_lost:
        body += f"\n💔 -{hp_lost} HP"
    if got_item:
        body += f"\n🎁 آیتم پیدا کردی: {got_item.get('emoji','🎁')} {got_item.get('name','?')}"
    if pet_levelup:
        if pet_levelup.get("evolved"):
            body += f"\n🐾✨ **{pet_levelup['emoji']} {pet_levelup['name']} تکامل پیدا کرد!** حالا {pet_levelup['evolution_label']}ه (سطح {pet_levelup['level']})"
        else:
            body += f"\n🐾 {pet_levelup['emoji']} **{pet_levelup['name']}** به سطح {pet_levelup['level']} رسید!"
    if milestone_hit:
        body += f"\n🏆 {milestone_hit}اُمین بارِ «{word}»! دستت درد نکنه."
    for t in new_titles:
        body += f"\n🏅 **عنوان جدید باز شد: {t}**"
    if leveled:
        body += f"\n\n🎉 **LEVEL UP! → {player['level']}**"
        log_sync(f"⭐ **LEVEL UP (WORD HUNT)**\n👤 {player.get('name','—')} (`{uid}`)\n📊 سطح: {player['level']}", "LEVELUP")

    try:
        if tier == "legendary":
            from titles_system import get_active_title
            display_name = get_active_title(player) or player.get("name", message.from_user.first_name or "بازیکن")
            banner = random.choice(LEGENDARY_BANNERS)
            flavor = random.choice(LEGENDARY_FLAVORS)
            await message.answer(f"{banner}\n👤 **{display_name}** با کلمه‌ی «{word}» — {flavor}\n\n{body}")
            log_sync(f"🌟 LEGENDARY word_hunt: {player.get('name','—')} (`{uid}`) — {word}", "INFO")
        else:
            await message.reply(body)
    except Exception:
        pass


def register_word_hunt_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(
        handle_word_hunt,
        F.chat.type.in_({"group", "supergroup"}),
        F.text.in_(TRIGGER_WORDS),
    )
