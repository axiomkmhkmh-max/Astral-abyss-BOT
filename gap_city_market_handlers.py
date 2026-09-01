# ============================================================
#  ASTRAL ABYSS — 🏮 هندلرهای بازارِ زنده‌ی شهر (Gap)
# ------------------------------------------------------------
#  نسخه‌ی Gap از city_market_handlers.py — همون منطق (اعتبارِ
#  فروشنده، تخفیفِ رابطه با پادشاه، ردیفِ ✨ ویژه، چانه‌زنی)، فقط با
#  gap_types (بدون ButtonStyle)، طبقِ قراردادِ بقیه‌ی فایل‌های gap_*.
# ============================================================
from __future__ import annotations

from gap_dispatcher import GapDispatcher
from gap_types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import city_markets as cmkt


def _hub_kb(map_name: str) -> InlineKeyboardMarkup:
    rows = []
    for stall in cmkt.get_stalls(map_name):
        rows.append([InlineKeyboardButton(
            text=f"{stall['emoji']} {stall['name']} — {stall['title']}",
            callback_data=f"cmkt:stall:{stall['id']}:{map_name}",
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— این شهر بازارِ فعالی نداره —", callback_data=f"cmkt:hub:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _stall_kb(stall_id: str, map_name: str, doc: dict, player: dict) -> InlineKeyboardMarkup:
    rows = []
    for row in doc.get("stock", []):
        if row["qty_left"] <= 0:
            continue
        it = row["item"]
        price = cmkt.discounted_price(player, stall_id, map_name, row["price"])
        mark = "✨ " if row.get("special") else ""
        price_text = f"{price:,} Zen" if price == row["price"] else f"~~{row['price']:,}~~ {price:,} Zen"
        rows.append([InlineKeyboardButton(
            text=f"{mark}{it.get('emoji','📦')} {it['name']} ({row['qty_left']}x) — {price_text}",
            callback_data=f"cmkt:buy:{stall_id}:{map_name}:{row['row_id']}",
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="— موجودی تموم شده، بعداً سر بزن —", callback_data=f"cmkt:stall:{stall_id}:{map_name}")])
    rows.append([InlineKeyboardButton(text="🎭 چانه‌زنی", callback_data=f"cmkt:haggle:{stall_id}:{map_name}")])
    rows.append([InlineKeyboardButton(text="🔙 لیستِ غرفه‌ها", callback_data=f"cmkt:hub:{map_name}")])
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
    rep = cmkt.get_vendor_rep(player, stall_id)
    rep_tier = cmkt.vendor_rep_tier(rep["purchases"])
    disc = cmkt.total_discount(player, stall_id, map_name)

    text = (
        f"{stall['emoji']} **{stall['title']}**\n**{stall['name']}**\n_{stall['desc']}_\n\n"
        f"💬 {cmkt.greeting_line(stall)}\n\n"
        f"{cmkt.vendor_rep_label(rep_tier)} — {rep['purchases']} خرید از این غرفه\n"
        f"💰 موجودیِ تو: **{player.get('zen', 0):,} Zen**"
    )
    if disc > 0:
        text += f"\n🏷️ تخفیفِ فعلی: {int(disc * 100)}%"
    text += "\n\n📦 کالاها:"
    await cb.message.answer(text, reply_markup=_stall_kb(stall_id, map_name, doc, player))


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

        price = cmkt.discounted_price(player, stall_id, map_name, row["price"])
        if player.get("zen", 0) < price:
            await cb.answer(f"❌ Zen کافی نداری! ({price:,} لازمه)", show_alert=True)
            return

        purchase = cmkt.buy_row(stall_id, map_name, row_id)
        if not purchase:
            await cb.answer("❌ این کالا همین الان تموم شد — یکی زودتر خریدش!", show_alert=True)
            return

        player["zen"] -= price
        player.setdefault("inventory", []).append(purchase["item"])
        cmkt.record_purchase(player, stall_id, price)
        await asave_player(uid, player)

    item = purchase["item"]
    flavor = cmkt.flavor_line(stall)
    special_tag = "✨ " if row.get("special") else ""
    await cb.answer(f"✅ {special_tag}{item['name']} خریداری شد!")
    log_sync(
        f"🏮 **CITY MARKET BUY (Gap)** — {player.get('name','—')} (`{uid}`) از {stall['name']} ({map_name}) خرید: "
        f"{item['name']} ({price:,} Zen)",
        "CITY_MARKET",
    )

    doc = cmkt.get_stock(stall_id, map_name)
    text = f"{stall['emoji']} **{stall['title']}**\n**{stall['name']}**\n\n💬 {flavor}"
    await cb.message.answer(text, reply_markup=_stall_kb(stall_id, map_name, doc, player))


async def cb_city_market_haggle(cb: CallbackQuery):
    uid = cb.from_user.id
    _, _, stall_id, map_name = cb.data.split(":")

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌", show_alert=True)
            return

        result = cmkt.try_haggle(player, stall_id, map_name)
        if not result.get("ok"):
            if result.get("reason") == "cooldown":
                await cb.answer("⏳ همین چرخه یه‌بار چانه زدی، بعدِ رفرشِ بعدی دوباره امتحان کن.", show_alert=True)
            else:
                await cb.answer("❌ این غرفه دیگه اینجا نیست.", show_alert=True)
            return
        await asave_player(uid, player)

    stall = result["stall"]
    if result["success"]:
        await cb.answer(f"✅ چانه‌زنی موفق شد! +{int(cmkt.HAGGLE_DISCOUNT * 100)}% تخفیفِ اضافه تا چرخه‌ی بعدی.", show_alert=True)
    else:
        await cb.answer("❌ فروشنده کوتاه نیومد. شاید دفعه‌ی بعد.", show_alert=True)

    doc = cmkt.get_stock(stall_id, map_name)
    text = f"{stall['emoji']} **{stall['title']}**\n**{stall['name']}**\n\n💬 {cmkt.greeting_line(stall)}"
    await cb.message.answer(text, reply_markup=_stall_kb(stall_id, map_name, doc, player))


def register_gap_city_market_handlers(dp: GapDispatcher):
    dp.register_callback(cb_city_market_hub, data_startswith="cmkt:hub:")
    dp.register_callback(cb_city_market_stall, data_startswith="cmkt:stall:")
    dp.register_callback(cb_city_market_buy, data_startswith="cmkt:buy:")
    dp.register_callback(cb_city_market_haggle, data_startswith="cmkt:haggle:")
