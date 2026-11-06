"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['scenarios', 'core_low', 'value'], 'round': 1}, 'high': {'path': ['scenarios', 'core_high', 'value'], 'round': 1}, 'distributions': {'path': ['scenarios', 'base', 'distributions_5'], 'take': 5, 'round_items': [4, 4, 3, 4, 4]}, 'terminal_low': {'path': ['scenarios', 'terminal_low', 'terminal_5'], 'round': 2}, 'terminal_high': {'path': ['scenarios', 'terminal_high', 'terminal_5'], 'round': 2}}
METADATA = {'symbol': 'CN:600600', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-28T21:00:00+08:00', 'valuation_note': '主法同一普通股实际分配折现：第一年收入316亿元、EBIT17.4%、增长1.2%渐降至15年为零；核心端点17.0%/0.8%/9.5%与17.8%/1.6%/8.5%。辅助独立单位经济法31.64元。全额286.3亿元金融资源中58.3亿元为动态无息运营资金，已取代同用途最低现金，不永久锁死；母投资关闭成本损失影响法定利润而不重复现金。无市场PE或额外净现金加项。', 'return_model_note': '2027—2031预计公司层税前实际付款，固定13.64195121亿股。终值从完全相同前五年状态出发，第六年收入递接共同Y5收入乘新路径Y6增长率，非回算Y1。全额资源桥含可收益及无息运营现金，后者随经营需求增减；税费、公积、内部债务和少数分配逐户控制。东南部分活动有限关闭预算的非现金资产/旧外债与母投资成本及补资分开，母损失无第二次现金支出。19全情景800/1200/1600年同付款政策收敛，无本金终值重复。未披露分户金额/退出范围为明确经济预算而非精确法人清算。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
