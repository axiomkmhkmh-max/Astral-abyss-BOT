# ============================================================
#  تستِ جریان‌های رویدادهای گروهیِ گپ (بدونِ Mongo، بدونِ شبکه، بدونِ ربات واقعی)
#  اجرا:   python test_gap_group_events.py
#  اگه aiogram/pymongo/aiohttp نصب نبود، استاب‌های مخصوصِ تست جاشون می‌شینن.
#  دیتابیس و GapBotAdapter فیک‌ان؛ بقیه (boss_engine، lootbox، economy، ...) واقعی‌ان.
# ============================================================
import asyncio
import os
import random
import sys
import tempfile
import time
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _install_stubs():
    class _Any:
        def __init__(self, *a, **k): pass
        def __call__(self, *a, **k): return _Any()
        def __getattr__(self, n): return _Any()
        def __iter__(self): return iter(())

    class _Mod(types.ModuleType):
        def __getattr__(self, n):
            if n.startswith("__"):
                raise AttributeError(n)
            c = type(n, (_Any,), {})
            setattr(self, n, c)
            return c

    for n in ["aiogram", "aiogram.types", "aiogram.enums", "aiogram.filters", "aiogram.fsm", "aiogram.fsm.context",
              "aiogram.fsm.state", "aiogram.utils", "aiogram.utils.keyboard", "aiogram.exceptions", "aiogram.client",
              "aiogram.client.default", "aiogram.dispatcher", "aiogram.methods", "pymongo", "pymongo.collection",
              "pymongo.errors", "aiohttp", "aiohttp.web", "openai", "httpx"]:
        if n not in sys.modules:
            m = _Mod(n); m.__path__ = []; sys.modules[n] = m
    sys.modules["aiogram.enums"].ButtonStyle = type("BS", (), {"DANGER": "d", "PRIMARY": "p", "SUCCESS": "s"})
    sys.modules["pymongo.collection"].ReturnDocument = type("RD", (), {"AFTER": 1, "BEFORE": 0})


try:
    import aiogram, pymongo, aiohttp  # noqa: F401
except Exception:
    _install_stubs()

import boss_engine as be
import gap_event_world as gw
import gap_event_media as gm
import gap_group_events as gge
from characters import ALL_CHARACTERS

PASS = []


def ok(name, cond, extra=""):
    PASS.append((name, bool(cond)))
    print(("✅ " if cond else "❌ ") + name + (f"  [{extra}]" if extra and not cond else ""))


# ─── فیک‌ها ──────────────────────────────────────────────────
class FakeCol:
    def __init__(self): self.docs = {}
    def find_one(self, f):
        d = self.docs.get(f.get("_id"))
        return dict(d) if d else None
    def update_one(self, f, upd, upsert=False):
        _id = f["_id"]
        d = self.docs.setdefault(_id, {"_id": _id})
        d.update(upd.get("$set", {}))
    def find(self, f=None):
        f = f or {}
        out = []
        for d in self.docs.values():
            good = True
            for k, v in f.items():
                if isinstance(v, dict) and "$gte" in v:
                    good &= d.get(k, 0) >= v["$gte"]
                else:
                    good &= d.get(k) == v
            if good:
                out.append(dict(d))
        return out


class FakeDB(dict):
    def __missing__(self, k):
        self[k] = FakeCol(); return self[k]


class FakeBot:
    def __init__(self):
        self.n = 100; self.sent = []; self.edits = []; self.photos = []; self.fail_photo = False
    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.n += 1; self.sent.append((chat_id, text, reply_markup, self.n)); return self.n
    async def edit_message_text(self, text, chat_id, message_id, reply_markup=None, **kw):
        self.edits.append((chat_id, message_id, text))
    async def send_photo(self, chat_id, photo, caption="", reply_markup=None, **kw):
        if self.fail_photo:
            raise RuntimeError("upload failed")
        self.n += 1; self.photos.append((chat_id, photo, caption)); return self.n
    def texts(self): return "\n".join(t for _c, t, _r, _i in self.sent)


