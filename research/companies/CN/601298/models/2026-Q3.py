"""Recompute the adopted company model from readable current inputs."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "2026-Q3"
sys.path.insert(0, str(SOURCE))
import model


data = json.loads((SOURCE / "inputs.json").read_text(encoding="utf-8"))
cases = []
for changes in data["scenarios"]:
    config = dict(data["base"])
    config.update(changes)
    cases.append(model.simulate(config))
model.formal_chain_tests(data["base"])
value_range = {"low": round(min(x["current_common_value_per_share"] for x in cases[1:3]), 2), "high": round(max(x["current_common_value_per_share"] for x in cases[1:3]), 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": "2026-10-31T20:50:00+00:00", "base_case_distributions_per_share": [round(x, 6) for x in cases[0]["distributions_per_share"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": round(min(x["year5_common_value_per_share"] for x in cases[3:5]), 2), "high": round(max(x["year5_common_value_per_share"] for x in cases[3:5]), 2)}}}

PUBLICATION = {'symbol': 'CN:601298', 'report_period': '2026-Q3', 'valuation_note': '核心是成熟业务正常盈利保持、两大项目缓慢爬坡、约203亿元未来工程净付现及正常上划的条件性路径。端点分别为10%/9%权益成本及较不利/较有利既有AP和预付归属，不是所有压力包络。主法8期实际普通股现金加经营/JV/金融资本末期价值，辅助同口径剩余收益；基准7.01/7.21元不取平均。永久低贡献约6.12元、周期弱6.76元、超支延期6.24元、较好兑现7.39元、慢本金释放6.56元。前置付款6.73元及其他有资金/政策冲突的结果仅为诊断，不宣称融资方案可实施。腾讯源内2026-10-30 16:14:57报价10.01元不是交易所收盘认证，该快照高于条件核心区间。', 'return_model_note': '五项为2026-11-01起逐个完整现金年度的实际普通股分配预算，非FCFF或无条件承诺；A/H普通股总股数64.911亿股，未假设新增稀释/回购。已宣派2026中期0.1399元在起点现金结算假设扣一次，不列未来D，Q3净资产不再次扣同一宣派。母体法定公积已停提；母/子/JV宣派、会计收益、到账与NCI金融索偿分别滚动。第五年末2031-10-31经济价值8.89—10.03元使用同基准D及资金状态，仅变折现率，并包含其后三年爬坡及持续经营、必要投入、债务/NCI/福利和金融本金释放，不复制当前区间。本金释放及配套工程/付款归属均为明确研究条件；15路径中的政策和运营缓冲不足不被自动融资填平。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
