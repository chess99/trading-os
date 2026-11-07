"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'value', '0.105'], 'floor_step': 10}, 'high': {'path': ['cases', 'core_high', 'value', '0.105'], 'ceil_step': 10}, 'distributions': {'path': ['cases', 'base', 'annual'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['cases', 'base', 'terminal5', '0.11']}, 'terminal_high': {'path': ['cases', 'base', 'terminal5', '0.1']}}
METADATA = {'symbol': 'CN:300308', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-29T21:50:00+00:00', 'valuation_note': '主方法量价/现金分配：竞争加剧与领先执行在10.5%折现下分别189.05189730、335.30149691元，端点向外取十元。基准252.09259197元；独立客户资本预算×光学金额×参与份额、资本回报入口212.00363367元，不平均。核心长期毛利29%—34%，配套资本55%/48%；结构损坏103.93682774元只作反例。融资失败停止，不负现金续估。', 'return_model_note': '未来五个完整十二月实付普通股现金预算，非FCF或利润。第5年终值从同一基准完整状态继续逐年到180年、并延长240/300年，以10%—11%折现后续分红；当前现金和金融收益均仅在同一现金池计一次。期初权益股数1,172,256,578，含未归属奖励后第5年1,187,003,548股；库存股5653063股不分红且注销尚待程序。母公司旧应收股利收现不二次计利、内部借款face/备抵分列、RE先弥亏后法储；海外税费、少数及条件退出权保留。未来分配和第二批履约为预算而非法律保证，核心不靠内在价增发救助。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
