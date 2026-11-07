"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value'], 'round': 1}, 'high': {'path': ['scenarios', 'core_high', 'value'], 'round': 0}, 'distributions': {'path': ['scenarios', 'base', 'dps5'], 'take': 5}, 'terminal_low': {'path': ['scenarios', 'core_low', 'tv5'], 'round': 2}, 'terminal_high': {'path': ['scenarios', 'core_high', 'tv5'], 'round': 2}}
METADATA = {'symbol': 'CN:300896', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T13:35:00+00:00', 'valuation_note': '主法逐主体收入、利润、资本、补亏储备与现金分配折现；核心两端资本成本11%/10%、成熟名义增长1%/2%、税后留存收益1%/2%、经营盈利中心的97%/103%。未来五年净新增经营资本8.345亿元，成熟母公司EBIT率Y1—Y5从54%降至51%，Y6—Y10再降4个百分点；Y6起普通股分配正常可归属收入85%加超额现金12%。精确当前端点26.5257/34.0204元，TV5为34.8751/45.1494元，终值现值占78.0%/82.4%。独立正常化盈利容量辅法24.5—27.1元，采用8年低增长后12年衰减、18%更新投入，仍走同一现金桥；不平均。周期28.83、结构17.27、乐观36.28元不混入核心。无证券行情。', 'return_model_note': '五个截止日起滚动年度实际现金预算1.40/1.45/1.60/1.75/1.80元，核心两端同额并经母公司法定利润/可用现金封顶。302592061股包含10月20日已完成员工持股过户的库存股；无未来融资、注销假设。9月末金融资金45.2716亿元逐户分列，非Huons权益5.1209亿元Y6—10回收70%，Huons只估持股现金不再加含商誉账面值；留存获息与本金分配只计一次。母公司起始现金38.5亿、未分配43.5亿为明确预算，其他亏损及储备逐户处理，境内上划滞后一年/REGEN两年并预算5%税费，已宣派及到账分别入账。Y1偿债及旧租赁0.3187亿，少数分配与补资贯通；已付9月每股1元不列未来，也不重扣期末现金。第五年价值来自之后持续同一付款政策，不把现金余额直接加入TV。全部情景400/600/800年级数收敛；无三年终值或IRR。 非经营资金主体Y12预算合规清算/减资返还剩余本金，成本回收不增母利润，返还减滚动母权益成本的处置净损益入法定利润、税费付现，成本不重扣现金；审批延至Y25已测，不永久锁死。 所有600年度均保存9主体完整明细。0.31869亿元母承担为代偿资金预算非法律债务归属断言，52%子公司付款替代29.94元；treasury99.75%是H1披露权益比例代理而非余额归属事实，57.5%—100%范围已测。其母权益成本初始0.42051亿元按追加资本滚动，50%/150%成本预算已测；母起始UR43.5=约46.149-3.014+0.365，41/46范围不改变分配。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
