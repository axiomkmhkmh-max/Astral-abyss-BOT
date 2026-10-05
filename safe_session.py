# ============================================================
#  SafeSession — جلوگیری از کرش/لوپِ ارورِ پارس برای پیام‌های «rich_message»
# ------------------------------------------------------------
#  تلگرام یه نوع پیامِ جدید (rich_message با جدول و دکمه) داره که مدل‌های
#  aiogram هنوز کاملش نمی‌کنن. اگه کسی روی همچین پیامی تو گروه ریپلای کنه،
#  pydantic کلِ آپدیت رو رد می‌کنه (ValidationError) و چون آپدیت تأیید
#  نمی‌شه، دوباره و دوباره از تلگرام میاد و لاگ رو پر می‌کنه.
#  اینجا قبل از پارس، کلیدِ rich_message رو از جوابِ getUpdates حذف می‌کنیم
#  (ربات به محتواش نیازی نداره؛ بقیه‌ی پیام سالم می‌مونه).
# ============================================================
import json

from aiogram.client.session.aiohttp import AiohttpSession

_DROP_KEYS = ("rich_message",)


def _strip(o):
    if isinstance(o, dict):
        for k in _DROP_KEYS:
            o.pop(k, None)
        for v in o.values():
            _strip(v)
    elif isinstance(o, list):
        for v in o:
            _strip(v)


class SafeSession(AiohttpSession):
    def check_response(self, bot, method, status_code, content):
        if type(method).__name__ == "GetUpdates" and "rich_message" in content:
            try:
                data = json.loads(content)
                _strip(data)
                content = json.dumps(data, ensure_ascii=False)
            except Exception:
                pass
        return super().check_response(bot, method, status_code, content)
