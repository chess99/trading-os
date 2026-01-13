# 决策记录与复盘（Journal）

建议每一次策略想法、每一次入场/离场、每一次重大判断都留下可检索记录。

后续我们会提供模板：
- 决策记录（当时信息、理由、预期、无效条件）
- 交易复盘（结果、偏差、改进动作）

模板目录：
- `journal/decisions/`：决策记录
- `journal/reviews/`：复盘记录

## 建议命名规则（方便检索）
- 决策：`journal/decisions/YYYY-MM-DD_SYMBOL_简短标题.md`
- 复盘：`journal/reviews/YYYY-MM-DD_SYMBOL_复盘.md`

## “研究→交易→复盘”如何串起来
- **研究/回测**：在决策记录里写明你使用的回测命令或 notebook 路径
- **纸交易**：运行 `paper-run-sma` 会生成事件日志（JSONL），把其路径粘到决策/复盘里
- **复盘**：在复盘模板里引用对应的决策记录 + 事件日志 + 回测证据

