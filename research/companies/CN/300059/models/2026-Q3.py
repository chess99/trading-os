"""当前采用的金融计算；历史实现比较及运输快照不参与默认运行。"""
import importlib.util,json,argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('financial_engine',HERE/'2026-Q3-engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
METADATA={'symbol': 'CN:300059', 'report_period': '2026-Q3', 'information_cutoff': '2026-10-26T11:15:00+00:00', 'valuation_note': '核心持续经营普通股现金折现，10%—11.5%得到6.048813720716—7.821900898803元；非证上划是有条件经济预算，无虚构法人储备。辅助存量客户有序退出6.651952256—7.509394999元，先偿外债、成本及税，非清算底。', 'return_model_note': '股本15,824,105,875含条件归属1,906,000股与0.045039认款；五年现金为1.8/2.2/2.7/3.2/3.8十亿元。第五年终值来自此后持续经营实际现金，不复制现值；第六年旧借款及资产本金1.898491收现仅改现金；非证0.2新宣派股利进入母利润，分配后减少权益及收益。非证法律明细不全采用经济能力预算及50%/零上划敏感；客户款、次级债、受控产品第三方请求权不归普通股。 母注册15.824105875为登记生效条件预算；沿已证15.804037675门槛重算各有效路径分红及价值不变。清算费用、税或债权不足时退出不执行，保留现金、待收、未偿债及股份，估值返回不可行。'}

def compute():

    engine.tests()
    path=engine.scenario({})
    assert path['feasible']
    bounds={side:engine.valued(path,rate)for side,rate in [('low',.115),('high',.10)]}
    values={side:round(bounds[side]['current_value'],2)for side in ['low','high']}
    distributions=[row['distribution_per_share']for row in path['rows'][:5]]
    terminal={side:bounds[side]['year5_value']for side in ['low','high']}

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
