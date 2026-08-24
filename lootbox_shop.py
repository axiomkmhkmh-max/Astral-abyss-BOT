# ============================================================
#  ASTRAL ABYSS — Lootbox Shop (باکسِ شانسی) 🎁
# ------------------------------------------------------------
#  فایلِ کاملاً جدا و مستقل — هیچ فایلِ قدیمی رو خراب نمی‌کنه.
#  ۱۶ باکسِ متفاوت (۸ تا با Zen، ۸ تا با Echo Shard) که مستقیم از
#  زیرمنویِ فروشگاهِ بازارِ سیاه (bm:shop) خریداری و باز می‌شن —
#  برخلافِ سیستمِ قدیمیِ Vault/Lockbox (که فقط دراپی‌ان و کلید
#  می‌خوان)، این‌ها مستقیم پولیَن، بدونِ نیاز به کلید.
#
#  هر باکس چندتا "رول" داره؛ هر رول یکی از این سه‌تاست:
#    • equipment  → item_system.generate_random_equipment (تجهیزِ واقعیِ اکیپ‌شدنی)
#    • material   → crafting_system.add_material          (مادّه‌ی خامِ کرفت)
#    • cosmetic   → COSMETICS پایینِ همین فایل             (فقط لقب/فلکس، بدون افیکسِ کمبتی)
#
#  قیمت‌ها از ۴۰۰ Zen (باکس چوبی) تا ۴۰۰ Echo Shard (باکس غول‌پیکر)
#  پخش شدن، طبقِ درخواستِ حسین: «قیمت‌های خیلی بالا و پایین».
# ============================================================
from __future__ import annotations
import random

import item_system as itsys
import crafting_system as cfs

# ─── Cosmetics (فقط تزئینی/فلکس — بدون تأثیرِ کمبتی، فقط برای پرستیژ/فروش) ───
COSMETICS = {
    "title_ember":       {"name": "لقب: خاکسترنشین",        "emoji": "🔥", "rarity": "rare",         "sell": 4_000},
    "title_frost":       {"name": "لقب: یخ‌زاده",            "emoji": "❄️", "rarity": "rare",         "sell": 4_000},
    "title_void":        {"name": "لقب: فرزندِ خلأ",         "emoji": "🌑", "rarity": "epic",         "sell": 9_000},
    "title_storm":       {"name": "لقب: توفان‌شکن",          "emoji": "⚡", "rarity": "epic",         "sell": 9_000},
    "title_dragon":      {"name": "لقب: خونِ اژدها",         "emoji": "🐉", "rarity": "legendary",    "sell": 20_000},
    "title_shadow":      {"name": "لقب: سایه‌ی بی‌نام",      "emoji": "🖤", "rarity": "legendary",    "sell": 20_000},
    "title_celestial":   {"name": "لقب: پیامبرِ آسمانی",     "emoji": "✨", "rarity": "astral",       "sell": 45_000},
    "title_king":        {"name": "لقب: تاج‌دارِ ابدیت",     "emoji": "👑", "rarity": "void",         "sell": 90_000},
    "title_oblivion":    {"name": "لقب: پژواکِ نیستی",       "emoji": "💀", "rarity": "celestial",    "sell": 180_000},
    "title_astralking":  {"name": "لقب: شاهنشاهِ کهکشان",    "emoji": "🌌", "rarity": "transcendent", "sell": 400_000},
}

MATERIAL_CATEGORY_TIERS = {
    "ore": cfs.ORE_TIERS, "beast": cfs.BEAST_TIERS,
    "herb": cfs.HERB_TIERS, "essence": cfs.ESSENCE_TIERS,
}

