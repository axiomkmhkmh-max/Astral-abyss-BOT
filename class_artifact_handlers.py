# ============================================================
#  ASTRAL ABYSS — Class Artifact Handlers (class_artifact_handlers.py)
# ============================================================
# دستورات: /staff /cane /ring (نمایش) + /staff_awaken /cane_awaken
# /ring_awaken (بیداری) + /artifact (تشخیص خودکار بر اساس کلاس)
# + دکمه‌های «🪄 چوب‌دستی»/«🦯 عصا»/«💍 انگشتر» تو پنلِ همون کلاس
#
# دقیقاً هم‌ساختارِ katana_handlers.py، ولی چون سه نوع آیتم داریم و
# منطقشون کاملاً یکسانه، همه‌چیز با یه پارامترِ atype جنریک نوشته شده
# (به‌جای سه بار کپی-پیستِ کامل).
# ============================================================

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_player, save_player, asave_player, aget_player
from class_artifact_core import (
    CLASS_ARTIFACT_MAP, ARTIFACT_META, TIER_BASE, AWAKENING_STAGE_NAMES,
    MATERIALS_INFO_BY_TYPE, AWAKENING_SKILLS_BY_TYPE,
    get_or_assign_artifact, calc_artifact_bonus, display_artifact_full,
    attempt_awaken_artifact, sync_artifact_capacity,
    awaken_cost, awaken_material_need, awaken_success_chance,
    bond_level_from_xp, get_bond_bonus, BOND_MAX_LEVEL, BOND_LEVEL_DESC,
)


# ─── کمکی‌های موجودی (همون منطقِ katana_handlers.py) ───────────

def _inventory_as_counts(player: dict) -> dict:
    counts = {}
    for it in player.get("inventory", []):
        n = it.get("name", "")
        key = "protection_scroll" if n == "Protection Scroll" else n
        counts[key] = counts.get(key, 0) + 1
    return counts


def _remove_items(player: dict, name_variants: set, qty: int) -> int:
    inv = player.get("inventory", [])
    removed = 0
    new_inv = []
    for it in inv:
        n = it.get("name", "")
        key = "protection_scroll" if n == "Protection Scroll" else n
        if key in name_variants and removed < qty:
            removed += 1
            continue
        new_inv.append(it)
    player["inventory"] = new_inv
    return removed


def _ensure_artifact_fields(player: dict):
    get_or_assign_artifact(player)  # اگه هنوز نداره، همین‌جا رندوم می‌سازه


def _atype_for_player(player: dict) -> str | None:
    return CLASS_ARTIFACT_MAP.get(player.get("class"))


# ─── /staff ، /cane ، /ring ، /artifact ─────────────────────────

def _menu_kb(atype: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌙 بیداری", callback_data=f"art_awaken_menu:{atype}", style=ButtonStyle.PRIMARY),
         InlineKeyboardButton(text="🔗 پیوند", callback_data=f"art_bond:{atype}", style=ButtonStyle.PRIMARY)],
    ])


async def _show_artifact(msg_or_cb, uid: int, expected_atype: str | None, is_callback: bool):
    player = await aget_player(uid)
    if not player or not player.get("class"):
        text = "⚠️ اول باید یه کلاس انتخاب کنی!"
        if is_callback:
            await msg_or_cb.answer(text, show_alert=True)
        else:
            await msg_or_cb.answer(text)
        return

    my_atype = _atype_for_player(player)
    if not my_atype:
        text = "🗡️ کلاسِ تو (ماجراجو) به‌جای این سیستم، کاتانا داره — از /katana استفاده کن."
        if is_callback:
            await msg_or_cb.answer(text, show_alert=True)
        else:
            await msg_or_cb.answer(text)
        return

    if expected_atype and my_atype != expected_atype:
        other_meta = ARTIFACT_META[my_atype]
        text = f"❌ کلاسِ تو ({ARTIFACT_META[my_atype]['class_fa']}) این آیتم رو نداره. آیتمِ خودت: {other_meta['command']}"
        if is_callback:
            await msg_or_cb.answer(text, show_alert=True)
        else:
            await msg_or_cb.answer(text)
        return

    _ensure_artifact_fields(player)
    await asave_player(uid, player)

    text = display_artifact_full(player)
    kb = _menu_kb(my_atype)
    if is_callback:
        await msg_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await msg_or_cb.answer()
    else:
        await msg_or_cb.answer(text, reply_markup=kb, parse_mode="Markdown")


async def cmd_staff(msg: Message):
    await _show_artifact(msg, msg.from_user.id, "staff", is_callback=False)


async def cmd_cane(msg: Message):
    await _show_artifact(msg, msg.from_user.id, "cane", is_callback=False)


