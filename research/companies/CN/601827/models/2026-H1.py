"""三峰环境有限期经营模型；金额十亿元，股数十亿股；标准库、无网络。"""
import json, math
from pathlib import Path
S=1.6719333; CASH=4.426616; DEBT=8.301204
HIST_OPERATING_CASH_OUT=3.95540311151
OPERATING_CASH0=HIST_OPERATING_CASH_OUT*2/12
# 期限组：明确合同终点优先；余额不伪装为逐厂核验，主路径2046，正常2044—2048。
KNOWN=[('同兴',1200,2027),('成都九江',1800,2033),('昆明一期',1000,2033),('六安',1800,2038),('丰盛',2400,2041),('大理',1200,2043),('东营',1200,2044),('百果园',4500,2045),('御临',3000,2047),('泰兴',800,2043)]
CAP=42564; REM=CAP-sum(x[1] for x in KNOWN)

def build(rem_end=2046, fee=70, recovery=.10, maint=.30, volume=1, cost=94, equip_margin=.28, prov=.85, sub_end=2038, shock_years=60, cash_months=2):
    rows=[]; op_cash=HIST_OPERATING_CASH_OUT*cash_months/12; cohorts=[]; reserve=0.; sub_ar=1.2; other_ar=2.655754-1.2; prev_wc=0.; cash=CASH; debt=DEBT; mac_ret=.025
    for t in range(1,61):
        y=2026+t
        vnow=volume if t<=shock_years else 1
        fnow=fee if t<=shock_years else 70
        qnow=recovery if t<=shock_years else .10
        active=(sum(c for _,c,e in KNOWN if y<=e)+(REM if y<=rem_end else 0))/CAP
        tonnes=16.24*min(1.02**t,1.10)*active*vnow # 百万吨
        kwh=min(350*1.004**t,365)
        power=tonnes*kwh*.335/1000
        provincial=tonnes*280*.1/1.13*prov/1000
        # 首年74%有效中央覆盖，截止2038线性退坡；独立于省级覆盖。
        central=tonnes*280*max(0,.65/1.13-.335-.1/1.13)*.74*max(0,(sub_end-y+1)/(sub_end-2026))/1000
        service=tonnes*fnow*1.005**min(t,20)/1000
        heat=.25*1.08**min(t,5)*active
        er=1.35*1.025**min(t,5)*(.95**max(0,t-10)) if t<=30 else 0
        mac=.2184*(1 if t<=8 else .95 if t==9 else 0) # 2026-09后剩约9年
        revenue=power+provincial+central+service+heat+er+mac
        # 国内现金成本、热成本、设备毛利、澳门现金利润率；共同费用保持收入相关。
        domestic=tonnes*cost*1.01**max(0,t-5)/1000+.07*active+heat*.45
        overhead=.413239*(active*.65+(er/1.35)*.35) if t<=30 else 0
        ebitda=power+provincial+central+service+heat-domestic+er*equip_margin+mac*.30-overhead-revenue*.007
        maintenance=maint*active+er*.015
        growth=.17*active if t<=5 else 0
        capex=maintenance+growth
        depreciation=.72*active+.04*(er/1.35)+sum(z['capex']/10 for z in rows[-9:])
        ebit=ebitda-depreciation
        tax_rate=.18 if y<=2029 else .20 if y==2030 else .25
        tax=max(0,ebit)*tax_rate
        sub_cash=sub_ar*qnow+central*.1
        new_sub_ar=sub_ar+central-sub_cash
        # 非中央旧净应收三年结清；新增服务约半年账期、设备约季账期。
        old_other=other_ar*[.5,.3,.2][t-1] if t<=3 else 0
        wc=service*.5+er*.25
        dwc=wc-prev_wc
        loss=(service+er)*.015
        # 旧应付全额偿付，既有存货/合同资产在三年释放；不再次在净债务桥扣。
        old_ap=1.765265*[.5,.3,.2][t-1] if t<=3 else 0
        asset_release=(.343175+.198987)*[.5,.3,.2][t-1] if t<=3 else 0
        quality=.343276/3 if t<=3 else 0
        expired=(sum(c for _,c,e in KNOWN if y==e)+(REM if y==rem_end else 0))/CAP
        transfer=.766507*1.025**t*expired
        refund=(power+provincial+sub_cash)*.065
        fcf=ebitda-tax-capex-(new_sub_ar-sub_ar)+old_other-dwc-loss-old_ap+asset_release-quality-transfer+refund
        # 必要运营现金是现有银行现金的用途划分，不是额外付款；规模退出后释放。
        op_cash_end=max(0,revenue-ebitda+tax)*cash_months/12
        op_cash_delta=op_cash_end-op_cash
        fcf_before_reserve=fcf
        fcf-=op_cash_delta
        # 联营已单列权益价值；这里只记录其股利用于集团资金承载检验。
        assoc=(.045*1.01**t if t<=25 else 0)+(.056535 if t==1 else 0)
        principal=min(debt,.55+({1:.999,2:.3,3:.35,4:.15}.get(t,0)))
        interest=debt*.025
        common=S*.266 if t<=5 else 0
        minority=.035 if t<=5 else 0
        shield=min(tax,interest*tax_rate)
        endcash=cash+fcf+op_cash_delta+assoc-interest+shield-principal-common-minority
        cohorts=[a*(1-qnow) for a in cohorts]+[central*.9]
        new_reserve=sum(a*[.05,.10,.20,.50,.80,1][min(len(cohorts)-i-1,5)] for i,a in enumerate(cohorts))
        credit=new_reserve-reserve+loss
        reserve=new_reserve
        profit=ebit-interest-tax+shield+.06*(1.01**t)-.088-credit-.06
        mac_profit=mac*.30*.88
        mac_ret+=mac_profit*.55*.6
        rows.append(dict(t=t,year=y,recovery=qnow,active=active,tonnes=tonnes,revenue=revenue,central=central,sub_cash=sub_cash,sub_ar=new_sub_ar,ebitda=ebitda,depreciation=depreciation,ebit=ebit,tax=tax,capex=capex,maintenance=maintenance,growth=growth,fcf=fcf,fcf_before_reserve=fcf_before_reserve,operating_cash_start=op_cash,operating_cash=op_cash_end,operating_cash_delta=op_cash_delta,excess_cash=endcash-op_cash_end,profit=profit,credit=credit,old_ap=old_ap,transfer=transfer,cash_start=cash,cash=endcash,interest=interest,principal=principal,debt_end=debt-principal,dividend=common,minority=minority,associate_dividend=assoc,tax_shield=shield,mac_fcf=mac*.30*.88,mac_minority_nav=mac_ret))
        assert abs(endcash-(cash+fcf+op_cash_delta+assoc-interest+shield-principal-common-minority))<1e-10
        op_cash=op_cash_end
        cash=endcash; debt-=principal; sub_ar=new_sub_ar; prev_wc=wc
    return rows

