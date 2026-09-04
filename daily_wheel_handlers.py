# ============================================================
#  ASTRAL ABYSS — 🎡 هندلرهای چرخِ شانسِ روزانه (Telegram)
# ------------------------------------------------------------
#  دکمه‌ی «🎡 چرخِ شانس» تو منوی اقتصاد: یه‌بار در روز رایگان
#  می‌چرخه، جایزه می‌ده، و استریکِ روزهای پشتِ‌سرهم رو نشون می‌ده.
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import daily_wheel as dwheel
import city_markets as cmkt  # برای رِپِ رریتی و متنِ خفنِ خریدِ بالا


def _entry_kb(can_spin: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_spin:
        rows.append([InlineKeyboardButton(text="🎡 بچرخون!", callback_data="dwheel:spin", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _streak_bar(streak: int) -> str:
    """نوارِ کوچیکِ بصریِ استریک تا نزدیک‌ترین نشونه‌ی بعدی."""
    next_milestone = next((d for d in dwheel.MILESTONE_DAYS if d > streak), dwheel.MILESTONE_DAYS[-1])
    prev_milestone = 0
    for d in dwheel.MILESTONE_DAYS:
        if d <= streak:
            prev_milestone = d
    span = max(1, next_milestone - prev_milestone)
    filled = int(10 * (streak - prev_milestone) / span)
    return "▰" * filled + "▱" * (10 - filled)


async def cmd_daily_wheel(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    dw = dwheel.get_state(player)
    can = dwheel.can_spin(player)
    streak = dw.get("streak", 0)

    text = f"🎡 **چرخِ شانسِ روزانه**\n\n"
    if streak > 0:
        text += f"🔥 استریک: **{streak} روز** {_streak_bar(streak)}\n"
        next_milestone = next((d for d in dwheel.MILESTONE_DAYS if d > streak), None)
        if next_milestone:
            text += f"🏁 نشونه‌ی بعدی: روزِ {next_milestone}\n"
        bonus = min(dwheel.MAX_STREAK_BONUS, streak * dwheel.STREAK_BONUS_PER_DAY)
        text += f"💪 بونوسِ زنِ فعلی: +{int(bonus*100)}%\n"
    text += f"🎯 مجموع چرخش‌ها: {dw.get('total_spins', 0)}\n\n"

    if can:
        text += "امروز هنوز نچرخوندیش — یه بار رایگانه، بزن بریم!"
    else:
        text += f"✅ امروز چرخوندیش. رفرشِ بعدی تا **{dwheel.time_until_reset()}** دیگه."

    await msg.answer(text, reply_markup=_entry_kb(can))


async def cb_daily_wheel_spin(cb: CallbackQuery):
    uid = cb.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌", show_alert=True)
            return
        result = dwheel.spin(player)
        if not result.get("ok"):
            await cb.answer("❌ امروز قبلاً چرخوندیش.", show_alert=True)
            return
        await asave_player(uid, player)

    reward = result["reward"]
    seg = result["segment"]
    streak = result["streak"]

    await cb.answer(f"✅ {seg['label']}!")

    if reward["type"] == "zen":
        reward_line = f"💰 **{reward['amount']:,} Zen** گرفتی!"
    else:
        it = reward["item"]
        tag = cmkt.rarity_tag(it)
        reward_line = f"{it.get('emoji','📦')} **{it['name']}** {tag} گرفتی!"

    text = f"🎡 چرخ ایستاد رو: **{seg['label']}**\n\n{reward_line}"
    if result.get("reaction"):
        text += f"\n\n{result['reaction']}"

    text += f"\n\n🔥 استریک: **{streak} روز** {_streak_bar(streak)}"
    if result["streak_bonus"] > 0:
        text += f" (بونوسِ زن: +{int(result['streak_bonus']*100)}%)"

    ms = result.get("milestone_reward")
    if ms:
        mit = ms["item"]
        mtag = cmkt.rarity_tag(mit)
        text += (
            f"\n\n🏁 **نشونه‌ی روزِ {ms['streak_days']}!** یه پاداشِ ویژه هم گرفتی:\n"
            f"💰 {ms['zen']:,} Zen + {mit.get('emoji','📦')} **{mit['name']}** {mtag}"
        )

    log_sync(
        f"🎡 **DAILY WHEEL** — {player.get('name','—')} (`{uid}`) — {seg['label']} "
        f"(استریک: {streak})" + (" + نشونه" if ms else ""),
        "DAILY_WHEEL",
    )
    await cb.message.answer(text)


def register_daily_wheel_handlers(dp, bot):
    dp.message.register(cmd_daily_wheel, F.text == "🎡 چرخِ شانس")
    dp.message.register(cmd_daily_wheel, Command("wheel"))
    dp.callback_query.register(cb_daily_wheel_spin, F.data == "dwheel:spin")
