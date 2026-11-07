"""洽洽食品，2026-Q3；CNY billion，股数 billion。无网络/第三方依赖。
所有forecast为研究预算；actuals的期后兑债在opening仅扣一次。
"""
import json,copy
from pathlib import Path
ACTUAL={'cash_equivalents':3.11039224728,'trading_financial':1.23308011310,'deposits_current':.38220270827,'deposits_long':.35562269185,'short_debt':.9895,'due_liabilities':1.54880849806,'lease_debt':.00364909872,'redemption_paid':1.540700195,'minority_equity':.03593239247,'repurchase_paid':.001477064,'shares_issued':.505856969,'treasury_shares':.009460417}
# settle residual liabilities and bank debt pro forma; actual redemption is part of due_liabilities, NOT added again.
C0=sum(ACTUAL[k] for k in ['cash_equivalents','trading_financial','deposits_current','deposits_long'])-sum(ACTUAL[k] for k in ['short_debt','due_liabilities','lease_debt','minority_equity','repurchase_paid'])-.015-.008
BASE={'revenues':[7.70,8.10,8.50,8.90,9.30], 'margins':[.093,.096,.097,.097,.097], 'growth_capex':[.13,.10,.08,.08,.08], 'working_capital':[.10,.072,.072,.072,.072], 'tax':.25,'minority':[.005]*5,'g':.02,'terminal_margin':.097,'terminal_capital_intensity':.50,'payout':.70,'upstream':.72,'arrival':.75,'parent_operating_share':.10,'cash_yield':.015,'min_cash_ratio':.8/7.4,'parent_min':.30,'cash0':C0,'parent_cash0':1.20,'parent_re0':1.71515294101,'subs_re0':0.,'restricted0':.46,'parent_extra_transfer':[0]*5,'loss_sub':[0]*5,'debt_limit':.5,'financing_rate':.04,'buyback_year1':.05-ACTUAL['repurchase_paid'],'repurchase_price':20.,'treasury_transfer_year':2,'treasury_transfer_price':20.,'extra_cost':[0]*5}

# Actual registered capital differs from latest issued shares; treasury movements are not new registered capital.
BASE.update(parent_registered=.505855092,parent_paid=.505856969,parent_statutory=.2535,
 source_buffer=.10,tail_source_buffer=0.,tail_release=.10,parent_release=.10,
 restriction_parent_fraction=0.,restriction_release_year=10,restriction_exit_cost=0.,
 illiquid_book=.21359620125,mother_illiquid_book=.06056887145,illiquid_net_rate=.70,
 illiquid_year=10,illiquid_legal_haircut=.30,cash_release_delay=0,horizon=320,
 shares_issued=ACTUAL['shares_issued'],treasury_initial=ACTUAL['treasury_shares'])

def legal_step(re,profit,reserve_rate,registered=None,reserve=0.):
    # Source call without registered is explicitly a governance buffer, not a statutory reserve.
    eligible=max(0.,profit-max(0.,-re));addition=eligible*reserve_rate
    if registered is not None:addition=min(addition,max(0.,registered*.5-reserve))
    return re+profit-addition,addition

