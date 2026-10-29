# ============================================================
#  ASTRAL ABYSS — Progression Handlers
#  (Combat Power + World Tier + Ascension Trials)
# ------------------------------------------------------------
#  همون الگوی فایل‌های دیگه (combat_handlers.py, team_handlers.py):
#  یه register_progression_handlers(dp, bot) که تو main() صدا زده می‌شه.
#
#  دستورات جدید:
#    /power     یا دکمه‌ی «⚔️ Combat Power»  → نمایش CP و منابع قدرت
#    /worldtier یا دکمه‌ی «🌍 تیر جهان»       → وضعیت تیرهای دنیا
#    /ascend                                  → تلاش برای رد کردن Trial بعدی
# ============================================================
import random
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from combat_power import calculate_combat_power, format_cp_card, recommended_cp_for_tier
from action_lock import no_double_tap
import trial_battle as tb
from world_tiers import (
    format_tier_status, next_trial_for_player, can_attempt_trial,
    resolve_trial_attempt, ASCENSION_TRIALS, get_current_world_tier, WORLD_TIERS,
)

# ─── /power ──────────────────────────────────────────────────
async def cmd_power(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return
    await msg.answer(format_cp_card(player))

# ─── /worldtier ──────────────────────────────────────────────
async def cmd_worldtier(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    text = format_tier_status(player)
    nxt = next_trial_for_player(player)
    buttons = []
    if nxt:
        buttons.append([InlineKeyboardButton(
            text=f"⚡ تلاش برای {ASCENSION_TRIALS[nxt]['name']}",
            callback_data=f"ascend_try:{nxt}"
        , style=ButtonStyle.PRIMARY)])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await msg.answer(text, reply_markup=kb)

# ─── /ascend ─────────────────────────────────────────────────
async def cmd_ascend(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول /start بزن!")
        return

    trial_id = next_trial_for_player(player)
    if not trial_id:
        level = player.get("level", 1)
        current_tier = get_current_world_tier(player)
        if current_tier >= 6:
            await msg.answer("👑 تو همه‌ی آزمون‌های Ascension رو رد کردی! بالاترین تیر دنیا در اختیار توئه.")
        else:
            needed = min(t["min_level"] for tid, t in ASCENSION_TRIALS.items())
            await msg.answer(f"⏳ هنوز لولت برای هیچ Trial جدیدی کافی نیست. (Lv.{level})")
        return

    await _offer_trial(msg, player, trial_id)

def _trial_cp(player: dict, trial_id: str) -> tuple[int, int]:
    """(CP بازیکن، CP توصیه‌شده‌ی تیرِ بعدیِ این Trial)"""
    next_tier_num = min(
        (n for n, t in WORLD_TIERS.items() if t["ascension_required"] == trial_id),
        default=None
    )
    rec_cp = recommended_cp_for_tier(next_tier_num) if next_tier_num else 1000
    return calculate_combat_power(player), rec_cp


def _battle_kb(v: dict) -> InlineKeyboardMarkup:
    sid, i = v["sid"], v["i"]
    btn = lambda key: InlineKeyboardButton(text=tb.COUNTERS[key], callback_data=f"tba:{sid}:{i}:{key}", style=ButtonStyle.PRIMARY)
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("guard"), btn("dodge")],
        [btn("strike"), btn("reflect")],
        [InlineKeyboardButton(text="📜 قوانین", callback_data=f"tbr:{sid}:{i}", style=ButtonStyle.SUCCESS)],
    ])


async def _show_battle_or_result(msg_or_cb, player: dict, fin: dict | None = None):
    """دورِ فعلی (یا نتیجه‌ی نهایی) رو نشون می‌ده. fin اگه از قبل تموم شده باشه."""
    target_edit = None
    if isinstance(msg_or_cb, CallbackQuery):
        target_edit = msg_or_cb.message.edit_text
        target_new = msg_or_cb.message.answer
    else:
        target_new = msg_or_cb.answer
    if fin is None:
        fin = tb.settle(player)
    if fin is not None:
        await _announce_result(target_edit or target_new, player, fin)
        return fin
    v = tb.view(player)
    if v is None:
        return None
    send = target_edit or target_new
    await send(v["text"], reply_markup=_battle_kb(v))
    return None


async def _announce_result(send, player: dict, fin: dict):
    result = resolve_trial_attempt(player, fin["trial"], fin["success"])
    trial_name = ASCENSION_TRIALS[fin["trial"]]["name"]
    header = "🎉 **قبول شدی!**" if fin["success"] else "💀 **شکست خوردی!**"
    last = fin.get("last")
    extra = ""
    if last is not None and not last["ok"]:
        extra = (f"\n\n❌ دورِ آخر: {tb.MOVES[last['move']]} — جوابِ درست "
                 f"{tb.COUNTERS[last['right']]} بود.")
    await send(
        f"{header}\n\n"
        f"⚡ {trial_name}\n"
        f"🎯 جوابِ درست: {fin['hits']}/{fin['rounds']} | ❤️ جان‌های باقی‌مونده: {fin['lives']}/{fin['max_lives']}"
        f"{extra}\n\n{result['reward']}"
    )


