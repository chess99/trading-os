"""Dong-E-E-Jiao: CNY billion except per-share, anniversary cash periods.
All forward inputs are research budgets, not company guidance. Standard library only.
Cash is common-owner attributable financial assets, after reserved obligations.
Minority cash capital removed initially; incremental minority profits removed annually.
Lease cost is cash rent in operating margins; hence no separate lease debt deduction.
"""
from pathlib import Path
import json, copy
SHARES=.639826824
CASH0=(3670798598.29+3611072057.36)/1e9-.020-.060541-.051-.09563224203
BASE=dict(revenues=[6.9,7.18,7.47,7.77,8.08,8.36,8.61,8.85,9.07,9.25],
 margins=[.295,.295,.297,.297,.297,.295,.293,.291,.289,.287],tax=.16,
 da=[.17,.19,.23,.25,.27,.28,.29,.30,.31,.32],
 maintenance=[.15,.17,.21,.24,.27,.28,.29,.30,.31,.32],
 project=[.60,.60,.17,0,0,0,0,0,0,0],
 other_growth=[.04,.04,.04,.04,.04,.04,.04,.04,.04,.04],
 nwc=[.12,.08,.07,.07,.07,.06,.06,.06,.06,.06],
 minority=[.003,.004,.005,.006,.007,.008,.009,.01,.011,.012],
 payout=.95,yield_net=.013,parent_share=.88,sub_payout=.8,
 parent_cash=CASH0-.4,sub_cash=.4,parent_re=8.0,sub_re=.35,
 parent_floor=.9,sub_floor=.1,internal_repayment=0.,g=.02,roic=.15)

def project(p):
    pc,sc,pr,sr=p['parent_cash'],p['sub_cash'],p['parent_re'],p['sub_re']
    rows=[]
    for i,rev in enumerate(p['revenues']):
        op=rev*p['margins'][i]*(1-p['tax'])-p['minority'][i]
        # Split owner-attributable profit/cash; subsidiaries are equity-weighted.
        pn,sn=op*p['parent_share'],op*(1-p['parent_share'])
        pi,si=pc*p['yield_net'],sc*p['yield_net']
        cap=p['maintenance'][i]+p['project'][i]+p['other_growth'][i]
        fcf=op+p['da'][i]-cap-p['nwc'][i]
        # Main park is legally funded by parent; other capital follows profit split.
        adj=p['da'][i]-p['maintenance'][i]-p['other_growth'][i]-p['nwc'][i]
        pfcf=pn+adj*p['parent_share']-p['project'][i]
        sfcf=sn+adj*(1-p['parent_share'])
        transfer=p['internal_repayment'] if i==0 else 0.
        sc_pre=sc+sfcf+si+transfer
        # Child legal reserve haircut 10%; dividend declared and paid same annual period.
        sub_profit=sn+si
        sub_legal=sr+sub_profit-.1*max(0,sub_profit)
        upstream=max(0,min(p['sub_payout']*(sn+si),sub_legal,sc_pre-p['sub_floor']))
        sr=sub_legal-upstream
        sc_new=sc_pre-upstream
        parent_profit=pn+pi+upstream
        parent_legal=pr+parent_profit # statutory reserve already >50% capital
        pc_pre=pc+pfcf+pi+upstream-transfer
        target=p['payout']*max(0,op+pi+si)
        dividend=max(0,min(target,parent_legal,pc_pre-p['parent_floor']))
        pc_new=pc_pre-dividend;pr=parent_legal-dividend
        assert min(pc_new-p['parent_floor'],sc_new-p['sub_floor'])>-1e-9
        assert abs(pc_new+sc_new-(pc+sc+fcf+pi+si-dividend))<1e-9
        rows.append(dict(year=i+1,revenue=rev,operating_profit_common=op,parent_own_profit=pn,
            subsidiary_profit=sn,financial_income=pi+si,parent_legal_profit=parent_profit,
            subsidiary_upstream=upstream,capex=cap,da=p['da'][i],nwc=p['nwc'][i],fcf=fcf,
            dividend=dividend,dps=dividend/SHARES,parent_cash=pc_new,subsidiary_cash=sc_new,
            cash=pc_new+sc_new,parent_retained=pr,subsidiary_retained=sr,
            bank_debt=0.,new_financing=0.,shares=SHARES,internal_repayment=transfer))
        pc,sc=pc_new,sc_new
    return rows

def operating_terminal(last,p,r):
    # Incremental investment funds steady growth; maintenance equals depreciation.
    next_profit=last['operating_profit_common']*(1+p['g'])
    return next_profit*(1-p['g']/p['roic'])/(r-p['g'])

def valuation(p,r,start=0,cash_release_delay=0):
    rows=project(p);n=len(rows)
    excess_cash=rows[-1]['cash']-p['parent_floor']-p['sub_floor']
    terminal=operating_terminal(rows[-1],p,r)+excess_cash*((1+p['yield_net'])/(1+r))**cash_release_delay
    pv_d=sum(x['dividend']/(1+r)**(x['year']-start) for x in rows[start:])
    pv_t=terminal/(1+r)**(n-start)
    return dict(value=(pv_d+pv_t)/SHARES,terminal_pv_fraction=pv_t/(pv_d+pv_t),
        terminal_equity=terminal,pv_dividends=pv_d,pv_terminal=pv_t,rows=rows)