# ─── تعریفِ ۱۶ باکس ────────────────────────────────────────────
# currency: "zen" یا "shard" (Echo Shard = player["rift_shards"])
# rolls: تعدادِ کشیدن
# rarity_pool/rarity_weights: بازه‌ی ندرتِ تجهیزِ قابل‌اکیپ
# material_chance / cosmetic_chance: احتمالِ هر رول که به‌جای تجهیز، مادّه یا کازمتیک بشه
# guaranteed_cosmetic: اگه هیچ کازمتیکی تو رول‌ها نیومد، یکی تضمینی اضافه می‌شه
BOXES = {
    # ─── ردیفِ Zen (ارزون → گرون) ───
    "wood_box": {
        "name": "باکس چوبی", "emoji": "🪵", "currency": "zen", "price": 400,
        "rolls": 1, "rarity_pool": ["common", "uncommon"], "rarity_weights": [70, 30],
        "material_chance": 0.5, "cosmetic_chance": 0.0,
        "desc": "یه شروعِ ساده — بیشترِ وقتا یه مادّه‌ی خام گیرت میاد.",
    },
    "bronze_box": {
        "name": "باکس برنزی", "emoji": "🥉", "currency": "zen", "price": 1_200,
        "rolls": 2, "rarity_pool": ["common", "uncommon", "rare"], "rarity_weights": [50, 35, 15],
        "material_chance": 0.35, "cosmetic_chance": 0.0,
        "desc": "دو تا رول، شانسِ کمِ نادر.",
    },
    "material_box": {
        "name": "باکس متریالِ خام", "emoji": "🌾", "currency": "zen", "price": 2_000,
        "rolls": 4, "rarity_pool": ["common"], "rarity_weights": [100],
        "material_chance": 1.0, "cosmetic_chance": 0.0,
        "desc": "۴ رول، همه‌ش مادّه‌ی کرفت — برای اونایی که تو Forge/Alchemy کم آوردن.",
    },
    "silver_box": {
        "name": "باکس نقره‌ای", "emoji": "🥈", "currency": "zen", "price": 3_500,
        "rolls": 2, "rarity_pool": ["uncommon", "rare", "epic"], "rarity_weights": [50, 35, 15],
        "material_chance": 0.25, "cosmetic_chance": 0.02,
        "desc": "یه‌کمی بهتر از برنزی، شانسِ خیلی کمِ کازمتیک.",
    },
    "gold_box": {
        "name": "باکس طلایی", "emoji": "🥇", "currency": "zen", "price": 9_000,
        "rolls": 3, "rarity_pool": ["rare", "epic", "mythic"], "rarity_weights": [50, 35, 15],
        "material_chance": 0.15, "cosmetic_chance": 0.04,
        "desc": "۳ رول تو محدوده‌ی نادر تا میتیک.",
    },
    "lucky_box": {
        "name": "باکس شانس", "emoji": "🍀", "currency": "zen", "price": 15_000,
        "rolls": 1, "rarity_pool": itsys.RARITY_ORDER[:6], "rarity_weights": [30, 25, 20, 14, 7, 4],
        "material_chance": 0.0, "cosmetic_chance": 0.05,
        "desc": "پرریسک — فقط ۱ رول ولی از common تا legendary همه رو می‌تونه بزنه.",
    },
    "diamond_box": {
        "name": "باکس الماس", "emoji": "💎", "currency": "zen", "price": 30_000,
        "rolls": 3, "rarity_pool": ["epic", "mythic", "legendary"], "rarity_weights": [45, 35, 20],
        "material_chance": 0.1, "cosmetic_chance": 0.06,
        "desc": "بالاترین باکسِ Zen — تضمینِ حماسی به بالا.",
    },
    "champion_box": {
        "name": "باکس قهرمان", "emoji": "🏆", "currency": "zen", "price": 60_000,
        "rolls": 4, "rarity_pool": ["mythic", "legendary", "ancient"], "rarity_weights": [50, 35, 15],
        "material_chance": 0.0, "cosmetic_chance": 0.08,
        "desc": "گرون‌ترین باکسِ Zen — ۴ رول تو محدوده‌ی میتیک تا باستانی.",
    },

    # ─── ردیفِ Echo Shard (ارزون → گرون) ───
    "shadow_box": {
        "name": "باکس سایه‌ی گمشده", "emoji": "🖤", "currency": "shard", "price": 25,
        "rolls": 2, "rarity_pool": ["legendary", "ancient"], "rarity_weights": [60, 40],
        "material_chance": 0.1, "cosmetic_chance": 0.15,
        "desc": "ورودی به دنیای باکس‌های Echo Shard.",
    },
    "astral_box": {
        "name": "باکس اختری", "emoji": "🌌", "currency": "shard", "price": 45,
        "rolls": 2, "rarity_pool": ["legendary", "ancient", "astral"], "rarity_weights": [45, 35, 20],
        "material_chance": 0.05, "cosmetic_chance": 0.1,
        "desc": "شانسِ رسیدن به رریتیِ اختری.",
    },
    "dragon_box": {
        "name": "باکس اژدهای کهن", "emoji": "🐉", "currency": "shard", "price": 90,
        "rolls": 3, "rarity_pool": ["ancient", "astral"], "rarity_weights": [55, 45],
        "material_chance": 0.0, "cosmetic_chance": 0.3,
        "desc": "باکسِ تِم‌دار — شانسِ بالای لقبِ 🐉 خونِ اژدها.",
    },
    "void_box": {
        "name": "باکس خلأ", "emoji": "🌑", "currency": "shard", "price": 130,
        "rolls": 2, "rarity_pool": ["astral", "void"], "rarity_weights": [55, 45],
        "material_chance": 0.0, "cosmetic_chance": 0.15,
        "desc": "دو رولِ سنگین تو محدوده‌ی خلأ.",
    },
    "mystery_box": {
        "name": "باکس مرموز", "emoji": "❓", "currency": "shard", "price": 160,
        "rolls": 2, "rarity_pool": itsys.RARITY_ORDER, "rarity_weights": None,
        "material_chance": 0.0, "cosmetic_chance": 0.1,
        "desc": "کاملاً تصادفی از بینِ همه‌ی ۱۱ رریتی — حتی ممکنه transcendent بیاد!",
    },
    "celestial_box": {
        "name": "باکس آسمانی", "emoji": "✨", "currency": "shard", "price": 220,
        "rolls": 3, "rarity_pool": ["astral", "void", "celestial"], "rarity_weights": [45, 35, 20],
        "material_chance": 0.0, "cosmetic_chance": 0.18,
        "desc": "۳ رولِ سنگین، شانسِ آسمانی.",
    },
    "transcendent_box": {
        "name": "باکس متعالی", "emoji": "👑", "currency": "shard", "price": 320,
        "rolls": 3, "rarity_pool": ["void", "celestial", "transcendent"], "rarity_weights": [40, 35, 25],
        "material_chance": 0.0, "cosmetic_chance": 0.2, "guaranteed_cosmetic": True,
        "desc": "یه کازمتیکِ نادر همیشه تضمینیه.",
    },
    "mega_box": {
        "name": "باکس غول‌پیکر", "emoji": "🎇", "currency": "shard", "price": 400,
        "rolls": 5, "rarity_pool": ["legendary", "ancient", "astral", "void", "celestial"],
        "rarity_weights": [30, 28, 22, 13, 7],
        "material_chance": 0.0, "cosmetic_chance": 0.25, "guaranteed_cosmetic": True,
        "desc": "گرون‌ترین و کامل‌ترین باکسِ بازی — ۵ رول + یه کازمتیکِ تضمینی.",
    },
}

