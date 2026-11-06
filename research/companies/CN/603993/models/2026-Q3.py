"""当前采用的金融计算；历史实现比较及运输快照不参与默认运行。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:603993', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T17:12:00+00:00', 'valuation_note': '主法为有限矿寿及真实归属约束的经济上划/母法定利润/有限融资/资本实现现金折现，11.5%与10%资本成本。六经营单元不虚构法人；母按真实注册、法定公积和香港投资成本，非现金处置折扣后完整偿债。辅助剩余收益6.68—8.03元，不平均；跨境逐层法定数据有限，通过2年延迟、10%摩擦和能力减半条件预算量化。', 'return_model_note': '五年按初始普通股实际所得现金冻结；股数21394310176五年内不变。五年后同一路径继续有限矿寿、少数、债务、税费、资本需求。原应收只收现；香港投资返本减母成本，损益单列；成熟期有偿减资同步取消所有持有人同比股份，最终Y32清算，终值按初始股剩余权益不重复调整分母。跨境上划为有事实约束的经济预算，非逐户法定余额认证；结算延迟和摩擦单列敏感。'}

def compute():

    engine.actual_tests()
    rows=engine.run('base',horizon=32,budget_version='revised')
    bounds={side:engine.valuation(rows,rate)for side,rate in [('low',.115),('high',.10)]}
    values={side:round(bounds[side]['pv'],1)for side in ['low','high']}
    distributions=[row['distribution_per_share']for row in rows[:5]]
    terminal={side:bounds[side]['tv5']for side in ['low','high']}

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
