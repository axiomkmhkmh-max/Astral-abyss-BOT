# ============================================================
#  ASTRAL ABYSS — 👑 هندلرهای دیدار با پادشاهِ نقشه (Gap)
# ------------------------------------------------------------
#  نسخه‌ی Gap از king_handlers.py — همون منطق (شاملِ پیشکش، لطفِ
#  ویژه، لقبِ exalted و تخفیفِ بازار)، فقط با gap_types (بدون
#  ButtonStyle، طبقِ قراردادِ بقیه‌ی فایل‌های gap_*).
# ============================================================
from __future__ import annotations

from gap_dispatcher import GapDispatcher
from gap_types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import aget_player, asave_player, player_lock
from logger import log_sync
import map_kings as mk


def _fmt_cooldown(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h} ساعت و {m} دقیقه"
    return f"{m} دقیقه"


def _king_kb(map_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 عرضِ ادب دوباره", callback_data=f"king:open:{map_name}")],
        [InlineKeyboardButton(text="🎁 تقدیمِ پیشکش", callback_data=f"king:tribute_menu:{map_name}")],
        [InlineKeyboardButton(text="👋 مرخصی", callback_data=f"king:bye:{map_name}")],
        [InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again")],
    ])


def _bye_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 برگشت به نقشه", callback_data="loot:again")],
    ])