async def cmd_ring(msg: Message):
    await _show_artifact(msg, msg.from_user.id, "ring", is_callback=False)


async def cmd_artifact(msg: Message):
    """تشخیصِ خودکار — هرکی هرچی داره نشونش می‌ده."""
    await _show_artifact(msg, msg.from_user.id, None, is_callback=False)


async def cb_art_menu(cb: CallbackQuery):
    atype = cb.data.split(":", 1)[1]
    await _show_artifact(cb, cb.from_user.id, atype, is_callback=True)


# ─── /bond → «🔗 پیوند» ─────────────────────────────────────────

def _bond_text(player: dict, atype: str) -> str:
    ident = get_or_assign_artifact(player)
    bond_xp = player.get("artifact_bond", 0)
    bond_level = player.get("artifact_bond_level", bond_level_from_xp(bond_xp))
    bonus = get_bond_bonus(bond_level)
    meta = ARTIFACT_META[atype]

    lines = [
        f"🔗 **پیوند — {ident['name']}**",
        f"سطح: **{bond_level}/{BOND_MAX_LEVEL}**  ({bond_xp} XP از تعداد کشته‌ها)",
        f"_{BOND_LEVEL_DESC.get(bond_level, '')}_",
        "",
        "📜 نردبان پیوند:",
    ]
    for lvl in sorted(BOND_LEVEL_DESC.keys()):
        mark = "✅" if bond_level >= lvl else "⬜"
        lines.append(f"{mark} سطح {lvl}: {BOND_LEVEL_DESC[lvl]}")

    lines.append("")
    lines.append("🎁 بونوس‌های فعال الان:")
    active = []
    if bonus["lifesteal"]: active.append(f"+{int(bonus['lifesteal']*100)}٪ لایف‌استیل")
    if bonus["crit"]: active.append(f"+{int(bonus['crit']*100)}٪ کریت")
    if bonus["dmg_mult"]: active.append(f"+{int(bonus['dmg_mult']*100)}٪ آسیب کلی")
    if bonus["awaken_echo"]: active.append("پژواک بیداری (شانس فعال‌سازی زودهنگام اثر ویژه‌ی تایر)")
    if bonus["soulbound"]: active.append(f"🔗 پیوند ابدی ({meta['word_fa']} از مرگ آسیب نمی‌بینه)")
    lines.append("، ".join(active) if active else "هنوز هیچ بونوسی باز نشده — بیشتر بجنگ!")

    if bond_level < BOND_MAX_LEVEL:
        need = bond_level * 50 - bond_xp
        lines.append("")
        lines.append(f"⏳ تا سطح بعد: {max(0, need)} کشته‌ی دیگه")

    return "\n".join(lines)


async def cb_art_bond(cb: CallbackQuery):
    atype = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_artifact_fields(player)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"art_menu:{atype}", style=ButtonStyle.PRIMARY)]
    ])
    await cb.message.edit_text(_bond_text(player, atype), reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


# ─── /staff_awaken ، /cane_awaken ، /ring_awaken ───────────────

def _awaken_preview_text(player: dict, atype: str) -> tuple[str, int, int]:
    ident = get_or_assign_artifact(player)
    tier = ident["tier"]
    cfg = TIER_BASE[tier]
    stage = player.get("artifact_awakening", 0)
    meta = ARTIFACT_META[atype]

    if stage >= cfg["max_awaken"]:
        text = (f"🏆 {ident['name']} ({cfg['name_fa']}) به اوج بیداریش رسیده "
                f"— مرحله‌ی {AWAKENING_STAGE_NAMES[stage]}!\nچیزی بالاتر از این براش نیست.")
        return text, -1, 0

    target = stage + 1
    from economy import bz_to_display
    cost = awaken_cost(tier, target)
    mat, qty = awaken_material_need(atype, tier, target)
    chance = awaken_success_chance(tier, target)
    info = MATERIALS_INFO_BY_TYPE[atype][mat]

    counts = _inventory_as_counts(player)
    have_mat = counts.get(mat, 0)
    have_gold = player.get("zen", 0)

    text = (
        f"🌙 **بیداری {meta['word_fa']} — {ident['name']}**\n"
        f"مرحله‌ی فعلی: {AWAKENING_STAGE_NAMES[stage]} → هدف: **{AWAKENING_STAGE_NAMES[target]}**\n\n"
        f"💰 هزینه: {bz_to_display(cost)}  (موجودی تو: {bz_to_display(have_gold)})\n"
        f"📦 نیاز: {qty}x {info['emoji']} {info['name_fa']}  (موجودی تو: {have_mat})\n"
        f"🎲 شانس موفقیت: **{int(chance*100)}٪**\n\n"
        f"🛡️ اگه طومار محافظت داشته باشی و ازش استفاده کنی، شکست باعث پس‌رفتِ سطح نمی‌شه.\n"
        f"در غیر این‌صورت، شکست یعنی یک مرحله پس‌رفت (اگه بیشتر از خفته باشه)."
    )
    return text, target, int(chance * 100)


async def _cmd_awaken(msg: Message, atype: str):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or _atype_for_player(player) != atype:
        await msg.answer("⚠️ این دستور مخصوصِ کلاسِ خودتِ نیست یا هنوز کلاس انتخاب نکردی!")
        return
    _ensure_artifact_fields(player)
    text, target, _ = _awaken_preview_text(player, atype)
    if target == -1:
        await msg.answer(text, parse_mode="Markdown")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ تلاش (بدون طومار)", callback_data=f"art_awk_go:{atype}:0", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡️ تلاش با طومار محافظت", callback_data=f"art_awk_go:{atype}:1", style=ButtonStyle.PRIMARY)],
    ])
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")


