# 全 A 股 Goal 长程执行 Playbook

## 目标

主 Agent 作为投资经理，用统一尺度快速看完全市场，再把有限研究时间集中到少数高信息价值公司。全覆盖不等于为 5500 家公司分别启动 Agent，也不等于制造 5500 份报告。

## 生产流程

```text
冻结普通 A 股 scope
→ 程序生成每批 100—200 家压缩 dossier
→ 同一投资经理 Agent 完整浏览一批
→ pass / watch / send_to_analyst
→ 少数候选由单公司研究员解决决定性问题
→ scoped research → deep research
→ 独立承保 / challenger
→ 最新行情下的组合综合
```

默认批量 150 家。批量是上下文与恢复边界，不是投资容量。

## Baseline 与 Incremental

Baseline 处理冻结 universe 中缺少 manager-screen terminal 的公司。已验证的 legacy rapid-triage terminal 可作为兼容终态，但旧 rapid-triage workflow 不再生产新资产。

Incremental 只处理截止日前真实命中的财报、公告、价格、论点、date/TTL 或证据过期事件。触发器定义不是 hit。两条 lane 可交错，但同一 symbol 只能有一个活动写入者。

## 初筛事实源

每批仅创建：

```text
coverage/cn-a/manager-screen/{RUN_ID}/{BATCH_ID}/
  batch.json + seal
  packet.json + seal
  result.json + seal
```

- `batch.json`：冻结成员、scope/policy 绑定和行政顺序。
- `packet.json`：全批压缩 dossier、证据目录和统一 rubric。
- `result.json`：一次主 Agent provenance 与逐公司决策。

`pass` 和 `watch` 不写单公司 Markdown；它们的不可变事实源是封存 result。只有研究员开始正式研究后才写公司时间线。

## 恢复与幂等

- 同 batch ID、同 scope/policy/容量可重放；不同内容必须失败。
- 新 batch 自动排除已冻结成员、已完成初筛、正在运行和已进入更深层的公司。
- 同一 result 重放只修复 coverage 物化，不重写 seal，也不把已进入更深层的公司降级。
- `research_queue.jsonl` 是可恢复物化状态，不取代 scope、batch 或 result。

## 质量边界

Material error 只包括：

1. 证券身份错误；
2. 可核验事实错误；
3. 重大风险遗漏；
4. decision contract 违规。

投资经理与 reviewer 对 `pass/watch/send_to_analyst` 的观点差异不是自动错误。程序对 schema、整批覆盖、顺序、证据引用和禁止字段做 100% 校验。可选校准抽样不阻塞批次，也不生成递归 correction。

## 研究员与更深阶段

研究员一次只处理一家公司，只解决投资经理列出的决定性问题。研究员结果仍需真实来源、反证、正常化盈利/现金桥接和 provenance。

只有完成 deep research 和结构化主张的公司才能进入独立承保。重大风险、重大分歧或潜在前五大仓位才购买 challenger。研究层不给组合操作。

## 命令

```bash
python -m trading_os coverage scope-freeze <run-id> --mode auto --scope-cutoff <timestamp>
python -m trading_os coverage scope-status <run-id>

python -m trading_os coverage manager-screen-freeze <run-id> <batch-id> --batch-size 150
python -m trading_os coverage manager-screen-record <run-id> <batch-id> --input <decisions.json>
python -m trading_os coverage manager-screen-status <run-id>

python -m trading_os coverage profile-status <cycle-id>
python -m trading_os coverage profile-compare <cycle-id> --stage quick_profile|scoped_research
python -m trading_os coverage profile-select <cycle-id> --stage quick_profile|scoped_research --decisions <decisions.json>
python -m trading_os coverage reconcile --check
```

以下命令只用于验证已封存旧资产，不得用于新 Goal：

```text
triage-freeze / triage-claim / triage-record / triage-compare / triage-finalize
quality-triage-* / allocate-research / apply-allocation / profile-finalize
```

## 进度与耗时

每个批次记录：

- dossier 生成耗时；
- 主 Agent 浏览与提交耗时；
- send_to_analyst 数量和比例；
- 研究员、深研、承保各自耗时；
- 验证与修复耗时。

不要用文件数量冒充进度。全市场进度以 scope 守恒和 manager-screen terminal 数量计算。