def value(rows,r=.07,start=0):
    # 设备第30年退出且清理营运资金；没有永续尾值。第60年残余补贴按继续收款几何PV。
    fcf_pv=sum(x['fcf']/(1+r)**(x['t']-start) for x in rows if x['t']>start)
    ar_tail=rows[-1]['sub_ar']*rows[-1]['recovery']/(r+rows[-1]['recovery'])/(1+r)**(60-start)
    assoc=sum(.045*1.01**t/(1+.09)**(t-start) for t in range(start+1,26))+.75/(1.09)**(25-start)
    assoc_receivable=.056535 if start==0 else 0
    # 澳门55%服务+已留存净金融权益；其它少数以0.85倍账面并随前5年留存增厚。
    mac=sum(x['mac_fcf']*.55/(1.09)**(x['t']-start) for x in rows if x['t']>start)
    nav=.025 if start==0 else rows[start-1]['mac_minority_nav']
    other=(.657388+.0566*.6*start)*.85
    minority=mac+nav+other
    cash=CASH if start==0 else rows[start-1]['cash']
    required_cash=rows[0]['operating_cash_start'] if start==0 else rows[start-1]['operating_cash']
    excess_cash=cash-required_cash
    debt=DEBT if start==0 else rows[start-1]['debt_end']
    total=fcf_pv+ar_tail+assoc+assoc_receivable+excess_cash-debt-minority
    return dict(per_share=total/S,fcf_pv=fcf_pv,ar_tail=ar_tail,assoc=assoc,assoc_receivable=assoc_receivable,cash=cash,required_cash=required_cash,excess_cash=excess_cash,debt=debt,minority=minority,terminal_share=ar_tail/max(fcf_pv+ar_tail,1e-9))

