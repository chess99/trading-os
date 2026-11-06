"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'pv_per_share'], 'round': 2}, 'high': {'path': ['scenarios', 'core_high', 'pv_per_share'], 'round': 2}, 'distributions': {'path': ['holder_terminal_paths', 'high', 'annual'], 'column': 'distribution_per_share', 'take': 5, 'round_items': [4, 1, 4, 4, 4]}, 'terminal_low': {'path': ['holder_terminal_paths', 'low', 'terminal_5_per_share'], 'round': 2}, 'terminal_high': {'path': ['holder_terminal_paths', 'high', 'terminal_5_per_share'], 'round': 1}}
METADATA = {'symbol': 'CN:300910', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T21:55:00+00:00', 'valuation_note': '主方法为十年逐年普通股现金和独立第十年持续经营终值；核心低高端同步重算利润率、折现率及再投资回报。辅助历史正常化经营收益加项目及金融资本17.93—26.62元，其中点较主方法高约37.6%，反映较快正常化和较少兑现摩擦，因此不平均。无证券价格输入。', 'return_model_note': '未来连续五个十二个月实际现金预算0.1583、0、0.0945、0.8486、0.9415元/股；第五年价值20.87—27.60元来自固定基准前五年全部现金/债务/营运资本/基金/母留存及储备状态后，仅第六年起改变利润率和尾期资本成本/再投资回报的完整重算；不借用从第一年变化的核心经济情景终值，非当前价值替身。采用全部已发行383.042277百万股，假设库存股先释放、不增加现金；既有主体99.5%经济归属和沙特60%对应利润及资本。经济预算不是逐法人法律可分配认证，需新增有限授信、现金上划和实际批准。180百万元必要经营现金为硬约束，不足即失败；必要现金缺口与实际未付请求分开，保留失败前分配及后续成本，全部PV/TV为null。注册资本383.042277百万元由7月31日新执照确认，资本公积转增不带来新现金。无第三年终值或现价回报。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