def _tribute_kb(map_name: str) -> InlineKeyboardMarkup:
    rows = []
    for key in ("small", "medium", "large"):
        label = mk.TRIBUTE_LABELS[key]
        cost = mk.tribute_cost(map_name, key)
        rows.append([InlineKeyboardButton(
            text=f"{label} — {cost:,} Zen",
            callback_data=f"king:tribute:{map_name}:{key}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 برگشت", callback_data=f"king:open:{map_name}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cb_king_open(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    uid = cb.from_user.id

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌ اول باید بازی رو شروع کنی: /start", show_alert=True)
            return

        king = mk.get_king(map_name)
        if not king:
            await cb.answer("❌ این نقشه پادشاهی نداره.", show_alert=True)
            return

        result = mk.hold_audience(player, map_name, player.get("level", 1))
        if result["gift_zen"]:
            player["zen"] = player.get("zen", 0) + result["gift_zen"]
        if result["gift_item"]:
            player.setdefault("inventory", []).append(dict(result["gift_item"]))
        await asave_player(uid, player)

    await cb.answer()

    lines = [
        f"{king['emoji']} **{king['title']}**",
        f"**{king['name']}**",
        f"_{king['domain']}_\n",
        f"💬 {result['greeting']}",
        f"💬 {result['tier_line']}",
    ]
    if result["lore_line"]:
        lines.append(f"\n📜 _{result['lore_line']}_")

    if result["on_cooldown"]:
        lines.append(f"\n⏳ فردا دوباره سر بزن — دیدارِ امروز رو قبلاً داشتی. ({_fmt_cooldown(result['cooldown_remaining'])} تا آدیانسِ بعدی)")
        lines.append("🎁 می‌تونی به‌جاش یه پیشکش تقدیم کنی تا اعتبارت بره بالا.")
    else:
        if result["royal_boon"]:
            lines.append("\n🎉 **لطفِ ویژه‌ی پادشاه!** پاداشِ امروز دوبرابر شد!")
        gift_lines = []
        if result["gift_zen"]:
            gift_lines.append(f"💰 +{result['gift_zen']:,} Zen")
        if result["gift_item"]:
            item = result["gift_item"]
            gift_lines.append(f"🎁 {item.get('emoji','📦')} {item.get('name','آیتمِ ناشناخته')}")
        if gift_lines:
            lines.append("\n" + "\n".join(gift_lines))
        if result["tier_up"]:
            lines.append(f"\n✨ رابطه‌ت با {king['name']} عمیق‌تر شد: {mk.tier_label(result['tier_after'])}")
        if result["exalted_first_time"]:
            lines.append(f"\n👑 **لقبِ ویژه دریافت کردی:** «{result['exalted_title']}»")

    fav = mk.get_player_favor(player, map_name)
    lines.append(f"\n{mk.tier_label(result['tier_after'])} — اعتبار: {fav['favor']}/{mk.FAVOR_CAP}")

    disc = mk.market_discount_mult(player, map_name)
    if disc > 0:
        lines.append(f"🏮 تخفیفِ بازارِ محلیِ این نقشه، به‌خاطرِ رابطه‌ت: {int(disc * 100)}%")

    await cb.message.answer("\n".join(lines), reply_markup=_king_kb(map_name))

    if result["gift_zen"] or result["gift_item"]:
        log_sync(
            f"👑 **KING AUDIENCE (Gap)** — {player.get('name','—')} (`{uid}`) با {king['name']} ({map_name}) — "
            f"+{result['gift_zen']:,} Zen"
            + (f" + {result['gift_item'].get('name','')}" if result['gift_item'] else "")
            + (" [BOON]" if result["royal_boon"] else ""),
            "KING",
        )


async def cb_king_bye(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    king = mk.get_king(map_name)
    await cb.answer()
    if king:
        text = f"{king['title']} **{king['name']}**\n\n👋 {mk.farewell_line(map_name)}"
    else:
        text = "👋 خداحافظ!"
    await cb.message.answer(text, reply_markup=_bye_kb())


async def cb_king_tribute_menu(cb: CallbackQuery):
    map_name = cb.data.split(":", 2)[2]
    king = mk.get_king(map_name)
    if not king:
        await cb.answer("❌ این نقشه پادشاهی نداره.", show_alert=True)
        return
    await cb.answer()

    text = (
        f"{king['emoji']} **{king['title']}**\n**{king['name']}**\n\n"
        "🎁 پیشکش تقدیم کن تا رابطه‌ت سریع‌تر عمیق‌تر بشه — این کار جایگزینِ "
        "آدیانسِ روزانه نمی‌شه، فقط تسریعش می‌کنه. هرچی اعتبارت بالاتر باشه، "
        "پیشکش‌های بعدی اعتبارِ کمتری می‌دن."
    )
    await cb.message.answer(text, reply_markup=_tribute_kb(map_name))


async def cb_king_tribute(cb: CallbackQuery):
    uid = cb.from_user.id
    _, _, map_name, tier_key = cb.data.split(":")

    async with player_lock(uid):
        player = await aget_player(uid)
        if not player:
            await cb.answer("❌ اول باید بازی رو شروع کنی: /start", show_alert=True)
            return

        king = mk.get_king(map_name)
        if not king:
            await cb.answer("❌ این نقشه پادشاهی نداره.", show_alert=True)
            return

        result = mk.offer_tribute(player, map_name, tier_key)
        if not result.get("success"):
            if result.get("reason") == "insufficient_zen":
                await cb.answer(f"❌ Zen کافی نداری! ({result['cost']:,} لازمه)", show_alert=True)
            else:
                await cb.answer("❌ این کار ممکن نیست.", show_alert=True)
            return

        await asave_player(uid, player)

    await cb.answer(f"✅ پیشکش پذیرفته شد! +{result['favor_gain']} اعتبار")

    lines = [
        f"{king['emoji']} **{king['title']}**",
        f"**{king['name']}**",
        f"\n💬 {result['line']}",
        f"\n💰 -{result['cost']:,} Zen   ⭐ +{result['favor_gain']} اعتبار",
    ]
    if result["tier_up"]:
        lines.append(f"\n✨ رابطه‌ت عمیق‌تر شد: {mk.tier_label(result['tier_after'])}")
    if result["exalted_first_time"]:
        lines.append(f"\n👑 **لقبِ ویژه دریافت کردی:** «{result['exalted_title']}»")

    fav = mk.get_player_favor(player, map_name)
    lines.append(f"\n{mk.tier_label(result['tier_after'])} — اعتبار: {fav['favor']}/{mk.FAVOR_CAP}")

    await cb.message.answer("\n".join(lines), reply_markup=_king_kb(map_name))

    log_sync(
        f"👑 **KING TRIBUTE (Gap)** — {player.get('name','—')} (`{uid}`) به {king['name']} ({map_name}) — "
        f"-{result['cost']:,} Zen / +{result['favor_gain']} اعتبار",
        "KING",
    )


async def cmd_kings_overview(message: Message):
    uid = message.from_user.id
    player = await aget_player(uid)
    if not player:
        await message.answer("❌ اول باید بازی رو شروع کنی: /start")
        return

    rows = mk.kings_overview(player)
    lines = ["👑 **دیوانِ سلطنتی — رابطه‌ی تو با حاکمانِ نقشه‌ها**\n"]
    for r in rows:
        king = r["king"]
        ready = "🟢 آماده‌ی دیدار" if r["can_audience"] else "⏳"
        lines.append(f"{king['emoji']} **{king['name']}** ({r['map_name']}) — {r['tier_label']} ({r['favor']}/{mk.FAVOR_CAP}) {ready}")

    if player.get("king_titles"):
        lines.append("\n🏅 **لقب‌های سلطنتی:**")
        for t in player["king_titles"]:
            lines.append(f"— {t}")

    await message.answer("\n".join(lines))


def register_gap_king_handlers(dp: GapDispatcher):
    dp.register_message(cmd_kings_overview, commands=["kings"])
    dp.register_callback(cb_king_open, data_startswith="king:open:")
    dp.register_callback(cb_king_bye, data_startswith="king:bye:")
    dp.register_callback(cb_king_tribute_menu, data_startswith="king:tribute_menu:")
    dp.register_callback(cb_king_tribute, data_startswith="king:tribute:")
