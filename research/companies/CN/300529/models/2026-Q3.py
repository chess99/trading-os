#!/usr/bin/env python3
"""Jafron 2026Q3 rebuilt economic budget. Standard library only, deterministic full JSON stdout.
Amounts CNY 100m, shares 100m. Forecasts are researcher budgets, not statutory entity forecasts.
"""
import copy,json
FACTS={'shares':(798605275-24242694)/1e8,'cash':(854933359.03+1987056935.26)/1e8-.0791182347,'mother_cash':(511083558.05+1785827339.56)/1e8,'bank':.3739107533+1.7153780637+.20,'bond':999829200*1.1/1e8,'investment':1.3066241057,'retained':25.4579677382,'reserve':4.03855193,'registered':7.98605275}
BASE=dict(name='base',kha=[4,4.7,5.4,6.1,6.8],legacy=[14.5,15,15.5,16,16.5],other=[3.5,3.8,4.1,4.4,4.7],gm=[.76,.82,.52],sell=.20,admin=.07,rd=.10,other_cost=.02,tax=.16,r=.10,g=.02,tail_growth=.04,roic=.18,capex=[2.5,2.1,1.8,1.9,2],da=[1.45,1.5,1.55,1.6,1.65],nwc=.12,payout=.60,sub_loss=.05,yield_cash=.015,mother_cash_shift=0,investment_recovery=1,acquire=True,minority=.02)
def variant(name,**kwargs):
 c=copy.deepcopy(BASE);c.update(kwargs);c['name']=name;return c
CASES={'base':BASE,'core_low':variant('core_low',kha=[3.6,4,4.4,4.8,5.2],legacy=[13.7,13.8,14,14.2,14.4],other=[3.2,3.5,3.8,4,4.2],gm=[.74,.81,.50],sell=.21,tax=.17,r=.105,tail_growth=.025,roic=.16),'core_high':variant('core_high',kha=[4.4,5.3,6.2,7.1,8],legacy=[15,15.6,16.2,16.8,17.4],other=[3.6,4.1,4.6,5.1,5.6],gm=[.78,.83,.54],sell=.195,r=.095,tail_growth=.05,roic=.20,capex=[2.7,2.4,2.1,2.2,2.3]),'cyclical':variant('cyclical',kha=[3.2,3.8,4.8,5.8,6.8],legacy=[12.5,13,14.5,15.5,16.5],other=[3,3.3,3.8,4.3,4.7],sell=.215,nwc=.18,payout=.50),'structural':variant('structural',kha=[4,4.6,5.2,5.6,6],legacy=[11.5,10.5,10,9.5,9],other=[3.2,3.3,3.4,3.5,3.6],gm=[.65,.72,.46],sell=.24,tax=.20,r=.11,g=0,tail_growth=-.02,roic=.10,nwc=.18,payout=.40,sub_loss=.12,investment_recovery=.5),'optimistic':variant('optimistic',kha=[4.6,5.8,7,8.2,9.4],legacy=[15,16,17,18,19],other=[3.8,4.5,5.2,5.9,6.6],gm=[.79,.84,.56],sell=.19,r=.095,tail_growth=.06,g=.025,roic=.22,capex=[3,2.7,2.6,2.6,2.7])}
def legal(retained,reserve,registered,profit,wanted,cash):
 add=min(max(0,.5*registered-reserve),.1*max(0,profit+min(0,retained)))
 paid=min(max(0,wanted),max(0,retained+profit-add),max(0,cash))
 return retained+profit-add-paid,reserve+add,paid,add

def tail(c,n):
 pv=0;rows=[]
 for y in range(6,11):
  gr=c['tail_growth']+(c['g']-c['tail_growth'])*(y-6)/4
  prior=n;n*=1+gr;reinvest=max(0,n-prior)/c['roic'];fcf=n-reinvest
  rows.append(dict(year=y,nopat=n,reinvestment=reinvest,fcf=fcf));pv+=fcf/(1+c['r'])**(y-5)
 stable=n*(1+c['g']);stable_fcf=stable*(1-c['g']/c['roic']);perpetuity=stable_fcf/(c['r']-c['g'])/(1+c['r'])**5
 return pv+perpetuity,rows,perpetuity

