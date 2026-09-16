# ============================================================
#  ASTRAL ABYSS — 🧵 رشته‌های سرنوشت (Fate Threads)
#  (fate_threads.py) — منطق و دیتای خالص، بدون UI تلگرام
# ------------------------------------------------------------
#  یه داستانِ کوتاهِ روزانه که براساسِ وضعیتِ *همون* بازیکن انتخاب
#  می‌شه (نمسیسِ فعال؟ رزونانسِ افراطی؟ عضوِ گیلد؟ آبروی بازارِ
#  سیاه؟) و طیِ ۵ روزِ پشتِ‌سرهم پیش می‌ره. هر روز یه انتخاب — هر
#  انتخاب یه ویژگی (trait) رو تقویت می‌کنه؛ در پایانِ رشته، ویژگیِ
#  غالب یه عنوانِ دائمی + یه بونوسِ کوچیکِ همیشگی می‌ده.
#
#  اگه یه روز جا بمونی، رشته قطع نمی‌شه (فقط استریک صفر می‌شه) —
#  ولی وقتی برگردی، «در غیابت» یه تیکِ خودکار به سمتِ ویژگیِ
#  ضعیف‌تر زده می‌شه (یعنی زمان به نفعِ تصمیمِ فعال کار می‌کنه، نه
#  بی‌تفاوتی).
#
#  بونوس‌های نهاییِ رشته‌ها («فیت‌پرک») از دو مسیرِ امن و از قبل
#  موجود وصل می‌شن: economy_engine.apply_gold_find (gold_find_pct)
#  و combat.calc_combat (dmg_pct) — دقیقاً همون الگویی که
#  guild_system.get_perk و skill_tree.get_skill_bonuses ازش
#  استفاده می‌کنن.
# ============================================================
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

STAGES_PER_ARC = 5
MAX_DMG_PCT_PERK = 0.10        # سقفِ کلِ بونوسِ دمیجِ جمع‌شده از رشته‌ها
MAX_GOLD_FIND_PERK = 0.10      # سقفِ کلِ بونوسِ اقبالِ جمع‌شده از رشته‌ها


