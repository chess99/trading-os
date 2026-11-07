"""独立Decimal复算：不导入生产金融函数；只共用已披露输入。

比较核心两个端点、利润率少1个百分点及同一基准Y5续期。
源码可直接审阅。生产模型本身的手算特例另由 --check 验证。
"""
import copy, json, decimal
from pathlib import Path
import subprocess,sys
sys.stdout.reconfigure(encoding="utf-8")

decimal.getcontext().prec=40
D=decimal.Decimal
P=Path(__file__).parent
raw=json.loads((P/'2026-Q3-inputs.json').read_text(encoding='utf-8'),parse_float=D,parse_int=D)
facts=raw['facts']

def dd(v):
    return v if isinstance(v,D) else D(str(v))

def independent(a, rate, growth):
    rate,growth=dd(rate),dd(growth)
    start=(facts['cash_equivalents_q3']+facts['liquid_investments_q3']-facts['paid_october_dividend']
        -facts['new_buyback_paid_october']-facts['debt_and_leases_q3']-facts['minority_equity_q3']+a['opening_common_cash_adjustment'])
    cash=[a['parent_opening_liquid_cash'],a['domestic_subs_opening_liquid_cash'],D(0)]
    cash[2]=start-cash[0]-cash[1]
    retained=[facts['parent_h1_retained_earnings']-facts['paid_october_dividend']+a['parent_retained_adjustment'],
        a['domestic_subs_opening_distributable_profit'],a['overseas_opening_retained_loss']]
    shares=facts['issued_shares']-facts['new_buyback_shares_held']
    K=a['opening_nwc']+a['opening_net_fixed_operating_capital']
    wc=a['opening_nwc']
    dividends=[]; rows=[]
    zero=D(0)
    for t in range(10):
        revenue=a['revenues'][t]
        nopat=revenue*a['cash_operating_margin'][t]*(1-a['tax_rate'])
        interest=[x*a['cash_yield_after_tax'] for x in cash]
        domestic=nopat*a['domestic_subs_profit_share']
        overseas=a['overseas_common_profit'][t]
        earning=[nopat-domestic-overseas+interest[0],domestic+interest[1],overseas+interest[2]]
        new_wc=revenue*a['nwc_ratio']; delta_wc=new_wc-wc;wc=new_wc
        da,capex=a['depreciation'][t],a['capex'][t]
        K+=capex-da+delta_wc
        previous=sum(cash)
        for j in range(3):
            cash[j]+=earning[j]+da*a['depreciation_allocation'][j]-capex*a['capex_allocation'][j]-delta_wc*a['nwc_change_allocation'][j]
            retained[j]+=earning[j]-(max(earning[j],zero)*D('.1') if j==1 else zero)
        required=[revenue*a['minimum_cash_ratio']*x for x in a['cash_floor_allocation']]
        for j in (1,2):
            contribution=max(required[j]-cash[j],zero)
            cash[j]+=contribution;cash[0]-=contribution
        leakage=zero
        if t+1>=a['subsidiary_upstream_start_year']:
            for j in (1,2):
                declared=max(min(cash[j]-required[j],retained[j]),zero)
                friction=declared*a['cross_border_dividend_friction'] if j==2 else zero
                cash[j]-=declared;retained[j]-=declared
                cash[0]+=declared-friction;retained[0]+=declared-friction;leakage+=friction
        recovered=zero
        if t+1==a['strategic_asset_recovery_year']:
            recovered=facts['strategic_financial_assets_q3']*a['strategic_asset_recovery_ratio']
            loss=facts['strategic_financial_assets_q3']-recovered
            w=a['strategic_asset_parent_share']
            cash[0]+=recovered*w;cash[2]+=recovered*(1-w)
            retained[0]-=loss*w;retained[2]-=loss*(1-w)
        bought=zero
        if t==0:
            bought=facts['remaining_minimum_buyback_cash']+a['buyback_fees_budget']
            cash[0]-=bought
            shares-=facts['remaining_minimum_buyback_cash']/facts['buyback_price_ceiling']
        policy=a['first_five_distribution_profit_ratio'] if t<5 else a['later_distribution_profit_ratio']
        wanted=policy*max(nopat+sum(interest),zero)
        if t>=5:
            wanted+=a['later_extra_parent_cash_release_ratio']*max(cash[0]-2*required[0],zero)
        paid=min(wanted,max(min(cash[0]-required[0],retained[0]),zero))
        cash[0]-=paid;retained[0]-=paid
        dividends.append(paid)
        identity=sum(cash)-previous-(nopat+sum(interest)+da-capex-delta_wc)+leakage-recovered+bought+paid
        assert abs(identity)<D('1e-30')
        assert cash[0]>=required[0]-D('1e-30')
        rows.append({'cash':cash[:],'required':required[:],'retained':retained[:],'K':K,'nopat':nopat})
    last=rows[-1]
    terminal_fcf=last['nopat']*(1+growth)+sum(last['required'])*a['cash_yield_after_tax']-growth*(last['K']+sum(last['required']))
    operating=terminal_fcf/(rate-growth)
    extra=sum(max(min(c-f,re),zero) for c,f,re in zip(cash,last['required'],retained))
    terminal=operating+extra
    current=(sum(d/(1+rate)**D(i+1) for i,d in enumerate(dividends))+terminal/(1+rate)**10)/shares
    fifth=(sum(d/(1+rate)**D(i+1) for i,d in enumerate(dividends[5:]))+terminal/(1+rate)**5)/shares
    return {'value_per_share':current,'year5_terminal_per_share':fifth,'fully_diluted_shares':shares,
        'first_five_dps':[d/shares for d in dividends[:5]],'year10_equity':terminal}

