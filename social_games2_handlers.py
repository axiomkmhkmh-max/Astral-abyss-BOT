# ============================================================
#  ASTRAL ABYSS — 🎭 هندلرهای بازی‌های ریپلای‌محورِ دسته‌ی دوم (Telegram)
# ------------------------------------------------------------
#  🕵️ جیب بزن | 💘 شیپ | ⚖️ محاکمه | 📊 مقایسه | 🏷 قیمتش چنده |
#  🎁 جعبه [مبلغ] | 🪦 فاتحه — همه باید ریپلای رویِ پیامِ یه نفر باشن.
#  منطق تو social_games2.py. مثلِ نسخه‌ی اول، یه هندلرِ واحد با
#  فیلترِ parse_command؛ متنِ نامرتبط می‌ره سراغِ بقیه‌ی هندلرها.
# ============================================================
from __future__ import annotations

import contextlib
from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import aget_player, asave_player, player_lock
from logger import log_sync
import social_games as sg
import social_games2 as g2


# ─── ابزارها ────────────────────────────────────────────────
def _target_from_reply(msg: Message, allow_self: bool = False) -> tuple[int | None, str | None, str | None]:
    r = msg.reply_to_message
    if not r or not r.from_user:
        return None, None, "برای این کار باید رویِ پیامِ یه نفر ریپلای کنی."
    if r.from_user.is_bot:
        return None, None, "رو من اثر نمی‌کنه 😼"
    if not allow_self and r.from_user.id == msg.from_user.id:
        return None, None, "رو خودت که نمی‌شه! یکی دیگه رو انتخاب کن."
    return r.from_user.id, sg.clean_name(r.from_user.first_name), None


async def _need_player(msg: Message) -> dict | None:
    player = await aget_player(msg.from_user.id)
    if not player or not player.get("class"):
        await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return None
    return player


@contextlib.asynccontextmanager
async def _two_locks(a: int, b: int):
    """قفلِ هر دو بازیکن، همیشه به ترتیبِ uid (ضدِ دِدلاک وقتی دو نفر هم‌زمان رو هم اکشن می‌زنن)."""
    lo, hi = g2.lock_order(a, b)
    async with player_lock(lo):
        async with player_lock(hi):
            yield


def _nm(p: dict | None, fallback: str) -> str:
    return sg.display_name(p, fallback) if p else fallback


# ─── 🕵️ جیب بزن ─────────────────────────────────────────────
async def cmd_pick(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fb, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"🕵️ {err}")
        return
    left = sg.cooldown_left("pick", uid)
    if left:
        await msg.reply(f"⏳ دزدِ خوب صبور هم هست؛ {left // 60 + 1} دقیقه‌ی دیگه.")
        return
    left = sg.cooldown_left("pickimm", t_uid)
    if left:
        await msg.reply(f"🛡 {t_fb} تازه جیبش زده شده و هنوز مراقبه؛ {left // 60 + 1} دقیقه‌ی دیگه بیا.")
        return

    async with _two_locks(uid, t_uid):
        thief, victim = await aget_player(uid), await aget_player(t_uid)
        if not thief or not thief.get("class"):
            await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        if not victim or not victim.get("class"):
            await msg.reply(f"🕵️ {t_fb} هنوز بازی رو شروع نکرده.")
            return
        why = g2.check_pick(thief, victim)
        if why:
            await msg.reply(f"🕵️ {why}")
            return
        t_name = sg.display_name(thief)
        v_name = sg.display_name(victim, t_fb)
        res = g2.do_pick(thief, victim, t_name, v_name)
        await asave_player(uid, thief)
        await asave_player(t_uid, victim)

    sg.set_cooldown("pick", uid, g2.PICK_CD)
    sg.set_cooldown("pickimm", t_uid, g2.PICK_IMMUNE)
    icon = "🕵️✅" if res["won"] else "🚨"
    await msg.reply(f"{icon} **جیب‌بری!**\n\n{res['line']}")
    log_sync(f"🕵️ PICK — {thief.get('name')} ({uid}) → {victim.get('name')} ({t_uid}) "
             f"{'+' if res['won'] else '-'}{res['amount']:,}", "CASINO")


