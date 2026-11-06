"""核对当前周期轻量交付；--recompute 才执行当前数学模型。"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def same(actual, expected):
    if type(actual) in (int, float) and type(expected) in (int, float):
        return (
            math.isfinite(actual)
            and math.isfinite(expected)
            and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            same(actual[key], expected[key]) for key in actual
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return type(actual) is type(expected) and actual == expected


def verify(root, period="2026-Q3", *, recompute=False, symbols=None, timeout=120):
    root = Path(root).resolve()
    states = []
    for partition in ("cn-a", "hk", "us"):
        path = root / "coverage" / partition / "research_state.jsonl"
        if path.exists():
            states.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
    rows = [
        row
        for row in states
        if row.get("report_period") == period and (not symbols or row["symbol"] in symbols)
    ]
    if not rows:
        raise ValueError("目标周期没有已完成研究")
    results = []
    for row in rows:
        symbol = row["symbol"]
        market, ticker = symbol.split(":", 1)
        directory = root / "research/companies" / market / ticker / "models"
        report = root / row["basis_report_path"]
        if not report.is_file():
            raise ValueError(f"{symbol}: 正式报告缺失")
        saved = directory / f"{period}-output.json"
        data = json.loads(saved.read_text(encoding="utf-8"))
        for key, expected in (
            ("symbol", symbol),
            ("report_period", period),
            ("value_range", row.get("value_range")),
            ("return_model", row.get("return_model")),
        ):
            if key not in data or not same(data[key], expected):
                raise ValueError(f"{symbol}: 当前结果与状态的 {key} 不一致")
        if data["value_range"] is None and not data.get("valuation_note"):
            raise ValueError(f"{symbol}: 空估值必须说明原因")
        if not data.get("return_model_note"):
            raise ValueError(f"{symbol}: 持有人模型必须说明口径或缺口")
        status = "not_run"
        producer = directory / f"{period}.py"
        if data["value_range"] is None and data["return_model"] is None:
            # A diagnostic script can exist while no complete equity model is adopted.
            # Its presence must not turn an unavailable numerical result into a pass.
            status = "numeric_model_unavailable"
        elif recompute:
            if not producer.is_file():
                raise ValueError(f"{symbol}: 非空估值缺少当前计算入口")
            with tempfile.TemporaryDirectory(prefix=f"q3-{ticker}-") as temporary:
                # Ordinary source/input files only. No Git history or hidden archive restoration.
                import shutil

                isolated_root = Path(temporary)
                target = isolated_root / "research/companies" / market / ticker / "models"
                target.mkdir(parents=True)
                shared_io = root / "research/model_io.py"
                if shared_io.is_file():
                    if shared_io.is_symlink():
                        raise ValueError("共享输出适配源码不能是外部链接")
                    shutil.copyfile(shared_io, isolated_root / "research/model_io.py")
                for source in directory.rglob("*"):
                    if source.is_file() and source.suffix in {".py", ".json", ".md", ".csv"}:
                        if source.name.endswith((
                            "-output.json", "-verification.json", "-independent-check.json",
                            "-diagnostics.json",
                        )):
                            continue
                        if source.is_symlink() or not source.resolve().is_relative_to(
                            directory.resolve()
                        ):
                            raise ValueError(f"{symbol}: 模型依赖不能通过链接读取外部文件")
                        destination = target / source.relative_to(directory)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, destination)
                (target / saved.name).unlink(missing_ok=True)
                completed = subprocess.run(
                    [sys.executable, "-B", str(target / producer.name)],
                    cwd=target,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                    env={
                        **os.environ,
                        "PYTHONHASHSEED": "0",
                        "PYTHONIOENCODING": "utf-8",
                        "PYTHONUTF8": "1",
                    },
                    check=False,
                )
                if completed.returncode:
                    raise ValueError(
                        f"{symbol}: 模型执行失败（{completed.returncode}）："
                        f"{completed.stderr[-2000:]}"
                    )
                generated = target / saved.name
                actual = json.loads(
                    generated.read_text(encoding="utf-8")
                    if generated.exists()
                    else completed.stdout
                )
                for key in ("symbol", "report_period", "value_range", "return_model"):
                    if key not in actual or not same(actual[key], data[key]):
                        raise ValueError(f"{symbol}: 模型实际复算的 {key} 不一致")
                status = "recomputed"
        results.append({"symbol": symbol, "contract": "matched", "numeric_check": status})
    return {
        "period": period,
        "contract_checked": len(results),
        "numeric_recomputed": sum(x["numeric_check"] == "recomputed" for x in results),
        "numeric_unavailable": sum(
            x["numeric_check"] == "numeric_model_unavailable" for x in results
        ),
        "results": results,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--period", default="2026-Q3")
    parser.add_argument("--symbol", action="append")
    parser.add_argument("--recompute", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        result = verify(
            args.root,
            args.period,
            recompute=args.recompute,
            symbols=args.symbol,
            timeout=args.timeout,
        )
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