# ─── ⏱️ کمکی‌هایِ روز/استریک (هم‌الگو با daily_wheel.py) ─────────
def _day_id(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _yesterday_id() -> str:
    return _day_id(datetime.now(timezone.utc) - timedelta(days=1))


def _default_state() -> dict:
    return {
        "arc_id": None,
        "stage": 0,
        "traits": {},
        "last_day": "",
        "streak": 0,
        "best_streak": 0,
        "completed": {},     # arc_id -> تعداد بار تکمیل‌شده
        "perks": {"dmg_pct": 0.0, "gold_find_pct": 0.0},
        "last_result": None,  # آخرین متنِ نتیجه، برای نمایشِ دوباره اگه کاربر دوباره /fate بزنه
    }


def get_state(player: dict) -> dict:
    ft = player.setdefault("fate_threads", _default_state())
    for k, v in _default_state().items():
        if k not in ft:
            ft[k] = v
    return ft


# ─── 🔌 قلاب‌هایِ امنِ اتصال به بقیه‌ی سیستم‌ها ───────────────────
def get_fate_bonus(player: dict, stat: str) -> float:
    """فراخوانی‌شده از economy_engine.py / combat.py — هیچ‌وقت اکسپشن نمی‌ده."""
    try:
        return float(player.get("fate_threads", {}).get("perks", {}).get(stat, 0.0))
    except Exception:
        return 0.0


# ─── 📖 تعریفِ رشته‌ها ────────────────────────────────────────────
# هر رشته: trigger(player)->bool، عنوان، ایموجی، دو trait، و ۵ مرحله.
# هر مرحله: text(player)->str و ۲ گزینه: {label, trait, reward(player)->str}


def _name(player: dict) -> str:
    return player.get("name") or "قهرمان"


def _apply_reward(player: dict, zen: int = 0, xp: int = 0, resonance: int = 0,
                   bm_reputation: int = 0) -> list[str]:
    parts = []
    if zen:
        try:
            from economy_engine import apply_gold_find
            zen = apply_gold_find(player, zen) if zen > 0 else zen
        except ImportError:
            pass
        player["zen"] = player.get("zen", 0) + zen
        parts.append(f"💰 {zen:+,} Zen")
    if xp:
        player["xp"] = player.get("xp", 0) + xp
        parts.append(f"✨ {xp:+,} XP")
    if resonance:
        player["resonance"] = max(-100, min(100, player.get("resonance", 0) + resonance))
        parts.append(f"{'🕊️' if resonance > 0 else '🌑'} رزونانس {resonance:+d}")
    if bm_reputation:
        player["bm_reputation"] = player.get("bm_reputation", 0) + bm_reputation
        parts.append(f"🕶️ آبروی بازارِ سیاه {bm_reputation:+d}")
    return parts


ARCS: dict[str, dict] = {

    # ───────────────────────────── نمسیس ─────────────────────────────
    "nemesis": {
        "title": "🗡️ سایه‌ی نمسیس",
        "trigger": lambda p: bool(p.get("nemesis")),
        "traits": ("vengeance", "mercy"),
        "trait_labels": {"vengeance": "انتقام", "mercy": "بخشش"},
        "stages": [
            {
                "text": lambda p, n=None: f"شبِ گذشته خوابِ {p.get('nemesis',{}).get('base_name','دشمنت')} رو دیدی؛ هنوز داغِ مبارزه‌ی نصفه‌تموم تو سینه‌ته.",
                "options": [
                    {"label": "بی‌درنگ نقشه‌ی حمله‌ی بعدی رو بکش", "trait": "vengeance",
                     "reward": lambda p: _apply_reward(p, xp=40)},
                    {"label": "یه لحظه وایسا و به این فکر کن چرا این‌قدر بهش گیر دادی", "trait": "mercy",
                     "reward": lambda p: _apply_reward(p, zen=300)},
                ],
            },
            {
                "text": lambda p: "یکی از هم‌سفرهات می‌گه این دشمن هم قبلاً یه قربانیِ عادی بوده، نه یه هیولای ذاتی.",
                "options": [
                    {"label": "\"مهم نیست کی بوده، الان دشمنمه\"", "trait": "vengeance",
                     "reward": lambda p: _apply_reward(p, zen=250)},
                    {"label": "دلت براش می‌سوزه — ولی هنوز دست از تعقیب نمی‌کشی", "trait": "mercy",
                     "reward": lambda p: _apply_reward(p, xp=60)},
                ],
            },
            {
                "text": lambda p: "تو یه بازارِ کوچیک، نشونی از مخفیگاهِ نمسیس پیدا می‌کنی — زودتر از چیزی که فکرشو می‌کردی.",
                "options": [
                    {"label": "شبانه بهش حمله کن، غافلگیرش کن", "trait": "vengeance",
                     "reward": lambda p: _apply_reward(p, zen=400)},
                    {"label": "بذار روز بعد، رودررو و منصفانه باهاش روبه‌رو شی", "trait": "mercy",
                     "reward": lambda p: _apply_reward(p, xp=80)},
                ],
            },
            {
                "text": lambda p: "نمسیس یه پیام برات می‌فرسته: یه پیشنهادِ آتش‌بس موقت، تا یه تهدیدِ بزرگ‌تر رفع بشه.",
                "options": [
                    {"label": "پیشنهادشو پس بزن — این تا نابودی ادامه داره", "trait": "vengeance",
                     "reward": lambda p: _apply_reward(p, xp=100)},
                    {"label": "موقتاً قبول کن، شاید فرصتِ بهتری بسازه", "trait": "mercy",
                     "reward": lambda p: _apply_reward(p, zen=500)},
                ],
            },
            {
                "text": lambda p, n=_name: f"لحظه‌ی آخر رسیده. {p.get('nemesis',{}).get('base_name','نمسیس')} رو در برابرت داری و باید تصمیمِ نهایی رو بگیری.",
                "options": [
                    {"label": "بدونِ رحم تمومش کن", "trait": "vengeance",
                     "reward": lambda p: _apply_reward(p, zen=800, xp=150)},
                    {"label": "شکستش بده ولی زنده بذارش", "trait": "mercy",
                     "reward": lambda p: _apply_reward(p, zen=500, xp=200)},
                ],
            },
        ],
        "finale": {
            "vengeance": {
                "title": "شکارچیِ بی‌رحم",
                "text": "اسمت به‌عنوانِ کسی که هیچ‌وقت از تعقیب دست نمی‌کشه پیچیده. ضربه‌هات یه ذره سنگین‌تر شدن.",
                "perk": ("dmg_pct", 0.02),
            },
            "mercy": {
                "title": "روحِ بخشنده",
                "text": "مردم بهت اعتماد بیشتری می‌کنن — معامله‌ها یه‌کم به نفعت می‌چرخه.",
                "perk": ("gold_find_pct", 0.02),
            },
        },
    },

    # ───────────────────────────── رزونانس ─────────────────────────────
    "resonance": {
        "title": "🌗 ندایِ دوسو",
        "trigger": lambda p: abs(p.get("resonance", 0)) >= 30,
        "traits": ("light", "void"),
        "trait_labels": {"light": "نور", "void": "پوچی"},
        "stages": [
            {
                "text": lambda p: "یه صدای دور، از اعماقِ خودت، امروز صداتون می‌زنه. باید جواب بدی؟",
                "options": [
                    {"label": "به نور روی بیار، به کسی کمک کن", "trait": "light",
                     "reward": lambda p: _apply_reward(p, resonance=8, xp=50)},
                    {"label": "به پوچی گوش بده، فقط به خودت فکر کن", "trait": "void",
                     "reward": lambda p: _apply_reward(p, resonance=-8, zen=300)},
                ],
            },
            {
                "text": lambda p: "یه مسافرِ زخمی وسطِ جاده افتاده؛ هیچ‌کس دیگه‌ای این‌جا نیست.",
                "options": [
                    {"label": "کمکش کن، حتی اگه دیر برسی جایی که می‌خواستی", "trait": "light",
                     "reward": lambda p: _apply_reward(p, resonance=10, xp=70)},
                    {"label": "رد شو، وقتِ تو باارزش‌تره", "trait": "void",
                     "reward": lambda p: _apply_reward(p, resonance=-10, zen=350)},
                ],
            },
            {
                "text": lambda p: "قدرتی حسش می‌کنی که ازت می‌خواد یه انتخابِ بزرگ‌تر بکنی — سمتِ نور یا سمتِ سایه.",
                "options": [
                    {"label": "علناً پرچمِ نور رو بلند کن", "trait": "light",
                     "reward": lambda p: _apply_reward(p, resonance=12, zen=300)},
                    {"label": "به‌آرومی به سایه تسلیم شو", "trait": "void",
                     "reward": lambda p: _apply_reward(p, resonance=-12, xp=90)},
                ],
            },
            {
                "text": lambda p: "یه محفلِ کوچیک ازت می‌خواد بین دو راهِ متضاد یکی رو انتخاب کنی و بهش متعهد بشی.",
                "options": [
                    {"label": "راهِ روشنایی رو انتخاب کن", "trait": "light",
                     "reward": lambda p: _apply_reward(p, resonance=10, xp=110)},
                    {"label": "راهِ تاریکی رو انتخاب کن", "trait": "void",
                     "reward": lambda p: _apply_reward(p, resonance=-10, zen=450)},
                ],
            },
            {
                "text": lambda p: "به نقطه‌ی بی‌بازگشت رسیدی — ندا امروز جواب می‌خواد، برای همیشه.",
                "options": [
                    {"label": "کاملاً به نور بپیوند", "trait": "light",
                     "reward": lambda p: _apply_reward(p, resonance=15, zen=500, xp=150)},
                    {"label": "کاملاً به پوچی بپیوند", "trait": "void",
                     "reward": lambda p: _apply_reward(p, resonance=-15, zen=500, xp=150)},
                ],
            },
        ],
        "finale": {
            "light": {
                "title": "نگهبانِ روشنایی",
                "text": "نور دورت رو گرفته؛ انگار خودِ شانس بهت لبخند می‌زنه.",
                "perk": ("gold_find_pct", 0.02),
            },
            "void": {
                "title": "فرزندِ پوچی",
                "text": "سایه زیرِ پوستت نشسته؛ ضربه‌هات سردتر و سنگین‌تر شدن.",
                "perk": ("dmg_pct", 0.02),
            },
        },
    },

    # ───────────────────────────── بازارِ سیاه ─────────────────────────────
    "blackmarket": {
        "title": "🕶️ پیشنهادِ سایه‌ها",
        "trigger": lambda p: p.get("bm_reputation", 0) >= 15,
        "traits": ("greed", "loyalty"),
        "trait_labels": {"greed": "طمع", "loyalty": "وفاداری"},
        "stages": [
            {
                "text": lambda p: "یه واسطه‌ی ناشناس یه معامله‌ی وسوسه‌انگیز ولی مشکوک پیشنهاد می‌ده.",
                "options": [
                    {"label": "قبول کن، سود سوده", "trait": "greed",
                     "reward": lambda p: _apply_reward(p, zen=400)},
                    {"label": "اول با شرکای قدیمیت مشورت کن", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, bm_reputation=3, xp=60)},
                ],
            },
            {
                "text": lambda p: "یکی از دلال‌های قدیمی ازت می‌خواد تو یه معامله‌ی مشترک شریکش رو دور بزنی.",
                "options": [
                    {"label": "دورش بزن، سهمِ بیشتری بردار", "trait": "greed",
                     "reward": lambda p: _apply_reward(p, zen=450)},
                    {"label": "قولت رو نگه دار، سهمِ برابر تقسیم کن", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, bm_reputation=4, zen=150)},
                ],
            },
            {
                "text": lambda p: "یه محموله‌ی پرخطر می‌تونی برای خودت نگه داری یا بینِ هم‌قطارهات تقسیم کنی.",
                "options": [
                    {"label": "همه‌شو برای خودت نگه دار", "trait": "greed",
                     "reward": lambda p: _apply_reward(p, zen=500)},
                    {"label": "بینِ همه تقسیم کن، اعتمادسازی کن", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, bm_reputation=5, xp=90)},
                ],
            },
            {
                "text": lambda p: "گارد داره یکی از هم‌قطارهات رو تعقیب می‌کنه؛ می‌تونی گمراهشون کنی یا بی‌خیال شی.",
                "options": [
                    {"label": "بی‌خیال شو، خطر نکن", "trait": "greed",
                     "reward": lambda p: _apply_reward(p, zen=350)},
                    {"label": "گاردا رو گمراه کن و نجاتش بده", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, bm_reputation=6, xp=120)},
                ],
            },
            {
                "text": lambda p: "رهبرِ شبکه ازت می‌خواد بینِ سود شخصیِ عظیم یا وفاداری به کل شبکه یکی رو انتخاب کنی.",
                "options": [
                    {"label": "سودِ شخصی رو انتخاب کن", "trait": "greed",
                     "reward": lambda p: _apply_reward(p, zen=900)},
                    {"label": "به شبکه وفادار بمون", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, bm_reputation=10, xp=150)},
                ],
            },
        ],
        "finale": {
            "greed": {
                "title": "دلالِ بی‌رحم",
                "text": "همه می‌دونن باهات فقط سرِ سود می‌شه حرف زد — و دقیقاً همینم بهت سود می‌رسونه.",
                "perk": ("gold_find_pct", 0.025),
            },
            "loyalty": {
                "title": "متحدِ سایه‌ها",
                "text": "شبکه پشتته؛ هم‌قطارهات یادت دادن چطور تو نبرد هم از هم محافظت کنید.",
                "perk": ("dmg_pct", 0.02),
            },
        },
    },

    # ───────────────────────────── گیلد ─────────────────────────────
    "guild": {
        "title": "🏰 سیاستِ گیلد",
        "trigger": lambda p: bool(p.get("guilds")),
        "traits": ("ambition", "loyalty"),
        "trait_labels": {"ambition": "جاه‌طلبی", "loyalty": "وفاداری"},
        "stages": [
            {
                "text": lambda p: "دو عضوِ گیلد سرِ تقسیمِ غنایم دعواشون شده و از تو نظر می‌خوان.",
                "options": [
                    {"label": "به نفعِ خودت رأی بده", "trait": "ambition",
                     "reward": lambda p: _apply_reward(p, zen=300)},
                    {"label": "منصفانه‌ترین راه‌حل رو پیشنهاد بده", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, xp=70)},
                ],
            },
            {
                "text": lambda p: "یه فرصت هست که با کمی زرنگی، سهمِ بیشتری از خزانه‌ی گیلد بردار.",
                "options": [
                    {"label": "از فرصت استفاده کن", "trait": "ambition",
                     "reward": lambda p: _apply_reward(p, zen=400)},
                    {"label": "بی‌خیالش شو، اعتمادِ بقیه مهم‌تره", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, xp=100)},
                ],
            },
            {
                "text": lambda p: "رهبرِ گیلد ازت می‌خواد رهبریِ یه ماموریتِ خطرناک رو به عهده بگیری.",
                "options": [
                    {"label": "قبول کن تا خودتو مطرح کنی", "trait": "ambition",
                     "reward": lambda p: _apply_reward(p, zen=350, xp=60)},
                    {"label": "قبول کن، ولی برای موفقیتِ تیم نه خودت", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, xp=130)},
                ],
            },
            {
                "text": lambda p: "شایعه شده که رهبرِ فعلیِ گیلد داره ضعیف می‌شه — جای خالی برای صعود هست.",
                "options": [
                    {"label": "شروع کن به جمع‌کردنِ حمایت برای خودت", "trait": "ambition",
                     "reward": lambda p: _apply_reward(p, zen=450)},
                    {"label": "به رهبرِ فعلی وفادار بمون", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, xp=140)},
                ],
            },
            {
                "text": lambda p: "لحظه‌ی تصمیمِ بزرگ: آینده‌ی خودت مهم‌تره یا آینده‌ی گیلد؟",
                "options": [
                    {"label": "آینده‌ی خودت", "trait": "ambition",
                     "reward": lambda p: _apply_reward(p, zen=700)},
                    {"label": "آینده‌ی گیلد", "trait": "loyalty",
                     "reward": lambda p: _apply_reward(p, zen=300, xp=180)},
                ],
            },
        ],
        "finale": {
            "ambition": {
                "title": "جاه‌طلبِ گیلد",
                "text": "همه می‌دونن یه روز رهبر می‌شی — این جاه‌طلبی بهت انگیزه‌ی بیشتری تو نبرد می‌ده.",
                "perk": ("dmg_pct", 0.02),
            },
            "loyalty": {
                "title": "ستونِ گیلد",
                "text": "گیلد بهت پاداشِ اعتماد می‌ده؛ معامله‌هات همیشه یه‌کم بهتر پیش می‌رن.",
                "perk": ("gold_find_pct", 0.02),
            },
        },
    },

    # ───────────────────────────── سرگردان (پیش‌فرض همیشگی) ─────────────────────────────
    "wanderer": {
        "title": "🧭 مسیرِ خودت",
        "trigger": lambda p: True,
        "traits": ("courage", "caution"),
        "trait_labels": {"courage": "شجاعت", "caution": "احتیاط"},
        "stages": [
            {
                "text": lambda p: "یه مسیرِ ناشناخته جلوته که کسی نقشه‌ش رو نداره.",
                "options": [
                    {"label": "بی‌باک وارد شو", "trait": "courage",
                     "reward": lambda p: _apply_reward(p, xp=60)},
                    {"label": "اول یه اسکاوت بفرست", "trait": "caution",
                     "reward": lambda p: _apply_reward(p, zen=250)},
                ],
            },
            {
                "text": lambda p: "یه غریبه پیشنهادِ یه معامله‌ی عجیب می‌ده که ریسکش بالاست ولی سودش هم همین‌طور.",
                "options": [
                    {"label": "ریسک کن", "trait": "courage",
                     "reward": lambda p: _apply_reward(p, zen=350)},
                    {"label": "رد کن، امن‌تره", "trait": "caution",
                     "reward": lambda p: _apply_reward(p, xp=80)},
                ],
            },
            {
                "text": lambda p: "صدای غرشی از دوردست میاد — می‌تونی بری ببینی چیه یا نادیده بگیری.",
                "options": [
                    {"label": "برو دنبالِ صدا", "trait": "courage",
                     "reward": lambda p: _apply_reward(p, zen=300, xp=40)},
                    {"label": "نادیده بگیر و به راهت ادامه بده", "trait": "caution",
                     "reward": lambda p: _apply_reward(p, zen=300)},
                ],
            },
            {
                "text": lambda p: "یه فرصتِ نادر جلوته، ولی برای گرفتنش باید از یه پلِ نیمه‌خراب رد شی.",
                "options": [
                    {"label": "از پل رد شو", "trait": "courage",
                     "reward": lambda p: _apply_reward(p, xp=110)},
                    {"label": "دنبالِ راهِ امن‌تر بگرد", "trait": "caution",
                     "reward": lambda p: _apply_reward(p, zen=400)},
                ],
            },
            {
                "text": lambda p: "امروز، بالاخره باید بفهمی چه‌جور آدمی می‌خوای باشی: بی‌باک یا حساب‌شده؟",
                "options": [
                    {"label": "بی‌باک", "trait": "courage",
                     "reward": lambda p: _apply_reward(p, xp=150, zen=200)},
                    {"label": "حساب‌شده", "trait": "caution",
                     "reward": lambda p: _apply_reward(p, zen=600)},
                ],
            },
        ],
        "finale": {
            "courage": {
                "title": "بی‌باکِ راه",
                "text": "شجاعتت زبانزد شده؛ تو میدون هم یه‌کم بی‌پرواتر می‌زنی.",
                "perk": ("dmg_pct", 0.015),
            },
            "caution": {
                "title": "محتاطِ زیرک",
                "text": "حساب‌وکتابت جواب داده؛ همیشه یه سکه‌ی اضافه از هرجا گیرت میاد.",
                "perk": ("gold_find_pct", 0.015),
            },
        },
    },
}


