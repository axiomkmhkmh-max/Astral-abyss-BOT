from aiogram.enums import ButtonStyle
# ============================================================
#  ASTRAL ABYSS RPG — Living Class Core (هسته‌ی زنده‌ی کلاس)
#  فاز ۱: موتورِ صورت‌فلکی + سیستمِ هسته + منطقِ حرکت رو نقشه
# ------------------------------------------------------------
#  ایده: به‌جای درختِ مهارتِ جدا برای هر کلاس، هر ۴ کلاس (جادوگر/
#  ماجراجو/تاجر/درمانگر) رو یک نقشه‌ی ستاره‌ایِ واحد و بدونِ مرز
#  می‌بینن. هرکس از «هابِ» کلاسِ خودش شروع می‌کنه، ولی می‌تونه —
#  با هزینه‌ی بیشتر هرچی دورتر بره — وارد قلمروِ کلاس‌های دیگه بشه.
#
#  ساختارِ نقشه:
#   • ۴ ناحیه (region) = ۴ کلاس. هر ناحیه RINGS حلقه داره (۱..RINGS)
#     و هر حلقه ARMS «بازو» (arm) داره. ring=0 یعنی هابِ مرکزیِ
#     همون ناحیه (رایگان، فقط برای صاحبِ همون کلاس).
#   • هر گره id: "{region}:{ring}:{arm}"
#   • یالِ عمودی: گره به گرهِ همون بازو تو حلقه‌ی قبلی (پیشرفتِ
#     طبیعیِ داخلِ کلاسِ خودت).
#   • یالِ جانبی (لِیترال): گره به گره‌های همسایه‌ی همون حلقه
#     (arm-1 / arm+1) — یعنی می‌تونی تو عمقِ یکسان جابه‌جا بشی.
#   • یالِ پُل (بازو صفرِ هر حلقه): به بازو صفرِ همون حلقه تو دو
#     ناحیه‌ی همسایه وصله — این‌جا مرزِ بین کلاس‌هاست. یعنی می‌تونی
#     بدونِ باز کردنِ هابِ کلاسِ دیگه، از مرز (بازو ۰) واردِ قلمروِ
#     اون کلاس بشی و از اونجا به بقیه‌ی بازوهاش (یالِ جانبی) برسی.
#   • برای باز کردنِ هر گره فقط لازمه حداقلِ یکی از پیش‌نیازهاش
#     (OR — نه همه‌شون) از قبل باز شده باشه؛ یعنی مسیرِ رسیدن به
#     یه نقطه، یکتا نیست — دقیقاً مثلِ واقعیِ یه صورت‌فلک.
#
#  هزینه: با عمق (ring) بیشتر می‌شه، و اگه گره تو ناحیه‌ی غیر از
#  کلاسِ خودِ بازیکن باشه، یه ضریبِ اضافه (بر اساسِ «فاصله‌ی
#  ناحیه‌ای» رو چرخه‌ی ۴تایی) روش می‌خوره.
#
#  یکپارچه‌سازی: get_core_bonuses(player) دقیقاً هم‌الگو با
#  skill_tree.get_skill_bonuses — یه dict تخت از همون کلیدهایی که
#  combat/pvp/economy/loot از قبل می‌شناسن (dmg_pct, gold_find_pct,
#  ...). skill_tree.get_skill_bonuses خودش این‌جا رو lazy-import
#  می‌کنه و جمع می‌زنه، پس هیچ فایلِ دیگه‌ای لازم نیست تغییر کنه.
# ============================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from class_system import CLASS_WIZARD, CLASS_ADVENTURER, CLASS_MERCHANT, CLASS_HEALER
except ImportError:  # pragma: no cover - fallback اگه class_system هنوز لود نشده
    CLASS_WIZARD, CLASS_ADVENTURER, CLASS_MERCHANT, CLASS_HEALER = "wizard", "adventurer", "merchant", "healer"

# ─── ناحیه‌ها (چرخه‌ی همسایگی — برای محاسبه‌ی فاصله) ────────────
REGION_ORDER = [CLASS_WIZARD, CLASS_ADVENTURER, CLASS_MERCHANT, CLASS_HEALER]

