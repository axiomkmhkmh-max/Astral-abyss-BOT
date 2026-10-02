# ============================================================
#  ASTRAL ABYSS — 🩸 نفرین/دعا/آینه/طلسم (Curse Family)
#  (curse_system.py) — منطق و دیتای خالص، بدون UI تلگرام/گپ
# ------------------------------------------------------------
#  هدف: یه خانواده‌ی سبک و بدونِ اصطکاکِ شوخی/اجتماعی برای گروه‌ها —
#  عمداً کاملاً تزئینی و روایی نگه داشته شده (هیچ عددِ واقعیِ نبرد/لوت
#  رو عوض نمی‌کنه)، چون هدف وایرال‌شدن و تعاملِ چته، نه تعادلِ بازی.
#  همه‌ی زمان‌بندی‌ها طبقِ خواسته‌ی مستقیم ۲ دقیقه‌ست.
#
#  state رو خودِ player doc نگه می‌داره (curse_state)؛ لیدربرد جدا و
#  per-chat تو کالکشنِ curse_board ذخیره می‌شه (database.curse_board_col).
# ============================================================
from __future__ import annotations

import random
import time

EFFECT_SEC = 120          # طبقِ خواسته: همه‌ی افکت‌ها ۲ دقیقه‌ای

CURSE_LABELS = [
    "🩸 سایه‌ی سنگین", "👁 چشم‌زخم", "🕷 بدشانسیِ محفل", "🌑 لکه‌ی تاریکی", "💀 نفسِ سرد",
]
BLESS_LABELS = [
    "✨ نورِ محافظ", "🍀 شانسِ محفل", "🕊 آرامشِ الهه", "🌟 برکتِ سایه", "💫 لمسِ ستاره",
]
SPELL_GOOD_LABELS = ["🌟 طلسمِ شانس", "✨ جرقه‌ی خوش‌یمن", "🍀 نسیمِ سبز"]
SPELL_BAD_LABELS = ["🫠 طلسمِ وارونه", "🕳 لغزشِ سایه", "🦨 بویِ گند"]

FLAVOR_CURSE = [
    "یه سایه‌ی سرد رو شونه‌ش نشست...",
    "نفرینت پرواز کرد و دقیق خورد بهش!",
    "یه زمزمه‌ی تاریک دورش پیچید.",
]
FLAVOR_BLESS = [
    "یه نورِ گرم دورش رو گرفت.",
    "دعات مستجاب شد — یه آرامشِ عجیب روش نشست.",
    "ستاره‌ها براش چشمک زدن.",
]
FLAVOR_MIRROR_SUCCESS = "🪞 نفرین برگشت! درست خورد تو صورتِ کسی که فرستادتش."
FLAVOR_MIRROR_FAIL = "🪞 آینه ترک خورد ولی نفرین برنگشت — هنوز روته."
FLAVOR_SPELL_GOOD = "🔮 طلسم روشن شد — انگار امشب شانس باهاته."
FLAVOR_SPELL_BAD = "🔮 طلسم وارونه زد — امشب بدشانسیِ کوچیکی در انتظارته."

MIRROR_SUCCESS_CHANCE = 0.5


def get_state(player: dict) -> dict:
    return player.setdefault("curse_state", {
        "debuff_until": 0, "debuff_label": None,
        "buff_until": 0, "buff_label": None,
        "last_curser": None,
    })


def active_status(player: dict) -> dict:
    """برمی‌گردونه چه افکتی الان فعاله (برای نمایش تو وضعیت/کارت)."""
    st = get_state(player)
    now = time.time()
    out = {}
    if st["debuff_until"] > now:
        out["debuff"] = {"label": st["debuff_label"], "left": int(st["debuff_until"] - now)}
    if st["buff_until"] > now:
        out["buff"] = {"label": st["buff_label"], "left": int(st["buff_until"] - now)}
    return out


def can_be_mirrored(player: dict) -> bool:
    st = get_state(player)
    return st["debuff_until"] > time.time() and st.get("last_curser") is not None


