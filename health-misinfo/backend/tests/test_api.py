"""API integration tests (FastAPI TestClient + temp database)."""

import io
import json

from healthmisinfo.ratelimit import limiter

from .conftest import FIXTURES, PASSWORD


def test_health_and_openapi(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] is True
    spec = client.get("/openapi.json").json()
    for path in [
        "/health",
        "/api/v1/models",
        "/api/v1/analyze",
        "/api/v1/history",
        "/api/v1/datasets",
        "/api/v1/datasets/import",
        "/api/v1/analytics",
        "/api/v1/reviews",
        "/api/v1/reviews/pending",
        "/api/v1/reports",
    ]:
        assert path in spec["paths"], path
    assert r.headers["x-content-type-options"] == "nosniff"


def test_auth_required_and_login_flow(client, users):
    assert client.get("/api/v1/models").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "wrong"}).status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "ADMIN@test.local", "password": PASSWORD})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert client.get("/api/v1/auth/me").json()["role"] == "admin"  # cookie session
    # CSRF: cookie-authenticated POST without X-Requested-With is refused
    assert client.post("/api/v1/analyze", json={"text": "Garlic cures influenza in one day"}).status_code == 403
    ok = client.post("/api/v1/analyze", json={"text": "Garlic cures influenza in one day"}, headers={"X-Requested-With": "fetch"})
    assert ok.status_code == 200
    client.post("/api/v1/auth/logout")
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_models_report_not_trained(client, auth):
    r = client.get("/api/v1/models", headers=auth["res"]).json()
    states = {s["language"]: s["state"] for s in r["slots"]}
    assert states == {"ar": "not_trained", "en": "not_trained"}
    assert {s["base_model"] for s in r["slots"]} == {"aubmindlab/bert-base-arabertv02", "FacebookAI/xlm-roberta-base"}
    assert r["versions"] == []


