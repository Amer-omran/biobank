from sra.dishes import Dish, DishExtractor, load_dishes_csv, save_dishes_csv


def names(extractor, text):
    return [m.canonical_name for m in extractor.extract(text)]


def test_synonyms_and_spelling_variants(extractor):
    assert names(extractor, "البرقر حلو") == ["برجر"]
    assert names(extractor, "شاورمه لذيذه") == ["شاورما"]
    assert names(extractor, "كبسه") == ["كبسة"]
    assert names(extractor, "burger") == ["برجر"]


def test_prefixes_and_elongation(extractor):
    assert names(extractor, "بالكبسة") == ["كبسة"]
    assert names(extractor, "والمندي") == ["مندي"]
    assert names(extractor, "الشاورماااا") == ["شاورما"]


def test_longest_match_wins(extractor):
    assert names(extractor, "دجاج مقلي وبطاطس") == ["دجاج مقلي", "بطاطس"]
    assert names(extractor, "قهوة سعودية") == ["قهوة سعودية"]


def test_never_invents_dishes(extractor):
    assert names(extractor, "الأكل لذيذ والخدمة ممتازة") == []
    assert names(extractor, "طلبت وجبة غريبة اسمها زغلول") == []
    assert names(extractor, "مطعم تميز") == []


def test_matched_text_is_original(extractor):
    mention = extractor.extract("جربت الكبسه")[0]
    assert mention.matched_text == "الكبسه"


def test_custom_dictionary_and_roundtrip(tmp_path):
    path = tmp_path / "d.csv"
    save_dishes_csv([Dish("بلاليط", "إفطار", ["بلاليط بالبيض"])], path)
    loaded = load_dishes_csv(path)
    assert loaded[0].canonical_name == "بلاليط" and loaded[0].synonyms == ["بلاليط بالبيض"]
    assert [m.canonical_name for m in DishExtractor(loaded).extract("البلاليط لذيذة")] == ["بلاليط"]


def test_from_records():
    extractor = DishExtractor.from_records([{"canonical_name": "مندي", "category": "", "synonyms": "مندى"}])
    assert [m.canonical_name for m in extractor.extract("مندى")] == ["مندي"]
