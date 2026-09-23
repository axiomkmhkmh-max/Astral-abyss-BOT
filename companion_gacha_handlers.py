# ============================================================
#  ASTRAL ABYSS — همدم‌ها (Companion Gacha)
# ------------------------------------------------------------
#  قلبِ اصلیِ مکانیزمِ «میوبات-استایل»: هر بار /claim می‌زنی یه
#  کاراکترِ رندوم با یه پرتره‌ی AI-generated واقعی می‌گیری — بدونِ
#  هیچ API keyـی. عکس‌ها زنده از pollinations.ai (سرویسِ رایگانِ
#  متن‌به‌عکس، بدونِ نیاز به کلید) کشیده می‌شن.
#
#  چرا اعتیادآوره (طراحیِ عمدی):
#   1) کول‌داونِ کوتاه (۲۰ دقیقه) → دلیلِ برگشتنِ مکرر به بازی.
#   2) ۱۱ سطحِ نُدرت (از خودِ item_system، همون سیستمِ تجهیزات) →
#      همیشه یه شانسِ کوچیکِ «شاید این‌بار لژندری بیاد» هست.
#   3) کالکشن قابلِ‌دیدنه (/collection) → حسِ پیشرفت و کامل‌کردن.
#   4) هرکاراکتر منحصربه‌فرده (seed تصادفی) → حتی دو نسخه از یه
#      آرکی‌تایپ ظاهرِ یکسان ندارن.
#   5) تکراری‌ها بی‌فایده نمی‌مونن، تبدیل به «شاردِ همانند‌سازی»
#      می‌شن (یه ارزِ جدید که بعداً می‌شه براش فروشگاه ساخت) →
#      حتی نتیجه‌ی «بد» هم یه پاداشِ کوچیک داره.
#   6) سیستمِ «همدمِ محبوب» (favorite) → یه بونوسِ کوچیکِ همیشگی،
#      باعث می‌شه بازیکن به یه کاراکترِ خاص دلبسته بشه (دقیقاً
#      همون حسی که سیستمِ ازدواج/هارمِ میوبات می‌سازه).
#
#  نصب: تو bot.py کنارِ بقیه‌ی register_*_handlers اضافه کن:
#      from companion_gacha_handlers import register_companion_handlers
#      register_companion_handlers(dp, bot)
# ============================================================
import random
import time
import uuid
from urllib.parse import quote

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from database import aget_player, asave_player
from logger import log_sync
from item_system import RARITY_DATA, RARITY_ORDER, roll_rarity

# ─── آرکی‌تایپ‌های کاراکتر ────────────────────────────────────
# هر کدوم یه تمِ بصری/شخصیتیِ متفاوت دارن. prompt به انگلیسیه چون
# مدل‌های تصویرسازی روی پرامپتِ انگلیسی خیلی بهتر جواب می‌دن؛ توضیح
# و اسم برای خودِ بازیکن فارسیه.
ARCHETYPES = [
    {"id": "flame_lady",   "title": "بانوی شعله",      "element": "🔥",
     "prompt": "female warrior made of living fire, molten armor, glowing ember skin, flames flowing like hair, muscular battle-ready pose"},
    {"id": "frost_witch",  "title": "جادوگرِ یخ",       "element": "❄️",
     "prompt": "female ice sorceress, crystalline frozen armor, pale blue skin with frost cracks, glowing icy eyes, frozen breath mist"},
    {"id": "shadow_blade", "title": "شمشیرزنِ سایه",    "element": "🌑",
     "prompt": "female shadow assassin, obsidian armor, glowing purple veins, twin curved blades, smoke and darkness wrapping around body"},
    {"id": "storm_rider",  "title": "سوارِ طوفان",      "element": "⚡",
     "prompt": "female storm knight, lightning-charged battle armor, electricity crackling around body, silver hair whipping in wind, thunderclouds"},
    {"id": "abyss_priest", "title": "کاهنه‌یِ ابیس",     "element": "🌌",
     "prompt": "female cosmic priestess, void-black robes with glowing star patterns, floating runic symbols, deep space aura, third eye glowing"},
    {"id": "jade_ranger",  "title": "کماندارِ یشمی",    "element": "🌿",
     "prompt": "female forest ranger, living vine armor fused with skin, glowing green eyes, ancient wooden bow, moss and bioluminescent plants"},
    {"id": "gold_paladin", "title": "پالادینِ زرین",     "element": "✨",
     "prompt": "female holy paladin, ornate golden plate armor, radiant divine light emanating from body, massive sacred greatsword, cathedral light rays"},
    {"id": "crimson_rogue","title": "دزدِ سرخ",         "element": "🩸",
     "prompt": "female crimson rogue, blood-red tactical armor, scars and battle wounds, twin daggers dripping, rain-soaked dark alley, neon reflections"},
    {"id": "void_empress", "title": "ملکه‌یِ خلأ",      "element": "🕳️",
     "prompt": "female void empress, reality-warping black crown, skin like liquid darkness, gravity-defying fragments floating around her, cosmic horror elegance"},
    {"id": "sky_dancer",   "title": "رقصنده‌یِ آسمان",  "element": "🌤️",
     "prompt": "female sky guardian, massive feathered wings, wind-swept battle robes, standing on floating cloud platform, golden hour sunlight"},
    {"id": "war_oracle",   "title": "پیشگویِ جنگ",      "element": "🗡️",
     "prompt": "female war oracle, blood-red battle tattoos glowing, ornate war spear, standing on a battlefield under a blood moon, ash falling"},
    {"id": "star_alchemist","title": "کیمیاگرِ ستاره", "element": "🌠",
     "prompt": "female star alchemist, chrome and silver exosuit, floating alchemical rings of light, galaxy reflected in glass visor, nebula background"},
]
ARCHETYPE_BY_ID = {a["id"]: a for a in ARCHETYPES}

