"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['paths', 'core_low', 'current'], 'round': 1}, 'high': {'path': ['paths', 'core_high', 'current'], 'round': 2}, 'distributions': {'path': ['paths', 'central', 'rows'], 'column': 'distribution_per_share', 'take': 5}, 'terminal_low': {'path': ['paths', 'core_low', 'terminal']}, 'terminal_high': {'path': ['paths', 'core_high', 'terminal']}}
METADATA = {'symbol': 'CN:603129', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T00:00:00+00:00', 'valuation_note': '核心为逐年普通股实际现金分配折现，前五年同一经营预算；低端资本成本11.5%、尾期增量回报16%、长期增长2.5%，高端10.5%/20%/3%。母子现金和母法定利润贯通，超额资金三年滚动释放，境外经济上划80%当前能力/20%延迟三年及7%摩擦为条件预算，不冒充逐户法律账。辅助第五年经营收益10—12倍及同口径金融债权桥得184.02—222.04元，不与主法平均。无现价判断。', 'return_model_note': '五次分配包括普通及可实现特别股息，不含已付2025年度4.20元。基准不转换，转债前五年实际票息及第六年108%偿付；已知激励现金与股份同步，第四年股数1.60634038亿。期末值来自第六年以后实际普通股现金分配现值，不复制当前价值、不再加已派现金。前五年不依赖子股利；之后宣派记母利润、翌年到账仅加现金，跨层7%摩擦、真实亏损当年冲减能力预算，非母税后金融收益及25%激励费用完整进入来源利润；仅注入本金不确认新利润。必要资产持续维护与生息，超额现金分批释放，320年数值逼近经640年收敛验证。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='2026-Q3-output.json'))
