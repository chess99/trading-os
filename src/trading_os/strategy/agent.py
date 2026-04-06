"""AgentStrategy — Claude API native integration.

Design:
- One API call per trading day (not per bar, not per symbol).
- Batch analysis: all symbols analyzed in a single prompt.
- Pydantic strict output validation.
- On parse failure: emit HOLD for all symbols, log WARNING.
- After 3 consecutive failures: raise StrategyError (halt strategy).
- confirm_mode='confirm': show analysis, wait for user approval.
- confirm_mode='auto': execute without confirmation (--bypass-confirm).

The strategy context passed to Claude:
    - Last N days of OHLCV for each symbol (formatted as a table)
    - Technical indicators computed locally (MA, RSI, volume ratio)
    - Trading date and task description

Output schema (Pydantic):
    List[AgentSignal] where AgentSignal has:
        symbol, action, size, reason, confidence
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Literal

from .base import Signal, Strategy, StrategyContext

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, Field, field_validator

    class AgentSignalSchema(BaseModel):
        symbol: str = Field(description="Canonical symbol id, e.g. SSE:600000")
        action: Literal["BUY", "SELL", "HOLD"] = Field(description="Trading action")
        size: float = Field(ge=0.0, le=1.0, description="Target portfolio allocation (0-1)")
        reason: str = Field(description="Brief reason for the signal")
        confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Confidence level")

        @field_validator("action")
        @classmethod
        def validate_action(cls, v: str) -> str:
            v = v.upper()
            if v not in ("BUY", "SELL", "HOLD"):
                raise ValueError(f"action must be BUY/SELL/HOLD, got {v!r}")
            return v

    class AgentOutputSchema(BaseModel):
        signals: list[AgentSignalSchema]
        market_summary: str = Field(default="", description="Brief market analysis")
        risk_notes: str = Field(default="", description="Risk observations")

    _PYDANTIC_AVAILABLE = True

except ImportError:
    _PYDANTIC_AVAILABLE = False
    AgentSignalSchema = None  # type: ignore
    AgentOutputSchema = None  # type: ignore


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_market_context(
    bars: "pd.DataFrame",
    symbols: list[str],
    trading_date: date,
    lookback_display: int = 20,
) -> str:
    """Build a text summary of recent market data for each symbol."""
    from ..data.schema import BarColumns

    lines = [
        f"Trading Date: {trading_date.isoformat()}",
        f"Symbols: {', '.join(symbols)}",
        "",
        "Recent Market Data (last 20 trading days, 前复权 adjusted):",
        "",
    ]

    for sym in symbols:
        sym_bars = bars[bars[BarColumns.symbol] == sym].sort_values(BarColumns.ts)
        if sym_bars.empty:
            lines.append(f"[{sym}] No data available")
            continue

        recent = sym_bars.tail(lookback_display)
        close = recent[BarColumns.close].astype(float)
        volume = recent[BarColumns.volume].astype(float)

        # Compute basic indicators
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else float("nan")
        last_close = close.iloc[-1]
        prev_close = close.iloc[-2] if len(close) >= 2 else last_close
        pct_change = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0

        vol_avg = volume.rolling(5).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        vol_ratio = last_vol / vol_avg if vol_avg > 0 else 1.0

        # RSI(14)
        rsi_val = float("nan")
        if len(close) >= 15:
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 0 else float("inf")
            rsi_val = 100 - 100 / (1 + rs)

        lines.append(f"[{sym}]")
        lines.append(f"  Last Close:  {last_close:.2f}  ({pct_change:+.2f}%)")
        lines.append(f"  MA5:         {ma5:.2f}  MA20: {ma20:.2f if ma20 == ma20 else 'N/A'}")
        lines.append(f"  RSI(14):     {rsi_val:.1f}" if rsi_val == rsi_val else "  RSI(14):     N/A")
        lines.append(f"  Volume Ratio (vs 5d avg): {vol_ratio:.2f}x")

        # Last 5 bars table
        lines.append("  Date         Open    High    Low     Close   Volume")
        for _, row in recent.tail(5).iterrows():
            ts = row[BarColumns.ts]
            d = ts.date() if hasattr(ts, "date") else str(ts)[:10]
            lines.append(
                f"  {d}  {row[BarColumns.open]:7.2f} {row[BarColumns.high]:7.2f} "
                f"{row[BarColumns.low]:7.2f} {row[BarColumns.close]:7.2f} "
                f"{row[BarColumns.volume]:10.0f}"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AgentStrategy
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a professional quantitative analyst for A-share (China mainland) stocks.

Your task: analyze the provided market data and generate trading signals.

Rules:
1. Only use the data provided. Do NOT use any information beyond what is given.
2. A-share market rules: T+1 settlement (shares bought today cannot be sold today).
3. Be conservative. When uncertain, output HOLD.
4. size represents target portfolio allocation (0.0–1.0). Max single position: 0.10 (10%).
5. Output ONLY valid JSON matching the schema. No markdown, no explanation outside JSON.

Output schema (JSON):
{
  "signals": [
    {
      "symbol": "SSE:600000",
      "action": "BUY" | "SELL" | "HOLD",
      "size": 0.08,
      "reason": "MA5 crossed above MA20 with volume confirmation",
      "confidence": 0.75
    }
  ],
  "market_summary": "Brief overall market assessment",
  "risk_notes": "Any risk observations"
}
"""


