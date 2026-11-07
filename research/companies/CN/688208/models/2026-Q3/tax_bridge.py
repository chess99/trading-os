"""r3 production tax/location lifecycle. Cash holds are NOT additional value claims."""
from common import *


def config(c):
    b=c['tax_bridge']
    if not b['enabled'] or b['legacy_60pct_rest_flow_enabled'] or b['incremental_tax_already_in_pack']:
        raise ValueError('ambiguous/double tax or legacy cash attribution is forbidden')
    if not b['corporate_tax_already_in_pack']:raise ValueError('normal corporate tax pack must remain intact')
    for k in ('foreign_rest_fraction','new_profit_upstream_fraction','incremental_repatriation_tax_rate'):
        valid=ZERO<=D(b[k])<ONE if k=='incremental_repatriation_tax_rate' else ZERO<=D(b[k])<=ONE
        if not valid:
            raise ValueError('tax/location parameter outside declared domain: '+k)
    if c.get('mode')=='company':
        observed=M(c['observed']['q3_existing_repatriation_dtl'])
        if M(b['old_tax_initial'])!=observed or M(b['old_parent_RE_unrecognized_hold'])!=observed:
            raise ValueError('both company conditions require full observed legacy cash and RE protection')
    return b


def initialize(s,c):
    b=config(c)
    s.update({'foreign_cash':M(b['foreign_initial_cash']),
              'foreign_old_profit_pool':M(b['foreign_old_profit_pool']),
              'old_tax_remaining':M(b['old_tax_initial']),
              'old_tax_parent_RE_hold':M(b['old_parent_RE_unrecognized_hold']),
              'new_tax_remaining':M(b['initial_new_tax']),
              'foreign_new_re':M(b['initial_foreign_new_RE']),
              'foreign_new_gross_profit_pool':ZERO,'new_tax_batches':[],
              'upstream_target_pending':ZERO,'tax_events':[]})
    if s['new_tax_remaining']!=0:raise ValueError('nonzero initial new tax requires identified recovered batch input')
    if not ZERO<=s['old_tax_parent_RE_hold']<=s['old_tax_remaining']:raise ValueError('invalid initial legacy RE hold')
    s['other_cash']=s['cash']-s['mother_cash']-s['nci_cash']-s['foreign_cash']
    # Negative initial location is visible in strict snapshot, never clipped/min-scaled.
    return s


def requirements(s,c):
    b=config(c);bg=s['buffer']+s['deposits'];be=s['nci_buffer']+s['nci_deposits']
    bm=ceil_money(D(b['mother_operating_buffer_fraction'])*s['buffer'])
    residual=bg-bm-be
    if residual<0:raise ValueError('fixed operating location requirements exceed original group requirement')
    bf=M(residual*D(b['foreign_remaining_requirement_fraction']));bo=residual-bf
    if bf<0 or bo<0:raise ValueError('invalid remaining requirement allocation')
    old=s['old_tax_remaining'];new=s['new_tax_remaining']
    rg=bg+old+new;rm=bm+old;rf=bf+new
    slacks={'group':s['cash']-rg,'mother':s['mother_cash']-rm,'entity':s['nci_cash']-be,
            'foreign':s['foreign_cash']-rf,'other':s['other_cash']-bo}
    return {'required_group':rg,'required_mother':rm,'required_entity':be,'required_foreign':rf,'required_other':bo,
            'operating_group':bg,'operating_mother':bm,'operating_entity':be,'operating_foreign':bf,'operating_other':bo,
            'legacy_tax_hold_mother':old,'new_tax_hold_foreign':new,
            'mother_available_RE':s['mother_re']-s['old_tax_parent_RE_hold'],
            'slacks':slacks,'strict_feasible':all(v>=0 for v in slacks.values()),
            'location_cash_residual':s['cash']-s['mother_cash']-s['nci_cash']-s['foreign_cash']-s['other_cash']}


def returns(s,c,days):
    req=requirements(s,c);a=c['assumptions'];r=D(a['financial_yield_pretax'])
    # All four stocks have unique ownership. Both tax holds earn no return.
    out={}
    for name,key,rate in [('mother','mother_cash',a['mother_tax_rate']),('entity','nci_cash',a['tax_rate']),
                          ('foreign','foreign_cash',a['tax_rate']),('other','other_cash',a['tax_rate'])]:
        out[name]=M(max(ZERO,s[key]-req['required_'+name])*r*D(days)*(1-D(rate))/365)
    out['group']=sum(out.values());return out


def accrue_new(s,c,d,profit,kind):
    """Tax all new positive gross after-normal-tax profits, including retained portions."""
    b=config(c);profit=M(profit);positive=max(ZERO,profit);tax=M(positive*D(b['incremental_repatriation_tax_rate']))
    s['foreign_new_re']+=profit-tax
    if positive:
        batch={'id':iso(d)+':'+kind,'date':d,'kind':kind,'original_profit':positive,'original_tax':tax,
               'gross_remaining':positive,'tax_remaining':tax}
        if any(x['id']==batch['id'] for x in s['new_tax_batches']):raise ValueError('duplicate new tax recognition')
        s['new_tax_batches'].append(batch);s['foreign_new_gross_profit_pool']+=positive;s['new_tax_remaining']+=tax
        s['upstream_target_pending']+=M(positive*D(b['new_profit_upstream_fraction']))
    return tax


