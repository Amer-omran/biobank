"""استخراج أسماء الوجبات من التعليقات اعتمادًا على قاموس قابل للتعديل.

المبدأ الأساسي: لا نستخرج إلا ما ورد في القاموس فعلًا، فلا يمكن للنظام أن
«يخترع» اسم وجبة لم يُذكر في التعليق. القاموس ملف CSV في data/dishes_dictionary.csv
بثلاثة أعمدة: canonical_name (الاسم الموحد)، category (الفئة)، synonyms (المرادفات
مفصولة بعلامة |).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .text_processing import normalize_arabic, squeeze, token_variants, tokenize


@dataclass
class Dish:
    canonical_name: str
    category: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass
class DishMention:
    canonical_name: str
    matched_text: str   # النص كما ورد في التعليق
    start: int          # موقع أول كلمة
    end: int            # موقع ما بعد آخر كلمة


def _key(token: str) -> str:
    """مفتاح مقارنة: تطبيع + دمج الحروف المكررة (شاورماا = شاورما)."""
    return squeeze(normalize_arabic(token))


class DishExtractor:
    """يطابق أسماء الوجبات ومرادفاتها، مع دعم السوابق (بالكبسة، والمندي)."""

    def __init__(self, dishes: list[Dish]):
        self.dishes = {d.canonical_name: d for d in dishes}
        # المفتاح: صف كلمات مطبعة، القيمة: الاسم الموحد
        self.index: dict[tuple[str, ...], str] = {}
        for dish in dishes:
            for name in [dish.canonical_name, *dish.synonyms]:
                tokens = tuple(_key(t) for t in tokenize(normalize_arabic(name)))
                if tokens:
                    self.index.setdefault(tokens, dish.canonical_name)
        # فهرس حسب الكلمة الأولى لتسريع البحث، الأطول أولًا
        self.by_first: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        for key, canonical in self.index.items():
            self.by_first.setdefault(key[0], []).append((key, canonical))
        for entries in self.by_first.values():
            entries.sort(key=lambda e: len(e[0]), reverse=True)

    # ------------------------------------------------------------ الإنشاء
    @classmethod
    def from_csv(cls, path: Path | str = config.DISHES_CSV) -> "DishExtractor":
        return cls(load_dishes_csv(path))

    @classmethod
    def from_records(cls, records) -> "DishExtractor":
        """من صفوف قاعدة البيانات أو قواميس تحتوي canonical_name وcategory وsynonyms."""
        dishes = []
        for r in records:
            synonyms = r["synonyms"] or ""
            dishes.append(Dish(r["canonical_name"], r["category"] or "",
                               [s.strip() for s in synonyms.split("|") if s.strip()]))
        return cls(dishes)

    # ------------------------------------------------------------ المطابقة
    def _token_matches(self, token: str, target: str) -> bool:
        return any(_key(v) == target for v in token_variants(token))

    def find_in_tokens(self, tokens: list[str]) -> list[DishMention]:
        """يبحث في قائمة كلمات مطبعة، ويُفضّل أطول تطابق (دجاج مقلي قبل دجاج)."""
        mentions = []
        i = 0
        while i < len(tokens):
            found = None
            first_keys = {_key(v) for v in token_variants(tokens[i])}
            for first in first_keys:
                for key, canonical in self.by_first.get(first, []):
                    n = len(key)
                    if found is not None and n <= found.end - found.start:
                        continue
                    if i + n <= len(tokens) and all(
                        self._token_matches(tokens[i + k], key[k]) for k in range(1, n)
                    ):
                        found = DishMention(canonical, " ".join(tokens[i:i + n]), i, i + n)
            if found:
                mentions.append(found)
                i = found.end
            else:
                i += 1
        return mentions

    def extract(self, text: str) -> list[DishMention]:
        """يستخرج الوجبات من نص خام. يُرجع قائمة (قد تتكرر الوجبة إذا ذُكرت مرتين)."""
        original_tokens = tokenize(text)
        normalized = [normalize_arabic(t) for t in original_tokens]
        mentions = self.find_in_tokens(normalized)
        for m in mentions:
            m.matched_text = " ".join(original_tokens[m.start:m.end])
        return mentions

    def unique_dishes(self, text: str) -> list[str]:
        seen = []
        for m in self.extract(text):
            if m.canonical_name not in seen:
                seen.append(m.canonical_name)
        return seen


def load_dishes_csv(path: Path | str = config.DISHES_CSV) -> list[Dish]:
    """يقرأ القاموس من CSV، ويتجاهل الأسطر الفارغة والأسماء المكررة."""
    dishes: list[Dish] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("canonical_name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            synonyms = [s.strip() for s in (row.get("synonyms") or "").split("|") if s.strip()]
            dishes.append(Dish(name, (row.get("category") or "").strip(), synonyms))
    return dishes


def save_dishes_csv(dishes: list[Dish], path: Path | str = config.DISHES_CSV) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["canonical_name", "category", "synonyms"])
        for d in dishes:
            writer.writerow([d.canonical_name, d.category, "|".join(d.synonyms)])