def run():
    base=build(); lo=build(rem_end=2044,maint=.33,prov=.8); hi=build(rem_end=2048,maint=.27,prov=.9)
    out={'shares':S,'units':'人民币十亿元/十亿股','known_groups':KNOWN,'remaining_capacity':REM,'base_rows':base,'base':[value(base,.075),value(base,.065)],'core':[value(lo,.075),value(hi,.065)],'year5':[value(lo,.075,5),value(hi,.065,5)],'base_year5':[value(base,.075,5),value(base,.065,5)],'sensitivities':{}}
    for name,args in [('operating_cash_3months',{'cash_months':3}),('sub_receipt_5pct',{'recovery':.05}),('maintenance_045',{'maint':.45}),('remaining_2042',{'rem_end':2042}),('remaining_2050',{'rem_end':2050}),('no_provincial',{'prov':0}),('cycle',{'volume':.95,'fee':67,'recovery':.08,'shock_years':3}),('structural',{'volume':.85,'fee':58,'cost':103,'equip_margin':.20,'maint':.4}),('upside',{'fee':75,'recovery':.15,'equip_margin':.30})]:
        rows=build(**args); out['sensitivities'][name]={'value':value(rows,.07),'year5':value(rows,.07,5),'min_cash5':min(x['cash'] for x in rows[:5])}
    out['normal_profit']=sum(z['profit'] for z in base[:3])/3
    out['pe']=[out['normal_profit']*m/S for m in [11,13]]
    parent_cash=3.519196; parent_re=3.025672; parent=[]
    for i,(principal,interest) in enumerate([(1.087613,.023212),(.384,.018347),(.35,.010460),(.15,.003390),(0,0)]):
        old=1.416211*([.9,.1,0,0,0][i]); recovery=1.479672 if i==0 else 0; pool=4.226397 if i==0 else 0
        end=parent_cash+.65+old+recovery-pool-principal-interest-S*.266-.084
        parent_re+=.65-.08-interest-S*.266
        parent.append(dict(year=i+1,start=parent_cash,new_dividend=.65,old_dividend=old,intercompany_recovery=recovery,pool_repaid=pool,principal=principal,interest=interest,common_dividend=S*.266,other_outflow=.084,end=end,retained_earnings=parent_re,group_cash=base[i]['cash']))
        parent_cash=end
    out['parent']=parent
    out['parent_half_recovery_min']=min(x['end'] for x in parent)-1.479672/2
    assert abs(sum(x['operating_cash_delta'] for x in base)+OPERATING_CASH0)<1e-10
    assert base[-1]['operating_cash']==0
    assert all(x['cash']>=x['operating_cash'] for x in base[:5])
    assert sum(c for _,c,_ in KNOWN)+REM==42564
    assert abs(sum([1/(1.1)**t for t in range(1,6)])-(1-1.1**-5)/.1)<1e-12
    assert all(x['active']==0 for x in base if x['year']>2047)
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k not in ['base_rows','known_groups']},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
