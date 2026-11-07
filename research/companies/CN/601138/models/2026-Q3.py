"""重算采用的核心路径及同一基准现金的第五年剩余权益。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:601138', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T11:00:00+00:00', 'valuation_note': '主法为产品现金贡献与全母子现金账，辅法独立附加值/资本周转；不平均，不使用证券行情或市场倍数。核心端点不是压力包络。', 'return_model_note': '五年分配来自base真实现金约束；Y5区间用同base第6年后全分配按10.5%/9.0%折现，不更换经营状态或复制当前区间。'}

def compute():

    cases={name:engine.run(engine.scenarios()[name])for name in ['base','core_low','core_high']}
    base=cases['base']
    values={'low':round(cases['core_low']['value_per_share'],2),'high':round(cases['core_high']['value_per_share'],2),'currency':'CNY'}
    distributions=list(base['dps_first5'])
    terminal={side:sum(row['parent']['dps']/(1+rate)**(row['year']-5)for row in base['rows']if row['year']>5)for side,rate in [('low', 0.105), ('high', 0.09)]}

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
