"""CN601088 2026Q3; CNY billion, billion shares. Standalone finite-life legal-cash model.
Forecast years are anniversaries from 2026-10-26; y1 is next 12 months.
Parent own operations + operating subsidiaries (28% NCI) + common-attributed investments.
Restricted restoration cash excluded alongside matched existing restoration obligation;
new safety/restoration cost remains expensed. No perpetual terminal growth.
"""
import json, math
from pathlib import Path
SHARES=21.689434304
INITIAL={'parent_cash':45.426,'sub_cash':45.677,'parent_debt':52.8,'sub_debt':109.752,
         'parent_legal_re':165.353,'parent_pool_payable':140.,'financial_assets':65.,'mineral_payable':35.283}

def pv(flows,r,start=1):
    return sum(v/(1+r)**t for t,v in enumerate(flows,start))

def run(r=.08,capex_shift=0.,coal_price_shift=0.,life=40,scenario='base',upstream=.75,pool_payment=0.,interest_shift=0.,recovery_year=10,ownership=.72,toy=None):
    # Test inputs travel through the exact operating/cash/distribution/PV engine.
    if toy:
        life=toy['life']; initial=toy['initial']; subshare=toy['subshare']
    else: initial=INITIAL; subshare=ownership
    pc=initial['parent_cash']; sc=initial['sub_cash']; pd=initial['parent_debt']; sd=initial['sub_debt']; re=initial['parent_legal_re']; pool=initial.get('parent_pool_payable',0)
    asset=initial.get('financial_assets',0); mineral=initial.get('mineral_payable',0); rows=[]; sre=0.; treasury=0.
    for y in range(1,life+1):
        # Capacity maintained for 25 years, then phased retirement; all assets stop by y40.
        scale=1. if y<=life-15 else max(0.,(life-y)/15)
        growth=1+.005*min(y-1,5)
        cyc= .80 if scenario=='cycle' and y<=3 else 1.
        structural= .72 if scenario=='structural' and y>=2 else 1.
        upside=1.10 if scenario=='upside' and y>=3 else 1.
        if scenario=='structural': scale*=max(.30,1-.025*max(0,y-5))
        opfactor=scale*growth*cyc*structural*upside
        # Coal diagnostic: 380Mt external own coal, 20 yuan/t = CNY7.6bn pretax,
        # net 6% resource-tax feedback; downstream internal transfers excluded.
        delta=coal_price_shift*.380*.94*scale
        peb=28.*opfactor+.30*delta; seb=64.*opfactor+.70*delta
        pda=5.6*scale; sda=29.4*scale
        capex=(57. if y<=3 else 52. if y<=5 else 46.)*scale + capex_shift*scale
        if scenario=='cycle' and y<=3: capex-=4.*scale # defer nonessential expansion, no later growth bonus
        if scenario=='structural': capex=max(34.*scale,capex*.9)
        if scenario=='upside': capex+=4.*scale if y<=5 else 1.*scale
        pcap=capex*.24; scap=capex*.76
        # Separate old mineral/long-payable settlement from capital formation.
        mineral_pay=min(mineral,7.0566) if y<=5 else 0.
        mineral-=mineral_pay
        pmin=mineral_pay*.15; smin=mineral_pay*.85
        p_rate=.025+interest_shift; s_rate=.03+interest_shift
        exit_reserve=8.*min(1.,max(0.,(y-(life-10))/5))
        pmincash=10.*scale+exit_reserve; smincash=15.*scale
        tax=.22 if y<=4 else .245 if y==5 else .25
        p_ni=(peb-pd*p_rate+pc*.015)*(1-tax); s_ni=(seb-sd*s_rate+sc*.015)*(1-tax)
        fin_earnings=3. if asset>0 else 0.
        fin_income=fin_earnings*.60 # 40% retained at investees for necessary capital, not parent cash
        # Realization at y10 is an assumption, not an announced divestiture. No residual asset duplicate.
        asset_sale=asset if y==recovery_year else 0.
        asset-=asset_sale
        wc=1.0*scale if y<=5 else 0.
        pfcf=p_ni+pda-pcap-pmin-wc*.3
        sfcf=s_ni+sda-scap-smin-wc*.7
        # Matched restricted funds pay inherited restoration obligation. New ongoing obligations
        # are already expensed in EBIT and cash (no provision addback).
        if toy:
            z=toy['annual'];scale=1.;p_ni=z.get('pni',0);s_ni=z.get('sni',0);fin_income=0;fin_earnings=0;asset_sale=0
            pfcf=z.get('pfcf',0);sfcf=z.get('sfcf',0);pmincash=smincash=0.;p_rate=s_rate=0.
            pcap=scap=pmin=smin=wc=0.
        pc0,sc0,pd0,sd0=pc,sc,pd,sd
        pay=min(pool,pool_payment) if y==1 else 0.;pool-=pay
        release=treasury if y==3 else 0.; treasury+=pay-release
        pc+=pfcf+fin_income+asset_sale-pay+release; sc+=sfcf
        # Operating/capital cash deficits funded first; explicit policy-period dividend support below.
        pb=max(0.,pmincash-pc);sb=max(0.,smincash-sc)
        if not toy and (pd+pb>100 or sd+sb>160): raise ValueError('Unfundable operating path')
        pd+=pb;sd+=sb;pc+=pb;sc+=sb
        # Subsidiary dividend has independent statutory current-profit and cash tests.
        sre+=s_ni-max(0.,s_ni)*.1
        s_legal=max(0.,sre) # statutory reserve allowance; no accumulated subsidiary profits assumed available
        scheduled_s=sd/max(1,life-y) if y>life-15 and not toy else 0.
        scheduled_p=pd/max(1,life-y) if y>life-15 and not toy else 0.
        declared=min(max(0.,s_ni)*upstream,s_legal,max(0.,sc-smincash-scheduled_s))
        sc-=declared;sre-=declared; received=declared*subshare; nci_div=declared*(1-subshare);pc+=received
        # Declarations and cash receipts are same-year budget; no opening receivable counted as profit.
        parent_legal_profit=p_ni+fin_income+received
        re+=parent_legal_profit-max(0.,parent_legal_profit)*.10
        common_profit=p_ni+s_ni*subshare+fin_earnings
        desired=max(0.,common_profit)*.70
        if toy: desired=toy['annual'].get('desired',desired)
        if not toy and y<=2:
            policy_gap=max(0.,.65*max(0.,common_profit)-max(0.,pc-pmincash))
            policy_borrow=min(policy_gap,max(0.,100-pd))
            pd+=policy_borrow;pb+=policy_borrow;pc+=policy_borrow
        dividend=min(desired,max(0.,re),max(0.,pc-pmincash-scheduled_p));pc-=dividend;re-=dividend
        # Residual operating cash amortizes actual external debt; ordinary dividends may be reduced first.
        pr=min(pd,max(0.,pc-pmincash));sr=min(sd,max(0.,sc-smincash))
        pc-=pr;sc-=sr;pd-=pr;sd-=sr
        sx=min(max(0.,sc-smincash),max(0.,sre)) if sd<1e-9 and not toy else 0.
        sc-=sx;sre-=sx;declared+=sx;received+=sx*subshare;nci_div+=sx*(1-subshare)
        pc+=sx*subshare;re+=sx*subshare*.9;parent_legal_profit+=sx*subshare
        # Once external financing is extinguished, extra parent cash is returned, legal profit permitting.
        special=min(max(0.,pc-pmincash),max(0.,re)) if pd<1e-9 else 0.
        pc-=special;re-=special;dividend+=special
        # Subsidiaries retain undeclared profit. At final closure liquidation legally returns capital,
        # with residual NCI applied to subsidiary net assets and an explicit exit-cost provision.
        liquidation=0.
        if y==life:
            exitcost=0. if toy else 8.
            sub_net=sc-sd
            liquidation=pc-pd+subshare*sub_net+asset+treasury-exitcost
            dividend+=liquidation
            pc=sc=pd=sd=asset=0.
        if y<life:
            assert abs(pc-(pc0+pfcf+fin_income+asset_sale-pay+release+pb+received-dividend-pr))<1e-7
            assert abs(sc-(sc0+sfcf+sb-declared-sr))<1e-7
            assert abs(pd-(pd0+pb-pr))<1e-7 and abs(sd-(sd0+sb-sr))<1e-7
        rows.append(dict(year=y,scale=scale,parent_ebit=peb,sub_ebit=seb,common_profit=common_profit,
          parent_ni=p_ni,sub_ni=s_ni,parent_legal_profit=parent_legal_profit,parent_legal_re=re,sub_legal_re=sre,treasury_cash=treasury,
          parent_fcf=pfcf,sub_fcf=sfcf,capex=pcap+scap,mineral_payment=pmin+smin,nwc=wc,tax_rate=tax,
          parent_borrow=pb,sub_borrow=sb,parent_repayment=pr,sub_repayment=sr,
          sub_declared=declared,upstream_received=received,nci_dividend=nci_div,pool_settlement=pay,
          dividend=dividend,dps=dividend/(toy.get('shares',SHARES) if toy else SHARES),
          parent_cash=pc,sub_cash=sc,parent_debt=pd,sub_debt=sd,remaining_financial_assets=asset,
          remaining_mineral_payable=mineral,financial_profit=fin_earnings,financial_cash=fin_income,financial_retained=fin_earnings-fin_income,liquidation=liquidation))
    flows=[z['dps'] for z in rows]
    assert min(flows)>-1e-9, 'Shareholders cannot face an unfunded terminal cash call'
    value=pv(flows,r)
    return {'value':value,'year5_terminal':pv(flows[5:],r), 'terminal_pv_share':pv(flows[5:],r,start=6)/value if value else 0,
            'distributions':flows[:5],'rows':rows,'parameters':dict(r=r,capex_shift=capex_shift,coal_price_shift=coal_price_shift,life=life,scenario=scenario,upstream=upstream,pool_payment=pool_payment,interest_shift=interest_shift,recovery_year=recovery_year,ownership=ownership)}

