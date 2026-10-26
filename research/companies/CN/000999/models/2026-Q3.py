"""CR Sanjiu 2026-Q3. CNY billion except per share; pure standard library.
Four legal-source budgets, not audited segment forecasts. Fiscal rolling annual
periods end each 26 October 2027-2036. Historical 16-Oct-2026 dividend excluded.
"""
import json,copy,pathlib
S=1.664217858
W=[1.,1.,.28,.2908]
NAMES=['上市付款母公司','传统子公司归普通股经济池','天士力收购会计口径','昆药收购会计口径']
# Q3 liquid assets 7.494486bn less non-cash-equivalent 0.385396bn,
# less already distributed 0.690650bn. Allocation estimates anchored H1.
CASH=[1.7-.69065041107,1.109090077,3.1-(.94880497180-.69065041107),1.2]
DEBT=[2.,.2,.5,1.292514408]
MINC=[.4,.7,.6,.5]
BASE={'name':'base','legal_opening':[8.77745218836,4.,5.,1.],'reserve_rates':[0.,.10,.10,.10],'growth':.025,'r':.095,'g':.015,'roic':.14,'margin':1.,'capex_mult':1.,'delay':.25,'old_receipt':[.55,.55], 'pool_payment':0.,'debt_rate':.035,'cash_yield':.01,'payout':.50,'sub_payout':.45,'cash_transfer_to_T':0.,'rev':[3.,17.5,8.3,3.8], 'nopat':[.4,2.45,1.6,-.25],'capital':[2.5,7.,6.,3.5],'da_rate':[.04,.075,.065,.06], 'maintenance_ratio':1.12, 'nonop_asset':.65}
def operating(p):
    rev=p['rev'][:]; cap=p['capital'][:]; n=p['nopat'][:]; out=[]
    for t in range(1,11):
        gr=p['growth'] if t<=5 else p['growth']+(p['g']-p['growth'])*(t-5)/5
        if p['name']=='cyclical' and t<=2: gr=-.04 if t==1 else 0
        if p['name']=='structural': gr=-.01 if t<=5 else 0
        rows=[]
        for i in range(4):
            oldrev=rev[i]; rev[i]*=1+gr
            if i==3:
                # modest channel repair, no return to prior high profits
                schedule=[-.25,-.10,0,.12,.20,.22,.24,.26,.28,.30]
                if p['name']=='structural': schedule=[-.5]*5+[-.25,-.1,0.,0.,0.]
                if p['name']=='optimistic': schedule=[-.1,.1,.3,.4,.5,.55,.6,.65,.7,.75]
                nop=schedule[t-1]
            else:
                n[i]*=1+gr; nop=n[i]*p['margin']
                if p['name']=='cyclical' and t<=2: nop*=.85 if t==1 else .92
            if 'nopat_schedule' in p: nop=p['nopat_schedule'][t-1][i]
            da=cap[i]*p['da_rate'][i]
            maintenance=da*p['maintenance_ratio']
            # 15% sales incremental tangible/development capital and 12% incremental WC.
            expansion=max(0,rev[i]-oldrev)*.15
            wc=(rev[i]-oldrev)*.12
            if p['name']=='cyclical' and t==1: wc+=.15
            if p['name']=='cyclical' and t==3: wc-=.15
            capex=(maintenance+expansion)*p['capex_mult']; cap[i]+=capex-da
            fcf=nop+da-capex-wc
            rows.append({'revenue':rev[i],'nopat':nop,'da':da,'maintenance':maintenance,'capex':capex,'delta_wc':wc,'capital_end':cap[i],'fcff':fcf})
        out.append(rows)
    return out

