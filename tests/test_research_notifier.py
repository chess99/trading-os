from __future__ import annotations

from typing import Any


class FlakyNotifier:
    destination = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        from trading_os.research.notifier import _delivery_result

        self.calls += 1
        return _delivery_result(
            alert,
            destination=self.destination,
            success=self.calls >= 3,
            message=f"attempt {self.calls}",
            attempt=self.calls,
        )


def test_deliver_alerts_retries_until_success_and_records_final_attempt():
    from trading_os.research.notifier import deliver_alerts

    alert = {
        "alert_id": "alert-1",
        "symbol": "SSE:600000",
        "as_of": "2026-06-12",
    }
    notifier = FlakyNotifier()

    deliveries = deliver_alerts([alert], notifier, max_attempts=3)

    assert notifier.calls == 3
    assert deliveries == [
        {
            "alert_id": "alert-1",
            "symbol": "SSE:600000",
            "as_of": "2026-06-12",
            "destination": "flaky",
            "success": True,
            "message": "attempt 3",
            "attempt": 3,
            "attempts": 3,
            "sent_at": deliveries[0]["sent_at"],
        }
    ]
