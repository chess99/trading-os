"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['attribution_bounds', 'core_low_past0_current0', 'pv'], 'round': 2}, 'high': {'path': ['attribution_bounds', 'core_high_past1_current0', 'pv'], 'round': 2}, 'distributions': {'path': ['holder_conditionals', 'core_high', 'distributions'], 'take': 5, 'round_items': [5, 6, 6, 6, 6]}, 'terminal_low': {'path': ['holder_conditionals', 'core_low', 'terminal_year5'], 'round': 2}, 'terminal_high': {'path': ['holder_conditionals', 'core_high', 'terminal_year5'], 'round': 1}}
METADATA = {'symbol': 'CN:688188', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T12:56:00+00:00', 'valuation_note': '真实法人分配与间接渠道分离；项目Y8有限结项治理预算进入核心，Y10/15延误及有成本同比例减资另算；无价格IRR。', 'return_model_note': '五年实际普通股现金，首年包含已宣派未付0.582元；第五年终值继续逐主体、少数和间接渠道全期限现金递推。起始405.984426百万股含已登记427083股及9/30已收认购现金，不重复追加；剩余计划按真实公司OR门槛、个人/任职/资格及预留期限分期，派息调价，四年末409.294880百万股。已分配现金不留在终值；未来股份支付同步进入法律利润，真实条件失败不递延；历史及9M归母SBC精确归属未知，核心按已知费用全部归母的上界条件预算，0–100%归属组合另完整检验。未来归属及预留授予均非承诺。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
