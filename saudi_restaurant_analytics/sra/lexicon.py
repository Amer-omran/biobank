"""قواميس المشاعر وجوانب الرأي (فصحى + لهجة سعودية/خليجية).

القواميس مكتوبة بإملاء طبيعي، وتُطبَّع تلقائيًا عند التحميل، لذلك يمكنك إضافة
كلمات جديدة بأي إملاء (ة أو ه، أ أو ا) دون القلق من التطابق.

الأوزان: 1.0 رأي عادي، 1.5 رأي قوي، 2.0 رأي شديد جدًا.
"""

from __future__ import annotations

from .text_processing import normalize_arabic, squeeze

# ---------------------------------------------------------- كلمات إيجابية
# الصيغة: الكلمة: (الوزن، الجانب الضمني أو None)
# الجانب الضمني يعني أن الكلمة نفسها تدل على الجانب (مثل «رخيص» تدل على السعر).
POSITIVE_WORDS = {
    "ممتاز": (1.5, None), "ممتازة": (1.5, None), "ممتازين": (1.5, None),
    "رائع": (1.5, None), "رائعة": (1.5, None), "رايع": (1.5, None), "روعة": (1.5, None),
    "لذيذ": (1.5, "food_quality"), "لذيذة": (1.5, "food_quality"), "لذيذين": (1.5, "food_quality"),
    "لذاذة": (1.3, "food_quality"), "الذ": (1.5, "food_quality"), "اطيب": (1.3, "food_quality"),
    "حلو": (1.0, None), "حلوة": (1.0, None), "احلى": (1.2, None), "طيب": (1.0, None),
    "طيبة": (1.0, None), "طيبين": (1.0, None), "زين": (1.0, None), "زينة": (1.0, None),
    "جميل": (1.0, None), "جميلة": (1.0, None), "مميز": (1.2, None), "مميزة": (1.2, None),
    "متميز": (1.2, None), "فخم": (1.2, None), "فخمة": (1.2, None), "مبدع": (1.2, None),
    "مبدعين": (1.2, None), "ابداع": (1.2, None), "تحفة": (1.5, None), "خرافي": (1.5, None),
    "خرافية": (1.5, None), "اسطوري": (1.5, None), "يجنن": (1.5, None), "يهبل": (1.5, None),
    "راقي": (1.2, None), "راقية": (1.2, None), "خطير": (1.2, None), "رهيب": (1.5, None), "رهيبة": (1.5, None), "فلة": (0.8, None), "عسل": (1.0, None), "افضل": (1.0, None),
    "احسن": (1.0, None), "ممتع": (1.0, None), "مقبول": (0.3, None), "معقول": (0.8, None),
    # أُضيفت بعد تحليل أخطاء ملف تدريب AQTE (الإصدار 1.1)
    "جيد": (1.0, None), "جيدة": (1.0, None), "جيدين": (1.0, None), "جيدا": (1.0, None),
    "كويس": (1.0, None), "كويسة": (1.0, None), "كويسين": (1.0, None), "فاخر": (1.0, None),
    "بطل": (1.3, None), "بطلة": (1.3, None), "تجنن": (1.5, None),
    "اخلاق": (1.0, "service"), "احترام": (1.0, "service"), "ترحيب": (1.0, "service"),
    "اشكر": (0.8, None), "نشكر": (0.8, None),
    "معقولة": (0.8, None), "مناسب": (0.7, None), "مناسبة": (0.7, None),
    "عجبني": (1.2, None), "عجبتني": (1.2, None), "عجبنا": (1.2, None), "حبيت": (1.2, None),
    "احب": (1.0, None), "انصح": (1.2, None), "انصحكم": (1.2, None), "يستاهل": (1.2, None),
    "تستاهل": (1.2, None), "برجع": (1.0, None), "بنرجع": (1.0, None), "راجعين": (1.0, None),
    "ارجع": (0.8, None), "اعود": (0.8, None), "شكرا": (0.5, None), "تسلم": (0.5, None),
    "طازج": (1.2, "food_quality"), "طازجة": (1.2, "food_quality"), "فريش": (1.2, "food_quality"),
    "مقرمش": (1.0, "food_quality"), "مقرمشة": (1.0, "food_quality"), "مستوي": (0.8, "food_quality"),
    "رخيص": (1.0, "price"), "رخيصة": (1.0, "price"), "رخيصه": (1.0, "price"),
    "وافي": (1.0, "quantity"), "وافية": (1.0, "quantity"), "يشبع": (1.0, "quantity"),
    "مشبع": (1.0, "quantity"), "تشبع": (1.0, "quantity"),
    "نظيف": (1.2, "cleanliness"), "نظيفة": (1.2, "cleanliness"), "معقم": (1.0, "cleanliness"),
    "محترم": (1.0, None), "محترمين": (1.0, None), "ودود": (1.0, "service"), "ودودين": (1.0, "service"),
    "بشوش": (1.0, "service"), "بشوشين": (1.0, "service"), "متعاون": (1.0, "service"),
    "متعاونين": (1.0, "service"), "خلوق": (1.0, "service"),
    "رايق": (1.0, "ambiance"), "رايقة": (1.0, "ambiance"),
    "هادي": (0.8, "ambiance"), "هادئ": (0.8, "ambiance"), "مريح": (0.8, "ambiance"),
    "مريحة": (0.8, "ambiance"), "واسع": (0.6, "ambiance"), "مرتب": (0.8, None), "مرتبة": (0.8, None),
    "good": (1.0, None), "nice": (1.0, None), "great": (1.2, None), "excellent": (1.5, None),
    "amazing": (1.5, None), "delicious": (1.5, "food_quality"), "tasty": (1.2, "food_quality"),
    "perfect": (1.5, None), "love": (1.2, None), "clean": (1.2, "cleanliness"),
}