def run(p,years=5):
    pc=p['parent_cash0'];sc=p['cash0']-pc;pre=p['parent_re0'];sre=p['subs_re0'];arrears=0.;debt=0.
    rp=p['restricted0']*p['restriction_parent_fraction'];rs=p['restricted0']-rp
    registered=p['parent_registered'];paid=p['parent_paid'];statutory=p['parent_statutory']
    n=p['shares_issued']-p['treasury_initial'];treasury=p['treasury_initial'];rows=[]
    heldp=helds=0.;lastrev=p['revenues'][0]
    for i in range(years):
        year=i+1;start=pc+sc;olddebt=debt
        if i<5:
            rev=p['revenues'][i];margin=p['margins'][i];cap=p['growth_capex'][i];wc=p['working_capital'][i]
            minority=p['minority'][i];extra=p['extra_cost'][i];loss=p['loss_sub'][i];transfer=p['parent_extra_transfer'][i]
        else:
            rev=p['revenues'][-1]*(1+p['g'])**(year-5);margin=p['terminal_margin']
            cap=(rev-lastrev)*p['terminal_capital_intensity'];wc=0.
            minority=p['minority'][-1]*(1+p['g'])**(year-5);extra=loss=transfer=0.
        if year==6:heldp=max(0.,pc-p['parent_min']-rp);helds=max(0.,sc-(lastrev*p['min_cash_ratio']-p['parent_min'])-rs-arrears)
        locked=6<=year<6+p['cash_release_delay']
        interest=debt*p['financing_rate'];ebit=rev*margin
        nopat=ebit-max(0.,ebit)*p['tax'] # operating loss creates no immediate cash refund
        parent_op=nopat*p['parent_operating_share']-interest-extra
        sub_op=nopat*(1-p['parent_operating_share'])-minority-loss
        pi=pc*p['cash_yield'];si=sc*p['cash_yield']
        parent_cf=parent_op+pi-.2*(cap+wc);sub_cf=sub_op+si-.8*(cap+wc)
        pc+=parent_cf-transfer;sc+=sub_cf+transfer
        # Purpose-restricted funds are consumed only by capex of their modeled holder.
        rp=max(0.,rp-.2*cap);rs=max(0.,rs-.8*cap)
        restriction_unlocked=0.;unlock_p=unlock_s=0.;realization_cash=0.;parent_guard=source_guard=0.;exit_cost=0.
        if year==p['restriction_release_year']:
            # Conditional issuer/shareholder-approved project change/termination, not automatic law.
            restriction_unlocked=rp+rs;unlock_p=rp*(1-p['restriction_exit_cost']);unlock_s=rs*(1-p['restriction_exit_cost']);pc-=rp*p['restriction_exit_cost'];sc-=rs*p['restriction_exit_cost']
            parent_guard+=rp*p['restriction_exit_cost'];source_guard+=rs*p['restriction_exit_cost'];exit_cost=(rp+rs)*p['restriction_exit_cost'];rp=rs=0.
        if year==p['illiquid_year']:
            motherbook=min(p['illiquid_book'],p['mother_illiquid_book']);sourcebook=p['illiquid_book']-motherbook
            pc+=motherbook*p['illiquid_net_rate'];sc+=sourcebook*p['illiquid_net_rate'];realization_cash=p['illiquid_book']*p['illiquid_net_rate']
            # Net realization budget includes tax/fees. Book value is NOT tax basis.
            # Capacity haircut is a disclosed legal-budget guard, not invented FVOCI P&L recycling.
            parent_guard+=motherbook*p['illiquid_legal_haircut'];source_guard+=sourcebook*p['illiquid_legal_haircut']
        sre,buffer=legal_step(sre,sub_op+si-source_guard,p['source_buffer'] if year<=10 else p['tail_source_buffer'])
        smin=max(0.,rev*p['min_cash_ratio']-p['parent_min'])+rs+(helds if locked else 0.)
        pmin=p['parent_min']+rp+(heldp if locked else 0.)
        settled=min(arrears,max(0.,sc-smin));sc-=settled;pc+=settled;arrears-=settled
        source_release=p['tail_release']*max(0.,sc-smin-arrears) if year>=6 and not locked else 0.
        declare=max(0.,min(sre,max(0.,sub_op+si)*p['upstream']+source_release,max(0.,sc-smin)/max(p['arrival'],1e-9)))
        pay=declare*p['arrival'];sre-=declare;arrears+=declare-pay;sc-=pay;pc+=pay
        pre,addition=legal_step(pre,parent_op+pi+declare-parent_guard,.1,registered,statutory);statutory+=addition
        buy=min(p['buyback_year1'],max(0.,pc-pmin),max(0.,pc+sc-pmin-smin)) if year==1 else 0.;bought=buy/p['repurchase_price'];pc-=buy;n-=bought;treasury+=bought
        equity_in=0.;cancelled=0.
        if year==p['treasury_transfer_year'] and year<=5:
            equity_in=treasury*p['treasury_transfer_price'];pc+=equity_in;n+=treasury;treasury=0.
        if year==4 and p['treasury_transfer_year']>5:
            # Already-paid treasury cancellation: no new cash, no external-holder dividend.
            cancelled=treasury;registered-=cancelled;paid-=cancelled;treasury=0.
        target=max(0.,nopat-minority)*p['payout']+(p['parent_release']*max(0.,pc-pmin) if year>=6 and not locked else 0.)
        dist=min(target,max(0.,pre),max(0.,pc-pmin),max(0.,pc+sc-pmin-smin-debt));pc-=dist;pre-=dist
        need=max(0.,pmin-pc)+max(0.,smin-sc)
        borrow=min(need,max(0.,p['debt_limit']-debt));debt+=borrow
        topup=min(borrow,max(0.,pmin-pc));pc+=topup;sc+=borrow-topup
        shortfall=max(0.,need-borrow)
        # Cash after required floors first repays external borrowing, never debt-financed dividends.
        repay=min(debt,max(0.,pc-pmin)+max(0.,sc-smin-arrears))
        take=min(repay,max(0.,pc-pmin));pc-=take;sc-=repay-take;debt-=repay
        assert abs(pc+sc-(start+parent_cf+sub_cf-buy+equity_in-dist+borrow-repay+realization_cash-exit_cost))<1e-7
        rows.append(dict(year=year,calendar_proxy=2026+year,revenue=rev,nopat=nopat,minority=minority,maintenance=rev*.025,DA=rev*.025,growth_capex=cap,working_capital=wc,common_operating_cash=nopat-minority-cap-wc-loss-extra-interest,subs_profit=sub_op,source_profit_buffer=buffer,source_earnings_budget=sre,declaration=declare,dividend_arrival=pay,old_dividend_receipt=settled,dividend_receivable=arrears,parent_legal_profit=parent_op+pi+declare-parent_guard,parent_retained=pre,parent_statutory=statutory,parent_reserve_add=addition,parent_registered=registered,parent_paid=paid,parent_cash=pc,subs_cash=sc,restricted=rp+rs,parent_restricted=rp,source_restricted=rs,cash=pc+sc,minimum_cash=rev*p['min_cash_ratio'],debt=debt,financing_cost=interest,new_financing=borrow,loan_repayment=repay,unfunded_even_zero_dividend=shortfall,distribution=dist,dps=dist/n,shares=n,treasury=treasury,repurchase=buy,equity_receipts=equity_in,treasury_cancelled=cancelled,internal_payment=transfer,restriction_unlocked=restriction_unlocked,parent_restriction_net_unlocked=unlock_p,source_restriction_net_unlocked=unlock_s,illiquid_net_recovery=realization_cash,parent_realization_guard=parent_guard,source_realization_guard=source_guard))
        if shortfall>1e-9:return dict(feasible=False,rows=rows,failure_year=year,failure_reason='Required cash unfunded at zero dividends and finite financing limit',assumptions=p)
        lastrev=rev
    return dict(feasible=True,rows=rows,assumptions=p,terminal_shares=n,g=p['g'])

