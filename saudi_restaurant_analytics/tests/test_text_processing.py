import math

from sra.text_processing import (
    NormalizationOptions,
    clean_text,
    find_duplicates,
    mask_personal_info,
    normalize_arabic,
    split_clauses,
    split_clauses_detailed,
    text_hash,
    to_text,
    token_variants,
    tokenize,
)


def test_clean_text_removes_urls_and_extra_spaces():
    assert clean_text("الأكل   لذيذ https://example.com  جدا\n\n") == "الأكل لذيذ جدا"
    assert clean_text("زوروا www.test.com الآن") == "زوروا الآن"


def test_missing_values_become_empty_text():
    for value in (None, float("nan"), "", "   "):
        assert to_text(value) == "" or to_text(value).strip() == ""
        assert clean_text(value) == ""
    assert not math.isnan(len(clean_text(float("nan"))))


def test_negation_words_are_preserved():
    for text in ("لا أنصح", "مو حلو", "ما عجبني", "مش نظيف"):
        cleaned = normalize_arabic(clean_text(text))
        assert cleaned.split()[0] in {"لا", "مو", "ما", "مش"}


def test_emojis_and_exclamation_are_kept():
    tokens = tokenize("حلو مرة 😍!")
    assert "😍" in tokens and "!" in tokens


def test_normalization_default_and_configurable():
    assert normalize_arabic("أكلة إيجابية مُمتازة") == "اكله ايجابيه ممتازه"
    assert normalize_arabic("حلوووووو") == "حلوو"
    keep_ta = NormalizationOptions(ta_marbuta_to_ha=False)
    assert normalize_arabic("وجبة", keep_ta) == "وجبة"
    assert normalize_arabic("٥ نجوم") == "5 نجوم"


def test_original_text_not_changed_by_cleaning_function_inputs():
    original = "الأكلُ لذيذٌ"
    normalize_arabic(original)
    assert original == "الأكلُ لذيذٌ"


def test_mask_personal_info():
    masked = mask_personal_info("تواصل 0551234567 أو test@mail.com أو @ahmed")
    assert "0551234567" not in masked and "test@mail.com" not in masked and "@ahmed" not in masked
    # أرقام الأسعار القصيرة لا تُخفى
    assert "35" in mask_personal_info("السعر 35 ريال")


def test_duplicates_detected_despite_diacritics_and_spaces():
    flags = find_duplicates(["الأكل لذيذ", "الاكل  لذيذ", "الأكلُ لذيذ!", "الخدمة سيئة"])
    assert flags == [False, True, True, False]
    assert text_hash("مُمتاز") == text_hash("ممتاز")


def test_split_clauses_on_punctuation_and_contrast():
    assert split_clauses("الأكل لذيذ بس الخدمة بطيئة") == ["الأكل لذيذ", "الخدمة بطيئة"]
    assert split_clauses("ممتاز، والسعر مناسب. أنصح فيه!") == ["ممتاز", "والسعر مناسب", "أنصح فيه"]
    detailed = split_clauses_detailed("حلو لكن غالي")
    assert detailed == [("حلو", False), ("غالي", True)]
    assert split_clauses("") == []


def test_token_variants_strip_prefixes_and_keep_full_word_first():
    variants = token_variants("والخدمه")
    assert variants[0] == "والخدمه" and "خدمه" in variants
    assert token_variants("بارد")[0] == "بارد"
