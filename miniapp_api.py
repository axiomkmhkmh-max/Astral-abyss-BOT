# ============================================================
#  Astral Abyss — Mini App API (aiohttp)   ·   نسخه‌ی کامل
#  استفاده:  from miniapp_api import register_miniapp; register_miniapp(app)
#  ENV لازم: BOT_TOKEN   |  اختیاری: MINIAPP_URL
#
#  بخش‌ها:  سفر/لوت/فروش (قبلی)  ·  اکتشاف مکان‌ها + ساختمون چندطبقه
#           بازار سیاه (فروشگاه، فروش، صندوق/کلید)  ·  بانک (سپرده، وام، انتقال، PIN)
#           گیلدها (عضویت، کوئست روایی، آزمون رتبه، اکشن، فروشگاه، خزانه، جنگ هفتگی)
#  همه‌ی منطق‌ها از همون ماژول‌های خودِ ربات صدا زده می‌شن (تکرار منطق نداریم).
# ============================================================
import os, re, time, json, hmac, hashlib, pathlib, asyncio
from urllib.parse import parse_qsl
from aiohttp import web

from database import aget_player, asave_player, player_lock
from economy import (MAPS_DATA, MAP_LOOT, MAP_LOCATIONS, DEFAULT_LOCATIONS, roll_loot,
                     get_travel_time, get_market_items, RARITY_E)
from economy_engine import add_reputation, get_reputation_discount
from economy_ledger import record_transaction
import async_bridge as bridge
from loot_handlers import get_ls, use_action, DAILY_MAX
import bank_system as bs
import guild_system as gs

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HERE = pathlib.Path(__file__).parent

# ۱۴ قلمرو اصلی؛ بازار سیاه و تخت فراموشی جدا (بخش «مکان‌های ویژه») نمایش داده می‌شن
EXTRA_REALMS = {"Abyssal Black Market", "Throne of Oblivion"}


# ───────────────────────── ابزارهای پایه ─────────────────────────
def _find_index():
    for p in (HERE / "miniapp" / "index.html", HERE / "miniapp_index.html", HERE / "index.html"):
        if p.exists():
            return p
    return None


def verify_init_data(raw: str, max_age: int = 86400):
    """اعتبارسنجی initData تلگرام؛ خروجی: user dict یا None"""
    try:
        data = dict(parse_qsl(raw, keep_blank_values=True))
        got = data.pop("hash", "")
        check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
        key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        if time.time() - int(data.get("auth_date", 0)) > max_age:
            return None
        return json.loads(data["user"])
    except Exception:
        return None


def _err(msg, code=400):
    return web.json_response({"error": msg}, status=code)


_MD = re.compile(r"\*+|__|`")
_IT = re.compile(r"(?<![\w])_([^_\n]+)_(?![\w])")


def _plain(t) -> str:
    """متن‌های مارک‌داونِ ربات (**بولد**، *ایتالیک*، _ایتالیک_) رو برای نمایش تو مینی‌اپ تمیز می‌کنه"""
    return _MD.sub("", _IT.sub(r"\1", str(t or ""))).strip()


def _int(v, lo=1):
    try:
        n = int(str(v).replace(",", "").replace("٬", "").strip())
        return n if n >= lo else None
    except Exception:
        return None


async def _body(request) -> dict:
    try:
        b = await request.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


def _uid(request):
    user = verify_init_data(request.headers.get("X-Init-Data", ""))
    if not user:
        return None, _err("unauthorized", 401)
    return user["id"], None


async def _load(uid):
    """بازیکن رو می‌خونه و اگه سفر تموم شده، مقصد رو ثبت می‌کنه"""
    player = await aget_player(uid)
    if not player:
        return None
    s = get_ls(uid)  # اگه سفر تموم شده، traveling خودش None می‌شه
    if not s.get("traveling") and s.get("dest"):
        player["map"] = s.pop("dest")
        await asave_player(uid, player)
    return player


async def _auth(request):
    uid, err = _uid(request)
    if err:
        return None, None, err
    player = await _load(uid)
    if not player:
        return None, None, _err("اول تو ربات /start بزن", 404)
    return uid, player, None


def _state(uid, player):
    s = get_ls(uid)
    now = time.time()
    traveling = s.get("traveling")
    return {
        "name": player.get("name") or player.get("first_name") or "",
        "level": player.get("level", 1),
        "xp": player.get("xp", 0),
        "gender": player.get("gender", "male"), "cls": player.get("class", "adventurer"),
        "hp": player.get("hp", 0), "max_hp": player.get("max_hp", 100),
        "zen": player.get("zen", 0),
        "map": player.get("map"),
        "traveling": traveling,
        "travel_left": max(0, int(s.get("arrive", 0) - now)) if traveling else 0,
        "travel_total": int(s.get("travel_total", 0)) if traveling else 0,
        "actions": s.get("actions", 0),
        "daily_left": DAILY_MAX - s.get("daily_used", 0),
        "inventory": [
            {"name": i.get("name"), "emoji": i.get("emoji", ""), "rarity": i.get("rarity", "common"),
             "sell": i.get("sell", 0), "qty": i.get("qty", 1), "desc": i.get("desc", ""),
             "locked": bool(i.get("shop_exclusive"))}
            for i in player.get("inventory", [])
        ],
    }


def _items_out(items):
    return [{"name": i.get("name"), "emoji": i.get("emoji", ""), "rarity": i.get("rarity", "common")} for i in items]


