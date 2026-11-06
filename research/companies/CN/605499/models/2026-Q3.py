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
model.hand_cases()
result = model.produce(data)
value_range = {"low": result["core_low"]["value_per_share"], "high": result["core_high"]["value_per_share"], "currency": "CNY"}
return_model = result["return_model"]

PUBLICATION = {'symbol': 'CN:605499', 'report_period': '2026-Q3', 'valuation_note': '主方法为经营FCFF折现加净金融资产：同一基准产品路径下，低端资本成本9.5%、尾段增量ROIC18%，高端8.5%和22%，长期增长均2.5%，2032经营利润率再淡化0.2个百分点；当前每股原始结果101.2760878995—117.5678369367元，正文四舍五入101.28—117.57元。2026-09-30财务经显式10月估计桥到2026-10-31，运行现金转入经营资本，旧H股应付股利、银行债务和少数归属处理一次，库存回购现金不再扣。辅助以2027—2029平均经营NOPAT49.14亿元乘13—16倍并走同权益桥，108.90—129.18元，不取两法平均。尾值现值占经营EV75.4%—79.0%；18%—22%回报依赖成熟品牌、产能利用和新品资本效率，非已实现项目收益。周期弱99.56、结构不利56.72、较好141.60元不并入核心区间。低收益保留现金下按五年实际分配加终值的现值诊断94.82—111.77元显示时间成本，并非本金法律失值或Y6强制派清。没有可靠同日股价，未固化IRR或价格判断。', 'return_model_note': '估值起点2026-10-31，五项为各真实周年至2027—2031年10月31日持续持有人收到的现金；预算每年5月31日支付40%、9月30日60%，不是公告承诺，旧已除息3元不再计入。股数维持727076759股，法定发行734199310股、库存7122551股无当前分红权；不预设注销或额外融资，若库存用于激励须重建完全稀释口径。母初始5亿元可调用现金由H1金融库存扣全额H股会计投入、后宣股利和结算缓冲形成；2026年末20亿元上划尚须合法宣派及到账，利润确认和收现分开，母增子减集团零。后续上划按利润及资本后现金预算，母已合法可用现金和历年余款可使用，分红不机械受当年FCFF上限约束；母公积按历史支持补1.07093155亿元差额，未来政策有变需更新。第五周年2031-10-31终值123.2521596551—142.5926072052元来自2031经营状态及2032持续再投资FCFF，年度2031-12-31经营EV和现金按剩余两月流量、实际付款及权利桥回周年；年内非分红流量均匀近似而非精确月度预算。周年经营EV约700.47—841.09亿元，加流动金融253.29及非流动金融5.53，减银行债62.73、少数约0.42亿元，全部已付普通分红已从现金扣；当前基准周年无新已宣未付股利。募集本金保留并计入金融资产，不在Y6强制派清，不重复计金融收益。未提交无独立经营端点的year_3。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
