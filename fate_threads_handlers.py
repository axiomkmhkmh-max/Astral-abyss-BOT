# ============================================================
#  ASTRAL ABYSS — 🧵 هندلرهای رشته‌های سرنوشت (Telegram)
# ------------------------------------------------------------
#  دکمه‌ی «🧵 رشته‌های سرنوشت»: یه رویدادِ روایی-شخصی‌سازی‌شده در
#  روز، براساسِ وضعیتِ خودِ بازیکن (نمسیس/رزونانس/گیلد/بازارِ سیاه).
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import fate_threads as ft


def _options_kb(options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"fate:opt:{i}", style=ButtonStyle.PRIMARY)]
        for i, label in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _streak_line(streak: int) -> str:
    if streak <= 0:
        return ""
    return f"🔥 استریکِ رشته: **{streak} روز**\n"


async def cmd_fate(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    prompt = ft.get_prompt(player)
    await asave_player(uid, player)  # ممکنه یه رشته‌ی جدید انتخاب/تیکِ غیابت خورده باشه

    if prompt["status"] == "answered":
        await msg.answer(
            "🧵 امروز قبلاً تصمیمت رو گرفتی.\n"
            f"⏳ رشته‌ی بعدی تا **{prompt['reset_in'] and ft.time_until_reset()}** دیگه به‌روز می‌شه."
        )
        return

    text = f"🧵 **{prompt['arc_title']}** — مرحله‌ی {prompt['stage']}/{prompt['total_stages']}\n\n"
    if prompt.get("neglect_note"):
        text += f"{prompt['neglect_note']}\n\n"
    text += prompt["text"] + "\n\n"
    text += _streak_line(prompt["streak"])
    text += "چیکار می‌کنی؟"

    await msg.answer(text, reply_markup=_options_kb(prompt["options"]))


async def cb_fate_choice(cb: CallbackQuery):
    uid = cb.from_user.id
    try:
        idx = int(cb.data.split(":")[-1])
    except (ValueError, IndexError):
        await cb.answer("❌", show_alert=True)
        return

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌", show_alert=True)
            return
        result = ft.choose(player, idx)
        if result is None:
            await cb.answer("❌ این تصمیم دیگه معتبر نیست (شاید امروز قبلاً جواب دادی).", show_alert=True)
            return
        await asave_player(uid, player)

    await cb.answer("✅ ثبت شد")

    lines = [f"🧵 **{result['arc_title']}**", f"› {result['chosen_label']}", ""]
    if result["reward_lines"]:
        lines.append("  ".join(result["reward_lines"]))
    lines.append("")
    lines.append(_streak_line(result["streak"]).strip())

    if result["finished"]:
        fin = result["finale"]
        perk_name = "دمیج" if fin["perk_stat"] == "dmg_pct" else "اقبال/گنج‌یابی"
        lines += [
            "",
            "🏁 **رشته به پایان رسید!**",
            f"عنوانِ جدید باز شد: **{fin['title']}**",
            fin["text"],
            f"➕ بونوسِ دائمی: +{int(fin['perk_amount']*100)}% {perk_name}",
            "",
            "فردا یه رشته‌ی جدید شروع می‌شه 🧵",
        ]
        log_sync(
            f"🧵 **FATE THREAD DONE** — {cb.from_user.full_name} (`{uid}`) — "
            f"{result['arc_title']} → {fin['title']}",
            "FATE_THREADS",
        )

    await cb.message.answer("\n".join(l for l in lines if l is not None))


def register_fate_handlers(dp, bot):
    dp.message.register(cmd_fate, F.text == "🧵 رشته‌های سرنوشت")
    dp.message.register(cmd_fate, Command("fate"))
    dp.callback_query.register(cb_fate_choice, F.data.startswith("fate:opt:"))