# ───────────────────────── قلمروها / سفر / لوت سریع ─────────────────────────
async def realms(request):
    out = []
    for key, d in MAPS_DATA.items():
        out.append({
            "key": key, "zone": d["zone"], "tier": d["tier"], "travel": d["travel"],
            "core": key not in EXTRA_REALMS, "secs": get_travel_time(key),
            "desc": d["desc"],
            "places": [{"name": p["name"], "desc": p.get("desc", "")} for p in MAP_LOCATIONS.get(key, [])],
            "loot": [{"name": i["name"], "rarity": i["rarity"]} for i in MAP_LOOT.get(key, [])],
        })
    return web.json_response(out)


async def me(request):
    uid, player, err = await _auth(request)
    if err: return err
    return web.json_response(_state(uid, player))


async def travel(request):
    uid, player, err = await _auth(request)
    if err: return err
    dest = (await _body(request)).get("map")
    if dest not in MAPS_DATA:
        return _err("قلمرو نامعتبر")
    s = get_ls(uid)
    if s.get("traveling"):
        return _err("هنوز در سفری")
    if s.get("actions", 0) <= 0:
        return _err("اقدام نداری")
    secs = 0 if player.get("map") == dest else get_travel_time(dest, player.get("zen", 0))
    s["traveling"] = dest if secs else None
    s["arrive"] = time.time() + secs
    s["travel_total"] = secs
    s["dest"] = dest if secs else None
    s["travel_token"] = s.get("travel_token", 0) + 1
    if not secs:
        player["map"] = dest
    else:
        s["daily_travel_used"] = s.get("daily_travel_used", 0) + 1
    await asave_player(uid, player)
    return web.json_response(_state(uid, player))


async def loot(request):
    """لوتِ سریعِ قلمرو (مثل قبل)"""
    uid, player, err = await _auth(request)
    if err: return err
    s = get_ls(uid)
    if s.get("traveling"):
        return _err("در حال سفری")
    realm = player.get("map")
    if realm not in MAPS_DATA:
        return _err("اول یه قلمرو انتخاب کن")
    if not await use_action(uid):
        return _err("اقدام یا سقف روزانه تموم شده")
    async with player_lock(uid):
        player = await _load(uid)
        found = roll_loot(realm, 5, player.get("level", 1))
        player.setdefault("inventory", []).extend(found)
        await asave_player(uid, player)
    st = _state(uid, player)
    st["found"] = _items_out(found)
    return web.json_response(st)


async def sell(request):
    """فروش آیتم‌ها؛ منطق و مالیات دقیقاً مثل cb_loot_sell_all داخل ربات."""
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        inv = player.get("inventory", [])
        if body.get("all"):
            picked = [i for i in inv if not i.get("shop_exclusive")]
        else:
            nm, em = body.get("name"), body.get("emoji", "")
            picked = [i for i in inv if i.get("name") == nm and i.get("emoji", "") == em and not i.get("shop_exclusive")]
        if not picked:
            return _err("آیتمی برای فروش نیست")
        zone = MAPS_DATA.get(player.get("map", ""), {}).get("zone", "contested")
        gross = 0
        for item in picked:
            _, sell_p, _, _ = await bridge.economy_engine.get_dynamic_price("global_loot", item)
            gross += sell_p
            await bridge.economy_engine.register_trade("global_loot", item, "sell")
        tax = await bridge.economy_engine.compute_sell_tax(player, gross, zone, "global_loot")
        zen_before = player.get("zen", 0)
        ids = {id(i) for i in picked}
        player["inventory"] = [i for i in inv if id(i) not in ids]
        player["zen"] = zen_before + tax["net"]
        add_reputation(player, min(3, len(picked)))
        await asave_player(uid, player)
    await bridge.economy_engine.deposit_tax_pool(tax["tax_amount"], uid)
    record_transaction("miniapp_sell", uid, username=player.get("name"),
                       item_name=f"{len(picked)} آیتم", quantity=len(picked),
                       amount=gross, fee=tax["tax_amount"],
                       balance_before=zen_before, balance_after=player["zen"],
                       extra={"zone": zone})
    st = _state(uid, player)
    st["sold"] = {"count": len(picked), "gross": gross, "tax": tax["tax_amount"], "net": tax["net"]}
    return web.json_response(st)


# ───────────────────────── اکتشاف مکان‌ها + داستان ─────────────────────────
def _locs(realm):
    return MAP_LOCATIONS.get(realm, DEFAULT_LOCATIONS)


def _run_state(uid):
    """وضعیت ساختمونِ چندطبقه‌ی در جریان (حافظه‌ی مشترک با ربات)"""
    try:
        from abandoned_locations import _building_runs, BUILDING_MAX_FLOOR, _floor_risk
    except Exception:
        return None
    run = _building_runs.get(uid)
    if not run:
        return None
    f = run["floor"]
    return {"map": run["map"], "floor": f, "max": BUILDING_MAX_FLOOR, "zen": run["zen"],
            "items": _items_out(run["items"]),
            "can_continue": f < BUILDING_MAX_FLOOR,
            "next_risk": int(_floor_risk(f + 1) * 100) if f < BUILDING_MAX_FLOOR else None}


KIND_FA = {"building": "ساختمان متروکه", "house": "خانه‌ی متروکه", "hospital": "بیمارستان متروکه", "bank": "بانک متروکه"}


