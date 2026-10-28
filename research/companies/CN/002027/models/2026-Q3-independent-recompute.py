"""独立字面输入复算：不导入生产模型，不从输出提取任何计算输入。"""
import json,math,pathlib,subprocess,tempfile,shutil,hashlib
ROOT=pathlib.Path(__file__).resolve().parent

def literal(m=.43,structural=False,normalized=False,asset_scale=1.):
    g=0. if structural else .015;capex=.20 if structural else .12;upstream=.9 if structural else .98
    liquid=3.37005689245+5.41729629228+.53050980819+.04-.4-.89487837921-.1-3-.09
    investments=(.08255321142+.68052811304+2.04129594824)*.8+.184221+.09
    liquid*=asset_scale;investments*=asset_scale
    target_assets=0.;target_cash=0.;target_legal=.10804049573*.90022
    parent_profit=7.99474198783;parent_reserve=4.44559442201;claims=6.9;parent_cash=0.;fundpool=0.
    rev=12.2;opcash=3.;last_effective=None;shares=14.442199726;results=[]
    for t in range(1,241):
        old=rev
        if t>1:rev*=1+(g if (normalized and t>=4) or t>5 else [.03,.03,.03,.02][t-2])
        if t==2:
            shares=15.976740235
            target_assets+=(1.87656154744-.5-.00052961208)*.90022*asset_scale
            payment=.0296495
        else:payment=0
        effective=rev*(.75 if structural else 1.)
        earnings=.8*(m-.04 if structural else m)*effective-.04
        nextbuffer=3*effective/12.2
        f=earnings-capex*effective/12.2-.22*max(0,effective-(last_effective if last_effective is not None else effective))-(nextbuffer-opcash)
        opcash=nextbuffer;last_effective=effective
        tp=(.06*1.1**min(t-2,4)*(1+g)**max(t-6,0)*.90022) if t>=2 else 0.
        if normalized and t>=4:tp=.066*(1+g)**(t-3)*.90022
        if structural and t>=2:tp=-.04*.90022
        tf=tp-(.02*.90022*(1+g)**max(t-2,0) if t>=2 else 0.)
        li=liquid*.015;ti=target_cash*.015
        investments*=1.01;target_assets*=1.01;fundpool*=1.01
        mature=investments*.2 if t>=6 else 0;investments-=mature
        tm=target_assets*.2 if t>=10 else 0;target_assets-=tm
        fund=.2 if t==1 else 0
        liquid+=f+li+mature-payment-fund;fundpool+=fund
        fundreturn=fundpool*.2 if t>=11 else 0.;fundpool-=fundreturn;liquid+=fundreturn
        target_cash+=tf+ti+tm
        if target_cash<0:liquid+=target_cash;target_cash=0
        signed_profit=tp+ti
        after=target_legal+signed_profit
        reserve_target=.1*max(0,min(signed_profit,after))
        target_legal=after-reserve_target
        target_up=min(target_cash,max(0,target_legal),max(0,tf+ti)+(target_cash*.1 if t>=10 else 0))
        target_cash-=target_up;target_legal-=target_up;liquid+=target_up
        declaration=upstream*max(0,earnings+li)+target_up
        reserve=min(declaration*.1,max(0,.5*shares-parent_reserve));parent_reserve+=reserve
        parent_profit+=declaration-reserve;claims+=declaration
        plan=.8*max(0,f+tf) if t<=5 else max(0,f+tf)+liquid*.1
        remittance=min(max(0,liquid),claims,max(0,f+target_up)+max(0,liquid)*.1,max(0,plan-parent_cash))
        parent_cash+=remittance
        paid=min(plan,parent_cash,max(0,parent_profit));parent_cash-=paid
        claims-=remittance;liquid-=remittance;parent_profit-=paid
        results.append((paid/shares,liquid+investments+target_cash+target_assets+parent_cash+fundpool,f,tf,shares,target_legal,target_up,earnings,tp))
    def price(r,start=0):
        coupons=sum(row[0]*math.pow(1+r,-(i+1)) for i,row in enumerate(results[start:]))
        d,c,f,tf,s,*_=results[-1]
        return coupons+((f+tf)*(1+g)/(r-g)+c)/s/(1+r)**(240-start)
    return {'low':price(.1),'high':price(.09),'terminal_low':price(.1,5),'terminal_high':price(.09,5),'year5_financial':results[4][1],'dps':[x[0] for x in results[:5]],'rows':results}

j=json.loads((ROOT/'2026-Q3-output.json').read_text());base=literal();sensitivity=literal(.41);structural=literal(structural=True);normal=literal(normalized=True);zero=literal(normalized=True,asset_scale=0.)
for answer,key in [(base,'base'),(sensitivity,'margin_minus_2pp'),(structural,'structural')]:
    result=j['scenarios'][key]
    for a,b in [('low','value_low'),('high','value_high'),('terminal_low','terminal_y5_low'),('terminal_high','terminal_y5_high')]:assert abs(answer[a]-result[b])<1e-10
    assert abs(answer['year5_financial']-result['years'][4]['ending_financial'])<1e-10
for idx,row in enumerate(structural['rows']):
    observed=j['scenarios']['structural']['years'][idx]
    assert abs(row[5]-observed['target_profit_budget'])<1e-9
    assert abs(row[6]-observed['target_upstream'])<1e-9
second={}
for name,r in [('low',.10),('high',.09)]:
    n=normal['rows'][2][7]+normal['rows'][2][8]
    f4=normal['rows'][3][2]+normal['rows'][3][3]
    cap=(f4+.04)/(r-.015)-.04/r
    pure=sum((x[2]+x[3])/x[4]/(1+r)**(i+1) for i,x in enumerate(normal['rows'][:3]))+cap/15.976740235/(1+r)**3
    value=pure+(zero[name]-pure)+(normal[name]-zero[name])
    assert abs(value-j['secondary'][name])<1e-10
    second[name]={'derived_PE':cap/n,'capitalized_operating_value':pure,'timing_adjustment':zero[name]-pure,'financial_contribution':normal[name]-zero[name],'value':value}
budget=.1-.3
assert abs(budget+.2)<1e-12
budget+=.15
assert budget<0
profit=.1;reserve=.1*(budget+profit);dividend=budget+profit-reserve
assert abs(dividend-.045)<1e-12 and abs(reserve-.005)<1e-12
for result in [base,sensitivity,structural,normal,zero]:result.pop('rows')
# Copy only model, execute from a different cwd, compare every output byte.
with tempfile.TemporaryDirectory(dir=ROOT) as d:
    p=pathlib.Path(d);shutil.copy2(ROOT/'2026-Q3.py',p/'2026-Q3.py')
    subprocess.run(['python',str(p/'2026-Q3.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    assert (p/'2026-Q3-output.json').read_bytes()==(ROOT/'2026-Q3-output.json').read_bytes()
report={'literal_structural':structural,'literal_secondary':second,'literal_loss_capital_recovery':{'capital_injection':.5,'post_loss_budget':-.2,'post_first_recovery':-.05,'recovered_profit_reserve':.005,'dividend':.045},'literal_base':base,'literal_margin_minus_2pp':sensitivity,'portable_full_output_bytes_equal':True,'production_hand_cases':j['tests']}
(ROOT/'independent-check-output.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
