# ============================================================
#  Astral Abyss — Mini App API (aiohttp)
#  استفاده:  from miniapp_api import register_miniapp; register_miniapp(app)
#  ENV لازم: BOT_TOKEN   |  اختیاری: MINIAPP_URL
# ============================================================
import os, time, json, hmac, hashlib, pathlib
from urllib.parse import parse_qsl
from aiohttp import web

from database import aget_player, asave_player
from economy import MAPS_DATA, MAP_LOOT, MAP_LOCATIONS, roll_loot, get_travel_time
from economy_engine import add_reputation
from economy_ledger import record_transaction
import async_bridge as bridge
from loot_handlers import get_ls, use_action, DAILY_MAX

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HERE = pathlib.Path(__file__).parent

# ۱۴ قلمرو اصلی؛ بازار سیاه و تخت فراموشی جدا (بخش «مکان‌های ویژه») نمایش داده می‌شن
EXTRA_REALMS = {"Abyssal Black Market", "Throne of Oblivion"}


def _find_index():
    # هم پوشه‌ی miniapp/ و هم کنار همین فایل (آپلود از موبایل) پشتیبانی می‌شه
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


async def _auth(request):
    user = verify_init_data(request.headers.get("X-Init-Data", ""))
    if not user:
        return None, None, _err("unauthorized", 401)
    player = await aget_player(user["id"])
    if not player:
        return None, None, _err("اول تو ربات /start بزن", 404)
    s = get_ls(user["id"])  # اگه سفر تموم شده، traveling خودش None می‌شه
    if not s.get("traveling") and s.get("dest"):
        player["map"] = s.pop("dest")
        await asave_player(user["id"], player)
    return user["id"], player, None


def _state(uid, player):
    s = get_ls(uid)
    now = time.time()
    traveling = s.get("traveling")
    # رسیدن به مقصد: مپ بازیکن لحظه‌ی رسیدن ثبت می‌شه
    return {
        "name": player.get("name") or player.get("first_name") or "",
        "level": player.get("level", 1),
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
             "sell": i.get("sell", 0), "qty": i.get("qty", 1), "desc": i.get("desc", "")}
            for i in player.get("inventory", [])
        ],
    }


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
    dest = (await request.json()).get("map")
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
    found = roll_loot(realm, 5, player.get("level", 1))
    player.setdefault("inventory", []).extend(found)
    await asave_player(uid, player)
    st = _state(uid, player)
    st["found"] = [{"name": i.get("name"), "emoji": i.get("emoji", ""), "rarity": i.get("rarity", "common")} for i in found]
    return web.json_response(st)


async def sell(request):
    """فروش آیتم‌ها؛ منطق و مالیات دقیقاً مثل cb_loot_sell_all داخل ربات.
    بدنه: {"name":..., "emoji":...} برای یک نوع آیتم، یا {"all": true} برای کل کوله"""
    uid, player, err = await _auth(request)
    if err: return err
    body = await request.json()
    inv = player.get("inventory", [])
    if body.get("all"):
        picked = list(inv)
    else:
        nm, em = body.get("name"), body.get("emoji", "")
        picked = [i for i in inv if i.get("name") == nm and i.get("emoji", "") == em]
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


async def index(request):
    f = _find_index()
    if not f:
        return web.Response(text="index.html پیدا نشد؛ فایل رو کنار miniapp_api.py آپلود کن", status=404)
    return web.FileResponse(f, headers={"Cache-Control": "no-store"})


async def ping(request):
    return web.json_response({"ok": True, "index": bool(_find_index()), "token": bool(BOT_TOKEN)})


def register_miniapp(app: web.Application):
    app.router.add_get("/app", index)
    app.router.add_get("/app/", index)
    app.router.add_get("/app/ping", ping)
    app.router.add_get("/api/realms", realms)
    app.router.add_get("/api/me", me)
    app.router.add_post("/api/travel", travel)
    app.router.add_post("/api/loot", loot)
    app.router.add_post("/api/sell", sell)