@dataclass
class AgentConfig:
    model: str = "claude-opus-4-6"
    max_tokens: int = 2048
    confirm_mode: Literal["confirm", "auto"] = "confirm"
    lookback_display: int = 20   # bars to show in context
    max_consecutive_failures: int = 3
    cache_dir: str | None = None  # cache API responses to disk (by date)


class AgentStrategy(Strategy):
    """Strategy driven by Claude API analysis.

    Usage::

        strategy = AgentStrategy(AgentConfig(confirm_mode="auto"))
        runner = BacktestRunner(strategy=strategy, pipeline=pipeline)
        result = runner.run(symbols=["SSE:600000"], start=..., end=...)

    For backtest over long periods, responses are cached by (symbols, date)
    to avoid redundant API calls.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()
        self._consecutive_failures = 0
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "AgentStrategy requires anthropic SDK: pip install anthropic"
            ) from e
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def generate_signals(
        self,
        bars: "pd.DataFrame",
        trading_date: date,
    ) -> dict[str, Signal]:
        from ..data.schema import BarColumns

        symbols = sorted(bars[BarColumns.symbol].unique().tolist())
        if not symbols:
            return {}

        # Check cache
        cached = self._load_cache(symbols, trading_date)
        if cached is not None:
            return cached

        # Build context
        context = _build_market_context(bars, symbols, trading_date, self.config.lookback_display)

        user_prompt = (
            f"Analyze the following A-share market data and generate trading signals "
            f"for {trading_date.isoformat()}.\n\n{context}\n\n"
            f"Generate signals for all {len(symbols)} symbols."
        )

        # Call Claude API
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = response.content[0].text
        except Exception as e:
            log.error("Claude API call failed on %s: %s", trading_date, e)
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.config.max_consecutive_failures:
                raise RuntimeError(
                    f"AgentStrategy: {self._consecutive_failures} consecutive API failures, halting"
                ) from e
            log.warning("Emitting HOLD for all symbols due to API failure")
            return {sym: Signal(sym, "HOLD", reason="API failure") for sym in symbols}

        # Parse output
        signals = self._parse_output(raw_text, symbols, trading_date)

        # Confirm mode
        if self.config.confirm_mode == "confirm":
            non_hold = {s: sig for s, sig in signals.items() if sig.action != "HOLD"}
            if non_hold:
                self._print_analysis(raw_text, non_hold, trading_date)
                approved = self._prompt_confirm()
                if not approved:
                    log.info("User rejected agent signals for %s", trading_date)
                    return {sym: Signal(sym, "HOLD", reason="User rejected") for sym in symbols}

        # Save cache
        self._save_cache(symbols, trading_date, signals)
        self._consecutive_failures = 0
        return signals

    def _parse_output(
        self,
        raw_text: str,
        symbols: list[str],
        trading_date: date,
    ) -> dict[str, Signal]:
        """Parse Claude's JSON output with Pydantic validation."""
        # Extract JSON (Claude sometimes wraps in markdown)
        text = raw_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse JSON on %s: %s\nRaw: %s", trading_date, e, raw_text[:500])
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.config.max_consecutive_failures:
                raise RuntimeError(
                    f"AgentStrategy: {self._consecutive_failures} consecutive parse failures, halting"
                ) from e
            return {sym: Signal(sym, "HOLD", reason="Parse failure") for sym in symbols}

        if _PYDANTIC_AVAILABLE:
            try:
                output = AgentOutputSchema(**data)
                signals = {}
                for s in output.signals:
                    if s.symbol in symbols:
                        signals[s.symbol] = Signal(
                            symbol=s.symbol,
                            action=s.action,
                            size=s.size,
                            reason=s.reason,
                            confidence=s.confidence,
                        )
                # Fill missing symbols with HOLD
                for sym in symbols:
                    if sym not in signals:
                        signals[sym] = Signal(sym, "HOLD", reason="Not in agent output")
                self._consecutive_failures = 0
                return signals
            except Exception as e:
                log.error("Pydantic validation failed on %s: %s", trading_date, e)
                self._consecutive_failures += 1
                return {sym: Signal(sym, "HOLD", reason="Validation failure") for sym in symbols}
        else:
            # Fallback: manual parsing
            signals = {}
            for item in data.get("signals", []):
                sym = item.get("symbol", "")
                if sym not in symbols:
                    continue
                try:
                    signals[sym] = Signal(
                        symbol=sym,
                        action=item.get("action", "HOLD"),
                        size=float(item.get("size", 0.0)),
                        reason=item.get("reason", ""),
                        confidence=float(item.get("confidence", 0.8)),
                    )
                except (ValueError, KeyError) as e:
                    log.warning("Could not parse signal for %s: %s", sym, e)
                    signals[sym] = Signal(sym, "HOLD", reason="Parse error")
            for sym in symbols:
                if sym not in signals:
                    signals[sym] = Signal(sym, "HOLD", reason="Not in agent output")
            return signals

    def _cache_key(self, symbols: list[str], trading_date: date) -> str:
        sym_hash = "_".join(sorted(symbols)).replace(":", "-")
        return f"{trading_date.isoformat()}_{sym_hash[:50]}"

    def _cache_path(self, key: str) -> "Path | None":
        if self.config.cache_dir is None:
            return None
        from pathlib import Path
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{key}.json"

    def _load_cache(self, symbols: list[str], trading_date: date) -> dict[str, Signal] | None:
        path = self._cache_path(self._cache_key(symbols, trading_date))
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return {
                sym: Signal(
                    symbol=sym,
                    action=item["action"],
                    size=item["size"],
                    reason=item["reason"] + " [cached]",
                    confidence=item.get("confidence", 0.8),
                )
                for sym, item in data.items()
            }
        except Exception:
            return None

    def _save_cache(
        self, symbols: list[str], trading_date: date, signals: dict[str, Signal]
    ) -> None:
        path = self._cache_path(self._cache_key(symbols, trading_date))
        if path is None:
            return
        try:
            data = {
                sym: {"action": sig.action, "size": sig.size, "reason": sig.reason, "confidence": sig.confidence}
                for sym, sig in signals.items()
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            log.warning("Failed to save cache: %s", e)

    def _print_analysis(
        self, raw_text: str, signals: dict[str, Signal], trading_date: date
    ) -> None:
        print(f"\n{'='*60}")
        print(f"  Agent Analysis — {trading_date}")
        print(f"{'='*60}")
        # Show market summary if available
        try:
            data = json.loads(raw_text)
            if data.get("market_summary"):
                print(f"  Market: {data['market_summary']}")
            if data.get("risk_notes"):
                print(f"  Risk:   {data['risk_notes']}")
        except Exception:
            pass
        print()
        for sym, sig in sorted(signals.items()):
            print(f"  {sig.action:4s}  {sym:20s}  size={sig.size:.1%}  conf={sig.confidence:.0%}")
            print(f"       {sig.reason}")
        print(f"{'='*60}")

    def _prompt_confirm(self) -> bool:
        try:
            ans = input("Execute agent signals? [y/N] ").strip().lower()
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
