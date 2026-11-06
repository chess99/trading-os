"""公司模型的轻量输出适配；计算源码和输入保持可读。

旧计算入口在临时目录运行，完整轨迹仅在显式请求时保存。
这里按公司适配器给出的字段路径取实际计算结果，不读取研究状态。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def selected(value, selector):
    for key in selector["path"]:
        value = value[key]
    if "take" in selector:
        value = value[: selector["take"]]
    if "column" in selector:
        value = [row[selector["column"]] for row in value]
    if "column_path" in selector:
        def cell(row):
            for key in selector["column_path"]:
                row = row[key]
            return row
        value = [cell(row) for row in value]
    if "round_items" in selector:
        value = [round(float(item), digits) for item, digits in zip(value, selector["round_items"])]
    if "round" in selector:
        value = round(float(value), selector["round"])
    if "floor_step" in selector:
        value = math.floor(float(value) / selector["floor_step"]) * selector["floor_step"]
    if "ceil_step" in selector:
        value = math.ceil(float(value) / selector["ceil_step"]) * selector["ceil_step"]
    return value


def read_json(path):
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return json.loads(data.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    raise ValueError(f"计算入口未产生完整 JSON：{path.name}")


def result(full, selectors, metadata):
    values = {key: selected(full, value) for key, value in selectors.items()}
    currency = metadata.get("currency", "CNY")
    return {
        "schema": "trading_os_research_result_v1",
        "symbol": metadata["symbol"],
        "report_period": metadata["report_period"],
        "information_cutoff": metadata["information_cutoff"],
        "value_range": {
            "low": float(values["low"]),
            "high": float(values["high"]),
            "currency": currency,
        },
        "valuation_note": metadata["valuation_note"],
        "return_model": {
            "schema_version": 1,
            "method": "annual_common_equity_irr_v1",
            "currency": currency,
            "model_as_of": metadata["information_cutoff"],
            "base_case_distributions_per_share": [
                float(value) for value in values["distributions"]
            ],
            "base_case_terminal_equity_value_range_per_share": {
                "year_5": {
                    "low": float(values["terminal_low"]),
                    "high": float(values["terminal_high"]),
                }
            },
        },
        "return_model_note": metadata["return_model_note"],
    }


def main(adapter_file, selectors, metadata, *, source_file="stdout.json"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="保存简明 JSON；默认输出到终端")
    parser.add_argument("--full-output", type=Path, help="另存完整计算输出到工作目录")
    args = parser.parse_args()
    adapter = Path(adapter_file).resolve()
    engine = adapter.with_name(adapter.stem + "-engine.py")
    if not engine.is_file() or engine.is_symlink():
        raise ValueError("缺少可读计算源码")
    relative = Path(source_file)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("计算输出须位于临时目录")
    env = {key: value for key, value in os.environ.items() if key.upper() in {
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "WINDIR"
    }}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    with tempfile.TemporaryDirectory(prefix="trading-model-") as temporary:
        work = Path(temporary)
        entry = work / adapter.name
        shutil.copyfile(engine, entry)
        with (work / "stdout.json").open("wb") as out, (work / "stderr.txt").open("wb") as err:
            execution = subprocess.run(
                [sys.executable, "-I", "-B", "-X", "utf8", str(entry)],
                cwd=work, env=env, stdout=out, stderr=err, timeout=300, check=False,
            )
        if execution.returncode:
            error = (work / "stderr.txt").read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"计算失败（退出 {execution.returncode}）：{error[-2000:]}")
        raw = work / relative
        compact = result(read_json(raw), selectors, metadata)
        if args.full_output:
            args.full_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(raw, args.full_output)
    text = json.dumps(compact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0
