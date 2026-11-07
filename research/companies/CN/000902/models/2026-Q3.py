"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'pv_per_share'], 'round': 2}, 'high': {'path': ['scenarios', 'core_high', 'pv_per_share'], 'round': 2}, 'distributions': {'path': ['scenarios', 'base', 'rows'], 'column': 'dividend_per_share', 'take': 5}, 'terminal_low': {'path': ['scenarios', 'core_low', 'terminal_year5_per_share'], 'round': 2}, 'terminal_high': {'path': ['scenarios', 'core_high', 'terminal_year5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:000902', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T22:12:00+00:00', 'valuation_note': '主方法为十年普通股现金和持续经营价值，核心低高端毛利偏移-0.25/+0.25个百分点、资本成本10.5%/9.5%；精确现值10.879247/13.190364元。长期增长1%、ROIC10%，矿山增益退出；辅助第二年EV/EBIT权益桥10.61—13.54元。未使用证券价格。', 'return_model_note': '基准转债现金偿付，实际股数1,254,734,903股；五年分配为0/0.35/0.45/0.60/0.70元，受母公司现金、宣派和利润条件限制。第五年价值由6—10年现金与10年末持续经营权益折算，精确端点15.538288/18.408694元。利润与必要资本均按普通经济归属96%预算，母公司转债和集团外担保全额承担；已派股利从现金扣除，必要现金不另加，金融资产有限退出及剩余现金计价，股数稀释与债务免偿另算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
