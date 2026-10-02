# ============================================================
#  ASTRAL ABYSS — 🎭 هندلرهای بازی‌های گروهیِ سریع (Telegram)
# ------------------------------------------------------------
#  💀 ضایع کن | 🪙 شیر یا خط [مبلغ] | ⚔️ دوئل | 🔮 شانسم | 🏷 لقب | 🎯 قرعه / منم
#  «ضایع کن»، «دوئل» و «لقب» باید ریپلای رویِ پیامِ یه نفر باشن.
#  منطق تو social_games.py — این فایل فقط UI و ثبتِ هندلره.
#  یه هندلرِ واحد همه‌ی متن‌ها رو با sg.parse_command مسیریابی می‌کنه
#  (نرمال‌سازیِ نیم‌فاصله/ی-ک عربی هم همون‌جاست) و اگه متن به هیچ‌کدوم
#  نخورد، فیلتر False برمی‌گردونه و پیام می‌ره سراغِ بقیه‌ی هندلرها.
# ============================================================
from __future__ import annotations

import asyncio

from aiogram.types import Message

from database import aget_player, asave_player, player_lock
from logger import log_sync
import social_games as sg


def _target_from_reply(msg: Message) -> tuple[int | None, str | None, str | None]:
    r = msg.reply_to_message
    if not r or not r.from_user:
        return None, None, "برای این کار باید رویِ پیامِ یه نفر ریپلای کنی."
    if r.from_user.is_bot:
        return None, None, "رو من اثر نمی‌کنه 😼"
    return r.from_user.id, sg.clean_name(r.from_user.first_name), None


async def _need_player(msg: Message) -> dict | None:
    player = await aget_player(msg.from_user.id)
    if not player or not player.get("class"):
        await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return None
    return player


