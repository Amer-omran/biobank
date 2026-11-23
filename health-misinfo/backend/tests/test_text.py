from healthmisinfo.text.langdetect import detect_language
from healthmisinfo.text.normalize import match_key, match_key_hash, normalize_for_model
from healthmisinfo.text.redact import redact_pii
from healthmisinfo.text.topics import tag_topic


def test_normalize_keeps_meaning_and_strips_noise():
    s = "اللّـــقاح يُسبّب العقم!! https://x.com/abc @someone"
    out = normalize_for_model(s, "ar")
    assert out == "اللقاح يسبب العقم!! [رابط] [مستخدم]"
    assert normalize_for_model("Visit www.example.com now", "en") == "Visit [URL] now"
    assert normalize_for_model("a​b‮c   d", "en") == "abc d"


def test_match_key_unifies_arabic_variants_and_punctuation():
    assert match_key("أحمد قال: الإنفلونزا!") == match_key("احمد قال الانفلونزا")
    assert match_key_hash("Garlic CURES flu.") == match_key_hash("garlic cures flu")
    assert match_key_hash("garlic cures flu") != match_key_hash("garlic prevents flu")


def test_language_detection():
    assert detect_language("الثوم يعالج كورونا").language == "ar"
    en = detect_language("Garlic cures COVID-19 in two days")
    assert en.language == "en" and en.supported_language == "en"
    fr = detect_language("Le vaccin contre la grippe provoque la maladie")
    assert fr.language == "unsupported" and fr.supported_language is None
    mixed = detect_language("5G يسبب كورونا covid-19 virus")
    assert mixed.language == "mixed"
    assert detect_language("!!").language == "unknown"


def test_topics_are_heuristic_and_bilingual():
    assert tag_topic("لقاح الإنفلونزا آمن") == "vaccines"
    assert tag_topic("COVID-19 vaccine causes infertility") == "covid19"
    assert tag_topic("Lemon water detoxes the liver") == "nutrition_diet"
    assert tag_topic("The weather is nice") == "other"


def test_redaction():
    text, counts = redact_pii("call +966 50 123 4567 or mail a.b@x.com, ask @someone, id 1234567890")
    assert "[PHONE]" in text and "[EMAIL]" in text and "[USER]" in text and "[ID]" in text
    assert "a.b@x.com" not in text and "4567" not in text
    assert counts == {"email": 1, "mention": 1, "id_number": 1, "phone": 1}
    assert redact_pii("Vitamin D 1000 IU daily")[1] == {}
