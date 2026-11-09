from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert 2025 in body["years"]


def test_summary():
    response = client.get("/api/v1/analysis/summary", params={"year": 2025})
    assert response.status_code == 200
    body = response.json()
    assert body["participants"] > 0
    assert "MT" in body["means"]


def test_percentile_endpoint():
    response = client.post(
        "/api/v1/analysis/percentile",
        json={"year": 2025, "scores": {"MT": 700, "LC": 620}},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert all(0 <= item["percentile"] <= 100 for item in body["results"])


def test_invalid_score_is_rejected():
    response = client.post(
        "/api/v1/analysis/percentile",
        json={"year": 2025, "scores": {"MT": 1200}},
    )
    assert response.status_code == 422


def test_socioeconomic_endpoint():
    response = client.get(
        "/api/v1/analysis/socioeconomic",
        params={"year": 2025, "area": "MT", "dimension": "renda"},
    )
    assert response.status_code == 200
    assert len(response.json()["groups"]) > 0


def test_region_school_endpoint():
    response = client.get(
        "/api/v1/analysis/region-school",
        params={"year": 2025, "area": "MT"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["states"]) == 27
    assert {item["uf"] for item in body["states"]}.__len__() == 27
    assert body["school_types"]


def test_region_school_accepts_school_type_filter():
    response = client.get(
        "/api/v1/analysis/region-school",
        params={"year": 2025, "area": "MT", "school_type": 2},
    )
    assert response.status_code == 200
    assert len(response.json()["states"]) == 27


def test_essay_endpoint():
    response = client.post("/api/v1/analysis/essay", json={"year": 2025, "score": 800})
    assert response.status_code == 200
    assert 0 <= response.json()["percentile"] <= 100
