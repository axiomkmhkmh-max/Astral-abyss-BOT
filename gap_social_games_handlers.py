# ============================================================
#  ASTRAL ABYSS — 🎭 هندلرهای بازی‌های گروهیِ سریع (Gap dispatcher)
# ------------------------------------------------------------
#  پورتِ گپِ social_games_handlers.py. منطق (social_games.py) مشترکه.
#  ⚠️ گپ (طبقِ gap_types فعلی) ریپلای رو نمی‌ده، پس «ضایع کن»، «دوئل»
#  و «لقب» فعلاً فقط پیامِ راهنما می‌دن (مثلِ «نفرین»/«دعا» تو
#  gap_curse_handlers). وقتی gap_types.Message.reply_to_message اضافه
#  شد، فقط _target_from_reply رو عوض کن و بدنه‌ی هندلرها رو از نسخه‌ی
#  تلگرام کپی کن. «شیر یا خط»، «شانسم» و «قرعه/منم» کامل کار می‌کنن.
# ============================================================
from __future__ import annotations

from gap_types import Message
from gap_dispatcher import GapDispatcher

from database import aget_player, asave_player, player_lock
from logger import log_sync
import social_games as sg

_NO_REPLY = "تو گپ هنوز ریپلای پشتیبانی نمی‌شه — این یکی فعلاً فقط تو تلگرام کار می‌کنه."


async def _need_player(msg: Message) -> dict | None:
    player = await aget_player(msg.from_user.id)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return None
    return player


# ─── ریپلای‌محورها (فعلاً غیرفعال تو گپ) ────────────────────
async def cmd_roast(msg: Message):
    await msg.answer(f"💀 {_NO_REPLY}")


async def cmd_duel(msg: Message):
    await msg.answer(f"⚔️ {_NO_REPLY}")


async def cmd_nick(msg: Message):
    await msg.answer(f"🏷 {_NO_REPLY}")


# ─── 🪙 شیر یا خط ───────────────────────────────────────────
async def cmd_coin(msg: Message):
    uid = msg.from_user.id
    raw = sg.normalize(msg.text)[len("شیر یا خط"):].strip()
    stake = sg.parse_amount(raw) if raw else None
    if stake is None:
        await msg.answer(
            "🪙 **شیر یا خط**\n\nبنویس: شیر یا خط 500\n"
            f"۵۰/۵۰ — یا دو برابر می‌شه یا از دست می‌ره. ({sg.COIN_MIN:,} تا {sg.COIN_MAX:,} Zen)"
        )
        return
    left = sg.cooldown_left("coin", uid)
    if left:
        await msg.answer(f"⏳ {left} ثانیه صبر کن.")
        return
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player or not player.get("class"):
            await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        res = sg.flip_coin(player, stake)
        if not res["ok"]:
            await msg.answer(f"🪙 {res['err']}")
            return
        await asave_player(uid, player)
    sg.set_cooldown("coin", uid, sg.COIN_CD)

    sign = "🎉 **بردی!** +" if res["won"] else "💸 **باختی.** -"
    await msg.answer(
        f"🪙 سکه چرخید... {res['side']}\n{res['flavor']}\n\n"
        f"{sign}{stake:,} Zen\n💰 موجودی: {res['zen']:,} Zen"
    )
    log_sync(f"🪙 FLIP (Gap) — {player.get('name')} ({uid}) {'+' if res['won'] else '-'}{stake:,}", "CASINO")


