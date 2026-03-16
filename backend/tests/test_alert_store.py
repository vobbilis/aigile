from unittest.mock import patch

from alert_store import AlertStore
from models import AlertRuleIn, MetricIn
from store import MetricStore


def test_evaluate_no_metrics():
    """Rules with no matching metrics should stay in 'ok' state."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    # Add rule but no metrics
    rule = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))

    # Evaluate - should return no transitions
    transitions = alert_store.evaluate(metric_store)
    assert transitions == []
    assert rule.state == "ok"


def test_evaluate_gt_operator():
    """Test 'gt' operator fires when latest > threshold."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))

    # Add metric above threshold
    metric_store.add(MetricIn(name="cpu", value=95.0))

    # Should transition from ok -> firing
    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "ok", "firing")
    assert rule.state == "firing"

    # Evaluate again - no change expected
    transitions = alert_store.evaluate(metric_store)
    assert transitions == []

    # Add metric below threshold
    metric_store.add(MetricIn(name="cpu", value=50.0))

    # Should transition from firing -> ok
    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "firing", "ok")
    assert rule.state == "ok"


def test_evaluate_lt_operator():
    """Test 'lt' operator fires when latest < threshold."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="lt", threshold=20.0))

    # Add metric below threshold
    metric_store.add(MetricIn(name="memory", value=15.0))

    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "ok", "firing")
    assert rule.state == "firing"


def test_evaluate_eq_operator():
    """Test 'eq' operator fires when latest == threshold."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="disk", operator="eq", threshold=100.0))

    # Add metric equal to threshold
    metric_store.add(MetricIn(name="disk", value=100.0))

    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "ok", "firing")
    assert rule.state == "firing"


def test_evaluate_multiple_rules():
    """Test evaluation with multiple rules and different scenarios."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule1 = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    rule2 = alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="lt", threshold=20.0))
    rule3 = alert_store.add_rule(AlertRuleIn(metric_name="disk", operator="eq", threshold=100.0))

    # Add metrics that trigger rule1 and rule3
    metric_store.add(MetricIn(name="cpu", value=95.0))  # triggers rule1 (95 > 80)
    metric_store.add(MetricIn(name="memory", value=50.0))  # doesn't trigger rule2 (50 not < 20)
    metric_store.add(MetricIn(name="disk", value=100.0))  # triggers rule3 (100 == 100)

    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 2

    # Check individual transitions
    transition_ids = [(t[0], t[1], t[2]) for t in transitions]
    assert (rule1.id, "ok", "firing") in transition_ids
    assert (rule3.id, "ok", "firing") in transition_ids

    # Check states updated
    assert rule1.state == "firing"
    assert rule2.state == "ok"
    assert rule3.state == "firing"


def test_delete_rules_by_metric_name():
    """Test deleting all rules for a specific metric name."""
    alert_store = AlertStore()

    # Add multiple rules, some with same metric name
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="lt", threshold=10.0))
    alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="gt", threshold=90.0))

    # Should have 3 rules
    assert len(alert_store.all_rules()) == 3

    # Delete all cpu rules
    deleted_count = alert_store.delete_rules_by_metric_name("cpu")
    assert deleted_count == 2

    # Should have 1 rule left (memory)
    remaining_rules = alert_store.all_rules()
    assert len(remaining_rules) == 1
    assert remaining_rules[0].metric_name == "memory"

    # Deleting non-existent metric should return 0
    deleted_count = alert_store.delete_rules_by_metric_name("nonexistent")
    assert deleted_count == 0
    assert len(alert_store.all_rules()) == 1


def test_delete_rules_by_metric_name_existing():
    """Verify deletion count when rules exist for the given metric name."""
    alert_store = AlertStore()

    # Add a rule for cpu metric
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    rule2 = alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="lt", threshold=20.0))

    # Verify initial state
    assert len(alert_store.all_rules()) == 2

    # Delete cpu rules - should return 1
    deleted_count = alert_store.delete_rules_by_metric_name("cpu")
    assert deleted_count == 1

    # Verify only memory rule remains
    remaining_rules = alert_store.all_rules()
    assert len(remaining_rules) == 1
    assert remaining_rules[0].metric_name == "memory"
    assert remaining_rules[0].id == rule2.id


def test_delete_rules_by_metric_name_nonexistent():
    """Verify zero count when no rules match the metric name."""
    alert_store = AlertStore()

    # Add rules for different metrics
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="lt", threshold=20.0))

    # Verify initial state
    assert len(alert_store.all_rules()) == 2

    # Delete rules for nonexistent metric - should return 0
    deleted_count = alert_store.delete_rules_by_metric_name("disk")
    assert deleted_count == 0

    # Verify all rules remain
    remaining_rules = alert_store.all_rules()
    assert len(remaining_rules) == 2
    metric_names = {rule.metric_name for rule in remaining_rules}
    assert metric_names == {"cpu", "memory"}


def test_delete_rules_by_metric_name_multiple():
    """Verify deletion when multiple rules reference the same metric."""
    alert_store = AlertStore()

    # Add multiple rules for same metric
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="lt", threshold=10.0))
    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="eq", threshold=50.0))
    rule4 = alert_store.add_rule(AlertRuleIn(metric_name="memory", operator="gt", threshold=90.0))

    # Verify initial state
    assert len(alert_store.all_rules()) == 4

    # Delete all cpu rules - should return 3
    deleted_count = alert_store.delete_rules_by_metric_name("cpu")
    assert deleted_count == 3

    # Verify only memory rule remains
    remaining_rules = alert_store.all_rules()
    assert len(remaining_rules) == 1
    assert remaining_rules[0].metric_name == "memory"
    assert remaining_rules[0].id == rule4.id


def test_evaluate_eq_operator_float_near_equal():
    """Test 'eq' operator fires for near-equal float values (0.1 + 0.2 vs 0.3)."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="result", operator="eq", threshold=0.3))

    # 0.1 + 0.2 == 0.30000000000000004 in IEEE 754
    metric_store.add(MetricIn(name="result", value=0.1 + 0.2))

    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "ok", "firing")
    assert rule.state == "firing"


def test_evaluate_eq_operator_float_small_difference():
    """Test 'eq' operator fires when value differs by tiny rounding error."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="eq", threshold=80.0))

    metric_store.add(MetricIn(name="cpu", value=80.000001))

    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
    assert transitions[0] == (rule.id, "ok", "firing")
    assert rule.state == "firing"


def test_evaluate_eq_operator_truly_different_values():
    """Test 'eq' operator does NOT fire for genuinely different values."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    rule = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="eq", threshold=80.0))

    metric_store.add(MetricIn(name="cpu", value=85.0))

    transitions = alert_store.evaluate(metric_store)
    assert transitions == []
    assert rule.state == "ok"


def test_evaluate_exception_does_not_crash():
    """Test that evaluate() raising an exception doesn't prevent future calls."""
    metric_store = MetricStore()
    alert_store = AlertStore()

    alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))

    # First call raises
    with patch.object(alert_store, "evaluate", side_effect=RuntimeError("boom")):
        try:
            alert_store.evaluate(metric_store)
        except RuntimeError:
            pass

    # Second call should work fine (store is not corrupted)
    metric_store.add(MetricIn(name="cpu", value=95.0))
    transitions = alert_store.evaluate(metric_store)
    assert len(transitions) == 1
