import pytest

from sra import ml_model
from sra.transformer_model import TransformerSentimentModel, TransformerUnavailable, map_model_labels

POS = ["الأكل لذيذ جدا", "ممتاز وأنصح فيه", "الخدمة رائعة", "حلو مرة", "طعمه رهيب", "يستاهل كل ريال",
       "المكان نظيف ومرتب", "الموظفين بشوشين"]
NEG = ["الأكل بارد وماصخ", "سيء جدا", "الخدمة بطيئة", "غالي ومو زين", "ما أنصح فيه", "وسخ ومقرف",
       "التوصيل متأخر", "ما عجبني أبد"]


def test_train_predict_save_load(tmp_path):
    texts, labels = POS + NEG, ["positive"] * len(POS) + ["negative"] * len(NEG)
    model, meta = ml_model.train_and_evaluate(texts, labels, test_size=0.25, data_is_synthetic=True)
    assert meta["metrics"]["n_test"] == 4 and meta["data_is_synthetic"]
    assert 0 <= meta["metrics"]["accuracy"] <= 1
    ml_model.save_model(model, meta, tmp_path / "m.joblib", tmp_path / "m.json")
    loaded = ml_model.SklearnSentimentModel.load(tmp_path / "m.joblib", tmp_path / "m.json")
    preds = loaded.predict(["لذيذ وممتاز", "سيء وبارد"])
    assert [p.label for p in preds] == ["positive", "negative"]
    assert all(0 <= p.confidence <= 1 for p in preds)
    assert loaded.version.startswith("sklearn-tfidf-lr-")


def test_training_rejects_bad_labels():
    with pytest.raises(ValueError):
        ml_model.train_and_evaluate(POS, ["positive"] * len(POS))
    with pytest.raises(ValueError):
        ml_model.train_and_evaluate(POS[:6] + NEG[:2], ["positive"] * 6 + ["negative"] * 2)
    with pytest.raises(ValueError):
        ml_model.train_and_evaluate(POS + NEG, ["good"] * 16)


def test_load_missing_model(tmp_path):
    with pytest.raises(FileNotFoundError):
        ml_model.SklearnSentimentModel.load(tmp_path / "none.joblib", tmp_path / "none.json")


def test_transformer_label_mapping():
    assert map_model_labels({0: "positive", 1: "negative", 2: "neutral"}) == {
        "positive": "positive", "negative": "negative", "neutral": "neutral"}
    with pytest.raises(TransformerUnavailable):
        map_model_labels({0: "LABEL_0", 1: "LABEL_1"})


def test_transformer_with_fake_pipeline():
    def fake_pipeline(texts, batch_size=16):
        return [[{"label": "positive", "score": 0.7}, {"label": "negative", "score": 0.2},
                 {"label": "neutral", "score": 0.1}] for _ in texts]

    model = TransformerSentimentModel("fake/model", pipeline=fake_pipeline,
                                      id2label={0: "positive", 1: "negative", 2: "neutral"})
    pred = model.predict(["حلو"])[0]
    assert pred.label == "positive" and pred.confidence == 0.7
    assert model.version == "hf-fake/model"


def test_transformer_missing_library_message(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(TransformerUnavailable, match="pip install"):
        TransformerSentimentModel("x/y")
