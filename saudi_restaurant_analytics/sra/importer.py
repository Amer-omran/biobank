"""استيراد ملفات CSV وExcel بمرونة: لا نفترض أسماء الأعمدة.

الخطوات:
1. read_table: قراءة الملف (مع تجربة عدة ترميزات للملفات العربية).
2. suggest_mapping: اقتراح الأعمدة المناسبة (يؤكدها المستخدم أو يغيّرها).
3. prepare_dataframe: التحقق والتنظيف وكشف التكرار، مع تقرير مفصل بالأخطاء.
4. database.insert_reviews: الحفظ في قاعدة البيانات.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .text_processing import (
    clean_text,
    contains_arabic,
    is_missing,
    mask_personal_info,
    normalize_arabic,
    text_hash,
)

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1256", "windows-1256", "iso-8859-6")
# parquet وjson/jsonl هي الصيغ التي تُنشر بها مجموعات Hugging Face غالبًا
SUPPORTED_EXTENSIONS = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".parquet", ".json", ".jsonl")

# كلمات تساعد على اقتراح الأعمدة (مطبعة، والمقارنة بالاحتواء)
COLUMN_HINTS = {
    "text": ["review", "comment", "text", "content", "tweet", "sentence", "body", "تعليق", "مراجعه",
             "مراجعة", "نص", "راي", "رأي", "تغريده"],
    "restaurant": ["restaurant", "place", "store", "branch", "business", "مطعم", "المطعم", "فرع", "محل"],
    "date": ["date", "time", "created", "تاريخ", "وقت"],
    "rating": ["rating", "stars", "star", "score", "rate", "تقييم", "نجوم", "درجه"],
    "city": ["city", "town", "location", "مدينه", "مدينة", "المدينه"],
    "label": ["label", "sentiment", "polarity", "class", "شعور", "تصنيف", "مشاعر"],
    "source": ["source", "platform", "مصدر", "منصه"],
}

# توحيد أسماء المدن السعودية المعروفة. المدن غير المعروفة تُحفظ كما هي.
KNOWN_CITIES = {
    "الرياض": ["الرياض", "رياض", "riyadh", "ar riyadh"],
    "جدة": ["جدة", "جده", "jeddah", "jedda"],
    "مكة المكرمة": ["مكة", "مكه", "مكة المكرمة", "مكه المكرمه", "makkah", "mecca"],
    "المدينة المنورة": ["المدينة", "المدينه", "المدينة المنورة", "المدينه المنوره", "madinah", "medina"],
    "الدمام": ["الدمام", "دمام", "dammam"],
    "الخبر": ["الخبر", "خبر", "khobar", "al khobar"],
    "الطائف": ["الطائف", "طائف", "taif"],
    "أبها": ["ابها", "أبها", "abha"],
    "تبوك": ["تبوك", "tabuk"],
    "بريدة": ["بريدة", "بريده", "buraydah"],
    "حائل": ["حائل", "حايل", "hail", "ha'il"],
    "جازان": ["جازان", "جيزان", "jazan", "jizan"],
    "نجران": ["نجران", "najran"],
    "الأحساء": ["الاحساء", "الأحساء", "الحسا", "ahsa", "al ahsa", "hofuf"],
    "ينبع": ["ينبع", "yanbu"],
}
_CITY_INDEX = {normalize_arabic(v): k for k, vs in KNOWN_CITIES.items() for v in vs}

LABEL_ALIASES = {
    "positive": ["positive", "pos", "p", "1", "+1", "إيجابي", "ايجابي", "موجب"],
    "negative": ["negative", "neg", "n", "-1", "سلبي", "سالب"],
    "neutral": ["neutral", "neu", "0", "محايد", "حيادي", "objective"],
}
_LABEL_INDEX = {normalize_arabic(v): k for k, vs in LABEL_ALIASES.items() for v in vs}


@dataclass
class ColumnMapping:
    """أسماء الأعمدة في ملف المستخدم. text إلزامي، والباقي اختياري (None)."""

    text: str
    restaurant: str | None = None
    date: str | None = None
    rating: str | None = None
    city: str | None = None
    label: str | None = None
    source: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class ImportReport:
    data: pd.DataFrame
    total_rows: int
    empty_text_rows: int = 0
    duplicate_rows: int = 0
    invalid_dates: int = 0
    invalid_ratings: int = 0
    unknown_labels: int = 0
    unrecognized_cities: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid_rows(self) -> int:
        return len(self.data)

    @property
    def ok(self) -> bool:
        return not self.errors and self.valid_rows > 0


# ============================================================== القراءة
def read_table(source, filename: str | None = None, sheet_name=0) -> pd.DataFrame:
    """يقرأ CSV أو Excel من مسار أو من ملف مرفوع (كائن يحتوي read()).

    يجرب عدة ترميزات لملفات CSV لأن الملفات العربية المحفوظة من Excel تكون غالبًا cp1256.
    """
    name = filename or (str(source) if isinstance(source, (str, Path)) else getattr(source, "name", ""))
    ext = Path(name).suffix.lower()
    if ext and ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"نوع الملف غير مدعوم: {ext}. الأنواع المدعومة: {', '.join(SUPPORTED_EXTENSIONS)}")
    raw = Path(source).read_bytes() if isinstance(source, (str, Path)) else source.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw:
        raise ValueError("الملف فارغ.")

    if ext in (".xlsx", ".xlsm", ".xls"):
        try:
            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name)
        except Exception as exc:  # noqa: BLE001 - نعرض سبب الخطأ للمستخدم بالعربية
            raise ValueError(f"تعذر قراءة ملف Excel: {exc}") from exc
    elif ext == ".parquet":
        try:
            df = pd.read_parquet(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"تعذر قراءة ملف Parquet: {exc}") from exc
    elif ext in (".json", ".jsonl"):
        text = raw.decode("utf-8-sig")
        try:
            # jsonl: سجل JSON في كل سطر؛ json: قائمة سجلات
            lines = ext == ".jsonl" or not text.lstrip().startswith("[")
            df = pd.read_json(io.StringIO(text), lines=lines, dtype=False)
        except ValueError as exc:
            raise ValueError(f"تعذر قراءة ملف JSON: {exc}") from exc
    else:
        df = None
        last_error = None
        for enc in CSV_ENCODINGS:
            try:
                text = raw.decode(enc)
            except UnicodeDecodeError as exc:
                last_error = exc
                continue
            try:
                df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str,
                                 keep_default_na=True)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if df is None:
            raise ValueError(f"تعذر قراءة ملف CSV بأي ترميز معروف: {last_error}")

    df.columns = [str(c).strip() for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("يحتوي الملف على أعمدة بأسماء مكررة؛ أعد تسميتها ثم ارفعه مجددًا.")
    return stringify_nested(df)


def excel_sheet_names(source) -> list[str]:
    raw = Path(source).read_bytes() if isinstance(source, (str, Path)) else source.getvalue()
    return list(pd.ExcelFile(io.BytesIO(raw)).sheet_names)


def stringify_nested(df: pd.DataFrame) -> pd.DataFrame:
    """الأعمدة التي تحتوي قوائم أو قواميس (شائعة في بيانات Hugging Face) تُحول إلى JSON نصي."""
    df = df.copy()
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict, tuple, np.ndarray))).any():
            df[col] = df[col].map(
                lambda v: json.dumps(v.tolist() if isinstance(v, np.ndarray) else v, ensure_ascii=False)
                if isinstance(v, (list, dict, tuple, np.ndarray)) else v
            )
    return df


# ======================================================== اقتراح الأعمدة
def suggest_mapping(df: pd.DataFrame) -> dict[str, str | None]:
    """اقتراح أولي للأعمدة اعتمادًا على الأسماء والمحتوى. ليس قرارًا نهائيًا."""
    suggestion: dict[str, str | None] = {k: None for k in COLUMN_HINTS}
    used: set[str] = set()
    for role, hints in COLUMN_HINTS.items():
        for col in df.columns:
            if col in used:
                continue
            col_norm = normalize_arabic(col)
            if any(normalize_arabic(h) in col_norm for h in hints):
                suggestion[role] = col
                used.add(col)
                break
    if suggestion["text"] is None:
        # العمود النصي الأطول متوسطًا والذي يحتوي حروفًا عربية
        best, best_len = None, 0.0
        for col in df.columns:
            if col in used:
                continue
            values = df[col].dropna().astype(str).head(200)
            if values.empty or not values.map(contains_arabic).mean() > 0.5:
                continue
            mean_len = values.str.len().mean()
            if mean_len > best_len:
                best, best_len = col, mean_len
        suggestion["text"] = best
    return suggestion


# ========================================================= تحويل القيم
def parse_date(value) -> str | None:
    if is_missing(value):
        return None
    ts = pd.to_datetime(str(value).strip(), errors="coerce", dayfirst=False)
    if pd.isna(ts):
        ts = pd.to_datetime(str(value).strip(), errors="coerce", dayfirst=True)
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def parse_rating(value, max_rating: float = 10.0) -> float | None:
    if is_missing(value):
        return None
    try:
        number = float(str(value).strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")))
    except ValueError:
        return None
    if np.isnan(number) or number < 0 or number > max_rating:
        return None
    return number


def normalize_label(value) -> str | None:
    if is_missing(value):
        return None
    return _LABEL_INDEX.get(normalize_arabic(str(value).strip()))


def normalize_city(value) -> tuple[str | None, bool]:
    """يُرجع (اسم المدينة، هل هي مدينة معروفة)."""
    if is_missing(value):
        return None, False
    raw = str(value).strip()
    canonical = _CITY_INDEX.get(normalize_arabic(raw))
    return (canonical, True) if canonical else (raw, False)


# =============================================================== التحضير
def prepare_dataframe(df: pd.DataFrame, mapping: ColumnMapping, dedupe: bool = True,
                      default_source: str | None = None, min_text_length: int = 2) -> ImportReport:
    """يتحقق من البيانات وينظفها ويُرجع تقريرًا. لا يكتب شيئًا في قاعدة البيانات."""
    report = ImportReport(data=pd.DataFrame(), total_rows=len(df))
    for role, col in mapping.as_dict().items():
        if col not in df.columns:
            report.errors.append(f"العمود «{col}» المحدد لـ {role} غير موجود في الملف.")
    if report.errors:
        return report

    original = df[mapping.text].map(lambda v: "" if is_missing(v) else str(v))
    texts = original.map(mask_personal_info).map(lambda t: t.strip())
    clean = texts.map(clean_text)
    empty_mask = clean.str.len() < min_text_length
    report.empty_text_rows = int(empty_mask.sum())
    # بقية الفحوص تُحسب على الصفوف التي تحتوي تعليقًا فقط
    df = df[~empty_mask]
    out = pd.DataFrame({"text": texts[~empty_mask], "clean_text": clean[~empty_mask]}, index=df.index)

    out["restaurant_name"] = (df[mapping.restaurant].map(lambda v: None if is_missing(v) else str(v).strip())
                              if mapping.restaurant else None)
    if mapping.date:
        out["review_date"] = df[mapping.date].map(parse_date)
        report.invalid_dates = int((out["review_date"].isna() & ~df[mapping.date].map(is_missing)).sum())
    else:
        out["review_date"] = None
    if mapping.rating:
        out["original_rating"] = df[mapping.rating].map(parse_rating)
        report.invalid_ratings = int((out["original_rating"].isna() & ~df[mapping.rating].map(is_missing)).sum())
    else:
        out["original_rating"] = None
    if mapping.city:
        cities = df[mapping.city].map(normalize_city)
        out["city"] = cities.map(lambda c: c[0])
        report.unrecognized_cities = int(cities.map(lambda c: c[0] is not None and not c[1]).sum())
    else:
        out["city"] = None
    if mapping.label:
        out["external_label"] = df[mapping.label].map(normalize_label)
        report.unknown_labels = int((out["external_label"].isna() & ~df[mapping.label].map(is_missing)).sum())
    else:
        out["external_label"] = None
    if mapping.source:
        out["source"] = df[mapping.source].map(lambda v: default_source if is_missing(v) else str(v).strip())
    else:
        out["source"] = default_source

    out["text_hash"] = out["clean_text"].map(text_hash)
    # التكرار داخل الملف: النص نفسه للمطعم نفسه في التاريخ نفسه
    dup_keys = pd.Series(
        [(h, normalize_arabic(r) if r else "", d or "")
         for h, r, d in zip(out["text_hash"], out["restaurant_name"], out["review_date"])],
        index=out.index, dtype=object,
    )
    dup_flags = dup_keys.duplicated(keep="first")
    report.duplicate_rows = int(dup_flags.sum())
    if dedupe:
        out = out[~dup_flags]

    if report.empty_text_rows:
        report.warnings.append(f"تم تجاهل {report.empty_text_rows} صفًا لأن التعليق فارغ أو قصير جدًا.")
    if report.duplicate_rows:
        action = "وحُذفت" if dedupe else "وأُبقيت حسب اختيارك"
        report.warnings.append(f"وُجد {report.duplicate_rows} تعليقًا مكررًا داخل الملف {action}.")
    if report.invalid_dates:
        report.warnings.append(f"{report.invalid_dates} تاريخًا غير صالح حُفظ فارغًا.")
    if report.invalid_ratings:
        report.warnings.append(f"{report.invalid_ratings} تقييمًا غير رقمي أو خارج النطاق حُفظ فارغًا.")
    if report.unknown_labels:
        report.warnings.append(f"{report.unknown_labels} وسمًا غير معروف (ليس إيجابي/سلبي/محايد) حُفظ فارغًا.")
    if report.unrecognized_cities:
        report.warnings.append(
            f"{report.unrecognized_cities} قيمة مدينة غير معروفة حُفظت كما هي، ولن تدخل مقارنة المدن الموثوقة."
        )
    if out.empty:
        report.errors.append("لا توجد صفوف صالحة للاستيراد بعد التحقق.")
    arabic_share = out["clean_text"].map(contains_arabic).mean() if not out.empty else 0
    if not out.empty and arabic_share < 0.5:
        report.warnings.append("أقل من نصف التعليقات تحتوي نصًا عربيًا؛ تأكد من اختيار عمود التعليقات الصحيح.")

    report.data = out.reset_index(drop=True)
    return report


def ratings_to_labels(ratings: pd.Series, max_rating: float = 5.0) -> pd.Series:
    """تحويل التقييم الرقمي إلى وسم ضعيف: (1-2 سلبي، 3 محايد، 4-5 إيجابي) على مقياس 5.

    تنبيه: هذا وسم تقريبي؛ كثير من التعليقات يخالف نصها تقييمها الرقمي.
    """
    scaled = ratings.astype(float) * (5.0 / max_rating)

    def to_label(v):
        if pd.isna(v):
            return None
        if v <= 2.5:
            return "negative"
        if v < 3.5:
            return "neutral"
        return "positive"

    return pd.Series([to_label(v) for v in scaled], index=ratings.index, dtype=object)
