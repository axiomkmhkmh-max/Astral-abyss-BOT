# ============================================================
#  ASTRAL ABYSS — 👑 هندلرهای دیدار با پادشاهِ نقشه (Telegram)
# ------------------------------------------------------------
#  دکمه‌ی «🗣️ دیدار با پادشاه» تو منوی لوکیشن‌های هر نقشه (همون‌جایی
#  که «👑 چالش باس منطقه» هست) بازیکن رو می‌بره به قصرِ حاکمِ همون
#  نقشه. یه‌بار در روز آدیانسِ واقعی (Zen + شانسِ آیتم) می‌ده؛
#  بعدش فقط فلیوره، تا فارم‌کردن ممکن نباشه.
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player
from logger import log_sync
import map_kings as mk


def _fmt_cooldown(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h} ساعت و {m} دقیقه"
    return f"{m} دقیقه"


def _king_kb(map_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 عرضِ ادب دوباره", callback_data=f"king:open:{map_name}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="👋 مرخصی", callback_data=f"king:bye:{map_name}", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again", style=ButtonStyle.PRIMARY)],
    ])


def _bye_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again", style=ButtonStyle.PRIMARY)],
    ])


async def cb_king_open(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول باید بازی رو شروع کنی: /start", show_alert=True)
        return

    king = mk.get_king(map_name)
    if not king:
        await cb.answer("❌ این نقشه پادشاهی نداره.", show_alert=True)
        return

    result = mk.hold_audience(player, map_name, player.get("level", 1))
    await asave_player(uid, player)
    await cb.answer()

    lines = [
        f"{king['emoji']} **{king['title']}**",
        f"**{king['name']}**",
        f"_{king['domain']}_\n",
        f"💬 {result['greeting']}",
        f"💬 {result['tier_line']}",
    ]
    if result["lore_line"]:
        lines.append(f"\n📜 _{result['lore_line']}_")

    if result["on_cooldown"]:
        lines.append(f"\n⏳ فردا دوباره سر بزن — دیدارِ امروز رو قبلاً داشتی. ({_fmt_cooldown(result['cooldown_remaining'])} تا آدیانسِ بعدی)")
    else:
        gift_lines = []
        if result["gift_zen"]:
            gift_lines.append(f"💰 +{result['gift_zen']:,} Zen")
        if result["gift_item"]:
            item = result["gift_item"]
            gift_lines.append(f"🎁 {item.get('emoji','📦')} {item.get('name','آیتمِ ناشناخته')}")
            player.setdefault("inventory", []).append(dict(item))
            await asave_player(uid, player)
        if gift_lines:
            lines.append("\n" + "\n".join(gift_lines))
        if result["tier_up"]:
            lines.append(f"\n✨ رابطه‌ت با {king['name']} عمیق‌تر شد: {mk.tier_label(result['tier_after'])}")

    fav = mk.get_player_favor(player, map_name)
    lines.append(f"\n{mk.tier_label(result['tier_after'])} — اعتبار: {fav['favor']}/{mk.FAVOR_CAP}")

    await cb.message.answer("\n".join(lines), reply_markup=_king_kb(map_name))

    if result["gift_zen"] or result["gift_item"]:
        log_sync(
            f"👑 **KING AUDIENCE** — {player.get('name','—')} (`{uid}`) با {king['name']} ({map_name}) — "
            f"+{result['gift_zen']:,} Zen"
            + (f" + {result['gift_item'].get('name','')}" if result['gift_item'] else ""),
            "KING",
        )


async def cb_king_bye(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    king = mk.get_king(map_name)
    await cb.answer()
    if king:
        text = f"{king['title']} **{king['name']}**\n\n👋 {mk.farewell_line(map_name)}"
    else:
        text = "👋 خداحافظ!"
    await cb.message.answer(text, reply_markup=_bye_kb())


async def cmd_kings_overview(message):
    """پنلِ خلاصه‌ی دیوانِ سلطنتی: رابطه‌ت با تمامِ پادشاهانِ نقشه‌ها."""
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    rows = mk.kings_overview(player)
    lines = ["👑 **دیوانِ سلطنتی — رابطه‌ی تو با حاکمانِ نقشه‌ها**\n"]
    for r in rows:
        king = r["king"]
        ready = "🟢 آماده‌ی دیدار" if r["can_audience"] else "⏳"
        lines.append(f"{king['emoji']} **{king['name']}** ({r['map_name']}) — {r['tier_label']} ({r['favor']}/{mk.FAVOR_CAP}) {ready}")
    await message.answer("\n".join(lines))


def register_king_handlers(dp, bot):
    dp.callback_query.register(cb_king_open, F.data.startswith("king:open:"))
    dp.callback_query.register(cb_king_bye, F.data.startswith("king:bye:"))
    dp.message.register(cmd_kings_overview, Command("kings"))