# ─── 💀 ضایع کن ─────────────────────────────────────────────
async def cmd_roast(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fallback, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"💀 {err}")
        return
    left = sg.cooldown_left("roast", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن، قربانی‌ها نفس بکشن.")
        return
    me = await _need_player(msg)
    if not me:
        return
    sg.set_cooldown("roast", uid, sg.ROAST_CD)

    target = await aget_player(t_uid)
    if not target or not target.get("class"):
        await msg.reply(f"💀 {t_fallback} هنوز بازی رو شروع نکرده؛ حتی ضایع‌شدن هم برای آدمای ثبت‌نام‌کرده‌ست 😏")
        return
    name = sg.display_name(target, t_fallback)
    await msg.reply(
        f"💀 **{sg.clean_name(me.get('name'))}** ضایعِ {name} کرد:\n\n{sg.roast_line(target, sg.clean_name(target.get('name') or t_fallback))}"
    )
    log_sync(f"💀 ROAST — {me.get('name')} ({uid}) → {name} ({t_uid})", "CURSE")


# ─── 🪙 شیر یا خط ───────────────────────────────────────────
async def cmd_coin(msg: Message, arg: str):
    uid = msg.from_user.id
    stake = sg.parse_amount(arg) if arg else None
    if stake is None:
        await msg.reply(
            "🪙 **شیر یا خط**\n\nبنویس: `شیر یا خط 500`\n"
            f"۵۰/۵۰ — یا دو برابر می‌شه یا از دست می‌ره. ({sg.COIN_MIN:,} تا {sg.COIN_MAX:,} Zen)"
        )
        return
    left = sg.cooldown_left("coin", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن.")
        return
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player or not player.get("class"):
            await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        res = sg.flip_coin(player, stake)
        if not res["ok"]:
            await msg.reply(f"🪙 {res['err']}")
            return
        await asave_player(uid, player)
    sg.set_cooldown("coin", uid, sg.COIN_CD)

    sign = "🎉 **بردی!** +" if res["won"] else "💸 **باختی.** -"
    await msg.reply(
        f"🪙 سکه چرخید... {res['side']}\n{res['flavor']}\n\n"
        f"{sign}{stake:,} Zen\n💰 موجودی: {res['zen']:,} Zen"
    )
    log_sync(f"🪙 FLIP — {player.get('name')} ({uid}) {'+' if res['won'] else '-'}{stake:,}", "CASINO")


# ─── ⚔️ دوئل ────────────────────────────────────────────────
async def cmd_duel(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fallback, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"⚔️ {err}")
        return
    if t_uid == uid:
        await msg.reply("⚔️ با خودت دوئل؟ تنها حریفِ لایقت آینه‌ست 🪞")
        return
    left = sg.cooldown_left("duel", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن، شمشیرا هنوز داغن.")
        return
    me = await _need_player(msg)
    if not me:
        return
    sg.set_cooldown("duel", uid, sg.DUEL_CD)

    other = await aget_player(t_uid)
    a_name = sg.display_name(me)
    b_name = sg.display_name(other, t_fallback) if other else t_fallback
    res = sg.duel_flip(a_name, b_name)

    sent = await msg.reply(res["intro"])
    await asyncio.sleep(2.5)
    try:
        await sent.edit_text(f"{res['intro']}\n\n{res['result']}")
    except Exception:
        await msg.reply(res["result"])

    # آمارِ نمایشیِ برد/باخت روی خودِ پلیرها (اگه ثبت‌نام‌شده باشن)
    for p_uid, won in ((uid, res["a_wins"]), (t_uid, not res["a_wins"])):
        async with player_lock(p_uid):
            p = await aget_player(p_uid)
            if p and p.get("class"):
                sg.record_duel(p, won)
                await asave_player(p_uid, p)
    log_sync(f"⚔️ DUEL — {a_name} vs {b_name} → {res['winner']}", "CURSE")


# ─── 🔮 شانسم ───────────────────────────────────────────────
async def cmd_fortune(msg: Message):
    uid = msg.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player or not player.get("class"):
            await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        is_new, text = sg.draw_fortune(player, sg.display_name(player))
        if is_new:
            await asave_player(uid, player)
    if is_new:
        await msg.reply(text)
    else:
        await msg.reply(f"🔮 امروز فالت رو گرفتی! فردا بیا. این همون فالِ امروزته:\n\n{text}")


# ─── 🏷 لقب بده ─────────────────────────────────────────────
async def cmd_nick(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fallback, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"🏷 {err}")
        return
    left = sg.cooldown_left("nick", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن، لقب‌ساز خسته شد.")
        return
    me = await _need_player(msg)
    if not me:
        return
    giver = sg.clean_name(me.get("name"))

    async with player_lock(t_uid):
        target = await aget_player(t_uid)
        if not target or not target.get("class"):
            await msg.reply(f"🏷 {t_fallback} هنوز بازی رو شروع نکرده؛ لقب برای ثبت‌نام‌کرده‌هاست.")
            return
        res = sg.give_nick(target, giver)
        await asave_player(t_uid, target)
    sg.set_cooldown("nick", uid, sg.NICK_CD)

    name = sg.clean_name(target.get("name") or t_fallback)
    extra = "\n(لقبِ قبلی‌ش پاک شد 😈)" if res["replaced"] else ""
    await msg.reply(
        f"🏷 **{giver}** به {name} لقب داد:\n\n**{res['label']}**\n\n"
        f"⏳ تا ۲۴ ساعت کنارِ اسمش می‌مونه.{extra}"
    )
    log_sync(f"🏷 NICK — {giver} → {name} ({t_uid}): {res['label']}", "CURSE")


# ─── 🎯 قرعه‌ی برق‌آسا ──────────────────────────────────────
async def cmd_lottery(msg: Message, arg: str):
    uid, chat_id = msg.from_user.id, msg.chat.id
    if msg.chat.type == "private":
        await msg.reply("🎯 قرعه فقط تو گروه معنی داره!")
        return
    prize = 0
    if arg:
        prize = sg.parse_amount(arg) or -1
        if prize < sg.LOTTERY_PRIZE_MIN or prize > sg.LOTTERY_PRIZE_MAX:
            await msg.reply(
                f"🎯 مبلغِ جایزه باید بین {sg.LOTTERY_PRIZE_MIN:,} تا {sg.LOTTERY_PRIZE_MAX:,} Zen باشه.\n"
                "یا فقط بنویس «قرعه» (بدونِ جایزه)."
            )
            return
    if sg.lottery_active(chat_id):
        info = sg.lottery_info(chat_id)
        await msg.reply(f"🎯 یه قرعه همین الان فعاله ({len(info['entrants'])} نفر)! بنویس «منم».")
        return
    gap = sg.lottery_gap_left(chat_id)
    if gap:
        await msg.reply(f"⏳ {gap} ثانیه دیگه می‌تونین قرعه‌ی جدید بزنین.")
        return
    me = await _need_player(msg)
    if not me:
        return
    if prize and int(me.get("zen", 0) or 0) < prize:
        await msg.reply(f"❌ Zen کافی نداری! موجودی: {int(me.get('zen', 0) or 0):,}")
        return

    name = sg.clean_name(me.get("name"))
    if not sg.lottery_create(chat_id, uid, name, prize):
        return
    prize_line = f"💰 جایزه: **{prize:,} Zen** (از جیبِ {name})\n" if prize else "🏆 جایزه: افتخارِ قرعه‌کشی 😎\n"
    await msg.answer(
        f"🎯 **قرعه‌ی برق‌آسا شروع شد!**\n\n{prize_line}"
        f"⏱ {sg.LOTTERY_SEC} ثانیه وقت دارین — هر کی می‌خواد بنویسه: **منم**"
    )
    bot, chat = msg.bot, chat_id

    async def _send(text: str):
        await bot.send_message(chat, text)

    sg.schedule_lottery_end(chat_id, _send)
    log_sync(f"🎯 LOTTERY start — {name} ({uid}) chat={chat_id} prize={prize:,}", "CURSE")


async def cmd_lottery_join(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        return    # قرعه‌ی فعال هست ولی این آدم بازیکن نیست — بی‌صدا رد شو
    r = sg.lottery_join(msg.chat.id, uid, sg.display_name(player))
    if r == "joined":
        n = len(sg.lottery_info(msg.chat.id)["entrants"])
        await msg.reply(f"✅ ثبت شدی! ({n} نفر)")
    elif r == "already":
        await msg.reply("😏 تو که قبلاً ثبت شدی، اینقدر هم حریص نباش.")


# ─── مسیریاب ────────────────────────────────────────────────
def _filter(msg: Message) -> bool:
    return bool(msg.text) and sg.parse_command(msg.text, msg.chat.id) is not None


async def on_social_text(msg: Message):
    cmd, arg = sg.parse_command(msg.text, msg.chat.id)
    if cmd == "roast":
        await cmd_roast(msg)
    elif cmd == "coin":
        await cmd_coin(msg, arg)
    elif cmd == "duel":
        await cmd_duel(msg)
    elif cmd == "fortune":
        await cmd_fortune(msg)
    elif cmd == "nick":
        await cmd_nick(msg)
    elif cmd == "lottery":
        await cmd_lottery(msg, arg)
    elif cmd == "join":
        await cmd_lottery_join(msg)


def register_social_games_handlers(dp, bot):
    dp.message.register(on_social_text, _filter)
