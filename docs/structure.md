# 目录结构与归档规则

这份文档用于回答两个问题：
- **东西应该放哪**（避免仓库变成“杂物间”）
- **Git 应该追踪哪些目录**（空目录如何保留）

## 一句话原则
- **`docs/`** 放“系统级、可被长期引用的共识/规范”
- **`docs/plans/`** 放“阶段性计划/路线图/里程碑”（会过期，但要保留历史）
- **`journal/`** 放“交易层的个人决策与复盘”（更频繁、更主观）
- **`data/` / `artifacts/`** 放“本地数据与产物”（默认不入库）

## 顶层目录

```text
trading-os/
  src/trading_os/      # 代码
  tests/               # 测试
  configs/             # 配置（不放密钥）
  notebooks/           # 可复现研究（实验性质）

  docs/                # 系统文档（长期有效）
  journal/             # 交易日志与复盘（个人）

  data/                # 本地数据（不入库）
  artifacts/           # 产物/报告（不入库）
```

## `docs/` 内部结构（建议）
- `docs/architecture/`：系统设计、模块边界、数据流
- `docs/data/`：数据口径（复权、时区、交易日历）、schema、质量检查
  - `docs/data/schemas/`：表结构定义与示例
- `docs/research/`：研究方法论、回测评估标准、指标定义
- `docs/execution/`：执行、订单状态机、风控规则说明
- `docs/ops/`：运行维护（定时任务、告警、密钥管理思路）
- `docs/adr/`：Architecture Decision Records（关键决策记录，解释“为什么这么选”）
- `docs/plans/`：阶段性建设计划（路线图/里程碑/迭代纪要）
- `docs/playbooks/`：操作手册（每日流程、排障、复盘流程）

## Git 如何“保留目录”
Git 不会记录空目录。为了让目录结构在初始化时就完整可见，我们在空目录里放入：
- `.gitkeep`（占位文件）或
- `README.md`（更推荐：顺便写清楚这个目录放什么）

本仓库会优先在关键目录放 `.gitkeep`，等内容增长后再替换成真实文档即可。

