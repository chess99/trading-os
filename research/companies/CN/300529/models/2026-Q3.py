"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_range', 'low']}, 'high': {'path': ['core_range', 'high']}, 'distributions': {'path': ['holder_distributions'], 'take': 5}, 'terminal_low': {'path': ['holder_terminal_range', 'low']}, 'terminal_high': {'path': ['holder_terminal_range', 'high']}}
METADATA = {'symbol': 'CN:300529', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T21:33:00+00:00', 'valuation_note': '以五年实际分配加第五年普通股经营/净现金/投资权益现值为主，展开6—10年及11年稳态；股权成本9.5%—10.5%、远期新增资本回报16%—20%。辅法第三年前瞻NOPAT14—18倍在t2同日权益桥并加前两年分配现值，14.42—17.72元，中枢高28.95%，主法同桥隐含11.62倍；高持久性证据不足，不平均。周期11.64、结构4.52、乐观18.14元不并入核心。', 'return_model_note': '五年分配是母法定利润与真实现金双约束下60%经济净利润预算，先弥亏再提法定公积，不依赖未知子股利。转债剩余面值999829200元按110%首年兑付含末息，外部股份774362581股，未来未假定转股/新增激励。爱多多少数收购是首年预算，未成交路径持续扣少数现金和永久归属。年度分配从余额扣除，第五年经营含6—10年及11年稳态，金融本金另列且不重复资本化利息；终值范围在同一基准第五年状态下改变远期参数。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