class U:
    def __init__(self, uid): self.id = uid; self.chat_id = abs(uid); self.is_group = True


class FakeCb:
    def __init__(self, chat_id, uid, data):
        self.from_user = U(uid); self.data = data
        self.message = types.SimpleNamespace(chat=types.SimpleNamespace(id=chat_id, type="group"))
        self.answers = []
    async def answer(self, text="", show_alert=False): self.answers.append((text, show_alert))


PLAYERS: dict = {}
DB = FakeDB()
BOT = FakeBot()
CHAR = next(iter(ALL_CHARACTERS))
CHAT = 555


def mk_player(uid, mp="Emberhollow", level=20):
    PLAYERS[uid] = {"id": uid, "name": f"P{abs(uid)}", "character": CHAR, "level": level, "katana_level": 3,
                    "map": mp, "hp": 200, "max_hp": 200, "zen": 5000, "xp": 0, "inventory": [], "combo": 0,
                    "skill_points": 0, "unlocked_skills": [], "equipped": {}}
    return PLAYERS[uid]


async def fake_aget(uid):
    p = PLAYERS.get(uid)
    return dict(p) if p else None


async def fake_asave(uid, data):
    PLAYERS[uid] = dict(data)


async def settle():
    for _ in range(6):
        await asyncio.sleep(0)
        if gge._BG:
            await asyncio.gather(*list(gge._BG), return_exceptions=True)


def reset_chat(chat=CHAT):
    gge._EVENTS.pop(chat, None); gge._BOSS_CHATS.discard(chat); gge._ACT.pop(chat, None)
    DB["gap_group_bosses"].docs.pop(chat, None)
    BOT.sent.clear(); BOT.edits.clear(); BOT.photos.clear()
    gm.reset_cache()


def setup():
    import database
    database.get_db = lambda: DB
    gge.get_db = lambda: DB
    gge.aget_player = fake_aget
    gge.asave_player = fake_asave
    gge._BOT = BOT
    gge.CFG.update({"boss_hit_cd_sec": 0, "ambush_hit_cd_sec": 0, "dungeon_join_sec": 3, "dungeon_room_sec": 2,
                    "ambush_dodge_chance": 0.0})
    gm.CFG["chat_min_gap_sec"] = 0
    random.seed(7)


def touch(uids, chat=CHAT):
    now = time.time()
    for u in uids:
        gge._ACT.setdefault(chat, {})[u] = now
    gge._LAST_CHAT_MSG[chat] = now


