# ============================================================
#  ASTRAL ABYSS — Gap Group Gate
# ------------------------------------------------------------
#  هدف: یه سری کلمه (نه اسلش‌کامند) مثل «حمله»، «وضعیت»، «لوت» رو
#  به‌عنوان میان‌بُر ثبت می‌کنیم که فقط وقتی از یه گروهِ گپ فرستاده
#  بشن کار کنن؛ تو چتِ خصوصی (پیوی) همون کلمه فقط یادآوری می‌کنه که
#  کامندِ اسلشیِ خودش رو بزنه (چیزی که تو پیوی همیشه جواب می‌ده).
#
#  استفاده (تو هر gap_*_handlers.py):
#     from gap_group_gate import group_word
#     dp.register_message(group_word(cmd_attack, "/attack"), text="حمله")
# ============================================================
from __future__ import annotations

from gap_types import Message


def is_group_msg(msg: Message) -> bool:
    return getattr(msg.chat, "type", "private") == "group"


def group_word(handler, slash_hint: str):
    """دکوریتور: هندلرِ اصلی (همون تابعِ کامند) رو فقط وقتی پیام از یه
    گروهِ گپ اومده صدا می‌زنه. توی پیوی، به‌جاش یادآوری می‌کنه که
    کامندِ اسلشیِ `slash_hint` رو بزنه (چون تشخیصِ گروه/پیوی توی گپ
    یه heuristic هست، این‌جوری اگه اشتباه هم تشخیص بده، کاربر همیشه
    یه راهِ مطمئن برای انجامِ کار داره)."""
    async def wrapped(msg: Message):
        if is_group_msg(msg):
            return await handler(msg)
        await msg.answer(
            f"⚠️ نوشتنِ کلمه فقط توی **گروه** کار می‌کنه.\n"
            f"این‌جا (پیوی) به‌جاش از `{slash_hint}` استفاده کن."
        )
    return wrapped
