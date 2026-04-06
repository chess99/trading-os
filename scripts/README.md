# Scripts for one-off analysis, maintenance, and tooling runs.
# Input: repo data lake/configs/CLI args; output: console logs, artifacts, and side effects.
# Update rule: when files change here, update this README; update parent index if scope changes.

## DCA 定投
- `dca_backtest.py`: DCA 策略回测（命令行）
- `dca_backtest_ui.py`: DCA 回测 Tkinter 可视化界面
- `dca_compare.py`: 多品种定投方案对比分析
- `dca_scan_best.py`: 扫描定投最优品种
- `dca_scan_etf.py`: 扫描定投 ETF 品种

## 分析
- `quick_analysis.py`: 快速分析工具（ad-hoc）
- `analyze_without_realtime.py`: 离线分析（无实时价格）
- `backtest_multi_factor.py`: 多因子策略回测
- `daily_market_analysis.py`: 每日市场分析（已重构，待更新）
- `search_symbol.py`: 交易品种搜索

## 账户与持仓
- `check_account_status.py`: 账户状态检查
- `init_simulation_account.py`: 初始化模拟账户
- `reset_account.py`: 重置账户状态
- `fix_zero_positions.py`: 修复零持仓问题
- `visualize_account.py`: 账户可视化

## 系统
- `system_status.py`: 系统状态快照
- `system_maintenance.py`: 系统维护任务