BOX_ORDER = [
    "wood_box", "bronze_box", "material_box", "silver_box", "gold_box",
    "lucky_box", "diamond_box", "champion_box",
    "shadow_box", "astral_box", "dragon_box", "void_box",
    "mystery_box", "celestial_box", "transcendent_box", "mega_box",
]


def get_box(box_id: str) -> dict | None:
    return BOXES.get(box_id)


def currency_balance(player: dict, currency: str) -> int:
    return player.get("zen", 0) if currency == "zen" else player.get("rift_shards", 0)


def currency_label(currency: str) -> str:
    return "Zen" if currency == "zen" else "Echo Shard 🔹"


def can_afford(player: dict, box: dict) -> bool:
    return currency_balance(player, box["currency"]) >= box["price"]


def _roll_rarity(box: dict) -> str:
    pool = box["rarity_pool"]
    weights = box.get("rarity_weights")
    if weights is None:
        weights = [1] * len(pool)
    return random.choices(pool, weights=weights, k=1)[0]


def _roll_material() -> tuple[str, str, int]:
    category = random.choice(list(MATERIAL_CATEGORY_TIERS.keys()))
    tiers = MATERIAL_CATEGORY_TIERS[category]
    tier_idx = random.randint(0, min(2, len(tiers) - 1))  # لوت‌باکس فقط متریالِ تیرِ پایین/میانی می‌ده
    mat_id = tiers[tier_idx]
    qty = random.randint(2, 5)
    return category, mat_id, qty


