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
result = model.run_suite(data)
value_range = {"low": round(result["core_value_range_per_share"][0], 1), "high": round(result["core_value_range_per_share"][1], 1), "currency": "CNY"}
return_model = result["return_model"]

PUBLICATION = {'symbol': 'CN:601827', 'report_period': '2026-Q3', 'valuation_note': '方法一为核心：有限BOT/BOO及澳门经营现金DCF，工程2036年后零增长能力资本化且不重复列现金，另加现金、旧款回收和联营权益、减归属外债。资本成本7.5%—8.5%，国内费用前现金毛利56%—60%、工程28%—34%、维护3.2—4.5亿元、前五年量增1.5%—2.5%、中央差额0.13—0.17元，金融归属94%—98%；所得税逐批退出，西部2031起25%。计算端点6.171314637474738—9.376132322949939元，按假设精度表达6.2—9.4元，基准7.7545159392003元。方法二按有限净经营资本回收，基准7.256004418111867元、约6.81—7.76元，不机械平均。核心低端不是极端全损外圈。', 'return_model_note': '五笔D直接使用普通盈利36%—40%的年度预算，经母现金、留存和资金缓冲约束；三条核心路径共用这组基准D，不将历史0.266元视为五年硬保底，2026年6月已付旧股利不再计入。第五年每股价值7.897754214069116—11.925782713300089元，来自剩余经营/回收现金现值，加已扣五笔D的年五现金及联营权益、减债务；基准桥为131.557+3.340+40.548−22.234+12.691≈165.902亿元。完全稀释股数代理为已发行1,671,933,300股，无未经承诺增发或回购。起点2026-09-30余额代理2026-10-31，五期按2027-10-31至2031-10-31周年末聚合，经营/政策年标签为年度近似，非精确日历年或实际分红日。现金收益0.5%、现金借款成本2.8%，母2026已知利润公积重分类不减少总权益；不把当前价值复制为终值、不提交未研究的三年终值或随价格变化的IRR。'}
PUBLICATION.update(value_range=value_range, return_model=return_model)
print(json.dumps(PUBLICATION, ensure_ascii=False, allow_nan=False, indent=2))
