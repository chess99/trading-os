"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'current_value']}, 'high': {'path': ['cases', 'core_high', 'current_value']}, 'distributions': {'path': ['cases', 'base', 'first5'], 'take': 5}, 'terminal_low': {'path': ['cases', 'core_low', 'year5_value']}, 'terminal_high': {'path': ['cases', 'core_high', 'year5_value']}}
METADATA = {'symbol': 'CN:300760', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T11:00:00+00:00', 'valuation_note': '主方法为产品收入—利润—资本—实体可分现金；核心10%/9.5%/9%要求回报。辅方法独立以正常化核心利润与新增资本回报建立经营入口，118.47元，不平均。180/720年真实延长尾期，无末年清算；结构压力49.10元另列，不用行情或倍数。', 'return_model_note': '五个周年截至2027—2031-10-29，实际每股现金4.5/4.9/5.3/5.7/6.1；Y5持续权益139.14—167.99来自同一路径后续分配，已付现金不再保留。1,211,799,431普通股；惠泰未来认款、参与分母和少数同步变化。接口method名称沿标准，无证券行情或IRR计算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