def asset_recovery_diagnostic(p,rows):
    """FIFO attribution to ACTUAL common cash; no extra value or legal dividend created."""
    fifth=rows[4];sm=max(0.,fifth['minimum_cash']-p['parent_min'])
    initial_p=max(0.,fifth['parent_cash']-p['parent_min']-fifth['parent_restricted'])
    initial_s=max(0.,fifth['subs_cash']-sm-fifth['source_restricted'])
    source={'source_Y5_surplus':initial_s};pending={'mother_Y5_surplus':initial_p,'source_Y5_surplus':0.}
    record={k:dict(net_principal=v,paid=0.,last_year=None) for k,v in [('mother_Y5_surplus',initial_p),('source_Y5_surplus',initial_s)]}
    def add(name,amount,is_source):
        if amount<=0:return
        record[name]=dict(net_principal=amount,paid=0.,last_year=None)
        pending[name]=0. if is_source else amount
        if is_source:source[name]=amount
    for x in rows[5:]:
        if x['illiquid_net_recovery']:
            mb=min(p['illiquid_book'],p['mother_illiquid_book']);add('mother_illiquid_net',mb*p['illiquid_net_rate'],False);add('source_illiquid_net',(p['illiquid_book']-mb)*p['illiquid_net_rate'],True)
        add('mother_restricted_net_release',x['parent_restriction_net_unlocked'],False)
        add('source_restricted_net_release',x['source_restriction_net_unlocked'],True)
        upstream=x['old_dividend_receipt']+x['dividend_arrival']
        for name in source:
            take=min(upstream,source[name]);source[name]-=take;upstream-=take;pending[name]+=take
        paid=x['distribution']
        for name in pending:
            take=min(paid,pending[name]);paid-=take;pending[name]-=take
            if take>1e-12:record[name]['paid']+=take;record[name]['last_year']=x['year']
    for v in record.values():v['unpaid']=v['net_principal']-v['paid']
    later={}
    for checkpoint in [20,80,160]:
        if len(rows)<=checkpoint:continue
        at=rows[checkpoint-1]
        m=max(0.,at['parent_cash']-p['parent_min']-at['parent_restricted'])
        s=max(0.,at['subs_cash']-max(0.,at['minimum_cash']-p['parent_min'])-at['source_restricted'])
        pending=m;left=s;paid=0.;last=None
        for future in rows[checkpoint:]:
            transfer=min(left,future['old_dividend_receipt']+future['dividend_arrival']);left-=transfer;pending+=transfer
            receipt=min(pending,future['distribution']);pending-=receipt;paid+=receipt
            if receipt>1e-12:last=future['year']
        later[str(checkpoint)]=dict(mother_surplus=m,source_surplus=s,paid=paid,last_year=last,unpaid=left+pending)
    return dict(later_cash_cohorts=later,cash_principal_batches=record,restricted_at_Y5=fifth['restricted'],restricted_used_for_capex_after_Y5=fifth['restricted']-sum(x['restriction_unlocked'] for x in rows[5:]),note='Funds spent on required capex become maintained productive assets, not an extra cash payout; ongoing cash flows carry their value.')

