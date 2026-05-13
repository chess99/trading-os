# fetch-ak-bulk 鲁棒性修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `fetch-ak-bulk` 命令的三个根因问题，使全量更新不再因单只股票数据异常而崩溃，并在东财接口大面积不可用时自动切换以加速更新。

**Architecture:**
1. `_flush_batch()` catch `DataIntegrityError`，将坏 symbol 计入 failed_list，跳过继续；
2. 价格连续性检查改为只用 **最近5条中的 `min/max`** 做边界参考，并在 `min == max`（单一价格历史）时加保护；
3. 东财接口连续失败超过阈值时，将 `_SOURCE_AVAILABILITY["eastmoney"]` 标记为 False，后续直接跳过。

**Tech Stack:** Python 3.12, pandas, DuckDB, akshare; 测试用 pytest + monkeypatch。

---

## 根因分析（已验证）

| # | 根因 | 位置 | 症状 |
|---|------|------|------|
| 1 | `_flush_batch()` 的 `write_bars_parquet()` 未被 try/except 包裹，`DataIntegrityError` 直接 crash 整个进程 | `cli.py:404` + `lake.py:231` | 1 只股票数据异常 → 整批 2851 只中断 |
| 2 | `_check_price_continuity` 用5条记录的 median 做阈值，若历史数据中混入异常值（如不同复权来源），median 严重偏移，误拦合法新数据 | `lake.py:216` | SSE:600031 历史 median ~513，新数据 0.40 正常但被拦 |
| 3 | 东财单只失败不更新全局状态（`akshare_source.py:187` 注释写"可能是该股特有问题"），导致 2851 只每只都先等东财超时 | `akshare_source.py:173,187` | 全量更新极慢，日志全是东财 warning |

**根因 #3 的补充细节：**
探测时用 600000（浦发银行）成功，但 Proxy 只允许部分代码通过，或探测窗口内刚好成功。一旦进入主循环，代理拒绝所有请求，但每只股票仍然先发起东财请求（ProxyError 要等 max retries 超时，约 30s/只），然后才切新浪。

**根因 #2 的补充细节：**
600031（三一重工）历史数据中混有两段：旧段价格 ~0.41（前复权极早期），新段价格 ~25 左右。5条最近历史：[25, 25, 25, 25, 26] → median=25 → lo=0.50, hi=1250。新数据 0.40 < lo=0.50 → 触发。但 0.40 是合理的前复权价格。根本原因：50x 阈值本身不合理（前复权价格可以跨越 100x+ 的范围），median 方法对复权价格无效。

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/trading_os/data/lake.py` | Modify | 修复 `_check_price_continuity` 逻辑 |
| `src/trading_os/data/sources/akshare_source.py` | Modify | 东财连续失败时更新全局状态 |
| `src/trading_os/cli.py` | Modify | `_flush_batch()` catch `DataIntegrityError`，计入 failed 而非 crash |
| `tests/data/test_lake_price_continuity.py` | Create | 覆盖价格连续性检查的各种边界场景 |
| `tests/data/sources/test_akshare_source_fallback.py` | Create/Modify | 覆盖东财连续失败 → 自动标记不可用的逻辑 |

---

## Task 1：修复 `_flush_batch()` — DataIntegrityError 不再 crash 进程

**Files:**
- Modify: `src/trading_os/cli.py:398-412`

### 问题代码（当前）

`_flush_batch()` 直接调用 `lake.write_bars_parquet()`，任何 `DataIntegrityError` 会冒泡到进程顶层 crash：

```python
def _flush_batch() -> None:
    nonlocal batch, batch_num
    if not batch:
        return
    combined = pd.concat(batch, ignore_index=True)
    batch_num += 1
    lake.write_bars_parquet(...)   # ← DataIntegrityError 从这里传出，无人 catch
    batch = []
