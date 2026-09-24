# ============================================================
#  ASTRAL ABYSS — Group-Only Gate
# ------------------------------------------------------------
#  هدف: از این به بعد، پنلِ اصلی (main_kb) و هرچیزی که باهاش بازی
#  می‌شه (دکمه‌ها/کلماتِ ساده مثل «حمله»، «وضعیت»، دسته‌ها، ...) فقط
#  توی گروه در دسترس باشه — نه توی پیوی/گپِ خصوصی با ربات.
#
#  توی پیوی فقط این‌ها آزادن:
#    • هر کامندِ اسلشی (/start, /invite, /streaks, ...)
#    • مرحله‌ی وارد کردنِ اسمِ کاراکتر (وقتی FSM state فعاله)
#  هرچیزِ دیگه (یعنی تلاش برای بازی با کلمه/دکمه توی پیوی) بلاک
#  می‌شه و به‌جاش یه پیامِ راهنما (+ حذفِ هر کیبوردِ قدیمی) می‌ره.
#
#  این به‌صورتِ یه middleware سراسریِ روی dp.message نصب می‌شه
#  (توی bot.py: dp.message.middleware(group_only_gate_middleware))،
#  پس نیازی نیست تک‌تک‌ِ هندلرهای پخش‌شده تو فایل‌های مختلف (combat,
#  shop, guild, ...) دستکاری بشن — همه‌شون قبل از رسیدن بهشون از این
#  middleware رد می‌شن.
# ============================================================
from __future__ import annotations

from aiogram.types import Message, ReplyKeyboardRemove


def is_group_chat(chat_type: str) -> bool:
    return chat_type != "private"


GROUP_ONLY_TEXT = (
    "🌑 از این به بعد بازی فقط توی **گروه** انجام می‌شه.\n\n"
    "ربات رو به گروهت اضافه کن و همون‌جا با تایپِ کلماتی مثل «حمله»، "
    "«وضعیت» یا «داستان اصلی» ادامه بده — نیازی به اسلش‌کامند یا دکمه‌ی "
    "خاصی نیست، فقط بنویس.\n\n"
    "🔗 لینکِ اضافه‌کردنِ ربات به گروه رو با /invite بگیر."
)


async def group_only_gate_middleware(handler, event: Message, data: dict):
    """میدلورِ سراسری: هر پیامِ متنیِ غیرکامند توی پیوی که وسطِ ساختِ
    کاراکتر (FSM state) هم نباشه، این‌جا متوقف می‌شه و اصلاً به هیچ
    هندلرِ دیگه‌ای (تو bot.py یا هر فایلِ دیگه) نمی‌رسه."""
    if is_group_chat(event.chat.type):
        return await handler(event, data)

    text = (event.text or "").strip()

    # کامندهای اسلشی همیشه توی پیوی مجازن (/start، /invite، ...)
    if text.startswith("/"):
        return await handler(event, data)

    # وسطِ ساختِ کاراکتر (مثلاً منتظرِ فرستادنِ اسم) — نذار گیر کنه
    state = data.get("state")
    if state is not None:
        try:
            current_state = await state.get_state()
        except Exception:
            current_state = None
        if current_state is not None:
            return await handler(event, data)

    await event.answer(GROUP_ONLY_TEXT, reply_markup=ReplyKeyboardRemove())
    return None
