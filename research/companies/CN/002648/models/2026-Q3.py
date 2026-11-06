"""当前采用的金融计算；历史实现比较及运输快照不参与默认运行。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:002648', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T08:00:00+00:00', 'valuation_note': '核心全部未来普通股实收DCF，Ke11%/10%、g1.5%/2%、新增ROIC10%/12%；精算23.5113646968—27.6352322601元。母真实利润及公积约束，子经营桶零旧容量、未来经济可实现95%，海外21%税和5%摩擦预算；全尾期维护/租金/利息持续、金融批次不漏项。辅助企业现金法28.074473—31.973927元，不平均。', 'return_model_note': '五年普通股实收0.65/0.75/0.85/0.95/1.05元；33.6864569亿股不变。Y5权益终值34.4537628034—39.4334029072，来自Y6以后完整现金链；所有额外金融本金、证券与投资变现只计实际支付一次，400/800年数值收敛。经济上划不是逐子公司法律事实；旧应收不增利润，母满额储备及延迟敏感另列。'}

def compute():

    engine.tests()
    paths={side:engine.run(engine.cases()['base'],engine.PARAM[side],400)for side in ['low','high']}
    assert all(x['feasible']for x in paths.values())
    values={side:round(paths[side]['value_per_share'],2)for side in ['low','high']}
    distributions=paths['low']['dps']
    terminal={side:paths[side]['terminal_equity_per_share']for side in ['low','high']}

    values['currency']='CNY'
    out=dict(METADATA)
    out.update(schema='trading_os_research_result_v1',value_range=values,
        return_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':METADATA['information_cutoff'],
            'base_case_distributions_per_share':distributions,'base_case_terminal_equity_value_range_per_share':{'year_5':terminal}})
    return out

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    text=json.dumps(compute(),ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')
