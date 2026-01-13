# 本地数据湖（DuckDB + Parquet）

## 目标
- 让数据**可追溯**（来源/口径清晰）
- 让研究/回测/执行都能用同一份数据
- 让查询足够快（DuckDB 直接查 Parquet）

## 存储布局（当前实现）
位于仓库根目录的 `data/` 下：
- `data/lake.duckdb`：DuckDB 元数据与视图
- `data/parquet/bars/*.parquet`：K线数据（append-only）

## 逻辑对象
- `bars`：DuckDB view，覆盖 `data/parquet/bars/*.parquet`

## CLI（MVP）
初始化 data lake（即便没有 parquet 也能成功）：

```bash
PYTHONPATH=src python -m trading_os lake-init
```

离线写入一份合成数据：

```bash
PYTHONPATH=src python -m trading_os seed --exchange NASDAQ --ticker TEST --days 30
```

查询 bars（打印前 20 行）：

```bash
PYTHONPATH=src python -m trading_os query-bars --symbols NASDAQ:TEST --limit 20
```