# ─── 🔮 شانسم ───────────────────────────────────────────────
async def cmd_fortune(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player or not player.get("class"):
            await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        is_new, text = sg.draw_fortune(player, sg.display_name(player))
        if is_new:
            await asave_player(uid, player)
    if is_new:
        await msg.answer(text)
    else:
        await msg.answer(f"🔮 امروز فالت رو گرفتی! فردا بیا. این همون فالِ امروزته:\n\n{text}")


# ─── 🎯 قرعه‌ی برق‌آسا ──────────────────────────────────────
async def cmd_lottery(msg: Message):
    uid, chat_id = msg.from_user.id, msg.chat.id
    if msg.chat.type == "private":
        await msg.answer("🎯 قرعه فقط تو گروه معنی داره!")
        return
    raw = sg.normalize(msg.text)[len("قرعه"):].strip()
    prize = 0
    if raw:
        prize = sg.parse_amount(raw) or -1
        if prize < sg.LOTTERY_PRIZE_MIN or prize > sg.LOTTERY_PRIZE_MAX:
            await msg.answer(
                f"🎯 مبلغِ جایزه باید بین {sg.LOTTERY_PRIZE_MIN:,} تا {sg.LOTTERY_PRIZE_MAX:,} Zen باشه.\n"
                "یا فقط بنویس «قرعه» (بدونِ جایزه)."
            )
            return
    if sg.lottery_active(chat_id):
        info = sg.lottery_info(chat_id)
        await msg.answer(f"🎯 یه قرعه همین الان فعاله ({len(info['entrants'])} نفر)! بنویس «منم».")
        return
    gap = sg.lottery_gap_left(chat_id)
    if gap:
        await msg.answer(f"⏳ {gap} ثانیه دیگه می‌تونین قرعه‌ی جدید بزنین.")
        return
    me = await _need_player(msg)
    if not me:
        return
    if prize and int(me.get("zen", 0) or 0) < prize:
        await msg.answer(f"❌ Zen کافی نداری! موجودی: {int(me.get('zen', 0) or 0):,}")
        return

    name = sg.clean_name(me.get("name"))
    if not sg.lottery_create(chat_id, uid, name, prize):
        return
    prize_line = f"💰 جایزه: **{prize:,} Zen** (از جیبِ {name})\n" if prize else "🏆 جایزه: افتخارِ قرعه‌کشی 😎\n"
    await msg.answer(
        f"🎯 **قرعه‌ی برق‌آسا شروع شد!**\n\n{prize_line}"
        f"⏱ {sg.LOTTERY_SEC} ثانیه وقت دارین — هر کی می‌خواد بنویسه: منم"
    )
    bot, chat = msg.bot, chat_id

    async def _send(text: str):
        await bot.send_message(chat, text)

    sg.schedule_lottery_end(chat_id, _send)
    log_sync(f"🎯 LOTTERY start (Gap) — {name} ({uid}) chat={chat_id} prize={prize:,}", "CURSE")


async def cmd_lottery_join(msg: Message):
    uid = msg.from_user.id
    if not sg.lottery_active(msg.chat.id):
        return    # «منم» یه حرفِ عادیه؛ وقتی قرعه‌ای نیست بی‌صدا رد شو
    player = await aget_player(uid)
    if not player or not player.get("class"):
        return
    r = sg.lottery_join(msg.chat.id, uid, sg.display_name(player))
    if r == "joined":
        n = len(sg.lottery_info(msg.chat.id)["entrants"])
        await msg.answer(f"✅ {sg.clean_name(player.get('name'))} ثبت شد! ({n} نفر)")
    elif r == "already":
        await msg.answer("😏 تو که قبلاً ثبت شدی، اینقدر هم حریص نباش.")


def register_gap_social_games_handlers(dp: GapDispatcher):
    dp.register_message(cmd_roast, text=["ضایع کن", "ضایعش کن"])
    dp.register_message(cmd_duel, text=["دوئل", "دوئل برق‌آسا"])
    dp.register_message(cmd_nick, text=["لقب", "لقب بده"])
    dp.register_message(cmd_fortune, text=["شانسم", "شانسم چیه", "شانسم چیه؟"])
    dp.register_message(cmd_coin, text=["شیر یا خط"], text_startswith="شیر یا خط ")
    dp.register_message(cmd_lottery, text=["قرعه"], text_startswith="قرعه ")
    dp.register_message(cmd_lottery_join, text=["منم"])
