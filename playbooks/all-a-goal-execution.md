# 全 A 股 Goal 长程执行 Playbook

## 目标与完成定义

目标是在有限研究预算下找到当下真正可执行的投资机会，并输出最新价、合理价值、
买入上限、预期回报、风险和仓位。完成全 A 股研究不等于给约 5500 家公司各写一份
报告，而是同时满足：

1. 本轮候选集合被显式冻结，来源、范围、异常和硬排除均有结构化记录；
2. 最新财报、价格和重大事件能够触发重新竞争研究预算；
3. 当前动态候选池完成 L1.5 快速甄别；
4. 各研究层都先完成同层批次，再横向比较晋级；
5. 最终承保候选按最新价格重新计算，并由组合层给实际买入结论；
6. 所有封存资产、coverage、索引、调度和提醒通过严格验证。

## 长程顺序

```text
显式冻结候选集合
→ 分配最多约200家动态快速甄别预算
→ 每家独立agent做15分钟快速甄别
→ 完整候选批次横向比较，最多约40家正式画像
→ 完整画像批次横向比较，最多约15家范围研究
→ 完整范围研究批次横向比较，最多约6家完整深研
→ 最多约3家独立承保
→ 最新行情下的组合综合与实际买入结论
```

容量全部是上限，不是配额。没有合格公司时允许少于上限，最终也允许没有
`buy_now`。

## 启动与恢复

1. 先读取 `AGENTS.md`、本文件、`playbooks/research-capital-allocation.md`、
   `playbooks/batch-dispatch.md` 和 `playbooks/portfolio-synthesis.md`。
2. 检查 `git status`、当前运行 agent、coverage 状态和已有封存资产。
3. 已完成且验证通过的单公司结果必须复用；正在运行的旧任务先安全收口或释放，
   不得由新分配静默覆盖。
4. 对显式给定的冻结输入执行研究分配并应用；新分配会保留已有正式研究进度。
5. 每家公司只允许一个独立 agent；单公司 agent 只提交 package 或公司资产，
   不直接编辑共享队列。
6. 每完成一个小批次就验证、封存、回写和只提交本批次文件。失败任务记录原因并释放，
   不阻塞其他公司。

## 强制闸门

- 外部筛选、已有清单或人工提名只能进入 `rapid_triage`。
- `triage-finalize` 在完整候选池终态前必须失败。
- `profile-finalize --stage quick_profile` 在完整正式画像批次终态前必须失败。
- `profile-finalize --stage scoped_research` 在完整范围研究批次终态前必须失败。
- 单公司层不得输出 `buy_now` 或仓位。
- 深研必须生成结构化主张与来源并验证后，才能冻结独立承保批次。
- 独立承保遵循半盲、揭示和必要 challenger；组合层必须使用最新行情重新计算，
  不能复述旧报告价格。

## 关键命令

```bash
python -m trading_os coverage allocate-research --ranking <frozen-input.json>
python -m trading_os coverage apply-allocation --ranking <frozen-input.json>

python -m trading_os coverage triage-claim --agent <agent-id>
python -m trading_os coverage triage-record --input <rapid-triage.json>
python -m trading_os coverage triage-status <cycle-id>
python -m trading_os coverage triage-finalize <cycle-id>

python -m trading_os coverage profile-claim --agent <agent-id>
python -m trading_os coverage record-profile --input <profile-package.json>
python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-finalize <cycle-id> --stage quick_profile
python -m trading_os coverage profile-finalize <cycle-id> --stage scoped_research

python -m trading_os assets validate
python -m trading_os coverage validate
python -m trading_os coverage reconcile --check
python -m trading_os index rebuild
python -m trading_os schedule build
python -m trading_os alerts build
```

## 对用户的最终交付

最终报告至少列出：

- 全市场覆盖数、候选数和每层实际晋级/停止数量；
- 所有进入承保或高优先观察公司的当前价格和价格时点；
- 悲观价值、合理价值区间、买入上限、基准预期年化回报；
- `buy_now`、`buy_on_weakness`、`watch`、`reject` 等组合操作；
- 建议初始仓位、目标仓位及组合约束；
- 主要投资逻辑、反方证据、证伪条件和重启触发器；
- 为什么其他最终候选没有被买入；
- 数据局限和仍需人工确认的事项。

持仓截图、个人成本、仓位等隐私只可用于本地研究优先级，禁止写入或提交公开仓库。
