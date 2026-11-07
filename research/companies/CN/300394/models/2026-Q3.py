"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['cases', 'core_low', 'present_value'], 'round': 1}, 'high': {'path': ['cases', 'core_high', 'present_value'], 'round': 1}, 'distributions': {'path': ['cases', 'base', 'years'], 'column': 'dps', 'take': 5, 'round_items': [6, 6, 6, 6, 6]}, 'terminal_low': {'path': ['cases', 'core_low', 'terminal_equity5'], 'round': 6}, 'terminal_high': {'path': ['cases', 'core_high', 'terminal_equity5'], 'round': 6}}
METADATA = {'symbol': 'CN:300394', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T12:17:30+00:00', 'valuation_note': '方法一为普通股实际现金分配折现，所有晚期经营现金、本金及所得金融收益同走母公司/江西/其余境外链法定利润与资金约束，未直接加净现金。核心低端资本成本10.5%、成熟增长2%、回报12%；高端9.5%、2.5%、15%。方法二从当期30亿元正常化经营盈利进入成熟经济学，经同一普通股支付链得26.3—32.4元，不机械平均。周期、结构、乐观与本金回收路径独立重算。', 'return_model_note': '五个未来12个月年度末分配，非自然年承诺；9月已付0.50元不重复。第5年每股未来可支付现金价值57.301335—67.103004元。普通股完全稀释10.93267939亿股，旧激励认购现金同步进入。必要运营现金10.24亿元不释放；额外本金95.8924亿元分母/江西/其余49.8993/31.0322/14.9610亿元，自第6/7/8年起各五年支付，受各自弥亏后可分利润和储备封顶约束；基准本金第5年现值仅67.6567亿元。未来经营现金、利息及基金回款也经同一路径，跨境代理预算扣10%损耗；不把经营FCFF和金融收益重复资本化。3/10/15年回收价值45.82/44.89/44.43元，80%最终回收44.71元，均不是永久锁死未知现金。母公司前五年无需子公司股利；新激励基准不达门槛，乐观按条件联动股份及认购现金。回购与H股不当作已完成。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
