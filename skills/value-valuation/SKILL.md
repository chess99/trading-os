---
name: value-investing-valuation
description: |
  Value Investing 体系程序化估值。封装 `python -m trading_os valuation` CLI 命令。
  触发词："估值分析"、"DCF 估值"、"内在价值"、"SOTP 估值"、"分部估值"、"安全边际"。
  通常由 value-system 在基本面研究后调用，也可以单独使用。
---

# Value Investing Valuation — 程序化估值

封装 Trading OS 的估值命令，禁止 LLM 口算估值。

**铁律**：所有估值必须通过程序计算，不允许 LLM 直接给出估值数字。

---

## 可用命令

```bash
# DCF 估值（现金流折现）
python -m trading_os valuation --ticker SSE:600519 --method dcf

# 相对估值（PE/PB 历史分位）
python -m trading_os valuation --ticker SSE:600519 --method relative

# 分部估值（多业务公司）
python -m trading_os valuation --ticker SSE:600519 --method sotp

# 敏感性矩阵（DCF 参数敏感性分析）
python -m trading_os valuation --ticker SSE:600519 --method dcf --sensitivity

# 综合估值（三种方法综合）
python -m trading_os valuation --ticker SSE:600519 --method all
```

---

## 使用流程

1. 确认标的代码（格式：`SSE:600519` 或 `SZSE:000858`）
2. 选择估值方法：
   - **DCF**：适合稳定现金流的公司（消费、金融、公用事业）
   - **相对估值**：适合有可比公司的行业
   - **SOTP**：适合多业务板块的集团公司
3. 运行命令，读取输出
4. 结合 fundamental-research 的护城河评估，判断安全边际

---

## 安全边际判断

```
安全边际 = (内在价值 - 当前价格) / 内在价值

≥ 30%：有吸引力的买入机会（格雷厄姆标准）
15-30%：合理，可以考虑买入
< 15%：等待更好价格
< 0%（高估）：不买入，持有者考虑减仓
```

巴菲特的修正：对于优秀的护城河公司，可以接受更低的安全边际（15-20%），因为护城河本身提供了额外的保护。

---

## 注意事项

- 估值是艺术，不是科学。程序输出是起点，不是终点
- 不同方法可能给出不同结果，取区间而非单点
- 对于高增长公司，DCF 对增长率假设极度敏感，运行敏感性矩阵必不可少
- 周期性行业（钢铁、煤炭）不适合用 DCF，用 PB 或周期底部 PE
