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
model.formal_chain_hand_cases(data)
cases = {n: model.evaluate(data["facts"], model.config_for(data, n)) for n in ["base", "core_low", "core_high"]}
value_range = {"low": round(cases["core_low"]["current_value_per_share"]), "high": round(cases["core_high"]["current_value_per_share"]), "currency": "CNY"}
base = cases["base"]
cfg = model.config_for(data, "base")
end = base["rows"][4]
low = model.enterprise_value_at(base["rows"], cfg, 5, discount=.1, terminal_growth=.02)
high = model.enterprise_value_at(base["rows"], cfg, 5, discount=.09, terminal_growth=.025)
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": data["information_cutoff"].replace("Z", "+00:00"), "base_case_distributions_per_share": [x["dps"] for x in base["rows"][:5]], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": (low["value"] + end["nfa"]) / end["shares"], "high": (high["value"] + end["nfa"]) / end["shares"]}}}

PUBLICATION = {'symbol': 'CN:300866', 'report_period': '2026-Q3', 'valuation_note': '主法为十年普通股经营FCFF加相容净金融资产、旧激励缴款PV，另减历史社保现金预算PV一次。核心前段增长12%—16%，扣持续合规成本后EBIT8.2%—9.3%、远期7.2%—8.3%，资本成本9%—10%、长期增长2%—2.5%。base合规增量0.25个百分点是作者条件假设（2025原披露不足约0.20%收入），low0.30/high0.20；三核心路径均留约1.9亿元Y1历史现金准备，不当作已披露当前净债务或硬责任上限。实际端点55.09/94.93，基准75.56，辅助99.17高31.23%因资本和持续期不同而不平均。历史已付或另有现值及现金覆盖条件诊断75.86，但仅已计提不能免支付，不作为核心上端默认。旧周期/结构/上行诊断未叠加本次社保条件，非新核心包络。9月底财务余额carry-forward至10月底，未声称已观测10月资产。', 'return_model_note': '未来五周年实际现金预算2.0971814465、2.3689067835、2.6485121665、2.8832894926、3.0811040879元/股，合计13.078994；已支付2026中期0.8元不重复。起点实发589432146股，旧激励450万股分三年归属及缴款同时计入，最终完全稀释593932146股。普通股经营税后利润归属95%，持续合规成本0.25个百分点各年及终值显式扣；历史1.9亿元Y1付一次，母体现金和集团现金是同笔。H1母体账面未分配利润42.2691亿元与起算37亿元预算分开，额外1.9亿元审慎分配准备使模型起点35.1亿元，非已入账调整；法定公积另列。正常银行续作/摊还和2031转债约11.60亿元偿付进入现金。Y5经营价值465.23亿元、分配后普通股净金融资产109.37亿元、转债零，历史现金已付不再扣本金；以同base经营和资金状态，低端10%折现/2%增长、高端9%/2.5%，得88.9312879339—102.9075760609元。Y5→Y6无巨额特别分红；母体高端Y7、baseY10减派，非集团破产。罚息/实体和覆盖映射不明仍保留尾部风险。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
