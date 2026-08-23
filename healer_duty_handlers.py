# ============================================================
#  ASTRAL ABYSS — 🩺 نوبت‌دهی — UI (healer_duty_handlers.py)
# ============================================================
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
import healer_duty as hd
import class_activity_engine as cae

BTN_TEXT = "🩺 نوبت‌دهی"

# 🩹 باگ‌فیکس: قبلاً بیمارِ در انتظار تو یه دیکشنریِ توی‌حافظه‌ی پروسه
# (_pending_patient) نگه داشته می‌شد. هر ری‌استارتِ بات (دیپلوی/کرش/
# آیدل روی Railway) این حافظه رو خالی می‌کرد — پس اگه بینِ «نمایشِ بیمار»
# و «زدنِ دکمه‌ی درمانش کن» بات یه بار ری‌استارت می‌شد، دکمه چیزی پیدا
# نمی‌کرد و پیامِ گمراه‌کننده‌ی «اول نوبت بگیر» می‌داد — حتی وقتی کاربر
# همین الان نوبت گرفته بود. حالا بیمارِ در انتظار رو رویِ خودِ سندِ
# بازیکن ذخیره می‌کنیم (class_system_data)، که هر بار با asave_player
# تو دیتابیس می‌مونه و از ری‌استارتِ بات جون سالم به در می‌بره.


def _get_pending(player: dict) -> tuple[dict | None, int | None]:
    csd = player.get("class_system_data", {})
    return csd.get("hduty_patient"), csd.get("hduty_real_target_uid")


def _set_pending(player: dict, patient: dict | None, real_target_uid: int | None) -> None:
    csd = player.setdefault("class_system_data", {})
    if patient is None:
        csd.pop("hduty_patient", None)
    else:
        csd["hduty_patient"] = patient
    if real_target_uid is None:
        csd.pop("hduty_real_target_uid", None)
    else:
        csd["hduty_real_target_uid"] = real_target_uid


