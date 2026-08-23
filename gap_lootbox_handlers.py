# ============================================================
#  ASTRAL ABYSS — Lootbox Handlers (Gap UI) 🎁
# ------------------------------------------------------------
#  پورتِ lootbox_handlers.py برای گپ. منطق مشترکه (lootbox_shop.py).
# ============================================================
from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import asave_player, aget_player
from economy import bz_to_display
import lootbox_shop as lbx


def _lootbox_kb() -> InlineKeyboardMarkup:
    rows = []
    for box_id in lbx.BOX_ORDER:
        box = lbx.BOXES[box_id]
        price_txt = f"{box['price']:,} {'Zen' if box['currency']=='zen' else '🔹'}"
        rows.append([InlineKeyboardButton(
            text=f"{box['emoji']} {box['name']} — {price_txt}",
            callback_data=f"lootbox_open:{box_id}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به فروشگاه", callback_data="bm:shop")])
    rows.append([InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _lootbox_text(player: dict) -> str:
    lines = [
        "🎁 **باکس‌های شانسی**\n",
        "هر باکس چند تا آیتم می‌ده: تجهیزِ واقعیِ قابل‌اکیپ، مادّه‌ی کرفت، یا لقبِ نادرِ کازمتیک.\n",
        f"💰 Zen: **{bz_to_display(player.get('zen', 0))}**  |  🔹 Echo Shard: **{player.get('rift_shards', 0):,}**\n",
    ]
    for box_id in lbx.BOX_ORDER:
        box = lbx.BOXES[box_id]
        price_txt = f"{box['price']:,} {'Zen' if box['currency']=='zen' else 'Echo Shard 🔹'}"
        lines.append(f"\n{box['emoji']} **{box['name']}** — {price_txt}\n_{box['desc']}_")
    return "".join(lines)


async def cb_lootbox_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    try:
        await cb.message.edit_text(_lootbox_text(player), reply_markup=_lootbox_kb())
    except Exception:
        await cb.message.answer(_lootbox_text(player), reply_markup=_lootbox_kb())


async def cb_lootbox_open(cb: CallbackQuery):
    uid = cb.from_user.id
    box_id = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    box = lbx.get_box(box_id)
    if not box:
        await cb.answer("❌ این باکس پیدا نشد.", show_alert=True)
        return

    ok, err, results = lbx.open_box(player, box_id)
    if not ok:
        await cb.answer(err, show_alert=True)
        return

    await asave_player(uid, player)

    from logger import log_sync
    log_sync(
        f"🎁 **LOOTBOX OPEN (GAP)**\n👤 {player.get('name','—')} (`{uid}`)\n"
        f"📦 باکس: {box['name']} ({box['price']:,} {box['currency']})\n"
        f"🎲 نتایج:\n" + "\n".join(f"  • {r['label']}" for r in results),
        "ECONOMY",
    )

    lines = [f"🎉 **{box['emoji']} {box['name']} باز شد!**\n"]
    for r in results:
        lines.append(f"• {r['label']}")
    lines.append(f"\n💰 موجودی: **{bz_to_display(player.get('zen', 0))}**  |  🔹 {player.get('rift_shards', 0):,}")

    await cb.answer("🎉 باز شد!", show_alert=False)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 باکسِ دیگه", callback_data="bm:lootbox")],
        [InlineKeyboardButton(text="🔙 برگشت به فروشگاه", callback_data="bm:shop")],
        [InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home")],
    ])
    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=kb)
    except Exception:
        await cb.message.answer("\n".join(lines), reply_markup=kb)


def register_gap_lootbox_handlers(dp: GapDispatcher):
    dp.register_callback(cb_lootbox_menu, data="bm:lootbox")
    dp.register_callback(cb_lootbox_open, data_startswith="lootbox_open:")
