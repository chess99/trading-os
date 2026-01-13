from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    symbol: str
    start_ts: str | None
    end_ts: str | None
    start_equity: float | None
    end_equity: float | None
    total_return: float | None
    max_drawdown: float | None
    fills: int
    risk_halts: int
    events_path: Path


def _parse_iso(ts: str) -> datetime:
    # handles "2020-01-01T00:00:00+00:00"
    return datetime.fromisoformat(ts)


def summarize_paper_events(events_path: Path) -> ReviewSummary:
    decision_symbol: str | None = None
    start_ts: str | None = None
    end_ts: str | None = None
    equities: list[float] = []

    fills = 0
    risk_halts = 0

    with events_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev: dict[str, Any] = json.loads(line)
            kind = ev.get("kind")
            payload = ev.get("payload", {})

            if kind == "decision":
                decision_symbol = str(payload.get("symbol") or decision_symbol or "")
            elif kind == "order_filled":
                fills += 1
            elif kind == "risk_halt":
                risk_halts += 1
            elif kind == "portfolio":
                ts = payload.get("ts") or ev.get("ts")
                eq = payload.get("equity")
                if ts is None or eq is None:
                    continue
                ts = str(ts)
                if start_ts is None:
                    start_ts = ts
                end_ts = ts
                try:
                    equities.append(float(eq))
                except Exception:
                    continue

    symbol = decision_symbol or "UNKNOWN"

    start_equity = equities[0] if equities else None
    end_equity = equities[-1] if equities else None

    total_return = None
    if start_equity and end_equity and start_equity > 0:
        total_return = (end_equity / start_equity) - 1.0

    max_drawdown = None
    if equities:
        peak = equities[0]
        mdd = 0.0
        for x in equities:
            if x > peak:
                peak = x
            dd = (x / peak) - 1.0
            if dd < mdd:
                mdd = dd
        max_drawdown = float(mdd)

    return ReviewSummary(
        symbol=symbol,
        start_ts=start_ts,
        end_ts=end_ts,
        start_equity=start_equity,
        end_equity=end_equity,
        total_return=total_return,
        max_drawdown=max_drawdown,
        fills=fills,
        risk_halts=risk_halts,
        events_path=events_path,
    )


def render_review_markdown(summary: ReviewSummary, *, decision_path: str | None = None) -> str:
    def fmt(x: float | None, digits: int = 4) -> str:
        if x is None:
            return ""
        return f"{x:.{digits}f}"

    return "\n".join(
        [
            "# 交易复盘（草稿，自动生成）",
            "",
            "## 基本信息",
            f"- 对应决策记录：{decision_path or '（待补充）'}",
            f"- 对应事件日志（JSONL）：`{summary.events_path}`",
            f"- 标的（symbol）：`{summary.symbol}`",
            f"- 开始日期 / 结束日期：{summary.start_ts or ''} / {summary.end_ts or ''}",
            "",
            "## 结果摘要（自动计算）",
            f"- 期初权益：{fmt(summary.start_equity, 2)}",
            f"- 期末权益：{fmt(summary.end_equity, 2)}",
            f"- 总收益：{fmt(summary.total_return, 4)}",
            f"- 最大回撤：{fmt(summary.max_drawdown, 4)}",
            f"- 成交次数：{summary.fills}",
            f"- 风控熔断次数：{summary.risk_halts}",
            "",
            "## 复盘：偏差来自哪里（你来补充）",
            "- 数据/口径问题（复权、时区、交易日历）：",
            "- 执行问题（滑点、费用、成交时点）：",
            "- 策略假设问题（假设是否被证伪）：",
            "- 风控是否有效（触发了吗，是否该更早）：",
            "",
            "## 可复现证据（你来补充）",
            "- 回测命令/Notebook：",
            "- 关键图表/指标：",
            "",
            "## 结论与改进动作（必须可执行）",
            "- 动作 1（代码/参数/流程）：负责人/截止日期",
            "- 动作 2：",
            "",
        ]
    )


def write_review_draft(
    *,
    events_path: Path,
    out_path: Path,
    decision_path: str | None = None,
    overwrite: bool = False,
) -> Path:
    summary = summarize_paper_events(events_path)
    md = render_review_markdown(summary, decision_path=decision_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not overwrite:
        raise RuntimeError(f"Output already exists: {out_path} (use --overwrite)")
    out_path.write_text(md, encoding="utf-8")
    return out_path

