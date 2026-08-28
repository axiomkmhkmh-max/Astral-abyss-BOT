# ============================================================
#  ASTRAL ABYSS RPG — Living Class Core Handlers
#  UI تلگرام برای صورت‌فلکِ کلاس‌ها (constellation_system.py = موتور/دیتا)
#  همه‌ی مسیرهای «بخون → تغییر بده → ذخیره کن» زیرِ player_lock هستن
#  (طبقِ همون قاعده‌ای که تو بقیه‌ی کدبیس داره رعایت می‌شه).
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database import aget_player, asave_player, player_lock
from logger import log_sync
import constellation_system as cs


async def cmd_core(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    if not player.get("class"):
        await msg.answer("❌ اول باید کلاستُ انتخاب کنی.")
        return
    async with player_lock(uid):
        player = await aget_player(uid)
        cs._ensure_core(player)
        await asave_player(uid, player)
    await msg.answer(cs.overview_text(player), reply_markup=cs.build_regions_kb())


async def cb_core_region(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌ اول /start بزن!", show_alert=True)
        return
    _, region, ring_s = cb.data.split(":")
    ring = int(ring_s)
    try:
        await cb.message.edit_text(cs.region_ring_text(player, region, ring),
                                    reply_markup=cs.build_region_ring_kb(player, region, ring))
    except Exception:
        pass
    await cb.answer()


async def cb_core_unlock(cb: CallbackQuery):
    uid = cb.from_user.id
    _, node_id, region, ring_s = cb.data.split(":")
    ring = int(ring_s)

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌ اول /start بزن!", show_alert=True)
            return
        ok, message = cs.unlock_node(player, node_id)
        if ok:
            await asave_player(uid, player)

    if ok:
        node = cs.CONSTELLATION[node_id]
        log_sync(
            f"🌌 **CORE UNLOCK**\n"
            f"👤 {player.get('name','—')} (`{uid}`)\n"
            f"🎯 ستاره: {node['name_fa']} ({node_id})\n"
            f"📊 ناحیه: {cs.REGIONS[node['region']]['name_fa']}"
            + (" | 🌉 عبور از مرزِ کلاسی" if node["region"] != player.get("class") else ""),
            "CORE",
        )

    await cb.answer(message, show_alert=not ok)
    if ok:
        try:
            await cb.message.edit_text(cs.region_ring_text(player, region, ring),
                                        reply_markup=cs.build_region_ring_kb(player, region, ring))
        except Exception:
            pass


async def cb_core_back_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    try:
        await cb.message.edit_text(cs.overview_text(player), reply_markup=cs.build_regions_kb())
    except Exception:
        pass
    await cb.answer()


async def cb_core_close(cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()


def register_core_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_core, F.text == "🌌 صورت‌فلکی")
    dp.message.register(cmd_core, Command("core"))
    dp.callback_query.register(cb_core_region, F.data.startswith("core_region:"))
    dp.callback_query.register(cb_core_unlock, F.data.startswith("core_unlock:"))
    dp.callback_query.register(cb_core_back_menu, F.data == "core_back_menu")
    dp.callback_query.register(cb_core_close, F.data == "core_close")