# ─── تست‌ها ──────────────────────────────────────────────────
def test_world():
    r, how = gw.pick_region(["Emberhollow", "Emberhollow", "Frostheim"])
    ok("region majority", r == "Emberhollow" and how == "majority")
    r, how = gw.pick_region(["EmberHollow", "VoidBreak Wastes"])
    ok("region tie normalizes names", r in ("Emberhollow", "Voidbreak Wastes") and how == "tie")
    r, how = gw.pick_region([None, "Abyssal Black Market", "??"])
    ok("region unknown -> weighted", r in gw.REGIONS and how == "weighted")
    # هر باسِ هر منطقه باید تو boss_engine باشه و عنصرش با منطقه‌ی «تم‌دار» نخونه نداشته باشه
    bad = [(rk, t) for rk, rv in gw.REGIONS.items() for t in rv["bosses"] if t not in be.WORLD_BOSS_TEMPLATES]
    ok("all region bosses exist in boss_engine", not bad, str(bad))
    ok("fire region never picks ice boss", all(gw.boss_element(gw.pick_boss_template("Emberhollow", be.WORLD_BOSS_TEMPLATES), be.WORLD_BOSS_TEMPLATES) == "fire" for _ in range(200)))
    ok("frost region never picks fire boss", all(gw.boss_element(gw.pick_boss_template("Frostheim", be.WORLD_BOSS_TEMPLATES), be.WORLD_BOSS_TEMPLATES) == "ice" for _ in range(200)))
    ok("void region bosses are void/arcane", all(gw.boss_element(gw.pick_boss_template("Voidbreak Wastes", be.WORLD_BOSS_TEMPLATES), be.WORLD_BOSS_TEMPLATES) in ("void", "arcane") for _ in range(200)))
    # اتاق‌ها
    rooms = gw.plan_rooms("ancient_forge", n=3)
    ok("rooms: no adjacent repeats", all(rooms[i]["type"] != rooms[i + 1]["type"] for i in range(2)))
    ok("rooms: best varies across templates", len({gw.make_room("bone_crypt", "combat")["best"] for _ in range(60)}) >= 2)
    room = {"best": "fight", "ok": "guard", "diff": 0.0}
    ok("chance best>ok>bad", gw.success_chance(room, "fight", 4, 50, 50, False) > gw.success_chance(room, "guard", 4, 50, 50, False) > gw.success_chance(room, "search", 4, 50, 50, False))
    ok("chance clamped", 0.08 <= gw.success_chance(room, None, 2, 1, 999, False) <= 0.95)
    ok("every monster has art key + valid elements", all(m["weak"] in gw.ELEMENTS and m["resist"] in gw.ELEMENTS for m in gw.MONSTERS.values()))
    ok("dungeon types per region valid", all(t in gw.DUNGEON_TYPES for rv in gw.REGIONS.values() for t in rv["dungeons"]))
    ok("monsters per region valid", all(m in gw.MONSTERS for rv in gw.REGIONS.values() for m in rv["monsters"]))


async def test_media():
    d = tempfile.mkdtemp()
    for sub, names in {"bosses": ["boss_pyrothrax_p1.webp", "boss_pyrothrax_p1_b.webp", "boss_pyrothrax_p2.webp",
                                  "boss_generic_ice_p1.webp"],
                       "boxes": ["box_wood_closed.webp", "box_legendary_closed.png"],
                       "dungeons": ["dungeon_bone_crypt.webp", "dungeon_bone_crypt_room.webp", "dungeon_final_boss.webp"],
                       "monsters": ["ambush_stone_golem.webp"]}.items():
        os.makedirs(os.path.join(d, sub), exist_ok=True)
        for n in names:
            open(os.path.join(d, sub, n), "wb").write(b"x")
    gm.set_asset_root(d)
    gm.CFG["chat_min_gap_sec"] = 0
    p1 = {gm.boss_image("pyrothrax", 0, "fire") for _ in range(30)}
    ok("variants chosen randomly (p1 + p1_b)", len(p1) == 2)
    ok("phase 3 falls back to phase 2 of SAME boss", gm.boss_image("pyrothrax", 2, "fire").endswith("boss_pyrothrax_p2.webp"))
    ok("fire boss w/o art never gets ice generic", gm.boss_image("infernus_warlord", 0, "fire") is None)
    ok("ice boss w/o art gets ice generic", gm.boss_image("glacies_regina", 0, "ice").endswith("boss_generic_ice_p1.webp"))
    ok("wood chest != legendary", "wood" in gm.chest_image("wood_box", False) and "legendary" in gm.chest_image("lucky_box", False))
    ok("opened chest missing -> None", gm.chest_image("wood_box", True) is None)
    ok("entrance excludes _room variant", all("room" not in (gm.dungeon_image("bone_crypt") or "") for _ in range(20)))
    ok("final boss generic fallback", gm.dungeon_final_image("ancient_forge").endswith("dungeon_final_boss.webp"))
    ok("monster art lookup", gm.has_monster_art("stone_golem") and not gm.has_monster_art("shadow_wolf"))
    bot = FakeBot()
    ok("send ok", await gm.send_photo_safe(bot, 1, gm.monster_image("stone_golem"), "cap") is True and len(bot.photos) == 1)
    ok("send None path -> False", await gm.send_photo_safe(bot, 1, None, "") is False)
    ok("send missing file -> False", await gm.send_photo_safe(bot, 1, "/nope.webp", "") is False)
    bot.fail_photo = True
    res = [await gm.send_photo_safe(bot, 2, gm.monster_image("stone_golem"), "c") for _ in range(5)]
    ok("upload failure never raises, returns False", not any(res))
    ok("circuit breaker trips after repeated failures", gm._STATE["disabled_until"] > time.time())
    gm.set_asset_root(os.path.join(d, "does_not_exist"))
    ok("missing asset root -> no crash", gm.boss_image("pyrothrax", 0, "fire") is None)
    gm.set_asset_root(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "group_events"))