def _roll_cosmetic() -> tuple[str, dict]:
    cid = random.choice(list(COSMETICS.keys()))
    return cid, COSMETICS[cid]


def _make_cosmetic_item(cid: str, c: dict) -> dict:
    item = {
        "name": c["name"], "emoji": c["emoji"], "rarity": c["rarity"], "sell": c["sell"],
        "type": "cosmetic", "cosmetic_id": cid,
    }
    # 🐛 فیکس: لقب‌های کازمتیک قبلاً فقط تو کوله‌پشتی می‌موندن و هیچ راهی
    # برای فعال‌سازی‌شون تو بخشِ لقب‌ها نبود. الان با فلگِ usable، دکمه‌ی
    # «✨ مصرف» تو کوله‌پشتی نشون داده می‌شه (هندل می‌شه تو bot.py/cb_inv_use).
    if cid.startswith("title_"):
        item["usable"] = True
        item["title_reward"] = c["name"]
    return item


def open_box(player: dict, box_id: str) -> tuple[bool, str, list[dict]]:
    """باکس رو می‌بنده/می‌خره و باز می‌کنه. برمی‌گردونه (ok, error_msg, results).
    results = [{"kind": "equipment"|"material"|"cosmetic", "label": "..."}]"""
    box = BOXES.get(box_id)
    if not box:
        return False, "❌ این باکس پیدا نشد.", []
    if not can_afford(player, box):
        have = currency_balance(player, box["currency"])
        return False, (
            f"❌ {currency_label(box['currency'])} کافی نداری!\n"
            f"لازم: {box['price']:,} | داری: {have:,}"
        ), []

    if box["currency"] == "zen":
        player["zen"] -= box["price"]
    else:
        player["rift_shards"] = player.get("rift_shards", 0) - box["price"]

    player_level = player.get("level", 1)
    inv = player.setdefault("inventory", [])
    results: list[dict] = []

    mc = box.get("material_chance", 0.0)
    cc = box.get("cosmetic_chance", 0.0)

    for _ in range(box["rolls"]):
        roll = random.random()
        if roll < mc:
            category, mat_id, qty = _roll_material()
            cfs.add_material(player, mat_id, qty)
            m = cfs.MATERIALS.get(mat_id, {"name": mat_id, "emoji": "📦"})
            results.append({"kind": "material", "label": f"{m['emoji']} {m['name']} x{qty}"})
        elif roll < mc + cc:
            cid, c = _roll_cosmetic()
            inv.append(_make_cosmetic_item(cid, c))
            r_label = itsys.RARITY_DATA.get(c["rarity"], {}).get("label", c["rarity"])
            results.append({"kind": "cosmetic", "label": f"{c['emoji']} {c['name']} ({r_label})"})
        else:
            rarity = _roll_rarity(box)
            item = itsys.generate_random_equipment(
                player_level, forced_rarity=rarity, drop_source=f"lootbox:{box_id}",
            )
            inv.append(item)
            r_label = itsys.RARITY_DATA.get(rarity, {}).get("label", rarity)
            results.append({
                "kind": "equipment",
                "label": f"{item['emoji']} {item['name']} ({r_label}) — {item['sell']:,} Zen",
            })

    if box.get("guaranteed_cosmetic") and not any(r["kind"] == "cosmetic" for r in results):
        cid, c = _roll_cosmetic()
        inv.append(_make_cosmetic_item(cid, c))
        r_label = itsys.RARITY_DATA.get(c["rarity"], {}).get("label", c["rarity"])
        results.append({"kind": "cosmetic", "label": f"🎁 {c['emoji']} {c['name']} ({r_label}) — تضمینی"})

    return True, "", results
