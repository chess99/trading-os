"""爱玛科技 2026-Q3. CNY million, shares million; no live price. Python stdlib only."""
import json,copy,pathlib
S=863.320284
I={'cash':9286.,'parent_cash':1800.,'debt':2970.,'parent_retained':1838.,'sub_retained':5000.,'collateral':5000.,'minimum_cash':2000.,'parent_minimum':400.,'sub_minimum':1600.,'previous_revenue':22500.,'operating_capital':7000.}
BASE={'revenue':[24000,26000,27500,28600,29700],'margin':[.055,.061,.065,.066,.066], 'capex':[2000,1500,1200,1100,1150], 'depreciation':[850,900,950,1000,1050], 'wc_ratio':.03,'collateral_ratio':.22,'gross_wc_ratio':.08,'supplier_finance_ratio':.27,'wc_extra':[300,0,0,0,0], 'parent_cost':300.,'upstream_ratio':.8,'arrival':1.,'payout':.5,'rate':.035,'yield':.015,'repay':[0,0,2200,0,970], 'extra_debt_cap':1500.,'terminal_margin':.066,'g':.015,'roic':.12,'r':.10}
def path(p,initial=I,shares=S):
 c=initial['cash'];pc=initial['parent_cash'];sc=c-pc;d=initial['debt'];pr=initial['parent_retained'];sr=initial['sub_retained'];ar=0.;drawn=0.;rev0=initial['previous_revenue'];capital=initial['operating_capital'];pledged=initial['collateral'];rows=[]
 for t in range(5):
  oldc=c;oldd=d;rev=p['revenue'][t];op=rev*p['margin'][t] # ordinary common NOPAT, includes yield on required collateral, excludes free financial pool
  cb=min(d,2000.) if t<3 and p['repay'][2]>=2200 else 0.;coupon=([30.,36.,0.,0.,0.][t] if cb else 0.)
  finance=c*p['yield']-(d-cb)*p['rate']-coupon; redemption_premium=200. if p['repay'][t]>=2200 else 0.
  ni=op+finance-redemption_premium;subprofit=ni+p['parent_cost']; parentown=-p['parent_cost']
  # Signed legal earnings remain signed; positive earnings retained; prudential 10% subsidiary reserve.
  sr+=subprofit-.1*max(subprofit,0);wc=(rev-rev0)*p['wc_ratio']+p['wc_extra'][t];pledge_add=(rev-rev0)*p['collateral_ratio'];pledged+=pledge_add
  gross_wc_add=(rev-rev0)*p['gross_wc_ratio'];supplier_finance_add=(rev-rev0)*p['supplier_finance_ratio']
  assert abs(wc-(pledge_add+gross_wc_add-supplier_finance_add+p['wc_extra'][t]))<1e-6
  capex=p['capex'][t];da=p['depreciation'][t];fcf=ni+da-capex-wc
  # Redemption premium is already NI/cash expense; principal excludes it.
  principal=max(0,p['repay'][t]-redemption_premium);principal=min(principal,d)
  sc+=fcf-parentown;pc+=parentown-principal;d-=principal
  capital+=capex-da+wc
  declared=min(max(sr,0),max(0,subprofit*p['upstream_ratio']),max(sc-initial['sub_minimum'],0))
  sr-=declared;ar+=declared;received=ar*p['arrival'];ar-=received;sc-=received;pc+=received
  pr+=parentown+declared # only declarations create legal investment profit, collections don't
  # Subsidiary receivable settlement is not presumed. Financing first supports required operations, never invented unlimited liquidity.
  need=max(initial['parent_minimum']-pc,0)+max(initial['sub_minimum']-sc,0)
  draw=min(need,max(p['extra_debt_cap']-drawn,0));drawn+=draw;d+=draw
  pdraw=min(draw,max(initial['parent_minimum']-pc,0));pc+=pdraw;sc+=draw-pdraw
  dividend=min(max(ni*p['payout'],0),max(pr,0),max(pc-initial['parent_minimum'],0),max(pc+sc-initial['minimum_cash'],0))
  pc-=dividend;pr-=dividend;c=pc+sc
  feasible=pc>=initial['parent_minimum']-1e-7 and sc>=initial['sub_minimum']-1e-7
  assert abs(c-(oldc+fcf-principal+draw-dividend))<1e-7
  assert abs(d-(oldd-principal+draw))<1e-7
  rows.append(dict(year=t+1,revenue=rev,operating_common_profit=op,finance=finance,net_income=ni,capex=capex,depreciation=da,working_capital_increase=wc,restricted_collateral=pledged,collateral_increase=pledge_add,gross_operating_wc_increase=gross_wc_add,incremental_supplier_finance=supplier_finance_add,fcf=fcf,declared=declared,received=received,upstream_receivable=ar,parent_legal_retained=pr,sub_legal_retained=sr,parent_cash=pc,sub_cash=sc,cash=c,debt=d,new_debt=draw,dividend=dividend,dps=dividend/shares,shares=shares,capital=capital,feasible=feasible))
  if not feasible:return {'feasible':False,'rows':rows,'failure_year':t+1,'reason':'zero dividends and finite financing still insufficient'}
  rev0=rev
 return {'feasible':True,'rows':rows}