def _patient_kb(has_real_option: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="💊 درمانش کن", callback_data="hduty:go", style=ButtonStyle.SUCCESS)]]
    if has_real_option:
        rows.append([InlineKeyboardButton(text="🧑‍🤝‍🧑 به‌جاش برو سراغِ یه بیمارِ واقعی", callback_data="hduty:real", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="↩️ بیمارِ بعدی", callback_data="hduty:skip", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _patient_text(player: dict, patient: dict, s: dict) -> str:
    a = patient["ailment"]
    csd = player.get("class_system_data", {})
    return (
        f"🩺 **نوبتِ بعدی**\n{'─'*22}\n"
        f"👤 بیمار: {patient['patient_name']}\n"
        f"🩹 وضعیت: {a['name']} (تیر {a['tier']})\n"
        f"🔹 فیضِ لازم: {hd.FAITH_COST_PER_PATIENT} (الان داری: {csd.get('faith',0)}/{csd.get('max_faith',0)})\n\n"
        f"{cae.status_line(s, max_actions=hd.MAX_ACTIONS, daily_max=hd.DAILY_MAX)}"
    )


async def _roll_and_store(uid: int, player: dict) -> tuple[dict, bool]:
    """بیمارِ جدید رول می‌کنه، رویِ سندِ بازیکن ذخیره می‌کنه."""
    patient = hd.roll_patient(player)
    real_target = hd.find_injured_player(uid)
    has_real = bool(real_target)
    _set_pending(player, patient, real_target.get("_uid") if has_real else None)
    await asave_player(uid, player)
    return patient, has_real


async def cmd_healer_duty(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "healer":
        await msg.answer("❌ این بخش مخصوصِ درمانگره.")
        return
    from class_abilities import tick_regen
    tick_regen(player)

    s = hd.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= hd.DAILY_MAX:
        await asave_player(uid, player)
        await msg.answer("📵 **نوبتِ امروزت پره!**\n\n" + cae.status_line(s, max_actions=hd.MAX_ACTIONS, daily_max=hd.DAILY_MAX))
        return

    patient, has_real = await _roll_and_store(uid, player)
    await msg.answer(_patient_text(player, patient, s), reply_markup=_patient_kb(has_real))


async def cb_hduty_skip(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "healer":
        await cb.answer("❌ مخصوصِ درمانگره.", show_alert=True)
        return
    s = hd.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= hd.DAILY_MAX:
        await cb.answer("📵 نوبتِ امروزت پره!", show_alert=True)
        return
    patient, has_real = await _roll_and_store(uid, player)
    await cb.message.edit_text(_patient_text(player, patient, s), reply_markup=_patient_kb(has_real))
    await cb.answer("بیمارِ بعدی رسید 🔄")


async def cb_hduty_go(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "healer":
        await cb.answer("❌ مخصوصِ درمانگره.", show_alert=True)
        return
    patient, _ = _get_pending(player)
    if not patient:
        await cb.answer("❌ اول یه نوبتِ جدید بگیر (🩺 نوبت‌دهی).", show_alert=True)
        return

    used, s = cae.use_action(hd.ACTIVITY_KEY, uid, max_actions=hd.MAX_ACTIONS, batch_reset=hd.BATCH_RESET,
                              daily_max=hd.DAILY_MAX, daily_reset=hd.DAILY_RESET)
    if not used:
        await cb.answer("📵 نوبتِ امروزت پره!", show_alert=True)
        return

    r = hd.treat_patient(uid, player, patient)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return

    _set_pending(player, None, None)
    await asave_player(uid, player)

    tag = "✅ **درمانِ موفق!**" if r["success"] else "🤏 نیمه‌موفق — بیمار بهتر شد ولی کاملاً خوب نشد."
    purge_txt = "\n🧟 مرده‌ی متحرک پاکسازی شد!" if r.get("purged") else ""
    lvl_txt = f"\n\n🎉 **لول‌آپ! سطح {r['new_level']}** 🎉" if r["leveled"] else ""
    text = f"{tag}\n💰 +{r['zen']:,} Zen | ✨ +{r['xp']} XP{purge_txt}{lvl_txt}"
    text += f"\n\n{cae.status_line(s, max_actions=hd.MAX_ACTIONS, daily_max=hd.DAILY_MAX)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🩺 بیمارِ بعدی", callback_data="hduty:next", style=ButtonStyle.PRIMARY)
    ]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_hduty_real(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "healer":
        await cb.answer("❌ مخصوصِ درمانگره.", show_alert=True)
        return
    _, real_target_uid = _get_pending(player)
    if not real_target_uid:
        await cb.answer("❌ الان بیمارِ واقعی‌ای در دسترس نیست.", show_alert=True)
        return
    target = {"_uid": real_target_uid}

    used, s = cae.use_action(hd.ACTIVITY_KEY, uid, max_actions=hd.MAX_ACTIONS, batch_reset=hd.BATCH_RESET,
                              daily_max=hd.DAILY_MAX, daily_reset=hd.DAILY_RESET)
    if not used:
        await cb.answer("📵 نوبتِ امروزت پره!", show_alert=True)
        return

    r = await hd.treat_real_player(uid, player, target)
    if not r["ok"]:
        await cb.answer(r["msg"], show_alert=True)
        return

    _set_pending(player, None, None)
    await asave_player(uid, player)

    lvl_txt = f"\n\n🎉 **لول‌آپ! سطح {r['new_level']}** 🎉" if r["leveled"] else ""
    text = (
        f"✨ **{r['target_name']}** رو واقعاً درمان کردی! ({r['cured']} برطرف شد)\n"
        f"💰 +{r['zen']:,} Zen | ✨ +{r['xp']} XP{lvl_txt}\n\n"
        f"{cae.status_line(s, max_actions=hd.MAX_ACTIONS, daily_max=hd.DAILY_MAX)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🩺 بیمارِ بعدی", callback_data="hduty:next", style=ButtonStyle.PRIMARY)
    ]])
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


async def cb_hduty_next(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or player.get("class") != "healer":
        await cb.answer("❌ مخصوصِ درمانگره.", show_alert=True)
        return
    s = hd.get_state(uid)
    if s["actions"] <= 0 or s.get("daily_used", 0) >= hd.DAILY_MAX:
        await cb.message.edit_text("📵 **نوبتِ امروزت پره!**\n\n" + cae.status_line(s, max_actions=hd.MAX_ACTIONS, daily_max=hd.DAILY_MAX))
        await cb.answer()
        return
    patient, has_real = await _roll_and_store(uid, player)
    await cb.message.edit_text(_patient_text(player, patient, s), reply_markup=_patient_kb(has_real))
    await cb.answer()


def register_healer_duty_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_healer_duty, F.text == BTN_TEXT)
    dp.callback_query.register(cb_hduty_go, F.data == "hduty:go")
    dp.callback_query.register(cb_hduty_real, F.data == "hduty:real")
    dp.callback_query.register(cb_hduty_skip, F.data == "hduty:skip")
    dp.callback_query.register(cb_hduty_next, F.data == "hduty:next")
