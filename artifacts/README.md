# Artifacts 目录契约

`artifacts/` 是交付层，不是 ResearchStore，也不是 recipe 的机器运行目录。

## 目录边界

- `artifacts/research/`：最终给人看的研究报告和投资备忘录。这里的文件必须有结论、判断、风险和证据链，不能只是脚本输出、CSV 摘要或 run 路径清单。
- `artifacts/research/archive/`：已经退出当前事实源、但仍需保留历史追溯的旧研究产物。归档文件不得作为新研究输入；需要复核历史时优先查 git history 和对应 run manifest。
- `artifacts/watchlist/state.json`：机器可读观察池状态，由 daily workflow 更新。
- `artifacts/watchlist/tracking/`：逐标的人工跟踪记录。
- `artifacts/journal/`：交易、提醒和执行审计产物，通常不入库。
- `data/research/runs/{run_id}/`：recipe 运行证据链，包含 manifest、trace、tables 和机器 report。这里不是最终投研交付目录。

## 命名

- Daily CANSLIM 汇报：`artifacts/research/daily-canslim-YYYYMMDD.md`
- Daily CANSLIM strict 复核：`artifacts/research/canslim-strict-review-YYYYMMDD.md`
- 单标的 CANSLIM 深研：`artifacts/research/canslim-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- Value 深研：`artifacts/research/value-{EXCHANGE}{TICKER}-YYYYMMDD.md`
- Elder 深研：`artifacts/research/elder-{EXCHANGE}{TICKER}-YYYYMMDD.md`

## 交付标准

最终报告必须由 agent 读完 run manifest、trace、tables 和必要的单标的证据后手工复核。报告至少回答：

- 今天有没有值得立即看的标的？
- 哪些标的只是观察，触发条件是什么？
- 哪些数据口径限制会降低置信度？
- 下一步该补什么数据、看什么价格、做什么风控动作？

脚本生成的 Markdown 只能算草稿；如果缺少研究判断，必须重写。
