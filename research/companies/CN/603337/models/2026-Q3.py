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
# The adopted principal correction removes the old retention-only haircut;
# operating budgets and actual distributions stay unchanged.
for scenario in data["scenarios"]:
    for endpoint in scenario["endpoints"]:
        endpoint["financial_retention_haircut"] = 0.0
result = model.evaluate(data, include_crosscheck=False)
base = result["scenarios"][0]
values = base["valuations"]
value_range = {"low": round(min(x["pv_of_actual_assumed_payment_dates_and_tv5"] / result["bridge"]["shares"] for x in values), 1), "high": round(max(x["pv_of_actual_assumed_payment_dates_and_tv5"] / result["bridge"]["shares"] for x in values), 1), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["as_of"] + "T00:00:00+00:00", "base_case_distributions_per_share": [x["cash_per_share"] for x in values[0]["annual_holder_distributions"]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": min(x["tv5_per_share"] for x in values), "high": max(x["tv5_per_share"] for x in values)}}}

PUBLICATION = {'symbol': 'CN:603337', 'report_period': '2026-Q3', 'valuation_note': '主采用为基准经营现金、分配预算与第五周年剩余普通股权益的折现路径：折现率12%/10%，长期增长1.5%/2%，ROIC淡化至10%/12%。已扣受限/经营缓冲/债务/NCI并计并购后，缺乏独立于低收益和等待的本金毁损证据，主法与辅法均不另扣金融本金。主低/高端持有现值每股为10.367425607364101971440511433433003506098452128933/14.155276725543417929541655087287348230621234777750元，一位小数10.4—14.2元；资产参照11.653028517159071339542435812779469653605213631996—15.259382781711734元，独立正常化辅法13.210122355932241693569110738641754778440870894196—15.535871884771189130936079488088782497356690734864元。低、高端资产与持有路径差592.19/508.59百万元，来自40%普通现金和余款1.2%净收益预算的时间/配置条件，未付本金仍在周年权益，不再叠加15%或10%额外扣减，也不把FCFF当法律分派上界或机械取低。历史回购反对永久低效留存的唯一推论，但未同步计现金及股数前不给免费回购收益。基准2031盈利约7亿元，约10亿元为条件上行；压力表保留的端点另有明示本金损失假设，不是相对新核心的单因素结果；五年替换费不等于永久通胀压力，25%分派端未完整重算。', 'return_model_note': '未来五个周年为2027—2031年11月1日；经营财政年2027—2031，另桥接2026Q4，终值在2031-11-01而非财政年末。未来6/11及10/9支付是假设，全年40%普通股利润目标中中期15%，末期补足，并受母利润、持续10%公积提取、上划及现金预算约束；FY2025现金23.87%与含回购40.45%不同。母报表430.73387542百万元为总盈余公积，未逐项证明法定分类；模型不因达到资本一半停提。总股本476388091减库存15752434，基准完全稀释经济股数460635657，假设无新增授予/回购/权益融资，现有已授股份已在内；未授160万另列稀释。第五周年经营价值4444.989977132972/6594.656048396934百万元，加已扣D后金融余额2423.316667972733百万元（均不另扣金融本金损失），除上述股数；2031余下经营现金仍在未来经营价值，不重计全年现金。终值含2032—2036资本回报与增长淡化及后续稳态，不含特别分红或资本自动回收。2026旧0.45/0.30、公开回购及未分配FCFF均非未来D。经营流量采用财政年末/月度短段近似，支付日采用month/day分数年，不等同ACT/365.25；相同状态下两端总现值差约0.181/0.160百万元，不影响核心一位小数。母两年不上划且结票路径负现金，相关D/TV/PV为null，不作为基准模型。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
