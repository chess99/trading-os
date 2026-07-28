# A 股覆盖与筛选 Playbook

## 自适应研究漏斗

全市场工作按研究的信息价值逐层购买更多证据：

```text
约 5000 家普通 A 股覆盖
→ 全市场多视角便宜地图
→ 约 200 家动态快速甄别候选
→ 约 40 家正式投资画像
→ 约 15 家范围研究
→ 约 6 家完整深研
→ 约 3 家独立承保与组合比较
```

覆盖不等于每家公司都获得完整初研。筛选只决定是否值得购买下一阶段研究预算，不是投资结论；小市值、低流动性、暂时亏损或负倍数不能成为硬跳过理由。

公开数据排名只能作为便宜地图，不能直接晋级深研、承保或买入。必须经过 `playbooks/research-capital-allocation.md` 的快速画像和范围研究；不同类型机会分别选样，并为危机错杀与假阴性抽查保留容量。

非金融公司额外运行可复算的神奇公式镜头。其原始财报抓取必须绑定 universe SHA、真实
抓取时间、公告/更新时间和来源；今天下载的重述数据不得伪装成历史点时数据。东方财富等
未文档化公开接口只可用于内部预筛，不代表再分发许可；晋级公司必须回到交易所或巨潮
法定报告核验。通用价值镜头排除银行与保险，避免金融企业同时占用通用和专用低估值容量。

每层横向比较都执行风险簇上限而非行业配额。小市值、亏损、低流动性、负 PE 仍可通过
危机错杀、信息变化或假阴性镜头竞争预算，不因风格约束而被静默排除。

## 事件性冲击与危机错杀

- 当期亏损、利润骤降或 PE 失真不能降低研究资格；这类公司应优先判断冲击是需求延后、周期波动还是永久损失。
- 估值使用 3—5 年正常化盈利和多情景现金流，不把危机期亏损机械外推，也不把危机前峰值直接当作常态。
- 必须核验现金消耗、债务到期、再融资能力、潜在稀释和维持经营所需资本，先回答公司能否活到需求恢复。
- 反推当前价格隐含的恢复时间、恢复幅度和长期回报，寻找“市场按永久受损定价、但资产负债表足以穿越周期”的错配。
- 不要求把研究流程改造成历史时点量化回测。历史案例和经验用于构造当前情景、基准率与反证，最终判断仍基于当下可得事实。

## 分流

- `catalog`：已完成全市场机器清洗，但本周期未获得快速画像预算；保留结构化重启触发器。
- `rapid_triage`：15分钟级快速甄别；完成后等待全批次横向比较。
- `triage_candidate`：快速甄别通过，尚未获得正式画像预算。
- `quick_profile`：一小时级正式投资画像。
- `profile_candidate`：画像通过，等待同层横向比较范围研究预算。
- `scoped_research`：只解决决定性未知数的范围研究。
- `deep_candidate`：范围研究通过，等待同层横向比较完整深研预算。
- `deep_research`：进入初研队列。
- `watch_only`：已有资产或等待触发器。
- `conditional_stop`：当前停止投入，但保留结构化重启条件。
- `hard_exclusion`：不构成可执行普通股票投资对象。
- `needs_manual_review`：证券状态、数据或重大风险需人工判断。
- `skip_not_in_scope`：基金、债券、B 股等不在普通 A 股范围。
- 其他 `skip_*` 仅用于退市或确实无法形成研究对象的硬排除，必须写结构化理由。

## 可恢复文件

`coverage/cn-a/companies.jsonl`、`screening.jsonl`、`research_queue.jsonl` 和 `runs.jsonl` 都是可审计 JSONL，并使用稳定 symbol 排序。任务必须记录优先级、理由、证据、状态、目标公司目录、结果路径和下一步。

## 命令

```bash
python -m trading_os coverage validate
python -m trading_os coverage status
python -m trading_os coverage rank-rebaseline --magic-formula <sealed-snapshot> --include-completed
python -m trading_os coverage allocate-research
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id>
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage record-profile --input <quick-profile-package.json>
python -m trading_os coverage profile-finalize <cycle-id> --stage quick_profile
python -m trading_os coverage profile-finalize <cycle-id> --stage scoped_research
python -m trading_os coverage reconcile --check
```

每个公司资产验证通过后立即更新对应队列项；批次末尾的 reconcile 只是漂移安全网。
