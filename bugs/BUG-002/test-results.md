/Users/vobbilis/go/src/github.com/vobbilis/codegen/metrics-dashboard/backend/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:208: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
============================= test session starts ==============================
platform darwin -- Python 3.11.8, pytest-8.3.4, pluggy-1.6.0 -- /Users/vobbilis/go/src/github.com/vobbilis/codegen/metrics-dashboard/backend/.venv/bin/python3.11
cachedir: .pytest_cache
rootdir: /Users/vobbilis/go/src/github.com/vobbilis/codegen/metrics-dashboard/backend
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-0.24.0
asyncio: mode=Mode.AUTO, default_loop_scope=None
collecting ... collected 55 items

tests/test_alert_store.py::test_evaluate_no_metrics PASSED               [  1%]
tests/test_alert_store.py::test_evaluate_gt_operator PASSED              [  3%]
tests/test_alert_store.py::test_evaluate_lt_operator PASSED              [  5%]
tests/test_alert_store.py::test_evaluate_eq_operator PASSED              [  7%]
tests/test_alert_store.py::test_evaluate_multiple_rules PASSED           [  9%]
tests/test_alert_store.py::test_delete_rules_by_metric_name PASSED       [ 10%]
tests/test_alert_store.py::test_delete_rules_by_metric_name_existing PASSED [ 12%]
tests/test_alert_store.py::test_delete_rules_by_metric_name_nonexistent PASSED [ 14%]
tests/test_alert_store.py::test_delete_rules_by_metric_name_multiple PASSED [ 16%]
tests/test_api.py::test_health PASSED                                    [ 18%]
tests/test_api.py::test_submit_metric PASSED                             [ 20%]
tests/test_api.py::test_list_metrics PASSED                              [ 21%]
tests/test_api.py::test_get_metric_by_name PASSED                        [ 23%]
tests/test_api.py::test_get_metric_not_found PASSED                      [ 25%]
tests/test_api.py::test_delete_metric PASSED                             [ 27%]
tests/test_api.py::test_metric_with_tags PASSED                          [ 29%]
tests/test_api.py::test_summary_empty PASSED                             [ 30%]
tests/test_api.py::test_summary_with_metrics PASSED                      [ 32%]
tests/test_api.py::test_store_history PASSED                             [ 34%]
tests/test_api.py::test_get_metric_history PASSED                        [ 36%]
tests/test_api.py::test_route_ordering_history_vs_by_name PASSED         [ 38%]
tests/test_api.py::test_history_returns_submitted_metrics PASSED         [ 40%]
tests/test_api.py::test_history_limit_parameter PASSED                   [ 41%]
tests/test_api.py::test_history_not_found PASSED                         [ 43%]
tests/test_api.py::test_history_caps_at_20 PASSED                        [ 45%]
tests/test_api.py::test_history_cleared_by_delete PASSED                 [ 47%]
tests/test_api.py::test_history_default_limit_is_20 PASSED               [ 49%]
tests/test_api.py::test_history_does_not_mix_metric_names PASSED         [ 50%]
tests/test_api.py::test_list_alerts_empty PASSED                         [ 52%]
tests/test_api.py::test_list_alerts_with_rules PASSED                    [ 54%]
tests/test_api.py::test_delete_alert_existing PASSED                     [ 56%]
tests/test_api.py::test_delete_alert_nonexistent PASSED                  [ 58%]
tests/test_api.py::test_delete_alert_removes_from_list PASSED            [ 60%]
tests/test_api.py::test_lifespan_background_task PASSED                  [ 61%]
tests/test_api.py::test_create_alert_rule PASSED                         [ 63%]
tests/test_api.py::test_create_alert_rule_validation_error PASSED        [ 65%]
tests/test_api.py::test_create_alert_rule_invalid_operator PASSED        [ 67%]
tests/test_api.py::test_evaluate_gt_fires PASSED                         [ 69%]
tests/test_api.py::test_evaluate_gt_ok PASSED                            [ 70%]
tests/test_api.py::test_evaluate_lt_fires PASSED                         [ 72%]
tests/test_api.py::test_evaluate_eq_fires PASSED                         [ 74%]
tests/test_api.py::test_evaluate_no_metrics_stays_ok PASSED              [ 76%]
tests/test_api.py::test_evaluate_state_transition PASSED                 [ 78%]
tests/test_api.py::test_alert_rule_with_long_metric_name PASSED          [ 80%]
tests/test_api.py::test_alert_rule_empty_metric_name PASSED              [ 81%]
tests/test_api.py::test_multiple_rules_same_metric PASSED                [ 83%]
tests/test_api.py::test_delete_metric_does_not_affect_alert_rules PASSED [ 85%]
tests/test_api.py::test_existing_metrics_unaffected_by_alerts PASSED     [ 87%]
tests/test_api.py::test_metrics_export_csv_empty PASSED                  [ 89%]
tests/test_api.py::test_metrics_export_csv_with_data PASSED              [ 90%]
tests/test_api.py::test_metrics_export_unsupported_format PASSED         [ 92%]
tests/test_api.py::test_delete_metric_cascades_alert_deletion PASSED     [ 94%]
tests/test_models.py::test_alert_types_import PASSED                     [ 96%]
tests/test_models.py::test_alert_operator_literals PASSED                [ 98%]
tests/test_models.py::test_alert_state_literals PASSED                   [100%]

============================== 55 passed in 0.42s ==============================