# ---------------------------------------------------------- كلمات سلبية
NEGATIVE_WORDS = {
    "سيء": (1.5, None), "سيئ": (1.5, None), "سيئة": (1.5, None), "سيئين": (1.5, None),
    "اسوا": (1.8, None), "زفت": (1.8, None), "ردي": (1.5, None), "رديء": (1.5, None),
    "رديئة": (1.5, None), "تعبان": (1.0, None), "تعبانة": (1.0, None), "فاشل": (1.5, None),
    "فاشلة": (1.5, None), "خايب": (1.3, None), "خايبة": (1.3, None), "خربان": (1.0, None),
    "مقرف": (1.8, None), "مقرفة": (1.8, None), "يقرف": (1.8, None), "ندمت": (1.5, None),
    "خسارة": (1.3, None), "مخيب": (1.3, None), "مخيبة": (1.3, None),
    "ناقص": (1.0, None), "ناقصة": (1.0, None),
    "خايس": (1.8, "food_quality"), "خايسة": (1.8, "food_quality"), "معفن": (2.0, "food_quality"),
    "بايت": (1.5, "food_quality"), "بايتة": (1.5, "food_quality"), "ماصخ": (1.3, "food_quality"),
    "ماصخة": (1.3, "food_quality"), "ماسخ": (1.3, "food_quality"), "مالح": (1.0, "food_quality"),
    "مالحة": (1.0, "food_quality"), "محروق": (1.3, "food_quality"), "محروقة": (1.3, "food_quality"),
    "ني": (1.0, "food_quality"), "نيء": (1.0, "food_quality"), "ناشف": (1.0, "food_quality"),
    "ناشفة": (1.0, "food_quality"), "يابس": (1.0, "food_quality"), "قاسي": (0.8, "food_quality"),
    "دسم": (0.6, "food_quality"), "تسمم": (2.0, "food_quality"), "مغص": (1.5, "food_quality"),
    "غالي": (1.2, "price"), "غالية": (1.2, "price"), "مبالغ": (1.2, "price"), "مكلف": (1.0, "price"),
    "نصب": (1.5, "price"), "سرقة": (1.5, "price"),
    "وسخ": (1.5, "cleanliness"), "وسخة": (1.5, "cleanliness"), "قذر": (1.8, "cleanliness"),
    "قذرة": (1.8, "cleanliness"), "متسخ": (1.5, "cleanliness"), "متسخة": (1.5, "cleanliness"),
    "حشرات": (1.8, "cleanliness"), "حشرة": (1.8, "cleanliness"), "صرصور": (2.0, "cleanliness"),
    "صراصير": (2.0, "cleanliness"), "ذباب": (1.5, "cleanliness"), "شعرة": (1.2, "cleanliness"),
    "وقح": (1.5, "service"), "وقحين": (1.5, "service"),
    "مهمل": (1.3, None), "مهملين": (1.3, None), "عصبي": (1.0, "service"), "متكبر": (1.0, "service"),
    "ازعاج": (1.0, "ambiance"), "مزعج": (1.0, "ambiance"), "مزعجة": (1.0, "ambiance"),
    "ضيق": (0.7, "ambiance"), "خانق": (0.8, "ambiance"),
    "bad": (1.5, None), "terrible": (2.0, None), "worst": (2.0, None), "disgusting": (2.0, None),
    "slow": (1.2, None), "expensive": (1.2, "price"), "dirty": (1.5, "cleanliness"),
}

