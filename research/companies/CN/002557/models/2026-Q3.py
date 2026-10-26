"""洽洽食品，2026-Q3；CNY billion，股数 billion。无网络/第三方依赖。
所有forecast为研究预算；actuals的期后兑债在opening仅扣一次。
"""
import json,copy
from pathlib import Path
ACTUAL={'cash_equivalents':3.11039224728,'trading_financial':1.23308011310,'deposits_current':.38220270827,'deposits_long':.35562269185,'short_debt':.9895,'due_liabilities':1.54880849806,'lease_debt':.00364909872,'redemption_paid':1.540700195,'minority_equity':.03593239247,'repurchase_paid':.001477064,'shares_issued':.505856969,'treasury_shares':.009460417}
# settle residual liabilities and bank debt pro forma; actual redemption is part of due_liabilities, NOT added again.
C0=sum(ACTUAL[k] for k in ['cash_equivalents','trading_financial','deposits_current','deposits_long'])-sum(ACTUAL[k] for k in ['short_debt','due_liabilities','lease_debt','minority_equity','repurchase_paid'])-.015-.008
BASE={'revenues':[7.70,8.10,8.50,8.90,9.30], 'margins':[.093,.096,.097,.097,.097], 'growth_capex':[.13,.10,.08,.08,.08], 'working_capital':[.10,.072,.072,.072,.072], 'tax':.25,'minority':[.005]*5,'g':.02,'terminal_margin':.097,'terminal_capital_intensity':.50,'payout':.70,'upstream':.72,'arrival':.75,'parent_operating_share':.10,'cash_yield':.015,'min_cash_ratio':.8/7.4,'parent_min':.30,'cash0':C0,'parent_cash0':1.20,'parent_re0':1.71515294101,'subs_re0':0.,'restricted0':.46,'parent_extra_transfer':[0]*5,'loss_sub':[0]*5,'debt_limit':.5,'financing_rate':.04,'buyback_year1':.05-ACTUAL['repurchase_paid'],'repurchase_price':20.,'treasury_transfer_year':2,'treasury_transfer_price':20.,'extra_cost':[0]*5}

def legal_step(re,profit,reserve_rate):
    # Existing losses survive; reserve is only taken from positive profit AFTER loss recovery.
    recoverable=max(0.,re+profit)-max(0.,re)
    reserve=reserve_rate*max(0.,recoverable)
    return re+profit-reserve,reserve

