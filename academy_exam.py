# ============================================================
#  ASTRAL ABYSS — Academy Exam Question Engine 📝
# ------------------------------------------------------------
#  بانکِ سؤالِ امتحانِ آکادمی. هیچ شانسی تو قبولی/ردی نیست — فقط
#  جوابِ درست حساب می‌شه. سؤال‌ها سه دسته‌ن (هم‌نام با درس‌ها):
#
#   ⚔️ combat — مسئله‌های محاسباتیِ نبرد (پارامترها هر بار تصادفی‌ان،
#               پس حفظ‌کردن/جستجو جواب نمی‌ده؛ باید حل کنی)
#   🔮 magic  — منطقِ عناصر، منا، کول‌داون، مقاومت
#   📚 lore   — دانشِ واقعیِ بازی؛ سؤال‌ها مستقیم از دیتای خودِ بازی
#               (WORLD_TIERS / ASCENSION_TRIALS / MAP_WORLD_TIER / SUBJECTS)
#               ساخته می‌شن، پس با تغییرِ بازی خودبه‌خود به‌روز می‌مونن.
#
#  «تصادفی» فقط تو اعدادِ سؤاله، نه تو نتیجه: هر سؤال یه جوابِ
#  قطعیِ درست داره.
#  ⚠️ تو متنِ سؤال‌ها از < > & استفاده نشده (parse_mode=HTML).
# ============================================================
import math
import random

ELEMENT_NAMES = ["آتش", "یخ", "برق", "زمین", "آب", "نور", "تاریکی"]


# ─── ابزارِ ساختِ سؤال ───────────────────────────────────────
def _fmt(x) -> str:
    return f"{x:,}" if isinstance(x, int) else str(x)