def apply_income(s,p,c,financial):
    b=config(c);f=D(b['foreign_rest_fraction'])
    fc=M(p['rest']['actual_cash']*f);mc=p['rest']['actual_cash']-fc
    fp=M(p['rest']['profit']*f);mp=p['rest']['profit']-fp
    s['foreign_cash']+=fc+financial['foreign'];s['other_cash']+=financial['other']
    s['mother_cash']+=mc+financial['mother']
    operating_tax=accrue_new(s,c,p['date'],fp,'operating_after_normal_tax')
    financial_tax=accrue_new(s,c,p['date'],financial['foreign'],'financial_after_normal_tax')
    return {'mother_operating_actual':mc,'foreign_operating_actual':fc,'mother_direct_profit':mp,
            'foreign_operating_profit':fp,'new_tax_operating_accrual':operating_tax,
            'new_tax_financial_accrual':financial_tax,'new_tax_accrual':operating_tax+financial_tax,
            'mother_direct_taxable':p['rest']['ebit']-M(f*p['rest']['ebit'])}


def preview_batch_payment(s,gross):
    gross=M(gross)
    if gross<0 or gross>s['foreign_new_gross_profit_pool']:raise ValueError('new profit batch overdraw')
    left=gross;tax=ZERO;uses=[]
    for batch in s['new_tax_batches']:
        take=min(left,batch['gross_remaining'])
        if take:
            paid=batch['tax_remaining'] if take==batch['gross_remaining'] else M(batch['tax_remaining']*take/batch['gross_remaining'])
            uses.append({'id':batch['id'],'gross':take,'tax':paid});tax+=paid;left-=take
        if left==0:break
    if left:raise ValueError('batch pool identity failure')
    return tax,uses


def settle_quarter(s,c,d):
    """No parent support or extra loan. Pending target is not a free claim on old profits."""
    zero={'gross':ZERO,'tax_paid':ZERO,'net_mother':ZERO,'uses':[]}
    if d.month not in (3,6,9,12) or d!=month_end(d.year,d.month):return zero
    req=requirements(s,c)
    upper=max(ZERO,min(s['upstream_target_pending'],s['foreign_new_gross_profit_pool']))
    def allowed(gross):
        tax,_=preview_batch_payment(s,gross);net=gross-tax
        return net<=s['foreign_new_re'] and s['foreign_cash']-gross>=req['operating_foreign']+s['new_tax_remaining']-tax
    # At negative RE or reserve deficit zero is not treated as remedial distribution.
    if not allowed(ZERO):return zero
    lo=0;hi=int(upper/CENT)
    while lo<hi:
        mid=(lo+hi+1)//2
        if allowed(D(mid)*CENT):lo=mid
        else:hi=mid-1
    gross=D(lo)*CENT;tax,uses=preview_batch_payment(s,gross);net=gross-tax
    byid={b['id']:b for b in s['new_tax_batches']}
    for u in uses:
        byid[u['id']]['gross_remaining']-=u['gross'];byid[u['id']]['tax_remaining']-=u['tax']
    s['foreign_cash']-=gross;s['mother_cash']+=net;s['cash']-=tax
    s['new_tax_remaining']-=tax;s['foreign_new_gross_profit_pool']-=gross;s['foreign_new_re']-=net
    s['upstream_target_pending']-=gross
    if gross:s['tax_events'].append({'date':d,'kind':'new_profit_upstream','payer':'foreign_rest','gross':gross,'tax_paid':tax,'mother_net':net,'uses':uses})
    return {'gross':gross,'tax_paid':tax,'net_mother':net,'uses':uses}


def legacy_event(s,c,d):
    item=config(c)['legacy_events'].get(iso(d),{});payment=M(item.get('payment',0));expense=M(item.get('parent_expense',0))
    if item.get('gross_old_upstream') is not None:raise ValueError('old gross upstream not authorised in this narrow policy')
    if payment<0 or payment>s['old_tax_remaining']:raise ValueError('legacy payment exceeds remaining tax')
    if expense<0 or expense>s['old_tax_parent_RE_hold']:raise ValueError('legacy mother expense exceeds unrecognized hold')
    s['cash']-=payment;s['mother_cash']-=payment;s['old_tax_remaining']-=payment
    s['old_tax_parent_RE_hold']-=expense
    if payment or expense:s['tax_events'].append({'date':d,'kind':'legacy_tax','payer':'mother','cash_payment':payment,'parent_expense':expense,'group_new_expense':ZERO})
    return {'payment':payment,'parent_expense':expense}


def claims(s):
    return {'old':s['old_tax_remaining'],'new':s['new_tax_remaining'],'total':s['old_tax_remaining']+s['new_tax_remaining']}


def operating_tax(c,rest_profit):
    return M(max(ZERO,M(D(config(c)['foreign_rest_fraction'])*rest_profit))*D(config(c)['incremental_repatriation_tax_rate']))
