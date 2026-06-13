from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MissingCapabilityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_name: str
    data: Any
    failures: list[dict[str, Any]] = field(default_factory=list)


class ProviderRouter:
    def __init__(self, providers: list[Any]) -> None:
        self.providers = providers

    def fetch(self, capability: str, method_name: str, *args: Any, **kwargs: Any) -> ProviderResult:
        candidates = [
            provider
            for provider in self.providers
            if capability in set(getattr(provider, "capabilities", set()))
        ]
        if not candidates:
            raise MissingCapabilityError(f"no provider available for capability={capability}")

        failures: list[dict[str, Any]] = []
        for provider in candidates:
            provider_name = _provider_name(provider)
            try:
                method = getattr(provider, method_name)
                data = method(*args, **kwargs)
            except Exception as exc:
                failures.append(
                    {
                        "provider": provider_name,
                        "capability": capability,
                        "method": method_name,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )
                continue
            return ProviderResult(provider_name=provider_name, data=data, failures=failures)

        raise RuntimeError(f"all providers failed for capability={capability}: {failures}")


def _provider_name(provider: Any) -> str:
    return str(getattr(provider, "name", provider.__class__.__name__))
