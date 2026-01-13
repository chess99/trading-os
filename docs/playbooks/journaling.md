# 日常工作流：记录与复盘（Playbook）

## 目标
让每一次“想法→交易→结果”都可检索、可复现、可迭代。

## 1. 新想法 / 新交易前（写决策）
从模板复制：
- `journal/decisions/TEMPLATE.md`

建议命名：
- `journal/decisions/YYYY-MM-DD_SYMBOL_简短标题.md`

关键要求：
- 写清楚 **入场/退出/失效条件**
- 写清楚 **假设**（为什么可能赚钱）与 **反例**
- 记录你将运行的回测命令或 notebook 路径

## 2. 纸交易执行（生成可追溯日志）
示例：

```bash
python -m trading_os paper-run-sma --symbol NASDAQ:TEST --fast 5 --slow 20 --stop-loss 0.1
```

会生成事件日志（JSONL），路径类似：
- `artifacts/paper/events_NASDAQ_TEST.jsonl`

把这个路径粘到你的决策记录里（便于后续复盘定位事实）。

## 3. 交易结束/阶段结束（写复盘）
从模板复制：
- `journal/reviews/TEMPLATE.md`

建议命名：
- `journal/reviews/YYYY-MM-DD_SYMBOL_复盘.md`

关键要求：
- 引用：决策记录 + 事件日志 + 回测证据
- 结论必须落为 **可执行改进动作**（代码/参数/流程）

