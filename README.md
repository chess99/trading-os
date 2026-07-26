# Trading OS

Trading OS 是一个以证据、不可变时间线和独立承保为核心的投资研究资产仓库。

## 资产分层

```text
coverage/                         全市场覆盖、筛选和可恢复队列
research/companies/{市场}/{代码}/ 单公司报告、证据和承保封存产物
research/batches/{批次}/          跨公司模型组合、排除记录和综合报告
automation/runs/{批次}/           可恢复状态、事件日志和 agent 租约
policies/                         版本化研究配置、承保、行业和组合政策
```

公司 `meta.json` 只保存身份、覆盖、报告时间线、承保状态、价值快照和复核触发器。最终操作和仓位只存在于批次模型组合中。

## 研究机制

1. 全市场先做多视角便宜地图；机器排名不得直接晋级深研。
2. 有限研究预算依次投入快速画像、范围研究和少数完整深研；停止必须可审计并带重启条件。
3. 完整初研生成不可变中文报告、来源清单和结构化主张。
4. 独立 agent 在半盲状态下重建证据、三张桥和三情景价值；结果先封存，再揭示差异。
5. 重大分歧触发完全独立的 challenger 和仲裁。
6. 单公司只能承保通过；跨公司组合层才决定 `buy_now`、其他操作和仓位。

## 命令

```bash
python -m trading_os assets validate
python -m trading_os review create <run-id> --scope-type industry --market CN --description "行业" --candidates <candidates.json>
python -m trading_os review prepare <run-id>
python -m trading_os review status <run-id>
python -m trading_os review validate <run-id> --strict
python -m trading_os review synthesize <run-id> --quotes <quotes.json>
python -m trading_os review report <run-id>
python -m trading_os coverage validate
python -m trading_os coverage rank-rebaseline
python -m trading_os coverage allocate-research
python -m trading_os coverage apply-allocation
python -m trading_os coverage evaluate-profile --input <quick-profile.json>
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```

详细流程见 `playbooks/`。价格提醒是复核触发器，不是自动交易指令。