def run():
    a=raw['base']
    lo=copy.deepcopy(a);hi=copy.deepcopy(a);minus=copy.deepcopy(a)
    lo.update(cash_operating_margin=[x-D('.003') for x in a['cash_operating_margin']],capex=[x*D('1.05') for x in a['capex']],nwc_ratio=D('.185'))
    hi.update(cash_operating_margin=[x+D('.003') for x in a['cash_operating_margin']],capex=[x*D('.97') for x in a['capex']],nwc_ratio=D('.175'))
    minus.update(cash_operating_margin=[x-D('.01') for x in a['cash_operating_margin']])
    results={'core_low':independent(lo,'.1025','.015'),'core_high':independent(hi,'.0925','.02'),
        'base':independent(a,'.0975','.02'),'margin_minus_1pp':independent(minus,'.0975','.02'),
        'same_base_y5_low':independent(a,'.1025','.015'),'same_base_y5_high':independent(a,'.0925','.02')}
    formal=json.loads(subprocess.run([sys.executable,'-B','-X','utf8',str(P/'2026-Q3.py')],cwd=P,capture_output=True,text=True,encoding='utf-8',check=True).stdout)
    assert round(results['core_low']['value_per_share'],2)==D(str(formal['value_range']['low']))
    assert round(results['core_high']['value_per_share'],2)==D(str(formal['value_range']['high']))
    rm=formal['return_model'];tv=rm['base_case_terminal_equity_value_range_per_share']['year_5']
    for k,i in [('same_base_y5_low','low'),('same_base_y5_high','high')]:
        assert abs(results[k]['year5_terminal_per_share']-D(str(tv[i])))<D('.00000051')
    for got,want in zip(results['base']['first_five_dps'],rm['base_case_distributions_per_share']):
        assert abs(got-D(str(want)))<D('.00000051')
    details=json.loads(subprocess.run([sys.executable,'-B','-X','utf8',str(P/'2026-Q3.py'),'--details'],cwd=P,capture_output=True,text=True,encoding='utf-8',check=True).stdout)
    expected=details['sensitivities']['margin_minus_1pp']['value_per_share']
    assert abs(results['margin_minus_1pp']['value_per_share']-D(str(expected)))<D('.000000001')
    return {'scope':'two core endpoints, dominant margin sensitivity, base cash conservation and same-base Y5 continuation',
        'passed':True,'method':'independent Decimal implementation; no production financial-function import',
        'results':results}

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2,default=str))