def terminal(last,r,g,roic,margin):
 # Fifth-year balance sheet is held fixed. Only subsequent earning power/cost of capital changes.
 next_profit=last['revenue']*(1+g)*margin
 operating=next_profit*(1-g/roic)/(r-g)
 bridge=last['cash']-I['minimum_cash']-last['debt']
 return {'operating':operating,'bridge':bridge,'total':operating+bridge,'per_share':(operating+bridge)/last.get('shares',S)}
def value(run,r,g,roic,margin):
 if not run['feasible']:return None
 tv=terminal(run['rows'][-1],r,g,roic,margin)
 pvdiv=sum(x['dividend']/(1+r)**x['year'] for x in run['rows']);pvt=tv['total']/(1+r)**5
 return {'value_per_share':(pvdiv+pvt)/run['rows'][-1].get('shares',S),'pv_distributions':pvdiv,'pv_terminal':pvt,'terminal_contribution':pvt/(pvdiv+pvt),'terminal':tv}
def tests():
 z=copy.deepcopy(BASE);z.update(revenue=[100]*5,margin=[.1]*5,capex=[0]*5,depreciation=[0]*5,wc_ratio=0,collateral_ratio=0,gross_wc_ratio=0,supplier_finance_ratio=0,wc_extra=[0]*5,parent_cost=0,upstream_ratio=1,arrival=1,payout=1,rate=0,repay=[0]*5,extra_debt_cap=0)
 z['yield']=0;ii=dict(I,cash=100,parent_cash=50,debt=0,parent_retained=100,sub_retained=100,minimum_cash=0,parent_minimum=0,sub_minimum=0,previous_revenue=100)
 q=path(z,ii);assert q['feasible'];assert all(abs(x['dividend']-10)<1e-8 for x in q['rows']);assert abs(q['rows'][-1]['cash']-100)<1e-8
 # formal legal chain preserves losses and later earnings repair them before payout
 ii['parent_retained']=-25;q=path(z,ii);assert q['rows'][0]['parent_legal_retained']==-15 and q['rows'][1]['dividend']==0 and q['rows'][2]['dividend']==5
 z['margin']=[-20]*5;assert not path(z,ii)['feasible']
 # same formal terminal function, zero growth 10 operating profit /10% plus 100 surplus cash
 a={'revenue':100,'cash':2100,'debt':0};assert abs(terminal(a,.1,0,.12,.1)['total']-200)<1e-8
 return 'pass: formal path cash, signed legal losses, financing infeasibility, formal terminal hand case'
