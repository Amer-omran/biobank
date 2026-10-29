"""محلل المشاعر العام والمشاعر حسب الجوانب (Aspect-Based Sentiment Analysis).

طريقة العمل (قائمة على القواعد والقاموس، قابلة للتفسير بالكامل):
1. تقسيم التعليق إلى مقاطع عند الترقيم وأدوات الاستدراك (بس، لكن...).
2. في كل مقطع: تحديد كلمات الجوانب (الأكل، السعر...) وأسماء الوجبات.
3. تحديد كلمات الرأي (لذيذ، غالي...) مع النفي (مو حلو) والتكثيف (مرة حلو).
4. ربط كل رأي بأقرب جانب في المقطع نفسه، أو بجانبه الضمني (غالي -> السعر).
5. جمع الدرجات لتحديد الشعور العام ودرجة الثقة، وكشف المشاعر المختلطة.

درجة الثقة هنا تقديرية (مبنية على قوة ووضوح الإشارات)، وليست احتمالًا معايرًا إحصائيًا.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .dishes import DishExtractor
from .lexicon import Lexicon, get_lexicon
from .text_processing import (
    clean_text,
    has_elongation,
    normalize_arabic,
    split_clauses_detailed,
    token_variants,
    tokenize,
)

GENERAL = "general"  # رأي لا يرتبط بجانب محدد (مثل «ممتاز» وحدها)
CONTRAST_WEIGHT = 1.3  # وزن المقطع الذي يلي «بس/لكن»
NEGATION_WINDOW = 3
INTENSIFIER_WINDOW = 2


@dataclass
class AspectResult:
    aspect: str
    sentiment: str
    score: float
    confidence: float
    evidence: str             # العبارة الداعمة من النص الأصلي
    dish: str | None = None   # الوجبة المرتبطة إن وُجدت في المقطع نفسه
    has_opinion: bool = True  # False: ذُكر الجانب دون رأي واضح


@dataclass
class DishResult:
    dish: str
    matched_text: str
    sentiment: str
    evidence: str


@dataclass
class SentimentResult:
    label: str
    confidence: float
    is_mixed: bool
    is_uncertain: bool
    positive_score: float
    negative_score: float
    aspects: list[AspectResult] = field(default_factory=list)
    dishes: list[DishResult] = field(default_factory=list)
    cues: list[str] = field(default_factory=list)  # كلمات الرأي التي بُني عليها الحكم
    model_name: str = config.LEXICON_MODEL_NAME
    model_version: str = config.LEXICON_MODEL_VERSION

    @property
    def label_ar(self) -> str:
        return config.SENTIMENT_AR[self.label]


@dataclass
class _Opinion:
    index: int
    score: float
    text: str
    implicit_aspect: str | None = None
    forced_anchor: int | None = None  # مرتبط بجانب محدد مسبقًا (مثل «مافي نظافة»)


@dataclass
class _Anchor:
    index: int
    aspect: str
    text: str
    dish: str | None = None


def score_to_label(score: float, threshold: float = 0.3) -> str:
    if score > threshold:
        return "positive"
    if score < -threshold:
        return "negative"
    return "neutral"


class LexiconSentimentAnalyzer:
    """المحلل الأساسي. لا يحتاج إلى تدريب ولا إنترنت."""

    name = config.LEXICON_MODEL_NAME
    version = config.LEXICON_MODEL_VERSION

    def __init__(self, dish_extractor: DishExtractor | None = None, lexicon: Lexicon | None = None,
                 confidence_threshold: float = config.CONFIDENCE_THRESHOLD):
        self.lexicon = lexicon or get_lexicon()
        self.dishes = dish_extractor
        self.confidence_threshold = confidence_threshold

    # ================================================================ عام
    def analyze(self, text: str) -> SentimentResult:
        clauses = split_clauses_detailed(clean_text(text))
        aspect_results: list[AspectResult] = []
        dish_signals: list[tuple] = []
        cues: list[str] = []
        positive = negative = 0.0

        for clause, after_contrast in clauses:
            weight = CONTRAST_WEIGHT if after_contrast else 1.0
            opinions, anchors, original_tokens = self._analyze_clause(clause)
            for op in opinions:
                cues.append(op.text)
                if op.score > 0:
                    positive += op.score * weight
                else:
                    negative += -op.score * weight
            clause_aspects = self._assign(opinions, anchors, clause)
            aspect_results.extend(clause_aspects)
            dish_signals.extend(self._dish_signals(anchors, clause_aspects, clause))

        dish_results = self._merge_dishes(dish_signals)
        return self._overall(positive, negative, aspect_results, dish_results, cues)

    # ============================================================ المقطع
    def _prepare_tokens(self, clause: str):
        """كلمات المقطع الأصلية والمطبعة، مع دمج عبارات النفي (ما فيه -> مافيه)."""
        original = tokenize(clause)
        normalized = [normalize_arabic(t) for t in original]
        merged_orig, merged_norm = [], []
        i = 0
        while i < len(normalized):
            pair = tuple(normalized[i:i + 2])
            if len(pair) == 2 and pair in self.lexicon.negation_joins:
                merged_norm.append(self.lexicon.negation_joins[pair])
                merged_orig.append(original[i] + " " + original[i + 1])
                i += 2
            else:
                merged_norm.append(normalized[i])
                merged_orig.append(original[i])
                i += 1
        return merged_orig, merged_norm

    def _analyze_clause(self, clause: str):
        lex = self.lexicon
        original, tokens = self._prepare_tokens(clause)
        used = [False] * len(tokens)
        anchors: list[_Anchor] = []
        opinions: list[_Opinion] = []

        # 1) الوجبات: تُعد مراسي لجانب جودة الطعام
        if self.dishes is not None:
            for m in self.dishes.find_in_tokens(tokens):
                anchors.append(_Anchor(m.start, "food_quality", " ".join(original[m.start:m.end]),
                                       m.canonical_name))
                for k in range(m.start, m.end):
                    used[k] = True

        # 2) كلمات جوانب متعددة الكلمات ثم المفردة
        for parts, aspect in lex.aspect_multi.items():
            n = len(parts)
            for i in range(len(tokens) - n + 1):
                if not any(used[i:i + n]) and all(
                    parts[k] in token_variants(tokens[i + k]) for k in range(n)
                ):
                    anchors.append(_Anchor(i, aspect, " ".join(original[i:i + n])))
                    for k in range(i, i + n):
                        used[k] = True

        # 3) العبارات الجاهزة (يفتح النفس، ماله طعم...)
        i = 0
        while i < len(tokens):
            matched = False
            for n in range(min(lex.max_phrase_len, len(tokens) - i), 0, -1):
                key = tuple(tokens[i:i + n])
                if key in lex.phrases and not any(used[i:i + n]):
                    score, aspect = lex.phrases[key]
                    opinions.append(_Opinion(i, score, " ".join(original[i:i + n]), aspect))
                    for k in range(i, i + n):
                        used[k] = True
                    i += n
                    matched = True
                    break
            if not matched:
                i += 1

        # 4) الكلمات المفردة
        negator_idx, absence_idx, modifiers, conditionals = [], [], {}, []
        for i, tok in enumerate(tokens):
            if used[i]:
                continue
            if tok in lex.emojis:
                opinions.append(_Opinion(i, lex.emojis[tok], original[i]))
                continue
            if tok in lex.absence_negators:
                absence_idx.append(i)
                negator_idx.append(i)
                continue
            if tok in lex.negators:
                negator_idx.append(i)
                continue
            variants = token_variants(tok)
            found = lex.lookup_opinion(variants)
            if found is not None:
                score, aspect = found
                if has_elongation(original[i]):
                    score *= 1.2
                opinions.append(_Opinion(i, score, original[i], aspect))
                continue
            # سابقة نفي ملتصقة: «ماعجبني»، «موزين»
            negated = self._attached_negation(tok)
            if negated is not None:
                score, aspect = negated
                opinions.append(_Opinion(i, self._negate(score), original[i], aspect))
                continue
            if tok in lex.intensifiers:
                modifiers[i] = lex.intensifiers[tok]
                # «كثير» قد تكون مكثفًا أو رأيًا في الكمية؛ نقرر لاحقًا
                if lex.lookup_conditional([tok]) is not None:
                    conditionals.append(i)
                continue
            if tok in lex.diminishers:
                modifiers[i] = lex.diminishers[tok]
                continue
            aspect = lex.lookup_aspect(variants)
            if aspect is not None:
                anchors.append(_Anchor(i, aspect, original[i]))
                continue
            if lex.lookup_conditional(variants) is not None:
                conditionals.append(i)

        anchors.sort(key=lambda a: a.index)

        # 5) النفي: أداة نفي قبل الرأي بمسافة قصيرة تعكس الشعور
        for op in opinions:
            for j in negator_idx:
                if 0 < op.index - j <= NEGATION_WINDOW and not self._opinion_between(opinions, j, op.index):
                    op.score = self._negate(op.score)
                    break

        # 6) المكثفات والمخففات القريبة من الرأي
        # كل مكثف يُطبق على أقرب رأي فقط؛ عند التساوي على الرأي السابق («لذيذ مرة»)
        consumed_modifiers = set()
        for j, factor in modifiers.items():
            candidates = [op for op in opinions if 0 < abs(op.index - j) <= INTENSIFIER_WINDOW]
            if candidates:
                target = min(candidates, key=lambda op: (abs(op.index - j), 0 if op.index < j else 1))
                target.score *= factor
                consumed_modifiers.add(j)

        # 7) الكلمات المشروطة بالجانب (كبير، قليل، بارد...)
        for i in conditionals:
            if i in consumed_modifiers:
                continue
            table = lex.lookup_conditional(token_variants(tokens[i]))
            anchor = self._nearest_anchor(anchors, i)
            score, aspect = None, None
            if anchor is not None and anchor.aspect in table:
                score, aspect = table[anchor.aspect], anchor.aspect
            elif "default" in table and (anchor is None or anchor.aspect not in table):
                aspect, score = table["default"]
            if score is None:
                continue
            for j in negator_idx:
                if 0 < i - j <= NEGATION_WINDOW:
                    score = self._negate(score)
                    break
            opinions.append(_Opinion(i, score, original[i], aspect))

        # 8) أدوات الانعدام قبل جانب بلا رأي: «مافي نظافة»، «بدون طعم»
        for j in absence_idx:
            for anchor in anchors:
                if 0 < anchor.index - j <= 2 and not any(
                    j < op.index <= anchor.index + 1 for op in opinions
                ):
                    opinions.append(_Opinion(anchor.index, -1.2, original[j] + " " + anchor.text,
                                             forced_anchor=anchor.index))
                    break

        opinions.sort(key=lambda o: o.index)
        return opinions, anchors, original

    def _attached_negation(self, tok: str):
        for prefix in self.lexicon.negation_prefixes():
            rest = tok[len(prefix):]
            if tok.startswith(prefix) and len(rest) >= 3:
                found = self.lexicon.lookup_opinion(token_variants(rest))
                if found is not None:
                    return found
        return None

    @staticmethod
    def _negate(score: float) -> float:
        """نفي الإيجابي يصبح سلبيًا قويًا؛ نفي السلبي يصبح إيجابيًا ضعيفًا (مو سيء ≠ ممتاز)."""
        return -0.9 * score if score > 0 else 0.5 * -score

    @staticmethod
    def _opinion_between(opinions, start, end) -> bool:
        return any(start < op.index < end for op in opinions)

    @staticmethod
    def _nearest_anchor(anchors, index):
        """أقرب جانب؛ عند التساوي نفضل الجانب السابق (الأكل لذيذ)."""
        best, best_key = None, None
        for a in anchors:
            distance = abs(a.index - index)
            key = (distance, 0 if a.index < index else 1)
            if best_key is None or key < best_key:
                best, best_key = a, key
        return best

    @staticmethod
    def _group(anchors: list[_Anchor], anchor: _Anchor) -> list[_Anchor]:
        """الجوانب المتتالية مباشرة تشترك في الرأي: «الأكل والخدمة ممتازين»."""
        group = [anchor]
        ordered = sorted(anchors, key=lambda a: a.index)
        pos = ordered.index(anchor)
        k = pos - 1
        while k >= 0 and group[0].index - ordered[k].index == 1:
            group.insert(0, ordered[k])
            k -= 1
        k = pos + 1
        while k < len(ordered) and ordered[k].index - group[-1].index == 1:
            group.append(ordered[k])
            k += 1
        return group

    # ========================================================== الربط
    def _assign(self, opinions, anchors, clause) -> list[AspectResult]:
        """يربط الآراء بالجوانب داخل المقطع، ويُرجع نتيجة لكل (جانب، وجبة)."""
        buckets: dict[tuple[str, str | None], list[float]] = {}
        dish_anchors = [a for a in anchors if a.dish]

        def nearest_dish(index):
            a = self._nearest_anchor(dish_anchors, index)
            return a.dish if a else None

        for op in opinions:
            targets: list[tuple[str, str | None]] = []
            if op.forced_anchor is not None:
                anchor = next(a for a in anchors if a.index == op.forced_anchor)
                targets = [(anchor.aspect, anchor.dish or nearest_dish(anchor.index))]
            elif op.implicit_aspect:
                targets = [(op.implicit_aspect, nearest_dish(op.index))]
            elif anchors:
                for a in self._group(anchors, self._nearest_anchor(anchors, op.index)):
                    targets.append((a.aspect, a.dish or nearest_dish(a.index)))
            for target in targets:
                buckets.setdefault(target, []).append(op.score)

        results = []
        for (aspect, dish), scores in buckets.items():
            total = sum(scores)
            label = score_to_label(total, threshold=0.2)
            confidence = min(0.95, 0.55 + 0.2 * abs(total))
            if label == "neutral":
                confidence = 0.5
            results.append(AspectResult(aspect, label, round(total, 3), round(confidence, 3), clause, dish))

        # جوانب ذُكرت دون أي رأي: نسجلها محايدة بثقة منخفضة
        covered = {a for a, _ in buckets}
        dishes_with_opinion = {d for _, d in buckets if d}
        for anchor in anchors:
            if anchor.dish and anchor.dish in dishes_with_opinion:
                continue
            if anchor.aspect not in covered:
                covered.add(anchor.aspect)
                results.append(AspectResult(anchor.aspect, "neutral", 0.0, 0.4, clause,
                                            anchor.dish, has_opinion=False))
        return results

    @staticmethod
    def _dish_signals(anchors, clause_aspects, clause) -> list[tuple]:
        """لكل وجبة في المقطع: (الوجبة، نصها، مجموع الدرجات، هل يوجد رأي، المقطع)."""
        signals, seen = [], set()
        for anchor in anchors:
            if not anchor.dish or anchor.dish in seen:
                continue
            seen.add(anchor.dish)
            linked = [a.score for a in clause_aspects if a.dish == anchor.dish and a.has_opinion]
            signals.append((anchor.dish, anchor.text, sum(linked), bool(linked), clause))
        return signals

    @staticmethod
    def _merge_dishes(signals) -> list[DishResult]:
        """يدمج إشارات الوجبة من كل المقاطع؛ العبارة الداعمة هي المقطع الذي فيه رأي."""
        merged: dict[str, dict] = {}
        for dish, text, score, has_opinion, clause in signals:
            entry = merged.setdefault(dish, {"text": text, "score": 0.0, "opinion": False, "evidence": clause})
            entry["score"] += score
            if has_opinion and not entry["opinion"]:
                entry["opinion"] = True
                entry["evidence"] = clause
        return [DishResult(dish, e["text"], score_to_label(e["score"], 0.2) if e["opinion"] else "neutral",
                           e["evidence"]) for dish, e in merged.items()]

    # ========================================================== الحكم العام
    def _overall(self, positive, negative, aspects, dishes, cues) -> SentimentResult:
        strength = positive + negative
        if strength == 0:
            # لا توجد أي إشارة شعورية: محايد، لكن غير مؤكد
            return SentimentResult("neutral", 0.45, False, True, 0.0, 0.0, aspects, dishes, cues)
        net = positive - negative
        label = score_to_label(net)
        polarity_ratio = abs(net) / strength
        confidence = 0.5 + 0.45 * polarity_ratio * min(1.0, strength / 2)
        if label == "neutral":
            confidence = 0.5
        confidence = round(max(0.34, min(0.95, confidence)), 3)
        is_mixed = positive >= 0.5 and negative >= 0.5
        return SentimentResult(
            label=label,
            confidence=confidence,
            is_mixed=is_mixed,
            is_uncertain=confidence < self.confidence_threshold,
            positive_score=round(positive, 3),
            negative_score=round(negative, 3),
            aspects=aspects,
            dishes=dishes,
            cues=cues,
        )