REGIONS = {
    CLASS_WIZARD:     {"name_fa": "قلمروِ جادوگر",  "emoji": "🧙‍♂️"},
    CLASS_ADVENTURER: {"name_fa": "قلمروِ ماجراجو", "emoji": "🗺️"},
    CLASS_MERCHANT:   {"name_fa": "قلمروِ تاجر",    "emoji": "💰"},
    CLASS_HEALER:     {"name_fa": "قلمروِ درمانگر", "emoji": "✨"},
}

# هر ناحیه ۳ کلیدِ باف دارد که به‌ترتیبِ arm % 3 بین گره‌ها می‌چرخد.
# همه‌ی کلیدها همون کلیدهاییِ که skill_tree._DEFAULT_BONUSES می‌شناسه.
FLAVOR_KEYS = {
    CLASS_WIZARD:     ["elem_amp", "status_chance", "crit_dmg_bonus"],
    CLASS_ADVENTURER: ["dmg_pct", "crit_chance", "dodge_chance"],
    CLASS_MERCHANT:   ["gold_find_pct", "loot_rarity_chance", "tax_discount"],
    CLASS_HEALER:     ["max_hp_pct", "lifesteal", "heal_cost_discount"],
}

# کلمه‌های تزئینی برای نام‌گذاریِ رویه‌ای گره‌ها (به‌جای نوشتنِ دستیِ صدها اسم)
_NAME_WORDS = {
    CLASS_WIZARD:     ["طلسم", "رازِ", "شعله‌یِ", "پژواکِ", "مِه", "زمزمه‌یِ", "نگاهِ", "کهکشانِ"],
    CLASS_ADVENTURER: ["نشانِ", "جاده‌یِ", "قطب‌نمایِ", "ردِ", "گنجِ", "طوفانِ", "قله‌یِ", "افقِ"],
    CLASS_MERCHANT:   ["کیسه‌یِ", "مهرِ", "کاروانِ", "ترازویِ", "سکه‌یِ", "قراردادِ", "بازارِ", "گنجینه‌یِ"],
    CLASS_HEALER:     ["نورِ", "دعایِ", "فیضِ", "شفایِ", "پرتوِ", "زنگوله‌یِ", "پناهِ", "چشمه‌یِ"],
}
_NAME_SUFFIX = ["مِه", "ستارگان", "ابدیت", "شب", "خاموش", "گمشده", "بی‌کران", "نهفته"]

RINGS = 8
ARMS = 8
_HOME_HUB_BONUS = 3  # امتیازِ رایگانِ اولیه، وقتی بازیکن اولین‌بار وارد این سیستم می‌شه


# ─── ساختِ گراف (یک‌بار موقعِ ایمپورت) ──────────────────────────

def _hub_id(region: str) -> str:
    return f"{region}:0:0"


def _node_id(region: str, ring: int, arm: int) -> str:
    if ring == 0:
        return _hub_id(region)
    return f"{region}:{ring}:{arm % ARMS}"


def region_distance(a: str, b: str) -> int:
    """فاصله‌ی ناحیه‌ای رو چرخه‌ی ۴تایی: خودش=۰، همسایه=۱، مقابل=۲."""
    if a == b:
        return 0
    ia, ib = REGION_ORDER.index(a), REGION_ORDER.index(b)
    d = abs(ia - ib) % len(REGION_ORDER)
    return min(d, len(REGION_ORDER) - d)