def _eligible_arcs(player: dict, ft: dict) -> list[str]:
    return [aid for aid, arc in ARCS.items() if arc["trigger"](player)]


def _pick_next_arc(player: dict, ft: dict) -> str:
    elig = _eligible_arcs(player, ft)
    last = ft.get("last_arc")
    if len(elig) > 1 and last in elig:
        elig = [a for a in elig if a != last] or elig
    completed = ft.get("completed", {})
    elig.sort(key=lambda a: completed.get(a, 0))
    min_count = completed.get(elig[0], 0)
    pool = [a for a in elig if completed.get(a, 0) == min_count]
    return random.choice(pool)


def _grant_finale(player: dict, ft: dict, arc_id: str) -> dict:
    arc = ARCS[arc_id]
    traits = ft["traits"]
    dominant = max(arc["traits"], key=lambda t: traits.get(t, 0))
    # مساوی؟ رندوم منصفانه بینِ دوتا
    if all(traits.get(t, 0) == traits.get(dominant, 0) for t in arc["traits"]):
        dominant = random.choice(arc["traits"])
    finale = arc["finale"][dominant]
    stat, amount = finale["perk"]
    cap = MAX_DMG_PCT_PERK if stat == "dmg_pct" else MAX_GOLD_FIND_PERK
    ft["perks"][stat] = round(min(cap, ft["perks"].get(stat, 0.0) + amount), 4)
    title = finale["title"]
    titles = player.setdefault("fate_titles", [])
    if title not in titles:
        titles.append(title)
    ft["completed"][arc_id] = ft.get("completed", {}).get(arc_id, 0) + 1
    return {"arc_id": arc_id, "dominant": dominant, "title": title, "text": finale["text"],
            "perk_stat": stat, "perk_amount": amount}