async def cmd_staff_awaken(msg: Message):
    await _cmd_awaken(msg, "staff")


async def cmd_cane_awaken(msg: Message):
    await _cmd_awaken(msg, "cane")


async def cmd_ring_awaken(msg: Message):
    await _cmd_awaken(msg, "ring")


async def cb_art_awaken_menu(cb: CallbackQuery):
    atype = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player:
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_artifact_fields(player)
    text, target, _ = _awaken_preview_text(player, atype)
    if target == -1:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"art_menu:{atype}", style=ButtonStyle.PRIMARY)]
        ])
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await cb.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ تلاش (بدون طومار)", callback_data=f"art_awk_go:{atype}:0", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🛡️ تلاش با طومار محافظت", callback_data=f"art_awk_go:{atype}:1", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"art_menu:{atype}", style=ButtonStyle.PRIMARY)],
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()


async def cb_art_awaken_go(cb: CallbackQuery):
    # data format: art_awk_go:{atype}:{0|1}
    _, atype, prot = cb.data.split(":")
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or _atype_for_player(player) != atype:
        await cb.answer("خطا!", show_alert=True)
        return
    _ensure_artifact_fields(player)

    use_protection = prot == "1"
    counts = _inventory_as_counts(player)
    gold = player.get("zen", 0)

    result = attempt_awaken_artifact(player, counts, gold, use_protection=use_protection)

    attempted = not any(k in result["message"] for k in ["کافی نداری", "نداری!", "اوج بیداری"])
    if attempted:
        player["zen"] = player.get("zen", 0) - result["gold_spent"]
        if result["material"] and result["material_spent"]:
            _remove_items(player, {result["material"]}, result["material_spent"])
        if result["protection_used"]:
            _remove_items(player, {"protection_scroll"}, 1)
        player["artifact_awakening"] = result["new_stage"]
        sync_artifact_capacity(player)

    await asave_player(uid, player)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"art_menu:{atype}", style=ButtonStyle.PRIMARY)]
    ])
    await cb.message.edit_text(result["message"], reply_markup=kb, parse_mode="Markdown")
    await cb.answer("✅" if result["success"] else "💥")


# ─── ثبت هندلرها ──────────────────────────────────────────────

def register_class_artifact_handlers(dp: Dispatcher, bot: Bot):
    dp.message.register(cmd_staff, Command("staff"))
    dp.message.register(cmd_cane, Command("cane"))
    dp.message.register(cmd_ring, Command("ring"))
    dp.message.register(cmd_artifact, Command("artifact"))

    dp.message.register(cmd_staff_awaken, Command("staff_awaken"))
    dp.message.register(cmd_cane_awaken, Command("cane_awaken"))
    dp.message.register(cmd_ring_awaken, Command("ring_awaken"))

    dp.callback_query.register(cb_art_menu, F.data.startswith("art_menu:"))
    dp.callback_query.register(cb_art_bond, F.data.startswith("art_bond:"))
    dp.callback_query.register(cb_art_awaken_menu, F.data.startswith("art_awaken_menu:"))
    dp.callback_query.register(cb_art_awaken_go, F.data.startswith("art_awk_go:"))

    # ─── دکمه‌های پنلِ کلاس (متن‌شون تو bot.py هم به CATEGORIES اضافه شده) ───
    dp.message.register(cmd_staff, F.text == "🪄 چوب‌دستی")
    dp.message.register(cmd_cane, F.text == "🦯 عصا")
    dp.message.register(cmd_ring, F.text == "💍 انگشتر")
