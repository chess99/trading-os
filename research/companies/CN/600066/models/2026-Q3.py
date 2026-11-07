"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['owner_low', 'per_share'], 'round': 1}, 'high': {'path': ['base', 'per_share'], 'round': 1}, 'distributions': {'path': ['holder', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['holder', 'terminal_low']}, 'terminal_high': {'path': ['holder', 'terminal_high']}}
METADATA = {'symbol': 'CN:600066', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-21T19:21:00+08:00', 'valuation_note': '集团经营路径不变，逐年将母体自身盈利、来源宣派和存量现金释放、投资本金回收经母法律/现金门槛传至实际分配；不得集团余额直接加回。核心23.1—30.5元，原直接资产桥25.2—32.8元高估可达性。独立辅助24.3—32.7元不含同样分配时点约束。 母自主提储及来源缓冲至Y10；结构压力7亿元净投入永久保持，不因零增长消失。', 'return_model_note': '五年DPS2/2.1/2.2/2.3/2.4不变；TV5为Y6后实际持有人现金现值27.73632305—32.77299507。母强制储备已满，自主10%及来源经济缓冲至Y10，Y5/Y20/永久边界重算；来源40%盈利+10%存量为有锚经济预算。有限投资净回收不等于利润，初始及后期现金批次均检验真实付款；结构情景永久7亿净投入，弱上划不自动恢复。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