def run(c,f=None):
 f=FACTS if f is None else f
 pc=f['mother_cash']+c['mother_cash_shift'];sc=f['cash']-pc;pl=f['retained'];pr=f['reserve'];sl=-1.;sr=.1;debt=f['bank'];prev_rev=21.6;capital=19.;rows=[];pvdiv=0
 for i in range(5):
  y=i+1;rev=sum(c[s][i] for s in ['kha','legacy','other']);gross=sum(c[s][i]*m for s,m in zip(['kha','legacy','other'],c['gm']));ebit=gross-rev*(c['sell']+c['admin']+c['rd']+c['other_cost']);n=ebit*(1-c['tax'])
  pn=n*(1+c['sub_loss']);sn=-n*c['sub_loss'];dep=c['da'][i];cx=c['capex'][i];wc=(rev-prev_rev)*c['nwc'];interest=debt*.035*(1-c['tax']);rep=min(debt,.45 if i==0 else .5);debt-=rep
  pi=pc*c['yield_cash'];si=sc*c['yield_cash'];bond=f['bond'] if i==0 else 0;acq=.17592 if i==0 and c['acquire'] else 0;mi=0 if c['acquire'] else c['minority']
  pb=pc+pn+pi+.9*(dep-cx-wc)-.15*(interest+rep)-bond-acq;sb=sc+sn+si+.1*(dep-cx-wc)-.85*(interest+rep)-mi
  injection=max(0,.5-sb)+(.0828 if i==0 and c['acquire'] else 0);pb-=injection;sb+=injection
  lp=pn+pi-.15*interest-(.30 if i==0 and f['bond'] else 0);sp=sn+si-.85*interest-mi
  wanted=max(0,(n+pi+si-interest-mi)*c['payout']);pl,pr,paid,add=legal(pl,pr,f['registered'],lp,wanted,pb-2)
  sl,sr,up,sa=legal(sl,sr,3.,sp,0,sb-.5);pc=pb-paid;sc=sb
  groupfcf=n+pi+si+dep-cx-wc-interest-rep-bond-acq-mi;opening=rows[-1]['group_cash'] if rows else f['cash']
  assert abs(pc+sc-opening-groupfcf+paid)<1e-9
  assert pc>=2-1e-10 and sc>=.5-1e-10 and up==0
  capital+=cx-dep+wc;pvdiv+=paid/(1+c['r'])**y;prev_rev=rev
  rows.append(dict(year=y,revenue=rev,gross_profit=gross,ebit=ebit,nopat=n,mother_nopat=pn,subsidiary_nopat=sn,depreciation=dep,capex=cx,working_capital_increase=wc,bank_interest=interest,bank_repayment=rep,bank_end=debt,bond_redemption=bond,financial_income=pi+si,acquisition=acq,minority_cash=mi,injection=injection,upstream=up,mother_legal_profit=lp,mother_retained=pl,mother_reserve=pr,reserve_addition=add,subsidiary_retained=sl,mother_cash=pc,subsidiary_cash=sc,group_cash=pc+sc,distribution=paid,distribution_per_share=paid/f['shares'],operating_capital=capital))
 op,tr,perp=tail(c,rows[-1]['nopat']);netcash=pc+sc-2.5-debt;invest=f['investment']*c['investment_recovery'];minority_tail=0 if c['acquire'] else c['minority']/c['r'];tv=op+netcash+invest-minority_tail;tvpv=tv/(1+c['r'])**5;value=(pvdiv+tvpv)/f['shares']
 apv=sum(z['distribution']/(1+c['r'])**z['year'] for z in rows[:2]);bridge=rows[1]['group_cash']-2.5-rows[1]['bank_end']+invest-minority_tail
 aux=[(apv+(rows[2]['nopat']*m+bridge)/(1+c['r'])**2)/f['shares'] for m in [14,18]]
 implicit=((value*f['shares']-apv)*(1+c['r'])**2-bridge)/rows[2]['nopat'] if rows[2]['nopat'] else None
 delta=rows[4]['operating_capital']-rows[0]['operating_capital'];increment=(rows[4]['nopat']-rows[0]['nopat'])/delta if delta else None
 return dict(inputs=c,years=rows,tail_years=tr,current_value=value,terminal_year5_per_share=tv/f['shares'],terminal_operation=op,terminal_net_cash=netcash,terminal_investment=invest,terminal_minority=minority_tail,terminal_pv_per_share=tvpv/f['shares'],terminal_total_pv_fraction=tvpv/(pvdiv+tvpv),perpetuity_y11_pv_fraction=perp/(1+c['r'])**5/(pvdiv+tvpv),auxiliary_value_range=aux,auxiliary_equity_bridge=dict(valuation_year=2,past_distribution_pv=apv,cash_after_distribution=rows[1]['group_cash'],bank_debt=rows[1]['bank_end'],buffer=2.5,investment=invest,minority=minority_tail,bridge=bridge,forward_nopat=rows[2]['nopat'],main_implied_forward_multiple=implicit),incremental_roic_y1_to_y5=increment)