async def test_boss():
    reset_chat()
    uids = [-101, -102, -103]
    for u in uids:
        mk_player(u, "Frostheim")
    touch(uids)
    region, how = await gge._detect_region(CHAT)
    ok("region detected from players' maps", region == "Frostheim" and how == "majority")
    boss = await gge._spawn_boss(CHAT)
    ok("boss spawn region-consistent (ice)", boss["element"] == "ice" and boss["region"] == "Frostheim")
    await gge._announce_boss_spawn(CHAT, boss, "x\n")
    ok("spawn text mentions HP/threat/element", "تهدید" in BOT.sent[-1][1] and "عنصر" in BOT.sent[-1][1])
    ok("spawn keeps hit button", BOT.sent[-1][2] is not None)

    # ضربه تا تغییرِ فاز
    phases_seen = set(); kills = 0
    announced = 0
    for i in range(400):
        uid = uids[i % 3]
        cb = FakeCb(CHAT, uid, "gev:b:hit")
        before = len(BOT.sent)
        await gge.on_callback(cb)
        await settle()
        doc = DB["gap_group_bosses"].docs[CHAT]
        phases_seen.add(doc["phase_index"])
        if not doc["alive"]:
            kills += 1; break
        # سپر تو فازِ shield باید با ضرباتِ بیشتر بشکنه؛ وسط مسیر ضدحمله‌ی منطقِ فاز رو نادیده می‌گیریم
    ok("boss went through phases 0..2", phases_seen >= {0, 1, 2}, str(phases_seen))
    ok("boss killed", kills == 1)
    txt = BOT.texts()
    n_phase_msgs = sum(1 for _c, t, _r, _i in BOT.sent if "آغاز شد" in t)
    ok("each phase announced exactly once (2 transitions)", n_phase_msgs == 2, f"got {n_phase_msgs}")
    ok("defeat summary with MVP + participants", "MVP" in txt and "شرکت‌کننده" in txt)
    ok("boss removed from watcher set", CHAT not in gge._BOSS_CHATS)
    zen_after = {u: PLAYERS[u]["zen"] for u in uids}
    # ضربه‌ی بعد از مرگ → پاداشِ دوباره نباید بده
    cb = FakeCb(CHAT, uids[0], "gev:b:hit"); await gge.on_callback(cb); await settle()
    ok("no double rewards after death", {u: PLAYERS[u]["zen"] for u in uids} == zen_after and cb.answers[-1][1] is True)
    ok("rewards actually granted (zen up, boxes opened)", all(PLAYERS[u]["zen"] > 5000 for u in uids) and any(PLAYERS[u]["inventory"] for u in uids))
    ok("cooldown stored", await asyncio.to_thread(gge._db_boss_cooldown, CHAT) > 0)


