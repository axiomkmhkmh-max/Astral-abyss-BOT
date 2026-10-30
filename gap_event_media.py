# ============================================================
#  ASTRAL ABYSS — Gap Event Media 🖼
# ------------------------------------------------------------
#  لایه‌ی تصویرِ رویدادهای گروهیِ گپ. دو کار می‌کنه:
#
#   1) پیدا کردنِ عکسِ درست از فایل‌های لوکال (assets/group_events/...)
#      — بدونِ دانلود، بدونِ شبکه؛ ایندکسِ فایل‌ها یک‌بار ساخته و کش می‌شه.
#   2) فرستادنِ عکس با GapBotAdapter.send_photo — *هیچ‌وقت* exception نمی‌ده:
#      اگه عکس نبود / آپلود خطا داد / گپ کند بود، فقط False برمی‌گردونه و
#      رویداد به‌صورتِ متنیِ عادی ادامه پیدا می‌کنه.
#
#  قراردادِ نام‌گذاریِ فایل‌ها (پسوند: .webp .png .jpg .jpeg)
#     bosses/boss_<template_id>_p1|p2|p3      عکسِ هر فازِ باس  (مثلاً boss_pyrothrax_p2.webp)
#     bosses/boss_<template_id>_defeated      باسِ شکست‌خورده (اختیاری)
#     bosses/boss_generic_<element>_p1|p2|p3  جایگزینِ عنصری (fire/ice/lightning/void/holy/nature/arcane/physical)
#     boxes/box_<tier>_closed|open            tier: wood bronze material silver gold legendary
#     dungeons/dungeon_<type>                 ورودی (bone_crypt forgotten_cathedral spider_cave
#                                             sunken_temple abandoned_tower shadow_labyrinth ancient_forge)
#     dungeons/dungeon_<type>_room            عکسِ اتاق‌ها (اختیاری)
#     dungeons/dungeon_final_boss[_<type>]    نگهبانِ نهایی
#     monsters/ambush_<monster_key>           حمله‌ی هیولا
#
#  چند نسخه برای یه عکس؟ پسوندِ _a _b _2 _v2 اضافه کن (مثلاً boss_pyrothrax_p1_b.webp)؛
#  هر بار یکی از نسخه‌ها رندوم انتخاب می‌شه (بدونِ تکرارِ پشتِ‌هم).
#
#  قانونِ سازگاری: عکس فقط با «کلیدِ» خودش پیدا می‌شه (باس/فاز/ندرت/نوعِ دانجن/هیولا) —
#  یعنی عکسِ باسِ یخی هیچ‌وقت برای باسِ آتشی نمایش داده نمی‌شه.
# ============================================================
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import tempfile
import time
from typing import Optional

from gap_event_world import (
    DUNGEON_TYPES, ELEMENTS, MONSTERS, CHEST_META, chest_meta,
)

log = logging.getLogger("gap.events.media")

ASSET_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "group_events")
SUBDIRS = ("bosses", "boxes", "dungeons", "monsters")
# ترتیبِ ترجیح وقتی از یه نام چند پسوند هست (png/jpg قطعاً توسطِ گپ پذیرفته می‌شن؛ webp رو آخر می‌ذاریم)
EXT_PREF = (".jpg", ".jpeg", ".png", ".webp")

CFG = {
    "max_bytes": 8 * 1024 * 1024,   # عکسِ بزرگ‌تر ارسال نمی‌شه
    "index_ttl_sec": 300,           # هر ۵ دقیقه ایندکسِ فایل‌ها تازه می‌شه (آرتِ جدید بدونِ ری‌استارت)
    "chat_min_gap_sec": 5,          # حداقل فاصله‌ی دو عکس تو یه گروه (ضدِ اسپم)
    "send_timeout_sec": 20,
    "fail_trip": 4,                 # بعد از این‌همه خطای پشت‌سرهم، عکس‌ها موقتاً خاموش می‌شن
    "fail_cooldown_sec": 600,
    "caption_max": 180,
    "jpeg_max_width": 1600,
}

_VARIANT_RE = re.compile(r"^(?:[a-z]|\d{1,2}|v\d{1,2})$")

_INDEX: dict[str, str] = {}          # stem(lowercase) -> path
_INDEX_AT = 0.0
_LAST_PICK: dict[tuple, str] = {}
_LAST_SEND: dict[int, float] = {}
_STATE = {"fails": 0, "disabled_until": 0.0, "prefer_jpg": False, "sent": 0, "failed": 0, "skipped": 0}


# ============================================================
#  ایندکسِ فایل‌ها
# ============================================================
def reset_cache():
    """برای تست و وقتی آرتِ جدید می‌ذاری: ایندکس و وضعیت‌ها رو پاک می‌کنه."""
    global _INDEX_AT
    _INDEX.clear()
    _LAST_PICK.clear()
    _LAST_SEND.clear()
    _INDEX_AT = 0.0
    _STATE.update({"fails": 0, "disabled_until": 0.0, "prefer_jpg": False, "sent": 0, "failed": 0, "skipped": 0})