async def map_info(request):
    uid, player, err = await _auth(request)
    if err: return err
    realm = player.get("map")
    if realm not in MAPS_DATA:
        return web.json_response({"map": None, "locations": [], "run": None})
    explored = set(player.get("explored", {}).get(realm, []))
    locs = []
    for i, l in enumerate(_locs(realm)):
        ex = i in explored
        locs.append({"idx": i, "explored": ex,
                     "name": l["name"] if ex else None, "emoji": l.get("emoji", "📍") if ex else "🌫️",
                     "desc": l.get("desc", "") if ex else "",
                     "kind": KIND_FA.get(l.get("type", "building"), "") if ex else "",
                     "type": l.get("type", "building") if ex else None})
    cds = player.get("bank_heist_cooldowns", {})
    return web.json_response({
        "map": realm, "locations": locs, "explored": len(explored), "total": len(locs),
        "run": _run_state(uid), "heist_wait": max(0, int(cds.get(realm, 0) - time.time())),
        "sick": max(0, int(player.get("sickness_until", 0) - time.time())),
    })


def _loot_story(loc, found, zen=0):
    """یه روایت کوتاه از چیزی که پیدا شد"""
    if not found:
        return f"{loc.get('desc', '')}. بین آوار گشتی ولی دست‌خالی برگشتی."
    order = ["common", "uncommon", "rare", "epic", "mythic", "legendary"]
    best = max(found, key=lambda i: order.index(i.get("rarity", "common")) if i.get("rarity", "common") in order else 0)
    r = best.get("rarity", "common")
    tail = {"common": "چیز خاصی نبود، ولی بی‌ارزش هم نبود.", "uncommon": "به درد بخور بود.",
            "rare": "برق چیزی چشمت رو گرفت — یه یافته‌ی نادر!",
            "epic": "قلبت تند زد؛ این یکی واقعاً ارزش داشت!",
            "mythic": "هوا سنگین شد... چیزی اسطوره‌ای دستت اومد.",
            "legendary": "سکوت مطلق. یه گنجینه‌ی افسانه‌ای تو دستاته."}.get(r, "")
    return (f"{loc.get('desc', '')}. وسط جستجو، {best.get('emoji', '')} {best.get('name', '')} رو پیدا کردی. {tail}")


async def explore(request):
    uid, err = _uid(request)
    if err: return err
    idx = _int((await _body(request)).get("idx"), lo=0)
    probe = await _load(uid)
    if not probe:
        return _err("اول تو ربات /start بزن", 404)
    s = get_ls(uid)
    if s.get("traveling"):
        return _err("در حال سفری")
    realm = probe.get("map")
    if realm not in MAPS_DATA:
        return _err("اول یه قلمرو انتخاب کن")
    locs = _locs(realm)
    if idx is None or idx >= len(locs):
        return _err("مکان نامعتبر")
    if _run_state(uid):
        return _err("هنوز تو یه ساختمون هستی؛ اول خارج شو یا ادامه بده")
    if probe.get("zen", 0) <= 0:
        return _err("ورشکسته‌ای! اول یه آیتم بفروش")
    if not await use_action(uid):
        return _err("اقدام یا سقف روزانه تموم شده")

    from fog_of_war import mark_explored, grant_discovery_reward
    loc = locs[idx]
    ltype = loc.get("type", "building")
    async with player_lock(uid):
        player = await _load(uid)
        discovery = None
        if mark_explored(player, realm, idx):
            discovery = grant_discovery_reward(player)
        story = {"title": loc["name"], "emoji": loc.get("emoji", "📍"), "kind": KIND_FA.get(ltype, ""), "type": ltype}
        found, alarm, busted = [], False, False

        if ltype == "building":
            from abandoned_locations import start_building_run
            res = start_building_run(uid, player, realm)
            story["text"] = _plain(loc.get("desc", "")) + "\n\n" + _plain(res["text"])
            busted = res.get("busted", False)
        elif ltype in ("house", "hospital", "bank"):
            from abandoned_locations import visit_location
            res = visit_location(player, loc, realm)
            text = _plain(res.get("text", ""))
            if res.get("spawn_alarm"):
                alarm = True
                dmg = max(1, int(player.get("max_hp", 100) * 0.12))
                player["hp"] = max(1, player.get("hp", 100) - dmg)
                text += f"\n\nنگهبان رسید! مجبور شدی فرار کنی و {dmg} HP از دست دادی. (نبرد با نگهبان فقط تو ربات انجام می‌شه)"
            story["text"] = _plain(loc.get("desc", "")) + "\n\n" + text
        else:
            found = roll_loot(realm, 5, player.get("level", 1))
            player.setdefault("inventory", []).extend(found)
            story["text"] = _loot_story(loc, found)
        try:
            from combat_handlers import update_quest
            update_quest(uid, "loot", 1)
        except Exception:
            pass
        await asave_player(uid, player)

    st = _state(uid, player)
    st.update({"story": story, "found": _items_out(found), "discovery": discovery,
               "alarm": alarm, "busted": busted, "run": _run_state(uid)})
    return web.json_response(st)


async def building_continue(request):
    uid, err = _uid(request)
    if err: return err
    from abandoned_locations import _advance_floor, _building_runs
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        if uid not in _building_runs:
            return _err("این سفر دیگه معتبر نیست")
        res = _advance_floor(uid, player)
        await asave_player(uid, player)
    st = _state(uid, player)
    st["story"] = {"text": _plain(res["text"]), "busted": bool(res.get("busted")), "floor": res.get("floor")}
    st["busted"] = bool(res.get("busted"))
    st["run"] = _run_state(uid)
    return web.json_response(st)


async def building_leave(request):
    uid, err = _uid(request)
    if err: return err
    from abandoned_locations import _cash_out, _building_runs
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        if uid not in _building_runs:
            return _err("سفری در جریان نیست")
        res = _cash_out(uid, player)
        await asave_player(uid, player)
    st = _state(uid, player)
    st["story"] = {"text": _plain(res["text"]), "left": True}
    st["run"] = None
    return web.json_response(st)


