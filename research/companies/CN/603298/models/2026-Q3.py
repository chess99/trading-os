"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['core_low', 'current_value_per_share'], 'round': 1}, 'high': {'path': ['core_high', 'current_value_per_share'], 'round': 1}, 'distributions': {'path': ['base', 'rows'], 'column': 'dps', 'take': 5}, 'terminal_low': {'path': ['core_low', 'year5_value_per_share'], 'round': 1}, 'terminal_high': {'path': ['core_high', 'year5_value_per_share'], 'round': 1}}
METADATA = {'symbol': 'CN:603298', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T20:19:55+00:00', 'valuation_note': '主方法为十年普通股分配及持续经营价值，核心同一路径18.220896/22.167450元：增长8%逐降3%、金融前归属制造率10.5%升11%后回落，必要再投及24.55亿项目完整支付；尾期增长2.5%、资本成本10.5%/9.5%、新增回报9.5%/11.5%。辅助正常化增长留存及逐笔两年延迟兑现法14.075868—16.908590元，中枢低约23%因不预奖扩张盈利，不平均两法，情景包络不充当核心区间。', 'return_model_note': '五项为未来五完整周年税前普通股实际现金预算而非承诺或FCF。第五年末25.454638—30.418058元由第6—10年分配及第十年权益独立折回。基准13.09812049亿股，对拟议债券预算第1年初发行、第6年末还本六期息；第三年初转股替代同步取消债并增股、提公积，自筹路径另算。集团CCE扣必要流动性和估计少数金融归属，金融债单列，经营少数不重复扣；联营股利不重复利润，金融本金十年返还，必要资本继续运营。母有符号利润先弥亏后公积，现金底线/募集专户/偿债准备与法定容量同时约束。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
