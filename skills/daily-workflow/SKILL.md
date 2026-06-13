---
name: daily-workflow
description: |
  每日研究工作流。由 Daily CANSLIM closure 生成当日候选、深研、决策、观察池状态和证据链。
  触发词："跑日常工作流"、"更新自选池"、"日常分析"、"今天市场怎样"、"日报"。
  输出：artifacts/research/daily-canslim-YYYYMMDD.md、artifacts/watchlist/state.json、linked run manifest。
---

# Daily Research Workflow

Daily 是 ResearchStore + DataHub + research recipe 驱动的 CANSLIM 收口流程，不是 agent 手工拼接脚本。

标准入口：

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

## Agent 职责

1. 根据用户问题确定 `as_of`。
2. 运行 Daily CANSLIM closure recipe。
3. 读取本次 run 的 `manifest.json`、`trace.md`、`report.md`。
4. 读取 `artifacts/research/daily-canslim-YYYYMMDD.md` 和 `artifacts/watchlist/state.json`。
5. 向用户解释候选清单、每个 strict 候选的决策、观察池变化和数据口径限制。

不要手工串联底层数据脚本。不要直接读取 parquet。不要在缺失数据时编造结论。
不能只输出 run manifest 路径；必须总结决策和 watchlist changes。

## 数据语义

- `as_of` 是研究视角日期。
- DataHub 默认使用 `cache_first` 和 `lazy_fill`。
- 行情快照、财务缓存、历史价格缺口由 DataHub 统一处理。
- 深研或回测需要额外数据时，只补当前任务需要的标的。

## 产物

Daily CANSLIM closure command:

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
```

Required final user-facing outputs:

- `artifacts/research/daily-canslim-YYYYMMDD.md`
- `artifacts/watchlist/state.json`
- linked `data/research/runs/{run_id}/manifest.json`

每次运行还会生成 recipe 证据链：

```
artifacts/runs/{run_id}/manifest.json
artifacts/runs/{run_id}/trace.md
artifacts/runs/{run_id}/tables/*.csv
artifacts/runs/{run_id}/charts/*.png
artifacts/runs/{run_id}/report.md
```

回答用户时必须引用本次 run 的 manifest/report 路径，并说明：

- 使用的 `as_of`
- 执行了哪些 recipe
- 关键候选或研究队列
- 决策摘要和观察池变化
- 数据缺口和口径限制

`--top` 只限制展示结果，不能限制下游 strict-candidate processing。workflow 不能在
写完 run manifests 后停止，必须完成日报、决策和观察池更新。

## 自选池解释规则

池中标的解释仍按体系分离：

- CANSLIM：基本面假设、EPS/销售增长、相对强度、技术确认。
- Elder：三重滤网、入场信号、价格止损。
- Value：护城河、估值、安全边际、逻辑止损。

任何进出池、升层、移出操作都应基于 recipe run manifest、研究报告或用户明确指定的证据文件。