def _build_graph() -> dict:
    nodes = {}
    for region in REGION_ORDER:
        nodes[_hub_id(region)] = {
            "id": _hub_id(region), "region": region, "ring": 0, "arm": 0,
            "prereq": [], "cost": 0, "effect": {},
            "name_fa": f"هستهٔ {REGIONS[region]['name_fa']}",
            "desc_fa": "هابِ مرکزیِ ناحیه — نقطه‌ی شروعِ صاحبانِ همین کلاس.",
        }
        for ring in range(1, RINGS + 1):
            for arm in range(ARMS):
                nid = _node_id(region, ring, arm)
                prereq = [_node_id(region, ring - 1, arm)]
                # یالِ جانبی: به همسایه‌های همین حلقه
                prereq.append(_node_id(region, ring, arm - 1))
                prereq.append(_node_id(region, ring, arm + 1))
                # یالِ پُل: فقط بازو صفر، به بازو صفرِ همون حلقه تو دو ناحیه‌ی همسایه
                if arm == 0:
                    idx = REGION_ORDER.index(region)
                    left = REGION_ORDER[(idx - 1) % len(REGION_ORDER)]
                    right = REGION_ORDER[(idx + 1) % len(REGION_ORDER)]
                    prereq.append(_node_id(left, ring, 0))
                    prereq.append(_node_id(right, ring, 0))
                # حذفِ خودارجاعی (ring=1, arm همسایه که به خودش برسه رو حلقه‌ی تک‌بازو نیست چون ARMS=8)
                prereq = [p for p in prereq if p != nid]

                key = FLAVOR_KEYS[region][arm % len(FLAVOR_KEYS[region])]
                magnitude = round(0.003 + ring * 0.0015, 4)
                base_cost = 1 + (ring - 1) // 2

                words = _NAME_WORDS[region]
                name = f"{words[(ring + arm) % len(words)]} {_NAME_SUFFIX[(ring * 3 + arm) % len(_NAME_SUFFIX)]}"

                nodes[nid] = {
                    "id": nid, "region": region, "ring": ring, "arm": arm,
                    "prereq": prereq, "cost": base_cost,
                    "effect": {key: magnitude},
                    "name_fa": name,
                    "desc_fa": f"{_bonus_label(key)} +{magnitude*100:.2f}٪",
                }
    return nodes


def _bonus_label(key: str) -> str:
    return {
        "dmg_pct": "🗡️ دمیج", "crit_chance": "🎯 شانس کریت", "crit_dmg_bonus": "☠️ آسیب کریت",
        "max_hp_pct": "❤️ حداکثر HP", "dodge_chance": "💨 جاخالی", "lifesteal": "🩸 لایف‌استیل",
        "heal_cost_discount": "⚕️ تخفیف هیل", "elem_amp": "🌪️ ضریب ضعف عنصری",
        "status_chance": "☣️ شانس افکت وضعیت", "gold_find_pct": "💰 درآمد طلا",
        "loot_rarity_chance": "🍀 شانس ندرت لوت", "tax_discount": "🏦 تخفیف مالیات",
    }.get(key, key)


CONSTELLATION: dict = _build_graph()


# ─── وضعیتِ بازیکن ───────────────────────────────────────────────

def _ensure_core(player: dict) -> dict:
    """اولین باری که بازیکن وارد این سیستم می‌شه، هابِ کلاسِ خودش رو
    رایگان باز می‌کنه و چند امتیازِ شروع بهش می‌ده. Idempotent."""
    core = player.setdefault("core", {})
    core.setdefault("unlocked", [])
    core.setdefault("points", 0)
    core.setdefault("behavior", {"offense": 0, "defense": 0, "economy": 0, "team": 0})
    if not core.get("initialized"):
        home = player.get("class")
        if home in REGIONS:
            hub = _hub_id(home)
            if hub not in core["unlocked"]:
                core["unlocked"].append(hub)
        core["points"] = core.get("points", 0) + _HOME_HUB_BONUS
        core["initialized"] = True
    return core


def points_for_core_level(new_level: int) -> int:
    pts = 1
    if new_level % 20 == 0:
        pts += 2
    return pts


def grant_core_points(player: dict, old_level: int, new_level: int) -> int:
    """با هر لول‌آپ صدا زده می‌شه (از database._sync_pending_levelups)."""
    core = _ensure_core(player)
    total = sum(points_for_core_level(lvl) for lvl in range(old_level + 1, new_level + 1))
    core["points"] = core.get("points", 0) + total
    return total