def test_analyze_without_model_returns_no_prediction(client, auth):
    r = client.post("/api/v1/analyze", json={"text": "اللقاح يسبب العقم عند النساء ويجب تجنبه"}, headers=auth["res"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "model_not_trained" and body["model_state"] == "not_trained"
    assert body["prediction"] is None and body["model"] is None
    assert body["language"]["detected"] == "ar" and body["language"]["used"] == "ar"
    assert body["disclaimer"]["en"].startswith("Research prediction only")
    assert body["review_status"] == "not_required"
    assert body["health_topic"] == "vaccines"
    fr = client.post("/api/v1/analyze", json={"text": "Le vaccin contre la grippe provoque la maladie"}, headers=auth["res"]).json()
    assert fr["status"] == "unsupported_language" and fr["prediction"] is None
    forced = client.post("/api/v1/analyze", json={"text": "Garlic cures influenza in one day", "model": "ar"}, headers=auth["res"]).json()
    assert "language_mismatch" in forced["warnings"]


def test_analyze_validation_and_pii_redaction(client, auth):
    assert client.post("/api/v1/analyze", json={"text": "short"}, headers=auth["res"]).status_code == 422
    assert client.post("/api/v1/analyze", json={"text": "x" * 2001}, headers=auth["res"]).status_code == 422
    assert client.post("/api/v1/analyze", json={"text": "valid text here", "model": "fr"}, headers=auth["res"]).status_code == 422
    r = client.post("/api/v1/analyze", json={"text": "Call +966 50 123 4567 to buy the cure for diabetes"}, headers=auth["res"]).json()
    assert "4567" not in r["text"] and r["redactions"] == {"phone": 1}


def test_similar_claims_come_only_from_real_imports(client, auth):
    csv_text = "text,label\nGarlic cures influenza within one day,F\nHandwashing reduces infections,T\n"
    files = {"file": ("d.csv", io.BytesIO(csv_text.encode()), "text/csv")}
    r = client.post(
        "/api/v1/datasets/import",
        headers=auth["admin"],
        files=files,
        data={"name": "sim", "version": "1", "language": "en", "label_mapping": json.dumps({"F": "MISLEADING", "T": "SUPPORTED"}), "license_confirmed": "true"},
    )
    assert r.status_code == 200, r.text
    res = client.post("/api/v1/analyze", json={"text": "Does garlic cure influenza in one day?"}, headers=auth["res"]).json()
    assert res["similar_claims"] and res["similar_claims"][0]["original_label"] == "F"
    assert res["prediction"] is None  # similarity never becomes a verdict


def test_history_visibility_and_review_request(client, auth):
    a_id = client.post("/api/v1/analyze", json={"text": "Lemon water cures diabetes quickly"}, headers=auth["res"]).json()["id"]
    client.post("/api/v1/analyze", json={"text": "Vitamin C prevents all colds forever"}, headers=auth["rev1"])
    mine = client.get("/api/v1/history", headers=auth["res"]).json()
    assert mine["total"] == 1
    assert client.get("/api/v1/history", headers=auth["admin"]).json()["total"] == 2
    assert client.get(f"/api/v1/history/{a_id}", headers=auth["rev1"]).status_code == 200
    other = client.get("/api/v1/history", headers=auth["rev1"]).json()["items"]
    other_id = [i["id"] for i in other if i["id"] != a_id][0]
    assert client.get(f"/api/v1/history/{other_id}", headers=auth["res"]).status_code == 404
    rr = client.post(f"/api/v1/history/{a_id}/request-review", headers=auth["res"]).json()
    assert rr["review_status"] == "pending"


def test_review_workflow_disagreement_and_adjudication(client, auth):
    a_id = client.post("/api/v1/analyze", json={"text": "Honey and garlic cure measles in children"}, headers=auth["res"]).json()["id"]
    client.post(f"/api/v1/history/{a_id}/request-review", headers=auth["res"])
    assert client.post("/api/v1/reviews", headers=auth["res"], json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING"}).status_code == 403
    pend = client.get("/api/v1/reviews/pending", headers=auth["rev1"]).json()
    assert [i["target_id"] for i in pend["items"]] == [a_id] and pend["items"][0]["reviews"] is None  # blind
    r1 = client.post(
        "/api/v1/reviews",
        headers=auth["rev1"],
        json={
            "target_type": "analysis",
            "target_id": a_id,
            "label": "MISLEADING",
            "evidence_urls": ["https://www.who.int/news-room/fact-sheets/detail/measles"],
        },
    )
    assert r1.status_code == 200 and r1.json()["target_review_status"] == "in_review"
    assert client.post("/api/v1/reviews", headers=auth["rev1"], json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING"}).status_code == 409
    assert client.get("/api/v1/reviews/pending", headers=auth["rev1"]).json()["total"] == 0
    r2 = client.post("/api/v1/reviews", headers=auth["rev2"], json={"target_type": "analysis", "target_id": a_id, "label": "NEEDS_REVIEW"})
    assert r2.json()["target_review_status"] == "disagreement"
    assert (
        client.post(
            "/api/v1/reviews", headers=auth["rev2"], json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING", "is_adjudication": True}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/reviews/pending", headers=auth["admin"]).json()["items"][0]["reviews"]  # admin sees labels
    adj = client.post(
        "/api/v1/reviews", headers=auth["admin"], json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING", "is_adjudication": True}
    )
    assert adj.json()["target_review_status"] == "adjudicated" and adj.json()["target_final_label_name"] == "MISLEADING"
    assert (
        client.post(
            "/api/v1/reviews",
            headers=auth["rev1"],
            json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING", "evidence_urls": ["javascript:alert(1)"]},
        ).status_code
        == 422
    )
    an = client.get("/api/v1/analytics", headers=auth["res"]).json()["reviews"]
    assert an["agreement"]["items_with_2plus_reviews"] == 1 and an["agreement"]["percent_agreement"] == 0.0


def test_dataset_import_preview_synthetic_guard_and_samples(client, auth):
    data = (FIXTURES / "synthetic_claims_en.csv").read_bytes()
    pv = client.post("/api/v1/datasets/preview", headers=auth["res"], files={"file": ("s.csv", data, "text/csv")}, data={"label_column": "label"}).json()
    assert pv["rows"] == 63 and pv["declares_synthetic"] is True and set(pv["label_values"]) == {"SUPPORTED", "MISLEADING", "NEEDS_REVIEW"}
    base = {
        "name": "syn-en",
        "version": "1",
        "language": "en",
        "group_key_column": "group_key",
        "id_column": "id",
        "label_mapping": json.dumps({"SUPPORTED": "SUPPORTED", "MISLEADING": "MISLEADING", "NEEDS_REVIEW": "NEEDS_REVIEW"}),
    }
    refused = client.post("/api/v1/datasets/import", headers=auth["res"], files={"file": ("s.csv", data, "text/csv")}, data=base)
    assert refused.status_code == 422 and "synthetic" in refused.json()["detail"]
    assert client.post("/api/v1/datasets/import", headers=auth["rev1"], files={"file": ("s.csv", data, "text/csv")}, data=base).status_code == 403
    ok = client.post("/api/v1/datasets/import", headers=auth["res"], files={"file": ("s.csv", data, "text/csv")}, data={**base, "is_synthetic": "true"})
    assert ok.status_code == 200, ok.text
    ds = ok.json()
    assert ds["is_synthetic"] is True and ds["stats"]["eligible"] == 0
    assert (
        client.post(
            "/api/v1/datasets/import", headers=auth["res"], files={"file": ("s.csv", data, "text/csv")}, data={**base, "is_synthetic": "true"}
        ).status_code
        == 409
    )
    lst = client.get("/api/v1/datasets", headers=auth["res"]).json()
    assert lst["progress"]["en"]["eligible"] == 0 and lst["progress"]["en"]["shortfall"] == 3000
    smp = client.get(f"/api/v1/datasets/{ds['id']}/samples?page_size=5", headers=auth["res"]).json()
    assert smp["total"] == 63 and smp["items"][0]["exclusion_reason"] == "synthetic_fixture"
    q = client.post(f"/api/v1/datasets/{ds['id']}/queue-review", headers=auth["res"], json={"count": 5, "only_eligible": False}).json()
    assert q["queued"] == 5
    assert client.get("/api/v1/reviews/pending?target_type=sample", headers=auth["rev1"]).json()["total"] == 5


def test_dataset_import_errors(client, auth):
    bad = client.post(
        "/api/v1/datasets/import",
        headers=auth["res"],
        files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")},
        data={"name": "x", "version": "1", "language": "en"},
    )
    assert bad.status_code == 422 and "Missing column" in bad.json()["detail"]
    inj = client.post(
        "/api/v1/datasets/import",
        headers=auth["res"],
        files={"file": ("x.csv", b"text\nhello world\n", "text/csv")},
        data={"name": "../etc", "version": "1", "language": "en"},
    )
    assert inj.status_code == 422
    unk = client.post(
        "/api/v1/datasets/import",
        headers=auth["res"],
        files={"file": ("x.csv", b"text\nhello world\n", "text/csv")},
        data={"name": "x", "version": "1", "language": "en", "source_key": "nope"},
    )
    assert unk.status_code == 422


def test_sources_and_license_review(client, auth):
    src = {s["key"]: s for s in client.get("/api/v1/sources", headers=auth["res"]).json()["items"]}
    assert src["arafacts"]["license_status"] == "verified" and src["pubhealth"]["license_status"] == "unclear_needs_review"
    assert src["arafacts"]["label_mapping"]["entry_status_counts"]["proposed"] > 0
    assert client.get("/api/v1/sources/arafacts/mapping", headers=auth["res"]).json()["source_key"] == "arafacts"
    body = {"license_status": "verified", "license_evidence": "Checked LICENSE file and author permission e-mail"}
    assert client.patch("/api/v1/sources/pubhealth", headers=auth["res"], json=body).status_code == 403
    r = client.patch("/api/v1/sources/pubhealth", headers=auth["admin"], json=body).json()
    assert r["license_status"] == "verified" and "R-0001" in r["license_evidence"]


def test_split_endpoint_refuses_without_data(client, auth):
    r = client.post("/api/v1/datasets/splits", headers=auth["admin"], json={"language": "ar", "version": "v1"})
    assert r.status_code == 422 and r.json()["detail"]["report"]["status"] == "invalid"
    assert client.post("/api/v1/datasets/splits", headers=auth["res"], json={"language": "ar", "version": "v1"}).status_code == 403


def test_analytics_and_reports_distinguish_measured_results(client, auth):
    an = client.get("/api/v1/analytics", headers=auth["res"]).json()
    assert an["measured_results_available"] is False and an["models"] == []
    cat = client.get("/api/v1/reports", headers=auth["res"]).json()
    assert "summary" in cat["types"]
    pdf = client.get("/api/v1/reports?type=summary&format=pdf", headers=auth["res"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    client.post("/api/v1/analyze", json={"text": '=HYPERLINK("http://evil") garlic cures flu'}, headers=auth["res"])
    csv_r = client.get("/api/v1/reports?type=analyses&format=csv", headers=auth["res"])
    assert csv_r.status_code == 200 and "'=HYPERLINK" in csv_r.content.decode("utf-8-sig")
    assert client.get("/api/v1/reports?type=analyses&format=pdf", headers=auth["res"]).content[:4] == b"%PDF"
    assert client.get("/api/v1/reports?type=evaluation&format=pdf", headers=auth["res"]).status_code == 404
    assert client.get("/api/v1/reports?type=audit&format=csv", headers=auth["res"]).status_code == 403
    assert client.get("/api/v1/reports?type=audit&format=csv", headers=auth["admin"]).status_code == 200
    assert client.get("/api/v1/reports?type=sources&format=csv", headers=auth["res"]).status_code == 200


def test_admin_users_settings_audit(client, auth):
    assert client.get("/api/v1/admin/users", headers=auth["res"]).status_code == 403
    weak = client.post("/api/v1/admin/users", headers=auth["admin"], json={"email": "n@research-uni.org", "display_name": "N", "password": "aaaaaaaaaaaa"})
    assert weak.status_code == 422
    u = client.post(
        "/api/v1/admin/users",
        headers=auth["admin"],
        json={"email": "n@research-uni.org", "display_name": "N", "password": "Str0ng-Passw0rd", "role": "reviewer"},
    )
    assert u.status_code == 201 and u.json()["reviewer_code"].startswith("R-")
    me = client.get("/api/v1/auth/me", headers=auth["admin"]).json()
    assert client.patch(f"/api/v1/admin/users/{me['id']}", headers=auth["admin"], json={"role": "reviewer"}).status_code == 409
    s = client.put("/api/v1/admin/settings", headers=auth["admin"], json={"reviews_required": 3}).json()
    assert s["reviews_required"] == 3
    logs = client.get("/api/v1/admin/audit-logs?action=settings.update", headers=auth["admin"]).json()
    assert logs["total"] == 1
    assert client.get("/api/v1/admin/training-runs", headers=auth["admin"]).json()["items"] == []


def test_rate_limit(client, auth, monkeypatch):
    from healthmisinfo.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_analyze", 2)
    limiter.reset()
    codes = [client.post("/api/v1/analyze", json={"text": "Garlic cures influenza fast"}, headers=auth["res"]).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_public_mode_guest_access(client, users, monkeypatch):
    from healthmisinfo.config import get_settings

    assert client.get("/api/v1/auth/public-config").json() == {"public_mode": False}
    assert client.post("/api/v1/analyze", json={"text": "Garlic cures influenza in one day"}).status_code == 401
    monkeypatch.setattr(get_settings(), "public_mode", True)
    assert client.get("/api/v1/auth/public-config").json() == {"public_mode": True}
    # guests can use the public pages
    assert client.get("/api/v1/models").status_code == 200
    assert client.get("/api/v1/analytics").status_code == 200
    assert client.get("/api/v1/datasets").status_code == 200
    assert client.get("/api/v1/sources").status_code == 200
    r = client.post("/api/v1/analyze", json={"text": "Garlic cures influenza in one day"})
    assert r.status_code == 200 and r.json()["status"] == "model_not_trained"
    a_id = r.json()["id"]
    # ...but never see history (their own or other people's)
    assert client.get("/api/v1/history").json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert client.get(f"/api/v1/history/{a_id}").status_code == 401
    assert client.post(f"/api/v1/history/{a_id}/request-review").status_code == 401
    # ...and cannot review, import, split or administer
    assert client.get("/api/v1/reviews/pending").status_code == 401
    assert client.post("/api/v1/reviews", json={"target_type": "analysis", "target_id": a_id, "label": "MISLEADING"}).status_code == 401
    assert client.post("/api/v1/datasets/splits", json={"language": "ar", "version": "x"}).status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    # reports: only aggregate / non-personal ones
    assert set(client.get("/api/v1/reports").json()["types"]) == {"summary", "sources", "evaluation"}
    assert client.get("/api/v1/reports?type=summary&format=pdf").status_code == 200
    assert client.get("/api/v1/reports?type=analyses&format=csv").status_code == 401
    # signed-in users keep full access in public mode
    from .conftest import bearer

    h = bearer(client, "admin@test.local")
    assert client.get("/api/v1/history", headers=h).json()["total"] == 1
    assert client.get("/api/v1/admin/users", headers=h).status_code == 200