def simulate(p):
    ops=operating(p); cash=CASH[:]; debt=DEBT[:]; legal=p['legal_opening'][:]; reserve_total=[0.]*4
    cash[0]-=p['cash_transfer_to_T'];cash[2]+=p['cash_transfer_to_T']
    pending=[0.,0.,0.,0.]; old=1.1; history=[]; pool=10.5 # internal net payable budget, NOT external debt
    for t,rows in enumerate(ops,1):
        begin=cash[:]; legal_begin=legal[:]; db=debt[:]; rec=[0.]*4; decl=[0.]*4; minority=0.; interest=[]; net=[]; reserve_add=[]
        for i,row in enumerate(rows):
            intr=debt[i]*p['debt_rate']*(.8 if row['nopat']>0 else 1.); earn=cash[i]*p['cash_yield']; interest.append(intr)
            net.append(row['nopat']-intr+earn)
            cash[i]+=row['fcff']-intr+earn
            provision=max(0.,net[-1])*p['reserve_rates'][i]
            reserve_add.append(provision);reserve_total[i]+=provision
            legal[i]+=net[-1]-provision # carry losses IN FULL; never clip legal balance
        # collect already recognized old Jiuxin receivable: NO new legal income.
        oldpay=min(old,p['old_receipt'][t-1] if t<=len(p['old_receipt']) else 0.,max(0,cash[1]-MINC[1]))
        cash[1]-=oldpay;cash[0]+=oldpay;old-=oldpay
        # repay a legitimate internal pool payable, not group external expenditure.
        settlement=p['pool_payment'] if t==1 else 0
        cash[0]-=settlement;cash[1]+=settlement;pool-=settlement
        for i in [1,2,3]:
            # ordinary budget limited by local legal distributable profit and money.
            ratio=p['sub_payout'] if i==1 else .50
            target=max(0,net[i])*ratio
            obligation=pending[i]
            available=max(0,cash[i]-MINC[i])
            rec[i]=min(obligation,available);cash[i]-=rec[i];pending[i]-=rec[i]
            available=max(0,cash[i]-MINC[i])
            decl[i]=min(target,max(0,legal[i]),available) # reserves not annualized
            immediate=decl[i]*(1-p['delay'])
            cash[i]-=immediate;pending[i]+=decl[i]-immediate;rec[i]+=immediate
            legal[i]-=decl[i]
            cash[0]+=rec[i]*W[i]; legal[0]+=decl[i]*W[i]
            minority+=rec[i]*(1-W[i])
        # shortfalls financed up to specific liquidity limit, then distributions flex.
        borrowing=[0.]*4; repayment=[0.]*4
        for i in range(4):
            borrowing[i]=max(0,MINC[i]-cash[i]);debt[i]+=borrowing[i];cash[i]+=borrowing[i]
            assert debt[i]<8, 'funding budget infeasible'
        common_profit=sum(net[i]*W[i] for i in range(4))
        target=max(0,common_profit)*p['payout']
        dividend=min(target,max(0,legal[0]),max(0,cash[0]-MINC[0]))
        cash[0]-=dividend;legal[0]-=dividend
        # no forced debt retirement: normal renewal; use surplus above 2x liquidity to repay.
        for i in range(4):
            repayment[i]=min(debt[i],max(0,cash[i]-2*MINC[i]))
            cash[i]-=repayment[i];debt[i]-=repayment[i]
        # consolidated cash conservation includes minority cash only, internal transfers cancel.
        netcf=sum(rows[i]['fcff']-interest[i]+begin[i]*p['cash_yield'] for i in range(4))
        assert abs(sum(cash)-sum(begin)-netcf+dividend+minority-sum(borrowing)+sum(repayment))<1e-8
        assert abs(sum(W[i]*(legal[i]-legal_begin[i]+reserve_add[i]-net[i]) for i in range(4))+dividend)<1e-8
        common_cash=sum(cash[i]*W[i] for i in range(4))
        common_debt=sum(debt[i]*W[i] for i in range(4))
        # internal dividend receivable matches sub liability; weighted elimination for parent.
        # cash already resides in sub at 100% pool; declared amounts payable minorities
        # remove full pending liability at sub then add parent's receivable => net adjustment zero for parent-owned share.
        # Correct ordinary equity bridge simply common cash-common debt; parent intercompany cancels.
        history.append({'year':t,'ops':rows,'cash':cash[:],'debt':debt[:],'legal_retained':legal[:],'statutory_reserve_add':reserve_add[:],'statutory_reserve_added_total':reserve_total[:],'dividend':dividend,'dps':dividend/S,'common_profit':common_profit,'minority_cash':minority,'declarations':decl,'receipts':rec,'old_receipt':oldpay,'old_receivable_end':old,'internal_pool_payable':pool,'pending':pending[:],'borrowing':borrowing,'repayment':repayment,'common_cash':common_cash,'common_debt':common_debt})
    return history

def operating_value(ops,start,r,g,roic):
    # continuation franchises renew assets via maintenance and growth capital.
    # Mature reinvestment g/ROIC; no patent-specific perpetuity or pipeline bonus.
    flows=[sum(W[i]*row['fcff'] for i,row in enumerate(year)) for year in ops]
    nop10=sum(W[i]*ops[-1][i]['nopat'] for i in range(4))
    terminal=nop10*(1+g)*(1-g/roic)/(r-g)
    value=sum(flows[t-1]/(1+r)**(t-start) for t in range(start+1,11))+terminal/(1+r)**(10-start)
    return value,terminal/(1+r)**(10-start)

def value(p):
    h=simulate(p);ops=[z['ops'] for z in h]
    # Enterprise cash valuation for year10 plus money/debt after distributions;
    # actual cash accumulation/interest/debt costs are carried through first ten years.
    _,tv=operating_value(ops,10,p['r'],p['g'],p['roic'])
    last=h[-1]; terminal10=tv+last['common_cash']-sum(W[i]*MINC[i] for i in range(4))-last['common_debt']+p['nonop_asset']
    pvdiv=sum(z['dividend']/(1+p['r'])**z['year'] for z in h)
    pvterm=terminal10/(1+p['r'])**10
    now=(pvdiv+pvterm)/S
    # year5 value of future 6-10 distributions + year10 terminal, independently dated.
    term5=(sum(z['dividend']/(1+p['r'])**(z['year']-5) for z in h[5:])+terminal10/(1+p['r'])**5)/S
    # Auxiliary capitalized operating earnings; subtract economic replenishment premium
    normal=sum(W[i]*(ops[0][i]['nopat']+ops[0][i]['da']-ops[0][i]['maintenance']) for i in range(4))
    opening=sum(W[i]*(CASH[i]-DEBT[i]) for i in range(4))
    auxiliary=[(normal*m+opening-sum(W[i]*MINC[i] for i in range(4))+p['nonop_asset'])/S for m in [13,15]]
    return {'parameters':p,'value_per_share':now,'terminal5_per_share':term5,'terminal_pv_share':pvterm/(pvdiv+pvterm),'auxiliary_range':auxiliary,'opening_common_net_liquid':opening,'history':h}

