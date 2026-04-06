# Scripts for one-off analysis, maintenance, and tooling runs.
# Input: repo data lake/configs/CLI args; output: console logs, artifacts, and side effects.
# Update rule: when files change here, update this README; update parent index if scope changes.

- `analyze_without_realtime.py`: analyze holdings without realtime pricing.
- `backtest_multi_factor.py`: run multi-factor backtest for research.
- `check_account_status.py`: check account status and key balances.
- `daily_market_analysis.py`: generate daily market analysis.
- `daily_routine.py`: run daily automation routine.
- `data_reliability_check.py`: validate data lake reliability.
- `dca_backtest_ui.py`: UI tool for DCA backtest comparisons.
- `execute_trade.py`: execute trade via standard flow.
- `execute_trade_v2.py`: execute trade via updated flow.
- `fix_zero_positions.py`: clean up zero-quantity positions.
- `init_simulation_account.py`: initialize a simulation account.
- `quick_analysis.py`: quick analysis utility for ad-hoc checks.
- `reset_account.py`: reset account state for testing.
- `system_maintenance.py`: run system maintenance tasks.
- `system_status.py`: report system status snapshot.
- `test_capital_allocation.py`: test capital allocation logic.
- `test_decision_log.py`: test decision logging.
- `test_factor_data.py`: test factor data ingestion.
- `test_proxy.py`: test proxy configuration.
- `test_realtime_price.py`: test realtime price retrieval.
- `test_stock_screener.py`: test stock screening pipeline.
- `track_positions.py`: track positions over time.
- `visualize_account.py`: visualize account metrics.
