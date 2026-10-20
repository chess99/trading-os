import json, math
from pathlib import Path
S0=3.12795823; TREASURY=.00753150
POOL=8.49254; DEPOSIT=6.38882; COMMITTED=1.14789
D=[.65,.72,.8,.88,.98]; SBS=[.30,.15,.074,.0096365,0]
G=[.14,.12,.08,.06,.03]; GM=[.60,.36,.30,.31,.45]
CAP=[.8,.45,.35,.35,.35]
RATE=.095; INTEREST=.012*(1-.15)
def asset_value(t=3,rate=RATE):
    # committed project capital supports the franchise; no standalone principal addition
    return POOL-DEPOSIT-COMMITTED+DEPOSIT*(1+INTEREST)**t/(1+rate)**t

def run(margin_shift=0, growth_scale=1, wc=.25, cap_scale=1):
    rev=[12.,10.,17.,3.,1.]; oldrev=38.6; cash=POOL; sh=S0
    parent=1.40549; pre=15.83695; gre=14.59953
    out=[]; recognition=[]; grants=[.0084864,.0084864*.6+.0008766,.0113152*.6+.0008766*.6,.0011688*.6,0]
    # First grant 100/60/60%, reserved grant 100/60/60% one year later.
    cumulative_d=.5
    for y in range(1,13):
        if y>1:
            scale=1 if y<=5 else max(0,(11-y)/6)
            growth=[(.025+(g*growth_scale-.025)*scale) for g in G]
            rev=[r*(1+g) for r,g in zip(rev,growth)]
        total=sum(rev); dr=total-oldrev
        gm=[g+margin_shift if i<4 else g for i,g in enumerate(GM)]
        gp=sum(r*m for r,m in zip(rev,gm)); sb=SBS[y-1] if y<=5 else 0
        np=(gp-total*.256+.35-sb)*.85
        capital=(CAP[y-1] if y<=5 else .08*dr)*cap_scale
        fcf=np+sb-capital-(wc+.025)*dr
        if y<=5:
            add=grants[y-1]
            # first H1 dividend is paid before first vesting; later annual distribution after vesting
            price=31.89-cumulative_d-(.33 if y==1 else 0)
            proceeds=add*price
            div=(sh-TREASURY)*.33+(sh+add-TREASURY)*.32 if y==1 else (sh+add-TREASURY)*D[y-1]
            interest=cash*INTEREST
            newcash=cash+fcf+interest+proceeds-div
            assert abs(newcash-cash-fcf-interest-proceeds+div)<1e-10
            pnp=(total*.95*(.35-.215)+.2-sb)*.85
            pcap=[.35,.2,.15,.15,.15][y-1]; sub=[.65,.35,.15,.15,.15][y-1]
            parent+=pnp+sb-.25*dr-pcap-sub+proceeds-div
            pre+=pnp-div;gre+=np+interest-div
            sh+=add;cash=newcash;cumulative_d+=D[y-1]
            recognition.append(proceeds)
            row={'year':y,'revenue':total,'operating_np':np,'fcf':fcf,'growth_capital':capital,'wc_and_reserve':(wc+.025)*dr,'sbs':sb,'shares':sh,'new_shares':add,'subscription':proceeds,'dividend_total':div,'interest_after_tax':interest,'cash':cash,'cash_excluding_deposit':cash-DEPOSIT,'parent_cash':parent,'parent_re':pre,'group_re':gre}
        else: row={'year':y,'revenue':total,'operating_np':np,'fcf':fcf,'growth_capital':capital,'wc_and_reserve':(wc+.025)*dr}
        out.append(row);oldrev=total
    tv=out[11]['fcf']*1.025/(RATE-.025)
    ev=sum(x['fcf']/(1+RATE)**x['year'] for x in out)+tv/(1+RATE)**12
    proceeds_pv=sum(a/(1+RATE)**(i+1) for i,a in enumerate(recognition))
    # DCF subtracts all capital explicitly: add committed cash once, as funding, unlike PE franchise reserve.
    dcf=(ev+asset_value()+COMMITTED+proceeds_pv)/sh
    terminal_reserve=out[5]['growth_capital']+out[5]['wc_and_reserve']
    terminal_extra=cash-terminal_reserve
    terminal=[(out[4]['operating_np']*m+terminal_extra)/sh for m in (18,21)]
    return {'years':out,'shares_y5':sh,'subscription_pv':proceeds_pv,'ev':ev,'dcf':dcf,'dcf_terminal_fraction':(tv/(1+RATE)**12)/ev,'terminal_reserve':terminal_reserve,'terminal_extra_cash':terminal_extra,'terminal':terminal}

base=run(); asset=asset_value(); adjusted=[5.5-POOL*INTEREST,6.2-POOL*INTEREST]
pe=[(n*m+asset+base['subscription_pv'])/base['shares_y5'] for n,m in zip(adjusted,[20,23])]
margin=42*.015*.85
sens={
'major_business_margin_minus_1_5pp':[( (n-margin)*m+asset+base['subscription_pv'])/base['shares_y5'] for n,m in zip(adjusted,[20,23])],
'deposit_recover_year5':[(n*m+asset_value(5)+base['subscription_pv'])/base['shares_y5'] for n,m in zip(adjusted,[20,23])],
'deposit_recover_year1':[(n*m+asset_value(1)+base['subscription_pv'])/base['shares_y5'] for n,m in zip(adjusted,[20,23])],
'wc40_dcf':run(wc=.4)['dcf'],'growth_capital_double_dcf':run(cap_scale=2)['dcf'],
'structural_dcf':run(margin_shift=-.05,growth_scale=.2,wc=.4,cap_scale=1.3)['dcf'],
'stronger_dcf':run(margin_shift=.005,growth_scale=1.1,wc=.2)['dcf']}
assert abs(asset_value(0)-(POOL-COMMITTED))<1e-10
assert all(x['parent_cash']>0 and min(x['parent_re'],x['group_re'])>0 for x in base['years'][:5])
assert base['shares_y5']<=S0+.03121
assert abs(sum(x['new_shares'] for x in base['years'][:5])+S0-base['shares_y5'])<1e-10
assert all(x['cash_excluding_deposit']>0 for x in base['years'][:5])
result={'unit':'亿元、亿股、元/股','parameters':{'pool':POOL,'deposit':DEPOSIT,'committed_capital':COMMITTED,'deposit_recovery_year':3,'interest_after_tax':INTEREST,'cost_of_equity':RATE,'normal_operating_profit_range':adjusted,'pe_multiples':[20,23]},'financial_asset_pv':asset,'base':base,'core_pe':pe,'core_rounded':[round(v,2) for v in pe],'sensitivity':sens,'distributions':D,'terminal_rounded':[round(v,2) for v in base['terminal']],'checks':'cash conservation, legal distribution, liquid funds, shares, zero-delay asset special case passed'}
Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['financial_asset_pv','core_pe','terminal_rounded','sensitivity']},ensure_ascii=False,indent=2))
