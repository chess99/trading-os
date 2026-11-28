# 完整行业研究

先读[工作台设计](../docs/design/investment-workbench.md)、[发布规则](../research/README.md)和[写作规范](research-writing.md)。明确研究对象、经济地域、上市市场、资料截止与真正需要解决的问题。中国行业研究以中国经营市场为分析主体，覆盖 A 股与港股相关竞争者，并按需对照[全球产业龙头参照表](../research/benchmarks/global-leaders.json)。

研究成果既供人快速把握“行业靠什么运转、现在处在周期哪一环、利润留在哪个环节”，也通过结构化状态 `industryState` 自动连接到个股决策台与轨道二筛选雷达。

## 一、目录分工与深耕节奏（重深度、去重复）

- **唯一标准分类**：使用[行业目录](../research/industries/catalog.json)的 34 个主题与[主题路由表](../research/industries/topic-routes.json)；旧 `research/industries/sectors/` 仅作路由与方法内部参考，不再新建平行版本。
- **拒绝“一天批量铺满”的浅层更新**：优先围绕两类核心主题保持**高质量半年度深度更新 + 按月指标维护**：
  1. **核心重仓与持仓关联行业**（如消费/白酒、家电与出海制造、电力电网与新能源、半导体与 AI 硬件、互联网与软件、医药医疗、金融与核心资源）；
  2. **处于景气拐点或深度出清尾声的行业**（直接作为[双轨筛选规范](screening/dual-track-screening.md)中轨道二选股的触发源）。
  其余行业在出现明显周期反转、政策剧变或个股研究需要时按需立项更新，不为“凑齐季度日历”生产低信息量短文。

## 二、行业机制与主导变量

沿“**最终需求 → 供给与库存 → 实现价格和成本 → 利润与现金 → 再投资与退出**”解释因果：
- 分别交代需求、有效供给与库存、盈利与现金、证券定价四组变量当前所处位置（它们可以异步：例如渗透率或装机高增，但产能过剩压低盈利）；
- 覆盖至少一个历史不利时期与失败退出案例；
- 明确未来 3–5 年的主导路径、替代解释与客观改判条件；
- 重点行业与拐点行业须同步按[指标规范](industry-indicators.md)在 `research/industries/<topic>/indicators.json` 维护可复算低频关键序列，并结合重点公司财报交叉验证行业结论是否出现样本背离。

## 三、发布与结构化 `industryState` 维护

达到完整研究深度后，按日期保存于 `research/industries/<topic>/reports/YYYY-MM-DD.md`，在 `research/publications.json` 登记（中国范围标记 `regionId: "cn"`）并**必须同步更新该主题最新条目的 `industryState` 元数据**：

```json
"industryState": {
  "cycleStage": "upcycle_tight | inflection_bottom | mature_stable | downcycle_clearing | overcapacity",
  "profitPoolTrend": "expanding | stable | contracting",
  "macroAlignment": "tailwind | neutral | headwind",
  "macroTransmission": "一句话说明宏观条件如何传到本行业需求、售价或成本",
  "inflectionCandidate": true,
  "keyDrivers": ["最关键的1-3个产业驱动变量"]
}
```

- `inflectionCandidate: true` 表示该行业存在结构性供需缺口、新技术渗透拐点或经历出清接近底部反转，将直接触发轨道二（`inflection_growth`）的个股重点扫描；
- `industryState` 由构建脚本自动投影到所有关联该主题的公司卡片与 `decision-index.json` 中，成为跨层决策的核心环境坐标。
