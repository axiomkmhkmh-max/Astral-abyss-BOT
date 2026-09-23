# ============================================================
#  ASTRAL ABYSS — Viral Loop Handlers (UI)
#  (viral_loop_handlers.py)
#  /invite     → لینکِ شخصی + آمار + پله‌ها + دکمه‌ی اشتراک
#  /invitetop  → برترین دعوت‌کننده‌ها
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import viral_loop as vl
from database import aget_player
from referral_system import user_ref_link


def _bar(cur: int, total: int, length: int = 8) -> str:
    filled = min(length, int(length * cur / total)) if total else length
    return "▰" * filled + "▱" * (length - filled)


def _me_text(uid: int) -> str:
    st = vl.get_stats(uid)
    lines = [
        "🎁 **دعوتِ دوستان — پاداش بگیر!**",
        "",
        f"🔗 لینکِ شخصیِ تو:\n`{user_ref_link(uid)}`",
        "",
        f"👥 دعوت‌شده‌ها: **{st['joined']}**  |  ✅ فعال: **{st['activated']}**  |  ⏳ در انتظار: **{st['pending']}**",
        f"💰 مجموعِ پاداشِ دعوت: **{st['total_zen']:,} Zen**",
        "",
        f"📌 هر دوستی که با لینکِ تو به **لِوِل {vl.ACTIVATION_LEVEL}** برسه:",
        f"  • تو: 💰 {vl.INVITER_ACTIVATION_ZEN:,} Zen + ✨ {vl.INVITER_ACTIVATION_XP} XP",
        f"  • اون: 💰 {vl.INVITEE_WELCOME_ZEN} Zen + ✨ {vl.INVITEE_WELCOME_XP} XP",
        "",
        "🏆 **پله‌ها:**",
    ]
    for m in vl.MILESTONES:
        done = m["count"] in st["tiers_paid"]
        mark = "✅" if done else "🔒"
        prog = "" if done else f"  {_bar(st['activated'], m['count'])} {min(st['activated'], m['count'])}/{m['count']}"
        lines.append(f"{mark} {m['count']} دعوتِ فعال — «{m['label']}» → {m['zen']:,} Zen{prog}")
    if st["today_used"] >= vl.DAILY_ACTIVATION_CAP:
        lines.append(f"\n⏳ سقفِ پاداشِ امروز ({vl.DAILY_ACTIVATION_CAP}) پر شد؛ بقیه فردا پرداخت می‌شه.")
    return "\n".join(lines)


def _kb(uid: int) -> InlineKeyboardMarkup:
    share_row = vl.share_kb(uid).inline_keyboard[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        share_row,
        [InlineKeyboardButton(text="🏆 برترین دعوت‌کننده‌ها", callback_data="viral:top", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="viral:me")],
    ])


async def cmd_invite(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    from asyncio import to_thread
    text = await to_thread(_me_text, uid)
    await msg.answer(text, reply_markup=_kb(uid))


async def cb_me(cb: CallbackQuery):
    from asyncio import to_thread
    uid = cb.from_user.id
    text = await to_thread(_me_text, uid)
    try:
        await cb.message.edit_text(text, reply_markup=_kb(uid))
    except Exception:
        pass  # متن عوض نشده
    await cb.answer()


async def _top_text() -> str:
    from asyncio import to_thread
    rows = await to_thread(vl.top_inviters, 10)
    if not rows:
        return "🏆 هنوز کسی دعوتِ فعالی نداره — اولین نفر باش! /invite"
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 **برترین دعوت‌کننده‌ها** (فقط دعوت‌های فعال)", ""]
    for i, r in enumerate(rows):
        p = await aget_player(r["_id"])
        name = (p or {}).get("name", "—")
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} {name} — **{r['count']}** دعوتِ فعال")
    return "\n".join(lines)


async def cmd_invitetop(msg: Message):
    await msg.answer(await _top_text())


async def cb_top(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ برگشت", callback_data="viral:me")]])
    try:
        await cb.message.edit_text(await _top_text(), reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


def register_viral_loop_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_invite, Command("invite"))
    dp.message.register(cmd_invitetop, Command("invitetop"))
    dp.callback_query.register(cb_me, F.data == "viral:me")
    dp.callback_query.register(cb_top, F.data == "viral:top")