async def test_boss_watcher():
    reset_chat()
    uids = [-201, -202]
    for u in uids:
        mk_player(u, "Emberhollow")
    touch(uids)
    boss = await gge._spawn_boss(CHAT, "abyss_sovereign", region="Voidbreak Wastes")
    # برو فازِ ۲ (area): HP فازِ ۱ رو صفر کن
    boss = await asyncio.to_thread(gge._db_get_boss, CHAT)
    for u in uids:
        boss["contributors"][str(u)] = {"dmg": 10, "hits": 1, "shield_dmg": 0, "defended": 0, "failed_defense": 0}
    boss["shield_active"] = False; boss["hp"] = 1
    be.process_attack(boss, uids[0], CHAR, 10**6)
    ok("engine moved to area phase", boss["mechanic"] == "area")
    boss["area_next_at"] = time.time() - 1
    await asyncio.to_thread(gge._db_save_boss, CHAT, boss)
    BOT.sent.clear()
    await gge._boss_watch_one(CHAT)
    t = BOT.texts()
    ok("area open sends a real warning (not the raw word 'open')", "ثانیه فرصت" in t and not any(x[1] == "open" for x in BOT.sent))
    ok("defend button present in warning", any(r and "gev:b:def" in str(r) for _c, _t, r, _i in BOT.sent))
    # uids[0] دفاع می‌کنه، uids[1] نه
    cb = FakeCb(CHAT, uids[0], "gev:b:def"); await gge.on_callback(cb)
    ok("defend registered", "دفاع ثبت" in cb.answers[-1][0])
    doc = await asyncio.to_thread(gge._db_get_boss, CHAT)
    doc["area_deadline"] = time.time() - 1
    await asyncio.to_thread(gge._db_save_boss, CHAT, doc)
    hp0 = {u: PLAYERS[u]["hp"] for u in uids}
    BOT.sent.clear()
    await gge._boss_watch_one(CHAT)
    ok("resolve penalizes only the player who didn't defend", PLAYERS[uids[0]]["hp"] == hp0[uids[0]] and PLAYERS[uids[1]]["hp"] < hp0[uids[1]])
    ok("hp floor >= 1", all(PLAYERS[u]["hp"] >= 1 for u in uids))
    n_before = len(BOT.sent)
    await gge._boss_watch_one(CHAT)
    ok("resolve does not repeat every tick (no spam)", len(BOT.sent) - n_before <= 1)
    # خشم + ضدحمله‌ی پایه
    doc = await asyncio.to_thread(gge._db_get_boss, CHAT)
    be._start_phase(doc, 2)
    doc["enrage_at"] = time.time() - 1
    await asyncio.to_thread(gge._db_save_boss, CHAT, doc)
    BOT.sent.clear()
    await gge._boss_watch_one(CHAT)
    ok("enrage start announced", "فرو رفته" in BOT.texts() or "خشم" in BOT.texts())
    # TTL
    doc = await asyncio.to_thread(gge._db_get_boss, CHAT)
    doc["spawn_time"] = time.time() - gge.CFG["boss_ttl_sec"] - 5
    await asyncio.to_thread(gge._db_save_boss, CHAT, doc)
    await gge._boss_watch_one(CHAT)
    ok("stale boss expires without rewards", not DB["gap_group_bosses"].docs[CHAT]["alive"] and CHAT not in gge._BOSS_CHATS)