# ─── سبکِ رندرِ عکس — واقع‌گرایانه/سینمایی/سه‌بعدی، نه انیمه ────
RENDER_STYLE = (
    "hyper-realistic 3D character render, unreal engine 5, octane render, "
    "photorealistic skin and materials, cinematic lighting, ultra detailed, 8k, "
    "sharp focus, dramatic composition, video game key art"
)

# ─── تزئینِ بصریِ متناسب با نُدرت — روی همون پرامپت اضافه می‌شه ──
RARITY_VISUAL = {
    "common": "simple background, plain lighting",
    "uncommon": "soft studio lighting, clean background",
    "rare": "detailed environment, dynamic action pose",
    "epic": "glowing magical particle effects, dramatic rim lighting",
    "mythic": "intense elemental aura, volumetric fog, epic camera angle",
    "legendary": "golden glowing aura, majestic heroic pose, cinematic god rays",
    "ancient": "ancient stone ruins background, floating runes, powerful aura",
    "astral": "cosmic nebula background, galaxy particles, ethereal glow",
    "void": "reality distortion effect, dark energy swirl, glitch fragments",
    "celestial": "divine radiance, heavenly light beams, holy symbols",
    "transcendent": "godlike energy aura, reality-bending background, masterpiece, ultra premium render",
}

# ─── تبدیلِ تکراری به «شاردِ همانند‌سازی» بر اساسِ نُدرت ──────────
DUPE_SHARD_REWARD = {
    "common": 2, "uncommon": 4, "rare": 8, "epic": 15, "mythic": 25,
    "legendary": 45, "ancient": 80, "astral": 140, "void": 250,
    "celestial": 450, "transcendent": 800,
}

CLAIM_COOLDOWN = 20 * 60          # ۲۰ دقیقه
FAVORITE_ZEN_BONUS_PER_TIER = 0.01  # هر پله‌ی ندرتِ همدمِ محبوب: +۱٪ Zen

_last_claim: dict[int, float] = {}


def _build_image_url(prompt: str, seed: int) -> str:
    encoded = quote(prompt, safe="")
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=768&height=1024&seed={seed}&nologo=true&model=flux"
    )


async def _fetch_image(url: str) -> bytes | None:
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        log_sync(f"⚠️ companion image fetch failed: {e}", "WARN")
    return None


def _fmt_remaining(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m} دقیقه و {s} ثانیه" if m else f"{s} ثانیه"