def run(p):
    pc=p['parent_cash0']; sc=p['cash0']-pc; pre=p['parent_re0']; sre=p['subs_re0']; arrears=0.;debt=0.;restricted=p['restricted0']
    n=ACTUAL['shares_issued']-ACTUAL['treasury_shares']; treasury=ACTUAL['treasury_shares'];rows=[];feasible=True
    for i,(rev,margin,cap,wc) in enumerate(zip(p['revenues'],p['margins'],p['growth_capex'],p['working_capital'])):
        year=i+1; start=pc+sc;olddebt=debt
        interest=debt*p['financing_rate'];tax=p['tax']; nopat=rev*margin*(1-tax)
        minority=p['minority'][i]; parent_op=nopat*p['parent_operating_share']-interest-p['extra_cost'][i]
        sub_op=nopat*(1-p['parent_operating_share'])-minority-p['loss_sub'][i]
        pi=pc*p['cash_yield'];si=sc*p['cash_yield']
        parent_cf=parent_op+pi-.2*(cap+wc)
        sub_cf=sub_op+si-.8*(cap+wc)
        transfer=p['parent_extra_transfer'][i];pc+=parent_cf-transfer;sc+=sub_cf+transfer
        # Restricted balances are used on real capital expenditure; not subtracted twice.
        restricted=max(0.,restricted-cap)
        sre,reserve=legal_step(sre,sub_op+si,.10)
        subsidiary_min=max(0.,rev*p['min_cash_ratio']-p['parent_min'])
        settled=min(arrears,max(0.,sc-subsidiary_min-restricted));sc-=settled;pc+=settled;arrears-=settled
        declare=min(max(0.,sre),max(0.,sub_op+si)*p['upstream'],max(0.,sc-subsidiary_min-restricted)/max(p['arrival'],1e-9))
        pay=declare*p['arrival'];sre-=declare;arrears+=declare-pay;sc-=pay;pc+=pay
        # Declaration affects legal income; settlement of earlier dividend receivable does not.
        pre,preserve=legal_step(pre,parent_op+pi+declare,0.) # parent statutory reserve already >50% registered capital
        buy=p['buyback_year1'] if year==1 else 0.; bought=buy/p['repurchase_price'];pc-=buy;n-=bought;treasury+=bought
        equity_in=0.
        if year==p['treasury_transfer_year']:
            equity_in=treasury*p['treasury_transfer_price'];pc+=equity_in;n+=treasury;treasury=0.
        # Never borrow solely to preserve target dividend. First cancel/reduce dividend.
        target=max(0.,nopat-minority)*p['payout'];dist=min(target,max(0.,pre),max(0.,pc-p['parent_min']))
        pc-=dist;pre-=dist
        need=max(0.,p['parent_min']-pc)+max(0.,subsidiary_min+restricted-sc)
        borrow=min(need,max(0.,p['debt_limit']-debt));debt+=borrow
        topup=min(borrow,max(0.,p['parent_min']-pc));pc+=topup;sc+=borrow-topup
        shortfall=max(0.,need-borrow)
        if shortfall>1e-9:feasible=False
        assert abs(pc+sc-(start+parent_cf+sub_cf-buy+equity_in-dist+borrow))<1e-8
        assert pre>=-1e-9 or dist==0
        rows.append(dict(year=year,calendar_proxy=2026+year,revenue=rev,nopat=nopat,minority=minority,maintenance=rev*.025,DA=rev*.025,growth_capex=cap,working_capital=wc,common_operating_cash=nopat-minority-cap-wc-p['loss_sub'][i]-p['extra_cost'][i]-interest,subs_profit=sub_op,subs_reserve=reserve,subs_legal_retained=sre,declaration=declare,dividend_arrival=pay,old_dividend_receipt=settled,dividend_receivable=arrears,parent_legal_profit=parent_op+pi+declare,parent_retained=pre,parent_cash=pc,subs_cash=sc,restricted=restricted,cash=pc+sc,minimum_cash=rev*p['min_cash_ratio'],debt=debt,financing_cost=interest,new_financing=borrow,unfunded_even_zero_dividend=shortfall,distribution=dist,dps=dist/n,shares=n,repurchase=buy,equity_receipts=equity_in,internal_payment=transfer))
        if not feasible:
            return {'feasible':False,'rows':rows,'failure_year':year,'failure_reason':'Even zero dividend and exhausted financing cap cannot fund required cash; no later operating/terminal value is asserted.'}
    rev6=p['revenues'][-1]*(1+p['g']);np6=rev6*p['terminal_margin']*(1-p['tax'])
    delta=rev6-p['revenues'][-1];reinvestment=delta*(p['terminal_capital_intensity']+p['min_cash_ratio'])
    fcf6=np6-p['minority'][-1]*(1+p['g'])-reinvestment # unlevered operating cash; actual debt deducted ONCE from asset bridge
    excess=pc+sc-p['revenues'][-1]*p['min_cash_ratio']-debt-restricted
    sub_available=max(0.,sc-(p['revenues'][-1]*p['min_cash_ratio']-p['parent_min'])-restricted)
    terminal_old_receipt=min(arrears,sub_available)
    terminal_declaration=min(max(0.,sre),max(0.,sub_available-terminal_old_receipt))
    terminal_loan_repayment=max(0.,sub_available-terminal_old_receipt-terminal_declaration)
    release_bridge={'parent_excess_cash':pc-p['parent_min'],'subs_excess_cash':sub_available,'old_dividend_receipt':terminal_old_receipt,'new_dividend_declaration':terminal_declaration,'internal_principal_repayment_needed':terminal_loan_repayment,'parent_legal_profit_after_declaration':pre+terminal_declaration,'cash_release_before_debt':pc-p['parent_min']+sub_available}
    return {'terminal_release_bridge':release_bridge,'feasible':feasible,'rows':rows,'terminal_revenue':rev6,'terminal_nopat':np6,'terminal_reinvestment':reinvestment,'terminal_fcf':fcf6,'terminal_excess_cash':excess,'terminal_shares':n,'g':p['g']}

def value(path,r):
    if not path['feasible']:return {'value':None,'terminal':None,'terminal_pv_share':None}
    tv=(path['terminal_fcf']/(r-path['g'])+path['terminal_excess_cash'])/path['terminal_shares']
    pv=sum(x['dps']/(1+r)**x['year'] for x in path['rows']);tpv=tv/(1+r)**5
    return {'value':pv+tpv,'terminal':tv,'terminal_pv_share':tpv/(pv+tpv)}

