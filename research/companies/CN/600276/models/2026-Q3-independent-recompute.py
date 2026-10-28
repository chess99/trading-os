#!/usr/bin/env python3
"""Independent Decimal ledger: reads public assumptions, never imports production.
Re-derives actual cash from direct accounting/cash equations, not business_fcf.
Compares all 25 paths and explicit legal-capacity and final valuation quantities.
"""
import json
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec=42
ROOT=Path(__file__).resolve().parent
Z=D(0);O=D(1)
def cv(x):
    if isinstance(x,bool) or isinstance(x,str) or x is None:return x
    if isinstance(x,(int,float)):return D(str(x))
    if isinstance(x,list):return [cv(v) for v in x]
    return {k:cv(v) for k,v in x.items()}
def calc(p):
    c,pc=p['cash'],p['parent_cash'];rp,rv=p['parent_retained'],p['parent_reserve']; debt=p['debt'];debt0=debt
    fixed,nwc,req=p['fixed'],p['nwc'],p['required_cash'];prod=p['products'][:];adv=p['advances'];assets=p['asset_net'];N=int(p['tail_end'])
    source=[[-p['subsidiary_loss_buffer']*s['weight'],Z] for s in p['sources']]; dividends=[];checkrows=[]
    def legal(r,s,x,capital):
        alloc=min(max(Z,capital/D(2)-s),max(Z,x-max(Z,-r))/D(10));return r+x-alloc,s+alloc
    for t in range(1,N+1):
        old_req=req
        if t<11:
            j=t-1;prod=[prod[a]*(O+p['growth'][a][j]) for a in range(3)]; revenue=sum(prod)
            lic=sum(p[a][j] for a in ('signed_near','milestones','new_deals','royalties'));revlic=lic+p['old_license_release'][j]
            ebit=sum(prod[a]*p['gross'][a] for a in range(3))+revlic-lic*p['license_cost']-revenue*sum([p['sales'][j],p['admin'][j],p['rd'][j],p['other']])
            depreciation=revenue*p['depreciation_ratio'];investment=(depreciation+p['g']*fixed) if p['normalize_after_year3'] and t>3 else p['capex'][j];cs,ps=p['parent_cash_share'],p['parent_profit_share'];funding=p['parent_funding'][j]+p['parent_extra_payment'][j]
            comp=(-p['employee_payment'] if t==1 else p['employee_receipt'] if t==2 else Z)+(p['employee_non_cash'] if t<=3 else Z);sale=paydebt=Z
        else:
            if t==11: repayment_schedule=adv/p['release_window']
            scale=(O+p['g'])**(t-10); revenue=revenue10*scale;lic=lic10*scale;revlic=lic;ebit=ebit10*scale
            depreciation=revenue*p['depreciation_ratio'];investment=depreciation+p['g']*fixed;cs,ps=p['tail_parent_cash_share'],p['tail_parent_profit_share'];funding=comp=Z
            sale=min(assets,p['asset_net']/p['release_window']);assets-=sale;paydebt=min(debt,debt0/p['release_window'])
        newnwc=revenue*p['nwc_ratio'];req=revenue*p['required_cash_ratio'];nopat=ebit-max(ebit,Z)*p['tax']
        fin=(c*p['cash_yield']-debt*p['debt_rate'])*(O-p['tax']);pfin=(pc*p['cash_yield']-debt*p['debt_parent_share']*p['debt_rate'])*(O-p['tax'])
        # Literal source cash: aftertax full-R&D EBIT + depreciation - physical
        # investment - working capital + cash license less recognized license.
        cash_source=nopat+depreciation-investment+nwc-newnwc+lic-revlic
        claim=(p['accrued_interest'] if t==int(p['accrued_receipt_year']) else Z)+(p['restricted_deposit'] if t==int(p['deposit_release_year']) else Z)
        c+=cash_source+fin+comp+sale-paydebt+claim
        pc+=cash_source*cs+pfin+comp+sale*p['asset_parent_share']-paydebt*p['debt_parent_share']-funding+claim*p['opening_claim_parent_share']
        adv+=funding;debt-=paydebt;fixed+=investment-depreciation;nwc=newnwc
        rp,rv=legal(rp,rv,nopat*ps+pfin,p['parent_registered'])
        sp=nopat*(O-ps)+fin-pfin
        for i,s in enumerate(p['sources']):source[i]=list(legal(source[i][0],source[i][1],sp*s['weight'],s['registered']))
        if t>10:
            repay=min(adv,repayment_schedule,max(Z,c-pc-req*(O-cs)));pc+=repay;adv-=repay
        friction=Z;upstream=Z
        if p['upstream_enabled'] and t>=p['upstream_start']:
            room=max(Z,c-pc-req*(O-cs))
            for i,s in enumerate(p['sources']):
                amount=min(max(Z,source[i][0]),room*s['weight']);source[i][0]-=amount
                net=amount*(O-p['upstream_friction']);pc+=net;rp+=net;c-=amount-net;friction+=amount-net;upstream+=amount
        if t<11:wanted=max(Z,nopat+fin)*p['payout'][t-1]
        else:
            denominator=max(O,p['release_window']-D(t-11)) if t<=10+p['release_window'] else p['release_after_window']
            # Sustainable cash = direct cash source - required cash increase + net finance.
            sustainable=max(Z,cash_source-req+old_req+fin-friction)
            wanted=sustainable+max(Z,c-req)/denominator
        div=min(wanted,max(Z,pc-max(p['parent_floor'],req*cs)),max(Z,rp),max(Z,c-req));pc-=div;c-=div;rp-=div
        dividends.append(div)
        checkrows.append(dict(group_cash=c,parent_cash=pc,parent_retained=rp,parent_reserve=rv,operating_cash_before_finance=cash_source,finance_income=fin,parent_finance_income=pfin,dividend=div,required_cash=req,advances=adv,upstream_gross=upstream,upstream_friction=friction,source_retained=[v[0] for v in source],source_reserve=[v[1] for v in source]))
        if t==10:revenue10,lic10,ebit10=revenue,lic,ebit
    tail=dividends[-1]*(O+p['g'])/(p['k']-p['g']);equity=sum(d/(O+p['k'])**(t+1) for t,d in enumerate(dividends))+tail/(O+p['k'])**N
    future5=sum(d/(O+p['k'])**(t+1-5) for t,d in enumerate(dividends) if t+1>5)+tail/(O+p['k'])**(N-5)
    return equity/p['shares'],future5/p['shares'],checkrows

