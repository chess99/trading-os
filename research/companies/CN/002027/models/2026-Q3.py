"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'base', 'value_low'], 'round': 1}, 'high': {'path': ['summary', 'base', 'value_high'], 'round': 2}, 'distributions': {'path': ['summary', 'base', 'distributions'], 'take': 5}, 'terminal_low': {'path': ['summary', 'base', 'terminal_y5_low']}, 'terminal_high': {'path': ['summary', 'base', 'terminal_y5_high']}}
METADATA = {'symbol': 'CN:002027', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-27T12:00:00+00:00', 'valuation_note': '主方法为受现金及母公司利润预算约束的普通股分配折现：原业务五年收入122至135.98亿元、现金经营率43%、税20%、远期1.5%增长、资本成本10%/9%。Y2纳入新潮90.022%及15.3454亿新股。辅助法将Y3盈利按成熟g=1.5%、资本需求及9%—10%风险推导11.3318—12.8447倍，并以同一亏损弥补、金融回收和付款约束校正，得3.15—3.58元，不机械平均。未交割、全资、周期及结构损伤另算。', 'return_model_note': '前五年实收现金股利分别0.2236113654/0.2015226005/0.2078312103/0.2143482133/0.2219611515元；Y1股数144.42199726亿、Y2起159.76740235亿。Y5终值3.8467891339—4.3182595236元，由之后经营分配及134.59亿元未分配金融权益继续回收形成，不复制当前价值。必要运营资金留存支持利润；金融收益不进经营利润、租赁不再扣债、银行债务与少数资产另处理。母公司上划及法定利润均为注明条件的预算，不声称逐主体未来法定余额。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
