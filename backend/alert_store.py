import math
import uuid

from models import AlertRuleIn, AlertRuleOut
from store import MetricStore


class AlertStore:
    def __init__(self) -> None:
        self._rules: list[AlertRuleOut] = []

    def add_rule(self, rule: AlertRuleIn) -> AlertRuleOut:
        out = AlertRuleOut(
            id=str(uuid.uuid4()),
            metric_name=rule.metric_name,
            operator=rule.operator,
            threshold=rule.threshold,
            state="ok",
        )
        self._rules.append(out)
        return out

    def all_rules(self) -> list[AlertRuleOut]:
        return list(self._rules)

    def delete_rule(self, rule_id: str) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.id != rule_id]
        return before - len(self._rules)

    def delete_rules_by_metric_name(self, metric_name: str) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.metric_name != metric_name]
        return before - len(self._rules)

    def clear(self) -> None:
        self._rules = []

    def evaluate(self, metric_store: MetricStore) -> list[tuple[str, str, str]]:
        """Evaluate all rules against latest metric values. Returns state transitions."""
        transitions: list[tuple[str, str, str]] = []

        for rule in self._rules:
            # Get metrics for this rule's metric name
            metrics = metric_store.by_name(rule.metric_name)

            if not metrics:
                # No data → not firing
                new_state = "ok"
            else:
                # Get latest value and compare with threshold
                latest = metrics[-1].value

                if rule.operator == "gt":
                    new_state = "firing" if latest > rule.threshold else "ok"
                elif rule.operator == "lt":
                    new_state = "firing" if latest < rule.threshold else "ok"
                elif rule.operator == "eq":
                    new_state = "firing" if math.isclose(latest, rule.threshold, rel_tol=1e-6) else "ok"
                else:
                    new_state = "ok"  # Unknown operator, default to ok

            # Check for state transition
            if new_state != rule.state:
                transitions.append((rule.id, rule.state, new_state))
                rule.state = new_state

        return transitions
