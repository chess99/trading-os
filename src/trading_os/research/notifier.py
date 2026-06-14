from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib import request


class Notifier(Protocol):
    destination: str

    def send(self, alert: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StdoutNotifier:
    destination: str = "stdout"

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        return _delivery_result(
            alert,
            destination=self.destination,
            success=True,
            message="alert accepted for local stdout delivery",
        )


@dataclass(frozen=True, slots=True)
class WebhookNotifier:
    url: str
    destination: str = "webhook"
    timeout_seconds: float = 5.0

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(_webhook_payload(alert), ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read(500).decode("utf-8", errors="replace")
            return _delivery_result(
                alert,
                destination=self.destination,
                success=True,
                message=f"webhook status={response.status} body={body}",
            )
        except Exception as exc:
            return _delivery_result(
                alert,
                destination=self.destination,
                success=False,
                message=str(exc),
            )


@dataclass(frozen=True, slots=True)
class TelegramNotifier:
    bot_token: str
    chat_id: str
    destination: str = "telegram"
    timeout_seconds: float = 5.0

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": _webhook_payload(alert)["text"],
                "disable_web_page_preview": True,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read(500).decode("utf-8", errors="replace")
            return _delivery_result(
                alert,
                destination=self.destination,
                success=True,
                message=f"telegram status={response.status} body={body}",
            )
        except Exception as exc:
            return _delivery_result(
                alert,
                destination=self.destination,
                success=False,
                message=str(exc),
            )


@dataclass(frozen=True, slots=True)
class SystemNotifier:
    destination: str = "system"
    command_runner: Callable[[list[str]], int] = subprocess.call

    def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        payload = _webhook_payload(alert)
        command = [
            "osascript",
            "-e",
            (
                'display notification '
                f'{json.dumps(payload["text"], ensure_ascii=False)} '
                'with title '
                f'{json.dumps(payload["title"], ensure_ascii=False)}'
            ),
        ]
        try:
            exit_code = self.command_runner(command)
        except Exception as exc:
            return _delivery_result(
                alert,
                destination=self.destination,
                success=False,
                message=str(exc),
            )
        return _delivery_result(
            alert,
            destination=self.destination,
            success=exit_code == 0,
            message=f"system notification exit_code={exit_code}",
        )


def build_notifier(
    mode: str,
    *,
    webhook_url: str | None = None,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
) -> Notifier | None:
    if mode == "none":
        return None
    if mode == "stdout":
        return StdoutNotifier()
    if mode in {"webhook", "feishu", "dingtalk"}:
        env_name = {
            "webhook": "TRADING_OS_ALERT_WEBHOOK_URL",
            "feishu": "TRADING_OS_FEISHU_WEBHOOK_URL",
            "dingtalk": "TRADING_OS_DINGTALK_WEBHOOK_URL",
        }[mode]
        url = webhook_url or os.environ.get(env_name)
        if not url:
            raise RuntimeError(f"--webhook-url or {env_name} is required")
        return WebhookNotifier(url=url, destination=mode)
    if mode == "telegram":
        token = telegram_bot_token or os.environ.get("TRADING_OS_TELEGRAM_BOT_TOKEN")
        chat_id = telegram_chat_id or os.environ.get("TRADING_OS_TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError(
                "--telegram-bot-token/--telegram-chat-id or TRADING_OS_TELEGRAM_* is required"
            )
        return TelegramNotifier(bot_token=token, chat_id=chat_id)
    if mode == "system":
        return SystemNotifier()
    raise RuntimeError(f"unknown notify mode: {mode}")


def deliver_alerts(
    alerts: list[dict[str, Any]],
    notifier: Notifier | None,
    *,
    max_attempts: int = 1,
) -> list[dict[str, Any]]:
    if notifier is None:
        return []
    return _deliver_with_retries(alerts, notifier, max_attempts=max_attempts)


def _deliver_with_retries(
    alerts: list[dict[str, Any]],
    notifier: Notifier,
    *,
    max_attempts: int,
) -> list[dict[str, Any]]:
    attempts = max(1, max_attempts)
    deliveries: list[dict[str, Any]] = []
    for alert in alerts:
        final_result: dict[str, Any] | None = None
        for attempt in range(1, attempts + 1):
            try:
                final_result = notifier.send(alert)
            except Exception as exc:
                final_result = _delivery_result(
                    alert,
                    destination=getattr(notifier, "destination", notifier.__class__.__name__),
                    success=False,
                    message=str(exc),
                    attempt=attempt,
                )
            final_result["attempt"] = int(final_result.get("attempt") or attempt)
            final_result["attempts"] = attempt
            if final_result.get("success"):
                break
        if final_result is not None:
            deliveries.append(final_result)
    return deliveries


def _delivery_result(
    alert: dict[str, Any],
    *,
    destination: str,
    success: bool,
    message: str,
    attempt: int | None = None,
) -> dict[str, Any]:
    result = {
        "alert_id": alert.get("alert_id"),
        "symbol": alert.get("symbol"),
        "as_of": alert.get("as_of"),
        "destination": destination,
        "success": success,
        "message": message,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    if attempt is not None:
        result["attempt"] = attempt
    return result


def _webhook_payload(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"Trading OS Alert: {alert.get('symbol')}",
        "text": (
            f"{alert.get('symbol')} {alert.get('trigger_type')} "
            f"trigger={alert.get('trigger_value')} pivot={alert.get('pivot_price')}"
        ),
        "alert": alert,
    }