def selftest():
    global W,S,CASH,DEBT,MINC
    # Same actual operating valuation function: 4 legal buckets, fixed 1 cash earnings,
    # zero growth/capex, W first bucket=1; 10-year plus zero-growth perpetuity equals 10.
    op=[[{'fcff':1. if i==0 else 0.,'nopat':1. if i==0 else 0.} for i in range(4)] for t in range(10)]
    a,b=operating_value(op,0,.10,0,.15); assert abs(a-10)<1e-10
    a,b=operating_value(op,5,.10,0,.15); assert abs(a-10)<1e-10
    saved=(W,S,CASH,DEBT,MINC)
    try:
        W=[1.,0.,0.,0.];S=1.;CASH=[0.]*4;DEBT=[0.]*4;MINC=[0.]*4
        toy=copy.deepcopy(BASE)
        toy.update({'growth':0.,'g':0.,'r':.10,'nopat':[1.,0.,0.,0.],
                    'capital':[0.]*4,'rev':[0.]*4,'payout':1.,'cash_yield':0.,
                    'old_receipt':[],'nonop_asset':0.})
        test=value(toy)
        assert abs(test['value_per_share']-10.)<1e-9
        assert all(abs(z['dps']-1.)<1e-9 for z in test['history'])
        full=test['value_per_share']
        # Actual simulate/value loss-recovery chain: losses -1, then +.5,+1;
        # unverified entity reserves 10% of POSITIVE profit, full loss carried.
        CASH=[2.,0.,0.,0.]
        loss_toy=copy.deepcopy(toy)
        loss_toy.update({'legal_opening':[0.]*4,'reserve_rates':[.1,0.,0.,0.],
                         'debt_rate':0.,'nopat_schedule':[[-1.,0.,0.,0.],[.5,0.,0.,0.],[1.,0.,0.,0.]]+[[0.]*4 for _ in range(7)]})
        loss_test=value(loss_toy)
        lh=loss_test['history']
        assert abs(lh[0]['legal_retained'][0]+1.)<1e-9
        assert abs(lh[1]['legal_retained'][0]+.55)<1e-9
        assert lh[0]['dividend']==0 and lh[1]['dividend']==0
        assert abs(lh[2]['dividend']-.35)<1e-9
        assert abs(lh[2]['statutory_reserve_added_total'][0]-.15)<1e-9
        loss_expected=.35/1.1**3+2.15/1.1**10
        assert abs(loss_test['value_per_share']-loss_expected)<1e-9
        loss_hand={'legal_first2':[-1.,-.55],'year3_dividend':.35,'reserve_added':.15,'end_cash':2.15,'value':loss_test['value_per_share'],'independent_expected':loss_expected}
    finally:
        W,S,CASH,DEBT,MINC=saved
    return {'formal_function_flat_perpetuity':a,'full_value_function_hand_case':full,'expected':10.,'loss_recovery_full_value_case':loss_hand,'pass':True}

def main():
    cases={}
    for name,changes in {
      'base':{},'core_low':{'r':.10,'growth':.02,'roic':.12},'core_high':{'r':.09,'growth':.03,'roic':.15},
      'cyclical':{'name':'cyclical'},'structural':{'name':'structural','margin':.8,'g':0.,'roic':.10,'capex_mult':1.1},
      'optimistic':{'name':'optimistic','growth':.045,'margin':1.05},
      'upstream_delay':{'delay':1.,'old_receipt':[],'pool_payment':1.},
      'capital_plus20':{'capex_mult':1.2},'discount_plus100bp':{'r':.105},
      'profit_minus10':{'margin':.9},'debt_rate_plus200bp':{'debt_rate':.055},'terminal_low':{'r':.10},'terminal_high':{'r':.09},'sub_payout30':{'sub_payout':.30},'opening_attribution':{'cash_transfer_to_T':.5},'nonop_zero':{'nonop_asset':0.}
    }.items():
        p=copy.deepcopy(BASE);p.update(changes);cases[name]=value(p)
    out={'units':'CNY billion; per-share CNY','shares_billion':S,'opening_cash':CASH,'opening_debt':DEBT,'ownership':W,'selftest':selftest(),'cases':cases}
    pathlib.Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k: {'value':v['value_per_share'],'term5':v['terminal5_per_share'],'dps':[x['dps'] for x in v['history'][:5]]} for k,v in cases.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
