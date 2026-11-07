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
results = {name: model.resource_asset_run(model.configured(data["paths"][name])) for name in ("A_low", "A_high")}
value_range = {"low": round(results["A_low"]["current_value_per_share"], 2), "high": round(results["A_high"]["current_value_per_share"], 2), "currency": "CNY"}
return_model = {"schema_version": 1, "method": "annual_common_equity_irr_v1", "currency": "CNY", "model_as_of": model.AS_OF, "base_case_distributions_per_share": results["A_low"]["distributions_per_share"], "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": results["A_low"]["year5_value_per_share"], "high": results["A_high"]["year5_value_per_share"]}}}

PUBLICATION = {'symbol': 'CN:600938', 'report_period': '2026-Q3', 'valuation_note': '核心采用A有限资源现金与剩余金融资产权益估价，明确采纳普通资本计划/分配延续。研究的未来五年公司口径产量预算（非管理层五年指引）805/821/837/854/871百万boe、实现油价78/73/70/70/71美元、资源现金1300/1350/1380/1420/1450亿元；十年付费寻找与开发。低端第五年后寻找/开发45/165元每boe、尾部递减12%、股权成本10%；高端35/135元、9%、8.5%，并分别采用较慢/较快有成本金融资产访问。长期子55%宣派、母45%意向、1.5%留存回报为有依据而可改判预算，不是2027年后承诺；资产边界折至Y5约占Y5价值45.1%/51.8%。A/B纯政策配对当前值相差约1.79/1.81元，未拆权益局部价差仅约0.029/0.063元。正常现金法13.60—21.27元为独立辅助，不是法律上限，不平均并入核心。PUD0/100、永久弱、资源效率弱和十五年寻找均保留完整不同结果。', 'return_model_note': '基准为同一普通股持有人、人民币投资者税前、47,529,953,984股，无新增稀释或回购假设；A/H属于同一香港发行人普通股，已在研究日前除息的2026中期股息不计未来D，初始现金扣旧应付股利。年度经营大约对应2027—2031，年度实付现金预算在期末折现，并非逐笔还原一年两次实际派息日历；2027后45%政策延续、子55%宣派及80%当期收款为研究预算。五期D从母和集团现金同时扣除。Y5值为之后普通分配现值与有限资源/债务/ARO结清边界剩余金融权益的折现，不直接复制当前值，不与B或正常现金法拼接。Y5仍有约398.43亿元债务及1597.40亿元ARO，后续在同链实际支付；基金与投资本金/收益不重复，资源结束不等于法体清算。首五年继续按10%提公积的有界比较仅改变合法利润分类，D与一般现金不变，不推及新A尾部。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