def apply_curse(target: dict, by_uid: int) -> dict:
    st = get_state(target)
    label = random.choice(CURSE_LABELS)
    st["debuff_until"] = time.time() + EFFECT_SEC
    st["debuff_label"] = label
    st["last_curser"] = by_uid
    return {"label": label, "flavor": random.choice(FLAVOR_CURSE), "seconds": EFFECT_SEC}


def apply_bless(target: dict) -> dict:
    st = get_state(target)
    label = random.choice(BLESS_LABELS)
    st["buff_until"] = time.time() + EFFECT_SEC
    st["buff_label"] = label
    return {"label": label, "flavor": random.choice(FLAVOR_BLESS), "seconds": EFFECT_SEC}


def try_mirror(player: dict) -> dict:
    """برمی‌گردونه: {"ok": bool, "bounced": bool, "original_curser": int|None}"""
    st = get_state(player)
    if st["debuff_until"] <= time.time():
        return {"ok": False, "reason": "no_curse"}
    original_curser = st.get("last_curser")
    bounced = random.random() < MIRROR_SUCCESS_CHANCE
    if bounced:
        st["debuff_until"] = 0
        st["debuff_label"] = None
        st["last_curser"] = None
    return {"ok": True, "bounced": bounced, "original_curser": original_curser}


def cast_random_spell(player: dict) -> dict:
    st = get_state(player)
    good = random.random() < 0.5
    if good:
        label = random.choice(SPELL_GOOD_LABELS)
        st["buff_until"] = time.time() + EFFECT_SEC
        st["buff_label"] = label
        return {"good": True, "label": label, "flavor": FLAVOR_SPELL_GOOD, "seconds": EFFECT_SEC}
    else:
        label = random.choice(SPELL_BAD_LABELS)
        st["debuff_until"] = time.time() + EFFECT_SEC
        st["debuff_label"] = label
        st["last_curser"] = None  # طلسمِ خودخواسته — کسی برای آینه‌کردن نیست
        return {"good": False, "label": label, "flavor": FLAVOR_SPELL_BAD, "seconds": EFFECT_SEC}


# ─── 📊 لیدربردِ per-chat ────────────────────────────────────
async def _bump(chat_id: int, uid: int, name: str, field: str, by: int = 1):
    from database import curse_board_col
    await curse_board_col().aupdate_one(
        {"_id": f"{chat_id}:{uid}"},
        {"$set": {"chat_id": chat_id, "uid": uid, "name": name},
         "$inc": {field: by}},
        upsert=True,
    )


async def record_curse(chat_id: int, curser_uid: int, curser_name: str, target_uid: int, target_name: str):
    await _bump(chat_id, curser_uid, curser_name, "cursed_others")
    await _bump(chat_id, target_uid, target_name, "been_cursed")


async def record_bless(chat_id: int, blesser_uid: int, blesser_name: str, target_uid: int, target_name: str):
    await _bump(chat_id, blesser_uid, blesser_name, "blessed_others")
    await _bump(chat_id, target_uid, target_name, "been_blessed")


async def record_mirror(chat_id: int, mirrorer_uid: int, mirrorer_name: str,
                         original_curser_uid: int, original_curser_name: str):
    await _bump(chat_id, mirrorer_uid, mirrorer_name, "mirror_bounces")
    await _bump(chat_id, original_curser_uid, original_curser_name, "been_cursed")


async def get_leaderboard(chat_id: int) -> dict:
    """برمی‌گردونه: {"most_cursed": [...], "most_cursers": [...], "most_mirrors": [...]}"""
    from database import curse_board_col
    rows = await curse_board_col().afind({"chat_id": chat_id})
    rows = list(rows)

    def top(field: str, n: int = 5) -> list[dict]:
        ranked = sorted(rows, key=lambda r: r.get(field, 0), reverse=True)
        return [r for r in ranked if r.get(field, 0) > 0][:n]

    return {
        "most_cursed": top("been_cursed"),
        "most_cursers": top("cursed_others"),
        "most_mirrors": top("mirror_bounces"),
    }