# ───────────────────────── بازار سیاه ─────────────────────────
def _discount_mult():
    try:
        from loot_handlers import _market_discount_mult
        return _market_discount_mult()
    except Exception:
        return 1.0


def _sellable_groups(inv):
    groups = {}
    for it in inv:
        if it.get("shop_exclusive"):
            continue
        k = (it.get("name"), it.get("emoji", ""), it.get("rarity", "common"))
        groups.setdefault(k, []).append(it)
    return groups


async def bm_info(request):
    uid, player, err = await _auth(request)
    if err: return err
    items = get_market_items()
    mult = _discount_mult()
    shop = []
    for i, it in enumerate(items):
        buy_p, _, arrow, _ = await bridge.economy_engine.get_dynamic_price("blackmarket_shop", it)
        shop.append({"idx": i, "name": it["name"], "emoji": it.get("emoji", ""), "rarity": it.get("rarity", "common"),
                     "price": int(buy_p * mult), "arrow": arrow, "desc": it.get("desc", "")})
    events = await bridge.economy_engine.get_active_events_display()
    overview = await bridge.economy_engine.get_market_overview("blackmarket_shop", items)
    trim = lambda rows: [{"name": r["name"], "emoji": r.get("emoji", ""), "mult": r.get("mult"), "buy": r.get("buy")} for r in rows]

    quotes, gross = [], 0
    for (nm, em, rar), its in _sellable_groups(player.get("inventory", [])).items():
        _, unit, arrow, _ = await bridge.economy_engine.get_dynamic_price("global_loot", its[0])
        total = 0
        for it in its:
            _, sp, _, _ = await bridge.economy_engine.get_dynamic_price("global_loot", it)
            total += sp
        gross += total
        quotes.append({"name": nm, "emoji": em, "rarity": rar, "qty": len(its), "unit": unit, "total": total, "arrow": arrow})
    tax = await bridge.economy_engine.compute_sell_tax(player, gross, "safe", "blackmarket_shop") if gross else \
        {"net": 0, "tax_amount": 0, "tax_rate": 0, "tax_free_event": False}

    inv = player.get("inventory", [])
    try:
        from loot_engine import LOCKBOXES, KEYS, FORTUNE_WARD_PRICE
        key_have = {}
        for it in inv:
            if it.get("type") == "key":
                key_have[it.get("key_id")] = key_have.get(it.get("key_id"), 0) + 1
        boxes = []
        for i, it in enumerate(inv):
            if it.get("type") == "lockbox":
                need = LOCKBOXES.get(it.get("box_id"), {}).get("key")
                boxes.append({"i": i, "name": it.get("name"), "emoji": it.get("emoji", "📦"),
                              "need": KEYS.get(need, {}).get("name", "?"), "has_key": key_have.get(need, 0) > 0})
        vault = {"boxes": boxes,
                 "keys": [{"id": k, "name": v["name"], "emoji": v["emoji"], "price": v["buy_price"], "have": key_have.get(k, 0)}
                          for k, v in KEYS.items()],
                 "ward_price": FORTUNE_WARD_PRICE, "ward_count": player.get("fortune_ward_count", 0)}
    except Exception:
        vault = {"boxes": [], "keys": [], "ward_price": 0, "ward_count": 0}

    return web.json_response({
        "zen": player.get("zen", 0), "rep": player.get("bm_reputation", 0),
        "discount_pct": int(get_reputation_discount(player) * 100), "sale": mult < 1.0,
        "shop": shop, "events": [_plain(e) for e in events],
        "gainers": trim(overview.get("gainers", [])), "losers": trim(overview.get("losers", [])),
        "tax_pool": await bridge.economy_engine.get_tax_pool(),
        "quotes": quotes, "sell": {"gross": gross, "tax": tax["tax_amount"], "net": tax["net"],
                                   "rate": round(tax["tax_rate"] * 100, 1), "free": bool(tax["tax_free_event"])},
        "vault": vault,
    })


async def bm_buy(request):
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    idx = _int(body.get("idx"), lo=0)
    items = get_market_items()
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        if idx is None or idx >= len(items) or items[idx]["name"] != body.get("name"):
            return _err("بازار به‌روز شد؛ صفحه رو دوباره باز کن")
        if player.get("zen", 0) <= 0:
            return _err("ورشکسته‌ای! اول یه آیتم بفروش")
        item = items[idx]
        buy_p, _, _, _ = await bridge.economy_engine.get_dynamic_price("blackmarket_shop", item)
        buy_p = int(buy_p * _discount_mult())
        bill = await bridge.economy_engine.compute_buy_total(player, buy_p, "safe", "blackmarket_shop")
        if player.get("zen", 0) < bill["total"]:
            return _err(f"Zen کافی نداری ({player.get('zen', 0):,}/{bill['total']:,})")
        zen_before = player["zen"]
        player["zen"] -= bill["total"]
        player.setdefault("inventory", []).append(item.copy())
        add_reputation(player, 1)
        await asave_player(uid, player)
    await bridge.economy_engine.register_trade("blackmarket_shop", item, "buy")
    await bridge.economy_engine.deposit_tax_pool(bill["vat_amount"], uid)
    record_transaction("bm_buy", uid, username=player.get("name"), item_name=item.get("name"),
                       item_id=item.get("id"), rarity=item.get("rarity"), amount=bill["total"], fee=bill["vat_amount"],
                       balance_before=zen_before, balance_after=player["zen"], note="miniapp")
    st = _state(uid, player)
    st["bought"] = {"name": item["name"], "emoji": item.get("emoji", ""), "total": bill["total"], "vat": bill["vat_amount"]}
    return web.json_response(st)


