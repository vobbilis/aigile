import asyncio
import csv
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import alert_store, app, store


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    alert_store.clear()
    yield
    store.clear()
    alert_store.clear()


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


def test_summary_empty():
    r = client.get("/metrics/summary")
    assert r.status_code == 200
    assert r.json() == {"unique_names": 0, "total_data_points": 0}


def test_summary_with_metrics():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "cpu", "value": 20.0})
    client.post("/metrics", json={"name": "mem", "value": 75.0})
    r = client.get("/metrics/summary")
    assert r.status_code == 200
    assert r.json() == {"unique_names": 2, "total_data_points": 3}


def test_store_history():
    from main import store
    from models import MetricIn

    # Empty history for non-existent metric
    assert store.history("cpu") == []

    # Add 5 metrics and check history
    for i in range(5):
        store.add(MetricIn(name="cpu", value=float(i)))

    history = store.history("cpu")
    assert len(history) == 5
    assert history[0].value == 0.0  # oldest first
    assert history[-1].value == 4.0  # newest last

    # Test limit parameter
    history_limited = store.history("cpu", limit=2)
    assert len(history_limited) == 2
    assert history_limited[0].value == 3.0  # last 2 entries
    assert history_limited[1].value == 4.0

    # Add more metrics to test deque cap (20)
    for i in range(20):
        store.add(MetricIn(name="cpu", value=float(i + 5)))

    history_full = store.history("cpu")
    assert len(history_full) == 20  # deque cap
    assert history_full[0].value == 5.0  # oldest in deque
    assert history_full[-1].value == 24.0  # newest

    # Test limit clamping
    history_min = store.history("cpu", limit=0)  # should clamp to 1
    assert len(history_min) == 1
    assert history_min[0].value == 24.0  # most recent

    history_max = store.history("cpu", limit=100)  # should clamp to 20
    assert len(history_max) == 20


