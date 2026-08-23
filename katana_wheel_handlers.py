# ============================================================
#  ASTRAL ABYSS — Katana Wheel Handlers (Telegram UI)
# ------------------------------------------------------------
#  دستورات: /گردونه (و /kwheel به‌عنوانِ معادلِ انگلیسی) + /کوپن <کد>
#  دکمه‌ی «🎡 گردونه‌ی کاتانا» از منوی کاتانا (kt_menu) هم به این‌جا
#  وصل می‌شه (کال‌بک kwheel_menu).
#  منطق تو katana_wheel_system.py هست — این فایل فقط UI/دکمه‌هاست.
# ============================================================
from aiogram import F, Dispatcher, Bot
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import asave_player, aget_player
from economy import bz_to_display
import katana_wheel_system as kws


# ─── کیبوردها ──────────────────────────────────────────────────

def _wheel_list_kb() -> InlineKeyboardMarkup:
    rows = []
    today = kws.get_daily_wheel_id()
    for wid in kws.WHEEL_ORDER:
        w = kws.WHEELS[wid]
        price_txt = f"{w['price']:,} {'Zen' if w['currency']=='zen' else '🔹'}"
        star = "⭐️ " if wid == today else ""
        rows.append([InlineKeyboardButton(
            text=f"{star}{w['emoji']} {w['name']} — {price_txt}",
            callback_data=f"kwheel_view:{wid}",
            style=ButtonStyle.PRIMARY if wid != today else ButtonStyle.SUCCESS,
        )])
    rows.append([InlineKeyboardButton(text="🎟️ فعال‌سازی کد کوپن", callback_data="kwheel_coupon_info", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🗡️ برگشت به کاتانا", callback_data="kt_menu", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _wheel_list_text(player: dict) -> str:
    today = kws.get_daily_wheel_id()
    today_w = kws.WHEELS[today]
    free_pulls = player.get("katana_wheel_free_pulls", 0)
    discount = player.get("katana_wheel_discount", 0)
    lines = [
        "🎡 **گردونه‌های کاتانای رلیک**\n",
        "هر گردونه یه استخرِ رتبه‌ی خاصِ خودش داره — کاتانایی که ازش می‌گیری یه سلاحِ واقعیِ قابل‌اکیپه، با افیکس و امتیازِ خودش.\n",
        f"⭐️ **گردونه‌ی ویژه‌ی امروز:** {today_w['emoji']} {today_w['name']} (۲۰٪ تخفیف روی خریدِ تکی!)\n",
        f"💰 Zen: **{bz_to_display(player.get('zen', 0))}**  |  🔹 Echo Shard: **{player.get('rift_shards', 0):,}**",
    ]
    if free_pulls:
        lines.append(f"🎁 کششِ رایگانِ باقی‌مونده: **{free_pulls}**")
    if discount:
        lines.append(f"🏷️ تخفیفِ فعال: **{int(discount*100)}٪** (روی خریدِ بعدی)")
    lines.append("")
    for wid in kws.WHEEL_ORDER:
        w = kws.WHEELS[wid]
        price_txt = f"{w['price']:,} {'Zen' if w['currency']=='zen' else 'Echo Shard 🔹'}"
        lines.append(f"{w['emoji']} **{w['name']}** — {price_txt}\n_{w['desc']}_")
    return "\n".join(lines)


def _wheel_view_kb(wheel_id: str) -> InlineKeyboardMarkup:
    w = kws.WHEELS[wheel_id]
    rows = []
    for size in kws.BUNDLE_SIZES:
        price = kws.daily_effective_price(wheel_id, w, size)
        style = ButtonStyle.SUCCESS if size == 50 else (ButtonStyle.PRIMARY if size == 1 else ButtonStyle.PRIMARY)
        tag = " 🎯 بنر تضمینی!" if size == 50 else (" (تضمین: افسانه‌ای+)" if size == 10 else "")
        rows.append([InlineKeyboardButton(
            text=f"🎲 x{size} — {price:,} {'Zen' if w['currency']=='zen' else '🔹'}{tag}",
            callback_data=f"kwheel_pull:{wheel_id}:{size}",
            style=style,
        )])
    rows.append([InlineKeyboardButton(text="🔙 لیستِ گردونه‌ها", callback_data="kwheel_menu", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _wheel_view_text(player: dict, wheel_id: str) -> str:
    w = kws.WHEELS[wheel_id]
    st = player.get("katana_wheel_state", {}).get(wheel_id, {"total_pulls": 0, "since_featured": 0, "since_banner": 0})
    featured = w["featured_tier"]
    f_info = kws.TIER_INFO[featured]
    pool_labels = " / ".join(
        f"{kws.TIER_INFO[t]['emoji']} {kws.TIER_INFO[t]['label']} ({wt}٪)"
        for t, wt in zip(w["tier_pool"], w["tier_weights"])
    )
    banner_target = kws.BANNER_PITY_INTERVAL
    if kws.is_daily_wheel(wheel_id):
        banner_target = max(5, int(kws.BANNER_PITY_INTERVAL * (1 - kws.DAILY_BANNER_BONUS)))

    lines = [
        f"{w['emoji']} **{w['name']}**",
        f"_{w['desc']}_\n",
        f"🎲 استخرِ رتبه‌ها: {pool_labels}",
        f"🎯 رتبه‌ی تضمینی در بسته‌ی ۱۰تایی: {f_info['emoji']} {f_info['label']}",
        f"👑 بنرِ اختصاصی (تضمینی هر {banner_target} کشش): {w['banner']}\n",
        f"📊 کششِ تو با این گردونه: **{st.get('total_pulls', 0)}**",
        f"⏳ تا بنرِ تضمینیِ بعدی: **{max(0, banner_target - st.get('since_banner', 0))}** کشش",
    ]
    if kws.is_daily_wheel(wheel_id):
        lines.append(f"\n⭐️ امروز گردونه‌ی ویژه‌ست: {int(kws.DAILY_DISCOUNT*100)}٪ تخفیف روی x1 + بنرِ زودتر!")
    lines.append("\nمثلِ بسته‌های عملیاتیِ کالاف: هرچی بسته بزرگ‌تر بخری، تخفیفِ واحد بیشتره و تضمینِ رتبه‌ی بالاتر داری.")
    return "\n".join(lines)


async def _safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            await cb.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")


# ─── هندلرها ──────────────────────────────────────────────────

async def cmd_kwheel(msg: Message):
    uid = msg.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("character"):
        await msg.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!")
        return
    await msg.answer(_wheel_list_text(player), reply_markup=_wheel_list_kb(), parse_mode="Markdown")


async def cb_kwheel_menu(cb: CallbackQuery):
    uid = cb.from_user.id
    player = await aget_player(uid)
    if not player or not player.get("character"):
        await cb.answer("⚠️ اول باید یه کاراکتر انتخاب کنی!", show_alert=True)
        return
    await cb.answer()
    await _safe_edit(cb, _wheel_list_text(player), _wheel_list_kb())


async def cb_kwheel_view(cb: CallbackQuery):
    uid = cb.from_user.id
    wheel_id = cb.data.split(":", 1)[1]
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return
    if wheel_id not in kws.WHEELS:
        await cb.answer("❌ این گردونه پیدا نشد.", show_alert=True)
        return
    await cb.answer()
    await _safe_edit(cb, _wheel_view_text(player, wheel_id), _wheel_view_kb(wheel_id))


async def cb_kwheel_pull(cb: CallbackQuery):
    uid = cb.from_user.id
    _, wheel_id, size_s = cb.data.split(":")
    size = int(size_s)
    player = await aget_player(uid)
    if not player:
        await cb.answer("❌", show_alert=True)
        return

    ok, err, results, meta = kws.pull_wheel(player, wheel_id, size)
    if not ok:
        await cb.answer(err, show_alert=True)
        return

    await asave_player(uid, player)

    w = kws.WHEELS[wheel_id]
    try:
        from logger import log_sync
        log_sync(
            f"🎡 **KATANA WHEEL PULL**\n👤 {player.get('name','—')} (`{uid}`)\n"
            f"🎰 گردونه: {w['name']} x{size} ({meta['price_paid']:,} {meta['currency']})\n"
            f"🎲 نتایج:\n" + "\n".join(f"  • {r['label']}" for r in results),
            "ECONOMY",
        )
    except Exception:
        pass

    lines = [f"🎉 **{w['emoji']} {w['name']} — x{size} باز شد!**\n"]
    if meta.get("banner_hit"):
        lines.append(f"👑 **تبریک! کاتانای بنرِ اختصاصی گرفتی: {w['banner']}**\n")
    for r in results:
        tag = " 👑" if r["is_banner"] else ""
        lines.append(f"• {r['label']}{tag}")
    lines.append("")
    if meta.get("free_used"):
        lines.append(f"🎁 {meta['free_used']} تا از این کشش‌ها رایگان بود.")
    if meta.get("discount_applied"):
        lines.append("🏷️ کدِ تخفیفت مصرف شد.")
    lines.append(f"💰 موجودی: **{bz_to_display(player.get('zen', 0))}**  |  🔹 {player.get('rift_shards', 0):,}")

    await cb.answer("🎉 گردونه چرخید!", show_alert=False)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 دوباره همین گردونه", callback_data=f"kwheel_view:{wheel_id}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 لیستِ گردونه‌ها", callback_data="kwheel_menu", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text="🏠 پنل اصلی", callback_data="menu:home", style=ButtonStyle.PRIMARY)],
    ])
    await _safe_edit(cb, "\n".join(lines), kb)


async def cb_kwheel_coupon_info(cb: CallbackQuery):
    await cb.answer()
    text = (
        "🎟️ **فعال‌سازی کد کوپن**\n\n"
        "برای فعال‌کردنِ کدِ تخفیف یا کششِ رایگان، این دستور رو بفرست:\n"
        "`/کوپن CODE`\n\n"
        "مثال: `/کوپن KATANA10`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 لیستِ گردونه‌ها", callback_data="kwheel_menu", style=ButtonStyle.PRIMARY)],
    ])
    await _safe_edit(cb, text, kb)


async def cmd_kcoupon(msg: Message):
    uid = msg.from_user.id
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await msg.answer("🎟️ استفاده: `/کوپن CODE`\nمثال: `/کوپن KATANA10`", parse_mode="Markdown")
        return
    code = parts[1].strip()
    player = await aget_player(uid)
    if not player:
        await msg.answer("❌ اول باید تو بازی ثبت‌نام کرده باشی.")
        return
    ok, result_msg = kws.redeem_coupon(player, code)
    if ok:
        await asave_player(uid, player)
    await msg.answer(result_msg)


def register_katana_wheel_handlers(dp: Dispatcher, bot: Bot):
    # نکته: تلگرام برای entity واقعیِ "bot_command" فقط حروفِ لاتین/عدد/آندرلاین
    # رو قبول می‌کنه، پس دستورِ فارسی مثلِ "/گردونه" به‌عنوانِ Command شناخته
    # نمی‌شه — به‌همین‌خاطر برای نسخه‌ی فارسی از فیلترِ متنی (startswith)
    # استفاده می‌کنیم، و /kwheel و /coupon (لاتین) به‌عنوانِ دستورِ رسمی ثبت می‌شن.
    dp.message.register(cmd_kwheel, Command("kwheel"))
    dp.message.register(cmd_kwheel, F.text.startswith("/گردونه"))
    dp.message.register(cmd_kcoupon, Command("coupon"))
    dp.message.register(cmd_kcoupon, F.text.startswith("/کوپن"))

    dp.callback_query.register(cb_kwheel_menu, F.data == "kwheel_menu")
    dp.callback_query.register(cb_kwheel_view, F.data.startswith("kwheel_view:"))
    dp.callback_query.register(cb_kwheel_pull, F.data.startswith("kwheel_pull:"))
    dp.callback_query.register(cb_kwheel_coupon_info, F.data == "kwheel_coupon_info")
