# ============================================================
#  ASTRAL ABYSS — انتخابِ کاتانا موقعِ ثبت‌نام
# ------------------------------------------------------------
#  جایگزینِ «کرکترِ رندوم». بعد از انتخابِ کلاس، ۴ تا کاتانای رندومِ آزاد
#  نشون داده می‌شه؛ پلیر روی هرکدوم بزنه، ابیلیتی‌هاش رو می‌بینه و بعد
#  یکی رو قطعی انتخاب می‌کنه. هر کاتانا یکتاست: وقتی کسی انتخابش کرد،
#  دیگه برای بقیه رندوم نمیاد.
#
#  وضعیت تو سندِ پلیر:
#     _awaiting_katana : True تا وقتی انتخاب نهایی نشده
#     _katana_offers   : لیستِ ۴ اسمِ کاتانا (با ریستارتِ ربات هم می‌مونه)
#  callbackها:  kat_view:<i>  |  kat_pick:<i>  |  kat_back
# ============================================================
from katanas import ALL_KATANAS, RARITY_EMOJI, RARITY_FA

OFFER_COUNT = 4


def _k(name: str) -> dict:
    return ALL_KATANAS.get(name, {})


def offers_text(offers: list) -> str:
    lines = [
        "🗡 **کاتاناتو انتخاب کن!**\n",
        "این ۴ تا کاتانا از اعماقِ Abyss برات اومدن. روی هرکدوم بزنی "
        "ابیلیتی‌هاش رو می‌بینی، بعد می‌تونی همونو انتخاب کنی.\n",
    ]
    for n in offers:
        d = _k(n)
        e = RARITY_EMOJI.get(d.get("rarity", "common"), "⚔️")
        lines.append(f"{e} **{n}** — {d.get('element', '—')}")
    lines.append("\n⚠️ انتخابت قطعیه و هر کاتانا فقط یه صاحب داره.")
    return "\n".join(lines)


def offers_kb(offers: list):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.enums import ButtonStyle
    rows = []
    for i, n in enumerate(offers):
        d = _k(n)
        e = RARITY_EMOJI.get(d.get("rarity", "common"), "⚔️")
        rows.append([InlineKeyboardButton(
            text=f"{e} {n}", callback_data=f"kat_view:{i}", style=ButtonStyle.PRIMARY,
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail_text(name: str) -> str:
    d = _k(name)
    e = RARITY_EMOJI.get(d.get("rarity", "common"), "⚔️")
    powers = "\n".join(f"  ✨ {p}" for p in d.get("powers", []))
    return (
        f"{e} **{name}**\n"
        f"🏷 ندرت: {RARITY_FA.get(d.get('rarity', 'common'), '—')}\n"
        f"🌀 عنصر: {d.get('element', '—')}\n"
        f"🎨 رنگِ تیغه: {d.get('color', '—')}\n"
        f"⚡ قدرتِ پایه: {d.get('base_dmg', 0)}\n\n"
        f"**ابیلیتی‌ها:**\n{powers}"
    )


def detail_kb(idx: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.enums import ButtonStyle
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ انتخابش می‌کنم", callback_data=f"kat_pick:{idx}", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 برگشت به ۴ کاتانا", callback_data="kat_back", style=ButtonStyle.PRIMARY)],
    ])