# ─── 💘 شیپ ─────────────────────────────────────────────────
async def cmd_ship(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fb, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"💘 {err}")
        return
    left = sg.cooldown_left("ship", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن، کوپید خسته‌ست.")
        return
    sg.set_cooldown("ship", uid, 5)
    pa, pb = await aget_player(uid), await aget_player(t_uid)
    na = sg.clean_name((pa or {}).get("name") or msg.from_user.first_name)
    nb = sg.clean_name((pb or {}).get("name") or t_fb)
    day = datetime.now(sg.TEHRAN).strftime("%Y-%m-%d")
    pct = g2.ship_percent(uid, t_uid, pa, pb, day)
    await msg.reply(
        f"💘 **شیپ: {na} ❤️ {nb}**\n\n"
        f"{g2.ship_bar(pct)}\n"
        f"💞 سازگاری: **{pct}٪**\n"
        f"👫 اسمِ زوج: **{g2.ship_name(na, nb)}**\n\n"
        f"{g2.ship_verdict(pct)}"
    )


# ─── 📊 مقایسه ──────────────────────────────────────────────
async def cmd_compare(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fb, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"📊 {err}")
        return
    left = sg.cooldown_left("compare", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن.")
        return
    me = await _need_player(msg)
    if not me:
        return
    other = await aget_player(t_uid)
    if not other or not other.get("class"):
        await msg.reply(f"📊 {t_fb} هنوز بازی رو شروع نکرده؛ آماری برای مقایسه نداره.")
        return
    sg.set_cooldown("compare", uid, 5)
    await msg.reply(g2.compare_card(me, other, sg.display_name(me), sg.display_name(other, t_fb)))


# ─── 🏷 قیمتش چنده ──────────────────────────────────────────
async def cmd_price(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fb, err = _target_from_reply(msg, allow_self=True)
    if err:
        await msg.reply(f"🏷 {err}")
        return
    left = sg.cooldown_left("price", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن.")
        return
    target = await aget_player(t_uid)
    if not target or not target.get("class"):
        await msg.reply(f"🏷 {t_fb} هنوز بازی رو شروع نکرده؛ برچسبی نداره، فقط یه ترحم 🥺")
        return
    sg.set_cooldown("price", uid, 5)
    await msg.reply(g2.price_text(target, sg.display_name(target, t_fb)))


# ─── 🪦 فاتحه ───────────────────────────────────────────────
async def cmd_fatiha(msg: Message):
    uid = msg.from_user.id
    t_uid, t_fb, err = _target_from_reply(msg, allow_self=True)
    if err:
        await msg.reply(f"🪦 {err}")
        return
    left = sg.cooldown_left("fatiha", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن.")
        return
    sg.set_cooldown("fatiha", uid, 10)
    async with player_lock(t_uid):
        target = await aget_player(t_uid)
        is_player = bool(target and target.get("class"))
        if is_player:
            g2.record_fatiha(target)
            await asave_player(t_uid, target)
    name = _nm(target if is_player else None, t_fb)
    await msg.reply(g2.fatiha_text(target if is_player else {}, name))


# ─── ⚖️ محاکمه ──────────────────────────────────────────────
def _trial_kb(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚖️ گناهکار", callback_data=f"sgt:{tid}:g"),
        InlineKeyboardButton(text="😇 بی‌گناه", callback_data=f"sgt:{tid}:i"),
    ]])


async def cmd_trial(msg: Message):
    uid, chat_id = msg.from_user.id, msg.chat.id
    if msg.chat.type == "private":
        await msg.reply("⚖️ دادگاه فقط تو گروه برپا می‌شه!")
        return
    t_uid, t_fb, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"⚖️ {err}")
        return
    if g2.trial_active_in(chat_id):
        await msg.reply("⚖️ یه دادگاه همین الان برقراره؛ صبر کن تا حکمش بیاد.")
        return
    left = sg.cooldown_left("trial", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن، قاضی استراحت می‌کنه.")
        return
    me = await _need_player(msg)
    if not me:
        return
    target = await aget_player(t_uid)
    name = sg.clean_name((target or {}).get("name") or t_fb)
    crime = g2.pick_crime(target)
    tid = g2.trial_create(chat_id, uid, t_uid, name, crime)
    if tid is None:
        return
    sg.set_cooldown("trial", uid, 30)

    sent = await msg.reply(
        f"⚖️ **دادگاهِ محفل!**\n\n"
        f"👤 متهم: **{name}**\n📜 اتهام: {crime}\n"
        f"👨‍⚖️ شاکی: {sg.clean_name(me.get('name'))}\n\n"
        f"🗳 رأی‌گیری مخفیه و {g2.TRIAL_SEC} ثانیه وقت دارین.\n"
        f"(متهم رأی نمی‌ده؛ حداقل {g2.TRIAL_MIN_VOTES} رأی لازمه)",
        reply_markup=_trial_kb(tid),
    )
    g2._TRIALS[tid]["msg_id"] = sent.message_id
    bot = msg.bot

    async def _finish(r: dict, label: str | None):
        if label and target and target.get("class"):
            async with player_lock(t_uid):
                p = await aget_player(t_uid)
                if p:
                    g2.apply_verdict_nick(p, label, "دادگاه")
                    st = g2.st2(p)
                    st["trial_guilty" if r["verdict"] == "guilty" else "trial_innocent"] += 1
                    await asave_player(t_uid, p)
        text = g2.verdict_text(r, label)
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=sent.message_id, reply_markup=None)
        except Exception:
            await bot.send_message(chat_id, text)

    g2.schedule_trial_end(tid, _finish)
    log_sync(f"⚖️ TRIAL — {me.get('name')} ({uid}) → {name} ({t_uid}) chat={chat_id}", "CURSE")


async def cb_trial(cb: CallbackQuery):
    try:
        _, tid_s, side = cb.data.split(":")
        tid = int(tid_s)
    except ValueError:
        await cb.answer()
        return
    t = g2.trial_get(tid)
    if not t or t["chat"] != cb.message.chat.id:
        await cb.answer("⌛ این دادگاه تموم شده.", show_alert=True)
        return
    player = await aget_player(cb.from_user.id)
    if not player or not player.get("class"):
        await cb.answer("❌ اول باید بازی رو شروع کنی (/start).", show_alert=True)
        return
    r = g2.trial_vote(tid, cb.from_user.id, side == "g")
    msgs = {
        "ok": "✅ رأیت ثبت شد (مخفیه)!",
        "dup": "😏 یه‌بار رأی دادی، قاضی‌بازی بسه.",
        "defendant": "🙅 متهم حقِ رأی نداره!",
        "closed": "⌛ این دادگاه تموم شده.",
    }
    await cb.answer(msgs[r], show_alert=(r != "ok"))


# ─── 🎁 جعبه‌ی مرموز ────────────────────────────────────────
def _box_kb(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎁 باز کن", callback_data=f"sgb:{bid}:o"),
        InlineKeyboardButton(text="🙅 نه", callback_data=f"sgb:{bid}:n"),
    ]])