def set_asset_root(path: str):
    global ASSET_ROOT
    ASSET_ROOT = path
    reset_cache()


def _build_index() -> dict[str, str]:
    found: dict[str, tuple[int, str]] = {}
    if not os.path.isdir(ASSET_ROOT):
        return {}
    for dirpath, _dirs, files in os.walk(ASSET_ROOT):
        for fn in files:
            stem, ext = os.path.splitext(fn)
            ext = ext.lower()
            if ext not in EXT_PREF:
                continue
            key = stem.lower()
            rank = EXT_PREF.index(ext)
            if key not in found or rank < found[key][0]:
                found[key] = (rank, os.path.join(dirpath, fn))
    return {k: v[1] for k, v in found.items()}


def _index() -> dict[str, str]:
    global _INDEX, _INDEX_AT
    now = time.monotonic()
    if now - _INDEX_AT > CFG["index_ttl_sec"] or not _INDEX_AT:
        try:
            _INDEX = _build_index()
        except Exception as e:  # noqa: BLE001
            log.warning("asset index failed: %s", e)
            _INDEX = {}
        _INDEX_AT = now
    return _INDEX


def variants(base: str) -> list[str]:
    """همه‌ی فایل‌های «base» و «base_<variant>» (variant = یه حرف، عدد یا vN)."""
    base = base.lower()
    out = []
    for stem, path in _index().items():
        if stem == base:
            out.append(path)
        elif stem.startswith(base + "_") and _VARIANT_RE.match(stem[len(base) + 1:]):
            out.append(path)
    return sorted(out)


def pick_image(*bases: str, chat_id: int | None = None) -> Optional[str]:
    """اولین baseای که فایل داره رو می‌گیره و یکی از نسخه‌هاش رو رندوم برمی‌گردونه
    (تا جای ممکن همونی که آخرین بار تو همین گروه نمایش داده شد نیست)."""
    for base in bases:
        files = variants(base)
        if not files:
            continue
        last = _LAST_PICK.get((chat_id, base))
        pool = [f for f in files if f != last] or files
        choice = random.choice(pool)
        _LAST_PICK[(chat_id, base)] = choice
        return choice
    return None


# ============================================================
#  انتخابِ عکسِ هر رویداد (همه None برمی‌گردونن اگه عکسی نباشه)
# ============================================================
def boss_image(tid: str, phase_index: int, element: str, chat_id: int | None = None) -> Optional[str]:
    """عکسِ فازِ phase_index (از ۰). اگه عکسِ اون فاز نبود، فازِ قبلیِ *همون باس*؛
    بعد جایگزینِ عنصریِ همون عنصر؛ وگرنه None (پیامِ متنی)."""
    bases = [f"boss_{tid}_p{p + 1}" for p in range(phase_index, -1, -1)]
    bases += [f"boss_generic_{element}_p{p + 1}" for p in range(phase_index, -1, -1)]
    return pick_image(*bases, chat_id=chat_id)


def boss_defeated_image(tid: str, element: str, chat_id: int | None = None) -> Optional[str]:
    return pick_image(f"boss_{tid}_defeated", f"boss_generic_{element}_defeated", chat_id=chat_id)


def chest_image(box_id: str, opened: bool, chat_id: int | None = None) -> Optional[str]:
    m = chest_meta(box_id)
    state = "open" if opened else "closed"
    bases = [f"box_{m['asset']}_{state}"]
    if m.get("alt"):
        bases.append(f"box_{m['alt']}_{state}")
    return pick_image(*bases, chat_id=chat_id)


def dungeon_image(dtype: str, chat_id: int | None = None) -> Optional[str]:
    return pick_image(f"dungeon_{dtype}", chat_id=chat_id)


def dungeon_room_image(dtype: str, chat_id: int | None = None) -> Optional[str]:
    return pick_image(f"dungeon_{dtype}_room", chat_id=chat_id)


def dungeon_final_image(dtype: str, chat_id: int | None = None) -> Optional[str]:
    return pick_image(f"dungeon_final_boss_{dtype}", "dungeon_final_boss", chat_id=chat_id)


def monster_image(key: str, chat_id: int | None = None) -> Optional[str]:
    return pick_image(f"ambush_{key}", chat_id=chat_id)


def has_monster_art(key: str) -> bool:
    return bool(variants(f"ambush_{key}"))


# ============================================================
#  ارسالِ امن
# ============================================================
def _clean_caption(c: str) -> str:
    c = (c or "").strip().replace("\n\n", "\n")
    m = CFG["caption_max"]
    return c if len(c) <= m else c[: m - 1] + "…"