def build():
    base=run();low=run(r=.085,capex_shift=2);high=run(r=.075,capex_shift=-2)
    cases={'base':base,'core_low':low,'core_high':high,'holder_low':run(r=.085),'holder_high':run(r=.075),'cycle':run(scenario='cycle'),
      'structural':run(scenario='structural',life=30),'upside':run(scenario='upside'),
      'coal_minus20':run(coal_price_shift=-20),'capex_plus5':run(capex_shift=5),
      'life30':run(life=30),'rate9':run(r=.09),'upstream50_pool10':run(upstream=.5,pool_payment=10),
      'interest_plus1pct':run(interest_shift=.01),'financial_recovery40':run(recovery_year=40),'sub_ownership68':run(ownership=.68),'sub_ownership76':run(ownership=.76)}
    # Independent economic crosscheck: finite 30-year normalized owner cash annuity,
    # financial assets and debt settled explicitly at present. Maintenance/growth capital kept in FCF.
    # Unlevered cash: group EBIT92*.78 + D&A35 - sustaining capex46 =60.76;
    # parent's direct share 30.4%, subsidiary equity 72%; use exact own/sub decomposition.
    owner_fcff=(28*.75+5.6-46*.24)+.72*(64*.75+29.4-46*.76)
    bridge=INITIAL['parent_cash']+.72*INITIAL['sub_cash']-INITIAL['parent_debt']-.72*INITIAL['sub_debt']+65-INITIAL['mineral_payable']*(.15+.85*.72)
    # Extra first five-year capex and working capital relative steady state.
    early=sum(((57 if y<=3 else 52)-46+1)*(.24+.76*.72)/(1.08**y) for y in range(1,6))
    cross={str(r): (owner_fcff*sum((1+r)**(-y) for y in range(1,31))+bridge-early)/SHARES for r in [.085,.08,.075]}
    toy={'life':2,'shares':1,'subshare':.75,'initial':{'parent_cash':0,'sub_cash':0,'parent_debt':0,'sub_debt':0,'parent_legal_re':100},'annual':{'pni':4,'sni':8,'pfcf':4,'sfcf':8,'desired':100}}
    t=run(r=.10,upstream=.75,toy=toy)
    # year1 parent receives4+6*.75=8.5; sub keeps2; year2 receives8.5 + liquidation4*.75=3.
    assert abs(t['value']-(8.5/1.1+11.5/1.1**2))<1e-10
    # One-year owner fully funded terminal cash hand case through same function.
    assert len(base['distributions'])==5 and all(z>=0 for z in base['distributions'])
    return {'units':'CNY billion except per-share CNY; anniversary years from 2026-10-26','shares':SHARES,'initial':INITIAL,'cases':cases,
      'method2':{'owner_fcff':owner_fcff,'ordinary_net_asset_bridge':bridge,'early_capex_pv':early,'values':cross},
      'hand_case':{'engine_value':t['value'],'manual_value':8.5/1.1+11.5/1.1**2,'flows':t['distributions']},
      'value_range':{'low':round(low['value'],2),'high':round(high['value'],2)},
      'year5_terminal_range':{'low':round(cases['holder_low']['year5_terminal'],2),'high':round(cases['holder_high']['year5_terminal'],2)}}
if __name__=='__main__':
    o=build();Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:o[k] for k in ['value_range','year5_terminal_range','method2','hand_case']},indent=2))