def get_prompt(player: dict) -> dict:
    """وضعیتِ امروز رو برمی‌گردونه. اگه امروز جواب داده باشه، status='answered'."""
    ft = get_state(player)
    today = _day_id()

    if ft["last_day"] == today and ft.get("arc_id") is not None:
        return {"status": "answered", "reset_in": _seconds_until_reset()}

    neglect_note = None
    if ft.get("arc_id") is not None and ft["last_day"] not in ("", today, _yesterday_id()):
        # جا افتادنِ حداقل یه روزِ کامل: یه تیکِ خودکار به سمتِ ویژگیِ عقب‌مونده
        arc = ARCS[ft["arc_id"]]
        t1, t2 = arc["traits"]
        weaker = t1 if ft["traits"].get(t1, 0) <= ft["traits"].get(t2, 0) else t2
        ft["traits"][weaker] = ft["traits"].get(weaker, 0) + 1
        ft["streak"] = 0
        neglect_note = (
            f"⏳ چند روزی نبودی — در غیابت رویدادها به سمتِ «{arc['trait_labels'][weaker]}» چرخیدن."
        )

    if ft.get("arc_id") is None:
        arc_id = _pick_next_arc(player, ft)
        ft["arc_id"] = arc_id
        ft["stage"] = 0
        ft["traits"] = {}
        ft["last_arc"] = arc_id

    arc = ARCS[ft["arc_id"]]
    stage_def = arc["stages"][ft["stage"]]
    return {
        "status": "prompt",
        "arc_title": arc["title"],
        "stage": ft["stage"] + 1,
        "total_stages": STAGES_PER_ARC,
        "text": stage_def["text"](player),
        "options": [o["label"] for o in stage_def["options"]],
        "streak": ft["streak"],
        "neglect_note": neglect_note,
    }


