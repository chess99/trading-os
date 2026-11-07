"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['models', 'core_low', 'ri_per_share'], 'round': 1}, 'high': {'path': ['models', 'core_high', 'ri_per_share'], 'round': 1}, 'distributions': {'path': ['models', 'base', 'distributions'], 'take': 5, 'round_items': [4, 4, 4, 4, 4]}, 'terminal_low': {'path': ['models', 'holder_terminal_low', 'ri_per_share'], 'round': 4}, 'terminal_high': {'path': ['models', 'holder_terminal_high', 'ri_per_share'], 'round': 4}}
METADATA = {'symbol': 'CN:002142', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:15:00+00:00', 'valuation_note': '核心为资产负债利差—拨备—双层资本与法律分配折现，贷款收益率3.73%-3.83%、成本收入比31.5%-29.5%、净核销0.64%-0.56%、资本成本11%-10%给39.0500-55.7287元。辅助独立普通股ROE 13.2%逐降10.5%的剩余收益约43.7194元；不平均。资产五年10%降6%、十年后降3%，300年现金及500年延长验证，无行情锚；结构性压力不纳入核心区间。', 'return_model_note': '五年分配按基准经营逐年扣减普通股权益；Y1含11月5日0.4元，不重复计入7月已付0.9元。9月报表至截止29天为研究预算桥。股数6,603,590,792股；扣少数与408.25亿元其他权益工具，优先分配单列。Y5两端从同一基准Y5完整状态继续运行，得到54.5758-75.2467元；不是复制当前区间。母行利润份额、子公司上划及未来法律可用余额为证据约束预算而非认证，已检验无上划、母行利润池减半、资本提高与融资失败。 r2逐工具区分宣告、经济归属与现金：stub现金0、10月29日已宣告应付157.625百万元；Y1现金1047.825，期末同额优先股应付为持续宣告预算。经济应计83.251849不重复扣权益；完整现金/应付/资本桥见正文及模型。结构性增速请求4%于15年降2%，首年资本压至2.986%，第二年恢复3.857%后下降。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