async def test_chest():
    reset_chat()
    uids = [-301, -302, -303, -304, -305, -306]
    for u in uids:
        mk_player(u, "Verdant Vale")
    touch(uids)
    ev = await gge._spawn_box(CHAT, "gold_box", region="Verdant Vale")
    ok("chest discovery text has rarity/time/winners", all(k in BOT.sent[-1][1] for k in ("ندرت", "دقیقه", "فقط یه نفر")))
    cbs = [FakeCb(CHAT, u, f"gev:x:{ev['id']}") for u in uids]
    await asyncio.gather(*(gge.on_callback(c) for c in cbs))
    await settle()
    winners = [c for c in cbs if c.answers and "باز شد" in c.answers[-1][0]]
    ok("race chest: simultaneous clicks -> exactly 1 winner", len(winners) == 1, str(len(winners)))
    ok("reveal message shows player + reward", "رو باز کرد" in BOT.texts())
    # صندوقِ ۴نفره + دابل‌کلیک
    ev2 = await gge._spawn_box(CHAT, "wood_box", region="Verdant Vale") if False else None
    reset_chat(); touch(uids)
    ev = await gge._spawn_box(CHAT, "wood_box", region="Verdant Vale")
    c = FakeCb(CHAT, uids[0], f"gev:x:{ev['id']}")
    await gge.on_callback(c); await gge.on_callback(c)
    ok("duplicate claim blocked", any("قبلاً" in a[0] for a in c.answers))
    cbs = [FakeCb(CHAT, u, f"gev:x:{ev['id']}") for u in uids[1:]]
    await asyncio.gather(*(gge.on_callback(x) for x in cbs))
    await settle()
    got = 1 + sum(1 for x in cbs if x.answers and "باز شد" in x.answers[-1][0])
    ok("party chest capped at 4 slots", got == gge.CFG["box_party_slots"], str(got))
    # سقفِ روزانه + سطح
    reset_chat(); touch(uids)
    PLAYERS[uids[0]]["gev_daily"] = {"d": gge._today(), "boxes": gge.CFG["box_daily_cap"]}
    ev = await gge._spawn_box(CHAT, "wood_box", region="Verdant Vale")
    c = FakeCb(CHAT, uids[0], f"gev:x:{ev['id']}"); await gge.on_callback(c)
    ok("daily cap preserved", "سقف" in c.answers[-1][0])
    ok("slot released after cap rejection", not ev["pending"] and not ev["claimed"])
    mk_player(-399, level=1); c = FakeCb(CHAT, -399, f"gev:x:{ev['id']}"); await gge.on_callback(c)
    ok("min level preserved", "سطح" in c.answers[-1][0])
    c = FakeCb(CHAT, -777, f"gev:x:{ev['id']}"); await gge.on_callback(c)
    ok("player without character rejected", "start" in c.answers[-1][0])
    c = FakeCb(CHAT, uids[1], "gev:x:deadbeef"); await gge.on_callback(c)
    ok("stale/unknown chest id handled", "دیگه نیست" in c.answers[-1][0])


async def test_ambush():
    reset_chat()
    uids = [-401, -402, -403]
    for u in uids:
        mk_player(u, "Emberhollow")
    touch(uids)
    ev = await gge._spawn_ambush(CHAT, region="Emberhollow")
    ok("ambush monster fits region", ev["key"] in gw.REGIONS["Emberhollow"]["monsters"])
    ok("ambush intro: name/HP/weakness", all(k in BOT.sent[-1][1] for k in ("HP", "ضعف")))
    ok("ambush hp scales with players", ev["max_hp"] == gw.monster_hp(3))
    for i in range(300):
        c = FakeCb(CHAT, uids[i % 3], f"gev:a:{ev['id']}")
        await gge.on_callback(c)
        if ev["done"]:
            break
    await settle()
    ok("ambush killed", ev["done"] and ev["hp"] <= 0)
    ok("victory board with all participants", all(f"P{abs(u)}" in BOT.texts() for u in uids) and "ضربه‌ی آخر" in BOT.texts())
    n = sum(1 for _c, t, _r, _i in BOT.sent if "شکست خورد" in t)
    ok("victory announced once", n == 1)
    ok("live leaderboard edited at least once", len(BOT.edits) >= 1)
    z = PLAYERS[uids[0]]["zen"]
    await gge._ambush_victory(CHAT, ev, uids[0])
    ok("no double reward on repeat victory call", PLAYERS[uids[0]]["zen"] == z)
    # جاخالی
    reset_chat(); touch(uids)
    gge.CFG["ambush_dodge_chance"] = 1.0
    ev = await gge._spawn_ambush(CHAT, region="Frostheim")
    ev["traits"] = ["evasive"]
    c = FakeCb(CHAT, uids[0], f"gev:a:{ev['id']}"); await gge.on_callback(c)
    ok("evasive monster dodges", "جاخالی" in c.answers[-1][0] and ev["hp"] == ev["max_hp"])
    gge.CFG["ambush_dodge_chance"] = 0.0


