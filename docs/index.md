# Trading OS 文档

这里放系统设计、数据口径、策略实验记录、踩坑总结等。

## 入口
- [`context.md`](context.md)：背景、目标、约束、工作约定（新人/新会话先看这个）
- [`structure.md`](structure.md)：目录结构与归档规则（写文档前先看）
- [`plans/trading_os_mvp.md`](plans/trading_os_mvp.md)：当前 MVP 计划（阶段性路线图，原样归档）

## 数据
- [`data/conventions.md`](data/conventions.md)：数据口径与约定
- [`data/lake.md`](data/lake.md)：本地数据湖（DuckDB + Parquet）

## 运行维护
- [`ops/python_env.md`](ops/python_env.md)：Python 环境（推荐 3.12）

## 研究与回测
- [`research/backtest.md`](research/backtest.md)：回测口径（MVP）

## 执行与风控
- [`execution/paper_trading.md`](execution/paper_trading.md)：纸交易（MVP）

## 操作手册
- [`playbooks/journaling.md`](playbooks/journaling.md)：日常工作流：记录与复盘
