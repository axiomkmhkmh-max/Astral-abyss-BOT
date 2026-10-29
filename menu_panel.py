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
        try:
            from next_step import suggest
            lines.append("")
            lines.append("🧭 **قدمِ پیشنهادی:** " + suggest(player)["text"])
        except Exception:
            pass
        lines.append("")
        lines.append("از منوی زیر استفاده کن:")
        return "\n".join(lines)

    # ─── هاب‌ها: ۴ گروهِ بزرگ به‌جای ۶-۸ دسته‌ی جدا ───────────────
    HUB_DEFS = [
        ("⚔️ ماجراجویی", lambda key, cat: cat.get("class_only") is not None),
        ("🏛 اجتماعی",   lambda key, cat: key in ("گیلد", "اجتماعی")),
        ("💰 اقتصاد",    lambda key, cat: key == "اقتصاد"),
        ("👤 من",        lambda key, cat: key in ("من", "اطلاعات", "زندگی")),
    ]

    def hub_items(self, hub_idx: int, player: dict | None):
        """[(cat_idx, j, text)] — فقط آیتم‌های بازشده؛ قفل‌ها اصلاً نشون داده نمی‌شن."""
        if not player:
            return []
        level = int(player.get("level", 1) or 1)
        visible = set(self.visible_fn(player))
        _title, pred = self.HUB_DEFS[hub_idx]
        seen, out = set(), []
        for idx, key in enumerate(self.cat_keys):
            if key not in visible or not pred(key, self.categories[key]):
                continue
            for j, text in enumerate(self.categories[key]["buttons"]):
                if level >= self.level_req.get(text, 1) and text not in seen:
                    seen.add(text)
                    out.append((idx, j, text))
        return out

    def hub_kb(self, uid: int, hub_idx: int, player: dict) -> InlineKeyboardMarkup:
        items = self.hub_items(hub_idx, player)
        btns = [InlineKeyboardButton(text=t, callback_data=f"{PREFIX}:d:{uid}:{i}:{j}",
                                     style=ButtonStyle.PRIMARY) for i, j, t in items]
        rows = [btns[k:k + MENU_ROW_WIDTH] for k in range(0, len(btns), MENU_ROW_WIDTH)]
        rows.append([InlineKeyboardButton(text=BACK_BTN_TEXT, callback_data=f"{PREFIX}:h:{uid}",
                                          style=ButtonStyle.PRIMARY)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # ─── کیبوردِ اصلی ─────────────────────────────────────────
    def main_kb(self, uid: int, player: dict | None, story_badge: bool = False) -> InlineKeyboardMarkup:
        from newbie_guard import MENU_MIN_LEVEL
        rows: list[list[InlineKeyboardButton]] = []
        btn = lambda text, cb: InlineKeyboardButton(text=text, callback_data=cb, style=ButtonStyle.PRIMARY)

        # ردیفِ اول همیشه: ▶️ ادامه — یه دکمه که کلِ بازی رو جلو می‌بره
        rows.append([btn("▶️ ادامه", f"{PREFIX}:n:{uid}")])

        level = int((player or {}).get("level", 1) or 1)
        in_tut = False
        step = None
        try:
            import onboarding
            in_tut = bool(player) and onboarding.is_in_tutorial(player)
            step = (player or {}).get("tutorial_step")
        except Exception:
            pass

        # 🆕 منوی سه‌دکمه‌ایِ تازه‌کار: چیزی که باز نیست اصلاً دیده نمی‌شه
        if player and (in_tut or level < MENU_MIN_LEVEL):
            row = []
            if not (in_tut and step == "first_loot"):
                row.append(btn("⚔️ حمله", f"{PREFIX}:w:{uid}:attack"))
            row.append(btn("🗺 لوت", f"{PREFIX}:w:{uid}:loot"))
            rows.append(row)
            if self.is_admin_fn and self.is_admin_fn(uid):
                rows.append([InlineKeyboardButton(text=ADMIN_BTN_TEXT, callback_data=f"{PREFIX}:a:{uid}",
                                                  style=ButtonStyle.DANGER)])
            return InlineKeyboardMarkup(inline_keyboard=rows)

        rows.append([btn(PROFILE_BTN_TEXT, f"{PREFIX}:p:{uid}")])
        buttons = [btn("⚔️ حمله", f"{PREFIX}:w:{uid}:attack"), btn("🗺 لوت", f"{PREFIX}:w:{uid}:loot")]
        for i, label in enumerate(self.shortcuts):
            if label == self.story_text:
                shown = label + (" 🆕" if story_badge else "")
                buttons.append(btn(shown, f"{PREFIX}:s:{uid}:{i}"))
        buttons.append(btn("📋 ماموریت‌ها", f"{PREFIX}:m:{uid}"))
        for hi, (title, _p) in enumerate(self.HUB_DEFS):
            if self.hub_items(hi, player):
                buttons.append(btn(title, f"{PREFIX}:g:{uid}:{hi}"))
        for i in range(0, len(buttons), MENU_ROW_WIDTH):
            rows.append(buttons[i:i + MENU_ROW_WIDTH])

        if self.is_admin_fn and self.is_admin_fn(uid):
            rows.append([InlineKeyboardButton(text=ADMIN_BTN_TEXT, callback_data=f"{PREFIX}:a:{uid}",
                                              style=ButtonStyle.DANGER)])
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
            # 🆕 آیتمِ قفل اصلاً نشون داده نمی‌شه
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
    try:
        import funnel
        if player and funnel.touch(player):
            from database import save_player
            save_player(uid, player)
    except Exception:
        pass
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

    @dp.message(F.text.in_({"ماموریت‌ها", "ماموریت ها", "📋 ماموریت‌ها", "/missions"}))
    async def cmd_missions(msg):
        from next_step import missions_card
        p = await aget_player(msg.from_user.id)
        if not p or not p.get("class"):
            await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        await msg.reply(missions_card(p))

    @dp.message(F.text == "/funnel")
    async def cmd_funnel(msg):
        from admin_panel import ADMIN_IDS
        if msg.from_user.id not in ADMIN_IDS:
            return
        import funnel
        await msg.reply(funnel.report())

    @dp.message(F.text.in_({"قدم بعدی", "قدمِ بعدی", "چیکار کنم", "چیکار کنم؟", "/next"}))
    async def cmd_next_step(msg):
        from next_step import suggest
        p = await aget_player(msg.from_user.id)
        if not p or not p.get("class"):
            await msg.reply("❌ اول باید کاراکترت رو بسازی! /start رو بزن.")
            return
        await msg.reply("🧭 " + suggest(p)["text"])

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

        # ─ قدمِ بعدی
        if action == "n":
            from next_step import suggest
            s = suggest(player)
            words = {"attack": "حمله", "loot": "لوت", "story": panel.story_text,
                     "hunt": "🏹 کوئست‌لاینِ شکار", "ascend": "/ascend",
                     "heal": "/heal", "rest": "/rest", "status": PROFILE_ACTION_TEXT}
            await cb.answer()
            await cb.message.answer("🧭 " + s["text"])
            if s["action"] in words:
                await _run_as_typed(cb, words[s["action"]])
            return

        # ─ دکمه‌های مستقیمِ حمله/لوت
        if action == "w":
            word = {"attack": "حمله", "loot": "لوت"}.get(parts[3] if len(parts) > 3 else "")
            await cb.answer()
            if word:
                await _run_as_typed(cb, word)
            return

        # ─ ماموریت‌ها
        if action == "m":
            from next_step import missions_card
            await cb.answer()
            await cb.message.answer(missions_card(player))
            return

        # ─ هاب (گروهِ بزرگِ دسته‌ها)
        if action == "g":
            try:
                hi = int(parts[3])
                title = panel.HUB_DEFS[hi][0]
            except (IndexError, ValueError):
                await cb.answer()
                return
            try:
                await cb.message.edit_text(f"{title}\n\nیکی رو انتخاب کن:",
                                           reply_markup=panel.hub_kb(owner, hi, player))
            except Exception:
                pass
            await cb.answer()
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
