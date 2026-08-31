# ============================================================
#  ASTRAL ABYSS — 🏮 هندلرهای بازارِ زنده‌ی شهر (Telegram)
# ------------------------------------------------------------
#  دکمه‌ی «🏮 بازارِ محلی» تو منوی لوکیشن‌های هر نقشه بازیکن رو
#  می‌بره به لیستِ غرفه‌های همون شهر → هر غرفه رو باز می‌کنه →
#  موجودیِ زنده و مشترک رو نشون می‌ده → خرید (با player_lock، ضدِ
#  ریسِ کالبکِ دوبل، دقیقاً طبقِ الگوی black_market_expansion_handlers).
# ============================================================
from __future__ import annotations

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import city_markets as cmkt


def _hub_kb(map_name: str) -> InlineKeyboardMarkup:
    rows = []
    for stall in cmkt.get_stalls(map_name):
        rows.append([InlineKeyboardButton(
            text=f"{stall['emoji']} {stall['name']} — {stall['title']}",
            callback_data=f"cmkt:stall:{stall['id']}:{map_name}",
            style=ButtonStyle.SUCCESS,
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— این شهر بازارِ فعالی نداره —", callback_data=f"cmkt:hub:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _stall_kb(stall_id: str, map_name: str, doc: dict) -> InlineKeyboardMarkup:
    rows = []
    for row in doc.get("stock", []):
        if row["qty_left"] <= 0:
            continue
        it = row["item"]
        rows.append([InlineKeyboardButton(
            text=f"{it.get('emoji','📦')} {it['name']} ({row['qty_left']}x) — {row['price']:,} Zen",
            callback_data=f"cmkt:buy:{stall_id}:{map_name}:{row['row_id']}",
            style=ButtonStyle.SUCCESS,
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— موجودی تموم شده، بعداً سر بزن —", callback_data=f"cmkt:stall:{stall_id}:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 لیستِ غرفه‌ها", callback_data=f"cmkt:hub:{map_name}", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_city_market_hub(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌ اول باید بازی رو شروع کنی: /start", show_alert=True)
        return
    await cb.answer()

    stalls = cmkt.get_stalls(map_name)
    text = f"🏮 **بازارِ محلیِ {map_name}**\n\n"
    if stalls:
        text += "غرفه‌های این شهر رو ببین:\n"
        for s in stalls:
            text += f"\n{s['emoji']} **{s['name']}** — {s['title']}\n_{s['desc']}_\n"
    else:
        text += "این شهر فعلاً غرفه‌ای نداره."
    await cb.message.answer(text, reply_markup=_hub_kb(map_name))


async def cb_city_market_stall(cb: CallbackQuery):
    _, _, stall_id, map_name = cb.data.split(":")
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    stall = cmkt.get_stall(stall_id)
    if not stall:
        await cb.answer("❌ این غرفه دیگه اینجا نیست.", show_alert=True)
        return
    await cb.answer()

    doc = cmkt.get_stock(stall_id, map_name)
    text = (
        f"{stall['emoji']} **{stall['title']}**\n**{stall['name']}**\n_{stall['desc']}_\n\n"
        f"💬 {cmkt.greeting_line(stall)}\n\n"
        f"💰 موجودیِ تو: **{player.get('zen', 0):,} Zen**\n\n📦 کالاها:"
    )
    await cb.message.answer(text, reply_markup=_stall_kb(stall_id, map_name, doc))


async def cb_city_market_buy(cb: CallbackQuery):
    uid = cb.from_user.id
    _, _, stall_id, map_name, row_id = cb.data.split(":")

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌", show_alert=True)
            return

        stall = cmkt.get_stall(stall_id)
        if not stall:
            await cb.answer("❌ این غرفه دیگه اینجا نیست.", show_alert=True)
            return

        doc = cmkt.get_stock(stall_id, map_name)
        row = next((r for r in doc.get("stock", []) if r["row_id"] == row_id), None)
        if not row or row["qty_left"] <= 0:
            await cb.answer("❌ این کالا دیگه موجود نیست.", show_alert=True)
            return
        price = row["price"]
        if player.get("zen", 0) < price:
            await cb.answer(f"❌ Zen کافی نداری! ({price:,} لازمه)", show_alert=True)
            return

        purchase = cmkt.buy_row(stall_id, map_name, row_id)
        if not purchase:
            await cb.answer("❌ این کالا همین الان تموم شد — یکی زودتر خریدش!", show_alert=True)
            return

        player["zen"] -= price
        player.setdefault("inventory", []).append(purchase["item"])
        await asave_player(uid, player)

    item = purchase["item"]
    flavor = cmkt.flavor_line(stall)
    await cb.answer(f"✅ {item['name']} خریداری شد!")
    log_sync(
        f"🏮 **CITY MARKET BUY** — {player.get('name','—')} (`{uid}`) از {stall['name']} ({map_name}) خرید: "
        f"{item['name']} ({price:,} Zen)",
        "CITY_MARKET",
    )

    doc = cmkt.get_stock(stall_id, map_name)
    text = f"{stall['emoji']} **{stall['title']}**\n**{stall['name']}**\n\n💬 {flavor}"
    await cb.message.answer(text, reply_markup=_stall_kb(stall_id, map_name, doc))


def register_city_market_handlers(dp, bot):
    dp.callback_query.register(cb_city_market_hub, F.data.startswith("cmkt:hub:"))
    dp.callback_query.register(cb_city_market_stall, F.data.startswith("cmkt:stall:"))
    dp.callback_query.register(cb_city_market_buy, F.data.startswith("cmkt:buy:"))