# --------------------------------------------- كلمات يعتمد معناها على الجانب
# «كبير» إيجابية مع الكمية وسلبية مع السعر. «default» تُستخدم إن لم يُذكر جانب.
CONDITIONAL_WORDS = {
    "كبير": {"quantity": 1.0, "price": -1.0},
    "كبيرة": {"quantity": 1.0, "price": -1.0},
    "صغير": {"quantity": -1.0, "ambiance": -0.6, "default": ("quantity", -0.8)},
    "صغيرة": {"quantity": -1.0, "ambiance": -0.6, "default": ("quantity", -0.8)},
    "قليل": {"quantity": -1.0, "price": 0.6, "default": ("quantity", -1.0)},
    "قليلة": {"quantity": -1.0, "price": 0.6, "default": ("quantity", -1.0)},
    "كثير": {"quantity": 1.0, "price": -0.8},
    "كثيرة": {"quantity": 1.0, "price": -0.8},
    "بارد": {"food_quality": -1.2, "delivery": -1.2, "ambiance": 0.5, "default": ("food_quality", -1.2)},
    "باردة": {"food_quality": -1.2, "delivery": -1.2, "ambiance": 0.5, "default": ("food_quality", -1.2)},
    "حار": {"food_quality": 0.6, "default": ("food_quality", 0.6)},
    "ساخن": {"food_quality": 0.8, "delivery": 0.8, "default": ("food_quality", 0.8)},
    "عالي": {"price": -1.0, "food_quality": 1.0},
    "عالية": {"price": -1.0, "food_quality": 1.0},
    "مرتفع": {"price": -1.0}, "مرتفعة": {"price": -1.0},
    "طويل": {"service": -1.0, "delivery": -1.0},
    "طويلة": {"service": -1.0, "delivery": -1.0},
    # السرعة: AQTE تعدّها من الخدمة، إلا إن كان الحديث عن التوصيل
    "سريع": {"service": 1.0, "delivery": 1.0, "default": ("service", 1.0)},
    "سريعة": {"service": 1.0, "delivery": 1.0, "default": ("service", 1.0)},
    "بسرعة": {"service": 0.8, "delivery": 0.8, "default": ("service", 0.8)},
    "سرعة": {"service": 0.8, "delivery": 0.8, "default": ("service", 0.8)},
    "بطيء": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "بطيئة": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "بطيئين": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "بطي": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "تاخير": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "تاخر": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "تاخروا": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "متاخر": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
    "متاخرة": {"service": -1.2, "delivery": -1.2, "default": ("service", -1.2)},
}

# --------------------------------------------------- عبارات متعددة الكلمات
# تُطابَق قبل الكلمات المفردة، وتستهلك كلماتها.
PHRASES = {
    "يفتح النفس": (1.5, "food_quality"), "يرد الروح": (1.5, "food_quality"),
    "ولا غلطة": (1.5, None), "ما عليه كلام": (1.5, None), "ماعليه كلام": (1.5, None),
    "ما يعلى عليه": (1.5, None), "مايعلى عليه": (1.5, None),
    "يستاهل كل ريال": (1.5, "price"), "قيمة مقابل سعر": (1.0, "price"),
    "على الوقت": (1.0, "delivery"), "في الوقت": (0.8, "delivery"),
    "يسد النفس": (-1.5, "food_quality"), "ماله طعم": (-1.3, "food_quality"),
    "ما له طعم": (-1.3, "food_quality"), "بدون طعم": (-1.3, "food_quality"),
    "طول الانتظار": (-1.2, "service"), "انتظرنا كثير": (-1.2, "service"),
    "انتظرنا ساعة": (-1.3, "service"), "وصل بارد": (-1.3, "delivery"),
    "وصلت باردة": (-1.3, "delivery"), "اخر مرة": (-1.3, None), "لن اعود": (-1.5, None),
    "حرام الفلوس": (-1.5, "price"), "خسارة فلوس": (-1.5, "price"),
    "على الفاضي": (-0.8, None), "مو نظيف": (-1.3, "cleanliness"),
    "لا بأس": (0.6, None), "لا باس": (0.6, None), "لاباس": (0.6, None), "لابأس": (0.6, None),
    "زي العسل": (1.3, None),
    # تعابير تبدأ بأداة نفي لكنها إيجابية؛ تُطابق كعبارة كاملة حتى لا يُعكس معناها
    "ما شاء الله": (0.5, None), "ماشاء الله": (0.5, None), "ما قصروا": (1.2, "service"),
    "ماقصروا": (1.2, "service"), "ما قصرو": (1.2, "service"), "لا يفوتكم": (1.3, None),
    "لايفوتكم": (1.3, None), "يعطيكم العافية": (0.8, None),
}

