import pytest
from fastapi.testclient import TestClient

from main import app, store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_submit_metric():
    r = client.post("/metrics", json={"name": "cpu", "value": 42.5})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "cpu"
    assert data["value"] == 42.5
    assert "id" in data
    assert "timestamp" in data


def test_list_metrics():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "mem", "value": 75.0})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_metric_by_name():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "cpu", "value": 20.0})
    r = client.get("/metrics/cpu")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_metric_not_found():
    r = client.get("/metrics/nonexistent")
    assert r.status_code == 404


def test_delete_metric():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "cpu", "value": 20.0})
    r = client.delete("/metrics/cpu")
    assert r.status_code == 200
    assert r.json() == {"deleted": 2}
    assert client.get("/metrics/cpu").status_code == 404


def test_metric_with_tags():
    r = client.post(
        "/metrics",
        json={"name": "latency", "value": 120.5, "tags": {"env": "prod", "region": "us-east"}},
    )
    assert r.status_code == 201
    assert r.json()["tags"] == {"env": "prod", "region": "us-east"}