def _build(rng: random.Random, subject: str, text: str, correct, wrongs: list, numeric: bool = True) -> dict:
    """گزینه‌ها رو یکتا می‌کنه، تا ۳ تا بدگزینه تکمیل می‌کنه و شافل می‌کنه."""
    uniq: list = []
    for w in wrongs:
        if w != correct and w not in uniq and (not numeric or w > 0):
            uniq.append(w)
    if numeric:
        step = 1
        while len(uniq) < 3:
            for cand in (correct + step, correct - step, correct + 2 * step):
                if cand > 0 and cand != correct and cand not in uniq and len(uniq) < 3:
                    uniq.append(cand)
            step += max(1, abs(correct) // 10 or 1)
    rng.shuffle(uniq)
    opts = [correct] + uniq[:3]
    rng.shuffle(opts)
    return {
        "s": subject,
        "t": text,
        "o": [_fmt(o) for o in opts],
        "a": opts.index(correct),
        "hid": [],
        "g": None,     # جوابِ داده‌شده (None = هنوز؛ -1 = تایم‌اوت)
        "t0": 0.0,
    }


# ═══ ⚔️ combat ═══════════════════════════════════════════════
def _c_hits_to_kill(rng, d):
    hp = rng.randrange(400, 1000, 50)
    dmg = rng.randrange(60, 141, 10)
    if d == 1:
        hits = math.ceil(hp / dmg)
        text = f"دشمن {hp} HP داره و هر ضربه‌ات {dmg} آسیب می‌زنه. حداقل چند ضربه لازمه؟"
        wrongs = [hits - 1, hits + 1, hits + 2]
    else:
        total, n = 0, 0
        while total < hp:
            n += 1
            total += dmg * 2 if n % 3 == 0 else dmg
        text = (f"دشمن {hp} HP داره. هر ضربه {dmg} آسیب می‌زنه، ولی هر ضربه‌ی سوم "
                f"(سوم، ششم، نهم...) کریتیکاله و دو برابر آسیب می‌زنه. حداقل چند ضربه لازمه؟")
        hits = n
        wrongs = [math.ceil(hp / dmg), n - 1, n + 1]
    return _build(rng, "combat", text, hits, wrongs)


def _c_buff_stack(rng, d):
    base = rng.randrange(200, 700, 50)
    a, b = rng.choice([10, 20, 25, 30]), rng.choice([20, 40, 50])
    add = int(base * (100 + a + b) / 100)
    mul = int(base * (100 + a) * (100 + b) / 10000)
    if d == 1 or rng.random() < 0.5:
        text = (f"ATK پایه‌ی تو {base}ـه. دو بافِ جمعی داری: +{a}٪ و +{b}٪ "
                f"(جمعی یعنی درصدها اول با هم جمع می‌شن). ATK نهایی؟")
        return _build(rng, "combat", text, add, [mul, int(base * (100 + a) / 100), int(base * (100 + b) / 100)])
    text = (f"ATK پایه‌ی تو {base}ـه. دو بافِ ضربی داری: +{a}٪ و +{b}٪ "
            f"(ضربی یعنی بافِ دوم روی نتیجه‌ی بافِ اول اعمال می‌شه). ATK نهایی؟")
    return _build(rng, "combat", text, mul, [add, int(base * (100 + a) / 100), int(base * (100 + b) / 100)])


def _c_defense(rng, d):
    raw = rng.randrange(180, 900, 60)
    df = rng.choice([25, 50, 100, 150, 300])
    final = raw * 100 // (100 + df)
    text = (f"فرمولِ آسیبِ نهایی = آسیبِ خام × 100 ÷ (100 + DEF). ضربه‌ای با آسیبِ خامِ {raw} "
            f"به دشمنی با DEF = {df} می‌خوره. آسیبِ نهایی؟")
    return _build(rng, "combat", text, final, [raw - df, raw // 2, raw * 100 // max(1, df + 50), raw - final])


def _c_sustain(rng, d):
    mx = rng.randrange(600, 1100, 100)
    hit = rng.randrange(60, 130, 10)
    dealt = rng.randrange(200, 500, 100)
    ls = rng.choice([10, 15, 20, 25])
    turns = rng.randrange(3, 6) if d == 1 else rng.randrange(5, 9)
    heal = dealt * ls // 100
    hp = mx
    start = mx - rng.randrange(1, 4) * 100 if d >= 2 else mx
    hp = start
    for _ in range(turns):
        hp -= hit
        hp += heal
        hp = min(hp, mx)
    cap = " (HP هیچ‌وقت از MaxHP بالاتر نمی‌ره)" if d >= 2 else ""
    text = (f"MaxHP تو {mx} و الان {start} HP داری. هر نوبت دشمن {hit} آسیب می‌زنه و تو "
            f"{dealt} آسیب می‌زنی و {ls}٪ از آسیبت رو lifesteal می‌کنی{cap}. "
            f"(ترتیب هر نوبت: اول دشمن می‌زنه، بعد heal.) بعد از {turns} نوبت چند HP داری؟")
    naive = start - turns * hit
    return _build(rng, "combat", text, hp, [naive, start - turns * hit + turns * heal + hit, hp + heal, hp - heal])


def _c_shield(rng, d):
    shield = rng.randrange(200, 500, 50)
    hp = rng.randrange(300, 700, 50)
    dmg = rng.randrange(120, 260, 10)
    regen = rng.choice([30, 40, 50])
    sh, h, turn = shield, hp, 0
    while h > 0 and turn < 60:
        turn += 1
        if sh > 0:
            absorbed = min(sh, dmg)
            sh -= absorbed
            h -= dmg - absorbed
            if sh > 0:
                sh += regen
        else:
            h -= dmg
    text = (f"باس {shield} سپر و {hp} HP داره. هر نوبت {dmg} آسیب بهش می‌زنی. آسیب اول از سپر کم می‌شه "
            f"و اگه اضافه بیاد از HP. اگه بعد از ضربه سپر هنوز صفر نشده باشه، {regen} سپر ترمیم می‌شه. "
            f"باس تو چندمین نوبت می‌میره؟")
    return _build(rng, "combat", text, turn, [math.ceil((shield + hp) / dmg), turn - 1, turn + 1])


COMBAT_GENS = {1: [_c_hits_to_kill, _c_buff_stack, _c_defense],
               2: [_c_hits_to_kill, _c_buff_stack, _c_defense, _c_sustain],
               3: [_c_sustain, _c_shield, _c_buff_stack, _c_hits_to_kill, _c_defense]}


# ═══ 🔮 magic ════════════════════════════════════════════════
def _m_element_chain(rng, d):
    k = 4 if d == 1 else 5
    cyc = rng.sample(ELEMENT_NAMES, k)          # cyc[i] بر cyc[i+1] غلبه داره
    rules = [f"{cyc[i]} بر {cyc[(i + 1) % k]} غلبه داره" for i in range(k)]
    rng.shuffle(rules)
    target_i = rng.randrange(k)
    target = cyc[target_i]
    steps = {1: 1, 2: 2, 3: 3}[d]
    ans = cyc[(target_i - steps) % k]
    if steps == 1:
        q = f"کدوم عنصر بر «{target}» غلبه داره؟"
    elif steps == 2:
        q = f"عنصری که بر «{target}» غلبه داره، خودش از دستِ کدوم عنصر ضعیفه؟"
    else:
        q = f"زنجیره رو سه قدم از «{target}» عقب برو: عنصرِ غالب بر غالب بر غالبِ «{target}» کیه؟"
    text = "قوانینِ عناصر (غلبه یعنی ضربه‌ی قوی‌تر): " + "؛ ".join(rules) + ".\n" + q
    wrongs = [e for e in cyc if e != ans]
    return _build(rng, "magic", text, ans, wrongs, numeric=False)


def _m_mana(rng, d):
    mx = rng.randrange(60, 130, 10)
    cost = rng.randrange(20, 41, 5)
    regen = rng.randrange(5, cost - 4, 5)
    turns = rng.randrange(5, 8) if d == 1 else rng.randrange(8, 13)
    mana, casts = mx, 0
    for _ in range(turns):
        if mana >= cost:
            mana -= cost
            casts += 1
        mana = min(mx, mana + regen)
    text = (f"منای تو {mx}ـه (و پر شروع می‌کنی). هر کست {cost} منا می‌خوره. آخرِ هر نوبت {regen} منا "
            f"برمی‌گرده (سقف: {mx}). هر نوبت اگه منا کافی باشه حتماً کست می‌کنی. "
            f"تو {turns} نوبت چند بار کست می‌کنی؟")
    return _build(rng, "magic", text, casts, [turns, mx // cost, casts - 1, casts + 1])


def _m_cooldown(rng, d):
    cd = rng.randrange(2, 5)
    turns = rng.randrange(10, 17)
    casts = math.ceil(turns / (cd + 1))
    if d >= 2:
        cd2 = cd + rng.randrange(2, 4)
        t2 = 0
        t_a = t_b = 1
        for t in range(1, turns + 1):
            if t >= t_a:
                t_a = t + cd + 1
                t2 += 1
            elif t >= t_b:
                t_b = t + cd2 + 1
                t2 += 1
        text = (f"دو اسپل داری؛ A با کول‌داونِ {cd} نوبت و B با کول‌داونِ {cd2} نوبت (کول‌داونِ N یعنی بعد از کست، "
                f"N نوبتِ بعدی نمی‌تونی همون اسپل رو بزنی). هر نوبت فقط یه اسپل می‌زنی و اولویت با A ـه. "
                f"هر دو از نوبتِ ۱ آماده‌ان. تو {turns} نوبت جمعاً چند اسپل می‌زنی؟")
        return _build(rng, "magic", text, t2, [casts, turns, turns - casts, t2 + 1])
    text = (f"اسپلی با کول‌داونِ {cd} نوبت داری (یعنی بعد از کست، {cd} نوبتِ بعدی نمی‌تونی بزنیش). "
            f"از نوبتِ ۱ آماده‌ست. تو {turns} نوبت حداکثر چند بار می‌تونی بزنیش؟")
    return _build(rng, "magic", text, casts, [turns // cd, casts + 1, casts - 1])


def _m_resist(rng, d):
    base = rng.randrange(200, 800, 40)
    res = rng.choice([10, 20, 25, 40, 50])
    final = int(base * 1.5 * (100 - res) / 100)
    if d == 1:
        text = (f"جادوت {base} آسیبِ پایه داره. دشمن به عنصرِ تو ضعیفه (آسیب ×1.5) و {res}٪ مقاومتِ عمومی داره "
                f"(آسیب رو {res}٪ کم می‌کنه). آسیبِ نهایی؟")
    else:
        res2 = rng.choice([10, 20, 25])
        final = int(base * 1.5 * (100 - res) * (100 - res2) / 10000)
        text = (f"جادوت {base} آسیبِ پایه داره. دشمن به عنصرِ تو ضعیفه (×1.5)، {res}٪ مقاومتِ عمومی و "
                f"{res2}٪ مقاومتِ جداگانه داره (مقاومت‌ها ضربی روی هم اعمال می‌شن). آسیبِ نهایی؟")
        return _build(rng, "magic", text, final,
                      [int(base * 1.5 * (100 - res - res2) / 100), int(base * (100 - res) * (100 - res2) / 10000),
                       int(base * 1.5 * (100 - res) / 100)])
    return _build(rng, "magic", text, final, [int(base * (100 - res) / 100), int(base * 1.5), int(base * (1.5 - res / 100))])


MAGIC_GENS = {1: [_m_element_chain, _m_mana, _m_cooldown, _m_resist],
              2: [_m_element_chain, _m_mana, _m_cooldown, _m_resist],
              3: [_m_element_chain, _m_cooldown, _m_resist, _m_mana]}


# ═══ 📚 lore (از دیتای واقعیِ بازی) ═══════════════════════════
def _lore_data():
    from world_tiers import WORLD_TIERS, ASCENSION_TRIALS, MAP_WORLD_TIER
    return WORLD_TIERS, ASCENSION_TRIALS, MAP_WORLD_TIER


def _l_trial_unlocks(rng, d):
    tiers, trials, _ = _lore_data()
    unlock = {t["ascension_required"]: n for n, t in tiers.items() if t["ascension_required"]}
    tid = rng.choice(list(unlock))
    n = unlock[tid]
    text = f"با رد کردنِ «{trials[tid]['name']}» کدوم تیرِ جهان باز می‌شه؟"
    ans = tiers[n]["name"]
    wrongs = [t["name"] for k, t in tiers.items() if k != n]
    return _build(rng, "lore", text, ans, wrongs, numeric=False)


def _l_trial_level(rng, d):
    _, trials, _ = _lore_data()
    tid = rng.choice(list(trials))
    ans = trials[tid]["min_level"]
    wrongs = [t["min_level"] for k, t in trials.items() if k != tid] + [ans + 5, ans - 5]
    text = f"حداقل لولِ لازم برای تلاش در «{trials[tid]['name']}» چنده؟"
    return _build(rng, "lore", text, ans, wrongs)


def _l_map_tier(rng, d):
    tiers, _, maps = _lore_data()
    name = rng.choice([m for m in maps if m != "Abyssal Black Market"])
    n = maps[name]
    ans = f"Tier {n}"
    wrongs = [f"Tier {k}" for k in tiers if k != n]
    text = f"مپِ «{name}» تو کدوم World Tier قرار داره؟"
    return _build(rng, "lore", text, ans, wrongs, numeric=False)


def _l_trial_penalty(rng, d):
    _, trials, _ = _lore_data()
    tid = rng.choice(list(trials))
    pct = int(trials[tid]["fail_hp_penalty"] * 100)
    if rng.random() < 0.5:
        text = f"شکست تو «{trials[tid]['name']}» چند درصد از MaxHP رو کم می‌کنه؟"
        wrongs = [int(t["fail_hp_penalty"] * 100) for k, t in trials.items() if k != tid] + [pct + 10, pct - 10]
        q = _build(rng, "lore", text, pct, wrongs)
        q["o"] = [o + "٪" for o in q["o"]]
        return q
    hrs = trials[tid]["retry_cooldown"] / 3600
    ans = f"{hrs:g} ساعت"
    wrongs = [f"{t['retry_cooldown'] / 3600:g} ساعت" for k, t in trials.items() if k != tid]
    text = f"بعد از شکست تو «{trials[tid]['name']}» چقدر باید صبر کنی تا دوباره تلاش کنی؟"
    return _build(rng, "lore", text, ans, wrongs, numeric=False)


def _l_academy(rng, d):
    import academy_system as acs
    stat_fa = {"atk": "حمله (ATK)", "def": "دفاع (DEF)", "max_hp": "جانِ حداکثر (MaxHP)"}
    kind = rng.choice(["subject", "enroll", "cooldown", "years"])
    if kind == "subject":
        sid = rng.choice(list(acs.SUBJECTS))
        s = acs.SUBJECTS[sid]
        text = f"کلاسِ «{s['name']}» تو آکادمی کدوم استت رو بالا می‌بره؟"
        ans = stat_fa[s["stat"]]
        wrongs = [v for k, v in stat_fa.items() if k != s["stat"]] + ["شانسِ کریتیکال (Crit)"]
        return _build(rng, "lore", text, ans, wrongs, numeric=False)
    if kind == "enroll":
        a = acs.ENROLL_LEVEL_REQ
        return _build(rng, "lore", "حداقل لولِ لازم برای ثبت‌نام تو آکادمی چنده؟", a, [a + 2, a - 3, a + 7, a * 2])
    if kind == "cooldown":
        h = acs.CLASS_COOLDOWN // 3600
        q = _build(rng, "lore", "فاصله‌ی بینِ دو کلاسِ آکادمی چند ساعته؟", h, [h * 2, h + 3, 1, 12])
        q["o"] = [o + " ساعت" for o in q["o"]]
        return q
    y = acs.YEARS_TOTAL
    return _build(rng, "lore", "دوره‌ی آکادمی چند سال طول می‌کشه؟", y, [y + 1, y - 1, y + 2, 5])


LORE_GENS = {1: [_l_trial_unlocks, _l_trial_level, _l_academy],
             2: [_l_trial_unlocks, _l_trial_level, _l_academy, _l_map_tier, _l_trial_penalty],
             3: [_l_map_tier, _l_trial_penalty, _l_trial_level, _l_trial_unlocks, _l_academy]}

_GENS = {"combat": COMBAT_GENS, "magic": MAGIC_GENS, "lore": LORE_GENS}
_ORDER = ["combat", "magic", "lore"]


def build_questions(year: int, n: int, rng: random.Random | None = None) -> list[dict]:
    """n سؤالِ متنوع، بین سه درس تقسیم‌شده، با درجه‌ی سختیِ سالِ مربوطه."""
    rng = rng or random.Random()
    d = min(3, max(1, year))
    pools = {s: list(_GENS[s][d]) for s in _ORDER}
    for p in pools.values():
        rng.shuffle(p)
    used_text: set[str] = set()
    out: list[dict] = []
    i = 0
    guard = 0
    while len(out) < n and guard < n * 20:
        guard += 1
        subj = _ORDER[i % 3]
        i += 1
        if not pools[subj]:
            pools[subj] = list(_GENS[subj][d])
            rng.shuffle(pools[subj])
        q = pools[subj].pop()(rng, d)
        if q["t"] in used_text:
            continue
        used_text.add(q["t"])
        out.append(q)
    return out
