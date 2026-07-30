# 全市场初筛 Playbook

## 原则

初筛回答的是“现在是否值得购买下一小时研究信息”，不是完整估值，也不是买卖建议。

全市场初筛由同一投资经理 Agent 批量完成。程序可以压缩数据、冻结顺序和校验输出，但不能替 Agent 做业务理解和研究价值判断。

## 行政 intake

可以决定处理顺序的字段：

- 已观察事件的紧急度；
- 逾期和等待时间；
- 是否缺少当前 manager-screen terminal；
- scope intake ordinal 和 symbol 稳定顺序。

不得用于剥夺初筛资格：

- PE、PB、ROE 或任何机械因子；
- 小市值、低流动性、利润正负；
- 行业、风格或旧评级；
- 完成先后。

## 压缩 dossier

packet 对每家公司提供：

- 证券身份、行业、价格、市值和基础估值快照；
- 主营摘要、近三年收入/利润/扣非利润/经营现金流和最新中期数据；
- 现金、有息债务、应收、存货、商誉、合同资产与审计意见；
- 数据缺口；缺失不是静默排除理由，而是降低置信度或形成决定性问题；
- prior screening 与 queue 摘要；
- 已有公司时间线的最新指针、承保/估值摘要和触发器；
- 可引用的 evidence ID。

投资经理可对少数信息不足项补查一手来源，并在 `additional_evidence` 中记录 URL、访问时间和 symbol。不要为了每家公司都查完整年报而把初筛变成深研。

## 统一 rubric

对每家公司快速回答：

1. 业务与普通股股东现金路径是否能大致理解；
2. 生存、治理、资本结构、会计或少数股东权益是否有明显阻断；
3. 正常化盈利与现金转换有没有可信轮廓；
4. 当前价格大致隐含什么；
5. 哪个问题最可能改变判断；
6. 下一小时研究的预期价值是否高于同批其他机会。

## 三条路由

### `pass`

当前研究信息价值低，停止继续花时间。必须写：

- 一句话理由；
- 决定性问题；
- 至少一个 filing/price/date/ttl/event/thesis 重启条件；
- 证据引用和置信度。

`pass` 不是永久垃圾标签。

### `watch`

业务可能可投，但需要等待价格、财报、事件或证据成熟。要求与 `pass` 相同，并明确等待什么。

### `send_to_analyst`

只有当下一小时研究很可能改变判断时使用。决定性问题必须足够具体，研究员能在有限预算内回答。该路由直接创建 `quick_profile` 预算，不再经过独立 L1 allocation。

## 禁止字段

初筛不得输出：

- rank、score、priority；
- expected return 精确排名；
- `buy_now`、组合操作、仓位；
- 静默跳过。

## 质量控制

- 程序 100% 校验 schema、整批覆盖、顺序、route、trigger、证据引用、provenance 和禁止字段。
- 路由分歧不自动等于事实错误。
- 校准抽样只检查身份、事实、重大遗漏和 contract；不阻塞正常批次。
- 发现 material error 后由正式研究或一次裁决更正；禁止 correction 套 correction。

## 守恒

```text
batch members = result decisions
scope screenable intake = completed + open batch + remaining unbatched + deferred current state
```

每批完成后运行：

```bash
python -m trading_os coverage manager-screen-status <run-id>
python -m trading_os coverage validate
```