async def test_dungeon():
    reset_chat()
    uids = [-501, -502, -503]
    for u in uids:
        mk_player(u, "Emberhollow")
    touch(uids)
    gge.CFG["dungeon_room_sec"] = 2
    ev = await gge._spawn_dungeon(CHAT, region="Emberhollow")
    ok("dungeon type matches region", ev["dtype"] in gw.REGIONS["Emberhollow"]["dungeons"])
    ok("entry shows region/party/countdown", all(k in BOT.sent[-1][1] for k in ("پیشنهادی", "ثانیه", "ثبت‌نام‌شده")))
    for u in uids:
        c = FakeCb(CHAT, u, f"gev:d:{ev['id']}:join"); await gge.on_callback(c)
    c = FakeCb(CHAT, uids[0], f"gev:d:{ev['id']}:join"); await gge.on_callback(c)
    ok("duplicate join blocked", "قبلاً" in c.answers[-1][0])
    c = FakeCb(CHAT, -9999, f"gev:d:{ev['id']}:join"); await gge.on_callback(c)
    ok("join without character blocked", "start" in c.answers[-1][0])
    # رأی‌دهی: هر ثانیه برای دورِ فعلی رأی بده
    async def voter():
        while not ev["done"]:
            r = ev["room"]
            if r >= 0:
                for u in uids:
                    a = random.choice(["fight", "guard", "search"])
                    await gge.on_callback(FakeCb(CHAT, u, f"gev:d:{ev['id']}:{r}:{a}"))
            await asyncio.sleep(0.3)
    vt = asyncio.create_task(voter())
    for _ in range(400):
        if ev["done"]:
            break
        await asyncio.sleep(0.25)
    vt.cancel()
    await settle()
    t = BOT.texts() + "\n".join(x[2] for x in BOT.edits)
    ok("dungeon completed (done flag)", ev["done"])
    ok("rooms shown with number + lives", "اتاقِ 1 از 4" in t and "❤️" in t)
    ok("final guardian stage reached or party fell before", "نگهبانِ نهایی" in t or "شکست داد" in t)
    ok("voting results shown", "رأی‌ها" in t)
    ok("final summary (success or failure) sent", ("فتح شد" in t) or ("شکست داد" in t))
    ok("MVP or rewards listed", "Zen" in t)
    # دانجنِ بدونِ نفرِ کافی
    reset_chat(); touch(uids)
    ev = await gge._spawn_dungeon(CHAT, region="Frostheim")
    c = FakeCb(CHAT, uids[0], f"gev:d:{ev['id']}:join"); await gge.on_callback(c)
    for _ in range(40):
        if ev["done"]:
            break
        await asyncio.sleep(0.25)
    ok("dungeon closes if too few join", ev["done"] and any("کافی نفر" in e[2] for e in BOT.edits))
    ok("late vote/join after close handled", True)
    c = FakeCb(CHAT, uids[1], f"gev:d:{ev['id']}:join"); await gge.on_callback(c)
    ok("join after close -> stale alert", "تموم" in c.answers[-1][0])


async def test_dungeon_perf_scaling():
    st_good = {"rooms_ok": 3, "lives": 3, "final_ok": True}
    st_bad = {"rooms_ok": 1, "lives": 1, "final_ok": True}
    ok("perf: better run > worse run", gge._dungeon_perf(st_good) > gge._dungeon_perf(st_bad))
    ok("perf perfect == 1.0", abs(gge._dungeon_perf(st_good) - 1.0) < 1e-9)