def record_behavior(player: dict, category: str, amount: int = 1) -> None:
    """رد کردنِ الگوی بازیکردنِ بازیکن (offense/defense/economy/team) —
    فقط برای پیشنهادِ جهت رو نقشه استفاده می‌شه، هیچ گره‌ای رو قفل/باز نمی‌کنه.
    فراخوانی‌اش دلخواه و امن‌ـه (هیچ‌جا لازم نیست صدا زده بشه تا سیستم کار کنه)."""
    if category not in ("offense", "defense", "economy", "team"):
        return
    core = _ensure_core(player)
    core["behavior"][category] = core["behavior"].get(category, 0) + amount


def suggested_region(player: dict) -> str | None:
    """بر اساسِ بیشترین رفتارِ ثبت‌شده، کدوم ناحیه رو پیشنهاد بده (صرفاً یه اشاره‌ی نقشه، اجباری نیست)."""
    core = _ensure_core(player)
    behavior = core.get("behavior", {})
    if not any(behavior.values()):
        return None
    top = max(behavior, key=lambda k: behavior[k])
    mapping = {
        "offense": CLASS_ADVENTURER, "defense": CLASS_HEALER,
        "economy": CLASS_MERCHANT, "team": CLASS_WIZARD,
    }
    return mapping.get(top)


# ─── منطقِ حرکت / آنلاک ──────────────────────────────────────────

def node_cost(player: dict, node_id: str) -> int:
    import math
    node = CONSTELLATION[node_id]
    if node["ring"] == 0:
        return 0
    home = player.get("class")
    dist = region_distance(home, node["region"]) if home else 2
    mult = 1.0 if dist == 0 else (1.5 if dist == 1 else 2.0)
    return max(1, math.ceil(node["cost"] * mult))


def node_status(player: dict, node_id: str) -> str:
    """unlocked | available | locked_path | locked_points"""
    core = _ensure_core(player)
    unlocked = set(core["unlocked"])
    if node_id in unlocked:
        return "unlocked"
    node = CONSTELLATION[node_id]
    if node["ring"] == 0:
        return "locked_path" if node["region"] != player.get("class") else "unlocked"
    if not any(p in unlocked for p in node["prereq"]):
        return "locked_path"
    if core.get("points", 0) < node_cost(player, node_id):
        return "locked_points"
    return "available"


def can_unlock(player: dict, node_id: str) -> tuple[bool, str]:
    if node_id not in CONSTELLATION:
        return False, "این ستاره تو نقشه وجود نداره."
    status = node_status(player, node_id)
    if status == "unlocked":
        return False, "قبلاً باز کردی."
    if status == "locked_path":
        return False, "هنوز به این ستاره راه نداری — اول یکی از ستاره‌های مجاورش رو باز کن."
    if status == "locked_points":
        cost = node_cost(player, node_id)
        core = _ensure_core(player)
        return False, f"امتیازِ هسته کافی نداری (نیاز: {cost}، موجودی: {core.get('points', 0)})."
    return True, ""


def unlock_node(player: dict, node_id: str) -> tuple[bool, str]:
    ok, reason = can_unlock(player, node_id)
    if not ok:
        return False, f"❌ {reason}"
    core = _ensure_core(player)
    node = CONSTELLATION[node_id]
    cost = node_cost(player, node_id)
    core["points"] -= cost
    core["unlocked"].append(node_id)
    crossing = node["region"] != player.get("class")
    tag = " 🌉 (عبور از مرزِ کلاسی!)" if crossing else ""
    return True, f"✨ **{node['name_fa']}** روشن شد!{tag}\n{node['desc_fa']}"


# ─── جمع‌بندی باف‌ها (نقطه‌ی اتصال — از skill_tree.get_skill_bonuses صدا زده می‌شه) ─

def get_core_bonuses(player: dict) -> dict:
    core = _ensure_core(player)
    unlocked = core.get("unlocked", [])
    bonuses: dict = {}
    for nid in unlocked:
        node = CONSTELLATION.get(nid)
        if not node:
            continue
        for k, v in node["effect"].items():
            bonuses[k] = bonuses.get(k, 0) + v
    return bonuses


# ─── UI: متن و کیبورد ────────────────────────────────────────────

def _status_icon(status: str) -> str:
    return {"unlocked": "✅", "available": "🔓"}.get(status, "🔒")


