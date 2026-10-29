# ============================================================
#  ASTRAL ABYSS — 🤖 AI Handlers (Telegram)
# ------------------------------------------------------------
#  راه‌های صدا زدنِ هوش مصنوعی (عمداً محدود، تا با بقیه‌ی هندلرها و
#  مرحله‌ی ساخت کاراکتر تداخل نداشته باشه):
#    • /ask سوالت        یا   /ai سوالت
#    • «سوال: ...»  یا  «بپرس ...»  (کلمه اولِ پیام)
#    • منشنِ ربات:  @ASTRALABYSS_BOT سوالت
#    • ریپلای روی یکی از جواب‌های خودِ AI  (ادامه‌ی گفتگو)
#  ادمین‌ها: /aistatus (آمار و وضعیتِ کلیدها)، /aireload (لودِ دوباره‌ی ai_knowledge.txt)،
#            /aikeys (محدودیتِ هر کلید از خودِ OpenRouter)، /aimodels (مدل‌های رایگانِ الان)
#            /aifind سوال  (ببین AI برای این سوال کدوم تکه‌های ربات رو پیدا می‌کنه)
# ============================================================
from __future__ import annotations

import html
import logging
import re
from collections import OrderedDict

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import ai_core

log = logging.getLogger("ai_handlers")

_PREFIX = re.compile(r"^\s*(سوال|سؤال|بپرس|ask)\s*[:：،,]?\s+(.+)$", re.S | re.I)
_ai_msg_ids: "OrderedDict[tuple[int, int], bool]" = OrderedDict()  # (chat_id, message_id)
_ME: dict = {}


def _is_admin(uid: int) -> bool:
    try:
        from admin_panel import ADMIN_IDS
        return uid in ADMIN_IDS
    except Exception:  # noqa: BLE001
        return False


async def _player_hint(uid: int) -> str:
    try:
        from database import aget_player
        p = await aget_player(uid)
        if p and p.get("class"):
            return f"بازیکن: سطح {p.get('level', 1)}، کلاس {p.get('class')}، مپ {p.get('map', '؟')}. (فقط برای لحنِ جواب؛ ازش عدد جعل نکن.)"
    except Exception:  # noqa: BLE001
        pass
    return ""


async def _answer(msg: Message, bot: Bot, question: str, chat_mode: bool = False):
    uid = msg.from_user.id
    try:
        await bot.send_chat_action(msg.chat.id, "typing")
    except Exception:  # noqa: BLE001
        pass
    text = await ai_core.ask(uid, question, player_hint=await _player_hint(uid),
                             chat_mode=chat_mode, is_admin=_is_admin(uid))
    sent = await msg.reply(html.escape(text))
    _ai_msg_ids[(sent.chat.id, sent.message_id)] = True
    while len(_ai_msg_ids) > 2000:
        _ai_msg_ids.popitem(last=False)


def register_ai_handlers(dp: Dispatcher, bot: Bot):
    @dp.message(Command("ask", "ai"))
    async def cmd_ask(msg: Message, command: CommandObject):
        await _answer(msg, bot, command.args or "")

    @dp.message(Command("aistatus"))
    async def cmd_aistatus(msg: Message):
        if not _is_admin(msg.from_user.id):
            return
        await msg.answer(html.escape(ai_core.status_text()))

    @dp.message(Command("aireload"))
    async def cmd_aireload(msg: Message):
        if not _is_admin(msg.from_user.id):
            return
        n = ai_core.reload_knowledge()
        await msg.answer(f"✅ {n} بخشِ دانش لود شد.")

    @dp.message(Command("aikeys"))
    async def cmd_aikeys(msg: Message):
        if not _is_admin(msg.from_user.id):
            return
        try:
            await msg.answer(html.escape(await ai_core.keys_report()))
        except Exception as e:  # noqa: BLE001
            await msg.answer(html.escape(f"خطا: {type(e).__name__}: {str(e)[:200]}"))

    @dp.message(Command("aimodels"))
    async def cmd_aimodels(msg: Message):
        if not _is_admin(msg.from_user.id):
            return
        try:
            await msg.answer(html.escape(await ai_core.free_models()))
        except Exception as e:  # noqa: BLE001
            await msg.answer(html.escape(f"خطا: {type(e).__name__}: {str(e)[:200]}"))

    @dp.message(Command("aifind"))
    async def cmd_aifind(msg: Message, command: CommandObject):
        if not _is_admin(msg.from_user.id):
            return
        await msg.answer(html.escape(ai_core.debug_find(command.args or "")))

    async def _trigger(msg: Message):
        """فیلترِ دستی: True یعنی این پیام مالِ AI هست و کوئسشن رو برمی‌گردونه."""
        text = (msg.text or "").strip()
        if not text or text.startswith("/"):
            return False
        m = _PREFIX.match(text)
        if m:
            return {"question": m.group(2).strip(), "chat_mode": False}
        # ریپلای روی جوابِ AI
        r = msg.reply_to_message
        if r and r.from_user and r.from_user.is_bot and (r.chat.id, r.message_id) in _ai_msg_ids:
            return {"question": text, "chat_mode": True}
        # منشن
        if "me" not in _ME:
            try:
                _ME["me"] = await bot.get_me()
            except Exception:  # noqa: BLE001
                return False
        uname = (_ME["me"].username or "").lower()
        if uname and f"@{uname}" in text.lower():
            q = re.sub(rf"@{re.escape(uname)}", "", text, flags=re.I).strip()
            return {"question": q, "chat_mode": True}
        return False

    @dp.message(_trigger)
    async def on_ai_trigger(msg: Message, question: str, chat_mode: bool):
        await _answer(msg, bot, question, chat_mode=chat_mode)