def build():
    paths={};p=copy.deepcopy(BASE);paths['base']=run(p)
    cyc=copy.deepcopy(BASE);cyc.update(revenues=[7.2,7.4,8.0,8.6,9.0],margins=[.06,.07,.085,.095,.097],growth_capex=[.10,.08,.08,.08,.08],working_capital=[.25,.08,-.05,.10,.072],upstream=.60,parent_extra_transfer=[.15,0,0,0,0]);paths['cyclical']=run(cyc)
    bear=copy.deepcopy(BASE);bear.update(revenues=[7.0,6.8,6.6,6.5,6.5],margins=[.05,.035,.03,.03,.03],growth_capex=[.08,.04,.03,.02,.02],working_capital=[.20,.10,.05,0,0],extra_cost=[.15,0,0,0,0],upstream=.50,terminal_margin=.03,g=0.,payout=.50,parent_extra_transfer=[.30,0,0,0,0]);paths['structural']=run(bear)
    bull=copy.deepcopy(BASE);bull.update(revenues=[8.,8.6,9.3,10.,10.6],margins=[.10,.105,.11,.11,.11],growth_capex=[.16,.14,.14,.12,.12],working_capital=[.15,.108,.126,.126,.108],terminal_margin=.11,g=.025);paths['upside']=run(bull)
    stress=copy.deepcopy(BASE);stress.update(margins=[-.15,-.10,.0,.03,.05],loss_sub=[.4,.3,0,0,0],working_capital=[.6,.3,.1,0,0],parent_extra_transfer=[.6,0,0,0,0],debt_limit=.20);paths['liquidity_failure']=run(stress)
    sens={}
    for key,dm in [('margin_minus_1pp',-.01),('margin_plus_1pp',.01)]:
        q=copy.deepcopy(BASE);q['margins']=[x+dm for x in q['margins']];q['terminal_margin']+=dm;sens[key]=value(run(q),.10)
    q=copy.deepcopy(BASE);q['arrival']=.25;q['parent_extra_transfer']=[.3,0,0,0,0];sens['upstream_delay_and_parent_payment']=value(run(q),.10)
    q=copy.deepcopy(BASE);q['treasury_transfer_year']=99;q['treasury_transfer_price']=0;sens['no_transfer_cancel_after_expiry']=value(run(q),.10)
    for years in [3,5]:
        path=paths['base'];r=.10
        delayed=copy.deepcopy(path)
        delayed['terminal_excess_cash']*=((1+BASE['cash_yield'])/(1+r))**years
        sens['terminal_financial_assets_release_delay_'+str(years)]=value(delayed,r)
    # Formal valuation function hand case: five 1 dividends, perpetual annual 1, r10%, g0 -> 10.
    simple={'feasible':True,'rows':[{'year':i,'dps':1.} for i in range(1,6)],'terminal_fcf':1.,'terminal_excess_cash':0.,'terminal_shares':1.,'g':0.}
    assert abs(value(simple,.1)['value']-10)<1e-12
    assert legal_step(-2.,1.,.1)==(-1.,0.)
    assert legal_step(-1.,2.,.1)==(.9,.1)
    assert not paths['liquidity_failure']['feasible']
    # actual simulation known cash bridge through same run: no cap/WC/distribution/interest/equity, cash rises exactly five NOPATs.
    q=copy.deepcopy(BASE);q.update(revenues=[1]*5,margins=[.1]*5,tax=0,minority=[0]*5,growth_capex=[0]*5,working_capital=[0]*5,payout=0,upstream=0,cash_yield=0,buyback_year1=0,treasury_transfer_year=99,restricted0=0,min_cash_ratio=0,parent_min=0,cash0=2,parent_cash0=1)
    test=run(q);assert abs(test['rows'][-1]['cash']-2.5)<1e-12
    debt_test=copy.deepcopy(q);debt_test.update(margins=[0]*5,cash0=0,parent_cash0=0,min_cash_ratio=.10,parent_min=.05,financing_rate=.04,terminal_margin=0,g=0)
    debt_check=run(debt_test)
    assert debt_check['feasible']
    assert abs(debt_check['terminal_fcf'])<1e-12
    assert abs(debt_check['terminal_excess_cash']+debt_check['rows'][-1]['debt'])<1e-12
    core={str(r):value(paths['base'],r) for r in [.105,.10,.095]}
    equity_pv=sum((z['equity_receipts']-z['repurchase'])/1.10**z['year'] for z in paths['base']['rows'])
    method2={str(mult):((paths['base']['rows'][1]['nopat']-.005)*mult+C0-.8+equity_pv)/paths['base']['terminal_shares'] for mult in [12,14]}
    return {'units':'CNY billion; shares billion; per-share CNY','actuals':ACTUAL,'opening_net_financial_assets':C0,'base_assumptions':BASE,'paths':paths,'core':core,'method2':method2,'scenario_values':{k:value(v,.10 if k!='structural' else .115) for k,v in paths.items()},'sensitivity':sens,'formal_chain_tests':'perpetuity=10; loss recovery; cash 2->2.5; insolvent path fails'}

if __name__=='__main__':
    out=build();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['opening_net_financial_assets','core','method2','scenario_values','sensitivity']},ensure_ascii=False,indent=2))