def scenario(name):
    p=copy.deepcopy(BASE)
    if name=='cyclical':
        p.update(revenues=[6.2,6.3,6.8,7.3,7.75,8.1,8.4,8.65,8.85,9.02],
          margins=[.255,.26,.28,.29,.295,.293,.291,.289,.287,.285],
          nwc=[.4,.2,-.12,-.08,.07,.06,.06,.06,.06,.06],payout=.8)
    elif name=='structural':
        p.update(revenues=[6.2,5.9,5.65,5.5,5.4,5.3,5.2,5.1,5.,4.9],
          margins=[.24,.21,.19,.18,.18,.18,.18,.18,.18,.18],tax=.20,
          nwc=[.35,.25,.15,.1,.1,.08,.08,.08,.08,.08],payout=.65,g=0.,roic=.10)
    elif name=='optimistic':
        p.update(revenues=[7.1,7.6,8.15,8.7,9.25,9.7,10.1,10.5,10.85,11.17],
          margins=[.30,.305,.31,.31,.31,.308,.306,.304,.302,.30],
          nwc=[.14,.14,.14,.14,.14,.12,.12,.1,.1,.1],g=.025,roic=.18)
    elif name=='margin_minus_2pp':p['margins']=[x-.02 for x in p['margins']]
    elif name=='credit_delay':p['nwc'][0]+=.6;p['nwc'][2]-=.6
    elif name=='park_overrun':p['project']=[x*1.3 for x in p['project']]
    elif name=='internal_settlement':p['internal_repayment']=.6
    elif name=='no_upstream':p['sub_payout']=0.
    return p

def checks():
    # Actual projection + valuation functions: no growth, one period, all profit paid.
    p=copy.deepcopy(BASE)
    p.update(revenues=[1.],margins=[1.],tax=0.,da=[0.],maintenance=[0.],project=[0.],
      other_growth=[0.],nwc=[0.],minority=[0.],payout=1.,yield_net=0.,parent_share=1.,
      sub_payout=0.,parent_cash=0.,sub_cash=0.,parent_re=0.,sub_re=0.,
      parent_floor=0.,sub_floor=0.,g=0.,roic=.2)
    v=valuation(p,.1)
    assert abs(v['value']-10/SHARES)<1e-10 # (1 + 1/.1)/1.1
    assert v['rows'][0]['cash']==0
    # Forced parent cash constraint reduces dividends, never borrows for distribution.
    p['project']=[.75]
    v=valuation(p,.1)
    assert abs(v['rows'][0]['dividend']-.25)<1e-10
    # Losses must remain signed: .5 loss then .3 recovery leaves .2 deficit.
    p.update(revenues=[1.,1.,1.],margins=[-.5,.3,.3],da=[0.]*3,maintenance=[0.]*3,
      project=[0.]*3,other_growth=[0.]*3,nwc=[0.]*3,minority=[0.]*3,parent_cash=1.)
    a=project(p)
    assert [round(z['dividend'],8) for z in a]==[0.,0.,.1]
    assert [round(z['parent_retained'],8) for z in a]==[-.5,-.2,0.]
    # Same test for subsidiary: positive profits reserve 10%, losses counted in full.
    p.update(parent_share=0.,sub_cash=1.,parent_cash=0.,sub_payout=1.)
    b=project(p)
    assert [round(z['subsidiary_upstream'],8) for z in b]==[0.,0.,.04]
    assert [round(z['subsidiary_retained'],8) for z in b]==[-.5,-.23,0.]
    return {'actual_chain_hand_case':10/SHARES,'cash_constraint_dividend':.25,
      'parent_loss_recovery_dividends':[z['dividend'] for z in a],
      'subsidiary_loss_recovery_upstream':[z['subsidiary_upstream'] for z in b]}

def main():
    out={'units':'CNY billion, shares billion, per-share CNY','assumptions':BASE,'initial_common_cash':CASH0,
      'base_low':valuation(BASE,.095),'base_high':valuation(BASE,.085),
      'year5_low':valuation(BASE,.095,5),'year5_high':valuation(BASE,.085,5),
      'checks':checks(),'scenarios':{}}
    for name in ['cyclical','structural','optimistic','margin_minus_2pp','credit_delay','park_overrun','internal_settlement','no_upstream']:
        out['scenarios'][name]=valuation(scenario(name),.09)
    out['scenarios']['terminal_cash_delay_3']=valuation(BASE,.09,cash_release_delay=3)
    out['scenarios']['terminal_cash_delay_5']=valuation(BASE,.09,cash_release_delay=5)
    # Forward 3-year operating earnings multiple with the same equity cash bridge.
    rows=project(BASE)
    out['method2']={str(m):(sum(x['dividend']/1.09**x['year'] for x in rows[:3])+
      (rows[2]['operating_profit_common']*m+rows[2]['cash']-1)/1.09**3)/SHARES for m in [16,19]}
    out['sensitivity_metadata']={'effective':'year 1 (2026-10-26 onward), consolidated business and listed parent',
      'margin_minus_2pp':'all years operating margin -2pp; revenue, tax, capex, NWC, payout policy, discount fixed',
      'credit_delay':'additional .6 year1 NWC, returns year3; all operating inputs fixed; financing/dividends recomputed',
      'park_overrun':'parent park capex +30%, no additional sales; all other inputs fixed',
      'internal_settlement':'parent transfers .6 to subsidiaries year1, no group cash cost; profits unchanged',
      'no_upstream':'subsidiary dividend zero all years; legal reserves and liquidity recomputed',
      'terminal_cash_delay':'at year10 excess financial assets released 3/5 years later, earn 1.3% net meanwhile; operating value and years1-10 dividends frozen',
      'structural':'permanent demand decline, margin compression, credit costs and tax; committed park still paid; no automatic recovery',
      'cyclical':'two years weak sales/margin, working capital release year3-4; park commitments retained',
      'optimistic':'new products scale with higher margins and NWC, same park, higher mature ROIC'}
    Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
