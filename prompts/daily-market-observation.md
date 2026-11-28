# 每日市场观察

本文件已升级并纳入高频工具箱，完整可执行规范见 [prompts/on-demand/daily-brief.md](on-demand/daily-brief.md)。

核心原则保持不变：**每日观察与新闻过滤仅在外部对话消费，结果不写入本仓库，不自动更新公司状态、行业结论或宏观报告，不创建日报目录。** 执行时优先读取 `dashboard/public/data/decision-index.json` 中的既有宏观因子与公司改判条件（`thesis_breakers`），无足以改变中长期判断的新证据时直接报告“未发现足以触发改判的新证据”。
