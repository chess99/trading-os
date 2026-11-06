"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['model_header', 'core', 'value_range', 'low']}, 'high': {'path': ['model_header', 'core', 'value_range', 'high']}, 'distributions': {'path': ['summary', 'core', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'core', 'tv5', 'low']}, 'terminal_high': {'path': ['summary', 'core', 'tv5', 'high']}}
METADATA = {'symbol': 'CN:300033', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T00:00:00+08:00', 'valuation_note': '分配折现主法；收入/利润率/税与必要资本不变，Y10起每五年交付50%多余金融现金，先返国内投资组合成本，剩余条件合格股利，2%费用；母Y15起有限有偿减资同步注销。原股权益组合归一，不重复加现金。资本政策为预测非批准事实。', 'return_model_note': 'V1五年接口。前五年股数0.75264bn、现金输入保持；Y5终值为当时每股原始持股组合后续所有分配/资本返还及剩余权益的折现值。Y15以后按比例有偿减资取消股数与注册、原股东比例不变，所有金额按原始股数归一；不得用注销后EPS乘原股数。必要资产/客户现金仍保留生息，组合成本/税基/费用独立。真实子留存/审批未知，经济实现预算需成立；无来源母现金冲击和不足能力不伪造利润。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
