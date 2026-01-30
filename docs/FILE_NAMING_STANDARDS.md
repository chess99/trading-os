# 文件命名规范

**版本**: 1.0
**日期**: 2026-01-30
**状态**: ✅ 已实施

---

## 🎯 目标

建立统一的文件命名规范,使文件:
- 易于查找和排序
- 清晰表达内容
- 便于版本管理

---

## 📋 命名规则

### 1. 报告文件

**格式**: `YYYY-MM-DD_<类型>_<描述>.md`

**示例**:
```
2026-01-30_ralph_loop_iteration_8.md
2026-01-30_current_status.md
2026-01-30_visualization_system.md
```

**类型标识**:
- `ralph_loop_*`: Ralph Loop迭代报告
- `current_status`: 当前状态报告
- `progress_*`: 进展报告
- `trade_*`: 交易报告
- `analysis_*`: 分析报告

### 2. 数据文件

**格式**: `YYYYMMDD_HHMMSS_<类型>_<描述>.<ext>`

**示例**:
```
20260130_162242_equity_curve.csv
20260130_162242_trades.csv
20260130_162242_equity.png
```

**类型标识**:
- `equity_curve`: 权益曲线数据
- `trades`: 交易记录
- `holdings`: 持仓数据
- `backtest_*`: 回测结果

### 3. 脚本文件

**格式**: `<动词>_<对象>.py`

**示例**:
```
check_account_status.py
backtest_multi_factor.py
visualize_account.py
execute_trade.py
```

**命名原则**:
- 使用动词开头
- 清晰描述功能
- 使用下划线分隔

### 4. 模块文件

**格式**: `<名词>.py`

**示例**:
```
capital_allocation.py
realtime_price.py
stock_screener.py
account.py
```

**命名原则**:
- 使用名词
- 描述模块功能
- 单数形式

---

## 🔧 实施指南

### 新建文件

创建新文件时,严格遵循命名规范:

```python
# 报告文件
timestamp = datetime.now().strftime("%Y-%m-%d")
filename = f"{timestamp}_analysis_market_overview.md"

# 数据文件
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{timestamp}_backtest_results.csv"
```

### 重命名现有文件

对于不符合规范的文件,逐步重命名:

1. 识别不规范文件
2. 确定新名称
3. 更新所有引用
4. 执行重命名

---

## 📂 目录结构

```
trading-os/
├── data/
│   ├── accounts/          # 账户数据
│   ├── backtest_results/  # 回测结果 (YYYYMMDD_HHMMSS_*)
│   ├── decisions/         # 决策记录 (YYYYMMDD_*)
│   ├── reports/           # 数据报告 (YYYYMMDD_*)
│   └── visualizations/    # 可视化图表 (YYYYMMDD_HHMMSS_*)
│
├── docs/
│   ├── reports/           # 文档报告 (YYYY-MM-DD_*)
│   ├── iterations/        # 迭代文档
│   └── guides/            # 使用指南
│
├── scripts/               # 工具脚本 (<动词>_<对象>.py)
│
└── src/trading_os/        # 源代码模块 (<名词>.py)
```

---

## ✅ 检查清单

创建新文件前,检查:

- [ ] 文件名包含日期(如果是报告或数据文件)
- [ ] 日期格式正确(YYYY-MM-DD或YYYYMMDD_HHMMSS)
- [ ] 使用下划线分隔,不使用空格或特殊字符
- [ ] 类型标识清晰
- [ ] 描述准确简洁
- [ ] 扩展名正确

---

## 🚫 反例

**不推荐的命名**:
```
report.md                    # 缺少日期和描述
final report.md              # 包含空格
报告-2026.md                 # 使用中文和特殊字符
2026-1-30_report.md          # 日期格式不规范(月份应为01)
backtest.csv                 # 缺少时间戳
test123.py                   # 名称不清晰
```

**推荐的命名**:
```
2026-01-30_ralph_loop_iteration_8.md
20260130_162242_equity_curve.csv
backtest_multi_factor.py
capital_allocation.py
```

---

## 📊 命名规范效果

### 之前
```
docs/reports/
├── report.md
├── final report.md
├── progress_report_2026-01-30_pm.md
└── trade_report_2026-01-30.md
```

### 之后
```
docs/reports/
├── 2026-01-30_current_status.md
├── 2026-01-30_ralph_loop_iteration_8.md
├── 2026-01-30_progress_afternoon.md
└── 2026-01-30_trade_summary.md
```

**优势**:
- ✅ 按日期自动排序
- ✅ 清晰的文件类型
- ✅ 易于查找
- ✅ 便于版本管理

---

## 🔄 维护

### 定期检查

每次Ralph Loop迭代时:
1. 检查新增文件命名
2. 识别不规范文件
3. 逐步重命名

### 自动化工具

可以创建脚本自动检查命名规范:

```python
def check_naming_convention(filepath: Path) -> bool:
    """检查文件命名是否符合规范"""
    name = filepath.name

    # 报告文件应以日期开头
    if filepath.suffix == '.md' and 'reports' in str(filepath):
        return re.match(r'^\d{4}-\d{2}-\d{2}_', name) is not None

    # 数据文件应包含时间戳
    if filepath.suffix in ['.csv', '.parquet']:
        return re.match(r'^\d{8}_\d{6}_', name) is not None

    return True
```

---

## 📚 参考

- [PEP 8 - Python命名规范](https://pep8.org/#naming-conventions)
- [Google Style Guide](https://google.github.io/styleguide/)
- 项目内部最佳实践

---

## 🎉 总结

统一的文件命名规范:
- ✅ 提升可维护性
- ✅ 便于团队协作
- ✅ 减少混淆
- ✅ 提高效率

**严格遵守命名规范,让系统更专业!**

---

**Trading OS - 基金管理AI系统**
**规范让系统更专业!** 📁