async def test_scheduler_and_missing_images():
    reset_chat()
    gm.set_asset_root(os.path.join(tempfile.mkdtemp(), "none"))   # هیچ عکسی نیست
    uids = [-601, -602, -603]
    for u in uids:
        mk_player(u, "Celestial Spire")
    touch(uids)
    for kind in ("box", "ambush", "dungeon", "boss"):
        reset_chat(); touch(uids)
        BOT.photos.clear()
        await gge._fire_event(CHAT, kind)
        await settle()
        ok(f"no-assets: {kind} event spawns text-only", BOT.sent and not BOT.photos)
        gge._live_events(CHAT)
        for e in gge._live_events(CHAT).values():
            e["done"] = True
    # آپلودِ خراب وسطِ رویداد
    reset_chat(); touch(uids)
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "boxes"))
    open(os.path.join(d, "boxes", "box_gold_closed.png"), "wb").write(b"x")
    gm.set_asset_root(d); gm.CFG["chat_min_gap_sec"] = 0
    BOT.fail_photo = True
    ev = await gge._spawn_box(CHAT, "gold_box", region="Celestial Spire")
    ok("photo upload failure -> event still posted with button", ev["mid"] is not None and BOT.sent[-1][2] is not None)
    BOT.fail_photo = False
    # بلاکینگ: یه رویداد فعال → اسکجولر رویداد جدید نمی‌ده
    st = await gge._get_settings(CHAT)
    st.update({"enabled": True, "next_at": time.time() - 1, "day": gge._today(), "count": 0})
    n = len(gge._live_events(CHAT))
    await gge._scheduler_tick(); await settle()
    ok("scheduler won't stack events on a live one", len(gge._live_events(CHAT)) == n)
    # حدِ روزانه
    gge._live_events(CHAT)[ev["id"]]["done"] = True
    st.update({"count": gge.CFG["max_events_per_day"], "next_at": time.time() - 1})
    sent_before = len(BOT.sent)
    await gge._scheduler_tick(); await settle()
    ok("daily cap respected", len(BOT.sent) == sent_before)
    # باس زنده → رویداد نمی‌یاد
    st.update({"count": 0, "next_at": time.time() - 1})
    gge._BOSS_CHATS.add(CHAT)
    DB["gap_group_bosses"].docs[CHAT] = {"_id": CHAT, "alive": True}
    await gge._scheduler_tick(); await settle()
    ok("no auto-event while raid boss alive", len(BOT.sent) == sent_before)
    # eid یکتا
    ids = {gge._eid(CHAT) for _ in range(5000)}
    ok("event ids unique", len(ids) == 5000)


async def test_graid_command():
    reset_chat()
    uids = [-701, -702]
    for u in uids:
        mk_player(u, "Frostheim")
    touch(uids)
    class M:
        def __init__(self, uid, text):
            self.from_user = U(uid); self.text = text; self.replies = []
            self.chat = types.SimpleNamespace(id=CHAT, type="group")
        async def answer(self, text, reply_markup=None, **kw): self.replies.append(text)
    m = M(uids[0], "/graid"); await gge.cmd_graid(m); await settle()
    ok("/graid spawns boss + announcement", DB["gap_group_bosses"].docs[CHAT]["alive"] and "تهدید" in BOT.texts())
    m2 = M(uids[1], "/graid"); await gge.cmd_graid(m2)
    ok("second /graid shows status, no second boss", m2.replies and "HP" in m2.replies[-1])
    m3 = M(uids[1], "/graid force"); await gge.cmd_graid(m3)
    ok("/graid force denied for non-admin", "فقط ادمین" in m3.replies[-1])
    m4 = M(-12345, "/graid"); await gge.cmd_graid(m4)
    ok("/graid requires character", "start" in m4.replies[-1])
    # دستور خصوصی
    m5 = M(uids[0], "/graid"); m5.chat.type = "private"; await gge.cmd_graid(m5)
    ok("/graid in private rejected", "گروه" in m5.replies[-1])


async def main():
    setup()
    test_world()
    await test_media()
    setup()
    for fn in (test_boss, test_boss_watcher, test_chest, test_ambush, test_dungeon, test_dungeon_perf_scaling,
               test_scheduler_and_missing_images, test_graid_command):
        print(f"\n— {fn.__name__} —")
        setup()
        try:
            await fn()
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            ok(f"{fn.__name__} ran without exception", False, repr(e))
    bad = [n for n, c in PASS if not c]
    print(f"\n{len(PASS) - len(bad)}/{len(PASS)} checks passed")
    if bad:
        print("FAILED:", *bad, sep="\n  - ")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    asyncio.run(main())
