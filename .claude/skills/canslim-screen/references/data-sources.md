# CANSLIM 数据获取参考

## A 股财务数据（AKShare）

```python
import akshare as ak

# EPS（每股收益）历史数据
df = ak.stock_financial_benefit_ths(symbol="600000", indicator="按年度")
# 字段：净利润, 每股收益, 净资产收益率

# 季度 EPS
df = ak.stock_financial_benefit_ths(symbol="600000", indicator="按单季度")

# ROE 历史
df = ak.stock_roe_em(symbol="600000")

# 营收和净利润增速
df = ak.stock_financial_analysis_indicator(symbol="600000")
```

## 机构持仓数据

```python
# 基金持仓（最新季度）
df = ak.stock_institute_hold(symbol="600000", quarter="20241")
# 字段：基金名称, 持股数量, 持股市值, 占流通股比例

# 北向资金（外资）
df = ak.stock_hsgt_individual_em(symbol="sh600000")
# 字段：日期, 持股数量, 持股市值, 持股占比
```

## 行业比较数据

```python
# 行业内所有股票涨跌幅（用于判断 L 维度）
df = ak.stock_sector_spot(sector="白酒")  # 替换为对应行业

# 个股相对强度（近6个月涨幅 vs 行业均值）
# 手动计算：个股涨幅 / 行业平均涨幅
```

## 大盘方向数据

```python
# 上证指数日线
df = ak.stock_zh_index_daily(symbol="sh000001")

# 北向资金净流入（大盘情绪指标）
df = ak.stock_hsgt_north_net_flow_in_em()

# 融资余额（市场杠杆水平）
df = ak.stock_margin_sse(date="20240101")
```

## 常用筛选条件（CANSLIM 标准）

```python
# 筛选 EPS 增长 > 25% 的 A 股
# 1. 获取所有 A 股列表
stocks = ak.stock_zh_a_spot_em()

# 2. 批量获取 EPS 数据（注意速率限制）
# 建议分批处理，每次 50 只

# 3. 过滤条件
# - 当季 EPS 同比增长 >= 25%
# - 年度 EPS 连续 3 年增长
# - ROE >= 17%
# - 机构持仓比例增加
```

## 注意事项

- AKShare 数据有时有延迟，财报数据以官方公告为准
- 季报时间节点：Q1（4月底）、Q2（8月底）、Q3（10月底）、年报（4月底）
- 分析时注意数据的发布时间，避免使用未公开数据（前瞻偏差）
- 部分接口需要 Tushare Token，参考 `.env.example`