async def bm_sell(request):
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        inv = player.get("inventory", [])
        if body.get("all"):
            picked = [i for i in inv if not i.get("shop_exclusive")]
        else:
            nm, em = body.get("name"), body.get("emoji", "")
            picked = [i for i in inv if i.get("name") == nm and i.get("emoji", "") == em and not i.get("shop_exclusive")]
        if not picked:
            return _err("آیتمی برای فروش نیست")
        gross = 0
        for item in picked:
            _, sp, _, _ = await bridge.economy_engine.get_dynamic_price("global_loot", item)
            gross += sp
            await bridge.economy_engine.register_trade("global_loot", item, "sell")
        tax = await bridge.economy_engine.compute_sell_tax(player, gross, "safe", "blackmarket_shop")
        zen_before = player.get("zen", 0)
        ids = {id(i) for i in picked}
        player["inventory"] = [i for i in inv if id(i) not in ids]
        player["zen"] = zen_before + tax["net"]
        add_reputation(player, min(3, len(picked)))
        await asave_player(uid, player)
    await bridge.economy_engine.deposit_tax_pool(tax["tax_amount"], uid)
    record_transaction("bm_sell_all", uid, username=player.get("name"), item_name=f"{len(picked)} آیتم",
                       quantity=len(picked), amount=gross, fee=tax["tax_amount"],
                       balance_before=zen_before, balance_after=player["zen"], extra={"src": "miniapp"})
    st = _state(uid, player)
    st["sold"] = {"count": len(picked), "gross": gross, "tax": tax["tax_amount"], "net": tax["net"]}
    return web.json_response(st)


async def bm_key(request):
    uid, err = _uid(request)
    if err: return err
    from loot_engine import KEYS
    kid = (await _body(request)).get("id")
    if kid not in KEYS:
        return _err("کلید نامعتبر")
    k = KEYS[kid]
    async with player_lock(uid):
        player = await _load(uid)
        if player.get("zen", 0) < k["buy_price"]:
            return _err("Zen کافی نداری")
        zb = player["zen"]
        player["zen"] -= k["buy_price"]
        player.setdefault("inventory", []).append(
            {"name": k["name"], "emoji": k["emoji"], "type": "key", "key_id": kid, "sell": int(k["buy_price"] * 0.3)})
        await asave_player(uid, player)
    record_transaction("bm_key_buy", uid, username=player.get("name"), item_name=k.get("name"), item_id=kid,
                       amount=k["buy_price"], balance_before=zb, balance_after=player["zen"])
    return web.json_response(_state(uid, player))


async def bm_ward(request):
    uid, err = _uid(request)
    if err: return err
    from loot_engine import FORTUNE_WARD_PRICE
    async with player_lock(uid):
        player = await _load(uid)
        if player.get("zen", 0) < FORTUNE_WARD_PRICE:
            return _err("Zen کافی نداری")
        zb = player["zen"]
        player["zen"] -= FORTUNE_WARD_PRICE
        player["fortune_ward_count"] = player.get("fortune_ward_count", 0) + 1
        await asave_player(uid, player)
    record_transaction("bm_ward_buy", uid, username=player.get("name"), item_name="fortune_ward",
                       amount=FORTUNE_WARD_PRICE, balance_before=zb, balance_after=player["zen"])
    return web.json_response(_state(uid, player))


async def bm_open(request):
    uid, err = _uid(request)
    if err: return err
    from loot_engine import LOCKBOXES, open_lockbox
    idx = _int((await _body(request)).get("i"), lo=0)
    async with player_lock(uid):
        player = await _load(uid)
        inv = player.get("inventory", [])
        if idx is None or idx >= len(inv) or inv[idx].get("type") != "lockbox":
            return _err("این صندوق دیگه وجود نداره")
        box = inv[idx]
        need = LOCKBOXES[box["box_id"]]["key"]
        kidx = next((i for i, it in enumerate(inv) if it.get("type") == "key" and it.get("key_id") == need), None)
        if kidx is None:
            return _err("کلید مناسب این صندوق رو نداری")
        results = open_lockbox(player, player.get("map"), box["box_id"])
        for i in sorted([idx, kidx], reverse=True):
            inv.pop(i)
        gained = []
        for r in results:
            if "set_id" not in r:
                inv.append(r)
            gained.append({"name": r.get("name"), "emoji": r.get("emoji", "📦"), "rarity": r.get("rarity", "rare"),
                           "set": r.get("set_display") if "set_id" in r else None, "sell": r.get("sell", 0)})
        await asave_player(uid, player)
    st = _state(uid, player)
    st["opened"] = {"box": box.get("name"), "items": gained}
    return web.json_response(st)


