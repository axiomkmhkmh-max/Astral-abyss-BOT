# ============================================================
#  ASTRAL ABYSS — منوی اصلیِ شیشه‌ای (Inline) — سبکِ NPC Ministry
# ------------------------------------------------------------
#  وقتی کسی تو گروه بنویسه «منو»، به‌جای لیستِ متنی یه پیامِ
#  این‌شکلی میاد:
#
#     سلام 👋 اسمِ بازیکن
#
#     💰 موجودی: $25,903
#     🏦 بدهی بانک: $0
#     🎫 سطح: 12 — تازه‌کار
#
#     از منوی زیر استفاده کن:
#     [ 👤 پروفایل / موجودی ]
#     [ دسته‌ی ۲ ] [ دسته‌ی ۱ ]
#     ...
#
#  - هر دکمه دقیقاً همون کاریو می‌کنه که تایپِ کلمه‌ش می‌کرد
#    (یه پیامِ متنیِ ساختگی به همون هندلرهای قبلی داده می‌شه) —
#    پس هیچ هندلرِ قدیمی‌ای دست نمی‌خوره.
#  - منو فقط برای صاحبش کار می‌کنه (آیدیش تو callback_data هست).
#  - دسته‌ها با دکمه‌ی شیشه‌ای باز می‌شن و «🔙 بازگشت» دارن.
# ============================================================
from __future__ import annotations

import time

from aiogram import F
from aiogram.enums import ButtonStyle
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update,
)

PREFIX = "mn"          # callback_data = mn:<action>:<owner_uid>[:...]

# تنظیماتِ ظاهری — هرچی خواستی عوض کن
PROFILE_BTN_TEXT = "👤 پروفایل / موجودی"
PROFILE_ACTION_TEXT = "وضعیت"          # کلمه‌ای که با زدنِ دکمه‌ی پروفایل «تایپ» می‌شه
BACK_BTN_TEXT = "🔙 بازگشت"
ADMIN_BTN_TEXT = "🛠 پنل ادمین"
MENU_ROW_WIDTH = 2                       # تعدادِ دکمه تو هر ردیف (پروفایل همیشه تمام‌عرضه)