def value(path,r):
    if not path['feasible']:return dict(value=None,terminal=None,terminal_pv_share=None)
    future=run(path['assumptions'],path['assumptions']['horizon'])
    if not future['feasible']:return dict(value=None,terminal=None,terminal_pv_share=None,failure=future)
    rows=future['rows'];first=sum(x['dps']/(1+r)**x['year'] for x in rows[:5])
    tv=sum(x['dps']/(1+r)**(x['year']-5) for x in rows[5:]);last=tv/(1+r)**5
    return dict(value=first+last,terminal=tv,terminal_pv_share=last/(first+last),explicit_rows=rows[:5],tail_rows=rows[5:],asset_recovery=asset_recovery_diagnostic(path['assumptions'],rows),terminal_method='actual mother cash/legal future payments; no group balance or forced intercompany principal plug')
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
        q=copy.deepcopy(BASE);q['cash_release_delay']=years;sens['terminal_financial_assets_release_delay_'+str(years)]=value(run(q),.10)
    tests=production_tests()
    core={str(r):value(paths['base'],r) for r in [.105,.10,.095]}
    equity_pv=sum((z['equity_receipts']-z['repurchase'])/1.10**z['year'] for z in paths['base']['rows'])
    method2={str(mult):((paths['base']['rows'][1]['nopat']-.005)*mult+C0-.8+equity_pv+BASE['illiquid_book']*BASE['illiquid_net_rate']/1.10**BASE['illiquid_year'])/paths['base']['terminal_shares'] for mult in [12,14]}
    governance={}
    changes={'source_buffer_zero':dict(source_buffer=0.),'source_buffer_forever':dict(tail_source_buffer=.10),
      'slow_release':dict(tail_release=.05,parent_release=.05),'fast_release':dict(tail_release=.20,parent_release=.20),
      'source_half_payout':dict(upstream=.36),'all_restricted_at_parent':dict(restriction_parent_fraction=1.),
      'illiquid_recovery_50pct':dict(illiquid_net_rate=.5,illiquid_legal_haircut=.5),
      'illiquid_recovery_90pct':dict(illiquid_net_rate=.9,illiquid_legal_haircut=.1),
      'illiquid_year15':dict(illiquid_year=15),'full_book_legal_guard':dict(illiquid_legal_haircut=1.),
      'restriction_year15':dict(restriction_release_year=15),'restriction_loss10pct':dict(restriction_exit_cost=.1),
      'parent_operating_zero':dict(parent_operating_share=0.),'parent_operating_5pct':dict(parent_operating_share=.05),'horizon400':dict(horizon=400)}
    for key,updates in changes.items():q=copy.deepcopy(BASE);q.update(updates);governance[key]=value(run(q),.10)
    q=copy.deepcopy(bear);q.update(restriction_release_year=15,restriction_exit_cost=.1);governance['structural_restriction_late_loss']=value(run(q),.115)
    return dict(units='CNY billion; shares billion',actuals=ACTUAL,opening_net_financial_assets=C0,base_assumptions=BASE,paths=paths,core=core,method2=method2,scenario_values={k:value(v,.10 if k!='structural' else .115) for k,v in paths.items()},sensitivity=sens,capital_governance=governance,formal_chain_tests=tests)

