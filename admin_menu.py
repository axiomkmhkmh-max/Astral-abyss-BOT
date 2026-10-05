# ============================================================
#  ASTRAL ABYSS — منوی کاملِ پنل ادمین (دسته‌بندی‌شده، همه‌ی کامندها دکمه)
# ------------------------------------------------------------
#  هر دکمه یکی از این کارهاست:
#    • اجرای مستقیمِ یه کامند (مثلاً /banlist)
#    • پرسیدنِ ورودی از ادمین (مثلاً آیدی پلیر) و بعد اجرای کامند با همون ورودی
#    • باز کردنِ یکی از صفحه‌های قدیمیِ پنل (آمار، اقتصاد، املاک، ...)
#
#  دکمه‌ها هیچ منطقِ جدیدی ندارن: «متنِ کامند» رو مثلِ اینکه خودِ ادمین
#  تایپ کرده باشه به همون هندلرهای قبلی می‌دن؛ پس چک‌ها و تاییدِ
#  کارهای خطرناک (مثلِ /resetall) دقیقاً مثلِ قبل کار می‌کنه.
#
#  برای اضافه‌کردنِ یه کامندِ جدید فقط یه خط به CATEGORIES اضافه کن.
# ============================================================
from __future__ import annotations

import time

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update,
)

PREFIX = "am"                 # callback_data = am:<action>[:...]
PENDING_TTL = 180             # ثانیه — اگه ادمین ورودی نفرستاد، منقضی می‌شه
ROW_WIDTH = 2

# هر آیتم: (برچسبِ دکمه، نوع، مقدار، راهنمای ورودی)
#   نوع "cmd"  → مقدار = کامند؛ اگه راهنمای ورودی خالی نباشه، اول ازت ورودی می‌گیره
#   نوع "cb"   → مقدار = callback_data یکی از صفحه‌های قدیمیِ پنل
CATEGORIES = [
    ("👤 مدیریت پلیر", [
        ("🔍 اطلاعات + ویرایش", "cmd", "/info",         "آیدیِ عددیِ پلیر رو بفرست:"),
        ("🔎 جست‌وجو",           "cmd", "/find",         "نام یا یوزرنیمِ پلیر رو بفرست:"),
        ("📝 یادداشت",           "cmd", "/note",         "بفرست: `<آیدی> <متن>`\n(برای پاک‌کردن متن رو `-` بذار)"),
        ("🚫 بن",                "cmd", "/ban",          "بفرست: `<آیدی> [دلیل]`"),
        ("✅ آنبن",              "cmd", "/unban",        "آیدیِ عددیِ پلیر رو بفرست:"),
        ("📃 لیست بن‌شده‌ها",    "cmd", "/banlist",      None),
        ("🔄 ریستِ کاملِ پلیر",  "cmd", "/playerreset",  "بفرست: `<آیدی>` یا `<آیدی> newchar`\n(newchar = کاراکترِ جدید هم می‌گیره)"),
        ("☢️ ریستِ همه‌ی پلیرها", "cmd", "/resetall",     None),
    ]),
    ("🎁 پاداش و آیتم", [
        ("💰 دادنِ Zen",         "cmd", "/givezen",      "بفرست: `<آیدی> <مقدار>`"),
        ("💸 کم‌کردنِ Zen",      "cmd", "/remgold",      "بفرست: `<آیدی> <مقدار>`"),
        ("✨ دادنِ XP",          "cmd", "/givexp",       "بفرست: `<آیدی> <مقدار>`"),
        ("⭐ تنظیمِ لول",        "cmd", "/setlevel",     "بفرست: `<آیدی> <لول> [تعداد لوت=3]`"),
        ("❤️ تنظیمِ HP",         "cmd", "/sethp",        "بفرست: `<آیدی> <عدد>`"),
        ("🎴 دادنِ کاراکتر",     "cmd", "/chargrant",    "بفرست: `<آیدی> <نام کاراکتر>`"),
        ("🔱 دادنِ مُهرِ الهی",  "cmd", "/blessgrant",   "بفرست: `<آیدی> <seal_id>`"),
        ("🚫 گرفتنِ مُهر",       "cmd", "/blessrevoke",  "آیدیِ عددیِ پلیر رو بفرست:"),
        ("🎒 حذفِ آیتم",         "cmd", "/remitem",      "آیدیِ عددیِ پلیر رو بفرست:"),
        ("🎟 دادنِ بتل‌پس",       "cmd", "/grantpass",    "آیدیِ عددیِ پلیر رو بفرست:"),
    ]),
    ("👥 اکشنِ گروهی", [
        ("💰 Zen به همه",        "cmd", "/massgivezen",  "بفرست: `<مقدار> [حداقل‌سطح] [حداکثرسطح]`"),
        ("✨ XP به همه",         "cmd", "/massgivexp",   "بفرست: `<مقدار> [حداقل‌سطح] [حداکثرسطح]`"),
    ]),
    ("📢 همگانی", [
        ("📨 پیام به همه‌ی بازیکن‌ها", "cmd", "/broadcast",  "متنِ پیام رو بفرست (تو پیویِ همه‌ی بازیکن‌ها می‌ره):"),
        ("📣 اعلان تو همه‌ی گروه‌ها",   "cmd", "/gbroadcast", "متنِ اعلان رو بفرست (تو همه‌ی گروه‌ها پست می‌شه):"),
    ]),
    ("👹 باس و ایونت", [
        ("👹 اسپانِ باسِ رندوم",  "cmd", "/spawnboss",    None),
        ("🎯 اسپانِ باسِ مشخص",   "cmd", "/spawnboss",    "آیدیِ باس رو بفرست (لیستش تو «لیست باس‌ها» هست):"),
        ("📜 لیست باس‌ها",        "cmd", "/bosslist",     None),
        ("💀 کشتنِ باسِ جهانی",   "cmd", "/killboss",     None),
        ("⚡ ضربانِ آبیس",        "cb",  "admin:pulse",   None),
        ("🎁 صندوقِ گنج (همین گروه)", "cmd", "/gchest",   None),
        ("🔁 ریستِ رِیدِ گروه",   "cmd", "/graid force",  None),
    ]),
    ("🛡 نظارت و آمار", [
        ("📊 آمارِ کلی",          "cb",  "admin:stats",       None),
        ("💹 سلامتِ اقتصاد",      "cb",  "admin:econ",        None),
        ("🏠 نظارتِ بر املاک",    "cb",  "admin:houses",      None),
        ("📈 بورسِ آبیس",         "cb",  "admin:exchange",    None),
        ("🏛 نظارتِ بر گیلدها",   "cb",  "admin:guilds",      None),
        ("🧾 آدیتِ تراکنش‌ها",    "cmd", "/audit",            None),
        ("🔬 آدیتِ فیلترشده",     "cmd", "/audit",            "بفرست: `<آیدی>` یا `<نوع>` یا `<آیدی> <نوع>`\n(مثلاً `bm_buy`، `auction_settle`)"),
        ("🕵️ اسکنِ مشکوک‌ها",    "cmd", "/suspects",         None),
    ]),
    ("🔧 دیباگ", [
        ("🔔 آیدی‌های ادمین",     "cb",  "admin:whoisadmin",  None),
        ("🪪 /whoami",            "cmd", "/whoami",           None),
        ("📋 راهنمای کامندها",    "cb",  "admin:help",        None),
    ]),
]

