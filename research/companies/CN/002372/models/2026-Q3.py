"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'base', 'valuation', 0, 'pv']}, 'high': {'path': ['scenarios', 'base', 'valuation', 1, 'pv']}, 'distributions': {'path': ['scenarios', 'base', 'annual'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['scenarios', 'base', 'valuation', 0, 'tv5']}, 'terminal_high': {'path': ['scenarios', 'base', 'valuation', 1, 'tv5']}}
METADATA = {'symbol': 'CN:002372', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T20:00:00+08:00', 'valuation_note': '基准经营现金路径按10%与8.5%折现；不使用未经核实的现价；独立EPV交叉而非历史估值锚定。', 'return_model_note': '每一初始普通股；五年分配与TV5来自同一法律现金路径，TV5为Y6之后实际股利和依法按比例返本的Y5现值；总股本扣库存股，非直接现金加回。 非核心退出为含税费执行摩擦的净实现预算，权益法账面不等税基；额外JV7500万元税负边界实际重算。全部可行情景金融余资最终经真实分配或条件同比例资本返还实现，必要经营资本持续支持经营；不直接终值加本金。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