def tests():
 a=legal(-2,0,10,5,99,99);assert max(abs(x-y) for x,y in zip(a,(0,.3,2.7,.3)))<1e-12
 assert legal(-7,0,10,5,99,99)==(-2,0,0,0)
 c=variant('hand',kha=[10]*5,legacy=[0]*5,other=[0]*5,gm=[1,0,0],sell=0,admin=0,rd=0,other_cost=0,tax=0,r=.1,g=0,tail_growth=0,capex=[0]*5,da=[0]*5,nwc=0,payout=.5,sub_loss=0,yield_cash=0,acquire=False,minority=0)
 f=dict(FACTS,shares=1,cash=25,mother_cash=20,bank=0,bond=0,investment=0,retained=100)
 h=run(c,f);hand=sum(5/1.1**t for t in range(1,6))+147.5/1.1**5;assert abs(h['current_value']-hand)<1e-9
 assert [x['group_cash'] for x in h['years']]==[30,35,40,45,50]
 ah=[5/1.1+5/1.1**2+(10*m+35-2.5)/1.1**2 for m in (14,18)];assert max(abs(a-b) for a,b in zip(h['auxiliary_value_range'],ah))<1e-9
 assert abs(tail(c,10)[0]-100)<1e-9
 m=run(dict(c,minority=.02),f);mh=sum(.01/1.1**t for t in range(1,6))+.25/1.1**5;assert abs(h['current_value']-m['current_value']-mh)<1e-9
 ma=.01/1.1+.01/1.1**2+.22/1.1**2;assert max(abs(a-b-ma) for a,b in zip(h['auxiliary_value_range'],m['auxiliary_value_range']))<1e-9
 return dict(loss_before_reserve=list(a),production_full_chain=hand,auxiliary_hand=ah,permanent_minority_difference=mh)

def main():
 diagnostics={'sell_plus_2pp':variant('sell_plus_2pp',sell=.22),'tail_roic_12pct':variant('tail_roic_12pct',roic=.12),'mother_cash_minus_5':variant('mother_cash_minus_5',mother_cash_shift=-5),'investment_zero':variant('investment_zero',investment_recovery=0),'capex_plus_1_y1_y5':variant('capex_plus_1_y1_y5',capex=[3.5,3.1,2.8,2.9,3]),'no_acquisition':variant('no_acquisition',acquire=False)}
 out=dict(units='CNY 100 million, shares 100 million, per share CNY',facts=FACTS,tests=tests(),cases={k:run(c) for k,c in CASES.items()},diagnostics={k:run(c) for k,c in diagnostics.items()})
 b=out['cases']['base'];ends=[(tail(CASES[k],b['years'][-1]['nopat'])[0]+b['terminal_net_cash']+b['terminal_investment'])/FACTS['shares'] for k in ['core_low','core_high']]
 out['core_range']={k:round(out['cases'][v]['current_value'],2) for k,v in [('low','core_low'),('high','core_high')]};out['holder_distributions']=[round(y['distribution_per_share'],4) for y in b['years']];out['holder_terminal_range']=dict(low=round(min(ends),2),high=round(max(ends),2))
 print(json.dumps(out,sort_keys=True,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
