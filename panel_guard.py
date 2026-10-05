# ============================================================
#  PANEL GUARD — هر پنل فقط برای صاحبش کار کنه (تو گروه)
# ------------------------------------------------------------
#  مشکل: تو گروه، وقتی A یه پنل باز می‌کنه (مثلاً «حمله»)، B می‌تونست
#  دکمه‌هاشو بزنه و پنلِ A رو دستکاری کنه.
#
#  راه‌حلِ سراسری (بدون دست‌زدن به صدها هندلر):
#   ۱) ActorMiddleware: برای هر آپدیت، «کی داره کار می‌کنه» رو تو یه
#      contextvar نگه می‌داره.
#   ۲) record_owner(): هر پیامی که ربات تو گروه با کیبوردِ شیشه‌ای می‌فرسته،
#      صاحبش (همون actor) ثبت می‌شه.
#   ۳) PanelOwnerGuard: روی هر دکمه، اگه کسی غیر از صاحبِ پیام بزنه،
#      جلوش گرفته می‌شه — مگه اینکه دکمه جزو «پنل‌های مشترک» باشه.
#
#  اگه صاحبِ پیام ثبت نشده بود (مثلاً بعد از ری‌استارت)، به فرستنده‌ی
#  پیامی که ربات بهش ریپلای کرده برمی‌گرده؛ اگه اون هم نبود، آزاد می‌ذاره
#  (پیام‌های عمومیِ ربات مثل صندوق/باس/اعلان‌ها صاحب ندارن).
#
#  تنظیمات (متغیر محیطی، اختیاری):
#    PANEL_LOCK=0                → کلاً خاموش
#    PANEL_LOCK_EXEMPT=a,b,c     → پیشوندهای callback_data که مشترک حساب بشن
# ============================================================
from __future__ import annotations

import contextvars
import os
from collections import OrderedDict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

ENABLED = os.getenv("PANEL_LOCK", "1") != "0"
MAX_TRACKED = 30000
LOCK_ALERT = "🔒 این پنل مالِ تو نیست — خودت دستورش رو بزن!"

# پنل‌هایی که ذاتاً چندنفرهان (دوئل، تریید، دعوت، رِید، صندوقِ گروهی، ...) یا
# خودشون چکِ دسترسیِ جدا دارن. اگه با یه پیشوند شروع بشن، قفل نمی‌شن.
SHARED_PREFIXES = (
    # دوئل / پی‌وی‌پی / آرنا / تیم‌پی‌وی‌پی — طرفِ مقابل باید بتونه بزنه
    "pvp", "arena", "tp_", "teampvp", "duel",
    # دعوت و درخواست — گیرنده باید بتونه قبول/رد کنه
    "trade", "binv", "mentor", "fr:", "team:", "guild_", "gw_", "shcabal",
    # عمومیِ گروه — همه می‌تونن بزنن
    "graid", "gchest", "gtop", "boss", "rb", "raidloot", "gth_", "lg:",
    "sgt:", "sgb:", "smug_", "viral", "top:", "help",
    # چک‌های اختصاصیِ خودشون
    "admin", "padm", "am:", "mn:", "fj:", "zencheck",
)
_EXTRA = tuple(x.strip() for x in os.getenv("PANEL_LOCK_EXEMPT", "").split(",") if x.strip())

_actor: contextvars.ContextVar = contextvars.ContextVar("panel_actor_uid", default=None)
_owners: "OrderedDict[tuple[int, int], int]" = OrderedDict()

_SEND_METHODS = {
    "SendMessage", "SendPhoto", "SendAnimation", "SendVideo", "SendDocument",
    "SendAudio", "SendVoice", "SendSticker", "SendVideoNote",
}


def is_shared(data: str) -> bool:
    return data.startswith(SHARED_PREFIXES + _EXTRA)


def record_owner(method, result) -> None:
    """از session middleware صدا زده می‌شه: پیامِ تازه‌فرستاده‌شده با کیبوردِ شیشه‌ای → ثبتِ صاحب."""
    if not ENABLED:
        return
    if type(method).__name__ not in _SEND_METHODS:
        return
    if not isinstance(getattr(method, "reply_markup", None), InlineKeyboardMarkup):
        return
    actor = _actor.get()
    if actor is None:
        return
    chat = getattr(result, "chat", None)
    mid = getattr(result, "message_id", None)
    if chat is None or mid is None or chat.type == "private":
        return
    _owners[(chat.id, mid)] = actor
    _owners.move_to_end((chat.id, mid))
    while len(_owners) > MAX_TRACKED:
        _owners.popitem(last=False)


class ActorMiddleware(BaseMiddleware):
    """ثبتِ «کاربرِ فعلی» برای کلِ پردازشِ این آپدیت."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        token = _actor.set(user.id if user else None)
        try:
            return await handler(event, data)
        finally:
            _actor.reset(token)


class PanelOwnerGuard(BaseMiddleware):
    """فقط صاحبِ پنل می‌تونه دکمه‌هاشو بزنه (تو گروه‌ها)."""

    async def __call__(self, handler, event: CallbackQuery, data):
        if ENABLED and isinstance(event, CallbackQuery):
            msg = event.message
            cdata = event.data or ""
            chat = getattr(msg, "chat", None)
            if msg is not None and chat is not None and chat.type != "private" and cdata and not is_shared(cdata):
                owner = _owners.get((chat.id, msg.message_id))
                if owner is None:
                    reply = getattr(msg, "reply_to_message", None)
                    ru = getattr(reply, "from_user", None) if reply else None
                    if ru is not None and not ru.is_bot:
                        owner = ru.id
                if owner is not None and owner != event.from_user.id:
                    await event.answer(LOCK_ALERT, show_alert=True)
                    return
        return await handler(event, data)