# --------------------------------------------------------- أدوات النفي
NEGATORS = {"لا", "ما", "مو", "مب", "مش", "ليس", "ليست", "لم", "لن", "غير", "موب", "مهو",
            "ماهو", "ماهي", "مهي", "ابدا", "not", "no", "never"}
# أدوات تدل على انعدام الشيء: «مافي نظافة» = سلبي للنظافة
ABSENCE_NEGATORS = {"مافي", "مافيه", "مافيها", "بدون", "ماله", "مالها", "معدوم", "معدومة",
                    "عديم", "عديمة", "لايوجد", "مايوجد", "without"}
# عبارات نفي من كلمتين تُدمج في كلمة واحدة قبل التحليل
NEGATION_JOINS = {("ما", "في"): "مافي", ("ما", "فيه"): "مافيه", ("ما", "فيها"): "مافيها",
                  ("ما", "له"): "ماله", ("ما", "لها"): "مالها", ("لا", "يوجد"): "لايوجد",
                  ("ما", "يوجد"): "مايوجد"}
# سوابق نفي ملتصقة بالكلمة: «ماعجبني»، «موزين»
NEGATION_PREFIXES = ("ما", "مو", "مب")

# ------------------------------------------------------- المكثفات والمخففات
INTENSIFIERS = {"جدا": 1.5, "مرة": 1.5, "مره": 1.5, "مرا": 1.5, "واجد": 1.4, "وايد": 1.4,
                "حيل": 1.4, "للغاية": 1.5, "بزيادة": 1.3, "كثير": 1.3, "very": 1.5, "so": 1.3}
DIMINISHERS = {"شوي": 0.6, "شوية": 0.6, "نوعا": 0.6, "نوعاما": 0.6, "نسبيا": 0.7,
               "تقريبا": 0.8, "بعض": 0.7}

# --------------------------------------------------------- الرموز التعبيرية
EMOJI_SCORES = {
    "😍": 1.2, "😋": 1.2, "👌": 1.0, "👍": 1.0, "❤": 1.0, "💯": 1.0, "😊": 0.8, "🥰": 1.0,
    "👏": 1.0, "🤤": 1.0, "😁": 0.8, "😃": 0.8, "🌹": 0.6, "✨": 0.5, "💕": 0.8, "🔥": 0.6,
    "😡": -1.3, "👎": -1.2, "🤢": -1.5, "🤮": -1.5, "😤": -1.0, "😠": -1.2, "💩": -1.5,
    "😒": -0.8, "😞": -1.0, "😔": -0.8, "🤬": -1.5, "😑": -0.6, "🙄": -0.6,
}

