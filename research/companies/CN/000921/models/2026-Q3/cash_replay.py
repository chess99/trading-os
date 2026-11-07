"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
from common import EconomicRefusal

def statute(profit,retained,registered,reserve,voluntary=0):
    # Full losses first; statutory cap uses registered, not paid-in or investment cost.
    eligible=max(0,profit-max(0,-retained))
    add=min(eligible*.1,max(0,registered*.5-reserve))
    voluntary_add=min(max(0,retained+profit-add),max(0,voluntary))
    return retained+profit-add-voluntary_add,reserve+add,add,voluntary_add

def parent_step(cash,retained,reserve,new_dividend,interest,old_receivable=0,loan_repayment=0,capital_principal=0,capital_gain=0,desired=1e99,registered=None):
    # Redemption/old receivable/principal are cash only; gain and NEW dividend enter income.
    if registered is None: raise ValueError('registered must be supplied explicitly')
    income=new_dividend+interest+capital_gain
    legal,rs,add,va=statute(income,retained,registered,reserve)
    available=cash+new_dividend+interest+old_receivable+loan_repayment+capital_principal+capital_gain
    if available < -1e-9:return dict(feasible=False,shortfall=-available)
    d=max(0,min(desired,available,legal))
    return dict(feasible=True,cash=available-d,retained=legal-d,reserve=rs,reserve_add=add,income=income,distribution=d)

def new_batch(batches,amount,t,delay,term):
    if amount>1e-11:batches.append(dict(origin=t,initial=amount,balance=amount,start=t+delay+1,end=t+delay+term,paid=0.,used=0.))

def consume(batches,amount):
    # Pro rata spending: no FIFO trick leaving newer cohorts indefinitely unvalued.
    total=sum(x['balance'] for x in batches)
    if amount>total+1e-8:return False
    if total:
        for x in batches:
            spent=x['balance']*amount/total;x['balance']-=spent;x['used']+=spent
    return True

def release(batches,t,capacity):
    due=[]
    for x in batches:
        if t>=x['start']:
            amount=x['balance'] if t>=x['end'] else x['balance']/(x['end']-t+1)
            due.append((x,amount))
    total=sum(a for _,a in due);factor=min(1,max(0,capacity)/total) if total else 0
    for x,a in due:
        x['balance']-=a*factor;x['paid']+=a*factor
        if a*factor>1e-11:x['last_payment']=t
    return total*factor,total

OLD_SHARES=1.384861171

def bridge(saved, shares=OLD_SHARES, registered=None, checkpoint=None):
    """P-only replay; B/R/J operating, tax, cash, payout routes remain saved inputs."""
    checkpoint=checkpoint or (lambda state:None)
    historical_copy=copy.deepcopy(saved)
    p=copy.deepcopy(saved['params']);registered=OLD_SHARES if registered is None else registered
    checkpoint({'phase':'input','params':p,'shares':shares,'registered':registered})
    cash=p['parent_start'];lp=6.03298055478;rp=.694073685;batches=[]
    new_batch(batches,cash,0,p['delay'],p['term']);rows=[];ds=[]
    for index,frozen in enumerate(saved['rows']):
        checkpoint({'phase':'year_open','year_index':index+1,'cash':cash,'retained':lp,'reserve':rp,'registered':registered,'shares':shares,'batches':copy.deepcopy(batches),'completed_rows':len(rows)})
        t=frozen['t'];old=frozen['P'];jr=frozen['J']['route'];start=cash
        interest=cash*p['y'];up=old['new_dividend'];jcapital_cash=old['japan_capital_cash']
        desired=[.65,.75,.85,.95,1.05][t-1]*shares if t<=5 else up+interest+jcapital_cash
        parent_capacity=max(0,lp+up+interest+jr['common_capital_pnl'])
        prelease,wanted=release(batches,t,max(0,parent_capacity-desired))
        if t>5:desired+=prelease
        z=parent_step(cash,lp,rp,up,interest,capital_principal=jr['common_capital_principal'],
          capital_gain=jr['common_capital_pnl'],desired=desired,registered=registered)
        if not z['feasible']: raise EconomicRefusal('hisense_parent_cash_exhausted',{'failure_row':{'year':t,'cash_open':cash,'retained_open':lp,'reserve_open':rp,'registered':registered,'new_upstream':up,'interest':interest,'capital_cash':jcapital_cash,'desired':desired,'unpaid_obligation':z['shortfall'],'batches':copy.deepcopy(batches)},'rows_before_failure':rows})
        d=z['distribution'];lp=z['retained'];rp=z['reserve']
        expected=cash+up+interest+jcapital_cash-d
        tracked=sum(x['balance'] for x in batches)
        if expected>tracked:new_batch(batches,expected-tracked,t,p['delay'],p['term'])
        elif not consume(batches,tracked-expected):raise AssertionError('parent cohort cash mismatch')
        cash=expected
        row=copy.deepcopy(frozen);row['shares']=shares;P=row['P']
        P.update(interest=interest,financial_gross_interest=start*p['y']/.75,
          financial_tax=start*p['y']/.75*.25,profit=z['income'],cash=cash,retained=lp,
          statutory_reserve=rp,reserve_add=z['reserve_add'],dividend=d,cohort_release=prelease)
        # Recompute common cash using untouched actual saved B/R/J components.
        end=.492*row['B']['cash']+row['R']['cash']+cash+.7094*row['J']['route']['cash']
        row['common_cash']=end+row['necessary_finance']
        row['available_common_cash']=end-.7094*row['J']['route']['cash']
        row['dividend_per_share']=d/shares
        row['parent_cash_residual']=start+up+interest+jcapital_cash-d-cash
        # The old complete-group residual remains in historical_copy, never relabelled current.
        if 'cash_residual' in row:del row['cash_residual']
        if abs(row['parent_cash_residual'])>1e-8:raise AssertionError('parent conservation')
        rows.append(row);ds.append(d/shares)
        checkpoint({'phase':'year_close','year':t,'row':row,'parent_batches':copy.deepcopy(batches)})
    r=p['r'];pv=sum(d/(1+r)**(i+1) for i,d in enumerate(ds))
    tv=sum(ds[i]/(1+r)**(i-4) for i in range(5,len(ds)))
    return {'feasible':True,'value':pv,'tv5':tv,'d5':ds[:5],
      'tv_pv_share':tv/(1+r)**5/pv if pv else 0,'params':p,'rows':rows,'parent_cohorts':batches,
      'shares':shares,'parent_registered_budget':registered,'new_cash_paid':0.,
      'historical_copy':historical_copy,'historical_copy_role':'Complete selected old record, exact and explicitly historical; includes B/R/J cohorts and old group cash_residual.'}


def reconstruct_selected(replayed):
    """Full old-selected schema reconstructed; no selected key is silently dropped.
    P/current cash fields come from actual recurrence; untouched fields come only from
    the separately identified historical container and are classified by field_ledger.
    """
    reconstructed=copy.deepcopy(replayed['historical_copy'])
    for k in ['feasible','value','tv5','d5','tv_pv_share','params']:
        reconstructed[k]=copy.deepcopy(replayed[k])
    for old,current in zip(reconstructed['rows'],replayed['rows']):
        for k in ['P','shares','dividend_per_share','common_cash','available_common_cash']:
            old[k]=copy.deepcopy(current[k])
    reconstructed['cohorts'][2]=copy.deepcopy(replayed['parent_cohorts'])
    return reconstructed
