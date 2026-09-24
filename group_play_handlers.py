# ============================================================
#  ASTRAL ABYSS — Group Play Handlers
#  (group_play_handlers.py)
#  /groups → جدولِ گروه‌های هفته   |   /gchest → (ادمین) پرتابِ دستیِ صندوق
#  + دکمه‌ی صندوق + middlewareِ سنجشِ فعالیتِ گروه
#  ⚠️ باید قبلِ register_group_handlers ثبت بشه (اون یه catch-all
#     برای تمامِ پیام‌های گروهیه و کامندهای بعدش رو می‌بلعه).
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import group_play as gp

_GROUP_TYPES = ("group", "supergroup")


async def _activity_middleware(handler, event: Message, data: dict):
    user = event.from_user
    if event.chat.type in _GROUP_TYPES and user and not user.is_bot:
        bot = data.get("bot")
        if bot is not None:
            async def _safe():
                try:
                    await gp.record_activity(bot, event.chat.id, user.id, event.chat.title)
                except Exception as e:
                    gp._log(f"🔴 group_play activity error: {e}", "ERROR")
            gp._spawn(_safe())
    return await handler(event, data)


async def cmd_groups(msg: Message):
    chat_id = msg.chat.id if msg.chat.type in _GROUP_TYPES else None
    await msg.answer(await gp.build_board_text(chat_id))


async def cmd_gchest(msg: Message, bot: Bot):
    from admin_panel import is_admin
    if msg.chat.type not in _GROUP_TYPES:
        await msg.answer("👥 این دستور فقط تو گروه کار می‌کنه.")
        return
    if not is_admin(msg):
        await msg.answer("❌ فقط ادمین می‌تونه صندوق بندازه!")
        return
    ok = await gp.maybe_drop(bot, msg.chat.id, msg.chat.title, set(), force=True)
    if not ok:
        await msg.answer("⚠️ نتونستم صندوق بفرستم.")


async def cb_chest(cb: CallbackQuery):
    try:
        _, chat_s, drop_id = cb.data.split(":")
        chat_id = int(chat_s)
    except ValueError:
        await cb.answer()
        return
    ok, text = await gp.claim_chest(cb.bot, chat_id, drop_id, cb.from_user.id)
    await cb.answer(text, show_alert=True)


def register_group_play_handlers(dp: Dispatcher, bot: Bot):
    dp.message.outer_middleware(_activity_middleware)
    dp.message.register(cmd_groups, Command("groups"))
    dp.message.register(cmd_gchest, Command("gchest"))
    dp.callback_query.register(cb_chest, F.data.startswith("gchest:"))