def main():
 base=path(BASE);out={'units':'CNY million except per share','shares':S,'initial':I,'base_inputs':BASE,'base':base,'tests':tests()}
 out['core_low']=value(base,.10,.015,.12,.066);out['core_high']=value(base,.095,.02,.15,.066)
 # Auxiliary: current normalized operating NOPAT times a justified reinvestment-adjusted PE + current excess net financial assets.
 out['method2']={'normalized_operating_common_profit':1600,'multiples':[11,14],'net_financial_bridge':I['cash']-I['minimum_cash']-I['debt'],'range':[(1600*m+I['cash']-I['minimum_cash']-I['debt'])/S for m in [11,14]]}
 scenarios={
 'cyclical':{'revenue':[21500,22500,25500,28000,29700],'margin':[.04,.045,.06,.065,.066],'wc_extra':[1000,300,-300,-300,0],'capex':[2000,1400,1200,1100,1150],'arrival':.75},
 'structural':{'revenue':[22000,21500,21000,21000,21000],'margin':[.035,.025,.025,.025,.025],'wc_extra':[2000,1000,0,0,0],'capex':[2000,1200,950,950,950],'arrival':.65,'terminal_margin':.025,'g':0,'roic':.08,'r':.11},
 'upside':{'revenue':[25000,28000,30500,32500,34000],'margin':[.06,.067,.07,.07,.07],'capex':[2200,1700,1500,1350,1350],'terminal_margin':.07,'g':.02,'roic':.15,'r':.095},
 'liquidity_extreme':{'revenue':[18000]*5,'margin':[-.02]*5,'wc_extra':[6500,1000,0,0,0],'arrival':.2,'extra_debt_cap':500}}
 out['scenarios']={}
 for k,ch in scenarios.items():
  p=copy.deepcopy(BASE);p.update(ch);run=path(p);out['scenarios'][k]={'effective':'year 1; consolidated operations and parent/sub distribution chain','changed':ch,'frozen':[x for x in BASE if x not in ch],'path':run,'valuation':value(run,p['r'],p['g'],p['roic'],p['terminal_margin'])}
 # Fully converted optimistic alternative, deliberately earliest conversion (maximum interest saving/dilution).
 p=copy.deepcopy(BASE);p.update(scenarios['upside']);p['repay']=[0,0,0,0,970]
 ii=dict(I,debt=970.);run=path(p,ii,S+1999.497/36.70)
 out['scenarios']['upside_full_conversion']={'effective':'all bonds convert before year 1; optimistic alternative only','changed':{'debt':970,'shares':S+1999.497/36.70,'repay':p['repay']},'frozen':'same upside business and legal rules','path':run,'valuation':value(run,.095,.02,.15,.07)}
 last=base['rows'][-1]
 upstream_available=min(max(last['sub_legal_retained'],0),max(last['sub_cash']-I['sub_minimum'],0))
 parent_spare=max(last['parent_cash']-I['parent_minimum'],0)
 release=min(upstream_available+parent_spare,max(last['parent_legal_retained']+upstream_available,0),max(last['cash']-I['minimum_cash']-last['debt'],0))
 out['terminal_release_capacity']={'sub_legal_retained':last['sub_legal_retained'],'sub_cash_after_minimum':last['sub_cash']-I['sub_minimum'],'available_upstream':upstream_available,'parent_cash_after_minimum':parent_spare,'parent_legal_after_declaration':last['parent_legal_retained']+upstream_available,'releasable_financial_principal':release,'required_financial_bridge':last['cash']-I['minimum_cash']-last['debt']}
 assert abs(release-out['core_low']['terminal']['bridge'])<1e-6
 out['financial_principal_delayed_release']={}
 for years in [3,5]:
  # Zero new operating income assigned to this diagnostic: only isolated surplus principal earns 1.5% after-tax yield until release.
  out['financial_principal_delayed_release'][str(years)]={}
  for side,r in [('low',.10),('high',.095)]:
   haircut=release*(1-(1.015/(1+r))**years)
   out['financial_principal_delayed_release'][str(years)][side]={'release_year_after_year5':years,'future_principal':release*1.015**years,'discounted_principal_at_year5':release*(1.015/(1+r))**years,'current_value_per_share':out['core_'+side]['value_per_share']-haircut/(1+r)**5/S,'terminal_per_share':out['core_'+side]['terminal']['per_share']-haircut/S}
 out['sensitivity']={}
 for label,ch in [('margin_minus_1pp',{'margin':[x-.01 for x in BASE['margin']],'terminal_margin':.056}),('upstream_arrival_50pct',{'arrival':.5}),('capex_plus_300',{'capex':[x+300 for x in BASE['capex']]}),('tax_25pct',{'margin':[x*.75/.8 for x in BASE['margin']],'terminal_margin':.066*.75/.8,'roic':.12*.75/.8})]:
  p=copy.deepcopy(BASE);p.update(ch);run=path(p);out['sensitivity'][label]={'changed':ch,'path':run,'value':value(run,.10,.015,p['roic'],p['terminal_margin'])}
 p=copy.deepcopy(BASE);p['arrival']=.5;ii=dict(I,parent_cash=800);run=path(p,ii);out['sensitivity']['parent_cash_and_receipt']={'initial_parent_cash':800,'arrival':.5,'path':run,'value':value(run,.10,.015,.12,.066)}
 ii=dict(I,cash=8786);run=path(BASE,ii);out['sensitivity']['additional_restricted_500']={'initial_cash':8786,'path':run,'value':value(run,.10,.015,.12,.066)}
 pathlib.Path(__file__).with_name('2026-Q3-output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
