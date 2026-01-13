# Python 环境（推荐 3.12）

## 为什么需要 3.10–3.12
MVP 需要 DuckDB/Parquet（`duckdb`/`pyarrow`/`pandas`）。这些库对新版本 Python 的 wheel 支持通常滞后。\n
因此仓库在 `pyproject.toml` 中约束了：`>=3.10,<3.13`。

## conda（miniforge）创建环境（推荐）

```bash
cd /Users/zcs/code2/trading-os
conda create -n trading-os-py312 python=3.12 -y
conda activate trading-os-py312
python -m pip install -U pip
pip install -e ".[data_lake]"
```

可选：接入 Yahoo 数据源

```bash
pip install -e ".[data_lake,data_yahoo]"
```

## 验证

```bash
python -m trading_os --help
python -m trading_os lake-init
python -m trading_os seed --exchange NASDAQ --ticker TEST --days 10
python -m trading_os query-bars --symbols NASDAQ:TEST --limit 5
```

