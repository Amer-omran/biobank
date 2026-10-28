"""وحدة معالجة النصوص العربية.

المبادئ:
- النص الأصلي يُحفظ كما هو (مع إخفاء المعلومات الشخصية فقط مثل الأرقام والبريد).
- التطبيع محدود وقابل للتعديل عبر NormalizationOptions، ويُستخدم للمطابقة فقط.
- لا نحذف كلمات النفي (لا، ما، مو...) ولا الرموز التعبيرية ولا علامات التعجب،
  لأنها تحمل دلالة شعورية.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

# ------------------------------------------------------------ أنماط ثابتة
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
MENTION_RE = re.compile(r"(?<!\w)@\w+")
# أرقام الجوال السعودية (05xxxxxxxx أو +9665xxxxxxxx) وأي رقم من 9 خانات فأكثر
PHONE_RE = re.compile(r"(?:\+?966[\s-]?|\b0)5\d(?:[\s-]?\d){7}\b|\b\d{9,}\b")
WHITESPACE_RE = re.compile(r"\s+")
TASHKEEL_RE = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
# تكرار الحرف نفسه ثلاث مرات أو أكثر (مثل حلوووو)
ELONGATION_RE = re.compile(r"(.)\1{2,}")

# رموز تعبيرية شائعة (نحتفظ بها كرموز مستقلة)
EMOJI_CHARS = "😍😋👌👍❤💯😊🥰👏🤤🔥😁😃🌹✨💕😡👎🤢🤮😤😠💩😒😞😔🤬😑🙄😐🤔"
EMOJI_RE = re.compile("[" + EMOJI_CHARS + "]")
# الكلمات: حروف عربية أو لاتينية أو أرقام
TOKEN_RE = re.compile(r"[ء-ي٠-٩A-Za-z0-9]+|[" + EMOJI_CHARS + "]|[!؟?]")

# أدوات الاستدراك التي تفصل بين آراء مختلفة داخل الجملة نفسها
CONTRAST_WORDS = ("بس", "لكن", "ولكن", "لكنه", "لكنها", "الا ان", "إلا أن", "بينما", "مع ان", "مع أن", "اما", "أما")
CLAUSE_SPLIT_RE = re.compile(
    r"[.،,;؛!؟?\n]+|\s(?:" + "|".join(re.escape(w) for w in CONTRAST_WORDS) + r")\s"
)

# كلمات النفي محفوظة دائمًا (تُستخدم في الاختبارات للتأكد من عدم حذفها)
NEGATION_WORDS = ("لا", "ما", "مو", "مب", "مش", "ليس", "ليست", "لم", "لن", "غير", "بدون", "موب", "مهو")


@dataclass
class NormalizationOptions:
    """خيارات التطبيع. كلها قابلة للتعطيل لأن بعض الباحثين يفضلون نصًا أقل تعديلًا."""

    unify_alef: bool = True          # أ إ آ ٱ -> ا
    alef_maqsura_to_ya: bool = True  # ى -> ي
    ta_marbuta_to_ha: bool = True    # ة -> ه
    hamza_on_carriers: bool = True   # ؤ -> و ، ئ -> ي
    remove_tashkeel: bool = True     # حذف الحركات
    remove_tatweel: bool = True      # حذف التطويل ـ
    reduce_elongation: bool = True   # حلوووو -> حلوو
    arabic_digits: bool = True       # ٣ -> 3
    lowercase_latin: bool = True


DEFAULT_OPTIONS = NormalizationOptions()
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def is_missing(value) -> bool:
    """يتعامل مع None وNaN والنصوص الفارغة بطريقة موحدة."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        import pandas as pd

        if value is pd.NA or value is pd.NaT:
            return True
    except ImportError:  # pragma: no cover - pandas مثبتة دائمًا في المشروع
        pass
    return isinstance(value, str) and value.strip() == ""


def to_text(value) -> str:
    """يحول أي قيمة إلى نص، والقيم الفارغة إلى نص فارغ."""
    if is_missing(value):
        return ""
    return str(value)


def mask_personal_info(text: str) -> str:
    """يخفي البريد الإلكتروني وأرقام الهواتف وأسماء الحسابات (@user).

    هذه المعلومات لا تفيد تحليل المشاعر، وتخزينها يخالف مبدأ تقليل البيانات الشخصية.
    """
    text = to_text(text)
    text = EMAIL_RE.sub("[بريد]", text)
    text = MENTION_RE.sub("@مستخدم", text)
    text = PHONE_RE.sub("[رقم]", text)
    return text


