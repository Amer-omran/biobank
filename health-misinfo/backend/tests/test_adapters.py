import json

import pytest

from healthmisinfo.data.adapters.aracovid import load_aracovid
from healthmisinfo.data.adapters.arafacts import load_arafacts
from healthmisinfo.data.adapters.common import SchemaError, parse_url_list
from healthmisinfo.data.adapters.generic import ColumnMapping, parse_generic
from healthmisinfo.data.adapters.pubhealth import load_pubhealth

from .conftest import FIXTURES


def test_parse_url_list_variants():
    assert parse_url_list("('https://a', 'https://b')") == ["https://a", "https://b"]
    assert parse_url_list("()") == []
    assert parse_url_list("https://a|https://b") == ["https://a", "https://b"]
    assert parse_url_list("__import__('os')") == []  # literal_eval only – never executes code
    assert parse_url_list("('javascript:alert(1)', 'https://ok.org')") == ["https://ok.org"]


def test_arafacts_health_filter_preserves_original_labels_and_drops_claim_urls():
    res = load_arafacts(FIXTURES / "arafacts_sample_schema.csv")
    assert res.rows_read == 6
    assert res.filtered_out == {"category_not_selected": 1}
    assert len(res.records) == 5
    r = {x.external_id: x for x in res.records}
    assert r["SYN_1"].original_label == "زائف"
    assert r["SYN_1"].original_labels["normalized_label"] == "FALSE"
    assert r["SYN_3"].evidence_urls == ["https://who.example/b", "https://moh.example/c"]
    assert r["SYN_1"].extra["claim_url_count"] == 1
    assert "claim_urls" not in json.dumps(r["SYN_1"].extra)
    assert r["SYN_2"].extra["claim_type"] == "image"
    assert len(load_arafacts(FIXTURES / "arafacts_sample_schema.csv", categories=None).records) == 6


def test_arafacts_schema_error(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("ClaimID,claim\n1,x\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="missing required column"):
        load_arafacts(p)


def test_aracovid_has_no_text_but_keeps_all_labels(tmp_path):
    res = load_aracovid(FIXTURES / "aracovid_sample_schema.csv")
    assert len(res.records) == 2
    assert all(r.text is None for r in res.records)
    assert res.records[0].original_labels["Contains_Fake_Information"] == "Yes"
    assert len(res.records[0].original_labels) == 10
    hyd = tmp_path / "h.csv"
    hyd.write_text("Tweet_ID,text\n1000000000000000001,[SYNTHETIC] hydrated text\n", encoding="utf-8")
    res2 = load_aracovid(FIXTURES / "aracovid_sample_schema.csv", hyd)
    assert res2.records[0].text == "[SYNTHETIC] hydrated text" and res2.records[1].text is None


def test_pubhealth_adapter(tmp_path):
    res = load_pubhealth(FIXTURES / "pubhealth_sample")
    assert [r.original_label for r in res.records] == ["false", "true", "mixture"]
    assert res.records[0].extra["original_split"] == "train"
    with pytest.raises(SchemaError, match="Download PUBHEALTH"):
        load_pubhealth(tmp_path)


def test_generic_rejects_non_http_source_urls():
    data = b"text,url\nGarlic cures flu quickly,javascript:alert(1)\nVitamins claim text here,https://fc.org/1\n"
    recs = parse_generic(data, "x.csv", "en", ColumnMapping(text="text", label=None, source_url="url")).adapter.records
    assert [r.source_url for r in recs] == [None, "https://fc.org/1"]


def test_generic_csv_and_json_with_row_errors():
    csv_bytes = b"t,l\nGarlic cures flu quickly,false\n,true\nok claim about vitamins,true\n"
    res = parse_generic(csv_bytes, "x.csv", "en", ColumnMapping(text="t", label="l"))
    assert len(res.adapter.records) == 2
    assert res.row_errors == [{"row": 2, "error": "empty text"}]
    js = json.dumps({"records": [{"text": "نص تجريبي عن الصحة", "label": "x"}]}).encode()
    res = parse_generic(js, "x.json", "ar", ColumnMapping())
    assert res.adapter.records[0].language == "ar"
    with pytest.raises(SchemaError, match="Missing column"):
        parse_generic(csv_bytes, "x.csv", "en", ColumnMapping(text="nope"))
    with pytest.raises(SchemaError, match="Unsupported file type"):
        parse_generic(b"x", "x.xlsx", "en", ColumnMapping())