class MenuPanel:
    def __init__(self, *, categories, level_req, visible_fn, shortcuts,
                 story_text, rank_fn, back_to_main_text="بازگشت به پنل اصلی",
                 is_admin_fn=None):
        self.categories = categories          # CATEGORIES از bot.py
        self.level_req = level_req            # LEVEL_REQUIREMENTS
        self.visible_fn = visible_fn          # visible_categories_for
        self.shortcuts = list(shortcuts)      # مثلاً ["حمله", "وضعیت", "📖 داستان اصلی"]
        self.story_text = story_text
        self.rank_fn = rank_fn                # rank_for_level(level, rebirth) -> (letter, name_fa)
        self.cat_keys = list(categories.keys())
        self.back_to_main_text = back_to_main_text
        self.is_admin_fn = is_admin_fn        # uid -> bool (دکمه‌ی پنل ادمین فقط برای ادمین‌ها)

    # ─── متنِ بالای منو ───────────────────────────────────────
    def header_text(self, player: dict | None, fallback_name: str) -> str:
        if not player:
            return f"سلام 👋 {fallback_name}\n\nاول باید کاراکترت رو بسازی! /start رو بزن."
        name = player.get("name") or fallback_name
        zen = int(player.get("zen", 0) or 0)
        debt = int(player.get("bank_debt", 0) or 0)
        level = int(player.get("level", 1) or 1)
        try:
            _letter, rank_name = self.rank_fn(level, player.get("rebirth_count", 0))
        except Exception:
            rank_name = "—"

        lines = [f"سلام 👋 **{name}**", ""]
        lines.append(f"💰 موجودی: **${zen:,}**")
        # بانکِ این بازی موجودیِ جدا نداره (کارت‌به‌کارته)؛ فقط اگه بدهی داشت نشون می‌دیم
        if debt > 0:
            lines.append(f"🏦 بدهی بانک: **${debt:,}**")
        lines.append(f"🎫 سطح: **{level}** — {rank_name}")
        lines.append("")
        lines.append("از منوی زیر استفاده کن:")
        return "\n".join(lines)

    # ─── کیبوردِ اصلی ─────────────────────────────────────────
    def main_kb(self, uid: int, player: dict | None, story_badge: bool = False) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []

        # ردیفِ اول: پروفایل (تمام‌عرض)
        rows.append([InlineKeyboardButton(
            text=PROFILE_BTN_TEXT, callback_data=f"{PREFIX}:p:{uid}", style=ButtonStyle.PRIMARY)])

        buttons: list[InlineKeyboardButton] = []

        # شورتکات‌ها (به‌جز «وضعیت» که الان دکمه‌ی پروفایل جاشو گرفته)
        for i, label in enumerate(self.shortcuts):
            if label == PROFILE_ACTION_TEXT:
                continue
            shown = label
            if story_badge and label == self.story_text:
                shown = label + " 🆕"
            buttons.append(InlineKeyboardButton(
                text=shown, callback_data=f"{PREFIX}:s:{uid}:{i}", style=ButtonStyle.PRIMARY))

        # دسته‌ها (فقط اونایی که به کلاسِ بازیکن می‌خورن)
        visible = set(self.visible_fn(player))
        for idx, key in enumerate(self.cat_keys):
            if key not in visible:
                continue
            title = self._plain_title(key)
            buttons.append(InlineKeyboardButton(
                text=title, callback_data=f"{PREFIX}:c:{uid}:{idx}", style=ButtonStyle.PRIMARY))

        for i in range(0, len(buttons), MENU_ROW_WIDTH):
            rows.append(buttons[i:i + MENU_ROW_WIDTH])

        # 🛠 دکمه‌ی پنل ادمین — فقط برای ادمین‌ها دیده می‌شه
        if self.is_admin_fn and self.is_admin_fn(uid):
            rows.append([InlineKeyboardButton(
                text=ADMIN_BTN_TEXT, callback_data=f"{PREFIX}:a:{uid}", style=ButtonStyle.DANGER)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _plain_title(self, key: str) -> str:
        """«🗺️ *ماجراجو*» → «🗺️ ماجراجو» (ستاره‌های مارک‌داون دکمه نمی‌خوان)."""
        return self.categories[key].get("title", key).replace("*", "").strip()

    # ─── کیبوردِ زیرمنوی یه دسته ──────────────────────────────
    def category_kb(self, uid: int, cat_idx: int, level: int) -> InlineKeyboardMarkup:
        key = self.cat_keys[cat_idx]
        items = self.categories[key]["buttons"]
        buttons: list[InlineKeyboardButton] = []
        for j, text in enumerate(items):
            req = self.level_req.get(text, 1)
            if level >= req:
                buttons.append(InlineKeyboardButton(
                    text=text, callback_data=f"{PREFIX}:d:{uid}:{cat_idx}:{j}",
                    style=ButtonStyle.PRIMARY))
            else:
                buttons.append(InlineKeyboardButton(
                    text=f"🔒 {text} (سطح {req})", callback_data=f"{PREFIX}:l:{uid}:{req}"))
        rows = [buttons[i:i + MENU_ROW_WIDTH] for i in range(0, len(buttons), MENU_ROW_WIDTH)]
        rows.append([InlineKeyboardButton(
            text=BACK_BTN_TEXT, callback_data=f"{PREFIX}:h:{uid}", style=ButtonStyle.PRIMARY)])
        return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────────────────────────────────────
#  ارسالِ منو (از هندلرِ «منو» صدا زده می‌شه)
# ─────────────────────────────────────────────────────────────
async def send_main_menu(panel: MenuPanel, msg, player: dict | None,
                         story_badge: bool = False, extra_text: str = ""):
    uid = msg.from_user.id
    text = panel.header_text(player, msg.from_user.first_name or "مسافر") + extra_text
    kb = panel.main_kb(uid, player, story_badge) if player else None
    await msg.reply(text, reply_markup=kb)


# ─────────────────────────────────────────────────────────────
#  هندلرِ دکمه‌ها
# ─────────────────────────────────────────────────────────────
def register_menu_panel(dp, bot, panel: MenuPanel, *, aget_player, story_badge_fn=None,
                        extra_text_fn=None):
    """تو bot.py، بعد از ساختنِ dp صدا بزن:
        register_menu_panel(dp, bot, panel, aget_player=aget_player, ...)"""

    async def _run_as_typed(cb: CallbackQuery, text: str):
        """همون پیامِ منو رو کپی می‌کنیم، فرستنده رو می‌ذاریم خودِ کاربر و متن رو
        می‌ذاریم همون کلمه‌ای که قبلاً تایپ می‌شد؛ بعد به dp می‌دیمش."""
        base = cb.message
        fake = base.model_copy(update={
            "from_user": cb.from_user,
            "text": text,
            "entities": None,
            "reply_markup": None,
            "reply_to_message": None,
            "caption": None,
        })
        try:
            fake = fake.as_(bot)
        except Exception:
            pass
        upd = Update(update_id=int(time.time() * 1000) % 2_000_000_000, message=fake)
        try:
            upd = upd.as_(bot)
        except Exception:
            pass
        await dp.feed_update(bot, upd)

    @dp.callback_query(F.data.startswith(f"{PREFIX}:"))
    async def cb_menu(cb: CallbackQuery):
        parts = (cb.data or "").split(":")
        if len(parts) < 3:
            await cb.answer()
            return
        action = parts[1]
        try:
            owner = int(parts[2])
        except ValueError:
            await cb.answer()
            return

        if cb.from_user.id != owner:
            await cb.answer("این منو مالِ تو نیست — خودت بنویس «منو» 😉", show_alert=True)
            return

        if action == "l":  # دکمه‌ی قفل
            req = parts[3] if len(parts) > 3 else "?"
            await cb.answer(f"🔒 این قابلیت از سطح {req} باز می‌شه.", show_alert=True)
            return

        # ─ پنل ادمین (چکِ ادمین‌بودن دوباره سمتِ سرور، نه فقط مخفی‌بودنِ دکمه)
        if action == "a":
            if not (panel.is_admin_fn and panel.is_admin_fn(cb.from_user.id)):
                await cb.answer("❌ فقط ادمین", show_alert=True)
                return
            from admin_menu import ADMIN_HEADER, main_kb as _admin_main_kb
            kb = _admin_main_kb(back_cb=f"{PREFIX}:h:{owner}")
            try:
                await cb.message.edit_text(ADMIN_HEADER, reply_markup=kb)
            except Exception:
                pass
            await cb.answer()
            return

        player = await aget_player(owner)
        if not player or not player.get("class"):
            await cb.answer("❌ اول باید کاراکترت رو بسازی! /start رو بزن.", show_alert=True)
            return

        # ─ پروفایل
        if action == "p":
            await cb.answer()
            await _run_as_typed(cb, PROFILE_ACTION_TEXT)
            return

        # ─ شورتکات
        if action == "s":
            try:
                text = panel.shortcuts[int(parts[3])]
            except (IndexError, ValueError):
                await cb.answer()
                return
            await cb.answer()
            await _run_as_typed(cb, text)
            return

        # ─ بازکردنِ یه دسته
        if action == "c":
            try:
                idx = int(parts[3])
                key = panel.cat_keys[idx]
            except (IndexError, ValueError):
                await cb.answer()
                return
            cat = panel.categories[key]
            only = cat.get("class_only")
            if only is not None and only != player.get("class"):
                await cb.answer("🔒 این دسته مخصوصِ کلاسِ دیگه‌ایه.", show_alert=True)
                return
            level = int(player.get("level", 1) or 1)
            title = panel._plain_title(key)
            try:
                await cb.message.edit_text(
                    f"{title}\n\nیکی رو انتخاب کن:",
                    reply_markup=panel.category_kb(owner, idx, level))
            except Exception:
                pass
            await cb.answer()
            return

        # ─ اجرای یه آیتمِ دسته
        if action == "d":
            try:
                idx, j = int(parts[3]), int(parts[4])
                text = panel.categories[panel.cat_keys[idx]]["buttons"][j]
            except (IndexError, ValueError):
                await cb.answer()
                return
            req = panel.level_req.get(text, 1)
            if int(player.get("level", 1) or 1) < req:
                await cb.answer(f"🔒 این قابلیت از سطح {req} باز می‌شه.", show_alert=True)
                return
            await cb.answer()
            await _run_as_typed(cb, text)
            return

        # ─ برگشت به منوی اصلی
        if action == "h":
            badge = bool(story_badge_fn(player)) if story_badge_fn else False
            extra = extra_text_fn(player) if extra_text_fn else ""
            text = panel.header_text(player, cb.from_user.first_name or "مسافر") + extra
            try:
                await cb.message.edit_text(text, reply_markup=panel.main_kb(owner, player, badge))
            except Exception:
                pass
            await cb.answer()
            return

        await cb.answer()