async def _to_jpeg(path: str) -> Optional[str]:
    """webp → jpeg (کشِ دیسکی) — فقط وقتی گپ webp رو نپذیرفت و Pillow هست."""
    def _conv() -> Optional[str]:
        try:
            from PIL import Image
        except Exception:
            return None
        try:
            cache_dir = os.path.join(tempfile.gettempdir(), "astral_gap_event_cache")
            os.makedirs(cache_dir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(path))[0]
            out = os.path.join(cache_dir, f"{stem}_{int(os.path.getmtime(path))}.jpg")
            if os.path.exists(out):
                return out
            with Image.open(path) as im:
                im = im.convert("RGB")
                if im.width > CFG["jpeg_max_width"]:
                    h = int(im.height * CFG["jpeg_max_width"] / im.width)
                    im = im.resize((CFG["jpeg_max_width"], h))
                im.save(out, "JPEG", quality=88)
            return out
        except Exception as e:  # noqa: BLE001
            log.warning("jpeg convert failed for %s: %s", path, e)
            return None
    return await asyncio.to_thread(_conv)


async def send_photo_safe(bot, chat_id: int, path: Optional[str], caption: str = "") -> bool:
    """عکس رو می‌فرسته. True فقط وقتی واقعاً فرستاده شد؛ در هر خطایی False (بدونِ exception)."""
    if not path:
        return False
    try:
        now = time.time()
        if now < _STATE["disabled_until"]:
            _STATE["skipped"] += 1
            return False
        if now - _LAST_SEND.get(chat_id, 0) < CFG["chat_min_gap_sec"]:
            _STATE["skipped"] += 1               # ضدِ اسپم: به‌جای عکس، رویداد متنی می‌ره
            return False
        if not os.path.isfile(path) or os.path.getsize(path) > CFG["max_bytes"]:
            _STATE["skipped"] += 1
            return False
        cap = _clean_caption(caption)

        attempts: list[str] = []
        if path.lower().endswith(".webp") and _STATE["prefer_jpg"]:
            conv = await _to_jpeg(path)
            if conv:
                attempts.append(conv)
        attempts.append(path)

        tried_conv = bool(attempts and attempts[0] != path)
        i = 0
        while i < len(attempts):
            p = attempts[i]
            i += 1
            try:
                await asyncio.wait_for(bot.send_photo(chat_id, p, caption=cap), CFG["send_timeout_sec"])
                _STATE["fails"] = 0
                _STATE["sent"] += 1
                _LAST_SEND[chat_id] = time.time()
                return True
            except Exception as e:  # noqa: BLE001
                log.warning("send photo failed (%s): %s", os.path.basename(p), e)
                # گپ ممکنه webp رو نپذیره → یه‌بار jpeg امتحان کن و اگه جواب داد، دفعه‌های بعد مستقیم jpeg
                if p.lower().endswith(".webp") and not tried_conv:
                    tried_conv = True
                    conv = await _to_jpeg(p)
                    if conv:
                        attempts.append(conv)
                        _STATE["prefer_jpg"] = True
        _STATE["fails"] += 1
        _STATE["failed"] += 1
        if _STATE["fails"] >= CFG["fail_trip"]:
            _STATE["disabled_until"] = time.time() + CFG["fail_cooldown_sec"]
            _STATE["fails"] = 0
            log.warning("event images disabled for %ss after repeated failures", CFG["fail_cooldown_sec"])
        return False
    except Exception as e:  # noqa: BLE001 — هیچ‌چیزی نباید رویداد رو بشکونه
        log.warning("send_photo_safe unexpected: %s", e)
        return False


def stats() -> dict:
    return dict(_STATE, indexed=len(_index()), root=ASSET_ROOT)


# ============================================================
#  فهرستِ فایل‌های موردنیاز + گزارشِ پوشش (برای /gassets و مستندات)
# ============================================================
def expected_assets(templates: dict) -> dict[str, list[str]]:
    """دسته → لیستِ stemهای موردانتظار. هر دسته: required (اصلی) و optional (جایگزین/اضافه)."""
    out: dict[str, list[str]] = {"bosses": [], "bosses_defeated": [], "bosses_generic": [],
                                 "boxes": [], "dungeons": [], "dungeon_rooms": [],
                                 "dungeon_final": ["dungeon_final_boss"], "monsters": []}
    for tid, tpl in templates.items():
        n = len(tpl.get("phases", [])) or 3
        out["bosses"] += [f"boss_{tid}_p{i}" for i in range(1, n + 1)]
        out["bosses_defeated"].append(f"boss_{tid}_defeated")
    for el in ELEMENTS:
        out["bosses_generic"] += [f"boss_generic_{el}_p{i}" for i in (1, 2, 3)]
    for meta in CHEST_META.values():
        a = meta["asset"]
        out["boxes"] += [f"box_{a}_closed", f"box_{a}_open"]
    out["dungeons"] = [f"dungeon_{t}" for t in DUNGEON_TYPES]
    out["dungeon_rooms"] = [f"dungeon_{t}_room" for t in DUNGEON_TYPES]
    out["dungeon_final"] += [f"dungeon_final_boss_{t}" for t in DUNGEON_TYPES]
    out["monsters"] = [f"ambush_{k}" for k in MONSTERS]
    return out


def coverage(templates: dict) -> dict[str, tuple[int, int]]:
    """دسته → (تعدادِ موجود، تعدادِ کل)."""
    res = {}
    for cat, stems in expected_assets(templates).items():
        have = sum(1 for s in stems if variants(s))
        res[cat] = (have, len(stems))
    return res
