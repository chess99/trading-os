历史研究可靠性评估（2026-10-23）

先读：历史研究可靠性评估.pdf，共13页；报告正文.txt为可检索纯文本。
逐股明细：data/7月买入名单241家.csv、data/逐股核对表.csv（UTF-8 BOM）。
冻结行情：2026-10-22；研究版本见data/manifest.json内五个固定Git提交。

范围：全量历史版本与价格统计、186家既有复核记录分类、关键案例9份原件复核。
不是5,435家公司全部重新完成基本面研究，也不是实际账户收益回测。
没有更改正式公司研报、覆盖状态、队列或筛选池。

复现：
1. 使用Python3运行collect.py和reports.py恢复固定提交的快照和正文。
2. 本次原始行情响应仍保存在聊天项目目录research-audit-2026-10-23/data/market.jsonl.gz。
   把该文件放入本目录data后运行analyze.py，可复现冻结统计。
   如重新联网采集，先运行market.py，再用MARKET_REPAIR=1运行market.py，最后运行sina_fallback.py。
   重新抓取可能遇到供应商历史更正；不保证与冻结结果逐字相同。
3. 使用带reportlab、pypdf的Python运行sources.py与build_report.py。
   sources.py核对原件，build_report.py重建PDF和中文CSV；默认使用macOS STHeiti字体。

方法：个股采用税前现金分红、不再投资、送转联动的简单总回报。
相对沪深300只比较价格回报，避免个股含息与指数不含息混比。
旧估值自原资料截止起逐项扣已分配现金并调整股数。
没有统一预测期限，因此未构造一个全库研究正确率。
data/recorded-corrections.json的32家属于既有复核记录的明确纠错下限，非新一轮逐公司全面验收。

验证：data/verification.json；8家重点公司腾讯/新浪收盘价一致；PDF已逐页渲染检查。
大体量原件、报告正文快照和行情响应未重复写入Git。
