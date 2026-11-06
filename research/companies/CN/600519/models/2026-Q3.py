"""重算采用的核心路径及同一基准现金的第五年剩余权益。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:600519', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T11:00:00+00:00', 'valuation_note': '主法逐年量价、成熟供给、库存资本与合法实际现金折现，普通股资本成本8%-9.5%、基准8.5%；80%常规股利、Y2起10%合法余款释放为未宣布条件。主区间非全压力包络。辅法独立正常化现金经营利润1030/1100/1160亿元与0%/1%/1.5%名义增长，不导入主法预测利润、不取平均。无证券报价输入。', 'return_model_note': '固定原始1,250,081,601股，五周年分配[56.277317, 70.006424, 71.380791, 72.979581, 74.802514]元；Y1只有常规分配，Y2起含未宣布的10%剩余合法余款释放。年五续期1061.279701—1343.981390元来自同基准年度6..240现金，以9.5%-8%折回年五，未拼其他情景、未另加锁定公积或现金。6月已付股利/回购不重复，母10%提储及子少数/金融资本和流动性全程约束。'}

def compute():

    cases={name:engine.run(engine.scenarios()[name])for name in ['base','core_low','core_high']}
    base=cases['base']
    values={'low':round(cases['core_low']['value_per_share'],2),'high':round(cases['core_high']['value_per_share'],2),'currency':'CNY'}
    distributions=list(base['dps_first5'])
    terminal={side:sum(row['dps']/(1+rate)**(row['year']-5)for row in base['rows']if row['year']>5)for side,rate in [('low', 0.095), ('high', 0.08)]}
    distributions=[round(v,6)for v in distributions]
    terminal={k:round(v,6)for k,v in terminal.items()}

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