# ------------------------------------------------------ كلمات جوانب الرأي
ASPECT_KEYWORDS = {
    "food_quality": ["اكل", "أكل", "طعام", "قهوة", "مشروبات", "مشروب", "حلويات", "طعم", "نكهة", "مذاق", "طبخ", "طبخة", "شيف", "الطباخ", "لحم",
                     "دجاج", "رز", "صوص", "خبز", "وجبة", "وجبات", "اكلات", "طبق", "اطباق", "صحن",
                     "جودة", "مستوى الاكل", "food", "taste"],
    "price": ["سعر", "اسعار", "أسعار", "فلوس", "ريال", "قيمة", "تكلفة", "فاتورة", "حساب", "مبلغ",
              "عرض", "عروض", "خصم", "كوبون", "price", "prices"],
    "quantity": ["كمية", "كميات", "حجم", "حصة", "portion", "size"],
    "service": ["خدمة", "موظف", "موظفين", "موظفة", "عامل", "عمال", "كاشير", "ويتر", "جرسون",
                "نادل", "استقبال", "تعامل", "طاقم", "ستاف", "محاسب", "انتظار", "تقديم",
                "service", "staff"],
    "delivery": ["توصيل", "مندوب", "مناديب", "دليفري", "ديليفري", "هنقرستيشن", "هنقر", "مرسول",
                 "تويو", "سواق", "سايق", "وصلني", "وصلتني", "وصل الطلب", "التطبيق", "delivery"],
    "cleanliness": ["نظافة", "حمام", "حمامات", "دورات المياه", "دورة المياه", "طاولات", "طاولة",
                    "مطبخ", "تعقيم", "cleanliness"],
    "ambiance": ["مكان", "معمار", "تصميم", "جلسات", "جلسة", "ديكور", "اجواء", "أجواء", "جو", "موسيقى", "اطلالة",
                 "اضاءة", "تكييف", "مكيف", "اثاث", "كراسي", "عوائل", "مواقف", "ambiance", "place"],
}


# ===================================================================== البناء
def _norm(word: str) -> str:
    return normalize_arabic(word)


def _build_word_index(words: dict, sign: float) -> dict:
    index = {}
    for word, (weight, aspect) in words.items():
        key = _norm(word)
        index[key] = (sign * weight, aspect)
        index.setdefault(squeeze(key), (sign * weight, aspect))
    return index


class Lexicon:
    """يجمع القواميس بعد تطبيعها في فهارس سريعة البحث."""

    def __init__(self):
        self.opinions = _build_word_index(POSITIVE_WORDS, 1.0)
        self.opinions.update(_build_word_index(NEGATIVE_WORDS, -1.0))
        self.conditional = {_norm(w): v for w, v in CONDITIONAL_WORDS.items()}
        self.phrases = {tuple(_norm(p).split()): v for p, v in PHRASES.items()}
        self.max_phrase_len = max(len(p) for p in self.phrases)
        self.negators = {_norm(w) for w in NEGATORS}
        self.absence_negators = {_norm(w) for w in ABSENCE_NEGATORS}
        self.negation_joins = {(_norm(a), _norm(b)): _norm(c) for (a, b), c in NEGATION_JOINS.items()}
        self.intensifiers = {_norm(w): v for w, v in INTENSIFIERS.items()}
        self.diminishers = {_norm(w): v for w, v in DIMINISHERS.items()}
        self.emojis = dict(EMOJI_SCORES)
        self.aspect_single: dict[str, str] = {}
        self.aspect_multi: dict[tuple, str] = {}
        for aspect, words in ASPECT_KEYWORDS.items():
            for word in words:
                parts = tuple(_norm(word).split())
                if len(parts) == 1:
                    self.aspect_single.setdefault(parts[0], aspect)
                else:
                    self.aspect_multi[parts] = aspect

    @staticmethod
    def negation_prefixes() -> tuple[str, ...]:
        return NEGATION_PREFIXES

    def lookup_opinion(self, variants: list[str]):
        """يبحث عن أول صيغة موجودة في قاموس الآراء. يُرجع (الدرجة، الجانب الضمني) أو None."""
        for v in variants:
            if v in self.opinions:
                return self.opinions[v]
        for v in variants:
            sq = squeeze(v)
            if sq in self.opinions:
                return self.opinions[sq]
        return None

    def lookup_conditional(self, variants: list[str]):
        for v in variants:
            if v in self.conditional:
                return self.conditional[v]
        return None

    def lookup_aspect(self, variants: list[str]):
        for v in variants:
            if v in self.aspect_single:
                return self.aspect_single[v]
        return None


_DEFAULT_LEXICON: Lexicon | None = None


def get_lexicon() -> Lexicon:
    """نسخة واحدة مشتركة من القاموس (تُبنى عند أول استخدام)."""
    global _DEFAULT_LEXICON
    if _DEFAULT_LEXICON is None:
        _DEFAULT_LEXICON = Lexicon()
    return _DEFAULT_LEXICON
