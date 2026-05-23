---
name: daily-workflow
description: |
  每日自选池工作流。由 scheduler 管理数据更新、全量扫描和日报门控。
  触发词："跑日常工作流"、"更新自选池"、"日常分析"、"今天市场怎样"、"日报"。
  输出：完成态日报，或 blocked 日报和明确阻塞原因。
  重要：不得绕过 scheduler 手工拼接日报；数据和扫描完成前不得给出市场或个股结论。
---

# Daily Workflow

**触发词**：「跑日常工作流」「更新自选池」「日常分析」「今天市场怎样」「日报」

## 核心原则

Daily 是 scheduler 驱动的流程，不是 agent 手工五步脚本。

默认只做三件事：

1. 查看 scheduler 当前状态。
2. 运行 `python -m trading_os daily` 生成完成态或 blocked 态日报。
3. 如果 blocked，停止分析并报告阻塞原因；如果完成，再基于日报和追踪文件做解释。

不要为了“完成 daily”直接运行 `fetch-ak-bulk`、`scan-elder`、`scan-canslim`、`pool status` 手工拼接结果，除非用户明确要求排查或修复 scheduler。

## 标准执行路径

```bash
python -m trading_os scheduler status
python -m trading_os scheduler jobs --limit 20
python -m trading_os daily
```

`daily` 会锚定当前应交付的 effective date，而不是回退到更早的完成态日报。若依赖未完成，它会生成临时 blocked 报告：`artifacts/daily/tmp/YYYYMMDD-blocked.md`。

看到 blocked 日报时：

- 不做大盘判断、个股买卖建议、扫描进出池结论。
- 不更新 pool，不把旧完成态当作今天的结果复用。
- 报告缺失的 job、effective date、当前进度文件和下一步可执行的 scheduler trigger。
- 如用户只要求日报，停在 blocked 状态即可。

看到完成态日报时：

- 使用日报中的 effective date 和 job id。
- CANSLIM `candidates` 由 scheduler 基于同日扫描结果重建；`watchlist/ready` 仍由人工研究维护。
- 如需进一步解释，读取 `artifacts/watchlist/`、`artifacts/scan/`、`artifacts/research/` 中对应日期文件。
- daily 的 TODO 和后续处理闭环写回对应的 `artifacts/daily/YYYYMMDD.md`。不要创建 `daily-followup`、`value-daily` 这类中间研究文件。
- 如果 TODO 需要深入研究某个标的，直接产出最终单标的报告到 `artifacts/research/{system}-{EXCHANGE}{TICKER}-YYYYMMDD.md`，并在 daily 中链接该报告。
- 结论必须明确基于该 effective date，不要把自然日“今天”等同于行情数据日期。

## Scheduler 语义

完整 daily 依赖同一 effective date 下这些成功 job：

- `market_data_bulk_refresh`
- `elder_scan`
- `canslim_scan`
- `daily_report`

`market_data_probe` 用于判断 A 股目标交易日是否已有可用数据。`market_data_bulk_refresh` 负责全量 K 线刷新，并会写入结构化进度。

扫描日期有前瞻偏差语义：行情数据 effective date 是最新已收盘数据日；扫描内部使用下一个交易日作为 signal date，因为 `DataPipeline` 在 signal date 只返回之前的数据。scan 产物文件名按 effective date 归档，JSON 内同时记录 effective date 和 signal date。不要手工把 effective date 直接传给 scan 命令来替代 scheduler 的转换。

## 手工触发

仅在用户要求诊断、补跑、修复时使用：

```bash
python -m trading_os scheduler trigger market_data_probe
python -m trading_os scheduler trigger market_data_bulk_refresh --effective-date YYYY-MM-DD
python -m trading_os scheduler trigger full_scan_and_daily --effective-date YYYY-MM-DD
```

`python -m trading_os scheduler run` 是长驻服务入口。启动前先看 `scheduler status`，避免重复启动多个 scheduler。交互式 agent 默认不需要启动长驻服务，除非用户明确要求。

## 进度与产物

关键文件：

- `data/scheduler.db`：scheduler job 状态事实源。
- `artifacts/jobs/status.json`：当前 scheduler 摘要。
- `artifacts/jobs/YYYYMMDD/*.log`：单 job 日志。
- `artifacts/jobs/current_fetch_bulk.json`：`fetch-ak-bulk` 当前进度或终态。
- `artifacts/daily/YYYYMMDD.md`：完成态日报。
- `artifacts/daily/tmp/YYYYMMDD-blocked.md`：阻塞态临时诊断报告，gitignored，不作为正式日报快照入库。
- `artifacts/scan/{system}-YYYYMMDD.json`：正式扫描快照。
- `artifacts/scan/{system}-YYYYMMDD.md`：同一扫描快照的人工解读；文件名必须与 JSON 同名。
- `artifacts/research/{system}-{EXCHANGE}{TICKER}-YYYYMMDD.md`：单标的最终深度研究报告。

排查 `fetch-ak-bulk` 是否卡住时，先看 `current_fetch_bulk.json` 和最近 job log。不要只因为命令耗时长就判定失败；A 股全量刷新可能运行较久，但必须持续更新进度或进入终态。

## 自选池解释规则

完成态日报已经包含扫描、候选池和需要立即处理事项。需要展开时：

```bash
python -m trading_os pool list -v
```

池中标的解释仍按体系分离：

- CANSLIM：基本面假设、EPS/销售增长、相对强度、技术确认。
- Elder：三重滤网、入场信号、价格止损。
- Value：护城河、估值、安全边际、逻辑止损。

任何进出池、升层、移出操作都应基于完成态日报或用户明确指定的扫描文件，不要基于 blocked 日报做交易动作。`pool sync-from-scan --apply` 只允许重建 `candidates`，不自动改 `watchlist/ready`。