ADMIN_HEADER = "🛠 **پنل ادمین**\n\nیه دسته انتخاب کن:"

# admin_id -> (کامند، زمانِ انقضا)
_pending: dict[int, tuple[str, float]] = {}


def _btn(text: str, data: str, style=ButtonStyle.PRIMARY) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style)


def main_kb(back_cb: str | None = None) -> InlineKeyboardMarkup:
    """کیبوردِ اصلیِ پنل. back_cb = callback_dataِ دکمه‌ی «بازگشت» (اختیاری)."""
    buttons = [_btn(title, f"{PREFIX}:c:{i}") for i, (title, _items) in enumerate(CATEGORIES)]
    rows = [buttons[i:i + ROW_WIDTH] for i in range(0, len(buttons), ROW_WIDTH)]
    rows.append([_btn("📋 لیستِ نوشتاریِ کامندها", f"{PREFIX}:l")])
    if back_cb:
        rows.append([_btn("🔙 بازگشت", back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_kb(idx: int) -> InlineKeyboardMarkup:
    items = CATEGORIES[idx][1]
    buttons = []
    for j, (label, kind, value, _prompt) in enumerate(items):
        if kind == "cb":
            buttons.append(_btn(label, value))          # صفحه‌ی قدیمیِ پنل
        else:
            buttons.append(_btn(label, f"{PREFIX}:r:{idx}:{j}"))
    rows = [buttons[i:i + ROW_WIDTH] for i in range(0, len(buttons), ROW_WIDTH)]
    rows.append([_btn("🔙 دسته‌ها", f"{PREFIX}:m")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# راهنمای آرگومانِ کامندهایی که پرامپتشون بک‌تیک نداره
_ARG_HINTS = {
    "/info": "<آیدی>", "/find": "<نام یا یوزرنیم>", "/unban": "<آیدی>",
    "/blessrevoke": "<آیدی>", "/remitem": "<آیدی>", "/grantpass": "<آیدی>",
    "/broadcast": "<پیام>", "/gbroadcast": "<پیام>", "/spawnboss": "[آیدیِ باس]",
}


def commands_text() -> str:
    """لیستِ نوشتاریِ همه‌ی کامندهای ادمین (برای دکمه‌ی «لیستِ کامندها»)."""
    lines = ["📋 **همه‌ی کامندهای ادمین**", ""]
    for title, items in CATEGORIES:
        seen: set[str] = set()
        cmds = []
        for _label, kind, value, prompt in items:
            if kind != "cmd" or value in seen:
                continue
            seen.add(value)
            arg = _ARG_HINTS.get(value, "")
            if not arg and prompt and "`" in prompt:
                arg = prompt.split("`")[1]
            cmds.append(f"`{value} {arg}`".replace(" `", "`") if not arg else f"`{value} {arg}`")
        if cmds:
            lines.append(f"**{title}**")
            lines.extend(f"• {c}" for c in cmds)
            lines.append("")
    return "\n".join(lines).strip()


def register_admin_menu(dp, bot, *, is_admin_fn, back_cb_fn=None):
    """تو bot.py بعد از ساختنِ dp صدا بزن."""

    async def _run_as_typed(base: Message, admin_user, text: str):
        fake = base.model_copy(update={
            "from_user": admin_user,
            "text": text,
            "entities": None,
            "reply_markup": None,
            "reply_to_message": None,
            "caption": None,
        })
        try:
            fake = fake.as_(bot)
        except Exception:
            pass
        upd = Update(update_id=int(time.time() * 1000) % 2_000_000_000, message=fake)
        try:
            upd = upd.as_(bot)
        except Exception:
            pass
        await dp.feed_update(bot, upd)

    # ─── ورودیِ متنیِ ادمین (بعد از زدنِ یه دکمه‌ی «ورودی‌دار») ───
    def _has_pending(msg: Message) -> bool:
        u = msg.from_user
        if not u or u.id not in _pending:
            return False
        cmd, exp = _pending[u.id]
        if time.time() > exp:
            _pending.pop(u.id, None)
            return False
        if (msg.text or "").startswith("/"):
            # ادمین خودش یه کامندِ دیگه زد — منتظرِ ورودی نمی‌مونیم
            _pending.pop(u.id, None)
            return False
        return True

    @dp.message(F.text, _has_pending)
    async def on_admin_input(msg: Message):
        cmd, _exp = _pending.pop(msg.from_user.id)
        await _run_as_typed(msg, msg.from_user, f"{cmd} {msg.text.strip()}")

    # ─── دکمه‌ها ───
    @dp.callback_query(F.data.startswith(f"{PREFIX}:"))
    async def cb_admin_menu(cb: CallbackQuery):
        if not is_admin_fn(cb.from_user.id):
            await cb.answer("❌ فقط ادمین", show_alert=True)
            return
        parts = (cb.data or "").split(":")
        action = parts[1] if len(parts) > 1 else ""

        # ─ منوی اصلی
        if action == "m":
            _pending.pop(cb.from_user.id, None)
            back = back_cb_fn(cb.from_user.id) if back_cb_fn else None
            try:
                await cb.message.edit_text(ADMIN_HEADER, reply_markup=main_kb(back))
            except Exception:
                pass
            await cb.answer()
            return

        # ─ لیستِ نوشتاریِ کامندها
        if action == "l":
            try:
                await cb.message.edit_text(
                    commands_text(),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("🔙 دسته‌ها", f"{PREFIX}:m")]]))
            except Exception:
                pass
            await cb.answer()
            return

        # ─ یه دسته
        if action == "c":
            try:
                idx = int(parts[2])
                title = CATEGORIES[idx][0]
            except (IndexError, ValueError):
                await cb.answer()
                return
            try:
                await cb.message.edit_text(f"{title}\n\nیکی رو انتخاب کن:", reply_markup=category_kb(idx))
            except Exception:
                pass
            await cb.answer()
            return

        # ─ لغوِ ورودیِ منتظر
        if action == "x":
            _pending.pop(cb.from_user.id, None)
            await cb.answer("❌ لغو شد.")
            try:
                await cb.message.delete()
            except Exception:
                pass
            return

        # ─ اجرای یه آیتم
        if action == "r":
            try:
                idx, j = int(parts[2]), int(parts[3])
                _label, kind, value, prompt = CATEGORIES[idx][1][j]
            except (IndexError, ValueError):
                await cb.answer()
                return
            if kind != "cmd":
                await cb.answer()
                return
            await cb.answer()
            if prompt:
                _pending[cb.from_user.id] = (value, time.time() + PENDING_TTL)
                await cb.message.answer(
                    f"{prompt}\n\n↩️ این پیام رو **ریپلای** کن و جوابت رو بنویس.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("❌ لغو", f"{PREFIX}:x", ButtonStyle.DANGER)]]),
                )
            else:
                await _run_as_typed(cb.message, cb.from_user, value)
            return

        await cb.answer()