def test_get_metric_history():
    # Add some metrics
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "cpu", "value": 20.0})
    client.post("/metrics", json={"name": "cpu", "value": 30.0})

    # Test basic history retrieval
    r = client.get("/metrics/cpu/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["value"] == 10.0  # oldest first
    assert data[-1]["value"] == 30.0  # newest last

    # Test limit parameter
    r = client.get("/metrics/cpu/history?limit=2")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["value"] == 20.0  # last 2 entries
    assert data[1]["value"] == 30.0

    # Test 404 for nonexistent metric
    r = client.get("/metrics/nonexistent/history")
    assert r.status_code == 404
    assert r.json() == {"detail": "No history found for 'nonexistent'"}


def test_route_ordering_history_vs_by_name():
    # Add a metric
    client.post("/metrics", json={"name": "cpu", "value": 10.0})

    # Test that /metrics/cpu/history works
    r_history = client.get("/metrics/cpu/history")
    assert r_history.status_code == 200

    # Test that /metrics/cpu still works (by_name route)
    r_by_name = client.get("/metrics/cpu")
    assert r_by_name.status_code == 200

    # Test that /metrics/summary still works
    r_summary = client.get("/metrics/summary")
    assert r_summary.status_code == 200


def test_history_returns_submitted_metrics():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.post("/metrics", json={"name": "cpu", "value": 20.0})
    client.post("/metrics", json={"name": "cpu", "value": 30.0})
    r = client.get("/metrics/cpu/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["value"] == 10.0
    assert data[2]["value"] == 30.0


def test_history_limit_parameter():
    for i in range(10):
        client.post("/metrics", json={"name": "cpu", "value": float(i)})
    r = client.get("/metrics/cpu/history?limit=3")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[-1]["value"] == 9.0


def test_history_not_found():
    r = client.get("/metrics/nonexistent/history")
    assert r.status_code == 404
    assert "nonexistent" in r.json()["detail"]


def test_history_caps_at_20():
    for i in range(30):
        client.post("/metrics", json={"name": "cpu", "value": float(i)})
    r = client.get("/metrics/cpu/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 20
    assert data[0]["value"] == 10.0  # oldest kept (30 - 20 = 10)
    assert data[-1]["value"] == 29.0  # newest


def test_history_cleared_by_delete():
    client.post("/metrics", json={"name": "cpu", "value": 10.0})
    client.delete("/metrics/cpu")
    r = client.get("/metrics/cpu/history")
    assert r.status_code == 404


def test_history_default_limit_is_20():
    for i in range(25):
        client.post("/metrics", json={"name": "cpu", "value": float(i)})
    r = client.get("/metrics/cpu/history")
    data = r.json()
    assert len(data) == 20


def test_history_does_not_mix_metric_names():
    client.post("/metrics", json={"name": "cpu", "value": 1.0})
    client.post("/metrics", json={"name": "mem", "value": 2.0})
    client.post("/metrics", json={"name": "cpu", "value": 3.0})
    r = client.get("/metrics/cpu/history")
    data = r.json()
    assert len(data) == 2
    assert all(d["name"] == "cpu" for d in data)


def test_list_alerts_empty():
    """GET /alerts returns empty array when no alerts exist."""
    r = client.get("/alerts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_alerts_with_rules():
    """GET /alerts returns all alert rules."""
    # Create two alert rules
    r1 = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    r2 = client.post("/alerts", json={"metric_name": "mem", "operator": "lt", "threshold": 50.0})

    # GET should return both
    r = client.get("/alerts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    rule_ids = {rule["id"] for rule in data}
    assert r1.json()["id"] in rule_ids
    assert r2.json()["id"] in rule_ids


def test_delete_alert_existing():
    """DELETE /alerts/{rule_id} returns {"deleted": 1} when rule exists."""
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 90.0})
    rule_id = r.json()["id"]

    # DELETE should return deleted: 1
    dr = client.delete(f"/alerts/{rule_id}")
    assert dr.status_code == 200
    assert dr.json() == {"deleted": 1}

    # Rule should be gone
    r = client.get("/alerts")
    assert r.json() == []


def test_delete_alert_nonexistent():
    """DELETE /alerts/{rule_id} returns {"deleted": 0} when rule doesn't exist, no 404."""
    dr = client.delete("/alerts/nonexistent-id")
    assert dr.status_code == 200
    assert dr.json() == {"deleted": 0}


def test_delete_alert_removes_from_list():
    """After deleting a rule, GET /alerts no longer includes it."""
    # Create two rules
    r1 = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    r2 = client.post("/alerts", json={"metric_name": "mem", "operator": "lt", "threshold": 50.0})
    rule1_id = r1.json()["id"]
    rule2_id = r2.json()["id"]

    # Confirm both exist
    alerts = client.get("/alerts").json()
    assert len(alerts) == 2

    # Delete first rule
    dr = client.delete(f"/alerts/{rule1_id}")
    assert dr.json() == {"deleted": 1}

    # Only second rule should remain
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["id"] == rule2_id


@pytest.mark.asyncio
async def test_lifespan_background_task():
    """Test that the lifespan context manager creates and runs the evaluation background task."""
    # Import needed for lifespan testing
    from main import _evaluate_loop

    with (
        patch("main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("main.alert_store.evaluate") as mock_evaluate,
    ):
        # Make sleep return immediately on first call, then raise cancellation to stop loop
        async def sleep_side_effect(duration):
            if mock_sleep.call_count == 1:
                return None  # First call returns immediately
            else:
                raise asyncio.CancelledError()  # Second call cancels to stop loop

        mock_sleep.side_effect = sleep_side_effect

        # Test the background task function directly
        task = asyncio.create_task(_evaluate_loop())

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify that evaluate was called with correct parameters
        mock_evaluate.assert_called_once_with(store)
        assert mock_sleep.call_count >= 1


def test_create_alert_rule():
    """POST /alerts creates an alert rule and returns all required fields."""
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 90.0})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["metric_name"] == "cpu"
    assert data["operator"] == "gt"
    assert data["threshold"] == 90.0
    assert data["state"] == "ok"
    assert "created_at" in data


def test_create_alert_rule_validation_error():
    """POST /alerts with empty body returns 422 validation error."""
    r = client.post("/alerts", json={})
    assert r.status_code == 422


def test_create_alert_rule_invalid_operator():
    """POST /alerts with invalid operator returns 422 validation error."""
    r = client.post(
        "/alerts", json={"metric_name": "cpu", "operator": "invalid", "threshold": 90.0}
    )
    assert r.status_code == 422


def test_evaluate_gt_fires():
    """Test that a 'greater than' alert rule fires when metric value exceeds threshold."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # Submit metric via API
    r = client.post("/metrics", json={"name": "cpu", "value": 95.0})
    assert r.status_code == 201

    # Evaluate directly
    alert_store.evaluate(store)

    # Check state via API
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["state"] == "firing"


def test_evaluate_gt_ok():
    """Test that a 'greater than' alert rule stays ok when metric value is below threshold."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # Submit metric via API
    r = client.post("/metrics", json={"name": "cpu", "value": 50.0})
    assert r.status_code == 201

    # Evaluate directly
    alert_store.evaluate(store)

    # Check state via API
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["state"] == "ok"


def test_evaluate_lt_fires():
    """Test that a 'less than' alert rule fires when metric value is below threshold."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "mem", "operator": "lt", "threshold": 20.0})
    assert r.status_code == 201

    # Submit metric via API
    r = client.post("/metrics", json={"name": "mem", "value": 10.0})
    assert r.status_code == 201

    # Evaluate directly
    alert_store.evaluate(store)

    # Check state via API
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["state"] == "firing"


def test_evaluate_eq_fires():
    """Test that an 'equals' alert rule fires when metric value equals threshold."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "disk", "operator": "eq", "threshold": 100.0})
    assert r.status_code == 201

    # Submit metric via API
    r = client.post("/metrics", json={"name": "disk", "value": 100.0})
    assert r.status_code == 201

    # Evaluate directly
    alert_store.evaluate(store)

    # Check state via API
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["state"] == "firing"


def test_evaluate_no_metrics_stays_ok():
    """Test that alert rule stays ok when no matching metrics are submitted."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # Evaluate directly without submitting any metrics
    alert_store.evaluate(store)

    # Check state via API
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["state"] == "ok"


def test_evaluate_state_transition():
    """Test that alert rule transitions between ok and firing states correctly."""
    # Create rule via API
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # First submission: value above threshold should fire
    r = client.post("/metrics", json={"name": "cpu", "value": 95.0})
    assert r.status_code == 201
    alert_store.evaluate(store)
    alerts = client.get("/alerts").json()
    assert alerts[0]["state"] == "firing"

    # Second submission: value below threshold should go back to ok
    r = client.post("/metrics", json={"name": "cpu", "value": 50.0})
    assert r.status_code == 201
    alert_store.evaluate(store)
    alerts = client.get("/alerts").json()
    assert alerts[0]["state"] == "ok"

    # Third submission: value above threshold should fire again
    r = client.post("/metrics", json={"name": "cpu", "value": 99.0})
    assert r.status_code == 201
    alert_store.evaluate(store)
    alerts = client.get("/alerts").json()
    assert alerts[0]["state"] == "firing"


def test_alert_rule_with_long_metric_name():
    """Test metric name length validation: 128 chars OK, 129 chars fail."""
    # 128 characters should be accepted
    metric_name_128 = "a" * 128
    r = client.post(
        "/alerts", json={"metric_name": metric_name_128, "operator": "gt", "threshold": 1.0}
    )
    assert r.status_code == 201

    # 129 characters should fail
    metric_name_129 = "a" * 129
    r = client.post(
        "/alerts", json={"metric_name": metric_name_129, "operator": "gt", "threshold": 1.0}
    )
    assert r.status_code == 422


def test_alert_rule_empty_metric_name():
    """Test empty metric name validation should fail."""
    r = client.post("/alerts", json={"metric_name": "", "operator": "gt", "threshold": 1.0})
    assert r.status_code == 422


def test_multiple_rules_same_metric():
    """Test multiple alert rules for same metric work independently."""
    # Create two rules for "cpu": one gt 80, one lt 20
    r1 = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r1.status_code == 201

    r2 = client.post("/alerts", json={"metric_name": "cpu", "operator": "lt", "threshold": 20.0})
    assert r2.status_code == 201

    # Submit metric with value 95.0, evaluate
    r = client.post("/metrics", json={"name": "cpu", "value": 95.0})
    assert r.status_code == 201
    alert_store.evaluate(store)

    # Check alerts: gt 80 should be firing, lt 20 should be ok
    alerts = client.get("/alerts").json()
    assert len(alerts) == 2

    gt_rule = next(rule for rule in alerts if rule["operator"] == "gt")
    lt_rule = next(rule for rule in alerts if rule["operator"] == "lt")
    assert gt_rule["state"] == "firing"
    assert lt_rule["state"] == "ok"

    # Submit metric with value 10.0, evaluate
    r = client.post("/metrics", json={"name": "cpu", "value": 10.0})
    assert r.status_code == 201
    alert_store.evaluate(store)

    # Check alerts: gt 80 should be ok, lt 20 should be firing
    alerts = client.get("/alerts").json()
    gt_rule = next(rule for rule in alerts if rule["operator"] == "gt")
    lt_rule = next(rule for rule in alerts if rule["operator"] == "lt")
    assert gt_rule["state"] == "ok"
    assert lt_rule["state"] == "firing"


def test_delete_metric_does_not_affect_alert_rules():
    """Test deleting metrics doesn't remove alert rules."""
    # Create alert rule
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # Submit metric
    r = client.post("/metrics", json={"name": "cpu", "value": 95.0})
    assert r.status_code == 201

    # Delete metrics
    r = client.delete("/metrics/cpu")
    assert r.status_code == 200

    # Alert rule should still exist
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1

    # Evaluate - rule should revert to "ok" since no metrics exist
    alert_store.evaluate(store)
    alerts = client.get("/alerts").json()
    assert alerts[0]["state"] == "ok"


def test_existing_metrics_unaffected_by_alerts():
    """Test that existing metrics functionality is unaffected by alerts."""
    # Submit two metrics
    r1 = client.post("/metrics", json={"name": "cpu", "value": 42.5})
    assert r1.status_code == 201
    r2 = client.post("/metrics", json={"name": "mem", "value": 75.0})
    assert r2.status_code == 201

    # Create alert rule
    r = client.post("/alerts", json={"metric_name": "cpu", "operator": "gt", "threshold": 80.0})
    assert r.status_code == 201

    # Evaluate alerts
    alert_store.evaluate(store)

    # Verify all metrics functionality still works
    # GET /metrics returns 2 items
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert len(metrics.json()) == 2

    # GET /metrics/cpu returns cpu items
    cpu_metrics = client.get("/metrics/cpu")
    assert cpu_metrics.status_code == 200
    cpu_data = cpu_metrics.json()
    assert all(item["name"] == "cpu" for item in cpu_data)

    # GET /metrics/cpu/history returns 200
    history = client.get("/metrics/cpu/history")
    assert history.status_code == 200

    # DELETE /metrics/cpu returns {"deleted": 1}
    delete_result = client.delete("/metrics/cpu")
    assert delete_result.status_code == 200
    assert delete_result.json() == {"deleted": 1}

    # GET /health returns {"status": "ok"}
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_metrics_export_csv_empty():
    """Test CSV export with no metrics returns just headers."""
    r = client.get("/metrics/export?format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"] == 'attachment; filename="metrics.csv"'
    assert r.text == "id,name,value,tags,timestamp\r\n"


def test_metrics_export_csv_with_data():
    """Test CSV export with metrics returns headers plus data rows."""
    # Add a metric first
    metric_data = {"name": "cpu", "value": 75.5, "tags": {"host": "server1", "region": "us-west"}}
    post_r = client.post("/metrics", json=metric_data)
    assert post_r.status_code == 201
    created_metric = post_r.json()

    # Export to CSV
    r = client.get("/metrics/export?format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"] == 'attachment; filename="metrics.csv"'

    # Parse CSV using csv.reader
    csv_reader = csv.reader(io.StringIO(r.text))
    rows = list(csv_reader)

    # Verify header row
    assert len(rows) >= 2  # At least header + one data row
    header_row = rows[0]
    assert header_row == ["id", "name", "value", "tags", "timestamp"]
    assert len(header_row) == 5  # Exactly 5 columns in header

    # Verify data rows
    data_row = rows[1]
    assert len(data_row) == 5  # Exactly 5 columns in data row

    # Check data row contains expected values
    assert created_metric["id"] in data_row
    assert "cpu" in data_row
    assert "75.5" in data_row
    assert "host" in data_row[3] and "server1" in data_row[3]  # tags column
    assert "region" in data_row[3] and "us-west" in data_row[3]  # tags column
    # Check timestamp is present (timestamp format may differ between JSON API and CSV)
    assert "2026-03-01" in data_row[4]  # timestamp column


def test_metrics_export_unsupported_format():
    """Test CSV export with unsupported format returns 400 error."""
    r = client.get("/metrics/export?format=json")
    assert r.status_code == 400
    assert r.json() == {"detail": "Unsupported format. Use format=csv"}
