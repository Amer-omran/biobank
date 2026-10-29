"""الإعدادات العامة للمشروع: المسارات والعتبات وأسماء التصنيفات.

كل القيم هنا قابلة للتعديل. يمكن تغيير مسار قاعدة البيانات عبر متغير البيئة
SRA_DB_PATH دون تعديل الكود.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------- المسارات
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
FONTS_DIR = BASE_DIR / "assets" / "fonts"

DB_PATH = Path(os.environ.get("SRA_DB_PATH", DATA_DIR / "restaurant_analytics.db"))
DISHES_CSV = DATA_DIR / "dishes_dictionary.csv"
SKLEARN_MODEL_PATH = MODELS_DIR / "sklearn_sentiment.joblib"
SKLEARN_META_PATH = MODELS_DIR / "sklearn_sentiment_meta.json"

ARABIC_FONT_REGULAR = FONTS_DIR / "Amiri-Regular.ttf"
ARABIC_FONT_BOLD = FONTS_DIR / "Amiri-Bold.ttf"

# ------------------------------------------------------------ التصنيفات
SENTIMENTS = ("positive", "negative", "neutral")
SENTIMENT_AR = {"positive": "إيجابي", "negative": "سلبي", "neutral": "محايد"}
# المشاعر قطبية (إيجابي ↔ سلبي) لذلك نستخدم زوجًا متباعدًا أزرق/أحمر مع رمادي محايد في المنتصف.
# هذا الزوج يبقى مميزًا لمن لديهم عمى ألوان، بخلاف الأخضر/الأحمر.
SENTIMENT_COLORS = {"positive": "#2a78d6", "negative": "#e34948", "neutral": "#a3a29b"}

ASPECTS = ("food_quality", "price", "quantity", "service", "delivery", "cleanliness", "ambiance")
ASPECT_AR = {
    "food_quality": "جودة الطعام والطعم",
    "price": "السعر والقيمة",
    "quantity": "الكمية وحجم الوجبة",
    "service": "الخدمة",
    "delivery": "التوصيل",
    "cleanliness": "النظافة",
    "ambiance": "الأجواء والمكان",
}

# ---------------------------------------------------------------- العتبات
# أقل درجة ثقة لاعتبار النتيجة مؤكدة؛ ما دونها يظهر «غير مؤكد».
CONFIDENCE_THRESHOLD = 0.6
# أقل عدد تعليقات لإدخال مطعم أو مدينة في أي ترتيب أو مقارنة نسب.
MIN_REVIEWS_FOR_RANKING = 20

# --------------------------------------------------------- إصدارات النماذج
LEXICON_MODEL_NAME = "lexicon"
LEXICON_MODEL_VERSION = "lexicon-absa-v1.3"

# نموذج Transformers المقترح (اختياري). يجب مراجعة بطاقة النموذج قبل الاعتماد عليه؛
# انظر README قسم «نموذج Hugging Face».
DEFAULT_TRANSFORMER_MODEL = os.environ.get(
    "SRA_TRANSFORMER_MODEL", "CAMeL-Lab/bert-base-arabic-camelbert-da-sentiment"
)

# متغير البيئة الخاص بمفتاح X API (لا يُكتب أي مفتاح داخل الكود).
X_BEARER_TOKEN_ENV = "X_BEARER_TOKEN"
