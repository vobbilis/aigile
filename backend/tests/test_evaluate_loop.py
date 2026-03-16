import asyncio
from unittest.mock import patch

import pytest

from main import _evaluate_loop


async def _fake_sleep_factory(call_count_ref):
    """Create a fake sleep that cancels after 3 calls."""
    async def _fake_sleep(seconds):
        call_count_ref[0] += 1
        if call_count_ref[0] >= 3:
            raise asyncio.CancelledError
    return _fake_sleep


@pytest.mark.asyncio
async def test_evaluate_loop_recovers_from_exception():
    """_evaluate_loop should catch exceptions and continue iterating."""
    eval_count = 0
    sleep_count = [0]

    def mock_evaluate(metric_store):
        nonlocal eval_count
        eval_count += 1
        if eval_count == 1:
            raise RuntimeError("Simulated crash")
        # Second call succeeds

    async def fake_sleep(seconds):
        sleep_count[0] += 1
        if sleep_count[0] >= 3:
            raise asyncio.CancelledError

    with patch("main.alert_store") as mock_alert_store, \
         patch("main.store"), \
         patch("main.asyncio.sleep", side_effect=fake_sleep):
        mock_alert_store.evaluate = mock_evaluate

        with pytest.raises(asyncio.CancelledError):
            await _evaluate_loop()

    # evaluate was called twice: first raised (caught), second succeeded, third sleep cancelled
    assert eval_count == 2
