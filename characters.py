# ============================================================
#  characters.py — لایه‌ی سازگاری (سیستمِ کرکتر حذف شده)
# ============================================================
#  کرکترها دیگه وجود ندارن؛ فقط کاتاناها مونده (katanas.py).
#  این فایل فقط اسم‌های قدیمی (ALL_CHARACTERS و ...) رو به کاتالوگِ
#  کاتاناها وصل می‌کنه تا ~۳۰ فایلِ دیگه که هنوز از اینجا import
#  می‌کنن بدونِ دستکاری کار کنن. «کلیدِ» هر آیتم الان اسمِ کاتاناست.
#  وقتی بقیه‌ی فایل‌ها به katanas.py منتقل شدن، می‌شه این فایل رو پاک کرد.
# ============================================================
from katanas import (
    ALL_KATANAS as ALL_CHARACTERS,          # همون آبجکت: کاتاناهای پروسیجرالِ بعدی هم اینجا دیده می‌شن
    SPECIAL_KATANAS as SPECIAL_CHARACTERS,
    MYTHIC_KATANAS as MYTHIC_CHARACTERS,
    RANDOM_KATANAS as RANDOM_CHARACTERS,
    RANDOM_KATANA_NAMES as RANDOM_CHAR_NAMES,
    SPECIAL_KATANA_NAMES as SPECIAL_CHAR_NAMES,
    MYTHIC_KATANA_NAMES as MYTHIC_CHAR_NAMES,
    RARITY_EMOJI,
)

# --- Astraelion | Special (بدونِ تغییر) ---
ASTRAELION = {
    "name": "Astraelion",
    "rarity": "Special",
    "element": "هاله آسمانی",
    "base_damage": 19,
}