def production_tests():
    q=copy.deepcopy(BASE);q.update(revenues=[1.]*5,margins=[1.]*5,tax=0.,minority=[0.]*5,growth_capex=[0.]*5,working_capital=[0.]*5,payout=1.,upstream=0.,cash_yield=0.,buyback_year1=0.,treasury_transfer_year=99,restricted0=0.,min_cash_ratio=0.,parent_min=0.,cash0=0.,parent_cash0=0.,parent_operating_share=1.,parent_re0=0.,parent_registered=1.,parent_paid=1.,parent_statutory=.5,shares_issued=1.,treasury_initial=0.,g=0.,terminal_margin=1.,illiquid_book=0.,horizon=400)
    v=value(run(q),.1);assert abs(v['value']-10)<1e-10
    q.update(revenues=[10.,0.,0.,0.,0.],parent_registered=20.,parent_paid=10.,parent_statutory=5.,shares_issued=10.)
    counter=run(q)['rows'][0];assert counter['parent_reserve_add']==1. and counter['distribution']==9.
    q.update(revenues=[-.5,.3,.3,0.,0.],cash0=1.,parent_cash0=1.)
    loss=run(q)['rows'];assert [round(r['distribution'],8) for r in loss[:3]]==[0.,0.,.09]
    q.update(parent_operating_share=0.,parent_cash0=0.,upstream=1.,arrival=1.)
    source=run(q)['rows'];assert [round(r['declaration'],8) for r in source[:3]]==[0.,0.,.09]
    q.update(tax=.25,parent_operating_share=1.,revenues=[-.5,.3,.3,0.,0.],cash0=1.,parent_cash0=1.)
    no_refund=run(q)['rows'][0];assert no_refund['nopat']==-.5
    return dict(negative_operating_tax_test=no_refund['nopat'],actual_source_loss=[r['declaration'] for r in source[:3]],actual_perpetuity=v['value'],registered20_paid10_reserve5_profit10=counter,loss_recovery=[r['distribution'] for r in loss[:3]])

if __name__=='__main__':
    out=build();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n');print({k:v['value'] for k,v in out['core'].items()});print({k:v['value'] for k,v in out['scenario_values'].items()})