async def cmd_box(msg: Message, arg: str):
    uid, chat_id = msg.from_user.id, msg.chat.id
    if msg.chat.type == "private":
        await msg.reply("🎁 جعبه فقط تو گروه معنی داره!")
        return
    t_uid, t_fb, err = _target_from_reply(msg)
    if err:
        await msg.reply(f"🎁 {err}\nمثال: ریپلای + «جعبه 500»")
        return
    stake = sg.parse_amount(arg) if arg else None
    if stake is None or stake < g2.BOX_MIN or stake > g2.BOX_MAX:
        await msg.reply(f"🎁 مبلغِ جعبه رو بنویس ({g2.BOX_MIN:,} تا {g2.BOX_MAX:,} Zen). مثال: «جعبه 500»")
        return
    left = sg.cooldown_left("box", uid)
    if left:
        await msg.reply(f"⏳ {left} ثانیه صبر کن.")
        return
    me = await _need_player(msg)
    if not me:
        return
    target = await aget_player(t_uid)
    if not target or not target.get("class"):
        await msg.reply(f"🎁 {t_fb} هنوز بازی رو شروع نکرده.")
        return
    if int(me.get("zen", 0) or 0) < stake:
        await msg.reply(f"❌ Zen کافی نداری! موجودی: {int(me.get('zen', 0) or 0):,}")
        return
    if int(target.get("zen", 0) or 0) < stake:
        await msg.reply(f"🎁 {t_fb} اونقدر Zen نداره که ریسکِ این جعبه رو بپذیره ({stake:,}).")
        return

    s_name, t_name = sg.clean_name(me.get("name")), sg.clean_name(target.get("name") or t_fb)
    bid = g2.box_create(chat_id, uid, t_uid, s_name, t_name, stake)
    if bid is None:
        await msg.reply("🎁 تو یه جعبه‌ی بازنشده داری؛ اول اون تموم بشه.")
        return
    sg.set_cooldown("box", uid, g2.BOX_CD)
    sent = await msg.reply(
        f"🎁 **جعبه‌ی مرموز!**\n\n"
        f"{s_name} یه جعبه‌ی {stake:,} Zen‌ی برای **{t_name}** فرستاد.\n\n"
        f"🎲 اگه باز کنی ۵۰/۵۰:\n"
        f"• 🍀 {stake:,} Zen از جیبِ {s_name} می‌برنی\n"
        f"• 💥 یا می‌ترکه و {stake:,} Zen از جیبِ خودت می‌ره\n\n"
        f"⏱ {g2.BOX_SEC} ثانیه وقت داری. فقط {t_name} می‌تونه باز کنه.",
        reply_markup=_box_kb(bid),
    )
    g2._BOXES[bid]["msg_id"] = sent.message_id
    bot = msg.bot

    async def _expire(b: dict):
        try:
            await bot.edit_message_text(
                f"🎁 جعبه‌ی {b['s_name']} برای {b['t_name']} باز نشد و خاک خورد 🕸\n(هیچ Zen‌ای جابه‌جا نشد)",
                chat_id=b["chat"], message_id=b["msg_id"], reply_markup=None)
        except Exception:
            pass

    g2.schedule_box_expiry(bid, _expire)
    log_sync(f"🎁 BOX — {s_name} ({uid}) → {t_name} ({t_uid}) stake={stake:,}", "CASINO")


