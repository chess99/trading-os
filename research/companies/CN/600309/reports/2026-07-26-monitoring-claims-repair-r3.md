<!-- trading-os-report-meta
{
  "schema_version": 2,
  "report_id": "CN-600309-2026-07-26-monitoring-claims-repair-r3",
  "report_type": "monitoring_update",
  "symbol": "CN:600309",
  "as_of": "2026-07-26",
  "information_cutoff": "2026-07-22T15:30:00+08:00",
  "price_snapshot_id": null,
  "policy_versions": {
    "industry.manufacturing": "1.0.0",
    "underwriting.default": "1.1.0"
  },
  "agent_id": "codex-gpt-5",
  "predecessor_reports": [
    "CN-600309-2026-07-22-initial-research-v2"
  ],
  "sealed_artifacts": [
    "evidence/CN-600309-2026-07-22-initial-research-v2-research-claims-r3.json"
  ],
  "source_manifest": "evidence/CN-600309-2026-07-26-monitoring-claims-repair-r3-sources.json"
}
-->
# 公司研究：万华化学（CN:600309）

## 上一轮判断复盘

2026年7月22日初研的正文、原始结构化主张和来源清单完整；随后为半盲承保脱敏生成的`research-claims-r2.json`中，C9与C11的部分中文被错误写成连续问号。旧r2已封存，不能覆盖或删除，因此历史承保将两项主张标记为不可测试是正确处理。

本次只修复未来批次的可信输入，不重新研究公司，也不改变初研评级、估值、买入观察区、触发器或既有承保结果。

## 新信息

没有新增公司经营、财务、行业、行情或治理信息。信息截止点仍为2026年7月22日15:30。

修复依据是仓库中未损坏的原始同ID主张，以及生成r2时留下的确定性转换记录。该记录完整保存了脱敏后C9、C11的目标文本、验证指标、证伪条件和来源ID，因而无需根据上下文猜写。

## 判断变化

投资判断没有变化。新封存的r3仅恢复r2原本要表达的脱敏主张：

- C9恢复2025年日常关联交易金额、审议程序、定价和关联应收回款的核验要求。
- C11恢复对MDI、TDI、石化和新材料分别正常化，单列维护性资本开支、净债务、新项目ROIC和周期敏感性的独立承保要求；2026H1利润仍只作为情景证据，不能直接年化。

## 证据更新

`research-claims-r3.json`以r2为基底，仅修复C9和C11的损坏字段；C1至C8、C10、decision对象及S1至S12来源保持不变。S13行情和S14公告索引仍按原脱敏规则排除，避免把初研价格答案或发现入口带入半盲包。

r3已经过脱敏主张包构建探针，未发现`decision_language`或`decision_value`泄漏，并由项目封存工具写入不可变JSON及seal。旧原始版、旧r2、旧seal和所有既有underwriting产物均保留不动。

## 跟踪触发器

沿用公司`meta.json`中的全部现有触发器，本次不新增、不删除、不调整阈值。2026年半年报披露后的分系列毛利、现金流、净债务、维护性资本开支和项目ROIC仍是下一次基本面复核重点。

## 风险

- r3只供修复完成后的未来批次使用，不追溯改写任何已冻结或已封存批次。
- 旧r2仍含乱码，任何直接指定旧文件的流程都应继续失败或降级，不能把r3视为对旧承保审计轨迹的改写。
- 本次没有新增一手披露，不能据此提高证据置信度或改变投资结论。

## 来源

外部事实来源完全沿用2026年7月22日初研的S1至S12一手公告，详见`evidence/CN-600309-2026-07-26-monitoring-claims-repair-r3-sources.json`。修复差异可由原始`research-claims.json`、损坏的`research-claims-r2.json`、生成r2时的确定性转换记录与新封存r3相互核对。