def choose(player: dict, option_index: int) -> dict | None:
    """گزینه‌ی انتخاب‌شده رو اعمال می‌کنه. اگه نامعتبر/تکراری باشه None برمی‌گردونه."""
    ft = get_state(player)
    today = _day_id()
    if ft.get("arc_id") is None or ft["last_day"] == today:
        return None
    arc = ARCS[ft["arc_id"]]
    stage_def = arc["stages"][ft["stage"]]
    if not (0 <= option_index < len(stage_def["options"])):
        return None

    opt = stage_def["options"][option_index]
    reward_lines = opt["reward"](player)
    ft["traits"][opt["trait"]] = ft["traits"].get(opt["trait"], 0) + 1
    ft["last_day"] = today
    ft["streak"] = ft.get("streak", 0) + 1
    ft["best_streak"] = max(ft.get("best_streak", 0), ft["streak"])
    ft["stage"] += 1

    result = {
        "chosen_label": opt["label"],
        "reward_lines": reward_lines,
        "streak": ft["streak"],
        "arc_title": arc["title"],
        "finished": False,
        "finale": None,
    }

    if ft["stage"] >= STAGES_PER_ARC:
        finale = _grant_finale(player, ft, ft["arc_id"])
        result["finished"] = True
        result["finale"] = finale
        ft["arc_id"] = None
        ft["stage"] = 0
        ft["traits"] = {}

    return result


def _seconds_until_reset() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


def time_until_reset() -> str:
    secs = _seconds_until_reset()
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return f"{h} ساعت و {m} دقیقه"