# ───────────────────────── بانک ─────────────────────────
def _bank_payload(uid, player, card):
    sv = bs.savings_summary(player)
    ln = bs.loan_status(player)
    return {
        "zen": player.get("zen", 0), "card": bs.format_card(card),
        "savings": sv["balance"], "new_interest": sv["new_interest"], "rate_pct": bs.SAVINGS_DAILY_RATE * 100,
        "loan": {"active": ln["active"], "owed": ln["principal"], "due_in": max(0, int(ln["due_at"] - time.time())) if ln["active"] else 0,
                 "credit": ln["credit_score"], "max": ln["max_loan"], "late": _plain(ln.get("late_msg")),
                 "interest_pct": int(bs.LOAN_INTEREST_RATE * 100), "penalty_pct": int(bs.LOAN_LATE_PENALTY_RATE * 100),
                 "term_h": bs.LOAN_TERM_SEC // 3600},
        "daily_left": bs.daily_remaining(player), "daily_cap": bs.DAILY_TRANSFER_CAP,
        "fee_pct": bs.TRANSFER_FEE_PCT * 100, "min_transfer": bs.MIN_TRANSFER,
        "has_pin": bs.has_pin(player), "pin_len": bs.PIN_LENGTH, "pin_locked": bs.pin_locked_remaining(player),
        "min_save": bs.MIN_SAVINGS_DEPOSIT,
        "history": [{"t": h.get("t"), "dir": h.get("dir"), "amount": h.get("amount"), "fee": h.get("fee", 0), "peer": h.get("peer", "?")}
                    for h in bs.get_history(player)],
    }


async def bank_info(request):
    uid, err = _uid(request)
    if err: return err
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        card = await bs.get_or_create_card(uid, player)
        out = _bank_payload(uid, player, card)
        await asave_player(uid, player)
    return web.json_response(out)


async def _bank_op(request, fn):
    """fn(player, body) -> {"ok","msg"}؛ بعدش وضعیت تازه‌ی بانک برمی‌گرده"""
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        res = fn(player, body)
        card = await bs.get_or_create_card(uid, player)
        await asave_player(uid, player)
        out = _bank_payload(uid, player, card)
    out.update({"ok": bool(res.get("ok")), "msg": _plain(res.get("msg"))})
    return web.json_response(out)


async def bank_savings(request):
    def op(p, b):
        amt = _int(b.get("amount"))
        if amt is None:
            return {"ok": False, "msg": "مقدار نامعتبره."}
        return bs.deposit_savings(p, amt) if b.get("action") == "deposit" else bs.withdraw_savings(p, amt)
    return await _bank_op(request, op)


async def bank_loan(request):
    def op(p, b):
        amt = _int(b.get("amount"))
        if amt is None:
            return {"ok": False, "msg": "مقدار نامعتبره."}
        return bs.borrow(p, amt) if b.get("action") == "borrow" else bs.repay(p, amt)
    return await _bank_op(request, op)


async def bank_pin(request):
    def op(p, b):
        act, pin, old = b.get("action"), str(b.get("pin") or ""), str(b.get("old") or "")
        if bs.has_pin(p) and not bs.check_pin(p, old):   # برای تغییر/حذف، PIN فعلی لازمه
            left = bs.pin_locked_remaining(p)
            return {"ok": False, "msg": f"PIN فعلی اشتباهه." if not left else f"حساب قفله؛ {left // 60 + 1} دقیقه‌ی دیگه امتحان کن."}
        if act == "clear":
            if not bs.has_pin(p):
                return {"ok": False, "msg": "PIN از قبل غیرفعاله."}
            bs.clear_pin(p)
            return {"ok": True, "msg": "PIN غیرفعال شد."}
        if not bs.set_pin(p, pin):
            return {"ok": False, "msg": f"PIN باید دقیقاً {bs.PIN_LENGTH} رقم باشه."}
        return {"ok": True, "msg": "PIN فعال شد. از این به بعد برای انتقال بهش نیاز داری."}
    return await _bank_op(request, op)


async def bank_transfer(request):
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    to, amt = str(body.get("to") or "").strip(), _int(body.get("amount"))
    if not to or amt is None:
        return _err("گیرنده و مبلغ رو کامل وارد کن")
    res = await bs.transfer(uid, to, amt, str(body.get("pin") or "") or None)   # قفل دوطرفه رو خودش می‌گیره
    async with player_lock(uid):
        player = await _load(uid)
        card = await bs.get_or_create_card(uid, player)
        out = _bank_payload(uid, player, card)
    out.update({"ok": bool(res.get("ok")), "msg": _plain(res.get("msg"))})
    return web.json_response(out)


# ───────────────────────── گیلدها ─────────────────────────
PERK_LABEL = {"pve_dmg_pct": "دمیج بیشتر در نبرد", "rare_loot_pct": "شانس لوت نادر", "zen_gain_pct": "Zen بیشتر",
              "forge_zen_pct": "سود بیشتر ذوب", "heal_pct": "درمان بیشتر", "xp_gain_pct": "XP بیشتر"}


def _quest_brief(q):
    st = q.get("stages", [])
    return {"id": q["id"], "title": _plain(q["title"]), "type": q["type"], "n": len(st),
            "intro": _plain(next((s.get("narrative") for s in st if s["kind"] == "intro"), "")),
            "goal": _plain(next((s.get("narrative") for s in st if s["kind"] in ("kill", "gather", "zen", "level")), "")),
            "has_choice": any(s["kind"] == "choice" for s in st)}


def _active_quest(player, gid):
    gd = player["guilds"][gid]
    q = gd.get("active_quest")
    if not q:
        return None
    idx = q["stage_idx"]
    stage = q["stages"][idx]
    cur, target, ready = gs.stage_progress(player, gid)
    out = {"title": _plain(q["title"]), "type": q["type"], "idx": idx, "n": len(q["stages"]),
           "log": [_plain(s.get("narrative", "")) for s in q["stages"][:idx] if s.get("narrative")],
           "stage": {"kind": stage["kind"], "narrative": _plain(stage.get("narrative", "")), "cur": cur, "target": target,
                     "ready": bool(ready), "min_rarity": stage.get("min_rarity")}}
    if stage["kind"] == "choice":
        out["stage"]["options"] = [{"i": i, "label": _plain(o["label"])} for i, o in enumerate(stage["options"])]
    return out


async def _treasury_view(gid, player, uid):
    doc = await asyncio.to_thread(gs.get_treasury, gid)
    lvl = doc.get("infra_level", 0)
    now = time.time()
    top = await asyncio.to_thread(gs.treasury_top_contributors, gid, 3)
    names = []
    for u, amt in top:
        try:
            p = await aget_player(int(u))
            names.append({"name": (p or {}).get("name", "؟"), "amount": amt})
        except Exception:
            names.append({"name": "؟", "amount": amt})
    return {"zen": doc.get("zen", 0), "total": doc.get("total_alltime", 0),
            "mine": doc.get("contributors", {}).get(str(uid), 0), "top": names,
            "infra": lvl, "infra_max": gs.INFRA_MAX_LEVEL, "infra_bonus": lvl * gs.INFRA_BONUS_PCT_PER_LEVEL,
            "infra_cost": gs.infra_cost(lvl + 1) if lvl < gs.INFRA_MAX_LEVEL else None,
            "infra_names": gs.INFRA_LEVEL_NAMES,
            "rally_left": max(0, int(doc.get("rally_until", 0) - now)), "rally_cd": max(0, int(doc.get("rally_cooldown_until", 0) - now)),
            "rally_cost": gs.RALLY_COST, "rally_bonus": gs.RALLY_BONUS_PCT, "rally_hours": gs.RALLY_DURATION_SEC // 3600}


async def guilds_overview(request):
    uid, player, err = await _auth(request)
    if err: return err
    gs.ensure_guild_data(player)
    war = await asyncio.to_thread(gs.get_war_state)
    scores = war.get("scores", {})
    remain = int(gs.WAR_DURATION_SEC - (time.time() - war.get("week_start", time.time())))
    out = []
    for gid, g in gs.GUILDS.items():
        gd = player["guilds"].get(gid)
        out.append({"id": gid, "name": g["name"], "emoji": g["emoji"], "desc": g["desc"], "npc": g["npc"],
                    "member": bool(gd), "rank": gd.get("rank") if gd else None,
                    "rank_fa": gs.RANK_NAMES_FA.get(gd.get("rank")) if gd else None,
                    "contribution": gd.get("contribution", 0) if gd else 0,
                    "quest": bool(gd and gd.get("active_quest")),
                    "war_score": scores.get(gid, 0),
                    "perk": PERK_LABEL.get(gs.PERK_STAT.get(gid), "")})
    last = war.get("last_winner")
    return web.json_response({
        "guilds": out, "war": {"remain": max(0, remain), "last_winner": last,
                               "last_winner_name": gs.GUILDS[last]["name"] if last in gs.GUILDS else None,
                               "buff_pct": int(gs.WAR_WINNER_XP_BUFF * 100)},
        "ranks": gs.RANKS, "rank_names": gs.RANK_NAMES_FA,
    })


async def guild_detail(request):
    uid, player, err = await _auth(request)
    if err: return err
    gid = request.match_info["gid"]
    if gid not in gs.GUILDS:
        return _err("گیلد نامعتبر")
    gs.ensure_guild_data(player)
    g = gs.GUILDS[gid]
    gd = player["guilds"].get(gid)
    out = {"id": gid, "name": g["name"], "emoji": g["emoji"], "desc": g["desc"], "npc": g["npc"], "s_title": g["s_title"],
           "action": {"name": g["action"]["name"], "desc": g["action"]["desc"], "cooldown": g["action"]["cooldown"]},
           "member": bool(gd), "zen": player.get("zen", 0), "perk_label": PERK_LABEL.get(gs.PERK_STAT.get(gid), "")}
    if not gd:
        return web.json_response(out)

    rank = gd.get("rank", "G")
    nxt = gs.trial_next_rank(gd)
    prev_need = gs.RANK_UP_CONTRIB[rank]
    need = gs.RANK_UP_CONTRIB[nxt] if nxt else None
    contrib = gd.get("contribution", 0)
    ready, reason = gs.trial_ready(player, gid)
    trial = {"ready": ready, "reason": reason}
    if nxt:
        pv = gs.trial_preview(player, gid)
        trial.update({"next": nxt, "chance": pv["chance"], "narrative": pv["narrative"]})
    a_ready, a_remain = gs.action_ready(player, gid)
    offers = player.get("_guild_quest_offers", {}).get(gid, {})
    out.update({
        "rank": rank, "rank_fa": gs.RANK_NAMES_FA[rank], "next_rank": nxt, "next_fa": gs.RANK_NAMES_FA.get(nxt) if nxt else None,
        "contribution": contrib, "need": need, "prev_need": prev_need,
        "pct": (min(1.0, max(0.0, (contrib - prev_need) / (need - prev_need))) if need else 1.0),
        "quests_done": gd.get("quests_done", 0), "bonus_pct": gs.get_guild_bonus_pct(player, gid),
        "perk_pct": round(gs.get_guild_perks(player).get(gs.PERK_STAT.get(gid), 0) * 100, 1),
        "trial": trial, "action_ready": a_ready, "action_remain": a_remain,
        "quest": _active_quest(player, gid), "quest_cd": max(0, int(gd.get("quest_cooldown", 0) - time.time())),
        "offers": [_quest_brief(q) for q in offers.values()],
        "shop": [{"id": i["id"], "name": i["name"], "desc": i["desc"], "cost": i["cost"], "ok": contrib >= i["cost"]}
                 for i in gs.get_shop_items(gid)],
        "treasury": await _treasury_view(gid, player, uid),
    })
    return web.json_response(out)


async def _gop(request, op):
    """op(player, gid, body) -> (ok, msg[, extra]) ؛ ذخیره و وضعیت تازه برمی‌گرده"""
    uid, err = _uid(request)
    if err: return err
    body = await _body(request)
    gid = body.get("gid")
    if gid not in gs.GUILDS:
        return _err("گیلد نامعتبر")
    async with player_lock(uid):
        player = await _load(uid)
        if not player:
            return _err("اول تو ربات /start بزن", 404)
        player.setdefault("id", uid)
        gs.ensure_guild_data(player)
        res = await op(player, gid, body)
        ok, msg = res[0], res[1]
        extra = res[2] if len(res) > 2 else {}
        await asave_player(uid, player)
    out = _state(uid, player)
    out.update({"ok": bool(ok), "msg": _plain(msg)}); out.update(extra)
    return web.json_response(out)


async def g_join(request):
    async def op(p, gid, b): return gs.join_guild(p, gid)
    return await _gop(request, op)


async def g_leave(request):
    async def op(p, gid, b): return gs.leave_guild(p, gid)
    return await _gop(request, op)


async def g_board(request):
    async def op(p, gid, b):
        if gid not in p.get("guilds", {}):
            return False, "اول عضو گیلد شو!"
        quests = gs.offer_quests(p, gid, n=3)
        p.setdefault("_guild_quest_offers", {})[gid] = {q["id"]: q for q in quests}
        return True, "تابلو به‌روز شد", {"offers": [_quest_brief(q) for q in quests]}
    return await _gop(request, op)


async def g_accept(request):
    async def op(p, gid, b):
        quest = p.get("_guild_quest_offers", {}).get(gid, {}).get(b.get("qid"))
        if not quest:
            return False, "این پیشنهاد منقضی شده؛ تابلو رو دوباره باز کن."
        ok, msg = gs.accept_quest(p, gid, quest)
        p.get("_guild_quest_offers", {}).pop(gid, None)
        return ok, msg
    return await _gop(request, op)


async def g_advance(request):
    async def op(p, gid, b):
        ok, msg, done = gs.advance_quest(p, gid)
        return ok, msg, {"done": bool(done)}
    return await _gop(request, op)


async def g_choose(request):
    async def op(p, gid, b):
        i = _int(b.get("i"), lo=0)
        return gs.choose_option(p, gid, i) if i is not None else (False, "گزینه نامعتبره")
    return await _gop(request, op)


async def g_cancel(request):
    async def op(p, gid, b): return gs.cancel_quest(p, gid)
    return await _gop(request, op)


async def g_trial(request):
    async def op(p, gid, b): return gs.attempt_trial(p, gid)
    return await _gop(request, op)


async def g_action(request):
    async def op(p, gid, b): return gs.do_guild_action(p, gid)
    return await _gop(request, op)


async def g_shop(request):
    async def op(p, gid, b): return gs.buy_shop_item(p, gid, str(b.get("item")))
    return await _gop(request, op)


async def g_treasury(request):
    async def op(p, gid, b):
        amt = _int(b.get("amount"))
        if amt is None:
            return False, "مقدار نامعتبره."
        return await asyncio.to_thread(gs.contribute_treasury, p, gid, amt)
    return await _gop(request, op)


async def g_infra(request):
    async def op(p, gid, b): return await asyncio.to_thread(gs.buy_infra_upgrade, p, gid)
    return await _gop(request, op)


async def g_rally(request):
    async def op(p, gid, b):
        if gid not in p.get("guilds", {}):
            return False, "اول باید عضو این گیلد بشی."
        return await asyncio.to_thread(gs.start_rally, gid)
    return await _gop(request, op)


# ───────────────────────── صفحه‌ی اصلی ─────────────────────────
async def index(request):
    f = _find_index()
    if not f:
        return web.Response(text="index.html پیدا نشد؛ فایل رو کنار miniapp_api.py آپلود کن", status=404)
    return web.FileResponse(f, headers={"Cache-Control": "no-store"})


async def ping(request):
    return web.json_response({"ok": True, "index": bool(_find_index()), "token": bool(BOT_TOKEN)})


def register_miniapp(app: web.Application):
    r = app.router
    r.add_get("/app", index); r.add_get("/app/", index); r.add_get("/app/ping", ping)
    r.add_get("/api/realms", realms); r.add_get("/api/me", me)
    r.add_post("/api/travel", travel); r.add_post("/api/loot", loot); r.add_post("/api/sell", sell)
    # اکتشاف و داستان
    r.add_get("/api/map", map_info); r.add_post("/api/explore", explore)
    r.add_post("/api/building/continue", building_continue); r.add_post("/api/building/leave", building_leave)
    # بازار سیاه
    r.add_get("/api/bm", bm_info); r.add_post("/api/bm/buy", bm_buy); r.add_post("/api/bm/sell", bm_sell)
    r.add_post("/api/bm/key", bm_key); r.add_post("/api/bm/ward", bm_ward); r.add_post("/api/bm/open", bm_open)
    # بانک
    r.add_get("/api/bank", bank_info); r.add_post("/api/bank/savings", bank_savings)
    r.add_post("/api/bank/loan", bank_loan); r.add_post("/api/bank/pin", bank_pin)
    r.add_post("/api/bank/transfer", bank_transfer)
    # گیلد
    r.add_get("/api/guilds", guilds_overview); r.add_get("/api/guild/{gid}", guild_detail)
    for name, fn in (("join", g_join), ("leave", g_leave), ("board", g_board), ("accept", g_accept),
                     ("advance", g_advance), ("choose", g_choose), ("cancel", g_cancel), ("trial", g_trial),
                     ("action", g_action), ("shop", g_shop), ("treasury", g_treasury), ("infra", g_infra),
                     ("rally", g_rally)):
        r.add_post(f"/api/guild/{name}", fn)