async def cb_box(cb: CallbackQuery):
    try:
        _, bid_s, action = cb.data.split(":")
        bid = int(bid_s)
    except ValueError:
        await cb.answer()
        return
    b = g2.box_get(bid)
    if not b or b["chat"] != cb.message.chat.id:
        await cb.answer("⌛ این جعبه دیگه نیست.", show_alert=True)
        return
    uid = cb.from_user.id
    if action == "n":
        if uid not in (b["target"], b["sender"]):
            await cb.answer("این جعبه مالِ تو نیست 😏", show_alert=True)
            return
        b = g2.box_close(bid)
        if not b:
            await cb.answer("⌛ این جعبه دیگه نیست.", show_alert=True)
            return
        await cb.answer()
        try:
            await cb.message.edit_text(f"🎁 جعبه‌ی {b['s_name']} برای {b['t_name']} رد شد 🙅\n(هیچ Zen‌ای جابه‌جا نشد)")
        except Exception:
            pass
        return
    # باز کردن — فقط خودِ گیرنده
    if uid != b["target"]:
        await cb.answer("این جعبه مالِ تو نیست 😏", show_alert=True)
        return
    b = g2.box_close(bid)          # اتمیک: دوبار-کلیک دوبار تسویه نمی‌کنه
    if not b:
        await cb.answer("⌛ این جعبه دیگه نیست.", show_alert=True)
        return
    await cb.answer()
    stake = b["stake"]
    async with _two_locks(b["sender"], b["target"]):
        sp, tp = await aget_player(b["sender"]), await aget_player(b["target"])
        if (not sp or not tp or int(sp.get("zen", 0) or 0) < stake or int(tp.get("zen", 0) or 0) < stake):
            text = f"🎁 جعبه کنسل شد — یکی از دو طرف دیگه {stake:,} Zen نداشت. هیچ Zen‌ای جابه‌جا نشد."
            res = None
        else:
            res = g2.settle_box(sp, tp, stake, b["s_name"], b["t_name"])
            await asave_player(b["sender"], sp)
            await asave_player(b["target"], tp)
            text = f"🎁 **نتیجه‌ی جعبه**\n\n{res['text']}"
    try:
        await cb.message.edit_text(text)
    except Exception:
        await cb.message.answer(text)
    if res:
        log_sync(f"🎁 BOX OPEN — {b['s_name']}→{b['t_name']} {res['kind']} stake={stake:,}", "CASINO")


# ─── مسیریاب ────────────────────────────────────────────────
def _filter(msg: Message) -> bool:
    return bool(msg.text) and g2.parse_command(msg.text) is not None


async def on_social2_text(msg: Message):
    cmd, arg = g2.parse_command(msg.text)
    if cmd == "pick":
        await cmd_pick(msg)
    elif cmd == "ship":
        await cmd_ship(msg)
    elif cmd == "trial":
        await cmd_trial(msg)
    elif cmd == "compare":
        await cmd_compare(msg)
    elif cmd == "price":
        await cmd_price(msg)
    elif cmd == "box":
        await cmd_box(msg, arg)
    elif cmd == "fatiha":
        await cmd_fatiha(msg)


def register_social_games2_handlers(dp, bot):
    dp.message.register(on_social2_text, _filter)
    dp.callback_query.register(cb_trial, F.data.startswith("sgt:"))
    dp.callback_query.register(cb_box, F.data.startswith("sgb:"))
