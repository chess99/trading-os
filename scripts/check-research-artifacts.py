"""检查研究交付的存储边界；不执行模型，也不认证研究结论。"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

FILE_BUDGET = 1024**2
PERIOD_BUDGET = 2 * FILE_BUDGET
PERIOD = re.compile(r"^(20\d{2}-(?:FY|Q1|H1|Q3))(?:[.-]|$)")
ARCHIVES = {".zip", ".gz", ".xz", ".xzpart", ".bin", ".7z", ".tar", ".bz2"}
PROCESS_NAME = re.compile(
    r"(?:^|[-_/])(?:candidate|trace|snapshot|payload|stdout|stderr|cache|history|"
    r"historical|evidence|attempt|checkpoint)(?:[-_./]|$)",
    re.I,
)
ENCODED = re.compile(r"^[A-Za-z0-9+/=~!@#$%^&*()_{}\[\]:;,.?<>|\\`'\"-]+$")


def encoded_fragment_size(tree: ast.AST) -> int:
    """Count obvious encoded chunks without evaluating source or decoding archives."""
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            chunks = [
                part.value
                for part in node.elts
                if isinstance(part, ast.Constant) and isinstance(part.value, (str, bytes))
            ]
            if len(chunks) == len(node.elts):
                chunks = [
                    part.decode("ascii", errors="replace") if isinstance(part, bytes) else part
                    for part in chunks
                ]
                if all(len(part) >= 16 and ENCODED.fullmatch(part) for part in chunks):
                    total += sum(len(part) for part in chunks)
        value = None
        repetitions = 1
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            value = node.value
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Mult)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, (str, bytes))
            and isinstance(node.right, ast.Constant)
            and type(node.right.value) is int
        ):
            value = node.left.value
            repetitions = max(node.right.value - 1, 0)
        if value is None:
            continue
        if isinstance(value, bytes):
            value = value.decode("ascii", errors="replace")
        size = len(value) * repetitions
        if size > 256 and ENCODED.fullmatch(value):
            total += size
    return total


def issues(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    totals: dict[tuple[str, str], int] = defaultdict(int)
    count = 0
    companies = root / "research/companies"
    # Existing long review documents are outside this delivery-only boundary.
    for model_dir in sorted(companies.glob("*/*/models")):
        if model_dir.is_symlink() or not model_dir.resolve().is_relative_to(root.resolve()):
            errors.append(f"{model_dir.relative_to(root)}: 模型目录不能是符号链接")
            continue
        for path in sorted(model_dir.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"{relative}: 交付文件不能是符号链接")
                continue
            if not path.is_file():
                continue
            count += 1
            local = path.relative_to(model_dir).as_posix()
            size = path.stat().st_size
            # A readable source tree may place the period below an author/module
            # directory. The first period component owns the whole subtree.
            match = next(
                (found for part in Path(local).parts if (found := PERIOD.match(part))),
                None,
            )
            if not match and not re.fullmatch(r"20\d{2}-\d{2}-\d{2}\.py", local):
                errors.append(f"{relative}: 公司模型文件须归入明确财报周期")
            if match:
                totals[(model_dir.as_posix(), match[1])] += size
            if size > FILE_BUDGET:
                errors.append(f"{relative}: {size} 字节超过单文件 1 MiB 预算")
            if path.suffix.lower() in ARCHIVES or path.suffix.lower() not in {
                ".py",
                ".json",
                ".md",
                ".csv",
            }:
                errors.append(f"{relative}: 模型交付只接受可读文本，不接受归档或分片")
            if PROCESS_NAME.search(local):
                errors.append(f"{relative}: 候选、过程轨迹及历史运行材料应留在临时目录")
            if size > FILE_BUDGET or path.suffix.lower() not in {".py", ".json", ".md", ".csv"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeError:
                errors.append(f"{relative}: 交付文件应为 UTF-8 文本")
                continue
            if path.suffix == ".py":
                try:
                    tree = ast.parse(text, filename=relative)
                except SyntaxError as error:
                    errors.append(f"{relative}: Python 语法错误：{error.msg}")
                    continue
                if encoded_fragment_size(tree) > 8192:
                    errors.append(f"{relative}: 分段编码常量应留在工作档案，不能嵌入源码")
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Constant) or not isinstance(
                        node.value, (str, bytes)
                    ):
                        continue
                    value = (
                        node.value.decode("ascii", errors="replace")
                        if isinstance(node.value, bytes)
                        else node.value
                    )
                    if len(value) > 65536 or (len(value) > 8192 and ENCODED.fullmatch(value)):
                        errors.append(
                            f"{relative}:{node.lineno}: 超长内嵌数据应拆为必要输入，"
                            "归档不能编码进源码"
                        )
                        break
            elif path.suffix == ".json":
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    errors.append(f"{relative}: 无效 JSON")
                    continue
                if isinstance(value, dict) and (
                    re.search(
                        r"lossless|verification_payload|complete_case_manifest",
                        str(value.get("schema", "")),
                    )
                    or re.search(r"base64|gzip|xz", str(value.get("encoding", "")))
                ):
                    errors.append(f"{relative}: 压缩载荷清单不能作为研究结果交付")
                if re.search(r'"[^"\\\r\n]{8192,}"', text):
                    errors.append(f"{relative}: 超长字符串载荷应留在临时归档")
    for (directory, period), size in sorted(totals.items()):
        if size > PERIOD_BUDGET:
            relative = Path(directory).relative_to(root).as_posix()
            errors.append(f"{relative}/{period}: {size} 字节超过公司周期 2 MiB 预算")
    # Period reports are current deliverables too. Legacy date-named reports and
    # historical review documents keep their existing archival treatment.
    for report_dir in sorted(companies.glob("*/*/reports")):
        if report_dir.is_symlink() or not report_dir.resolve().is_relative_to(root.resolve()):
            errors.append(f"{report_dir.relative_to(root)}: 报告目录不能是符号链接")
            continue
        for path in sorted(report_dir.glob("*.md")):
            if not re.fullmatch(r"20\d{2}-(?:FY|Q1|H1|Q3)\.md", path.name):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"{relative}: 交付文件不能是符号链接")
            elif path.is_file() and (size := path.stat().st_size) > FILE_BUDGET:
                errors.append(f"{relative}: {size} 字节超过单文件 1 MiB 预算")
    return errors, count


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors, count = issues(args.root.resolve())
    print(
        json.dumps(
            {"ok": not errors, "model_files_checked": count, "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