async def cmd_claim(message: Message):
    uid = message.from_user.id
    now = time.time()

    remaining = CLAIM_COOLDOWN - (now - _last_claim.get(uid, 0))
    if remaining > 0:
        await message.reply(f"⏳ همدمِ بعدی هنوز آماده نیست — {_fmt_remaining(remaining)} دیگه صبر کن.")
        return

    player = await aget_player(uid)
    if not player:
        await message.reply("❌ اول باید بازی رو شروع کنی: /start")
        return

    _last_claim[uid] = now

    archetype = random.choice(ARCHETYPES)
    rarity = roll_rarity()
    rdata = RARITY_DATA[rarity]
    seed = random.randint(1, 2_000_000_000)
    visual = RARITY_VISUAL.get(rarity, "")
    full_prompt = f"{archetype['prompt']}, {RENDER_STYLE}, {visual}"
    image_url = _build_image_url(full_prompt, seed)

    wait_msg = await message.reply("🎴 در حالِ احضارِ همدم... چند لحظه صبر کن.")

    companions = player.setdefault("companions", {})
    existing = companions.get(archetype["id"])

    is_new = existing is None
    is_upgrade = False
    shard_reward = 0

    if is_new:
        companions[archetype["id"]] = {
            "rarity": rarity,
            "count": 1,
            "seed": seed,
            "claimed_at": now,
        }
    else:
        existing["count"] = existing.get("count", 1) + 1
        old_idx = RARITY_ORDER.index(existing.get("rarity", "common"))
        new_idx = RARITY_ORDER.index(rarity)
        if new_idx > old_idx:
            is_upgrade = True
            existing["rarity"] = rarity
            existing["seed"] = seed
        shard_reward = DUPE_SHARD_REWARD.get(rarity, 2)
        player["fusion_shards"] = player.get("fusion_shards", 0) + shard_reward

    await asave_player(uid, player)

    caption_lines = [
        f"{rdata['emoji']} **{rdata['label']}** — {archetype['element']} {archetype['title']}",
    ]
    if is_new:
        caption_lines.append("✨ همدمِ جدید به کالکشنت اضافه شد!")
    elif is_upgrade:
        caption_lines.append(f"⬆️ ارتقا! نسخه‌ی بهترِ این همدم رو گرفتی.")
    else:
        caption_lines.append(f"🔁 تکراری بود — به‌جاش **{shard_reward} شاردِ همانند‌سازی** گرفتی.")
    caption_lines.append(f"\n💠 مجموع شاردهات: {player.get('fusion_shards', 0):,}")
    caption = "\n".join(caption_lines)

    image_bytes = await _fetch_image(image_url)
    try:
        await wait_msg.delete()
    except Exception:
        pass

    try:
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename=f"{archetype['id']}_{seed}.jpg")
            await message.answer_photo(photo, caption=caption)
        else:
            # اگه عکس نیومد، خودِ لینک رو هم می‌ذاریم که تلگرام خودش امتحان کنه
            try:
                await message.answer_photo(image_url, caption=caption)
            except Exception:
                await message.answer(caption + "\n\n(⚠️ عکس این‌بار لود نشد، ولی خودِ همدم ثبت شد.)")
    except Exception as e:
        log_sync(f"⚠️ companion send failed: {e}", "WARN")
        await message.answer(caption)


async def cmd_collection(message: Message):
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.reply("❌ اول باید بازی رو شروع کنی: /start")
        return

    companions = player.get("companions", {})
    if not companions:
        await message.reply("📭 هنوز هیچ همدمی نداری. با /claim اولین همدمت رو احضار کن!")
        return

    fav_id = player.get("favorite_companion")
    partner_id = player.get("battle_partner")
    total_power = 0
    lines = [f"🎴 **کالکشنِ همدم‌ها** ({len(companions)}/{len(ARCHETYPES)})\n"]
    for aid, data in sorted(
        companions.items(), key=lambda kv: -RARITY_ORDER.index(kv[1].get("rarity", "common"))
    ):
        arch = ARCHETYPE_BY_ID.get(aid)
        if not arch:
            continue
        rdata = RARITY_DATA[data.get("rarity", "common")]
        power = companion_power_score(data)
        total_power += power
        tags = ""
        if aid == fav_id:
            tags += " 💖"
        if aid == partner_id:
            tags += " ⚔️"
        if data.get("count", 1) >= AWAKEN_DUPE_THRESHOLD:
            tags += " 🔥"
        lines.append(
            f"{rdata['emoji']} {arch['element']} **{arch['title']}** — {rdata['label']} "
            f"×{data.get('count', 1)} (قدرت: {power}){tags}"
        )
    lines.append(f"\n💪 قدرتِ کلِ کالکشن: **{total_power:,}**")
    lines.append(f"💠 شاردِ همانند‌سازی: {player.get('fusion_shards', 0):,}")
    lines.append(
        "\n💡 دستورهای بیشتر:\n"
        "`/favorite <اسم>` → بونوسِ Zenِ دائمی\n"
        "`/partner <اسم>` → بونوسِ دمیجِ PvE\n"
        "`/fuse <اسم>` → با شارد، یه پله ارتقاش بده\n"
        "🔥 = بیدارشده (۵+ تکراری، بونوسِ اضافه)"
    )

    await message.reply("\n".join(lines))


