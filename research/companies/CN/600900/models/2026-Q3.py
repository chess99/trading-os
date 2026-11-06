"""重算采用的核心路径及同一基准现金的第五年剩余权益。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:600900', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-30T23:11:24.100682+00:00', 'valuation_note': '主方法为有限50年经营现金DCF与完整普通股桥：正常发电2950—3050亿度、净价0.245—0.249元、维护80—90亿元，经营折现5.0—5.5%，资产群折旧与税率逐年传导；不计永久水量增长。辅助正常化所有者盈利资本化21.10—25.63元，股权成本6.5—7.2%，不同资本政策但相同经营与权益边界；两法中点差约6.6%，不据此上调主区间。', 'return_model_note': '未来五个周年现金分配按2026约325亿元归母及以后实际模型利润70%预算；母公司法定利润、到账现金及借款能力约束同时检验。已付历史1.00元不重复纳入。基准第五年债务2512.02亿元、经营现金80亿元，两端终值均使用同一基准前五年实际现金与债务，再研究未来45年经营、继续建设、参股及少数权益；不重复加留存、在建资产或已分红现金。最终股数244.68217716亿股，无回购分配及第三年终值。'}

def compute():

    p=json.loads((HERE/'2026-Q3-inputs.json').read_text(encoding='utf-8'))
    cases={}
    for name in ['base','core_low','core_high']:
        data=engine.copy.deepcopy(p['base']);data.update(p['cases'][name]);cases[name]=engine.run(data)
        assert cases[name]['current'] is not None
    base=cases['base']
    values={'low':round(cases['core_low']['current']['per_share'],2),'high':round(cases['core_high']['current']['per_share'],2),'currency':'CNY'}
    distributions=[row['distribution_per_share']for row in base['financing'][:5]]
    terminal={side:engine.valuation(cases['core_'+side]['parameters'],cases['core_'+side]['operations'],base['financing'],5)['per_share']for side in ['low','high']}

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
