# ============================================================
#  ASTRAL ABYSS RPG — Class Ascension Handlers (UI)
#  (class_ascension_handlers.py)
# ============================================================
# لایه‌ی UI/دکمه‌ی پنلِ «🏔 ارتقای کلاس» — منطقِ خالص تو
# class_ascension_system.py هست.
# ============================================================

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import asave_player, aget_player
import class_ascension_system as asc

BACK_BTN = InlineKeyboardButton(text="🔙 برگشت", callback_data="asc:panel", style=ButtonStyle.PRIMARY)


async def _show_panel(target, player: dict, edit: bool):
    text = asc.ascension_status_text(player)
    kb = asc.ascension_kb(player)
    if edit:
        await target.message.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def cmd_ascension(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await msg.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
        return
    if player.get("class") not in asc.ASCENSION_PATHS:
        await msg.answer("❌ این بخش فقط برای جادوگر/ماجراجو/تاجر/درمانگره.")
        return
    await _show_panel(msg, player, edit=False)


async def cb_ascension_panel(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await cb.answer("❌ اول باید کاراکترت رو بسازی!", show_alert=True)
        return
    await _show_panel(cb, player, edit=True)
    await cb.answer()


async def cb_ascension_view(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await cb.answer("❌ اول باید کاراکترت رو بسازی!", show_alert=True)
        return

    path_id = cb.data.split(":", 1)[1]
    path = asc.get_path(path_id)
    if not path or path["class"] != player.get("class"):
        await cb.answer("❌ همچین مسیری وجود نداره.", show_alert=True)
        return

    st = asc.path_requirement_status(player, path)
    lines = [
        f"{path['emoji']} **{path['name_fa']}** — {path['tagline']}\n",
        f"{path['desc']}\n",
        f"📋 شرط: {path['req_metric_label']} — {st['have']}/{st['need']} "
        f"{'✅' if st['metric_ok'] else '🔒'}",
        f"📊 لولِ لازم: {asc.ASCENSION_MIN_LEVEL} (الان لولِ {st['level']}ای) "
        f"{'✅' if st['level_ok'] else '🔒'}",
        "\n⚠️ این انتخاب **دائمیه** — بعداً قابلِ تغییر نیست.",
    ]
    text = "\n".join(lines)

    if st["eligible"]:
        kb = asc.ascension_confirm_kb(path_id)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[BACK_BTN]])

    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_ascension_confirm(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("class"):
        await cb.answer("❌ اول باید کاراکترت رو بسازی!", show_alert=True)
        return

    path_id = cb.data.split(":", 1)[1]
    r = asc.ascend(player, path_id)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return

    await asave_player(uid, player)
    path = r["path"]
    text = (
        f"🎉 **ارتقا موفق بود!**\n\n"
        f"{path['emoji']} حالا مسیرت «**{path['name_fa']}**»ه — {path['tagline']}.\n"
        f"{path['desc']}"
    )
    await cb.message.edit_text(text)
    await cb.answer("✅ ارتقا انجام شد!", show_alert=True)


async def cb_ascension_back(cb: CallbackQuery):
    await cb_ascension_panel(cb)


def register_class_ascension_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_ascension, F.text == "🏔 ارتقای کلاس")
    # ⚠️ توجه: `/ascend` قبلاً تو progression_handlers.py برای سیستمِ
    # کاملاً جداگانه‌ی «آزمونِ عروجِ ورلدتایر» رجیستر شده — عمداً همون
    # اسم استفاده نشد تا با اون تداخل نکنه.
    dp.message.register(cmd_ascension, Command("classascend"))
    dp.callback_query.register(cb_ascension_panel, F.data == "asc:panel")
    dp.callback_query.register(cb_ascension_view, F.data.startswith("asc_view:"))
    dp.callback_query.register(cb_ascension_confirm, F.data.startswith("asc_confirm:"))
    dp.callback_query.register(cb_ascension_back, F.data == "asc_back")
