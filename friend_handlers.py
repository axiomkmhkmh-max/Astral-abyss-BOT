# ============================================================
#  ASTRAL ABYSS RPG — Friend Handlers (UI)
#  (friend_handlers.py)
# ============================================================
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import friend_system as fs
from database import aget_player
from logger import log_sync


def _friends_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 درخواست‌ها", callback_data="fr:requests", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="🎁 هدیه", callback_data="fr:giftmenu", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="📊 مقایسه", callback_data="fr:cmpmenu", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="❌ حذفِ دوست", callback_data="fr:removemenu", style=ButtonStyle.DANGER)],
    ])


async def cmd_friends(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    await msg.answer(fs.friends_list_text(player), reply_markup=_friends_kb())


async def cmd_addfriend(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی!")
        return

    arg = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_uid = msg.reply_to_message.from_user.id
    else:
        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await msg.answer("✏️ استفاده: `/addfriend @username` یا `/addfriend آیدی` — یا روی پیامِ کسی ریپلای کن.")
            return
        target_uid = fs.resolve_player_target(parts[1], uid)

    if not target_uid:
        await msg.answer("❌ همچین بازیکنی پیدا نشد.")
        return

    r = await fs.send_request(uid, target_uid)
    if not r["ok"]:
        await msg.answer(r["msg"])
        return

    if r.get("mutual"):
        await msg.answer(f"🎉 چون اونم قبلاً بهت درخواست داده بود، الان با **{r['target_name']}** دوست شدی!")
    else:
        await msg.answer(f"📤 درخواستِ دوستی برای **{r['target_name']}** فرستاده شد.")
        try:
            from bot import bot as _bot
            await _bot.send_message(
                target_uid,
                f"📥 **{player.get('name','یه بازیکن')}** بهت درخواستِ دوستی داد!\nاز «👥 دوستان» → «📥 درخواست‌ها» می‌تونی قبول/رد کنی."
            )
        except Exception:
            pass


async def cb_fr_requests(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    inn = player.get("friend_requests_in", [])
    kb_rows = []
    for rid in inn[:10]:
        rp = await aget_player(rid)
        name = rp.get("name", "—") if rp else "—"
        kb_rows.append([
            InlineKeyboardButton(text=f"✅ {name}", callback_data=f"fr:accept:{rid}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text=f"❌ {name}", callback_data=f"fr:decline:{rid}", style=ButtonStyle.DANGER),
        ])
    kb_rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="fr:back", style=ButtonStyle.PRIMARY)])
    await cb.message.edit_text(fs.requests_list_text(player), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cb.answer()


async def cb_fr_accept(cb: CallbackQuery):
    uid = cb.from_user.id
    requester_uid = int(cb.data.split(":")[2])
    r = await fs.accept_request(uid, requester_uid)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    await cb.answer(f"✅ حالا با {r['name']} دوستی!", show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text(fs.requests_list_text(player))
    try:
        from bot import bot as _bot
        p2 = await aget_player(uid)
        await _bot.send_message(requester_uid, f"🎉 **{p2.get('name','یه بازیکن')}** درخواستِ دوستیت رو قبول کرد!")
    except Exception:
        pass


async def cb_fr_decline(cb: CallbackQuery):
    uid = cb.from_user.id
    requester_uid = int(cb.data.split(":")[2])
    await fs.decline_request(uid, requester_uid)
    await cb.answer("❌ رد شد.")
    player = await aget_player(uid)
    await cb.message.edit_text(fs.requests_list_text(player))


async def cb_fr_back(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.message.edit_text(fs.friends_list_text(player), reply_markup=_friends_kb())
    await cb.answer()


def _friend_pick_kb(player: dict, prefix: str) -> InlineKeyboardMarkup | None:
    friends = player.get("friends", [])
    if not friends:
        return None
    rows = []
    from database import all_players
    all_p = all_players()
    for fid in friends[:15]:
        fp = all_p.get(str(fid))
        name = fp.get("name", "—") if fp else "—"
        rows.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}:{fid}", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="fr:back", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_fr_giftmenu(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    kb = _friend_pick_kb(player, "fr:gift")
    if not kb:
        await cb.answer("❌ هنوز دوستی نداری.", show_alert=True)
        return
    await cb.message.edit_text(f"🎁 به کدوم دوست هدیه بدی؟ (هر هدیه {fs.GIFT_AMOUNT:,} Zen)", reply_markup=kb)
    await cb.answer()


async def cb_fr_gift(cb: CallbackQuery):
    uid = cb.from_user.id
    target_uid = int(cb.data.split(":")[2])
    r = await fs.send_gift(uid, target_uid)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return
    await cb.answer(f"🎁 {r['amount']:,} Zen به {r['target_name']} فرستاده شد!", show_alert=True)
    try:
        from bot import bot as _bot
        player = await aget_player(uid)
        await _bot.send_message(target_uid, f"🎁 دوستت **{player.get('name','یه بازیکن')}** بهت {r['amount']:,} Zen هدیه داد!")
    except Exception:
        pass


async def cb_fr_cmpmenu(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    kb = _friend_pick_kb(player, "fr:cmp")
    if not kb:
        await cb.answer("❌ هنوز دوستی نداری.", show_alert=True)
        return
    await cb.message.edit_text("📊 با کدوم دوست مقایسه کنم؟", reply_markup=kb)
    await cb.answer()


async def cb_fr_cmp(cb: CallbackQuery):
    uid = cb.from_user.id
    target_uid = int(cb.data.split(":")[2])
    player = await aget_player(uid)
    other = await aget_player(target_uid)
    if not player or not other:
        await cb.answer("❌", show_alert=True)
        return
    await cb.message.edit_text(fs.compare_text(player, other), reply_markup=_friends_kb())
    await cb.answer()


async def cb_fr_removemenu(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    kb = _friend_pick_kb(player, "fr:remove")
    if not kb:
        await cb.answer("❌ هنوز دوستی نداری.", show_alert=True)
        return
    await cb.message.edit_text("❌ کدوم دوست رو حذف کنم؟", reply_markup=kb)
    await cb.answer()


async def cb_fr_remove(cb: CallbackQuery):
    uid = cb.from_user.id
    target_uid = int(cb.data.split(":")[2])
    await fs.remove_friend(uid, target_uid)
    await cb.answer("✅ حذف شد.", show_alert=True)
    player = await aget_player(uid)
    await cb.message.edit_text(fs.friends_list_text(player), reply_markup=_friends_kb())


def register_friend_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_friends, F.text == "👥 دوستان")
    dp.message.register(cmd_friends, Command("friends"))
    dp.message.register(cmd_addfriend, Command("addfriend"))

    dp.callback_query.register(cb_fr_requests, F.data == "fr:requests")
    dp.callback_query.register(cb_fr_accept, F.data.startswith("fr:accept:"))
    dp.callback_query.register(cb_fr_decline, F.data.startswith("fr:decline:"))
    dp.callback_query.register(cb_fr_back, F.data == "fr:back")
    dp.callback_query.register(cb_fr_giftmenu, F.data == "fr:giftmenu")
    dp.callback_query.register(cb_fr_gift, F.data.startswith("fr:gift:"))
    dp.callback_query.register(cb_fr_cmpmenu, F.data == "fr:cmpmenu")
    dp.callback_query.register(cb_fr_cmp, F.data.startswith("fr:cmp:"))
    dp.callback_query.register(cb_fr_removemenu, F.data == "fr:removemenu")
    dp.callback_query.register(cb_fr_remove, F.data.startswith("fr:remove:"))
