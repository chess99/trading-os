"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 2, 'value_per_share'], 'round': 2}, 'high': {'path': ['cases', 3, 'value_per_share'], 'round': 2}, 'distributions': {'path': ['cases', 0, 'first5_dps'], 'take': 5, 'round_items': [4, 5, 5, 5, 5]}, 'terminal_low': {'path': ['cases', 0, 'terminal5_per_share'], 'round': 2}, 'terminal_high': {'path': ['cases', 1, 'terminal5_per_share'], 'round': 2}}
METADATA = {'symbol': 'CN:600285', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T09:15:56+00:00', 'valuation_note': '主法分主体普通股现金折现，首年收入40.50亿元、经营利润率23.4%，以后四年增长4%，至第20年增长衰减至0、利润率至22%；核心低高为增长3.5%/4.5%、利润率23.0%/24.0%、股权成本9.75%。辅助按贴剂量价和其他业务贡献独立入模，约15.58元，不平均。基金按有限合同、250m公司LP份额、200m剩余调用、2%认缴/未退成本费基、返本/8%单利优先/GP追补/80:20及税后实际母现金建模；正常、延后、损失路径在两法重算。基金不保证本金或优先回报，不按固定期限兑付面值；法定利润与实际付款受约束。', 'return_model_note': '年度桶约对应2027—2031年。567,115,486股含已发行限制性股，不扣库存股金额对应的假股份。母公司和子组依实际现金/法定利润限制，前五年普通股盈利80%加每年10%超额现金渐进分配；是预算非承诺，2026年已派1.10元不重复。TV5由相同基准前五年全部状态后的第6—240年现金折现，资本成本10%/9.5%；不同于当前核心经营参数区间。基金期初50m账面/税基为个别NAV未披露的条件估计，另45/55m账税差诊断。项目实现净收益、LP累计返本、历史已确认收益收现、GP及税款分别进母现金/RE；本金返回不增加利润。额外维护现金50m压力保持DA不动。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
