# ============================================================
#  ASTRAL ABYSS — Social Retention Handlers (UI + middleware)
#  (social_retention_handlers.py)
#  /streaks → استریکِ ورود + استریکِ دوتایی + دکمه‌ی «بیدارش کن»
# ============================================================
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import social_retention as sr
from database import aget_player

_tasks: set = set()  # رفرنسِ زنده به تسک‌ها (تا GC نشن)


def _fire(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _activity_middleware(handler, event, data):
    """هر بازیکن رو روزی یه‌بار (تو پس‌زمینه) ثبت می‌کنه؛ هیچ‌وقت مسیرِ هندلر رو کند نمی‌کنه."""
    user = getattr(event, "from_user", None)
    if user and not user.is_bot:
        bot = data.get("bot")
        if bot is not None:
            async def _safe():
                try:
                    # کمی صبر: تا هندلرِ اصلیِ همین اکشن پلیر رو ذخیره کنه و پاداشِ ما زیرش له نشه
                    await asyncio.sleep(2)
                    await sr.touch(bot, user.id)
                except Exception as e:
                    sr._log(f"🔴 retention touch error: {e}", "ERROR")
            _fire(_safe())
    return await handler(event, data)


async def _overview(uid: int):
    text, inactive = await sr.build_overview(uid)
    rows = []
    row = []
    for f in inactive:
        row.append(InlineKeyboardButton(text=f"👋 {await sr._name(f)}", callback_data=f"ret:poke:{f}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="ret:me")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_streaks(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    text, kb = await _overview(uid)
    await msg.answer(text, reply_markup=kb)


async def cb_me(cb: CallbackQuery):
    text, kb = await _overview(cb.from_user.id)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


async def cb_poke(cb: CallbackQuery):
    try:
        target = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer()
        return
    result = await sr.poke(cb.bot, cb.from_user.id, target)
    await cb.answer(result, show_alert=True)


def register_social_retention_handlers(dp: Dispatcher, bot: Bot):
    dp.message.outer_middleware(_activity_middleware)
    dp.callback_query.outer_middleware(_activity_middleware)
    dp.message.register(cmd_streaks, Command("streaks"))
    dp.callback_query.register(cb_me, F.data == "ret:me")
    dp.callback_query.register(cb_poke, F.data.startswith("ret:poke:"))