def clean_text(text) -> str:
    """تنظيف خفيف: حذف الروابط والفراغات الزائدة. لا يغيّر الحروف ولا يحذف النفي."""
    text = to_text(text)
    text = URL_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_arabic(text, options: NormalizationOptions = DEFAULT_OPTIONS) -> str:
    """تطبيع محدود للحروف العربية لأغراض المطابقة والتحليل فقط."""
    text = to_text(text)
    if options.remove_tashkeel:
        text = TASHKEEL_RE.sub("", text)
    if options.remove_tatweel:
        text = text.replace(TATWEEL, "")
    if options.unify_alef:
        text = re.sub("[أإآٱ]", "ا", text)
    if options.alef_maqsura_to_ya:
        text = text.replace("ى", "ي")
    if options.ta_marbuta_to_ha:
        text = text.replace("ة", "ه")
    if options.hamza_on_carriers:
        text = text.replace("ؤ", "و").replace("ئ", "ي")
    if options.arabic_digits:
        text = text.translate(ARABIC_INDIC_DIGITS)
    if options.reduce_elongation:
        text = ELONGATION_RE.sub(r"\1\1", text)
    if options.lowercase_latin:
        text = text.lower()
    return WHITESPACE_RE.sub(" ", text).strip()


def has_elongation(token: str) -> bool:
    """هل في الكلمة الأصلية تطويل بالتكرار؟ (يدل غالبًا على مبالغة في الشعور)."""
    return bool(ELONGATION_RE.search(token))


def squeeze(token: str) -> str:
    """يدمج الحروف المتكررة المتتالية في حرف واحد: مممتاز -> متاز.

    يُستخدم كمفتاح احتياطي للمطابقة مع القاموس عند وجود تطويل.
    """
    return re.sub(r"(.)\1+", r"\1", token)


def tokenize(text: str) -> list[str]:
    """تقسيم النص إلى كلمات ورموز تعبيرية وعلامات تعجب/استفهام."""
    return TOKEN_RE.findall(to_text(text))


def split_clauses_detailed(text: str) -> list[tuple[str, bool]]:
    """تقسيم التعليق إلى مقاطع، مع بيان هل جاء المقطع بعد أداة استدراك (بس، لكن...).

    المقطع الذي يلي «بس/لكن» يحمل غالبًا الرأي الأهم عند الكاتب.
    يُعيد مقاطع النص الأصلي غير المطبع، لتُعرض كعبارة داعمة للحكم.
    """
    text = clean_text(text)
    if not text:
        return []
    padded = " " + text + " "
    clauses: list[tuple[str, bool]] = []
    position = 0
    after_contrast = False
    for match in CLAUSE_SPLIT_RE.finditer(padded):
        piece = padded[position:match.start()].strip()
        if piece:
            clauses.append((piece, after_contrast))
        separator = match.group(0).strip()
        # بعد علامة ترقيم عادية لا نُلغي أثر الاستدراك إذا لم يأتِ مقطع بعدُ
        if separator in CONTRAST_WORDS:
            after_contrast = True
        elif piece:
            after_contrast = False
        position = match.end()
    tail = padded[position:].strip()
    if tail:
        clauses.append((tail, after_contrast))
    return clauses


def split_clauses(text: str) -> list[str]:
    """مثل split_clauses_detailed لكن يُعيد نصوص المقاطع فقط."""
    return [clause for clause, _ in split_clauses_detailed(text)]


# السوابق الشائعة: حروف العطف والجر وأل التعريف (الأطول أولًا)
PREFIXES = ("وبال", "وال", "بال", "فال", "كال", "ولل", "لل", "ال", "و", "ف", "ب", "ل", "ك")
# اللواحق الشائعة: الضمائر وعلامات الجمع والتأنيث
SUFFIXES = ("هم", "ها", "كم", "نا", "ين", "ات", "ه", "ي")


def token_variants(token: str) -> list[str]:
    """صيغ مرشحة للكلمة بعد نزع السوابق واللواحق، لمطابقتها بالقواميس.

    مثال: «والخدمه» -> [والخدمه، الخدمه، خدمه، ...]. الكلمة الكاملة تأتي أولًا دائمًا
    حتى لا نخطئ في كلمات تبدأ أصلًا بحرف يشبه السابقة (مثل «بارد»).
    """
    variants = [token]
    for prefix in PREFIXES:
        rest = token[len(prefix):]
        minimum = 2 if len(prefix) > 1 else 3
        if token.startswith(prefix) and len(rest) >= minimum:
            variants.append(rest)
    with_suffixes = []
    for variant in variants:
        for suffix in SUFFIXES:
            stem = variant[: -len(suffix)]
            if variant.endswith(suffix) and len(stem) >= 3:
                with_suffixes.append(stem)
    seen: set[str] = set()
    ordered = []
    for v in variants + with_suffixes:
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def text_hash(text: str) -> str:
    """بصمة للنص بعد التطبيع، لاكتشاف التعليقات المكررة رغم اختلاف التشكيل والفراغات."""
    key = squeeze(normalize_arabic(clean_text(text)))
    key = re.sub(r"[^\w\s]", "", key)
    key = WHITESPACE_RE.sub(" ", key).strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def find_duplicates(texts) -> list[bool]:
    """يُرجع قائمة: True للتعليق المكرر (التكرار الثاني فما بعد)، False للأول."""
    seen: set[str] = set()
    flags = []
    for t in texts:
        h = text_hash(t)
        flags.append(h in seen)
        seen.add(h)
    return flags


def contains_arabic(text: str) -> bool:
    return bool(re.search(r"[ء-ي]", to_text(text)))
