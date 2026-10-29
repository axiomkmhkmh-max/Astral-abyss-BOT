# ============================================================
#  ASTRAL ABYSS — 🤖 AI Handlers (Gap)
# ------------------------------------------------------------
#  پورتِ گپِ ai_handlers.py. هسته (ai_core.py) مشتراکه.
#  گپ ریپلای/منشن نمی‌ده، پس فقط:  /ask سوال   |   «سوال: ...»  |  «بپرس ...»
#  ادمین (GAP_ADMIN_IDS): /aistatus  و  /aireload
# ============================================================
from __future__ import annotations

import re

from gap_types import Message
from gap_dispatcher import GapDispatcher
from gap_admin_panel import is_gap_admin

import ai_core

_PREFIX = re.compile(r"^\s*(سوال|سؤال|بپرس|ask)\s*[:：،,]?\s+(.+)$", re.S | re.I)
_CMD_FIND = re.compile(r"^\s*/aifind(?:@\w+)?\s*(.*)$", re.S | re.I)
_CMD = re.compile(r"^\s*/(?:ask|ai)(?:@\w+)?\s*(.*)$", re.S | re.I)


async def _reply(msg: Message, question: str):
    uid = msg.from_user.id
    hint = ""
    try:
        from database import aget_player
        p = await aget_player(uid)
        if p and p.get("class"):
            hint = f"بازیکن: سطح {p.get('level', 1)}، کلاس {p.get('class')}. (فقط برای لحنِ جواب؛ ازش عدد جعل نکن.)"
    except Exception:
        pass
    text = await ai_core.ask(uid, question, player_hint=hint, is_admin=is_gap_admin(msg))
    await msg.answer(text)


async def cmd_ask(msg: Message):
    m = _CMD.match(msg.text or "")
    await _reply(msg, (m.group(1) if m else "").strip())


async def on_prefix(msg: Message):
    m = _PREFIX.match(msg.text or "")
    if m:
        await _reply(msg, m.group(2).strip())


async def cmd_aistatus(msg: Message):
    if is_gap_admin(msg):
        await msg.answer(ai_core.status_text())


async def cmd_aireload(msg: Message):
    if is_gap_admin(msg):
        await msg.answer(f"✅ {ai_core.reload_knowledge()} بخشِ دانش لود شد.")


async def cmd_aikeys(msg: Message):
    if is_gap_admin(msg):
        try:
            await msg.answer(await ai_core.keys_report())
        except Exception as e:
            await msg.answer(f"خطا: {type(e).__name__}: {str(e)[:200]}")


async def cmd_aimodels(msg: Message):
    if is_gap_admin(msg):
        try:
            await msg.answer(await ai_core.free_models())
        except Exception as e:
            await msg.answer(f"خطا: {type(e).__name__}: {str(e)[:200]}")


async def cmd_aifind(msg: Message):
    if is_gap_admin(msg):
        m = _CMD_FIND.match(msg.text or "")
        await msg.answer(ai_core.debug_find((m.group(1) if m else "").strip()))


def register_gap_ai_handlers(dp: GapDispatcher):
    dp.register_message(cmd_ask, commands=["ask", "ai"])
    dp.register_message(cmd_aistatus, commands=["aistatus"])
    dp.register_message(cmd_aireload, commands=["aireload"])
    dp.register_message(cmd_aikeys, commands=["aikeys"])
    dp.register_message(cmd_aimodels, commands=["aimodels"])
    dp.register_message(cmd_aifind, commands=["aifind"])
    for w in ("سوال", "بپرس"):
        dp.register_message(on_prefix, text_startswith=w)
