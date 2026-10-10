"""میان‌افزار: ضد‌اسپم، ساخت/به‌روزرسانی کاربر، ردیابی گروه‌های فعال."""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Chat, User as TgUser
from pymongo.errors import DuplicateKeyError

import config
from database import GroupChat, User
from services.redis_service import redis_service
from utils.helpers import utcnow


async def ensure_user(tg: TgUser) -> User:
    uname = tg.username.lower() if tg.username else None
    name = tg.full_name
    user = await User.find_one(User.tg_id == tg.id)
    if user is None:
        try:
            user = User(tg_id=tg.id, name=name, username=uname)
            await user.insert()
        except DuplicateKeyError:
            user = await User.find_one(User.tg_id == tg.id)
        return user
    patch: dict[str, Any] = {}
    if user.name != name:
        patch["name"] = name
    if user.username != uname:
        patch["username"] = uname
    if (utcnow() - user.last_seen).total_seconds() > 60:
        patch["last_seen"] = utcnow()
    if patch:
        await user.set(patch)
    return user


async def track_group(chat: Chat, uid: int) -> None:
    r = redis_service.r
    key = f"active:{chat.id}"
    await r.zadd(key, {str(uid): time.time()})
    await r.expire(key, 3600)
    if await redis_service.cooldown(f"grp:{chat.id}", 60) == 0:
        g = await GroupChat.find_one(GroupChat.chat_id == chat.id)
        if g is None:
            try:
                await GroupChat(chat_id=chat.id, title=chat.title or "").insert()
            except DuplicateKeyError:
                pass
        else:
            await g.set({"title": chat.title or "", "last_activity": utcnow(), "is_active": True})


class GameContextMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, dict], Awaitable[Any]], event: Any, data: dict) -> Any:
        tg = data.get("event_from_user")
        chat = data.get("event_chat")
        if tg is None or tg.is_bot:
            return await handler(event, data)
        if not await redis_service.r.set(f"thr:{tg.id}", "1", nx=True, px=config.THROTTLE_MS):
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ آروم‌تر!")
            return None
        data["user"] = await ensure_user(tg)
        if chat is not None and chat.type in ("group", "supergroup"):
            await track_group(chat, tg.id)
        return await handler(event, data)
