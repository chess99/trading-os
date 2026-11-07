"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['results', 'core_low', 'value_per_share'], 'round': 2}, 'high': {'path': ['results', 'core_high', 'value_per_share'], 'round': 1}, 'distributions': {'path': ['results', 'base', 'distribution_5'], 'take': 5}, 'terminal_low': {'path': ['results', 'terminal_low_same_y5', 'terminal_y5'], 'round': 2}, 'terminal_high': {'path': ['results', 'terminal_high_same_y5', 'terminal_y5'], 'round': 2}}
METADATA = {'symbol': 'CN:603871', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T11:00:00+00:00', 'valuation_note': '方法一分部经营→同主体税/投入→母子法律现金桥为核心，低高经营假设形成5.79—7.40元，基准6.56元。独立经济输入的经营资本回报辅助法4.58—5.66元，基准5.10元，约22%差异不平均，反映成熟资本回报26%与核心35.7%的实质分歧。未读取证券行情。', 'return_model_note': '未来连续五个十二个月，已付2026-10-23中期分红不在其中；以同一基准Y5全部资产、债权、现金、储备及剩余合同状态冻结后再估低高终值。13.68008658亿完全稀释已发行股含未注销库存股，不计回购为持有人收入；无三年终值。贷款和优先按条件预算清偿，续作拒绝另列退出，未付债权保留。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
