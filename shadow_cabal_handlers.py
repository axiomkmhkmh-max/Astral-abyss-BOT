# ============================================================
#  ASTRAL ABYSS — 🕳 هندلرهای غارتِ محفلِ سایه (Telegram)
# ------------------------------------------------------------
#  دکمه‌ی «🕳 غارت محفل» تو منوی اجتماعی. منطقِ واقعی تو
#  shadow_cabal.py هست؛ این فایل فقط پیام/دکمه‌های تلگرام رو
#  می‌سازه و پارتنرِ تیم رو (اگه بود) خبر می‌کنه.
# ============================================================
from __future__ import annotations

import random

from aiogram import F, Bot
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import shadow_cabal as cabal


def _seal_kb(tried: list[int]) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=lbl, callback_data=f"shcabal:seal:{i}", style=ButtonStyle.PRIMARY)
        for i, lbl in enumerate(cabal.SIGIL_LABELS) if i not in tried
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _loot_kb(can_grab: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_grab:
        rows.append([InlineKeyboardButton(text="🎒 یه چیزِ دیگه هم بردار", callback_data="shcabal:grab", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🏃 فرار با غنیمتِ فعلی", callback_data="shcabal:flee", style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _alarm_bar(alarm: int) -> str:
    filled = round(alarm / 10)
    return "🟥" * filled + "⬜" * (10 - filled)


async def cmd_shadow_cabal(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    st = cabal.get_state(player)
    session = st.get("session")

    if session:
        await _send_stage(msg, player, session)
        return

    ok, reason = cabal.can_start(player)
    if not ok:
        await msg.answer(f"🕳 **غارتِ محفلِ سایه**\n\n{reason}")
        return

    partner_uid = player.get("team_partner")
    text = (
        "🕳 **غارتِ محفلِ سایه**\n\n"
        + random.choice(cabal.FLAVOR_ENTER) + "\n\n"
        "یه مهرِ سایه جلوته. اگه بازش کنی می‌تونی غارت کنی — ولی هرچی بیشتر برداری، "
        "زنگِ خطرِ محفل بیشتر می‌شه و شانسِ گیرافتادنت بالاتر می‌ره.\n"
    )
    if partner_uid:
        text += "\n👥 پارتنرِ تیمت هم باهات میاد و از سهمِ غنیمت بی‌نصیب نمی‌مونه."
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔓 شروعِ غارت", callback_data="shcabal:start", style=ButtonStyle.DANGER)
    ]])
    await msg.answer(text, reply_markup=kb)


async def cb_shadow_cabal_start(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌", show_alert=True)
            return
        ok, reason = cabal.can_start(player)
        if not ok:
            await cb.answer(reason, show_alert=True)
            return
        partner_uid = player.get("team_partner")
        session = cabal.start_heist(player, partner_uid=partner_uid)
        await asave_player(uid, player)

    await cb.answer("🕳 مهر جلوته...")
    await _send_stage(cb.message, player, session)

    if partner_uid:
        try:
            await bot.send_message(
                partner_uid,
                f"👥 {player.get('name','تیم‌میتت')} یه غارتِ محفلِ سایه رو شروع کرد و تو رو هم دیده‌بان کرده — "
                f"اگه موفق بشه، سهمت خودکار میاد."
            )
        except Exception:
            pass


async def _send_stage(msg: Message, player: dict, session: dict):
    if session["stage"] == "seal":
        text = (
            "🕳 **مهرِ محفل**\n\n"
            "یکی از نشانه‌ها رو انتخاب کن. اگه اشتباه بزنی، زنگِ خطر بالا می‌ره ولی می‌تونی دوباره امتحان کنی.\n\n"
            f"🔔 زنگِ خطر: {_alarm_bar(session['alarm'])} ({session['alarm']}٪)"
        )
        await msg.answer(text, reply_markup=_seal_kb(session["seal_tries"]))
    else:
        text = (
            "🕳 **داخلِ محفل**\n\n"
            f"تا الان {session['grabs']} بار برداشتی.\n"
            f"🔔 زنگِ خطر: {_alarm_bar(session['alarm'])} ({session['alarm']}٪)\n\n"
            "هرچی بیشتر بمونی، ریسک بیشتره — ولی غنیمت بیشتری هم می‌بری."
        )
        can_grab = session["grabs"] < cabal.MAX_GRABS and session["alarm"] < 100
        await msg.answer(text, reply_markup=_loot_kb(can_grab))


async def cb_shadow_cabal_seal(cb: CallbackQuery):
    uid = cb.from_user.id
    choice = int(cb.data.split(":")[-1])
    async with player_lock(uid):
        player = await aget_player(uid)
        session = cabal.get_state(player).get("session")
        if not player or not session or session["stage"] != "seal":
            await cb.answer("❌ جلسه‌ای در جریان نیست.", show_alert=True)
            return
        result = cabal.try_seal(player, choice)
        await asave_player(uid, player)

    if result["correct"]:
        await cb.answer("✅ باز شد!")
        await cb.message.answer(cabal.FLAVOR_CORRECT)
    else:
        await cb.answer("❌ اشتباه بود.")
        await cb.message.answer(random.choice(cabal.FLAVOR_WRONG))

    session = cabal.get_state(player)["session"]
    if session:
        await _send_stage(cb.message, player, session)
    else:
        # ⚠️ اگه اشتباهاتِ پیاپی زنگ رو صد کرده بود (نظری، فعلاً رخ نمی‌ده چون
        # فرارِ اجباری فقط تو مرحله‌ی looting چک می‌شه) — این شاخه فعلاً بی‌اثره.
        pass


async def cb_shadow_cabal_grab(cb: CallbackQuery, bot: Bot):
    uid = cb.from_user.id
    async with player_lock(uid):
        player = await aget_player(uid)
        session = cabal.get_state(player).get("session")
        if not player or not session or session["stage"] != "looting":
            await cb.answer("❌ جلسه‌ای در جریان نیست.", show_alert=True)
            return
        result = cabal.grab_loot(player)
        await asave_player(uid, player)

    if result["item"]:
        await cb.answer(f"🎒 {result['item'].get('emoji','📦')} {result['item']['name']} + {result['zen']:,} Zen")
    else:
        await cb.answer(f"🎒 فقط {result['zen']:,} Zen پیدا کردی.")

    if result["forced"]:
        await cb.message.answer("🚨 زنگِ خطر رسید به سقف — باید همین الان فرار کنی!")
        await _do_flee(cb.message, uid, bot)
        return

    session = cabal.get_state(player)["session"]
    await _send_stage(cb.message, player, session)


async def cb_shadow_cabal_flee(cb: CallbackQuery, bot: Bot):
    await _do_flee(cb.message, cb.from_user.id, bot)
    await cb.answer()


async def _do_flee(msg: Message, uid: int, bot: Bot | None):
    async with player_lock(uid):
        player = await aget_player(uid)
        session = cabal.get_state(player).get("session") if player else None
        if not player or not session:
            return
        result = cabal.resolve_escape(player)
        await asave_player(uid, player)

    if result["caught"]:
        text = (
            f"{cabal.FLAVOR_CAUGHT}\n\n"
            f"💰 فقط {result['kept_zen']:,} Zen موند (باقیش رفت)\n"
            f"📦 {len(result['kept_loot'])} آیتم موند، {result['lost_loot']} آیتم جا موند\n"
            f"🔖 تا {cabal.MARKED_SEC // 3600} ساعت نشان‌دار شدی."
        )
    else:
        lines = [f"{cabal.FLAVOR_ESCAPED}\n", f"💰 **{result['kept_zen']:,} Zen**"]
        for it in result["kept_loot"]:
            lines.append(f"{it.get('emoji','📦')} {it['name']}")
        text = "\n".join(lines)

    await msg.answer(text)
    log_sync(
        f"🕳 **SHADOW CABAL** — {player.get('name','—')} (`{uid}`) — "
        f"{'گیرافتاد' if result['caught'] else 'فرار موفق'} — "
        f"{result['grabs']} برداشت، شانسِ گیرافتادن {result['catch_chance']}٪",
        "SHADOW_CABAL",
    )

    partner_uid = result.get("partner_uid")
    if partner_uid and not result["caught"] and bot is not None:
        async with player_lock(partner_uid):
            partner = await aget_player(partner_uid)
            if partner:
                pr = cabal.grant_partner_reward(partner, result["kept_zen"], bool(result["kept_loot"]))
                await asave_player(partner_uid, partner)
        try:
            extra = f" + {pr['item'].get('emoji','📦')} {pr['item']['name']}" if pr.get("item") else ""
            await bot.send_message(
                partner_uid,
                f"👥 غارتِ محفلِ سایه‌ای که توش دیده‌بان بودی موفق شد!\n💰 {pr['zen']:,} Zen{extra}"
            )
        except Exception:
            pass


def register_shadow_cabal_handlers(dp, bot):
    dp.message.register(cmd_shadow_cabal, F.text == "🕳 غارت محفل")
    dp.callback_query.register(cb_shadow_cabal_start, F.data == "shcabal:start")
    dp.callback_query.register(cb_shadow_cabal_seal, F.data.startswith("shcabal:seal:"))
    dp.callback_query.register(cb_shadow_cabal_grab, F.data == "shcabal:grab")
    dp.callback_query.register(cb_shadow_cabal_flee, F.data == "shcabal:flee")
