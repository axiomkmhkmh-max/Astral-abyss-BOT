# ============================================================
#  ASTRAL ABYSS — Funnel (قیفِ ریزشِ پلیرِ جدید)
# ------------------------------------------------------------
#  هر قدم برای هر پلیر فقط یک بار ثبت می‌شه: player["funnel"][step] = timestamp
#  گزارش برای ادمین: «/funnel» — چند نفر به هر قدم رسیدن.
# ============================================================
import time

STEPS = [
    ("started",      "شروع (/start)"),
    ("class_chosen", "انتخابِ کلاس"),
    ("first_loot",   "اولین لوت"),
    ("first_attack", "اولین حمله"),
    ("first_kill",   "اولین کشتن"),
    ("first_death",  "اولین مرگ"),
    ("lvl5",         "رسیدن به سطح ۵"),
    ("lvl10",        "رسیدن به سطح ۱۰"),
    ("returned",     "برگشت بعد از ≥۲۰ ساعت"),
]


def mark(player: dict, step: str) -> bool:
    """قدم رو ثبت می‌کنه؛ True یعنی تازه ثبت شد (صدازننده باید پلیر رو ذخیره کنه)."""
    if not isinstance(player, dict):
        return False
    f = player.setdefault("funnel", {})
    if step in f:
        return False
    f[step] = int(time.time())
    return True


def touch(player: dict) -> bool:
    """برگشتِ پلیر بعد از ≥۲۰ ساعت از اولین ثبت."""
    f = player.get("funnel") or {}
    first = f.get("started") or f.get("class_chosen") or f.get("first_loot")
    if first and time.time() - first >= 20 * 3600:
        return mark(player, "returned")
    return False


def report() -> str:
    from database import players_col
    col = players_col()
    base = col.count_documents({"funnel.started": {"$exists": True}}) or 1
    lines = ["📉 **قیفِ پلیرِ جدید** (از وقتی این ردیابی فعال شد)\n"]
    for key, label in STEPS:
        n = col.count_documents({f"funnel.{key}": {"$exists": True}})
        lines.append(f"{label}: **{n}** ({n * 100 // base}٪)")
    return "\n".join(lines)
