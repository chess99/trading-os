"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['summary', 'low', 'pv'], 'round': 2}, 'high': {'path': ['summary', 'high', 'pv'], 'round': 2}, 'distributions': {'path': ['summary', 'base', 'd'], 'take': 5, 'round_items': [4, 4, 4, 4, 4]}, 'terminal_low': {'path': ['summary', 'holder_low', 'tv5'], 'round': 2}, 'terminal_high': {'path': ['summary', 'holder_high', 'tv5'], 'round': 2}}
METADATA = {'symbol': 'CN:300628', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T20:36:00+00:00', 'valuation_note': '主方法为母公司真实法律及现金约束与子经济可实现上划预算的普通股现金折现，基准31.6778元，核心29.12—34.59元；方法二为无增长经营获利能力23.46—25.66元，不平均。结构收缩继续经营并有条件实现额外金融本金，12.5781元；停止经营仅为另列资产回收边界。真实主体、法域和投资成本与经济预算分开，未核资本储备保持未知。', 'return_model_note': '五年普通及额外现金分配为2.1383/2.2633/2.3946/2.4861/2.5673元；第五年终值32.86—38.83元来自同一基准前五年状态的第6年以后分配折现，仅Y6后利润率和折现率变化。实际股本12.66918377亿，前三年每年新增300万股及16.58元认股款同时入模，末期12.75918377亿股。母子旧应收到账不重复利润，母公司法定储备按注册资本50%门槛，子公司仅经济上划预算、初始可实现利润为零、未来50%可实现比例并以十年停付后恢复及永久拒付未实现权益诊断约束；少数为零，已分配现金不留在终值。分配与实体拆分为估计，非董事会承诺。 资本返还不当作利润，成本以上才预算处置利得；有偿减资同步减少原持有人股份，税费实际支付。库存股按账面成本单列，不从已发生现金重复扣减；未用现价反推股数。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
