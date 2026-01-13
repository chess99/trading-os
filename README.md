# Trading OS（交易系统）

这是一套面向“持续赚钱目标”的个人交易系统骨架：把 **数据→研究→回测→（纸交易/实盘）执行→风控→记录复盘→迭代** 做成可维护闭环。

## 重要声明
- **不构成投资建议**：本仓库仅用于研究与工程实践。
- **风险自担**：实盘前必须在纸交易中验证稳定性，并设置严格风控。

## 快速开始（先跑通骨架）

进入项目：

```bash
cd /Users/zcs/code2/trading-os
```

创建虚拟环境并安装（推荐；后续你 `git init` 后也可照用）：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[data_lake]"
```

运行 CLI（目前是占位，用来验证工程结构）：

```bash
python -m trading_os --help
python -m trading_os paths
```

如果你暂时不想安装，也可以临时指定 `PYTHONPATH`：

```bash
PYTHONPATH=src python -m trading_os --help
```

## Python 版本说明
- 本项目的“数据湖（DuckDB/Parquet）”依赖目前通常需要 **Python 3.10–3.12**。
- 如果你当前是 Python 3.13，建议用 `conda`/`pyenv` 创建 3.12 环境再安装依赖。

## 目录结构
- `src/trading_os/`: 核心代码
  - `data/`: 数据采集、清洗、本地数据湖
  - `backtest/`: 回测引擎与评估
  - `execution/`: 纸交易/（未来）券商适配
  - `risk/`: 风控
  - `journal/`: 结构化交易日志
- `docs/`: 方法论与系统文档
- `journal/`: 你的决策记录与复盘（Markdown，便于检索）
- `notebooks/`: 研究 Notebook（可复现）
- `configs/`: 配置文件
- `data/`: 本地数据（建议不入库）
- `artifacts/`: 运行产物/报告（建议不入库）

## 推荐工作流（我们接下来会落地）
- 先定统一的数据 schema 与标的命名
- 建本地数据湖（DuckDB/Parquet）
- 回测与报告标准化（费用/滑点/走前验证）
- 纸交易执行 + 最小风控 + 全量记录
