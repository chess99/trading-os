"""重算当前采用的普通股模型；完整轨迹通过 --full-output 另存工作目录。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
spec = importlib.util.spec_from_file_location("research_model_io", ROOT / "research/model_io.py")
model_io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model_io)

SELECTORS = {'low': {'path': ['base_low', 'today_value'], 'round': 1}, 'high': {'path': ['base_high', 'today_value'], 'round': 1}, 'distributions': {'path': ['base_exercise', 'rows'], 'column': 'company_dividend_per_share', 'take': 5}, 'terminal_low': {'path': ['base_low', 'year5_value'], 'round': 2}, 'terminal_high': {'path': ['base_high', 'year5_value'], 'round': 2}}
METADATA = {'symbol': 'CN:688777', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T15:45:00+00:00', 'valuation_note': '主法为十期实际普通股分配及同路径续期价值，前五期经营恢复、后五期增长与利润率淡化；核心折现10%—11%、长期增长1%—2%，私人资本回收65%—90%，标的额外周转1.5—3亿元、部分回收，终端现金核心两端另等8/3年，中值及经营对照统一3年。独立产品盈利能力法重建现有77.5亿元收入及费用，约3.8—5.0元，不复用主法第五期利润率；两法不机械平均，主区间承担有限AI复用的证据责任。终端本金实现是核心条件，不是已批特别分红；Singapore大量净资产为本金而非可派利润，一般资本程序不证明本公司决定。现金项当前每股贡献0.90—1.73元，mid额外3/8/15年等待对应6.12/5.57/5.10；不计该现金项4.53仅显示依赖、非清算底。不能筹足正常经营现金的压力路径价值及终值为null。', 'return_model_note': '五期为截止时点后滚动12个月，列示核心两端实际通过母现金/留存、旧已宣派义务、全年度母子利润联合抵亏提储和集团用途留存约束后的D，不是FCF或回购支出。首期0.20中0.10为已批H1股利，登记权益尚待核实；若已不属于当前持有人，则首期权益减少0.10，集团付款现金桥不消失，低/高端价值各少0.090/0.091元，TV5不变。第5年值分别由各端点自身前五期实际派现后的余额续跑第6—10期及终端权益桥得出；low/high收购支持及回收不同，Y5集团现金42.89/44.25亿元，不能称相同state。现金薪酬、不依赖认款基准的有权股7.77446096亿；未用库存注销同时减发行及库存，不额外减少有权股。认款替代情景同时计合同现金、股份流回和非现金服务成本；基准不含该认款。银行/租赁债、少数、必要运营现金和投资义务均进入权益桥；终端本金等待不等于已批准分红。 公司授予调价只读公司分配合同历史，个人是否享有旧登记股利不改变公司认款、股数、现金、留存或续期价值。'}

if __name__ == "__main__":
    raise SystemExit(model_io.main(__file__, SELECTORS, METADATA, source_file='stdout.json'))