async def _offer_trial(msg_or_cb, player: dict, trial_id: str):
    # نبردِ نیمه‌کاره: ادامه بده (نمی‌شه با ول‌کردن و شروعِ دوباره، دنباله‌ی بهتر گرفت)
    if player.get("trial_battle"):
        fin = await _show_battle_or_result(msg_or_cb, player)
        await asave_player(msg_or_cb.from_user.id, player)
        return

    ok, reason = can_attempt_trial(player, trial_id)
    trial = ASCENSION_TRIALS[trial_id]
    target = msg_or_cb.answer if isinstance(msg_or_cb, Message) else msg_or_cb.message.answer
    if not ok:
        await target(reason)
        return

    player_cp, rec_cp = _trial_cp(player, trial_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ شروع آزمون", callback_data=f"ascend_start:{trial_id}", style=ButtonStyle.SUCCESS),
        InlineKeyboardButton(text="❌ فعلاً نه", callback_data="ascend_cancel", style=ButtonStyle.DANGER),
    ]])
    await target(
        tb.briefing(trial_id, trial["name"], player_cp, rec_cp) +
        f"\n⚠️ اگه شکست بخوری: {int(trial['fail_hp_penalty']*100)}٪ از Max HP کم می‌شه "
        f"و {trial['retry_cooldown']//60} دقیقه باید صبر کنی.\n\n"
        f"آماده‌ای؟",
        reply_markup=kb
    )

async def cb_ascend_try(cb: CallbackQuery):
    trial_id = cb.data.split(":")[1]
    player = await aget_player(cb.from_user.id)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    await cb.answer()
    await _offer_trial(cb, player, trial_id)

async def cb_ascend_cancel(cb: CallbackQuery):
    await cb.answer("لغو شد.")
    try:
        await cb.message.delete()
    except Exception:
        pass

@no_double_tap()
async def cb_ascend_start(cb: CallbackQuery):
    """
    شروعِ نبردِ Trial (نبردِ مهارتی — جزئیات تو trial_battle.py).
    هیچ شانسی تو نتیجه نیست؛ CP فقط تعدادِ جان‌ها رو تعیین می‌کنه.
    """
    uid = cb.from_user.id
    trial_id = cb.data.split(":")[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if trial_id not in tb.TRIAL_BATTLES:
        await cb.answer("❌ Trial نامعتبر.", show_alert=True)
        return

    if not player.get("trial_battle"):
        ok, reason = can_attempt_trial(player, trial_id)
        if not ok:
            await cb.answer(reason, show_alert=True)
            return
        player_cp, rec_cp = _trial_cp(player, trial_id)
        tb.start_battle(player, trial_id, player_cp, rec_cp)
    await cb.answer("⚔️ نبرد شروع شد!")
    await _show_battle_or_result(cb, player)
    await asave_player(uid, player)


@no_double_tap()
async def cb_trial_answer(cb: CallbackQuery):
    uid = cb.from_user.id
    try:
        _, sid, i, counter = cb.data.split(":")
        i = int(i)
    except ValueError:
        await cb.answer()
        return
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    err, fin = tb.answer(player, sid, i, counter)
    if err:
        await cb.answer(err, show_alert=True)
        return
    await cb.answer()
    await _show_battle_or_result(cb, player, fin)
    await asave_player(uid, player)


async def cb_trial_rules(cb: CallbackQuery):
    player = await aget_player(cb.from_user.id)
    sess = (player or {}).get("trial_battle")
    if not sess:
        await cb.answer("⚠️ نبردی در جریان نیست.", show_alert=True)
        return
    await cb.answer(tb.rules_text(sess["trial"]), show_alert=True)

# ─── Register ────────────────────────────────────────────────
def register_progression_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_power,     Command("power"))
    dp.message.register(cmd_power,     F.text == "⚔️ Combat Power")
    dp.message.register(cmd_worldtier, Command("worldtier"))
    dp.message.register(cmd_worldtier, F.text == "تیر جهان")
    dp.message.register(cmd_ascend,    Command("ascend"))

    dp.callback_query.register(cb_ascend_try,    F.data.startswith("ascend_try:"))
    dp.callback_query.register(cb_ascend_start,  F.data.startswith("ascend_start:"))
    dp.callback_query.register(cb_ascend_cancel, F.data == "ascend_cancel")
    dp.callback_query.register(cb_trial_answer,  F.data.startswith("tba:"))
    dp.callback_query.register(cb_trial_rules,   F.data.startswith("tbr:"))