def main():
    data=json.loads((ROOT/'2026-Q3-output.json').read_text());res={}
    for name,item in {**data['results'],**data['sensitivities'],**{k:v['result'] for k,v in data['auxiliary']['cases'].items()}}.items():
        value,t5,rows=calc(cv(item['parameters']));maxerr=Z
        for a,b in zip(rows,item['rows']):
            for k,v in a.items():
                if k=='source_retained':expected=[D(str(x['closing_retained'])) for x in b['sources']]
                elif k=='source_reserve':expected=[D(str(x['reserve'])) for x in b['sources']]
                else:expected=D(str(b[k]))
                errors=[abs(x-y) for x,y in zip(v,expected)] if isinstance(v,list) else [abs(v-expected)]
                maxerr=max(maxerr,*errors)
        error=abs(value-D(str(item['value_per_share']))); assert error<D('1e-9') and maxerr<D('1e-8'),(name,str(error),str(maxerr))
        assert abs(t5-D(str(item['year5_terminal_per_share'])))<D('1e-9')
        res[name]={'value_decimal':str(value),'year5_terminal_decimal':str(t5),'max_row_error':str(maxerr),'passed':True}
    boundary=data['results']['structural_adverse']['cash_recovery_boundary'];p=data['results']['structural_adverse']['parameters']
    for case in boundary['cases']:
        a=cv(case);delta=(a['net_receipt']-a['annual_income_removed']/D(str(p['k'])))/(O+D(str(p['k'])))**int(a['realization_year'])/D(str(p['shares']))
        assert abs(delta-a['value_delta_per_share'])<D('1e-12')
    aux_checks={}
    for name,item in data['auxiliary']['cases'].items():
        q=cv(item['result']['parameters']);z=cv(item['result']['rows'][2]);g=q['g'];k=q['k']
        recurring=z['ebit']-z['opening_license_release'];cap=z['fixed_assets']+z['nwc']+z['required_cash']
        c4=recurring*(O-q['tax'])*(O+g)+z['required_cash']*q['cash_yield']*(O-q['tax'])-g*cap
        multiple=c4/(k-g)/recurring
        assert abs(multiple-D(str(item['earnings_capitalization_multiple'])))<D('1e-10')
        first3=sum(D(str(z['dividend']))/(O+k)**z['year'] for z in item['result']['rows'][:3])
        assert abs(first3-D(str(item['first_three_actual_dividends_pv'])))<D('1e-10')
        aux_checks[name]={'derived_multiple_decimal':str(multiple),'first_three_dividends_pv_decimal':str(first3),'passed':True}
    result={'method':'Independent Decimal direct-source actual-cash and legal-capacity ledger; no import of production','paths':res,'conditional_recovery_cases':9,'normalized_earnings_capitalization':aux_checks,'passed':True}
    (ROOT/'independent-check-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'paths':len(res),'boundary_cases':9,'passed':True}))
if __name__=='__main__':main()