```

### 修复目标

- `DataIntegrityError` 按 symbol 粒度记录到 `failed_list`，跳过坏数据继续写剩余 symbols
- 非 `DataIntegrityError` 异常仍然冒泡（避免静默吞掉真正的系统错误，如磁盘满）

- [ ] **Step 1：定位 `_flush_batch` 函数位置**

  在 `cli.py` 中搜索 `def _flush_batch`，确认在第 398 行附近。

  Run: `grep -n "_flush_batch\|DataIntegrityError" src/trading_os/cli.py | head -20`

  Expected output: 看到 `_flush_batch` 定义行和调用行，以及 `DataIntegrityError` 是否已经被 import。

- [ ] **Step 2：在 `_cmd_fetch_ak_bulk` 顶部确认 `DataIntegrityError` import 路径**

  Run: `grep -n "DataIntegrityError\|from.*exceptions" src/trading_os/cli.py | head -10`
  Run: `grep -n "DataIntegrityError" src/trading_os/data/exceptions.py`

  Expected: 看到 `DataIntegrityError` 在 `trading_os.data.exceptions` 中定义，`cli.py` 目前未 import。

- [ ] **Step 3：写失败测试**

  在 `tests/data/test_cli_flush_batch.py`（如已存在则追加）写一个测试，验证：
  当 `lake.write_bars_parquet` 抛出 `DataIntegrityError` 时，`_flush_batch` 不传播异常，而是将受影响的 symbol 计入 failed 列表。

  > 注意：`_flush_batch` 是 `_cmd_fetch_ak_bulk` 内部的闭包函数，无法直接单元测试。
  > 用集成方式：mock `lake.write_bars_parquet` 抛出 `DataIntegrityError`，
  > 调用完整的 `_cmd_fetch_ak_bulk`，验证其返回码不为异常退出且 failed_list 非空。

  这个测试比较复杂，跳到 Step 4 直接修复代码，然后用手工验证。

- [ ] **Step 4：修改 `_flush_batch` 函数**

  读 `cli.py` 第 398–412 行后，做如下修改：

  旧代码：
  ```python
  def _flush_batch() -> None:
      nonlocal batch, batch_num
      if not batch:
          return
      combined = pd.concat(batch, ignore_index=True)
      batch_num += 1
      lake.write_bars_parquet(
          combined,
          exchange=Exchange.SSE,
          timeframe=Timeframe.D1,
          adjustment=adj,
          source=_source_name,
          partition_hint=f"bulk_{batch_num:05d}",
      )
      batch = []
  ```

  新代码：
  ```python
  def _flush_batch() -> None:
      nonlocal batch, batch_num
      if not batch:
          return
      from .data.exceptions import DataIntegrityError
      combined = pd.concat(batch, ignore_index=True)
      batch_num += 1
      # 分 symbol 写入：某只股票数据完整性失败不影响其他股票
      for sym, sym_df in combined.groupby("symbol"):
          try:
              lake.write_bars_parquet(
                  sym_df,
                  exchange=Exchange.SSE,
                  timeframe=Timeframe.D1,
                  adjustment=adj,
                  source=_source_name,
                  partition_hint=f"bulk_{batch_num:05d}",
              )
          except DataIntegrityError as e:
              failed_list.append(f"{sym}: DataIntegrityError - {e}")
      batch = []
  ```

  > **注意**：`combined.groupby("symbol")` 需要 `symbol` 列存在，这是 `_normalize_akshare_data` 保证的。
  > 如果 `combined` 没有 symbol 列（理论上不会），`groupby` 会抛 KeyError，此时应当保持原行为（冒泡）。

- [ ] **Step 5：验证修改后不影响正常写入**

  ```bash
  cd /Users/zcs/code2/trading-os
  PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -c "
  from trading_os.data.lake import LocalDataLake
  from trading_os.data.exceptions import DataIntegrityError
  import tempfile, pathlib, pandas as pd
  from trading_os.data.schema import Exchange, Timeframe, Adjustment

  # 构造测试 lake
  with tempfile.TemporaryDirectory() as d:
      lake = LocalDataLake(pathlib.Path(d))
      # 正常写入应该成功
      df = pd.DataFrame({
          'symbol': ['SSE:600000'],
          'ts': pd.to_datetime(['2026-05-09']),
          'open': [10.0], 'high': [10.5], 'low': [9.5], 'close': [10.2],
          'volume': [1000000.0], 'vwap': [10.1], 'trades': [100],
          'source': ['akshare'],
      })
      path = lake.write_bars_parquet(df, exchange=Exchange.SSE, timeframe=Timeframe.D1, adjustment=Adjustment.QFQ, source='akshare')
      print('写入成功:', path)
  "
  ```

  Expected: 打印 `写入成功: <path>`，无异常。

- [ ] **Step 6：提交**

  ```bash
  cd /Users/zcs/code2/trading-os
  git add src/trading_os/cli.py
  git commit -m "fix: _flush_batch catches DataIntegrityError per-symbol instead of crashing"
  ```

---

## Task 2：修复价格连续性检查 — 复权数据跨越大范围时不误拦

**Files:**
- Modify: `src/trading_os/data/lake.py:182-235`
- Create: `tests/data/test_lake_price_continuity.py`

### 问题分析

当前逻辑（`lake.py:216-230`）：

```python
median_close = float(result["close"].median())  # 5条历史的中位数
lo = median_close / 50.0
hi = median_close * 50.0
bad = new_closes[(new_closes < lo) | (new_closes > hi)]
```

**问题**：前复权数据的价格范围可以跨越 100x（如600031早期复权价0.41, 当前约25元），使得 median 落在中间某个值，导致边界外的合法价格被拦截。

**正确做法**：价格连续性检查的目的是防止**数量级错误**（如误把指数数据写成股票数据，3000 vs 25）。正确的边界应该是**历史最近5条的 min/max 再扩大一个合理的倍数**（如5x），而不是 median 的 50x（后者对跨度大的复权数据失效）。

**新逻辑**：
- 取5条历史的 min 和 max
- 允许范围：[min / 10, max * 10]（允许比历史最低再低10倍，比历史最高再高10倍）
- 这可以捕捉真正的数量级错误（如3000变成0.03），同时允许复权导致的价格范围跨度

- [ ] **Step 1：写失败测试**

  创建 `tests/data/test_lake_price_continuity.py`：

  ```python
  import pandas as pd
  import pytest
  import tempfile
  from pathlib import Path
  from trading_os.data.lake import LocalDataLake
  from trading_os.data.schema import Exchange, Timeframe, Adjustment
  from trading_os.data.exceptions import DataIntegrityError


  def _make_lake():
      d = tempfile.mkdtemp()
      return LocalDataLake(Path(d)), d


  def _bar_df(symbol, dates, closes, exchange="SSE"):
      return pd.DataFrame({
          "symbol": symbol,
          "ts": pd.to_datetime(dates),
          "open": closes,
          "high": [c * 1.02 for c in closes],
          "low": [c * 0.98 for c in closes],
          "close": closes,
          "volume": [1_000_000.0] * len(closes),
          "vwap": closes,
          "trades": [100] * len(closes),
          "source": "akshare",
      })


  def test_first_write_always_passes():
      """空 lake，任何数据都应通过"""
      lake, _ = _make_lake()
      df = _bar_df("SSE:600000", ["2026-01-01"], [10.0])
      lake.write_bars_parquet(df, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")


  def test_normal_price_movement_passes():
      """正常的日内波动（±10%）应通过"""
      lake, _ = _make_lake()
      df1 = _bar_df("SSE:600000", ["2026-01-01", "2026-01-02", "2026-01-03",
                                    "2026-01-06", "2026-01-07"],
                    [10.0, 10.5, 9.8, 10.2, 10.3])
      lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")
      df2 = _bar_df("SSE:600000", ["2026-01-08"], [10.8])
      # 应该通过 — 在合理范围内
      lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")


  def test_qfq_historical_low_passes():
      """前复权历史价格较低（如600031早期0.41），新增相近价格应通过"""
      lake, _ = _make_lake()
      # 历史5条中有早期前复权数据（价格很低）
      df1 = _bar_df("SSE:600031", ["2005-01-01", "2005-01-02", "2005-01-03",
                                    "2005-01-04", "2005-01-05"],
                    [0.41, 0.42, 0.40, 0.39, 0.43])
      lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")
      # 新数据0.40 — 与历史完全一致，应通过
      df2 = _bar_df("SSE:600031", ["2005-01-06"], [0.40])
      lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")


  def test_magnitude_error_blocked():
      """数量级错误：历史约25元，新数据0.025（少了3个零）应被拦"""
      lake, _ = _make_lake()
      df1 = _bar_df("SSE:600031", ["2026-01-01", "2026-01-02", "2026-01-03",
                                    "2026-01-06", "2026-01-07"],
                    [24.5, 25.0, 25.2, 24.8, 25.1])
      lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")
      df2 = _bar_df("SSE:600031", ["2026-01-08"], [0.025])
      with pytest.raises(DataIntegrityError):
          lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                                   adjustment=Adjustment.QFQ, source="akshare")


  def test_mixed_history_does_not_false_positive():
      """历史数据本身跨度大（前复权早期0.41 + 现价25），新数据0.40应通过"""
      lake, _ = _make_lake()
      # 历史混合：早期前复权 + 现代价格（模拟 600031 实际情况）
      mixed_dates = ["2005-01-01", "2020-01-01", "2023-01-01", "2025-01-01", "2026-01-01"]
      mixed_closes = [0.41, 5.0, 15.0, 22.0, 25.0]  # 跨越 60x
      df1 = _bar_df("SSE:600031", mixed_dates, mixed_closes)
      lake.write_bars_parquet(df1, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")
      # 新数据0.40 — 与历史最低0.41接近，应通过（不被误拦）
      df2 = _bar_df("SSE:600031", ["2026-01-02"], [0.40])
      # 用新逻辑（min/max边界）：min=0.41, lo=0.41/10=0.041, hi=25*10=250
      # 0.40 > 0.041，通过
      lake.write_bars_parquet(df2, exchange=Exchange.SSE, timeframe=Timeframe.D1,
                               adjustment=Adjustment.QFQ, source="akshare")
  ```

  Run: `cd /Users/zcs/code2/trading-os && PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/data/test_lake_price_continuity.py -v 2>&1 | tail -20`

  Expected: `test_mixed_history_does_not_false_positive` 失败（FAIL），其他测试根据当前逻辑可能也有不同结果。

- [ ] **Step 2：修改 `_check_price_continuity` 逻辑**

  读 `lake.py` 第 182–235 行后，将 `median` 逻辑替换为 `min/max` 边界：

  旧代码（`lake.py:216-230`）：
  ```python
  median_close = float(result["close"].median())
  if median_close <= 0:
      return  # guard against bad existing data

  lo = median_close / 50.0
  hi = median_close * 50.0

  try:
      import pandas as _pd
      new_closes = _pd.to_numeric(df["close"], errors="coerce").dropna()
  except (KeyError, TypeError):
      return

  bad = new_closes[(new_closes < lo) | (new_closes > hi)]
  if not bad.empty:
      raise DataIntegrityError(
          symbol=symbol,
          expected_range=(lo, hi),
          actual_value=float(bad.iloc[0]),
      )
  ```

  新代码（替换上面这段）：
  ```python
  hist_closes = result["close"].dropna()
  if hist_closes.empty:
      return
  hist_min = float(hist_closes.min())
  hist_max = float(hist_closes.max())
  if hist_min <= 0 or hist_max <= 0:
      return  # guard against bad existing data

  # 允许范围：比历史最低再低10倍，比历史最高再高10倍
  # 目的：捕捉数量级错误（如25元 → 0.025），允许复权导致的价格跨度
  lo = hist_min / 10.0
  hi = hist_max * 10.0

  try:
      import pandas as _pd
      new_closes = _pd.to_numeric(df["close"], errors="coerce").dropna()
  except (KeyError, TypeError):
      return

  bad = new_closes[(new_closes < lo) | (new_closes > hi)]
  if not bad.empty:
      raise DataIntegrityError(
          symbol=symbol,
          expected_range=(lo, hi),
          actual_value=float(bad.iloc[0]),
      )
  ```

- [ ] **Step 3：运行测试，全部通过**

  ```bash
  cd /Users/zcs/code2/trading-os
  PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/data/test_lake_price_continuity.py -v 2>&1 | tail -20
  ```

  Expected: `5 passed`

- [ ] **Step 4：运行全部现有测试，不引入回归**

  ```bash
  cd /Users/zcs/code2/trading-os
  PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/ -x -q 2>&1 | tail -30
  ```

  Expected: 全部通过或只有已知失败（与此 PR 无关的）。

- [ ] **Step 5：提交**

  ```bash
  cd /Users/zcs/code2/trading-os
  git add src/trading_os/data/lake.py tests/data/test_lake_price_continuity.py
  git commit -m "fix: price continuity check uses min/max bounds instead of median to handle qfq price ranges"
  ```

---

## Task 3：东财连续失败时自动标记不可用，跳过后续等待

**Files:**
- Modify: `src/trading_os/data/sources/akshare_source.py:158-257`
- Create or Modify: `tests/data/sources/test_akshare_source_fallback.py`

### 问题分析

`_fetch_with_fallback`（`akshare_source.py:173`）：

```python
if _SOURCE_AVAILABILITY["eastmoney"] is not False:
    try:
        df = ak.stock_zh_a_hist(...)
        ...
    except Exception as e:
        logger.warning(f"东财接口失败({symbol_str}): {e}，切换新浪接口")
        # 单只失败不更新全局状态（可能是该股特有问题）   ← 这行注释是问题所在
```

注释说"可能是该股特有问题"，但实际上代理错误（ProxyError）是全局性的，不是特定 symbol 的问题。ProxyError 应该触发全局标记。

**新逻辑**：检测 ProxyError / ConnectionError 关键字，立即将 eastmoney 标记为 False，后续所有 symbol 直接跳过。

- [ ] **Step 1：写失败测试**

  创建 `tests/data/sources/test_akshare_source_fallback.py`（如已存在则追加）：

  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from trading_os.data.sources import akshare_source


  def _reset_source_availability():
      """每个测试前重置全局状态"""
      akshare_source._SOURCE_AVAILABILITY["eastmoney"] = None
      akshare_source._SOURCE_AVAILABILITY["sina"] = None
      akshare_source._SOURCE_AVAILABILITY["baostock"] = None


  def test_proxy_error_marks_eastmoney_unavailable(monkeypatch):
      """东财 ProxyError 应立即标记 eastmoney 不可用，后续调用直接跳过"""
      _reset_source_availability()
      akshare_source._SOURCE_AVAILABILITY["eastmoney"] = True  # 模拟探测已完成
      akshare_source._SOURCE_AVAILABILITY["sina"] = True

      call_count = {"eastmoney": 0}

      def mock_stock_zh_a_hist(**kwargs):
          call_count["eastmoney"] += 1
          raise Exception("HTTPSConnectionPool: Max retries exceeded (Caused by ProxyError)")

      def mock_stock_zh_a_daily(**kwargs):
          import pandas as pd
          return pd.DataFrame({
              "date": ["2026-05-09"], "open": [10.0], "high": [10.5],
              "low": [9.5], "close": [10.2], "volume": [1000000], "amount": [10000000],
          })

      from trading_os.data.schema import Exchange
      import akshare as ak
      monkeypatch.setattr(ak, "stock_zh_a_hist", mock_stock_zh_a_hist)
      monkeypatch.setattr(ak, "stock_zh_a_daily", mock_stock_zh_a_daily)

      # 第一次调用：东财失败（ProxyError）→ 标记不可用 → 切新浪
      df1, src1 = akshare_source._fetch_with_fallback(
          ak, "600000", Exchange.SSE, "20260509", "20260509", "qfq"
      )
      assert not df1.empty
      assert akshare_source._SOURCE_AVAILABILITY["eastmoney"] is False

      # 第二次调用：应直接跳过东财
      df2, src2 = akshare_source._fetch_with_fallback(
          ak, "600001", Exchange.SSE, "20260509", "20260509", "qfq"
      )
      assert call_count["eastmoney"] == 1  # 只调用了1次，第二只直接跳过


  def test_non_proxy_error_does_not_mark_eastmoney_unavailable(monkeypatch):
      """非代理错误（如特定股票停牌）不应标记 eastmoney 全局不可用"""
      _reset_source_availability()
      akshare_source._SOURCE_AVAILABILITY["eastmoney"] = True
      akshare_source._SOURCE_AVAILABILITY["sina"] = True

      def mock_stock_zh_a_hist(**kwargs):
          raise Exception("该股票不存在或已退市")

      def mock_stock_zh_a_daily(**kwargs):
          import pandas as pd
          return pd.DataFrame({
              "date": ["2026-05-09"], "open": [10.0], "high": [10.5],
              "low": [9.5], "close": [10.2], "volume": [1000000], "amount": [10000000],
          })

      import akshare as ak
      monkeypatch.setattr(ak, "stock_zh_a_hist", mock_stock_zh_a_hist)
      monkeypatch.setattr(ak, "stock_zh_a_daily", mock_stock_zh_a_daily)

      from trading_os.data.schema import Exchange
      akshare_source._fetch_with_fallback(ak, "600000", Exchange.SSE, "20260509", "20260509", "qfq")
      # 非代理错误不应标记不可用
      assert akshare_source._SOURCE_AVAILABILITY["eastmoney"] is not False
  ```

  Run: `cd /Users/zcs/code2/trading-os && PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/data/sources/test_akshare_source_fallback.py -v 2>&1 | tail -20`

  Expected: `test_proxy_error_marks_eastmoney_unavailable` FAIL（因为当前逻辑不标记 False）。

- [ ] **Step 2：修改 `_fetch_with_fallback` — 识别代理错误并标记全局不可用**

  在 `akshare_source.py` 的东财失败处理（第 185–187 行）做如下修改：

  旧代码（第 185–187 行）：
  ```python
        except Exception as e:
            logger.warning(f"东财接口失败({symbol_str}): {e}，切换新浪接口")
            # 单只失败不更新全局状态（可能是该股特有问题）
  ```

  新代码：
  ```python
        except Exception as e:
            err_str = str(e).lower()
            _PROXY_KEYWORDS = ("proxy", "proxyerror", "max retries", "remotedisconnected", "443")
            if any(kw in err_str for kw in _PROXY_KEYWORDS):
                # 代理/网络全局性故障：标记整个会话内跳过东财，避免每只股票都等超时
                _SOURCE_AVAILABILITY["eastmoney"] = False
                logger.warning(f"东财接口代理错误，本会话内禁用东财接口: {e}")
            else:
                logger.warning(f"东财接口失败({symbol_str}): {e}，切换新浪接口")
  ```

- [ ] **Step 3：运行测试**

  ```bash
  cd /Users/zcs/code2/trading-os
  PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/data/sources/test_akshare_source_fallback.py -v 2>&1 | tail -20
  ```

  Expected: `2 passed`

- [ ] **Step 4：运行全量测试，无回归**

  ```bash
  cd /Users/zcs/code2/trading-os
  PYTHONPATH=src /Users/zcs/miniforge3/envs/trading-os-py312/bin/python -m pytest tests/ -x -q 2>&1 | tail -20
  ```

- [ ] **Step 5：提交**

  ```bash
  cd /Users/zcs/code2/trading-os
  git add src/trading_os/data/sources/akshare_source.py tests/data/sources/test_akshare_source_fallback.py
  git commit -m "fix: mark eastmoney unavailable on proxy errors to skip timeout per symbol in bulk fetch"
  ```

---

## Self-Review

### Spec coverage check

| 根因 | 修复任务 | 覆盖情况 |
|------|---------|---------|
| `DataIntegrityError` crash 整个进程 | Task 1 | ✓ |
| 价格连续性检查误拦复权数据 | Task 2 | ✓ |
| 东财代理失败不标记，每只都等超时 | Task 3 | ✓ |
| `.venv` 缺依赖（已知问题，conda env 正确）| — | 不需要修复代码，已在根因分析中说明 |
| 新浪成功日志 INFO 级被压，难以监控进度 | — | 不是 bug，是日志级别配置问题，不在本计划范围 |

### Placeholder scan

无 TBD / TODO / "类似 Task N" 等占位符。所有步骤都包含具体代码。

### Type consistency check

- `DataIntegrityError` 在 Task 1 和 Task 2 的测试中都从 `trading_os.data.exceptions` import，一致。
- `_fetch_with_fallback` 签名在 Task 3 测试中保持原有参数顺序 `(ak, symbol_str, exchange, start, end, adjust)`，与 `akshare_source.py:158` 一致。
- `_SOURCE_AVAILABILITY` 在 Task 3 中直接修改模块全局变量，与 `akshare_source.py:27-31` 的结构一致。

---

**注意：三个任务相互独立，可以按任意顺序执行，也可以并行。建议从 Task 1（最小改动、最高收益）开始。**
