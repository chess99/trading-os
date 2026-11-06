"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'residual_income_value_per_share'], 'round': 14}, 'high': {'path': ['cases', 'core_high', 'residual_income_value_per_share'], 'round': 14}, 'distributions': {'path': ['cases', 'base', 'annual'], 'column': 'common_per_share', 'take': 5}, 'terminal_low': {'path': ['cases', 'core_low', 'tv5_per_share']}, 'terminal_high': {'path': ['cases', 'core_high', 'tv5_per_share']}}
METADATA = {'symbol': 'CN:603345', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T00:49:13+00:00', 'valuation_note': '主法是同一基准经营路径下按10%/8%资本成本折现实际普通股现金。Y6后增长与成熟利润率衰减，Y15后零增长；现金、资本、公积、RE与贷款持续滚动，核心不含截断清算。正式辅法从FY2024/2025去金融、补助、公允价值及处置后的正常经营收益独立起算，补齐鼎味泰并表期；维护及资本承诺另行投入、按资本回报兑现，值47.50元，不与主法平均、不另加合并净现金。', 'return_model_note': 'Y1—Y5为截止后五个完整年度、年末实际分配预算；TV5从相同Y5经营/资本/母子现金/法定RE/债务/少数状态推导未来分配。截止日分红权333288932减库存1160900=332128032股；基准Y1将既有库存全部用于员工激励，确认非现金SBC及RE/资本公积/库存转出，未来分红权333288932股，过往回购现金不重扣。已付H1现金不重复纳入，过期期权无行权。IFC/印尼为有条件未来预算，收购付款及少数归属同步；除此既有库存用途外，无新增回购/增发假设。主法不强制清算或无据减资，既有现金只通过受约束分配实现，不另加净现金；无固定现价IRR。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
