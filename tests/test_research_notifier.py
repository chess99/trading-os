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


def test_build_notifier_supports_named_webhook_channels():
    from trading_os.research.notifier import build_notifier

    feishu = build_notifier("feishu", webhook_url="https://example.test/feishu")
    dingtalk = build_notifier("dingtalk", webhook_url="https://example.test/dingtalk")

    assert feishu is not None
    assert dingtalk is not None
    assert feishu.destination == "feishu"
    assert dingtalk.destination == "dingtalk"


def test_build_notifier_supports_telegram():
    from trading_os.research.notifier import build_notifier

    notifier = build_notifier(
        "telegram",
        telegram_bot_token="token",
        telegram_chat_id="chat-1",
    )

    assert notifier is not None
    assert notifier.destination == "telegram"


def test_system_notifier_uses_command_runner():
    from trading_os.research.notifier import SystemNotifier

    calls = []

    def fake_runner(command):
        calls.append(command)
        return 0

    notifier = SystemNotifier(command_runner=fake_runner)
    result = notifier.send(
        {
            "alert_id": "alert-1",
            "symbol": "SSE:600000",
            "as_of": "2026-06-12",
            "trigger_type": "pivot",
        }
    )

    assert result["success"] is True
    assert result["destination"] == "system"
    assert calls
