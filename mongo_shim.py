# ============================================================
#  MONGO_SHIM — لایه‌ی نازکِ اتصال به MongoDB واقعی
# ------------------------------------------------------------
#  برخلافِ pg_shim.py (که کلِ رفتارِ Mongo رو دستی روی Postgres
#  شبیه‌سازی می‌کرد)، اینجا مستقیم از pymongo استفاده می‌کنیم —
#  یعنی فیلترها ($or, $gte, $in, ...) و آپدیت‌ها ($set, $inc, ...)
#  مستقیم به‌دستِ خودِ MongoDB می‌رسن، نه یه پیاده‌سازیِ دستی.
#
#  API عمومیِ این فایل (Collection, get_shim_db) دقیقاً همونیه که
#  pg_shim.py داشت، پس database.py و region_boss_system.py و
#  group_system.py و referral_system.py فقط نیازه import‌شون رو
#  از pg_shim به mongo_shim عوض کنن — هیچ‌جای دیگه‌ای لازم نیست
#  تغییر کنه.
#
#  فقط یه فرق: find() اینجا هم (مثلِ قبل) یه لیستِ کامل برمی‌گردونه
#  نه یه cursor — چون کدِ فراخوان‌ها (auction_system.py, ...) رفتارِ
#  لیست رو انتظار دارن (مثلاً .sort() پایتونی روی نتیجه می‌زنن).
# ============================================================
import os
import asyncio
import threading
from typing import Any, Optional

from pymongo import MongoClient
from pymongo.collection import ReturnDocument

MONGODB_URI = os.getenv("MONGODB_URI", "") or os.getenv("MONGO_URL", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "astral_abyss")

_client: Optional[MongoClient] = None
_client_lock = threading.Lock()


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not MONGODB_URI:
                    raise RuntimeError(
                        "MONGODB_URI تنظیم نشده — آدرسِ اتصالِ MongoDB (Atlas یا هر "
                        "میزبانِ دیگه) رو تویِ متغیرهایِ محیطی ست کن."
                    )
                _client = MongoClient(
                    MONGODB_URI,
                    maxPoolSize=int(os.getenv("MONGO_POOL_MAX", "50")),
                    minPoolSize=int(os.getenv("MONGO_POOL_MIN", "5")),
                    serverSelectionTimeoutMS=10000,
                )
                # یه پینگِ سبک برای مطمئن‌شدن از اتصال (خطا رو زودتر نشون بده،
                # نه اولین‌باری که یه هندلر واقعی صداش می‌زنه)
                _client.admin.command("ping")
    return _client


class _Result:
    """رپرِ نازک روی pymongo.results تا امضایِ .matched_count/.modified_count/
    .upserted_id/.deleted_count/.inserted_id (همونی که کدِ بقیه‌ی پروژه انتظار
    داره) حفظ بمونه، صرف‌نظر از اینکه از چه نوع نتیجه‌ای اومده."""

    def __init__(self, matched=0, modified=0, upserted_id=None, deleted=0, inserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id
        self.deleted_count = deleted
        self.inserted_id = inserted_id


class Collection:
    """جایگزینِ pg_shim.Collection — همون امضایِ متدها، ولی مستقیم delegate
    به pymongo.collection.Collection می‌کنه (بدونِ بازتولیدِ منطقِ Mongo)."""

    def __init__(self, name: str):
        self.name = name

    @property
    def _real(self):
        return _get_client()[MONGODB_DB_NAME][self.name]

    # ---- API عمومی (سینک) ----
    def find_one(self, filt: Optional[dict] = None, projection: Optional[dict] = None) -> Optional[dict]:
        return self._real.find_one(filt or {}, projection)

    def find(self, filt: Optional[dict] = None) -> list[dict]:
        return list(self._real.find(filt or {}))

    def insert_one(self, doc: dict) -> _Result:
        res = self._real.insert_one(doc)
        return _Result(inserted_id=res.inserted_id)

    def update_one(self, filt: dict, update: dict, upsert: bool = False) -> _Result:
        res = self._real.update_one(filt, update, upsert=upsert)
        return _Result(matched=res.matched_count, modified=res.modified_count, upserted_id=res.upserted_id)

    def find_one_and_update(self, filt: dict, update: dict, upsert: bool = False) -> Optional[dict]:
        return self._real.find_one_and_update(
            filt, update, upsert=upsert, return_document=ReturnDocument.AFTER
        )

    async def afind_one_and_update(self, filt: dict, update: dict, upsert: bool = False):
        return await asyncio.to_thread(self.find_one_and_update, filt, update, upsert)

    def replace_one(self, filt: dict, replacement: dict, upsert: bool = False) -> _Result:
        res = self._real.replace_one(filt, replacement, upsert=upsert)
        return _Result(matched=res.matched_count, modified=res.modified_count, upserted_id=res.upserted_id)

    def delete_one(self, filt: dict) -> _Result:
        res = self._real.delete_one(filt)
        return _Result(deleted=res.deleted_count)

    def count_documents(self, filt: Optional[dict] = None) -> int:
        return self._real.count_documents(filt or {})

    def distinct(self, field: str, filt: Optional[dict] = None) -> list:
        return self._real.distinct(field, filt or {})

    def aggregate(self, pipeline: list) -> list:
        return list(self._real.aggregate(pipeline))

    # ---- نسخه‌های async (asyncio.to_thread — همون الگویِ pg_shim.py،
    #      تا هندلرهایِ async قفل نشن) ----
    async def afind_one(self, filt: Optional[dict] = None, projection: Optional[dict] = None):
        return await asyncio.to_thread(self.find_one, filt, projection)

    async def afind(self, filt: Optional[dict] = None):
        return await asyncio.to_thread(self.find, filt)

    async def ainsert_one(self, doc: dict):
        return await asyncio.to_thread(self.insert_one, doc)

    async def aupdate_one(self, filt: dict, update: dict, upsert: bool = False):
        return await asyncio.to_thread(self.update_one, filt, update, upsert)

    async def areplace_one(self, filt: dict, replacement: dict, upsert: bool = False):
        return await asyncio.to_thread(self.replace_one, filt, replacement, upsert)

    async def adelete_one(self, filt: dict):
        return await asyncio.to_thread(self.delete_one, filt)

    async def acount_documents(self, filt: Optional[dict] = None):
        return await asyncio.to_thread(self.count_documents, filt)

    async def adistinct(self, field: str, filt: Optional[dict] = None):
        return await asyncio.to_thread(self.distinct, field, filt)

    async def aaggregate(self, pipeline: list):
        return await asyncio.to_thread(self.aggregate, pipeline)


class Database:
    def __getitem__(self, name: str) -> Collection:
        return Collection(name)


def get_shim_db() -> Database:
    _get_client()  # مطمئن شو اتصال برقراره (خطا رو همین‌جا بده، نه بعداً)
    return Database()