async def cmd_favorite(message: Message):
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.reply("❌ اول باید بازی رو شروع کنی: /start")
        return

    companions = player.get("companions", {})
    if not companions:
        await message.reply("📭 هنوز هیچ همدمی نداری که محبوبش کنی.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        options = ", ".join(ARCHETYPE_BY_ID[a]["title"] for a in companions if a in ARCHETYPE_BY_ID)
        await message.reply(f"✏️ اسمِ همدم رو هم بنویس، مثلاً:\n`/favorite بانوی شعله`\n\nهمدم‌های تو: {options}")
        return

    query = args[1].strip()
    match_id = None
    for aid in companions:
        arch = ARCHETYPE_BY_ID.get(aid)
        if arch and arch["title"] == query:
            match_id = aid
            break

    if not match_id:
        await message.reply("❌ همچین همدمی تو کالکشنت پیدا نکردم. اسمِ دقیق رو از /collection کپی کن.")
        return

    player["favorite_companion"] = match_id
    await asave_player(uid, player)
    arch = ARCHETYPE_BY_ID[match_id]
    fav_rarity = companions[match_id].get("rarity", "common")
    bonus_pct = (RARITY_ORDER.index(fav_rarity) + 1) * FAVORITE_ZEN_BONUS_PER_TIER * 100
    await message.reply(
        f"💖 {arch['element']} **{arch['title']}** الان همدمِ محبوبته!\n"
        f"از این به بعد تو هر شکار/غنیمت **{bonus_pct:.0f}٪** Zenِ بیشتری می‌گیری."
    )


def get_favorite_zen_bonus(player: dict) -> float:
    """برای استفاده‌ی سیستم‌های دیگه (مثلِ word_hunt_handlers/mob_combat): بونوسِ Zenِ
    همدمِ محبوب رو برمی‌گردونه (۰.۰ اگه محبوبی انتخاب نشده باشه)."""
    fav_id = player.get("favorite_companion")
    if not fav_id:
        return 0.0
    data = player.get("companions", {}).get(fav_id)
    if not data:
        return 0.0
    tier = RARITY_ORDER.index(data.get("rarity", "common")) + 1
    return tier * FAVORITE_ZEN_BONUS_PER_TIER


BATTLE_PARTNER_DMG_PCT_PER_TIER = 0.008     # هر پله‌ی ندرت: +۰.۸٪ دمیجِ PvE
AWAKEN_DUPE_THRESHOLD = 5                    # از ۵ تکراریِ همون کاراکتر → بیدارشده
AWAKEN_DMG_BONUS = 0.03                      # بونوسِ ثابتِ اضافه بعدِ بیداری


def get_battle_partner_combat_bonus(player: dict) -> float:
    """درصدِ دمیجِ اضافه‌ای که «یارِ نبردِ» انتخاب‌شده به مبارزاتِ PvE می‌ده.
    combat.py این رو دقیقاً مثلِ guild_dmg_pct/fate_dmg_pct صدا می‌زنه."""
    partner_id = player.get("battle_partner")
    if not partner_id:
        return 0.0
    data = player.get("companions", {}).get(partner_id)
    if not data:
        return 0.0
    tier = RARITY_ORDER.index(data.get("rarity", "common")) + 1
    bonus = tier * BATTLE_PARTNER_DMG_PCT_PER_TIER
    if data.get("count", 1) >= AWAKEN_DUPE_THRESHOLD:
        bonus += AWAKEN_DMG_BONUS
    return bonus


async def cmd_partner(message: Message):
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.reply("❌ اول باید بازی رو شروع کنی: /start")
        return

    companions = player.get("companions", {})
    if not companions:
        await message.reply("📭 هنوز هیچ همدمی نداری که یارِ نبردت کنی.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        options = ", ".join(ARCHETYPE_BY_ID[a]["title"] for a in companions if a in ARCHETYPE_BY_ID)
        await message.reply(f"⚔️ اسمِ همدم رو هم بنویس، مثلاً:\n`/partner بانوی شعله`\n\nهمدم‌های تو: {options}")
        return

    query = args[1].strip()
    match_id = next((aid for aid in companions if ARCHETYPE_BY_ID.get(aid, {}).get("title") == query), None)
    if not match_id:
        await message.reply("❌ همچین همدمی تو کالکشنت پیدا نکردم.")
        return

    player["battle_partner"] = match_id
    await asave_player(uid, player)

    arch = ARCHETYPE_BY_ID[match_id]
    data = companions[match_id]
    tier = RARITY_ORDER.index(data.get("rarity", "common")) + 1
    dmg_pct = tier * BATTLE_PARTNER_DMG_PCT_PER_TIER
    awakened = data.get("count", 1) >= AWAKEN_DUPE_THRESHOLD
    if awakened:
        dmg_pct += AWAKEN_DMG_BONUS

    txt = (
        f"⚔️ {arch['element']} **{arch['title']}** الان یارِ نبردته!\n"
        f"از این به بعد **{dmg_pct*100:.1f}٪** دمیجِ بیشتر تو نبردهای PvE می‌گیری."
    )
    if awakened:
        txt += "\n🔥 این همدم **بیدار شده** (۵+ تکراری) — بونوسِ اضافه فعاله."
    await message.reply(txt)


def companion_power_score(data: dict) -> int:
    """امتیازِ قدرتِ یه همدم — برای نمایشِ «قدرتِ کل» تو /collection."""
    tier = RARITY_ORDER.index(data.get("rarity", "common")) + 1
    base = tier * tier * 40
    dupes_bonus = min(data.get("count", 1) - 1, 20) * (tier * 6)
    return base + dupes_bonus


FUSE_COST_BY_TARGET_TIER = {
    # تیرِ مقصد (یعنی ندرتی که می‌خوای *بهش* برسی) → هزینه‌ی شارد
    "uncommon": 15, "rare": 35, "epic": 70, "mythic": 130,
    "legendary": 220, "ancient": 380, "astral": 600,
    "void": 950, "celestial": 1500, "transcendent": 2400,
}


async def cmd_fuse(message: Message):
    """با خرجِ شاردِ همانند‌سازی، یه همدمِ مشخص رو تضمینی یه پله ارتقا می‌ده."""
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.reply("❌ اول باید بازی رو شروع کنی: /start")
        return

    companions = player.get("companions", {})
    if not companions:
        await message.reply("📭 هنوز هیچ همدمی نداری که فیوژن کنی.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        options = ", ".join(ARCHETYPE_BY_ID[a]["title"] for a in companions if a in ARCHETYPE_BY_ID)
        await message.reply(f"🔮 اسمِ همدم رو هم بنویس، مثلاً:\n`/fuse بانوی شعله`\n\nهمدم‌های تو: {options}")
        return

    query = args[1].strip()
    match_id = next((aid for aid in companions if ARCHETYPE_BY_ID.get(aid, {}).get("title") == query), None)
    if not match_id:
        await message.reply("❌ همچین همدمی تو کالکشنت پیدا نکردم.")
        return

    data = companions[match_id]
    cur_rarity = data.get("rarity", "common")
    cur_idx = RARITY_ORDER.index(cur_rarity)
    if cur_idx >= len(RARITY_ORDER) - 1:
        await message.reply("👑 این همدم از قبل تو بالاترین سطحِ ندرته — دیگه جایی برای ارتقا نمونده.")
        return

    next_rarity = RARITY_ORDER[cur_idx + 1]
    cost = FUSE_COST_BY_TARGET_TIER.get(next_rarity, 999999)
    shards = player.get("fusion_shards", 0)
    if shards < cost:
        await message.reply(
            f"💠 برای رسوندنِ این همدم به «{RARITY_DATA[next_rarity]['label']}» "
            f"به **{cost:,}** شارد نیاز داری (الان: {shards:,})."
        )
        return

    player["fusion_shards"] = shards - cost
    data["rarity"] = next_rarity
    await asave_player(uid, player)

    arch = ARCHETYPE_BY_ID[match_id]
    rdata = RARITY_DATA[next_rarity]
    await message.reply(
        f"🔮✨ فیوژن موفق! {arch['element']} **{arch['title']}** حالا "
        f"{rdata['emoji']} **{rdata['label']}**ـه.\n💠 شاردِ باقی‌مونده: {player['fusion_shards']:,}"
    )


def register_companion_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_claim, Command("claim"))
    dp.message.register(cmd_collection, Command("collection"))
    dp.message.register(cmd_favorite, Command("favorite"))
    dp.message.register(cmd_partner, Command("partner"))
    dp.message.register(cmd_fuse, Command("fuse"))
