---
name: value-investing-valuation
description: |
  Value Investing 体系估值入口。触发词："估值分析"、"DCF 估值"、"内在价值"、"SOTP 估值"、"分部估值"、"安全边际"。
  通常由 value-system 在基本面研究后调用，也可以单独使用。
---

# Value Investing Valuation

当前估值产物通过 ResearchStore-backed company research recipe 生成，不再使用独立估值 CLI。

## 可用命令

```bash
python -m trading_os research company SSE:600519 --template value --as-of YYYY-MM-DD
```

## 使用流程

1. 确认标的代码为 `SSE:600519` / `SZSE:000858` 这类 canonical symbol。
2. 运行 company research recipe。
3. 读取 `data/research/runs/{run_id}/manifest.json` 和 `report.md`。
4. 在回复中说明估值口径、关键假设、数据缺口和置信度。

## 规则

- 不允许 LLM 口算估值数字。
- 报告中的估值区间必须来自 recipe 输出或明确标注为待补充。
- 缺少分部、现金流或一致预期数据时，必须降低置信度并写入口径限制。