def overview_text(player: dict) -> str:
    core = _ensure_core(player)
    home = player.get("class")
    lines = [
        "🌌 **هسته‌ی زنده — صورت‌فلکِ کلاس‌ها**",
        "یک نقشه‌ی ستاره‌ایِ واحد که هر ۴ کلاس رو به هم وصل می‌کنه. از قلمروِ خودت شروع کن،",
        "و هرجا خواستی (با هزینه‌ی بیشتر هرچی دورتر بری) وارد قلمروِ کلاس‌های دیگه شو.\n",
        f"💠 امتیازِ آزادِ هسته: `{core.get('points', 0)}`",
    ]
    for region in REGION_ORDER:
        info = REGIONS[region]
        cnt = sum(1 for nid in core["unlocked"] if CONSTELLATION[nid]["region"] == region)
        total = RINGS * ARMS + 1
        mark = " (قلمروِ خودت)" if region == home else ""
        lines.append(f"{info['emoji']} {info['name_fa']}{mark} — {cnt}/{total} روشن")
    sug = suggested_region(player)
    if sug:
        lines.append(f"\n🧭 بر اساسِ الگوی بازیکردنت، شاید ادامه‌ی مسیر تو {REGIONS[sug]['emoji']} {REGIONS[sug]['name_fa']} برات جذاب باشه (فقط پیشنهاده، اجباری نیست).")
    return "\n".join(lines)


def build_regions_kb() -> InlineKeyboardMarkup:
    rows = []
    for region in REGION_ORDER:
        info = REGIONS[region]
        rows.append([InlineKeyboardButton(text=f"{info['emoji']} {info['name_fa']}", callback_data=f"core_region:{region}:1", style=ButtonStyle.PRIMARY)])
    rows.append([InlineKeyboardButton(text="🏠 بستن", callback_data="core_close", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_ring_text(player: dict, region: str, ring: int) -> str:
    info = REGIONS[region]
    core = _ensure_core(player)
    lines = [f"{info['emoji']} **{info['name_fa']}** — حلقه {ring}/{RINGS}",
             f"امتیازِ آزاد: `{core.get('points', 0)}`\n"]
    if ring == 0:
        node = CONSTELLATION[_hub_id(region)]
        status = node_status(player, node["id"])
        lines.append(f"{_status_icon(status)} {node['name_fa']} — {node['desc_fa']}")
    else:
        for arm in range(ARMS):
            nid = _node_id(region, ring, arm)
            node = CONSTELLATION[nid]
            status = node_status(player, nid)
            cost = node_cost(player, nid)
            bridge_tag = " 🌉" if arm == 0 else ""
            lines.append(f"{_status_icon(status)} **{node['name_fa']}**{bridge_tag} (هزینه {cost}) — {node['desc_fa']}")
    return "\n".join(lines)


def build_region_ring_kb(player: dict, region: str, ring: int) -> InlineKeyboardMarkup:
    rows = []
    if ring == 0:
        nid = _hub_id(region)
        status = node_status(player, nid)
        if status == "available":
            rows.append([InlineKeyboardButton(text="🔓 باز کردن هاب", callback_data=f"core_unlock:{nid}", style=ButtonStyle.PRIMARY)])
    else:
        row = []
        for arm in range(ARMS):
            nid = _node_id(region, ring, arm)
            node = CONSTELLATION[nid]
            status = node_status(player, nid)
            icon = _status_icon(status)
            label = f"{icon} ⭐{arm+1}"
            row.append(InlineKeyboardButton(text=label, callback_data=f"core_unlock:{nid}", style=ButtonStyle.PRIMARY))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    nav = []
    if ring > 0:
        nav.append(InlineKeyboardButton(text="⬅️ حلقه‌ی قبل", callback_data=f"core_region:{region}:{ring-1}", style=ButtonStyle.PRIMARY))
    if ring < RINGS:
        nav.append(InlineKeyboardButton(text="حلقه‌ی بعد ➡️", callback_data=f"core_region:{region}:{ring+1}", style=ButtonStyle.PRIMARY))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🌌 نواحی", callback_data="core_back_menu", style=ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
