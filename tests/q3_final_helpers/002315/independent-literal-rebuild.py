"""Fresh scalar budget algorithm. Does not import or read production model/outputs
until all paths below calculated. Units million CNY. S is not legal person."""
from pathlib import Path
import json,base64,gzip,hashlib
D=Path(__file__).parent

def calc(r,g,up=True,hurdle=-650,factor=.65,continued=False,shift=0,lag=False,lshare=.9987,recovery=True,recoverydelay=0,friction=.10,basisratio=1,taxbasisratio=1,parentreturn=True,premium=1000.,parentstart=12,parentfee=.02,loanexit=None,opening=27.64133653,scenario="base",horizon=80):
 # Independently transcribed literal forecast budgets; no production imports.
 budgets={
 "base":([1990,2150,2320,2490,2640],[105,130,155,178,200],[230,235,240,245,250],[.313,.319,.324,.328,.330],[.68,.68,.68,.67,.66],[-25,-18,-10,-5,0],.15,.018,.06,True),
 "cyclical":([1800,1810,1950,2130,2300],[90,100,115,135,155],[210,210,220,230,240],[.275,.270,.295,.310,.320],[.64,.62,.64,.65,.65],[-40,-35,-20,-10,-5],.17,.018,.05,False),
 "structural":([1750,1550,1400,1280,1200],[80,65,55,50,45],[200,180,165,150,140],[.23,.18,.14,.12,.10],[.58,.50,.44,.40,.38],[-50,-45,-35,-25,-15],.20,.022,-.02,False),
 "optimistic":([2070,2340,2630,2920,3210],[120,165,220,285,350],[240,255,270,285,300],[.32,.335,.345,.355,.36],[.70,.71,.71,.70,.69],[-20,-10,0,8,15],.15,.021,.07,True)}
 micseq,aiseq,otherseq,marginseq,floatseq,subsseq,taxrate,caprate,fadegrowth,exercise=budgets[scenario]
 pc,sc,lc=500.,4.782733,0.;pd,sd,ld=2100.,160.867732,220.;pe,se=620.,184.88038429;associate=49.17621371;carveoutbasis=(160.867732+184.88038429+4.782733-20)*factor*basisratio;caprecv=0.;recovered=False
 pa=sa=la=0.;pu,pr=1300.,186.36459629;su=hurdle;lu=lr=0.;debt=1.5
 n=413.375586;reg=n;pending=0.;cumdiv=0.;recv=0.;oldwc=-1488.547204+opening
 rows=[];pay=[];holderfactor=1.;loanclosed=False
 for y in range(1,horizon+1):
  if y<=5:
   mic=micseq[y-1];ai=aiseq[y-1];other=otherseq[y-1]
   mar=marginseq[y-1]+shift;cl=floatseq[y-1];so=subsseq[y-1]
  else:
   grow=g+(fadegrowth-g)*max(0,(10-y)/5);mic*=1+grow;ai*=1+grow;other*=1+grow;so=(subsseq[-1] if scenario=="structural" else max(subsseq[-1],4))*(1+g)**(y-5)
  rev=mic+ai;issue=(10.329613 if y==1 else 8.156226 if y==2 else 0.) if exercise else 0.
  injected=issue*max(0,20.84-cumdiv);premium+=max(injected-issue,0);n+=issue;reg+=pending if lag else issue;pending=issue if lag else 0
  pm=min(pd,600 if y==1 else 500 if y in [2,3,4] else 0);sm=sd if y==1 else 0;lm=ld if y==1 else 0
  pi=.018*(pc+pd)+.025*pe;si=.015*(sc+sd);li=.018*(lc+ld)
  pa+=pd*.018;sa+=sd*.015;la+=ld*.018
  pp=pa*pm/pd if pd else 0;sp=sa*sm/sd if sd else 0;lp=la*lm/ld if ld else 0
  pa-=pp;sa-=sp;la-=lp;pic=pc*.018+pe*.025+pp;sic=sc*.015+sp;lic=lc*.018+lp
  psale=pe*.9 if y==8 else 0;pbook=pe if y==8 else 0;ssale=se*.65 if y==10 else 0;sbook=se if y==10 else 0
  asale=.65*associate if y==10 else 0;abook=associate if asale else 0;psale+=asale;pbook+=abook
  stax=max(so+si,0)*.2;spft=so+si-stax+ssale-sbook
  savail=sc+so+sic-stax+sm+ssale;fund=max(0,-so,20-savail)
  assert fund<=60;sc=savail+fund;su+=spft
  capitalnet=capitalprofit=0.
  if recovery and not recovered and y>=10+recoverydelay:
   gross=max(sc-20,0);proceeds=gross*factor*(1-friction);ctax=max(proceeds-carveoutbasis*taxbasisratio,0)*.25
   capitalnet=proceeds-ctax;capitalprofit=capitalnet-carveoutbasis;sc-=gross;recovered=True
  sdv=max(sc-20,0) if up and recovered else 0;sc-=sdv;su-=sdv
  lpft=li*.75;ltake=.1*max(lpft+min(lu,0),0)
  if not continued:ltake=min(ltake,max(100-lr,0))
  lu+=lpft-ltake;lr+=ltake;lc+=lic-li*.25+lm
  lbuffer=0 if loanclosed else 220
  ldv=max(0,min(lpft*.8 if y<10 else max(lc-lbuffer,0),lu,lc-lbuffer));lu-=ldv;lc-=ldv
  if loanexit==y:
   proceeds=lc*lshare*.9;xtax=max(proceeds-205.15818722,0)*.25
   capitalnet+=proceeds-xtax;capitalprofit+=proceeds-xtax-205.15818722;lc=lu=lr=0.;loanclosed=True
  newdiv=ldv*lshare+sdv*factor
  ebit=rev*mar;ic=debt*.05;tax=max(ebit+pi-ic,0)*taxrate+max(psale-pbook,0)*.25
  puopen,propen=pu,pr
  pprofit=ebit+pi-ic-tax+psale-pbook+newdiv+capitalprofit-min(fund,max(-so,0))
  rtake=.1*max(pprofit+min(pu,0),0)
  if not continued:rtake=min(rtake,max(reg*.5-pr,0))
  pu+=pprofit-rtake;pr+=rtake
  wc=(-cl+.045)*rev;buffer=(.30*cl+.12)*rev
  pc+=ebit+pic-ic-tax+.017*rev-caprate*rev-wc+oldwc+pm+psale+recv+caprecv+injected-fund
  borrowed=min(max(0,buffer-pc),max(0,100-debt));pc+=borrowed
  assert pc>=buffer-1e-7
  repay=min(max(0,pc-buffer),debt+borrowed);pc-=repay;debt+=borrowed-repay
  ordinary=.8*max(0,ebit*(1-taxrate)+pi*(1-taxrate)+so+newdiv);extra=.2*rev if y>=6 else 0
  dv=max(0,min(ordinary+extra,pu,pc-buffer));pc-=dv;pu-=dv
  n_before=n;factor_before=holderfactor;cp=0.
  if parentreturn and y>=parentstart and (y-parentstart)%5==0:
   pool=reg+premium;guard=max(buffer,max(-wc,0));cp=min(max(pc-guard,0)/(1+parentfee),pool*max(0,1-100/reg))
   if cp>1e-8:
    assert debt==0
    fee=cp*parentfee;correctedprofit=pprofit-fee;newtake=.1*max(correctedprofit+min(puopen,0),0)
    if not continued:newtake=min(newtake,max(reg*.5-propen,0))
    pu=puopen+correctedprofit-newtake;pr=propen+newtake;pc+=dv-fee
    dv=max(0,min(ordinary+extra,pu,pc-buffer));pc-=dv;pu-=dv
    f=cp/pool;pc-=cp;reg*=1-f;n*=1-f;holderfactor*=1-f;premium*=1-f
  d=(dv+cp)/n_before*factor_before;cumdiv+=d;pay.append(d);recv=newdiv;caprecv=capitalnet;oldwc=wc
  pd-=pm;sd-=sm;ld-=lm
  if y==8:pe=0
  if y==10:se=0;associate=0
  rows.append({'year':y,'P_cash':pc,'S_cash':sc,'L_cash':lc,'P_capacity':pu,'S_capacity':su,'L_capacity':lu,'P_reserve':pr,'L_reserve':lr,'P_distribution':dv,'S_distribution':sdv,'L_distribution':ldv,'dps':d,'shares':n,'registered_budget':reg,'pending':pending})
 pv=sum(v/(1+r)**(i+1) for i,v in enumerate(pay))+pay[-1]*(1+g)/(r-g)/(1+r)**horizon
 tv=sum(pay[i-1]/(1+r)**(i-5) for i in range(6,horizon+1))+pay[-1]*(1+g)/(r-g)/(1+r)**(horizon-5)
 return {'PV':pv,'TV5':tv,'D':pay[:5],'annual':rows}
results={'opening_frozen':calc(.1,.025,opening=.045*2134.324686),'opening_overlap':calc(.1,.025,opening=27.64133653+55-43.79557263),'opening_no_receivables':calc(.1,.025,opening=27.64133653-(14.85441390-.35618504)),'low':calc(.105,.02),'high':calc(.095,.03),'middle':calc(.1,.025,up=False),'S_up':calc(.1,.025,up=True),'S_zero_hurdle':calc(.1,.025,up=True,hurdle=0),'S_100':calc(.1,.025,up=True,hurdle=0,factor=1),'continued':calc(.1,.025,continued=True),'margin':calc(.1,.025,shift=-.01),'register_lag':calc(.1,.025,lag=True),'L_direct':calc(.1,.025,lshare=.975),'no_recovery':calc(.1,.025,recovery=False),'delay5':calc(.1,.025,recoverydelay=5),'fee25':calc(.1,.025,friction=.25),'full_cost':calc(.1,.025,basisratio=974.76695646/214.8450520385),'basis2':calc(.1,.025,basisratio=2),'zero_taxbasis':calc(.1,.025,taxbasisratio=0),'parent_no':calc(.1,.025,parentreturn=False),'parent_premium0':calc(.1,.025,premium=0),'parent_delay20':calc(.1,.025,parentstart=20),'parent_fee10':calc(.1,.025,parentfee=.1),'loan20':calc(.1,.025,loanexit=20),'loan40':calc(.1,.025,loanexit=40),'loan_direct20':calc(.1,.025,loanexit=20,lshare=.975)}
# Complete independent paths are evaluated before reading or importing production.
endpoints={"base":[(.105,.02),(.095,.03)],"cyclical":[(.115,.015),(.105,.025)],"structural":[(.13,0.),(.115,0.)],"optimistic":[(.10,.025),(.09,.035)]}
major_results={}
for name, pairs in endpoints.items():
 for idx,(r,g) in enumerate(pairs):
  for horizon in (80,120,160):
   major_results[f"{name}@{idx}:{horizon}"]=calc(r,g,scenario=name,horizon=horizon)
def decode(x):
 if isinstance(x,dict) and x.get('encoding')=='gzip-mtime0-base64-json-utf8':
  raw=gzip.decompress(base64.b64decode(x['data']));assert hashlib.sha256(raw).hexdigest()==x['sha256'];return json.loads(raw)
 if isinstance(x,dict):return {k:decode(v) for k,v in x.items()}
 if isinstance(x,list):return [decode(v) for v in x]
 return x
# Only after independent computations may formal output be read.
o=decode(json.loads((D/'2026-Q3-output.json').read_text()));mapping={'opening_frozen':'opening_frozen_normalized','opening_overlap':'opening_all_legacy_overlap_credit','opening_no_receivables':'opening_ex_other_receivables','S_up':'S_upstream_after_legal_recovery','S_zero_hurdle':'S_loss_zero','S_100':'S_realizability_100','continued':'continue_reserves','margin':'margin_minus_1pt','register_lag':'parent_registration_delay1','L_direct':'L_direct_only975','middle':'no_S_upstream','no_recovery':'no_asset_recovery','delay5':'asset_recovery_delay5','fee25':'recovery_friction25','full_cost':'recovery_full_disclosed_cost','basis2':'recovery_book_cost_2x','zero_taxbasis':'recovery_zero_tax_basis','parent_no':'parent_no_capital_return','parent_premium0':'parent_premium_zero','parent_delay20':'parent_return_start20','parent_fee10':'parent_return_fee10','loan20':'loan_exit20','loan40':'loan_exit40','loan_direct20':'loan_exit20_direct_only'}
def compare(a,b):
 pv=b['current'] if 'current' in b else b['value'];tv=b['year5'] if 'year5' in b else b['TV5'];d={'PV':a['PV']-pv,'TV5':a['TV5']-tv,'maximum_state_error':0}
 assert abs(a['PV']-pv)<1e-8 and abs(a['TV5']-tv)<1e-8
 assert len(a['annual'])==len(b['annual_trace'])
 for x,y in zip(a['annual'],b['annual_trace']):
  for label,ent,field in [('P_cash','P','cash'),('S_cash','S','cash'),('L_cash','L','cash'),('P_capacity','P','capacity_budget'),('S_capacity','S','capacity_budget'),('L_capacity','L','capacity_budget'),('P_reserve','P','reserve_budget'),('L_reserve','L','reserve_budget'),('P_distribution','P','distribution'),('S_distribution','S','distribution'),('L_distribution','L','distribution')]:
   error=abs(x[label]-y[ent][field]);d['maximum_state_error']=max(d['maximum_state_error'],error);assert error<1e-7,(x['year'],label,x[label],y[ent][field])
  assert abs(x['registered_budget']-y['states']['P']['registered_capital_budget'])<1e-7
  assert abs(x['shares']-y['shares'])<1e-7
  assert abs(x['dps']-y['dps'])<1e-8
 return d
diffs={}
for k,a in results.items():
 b=o['scenarios']['base'][0 if k=='low' else 1] if k in ['low','high'] else o['sensitivity'][mapping[k]]
 diffs[k]=compare(a,b)
# Import only now, after every independent 80/120/160-year calculation. Production
# functions provide comparator paths only, never independent parameters or states.
import importlib.util
spec=importlib.util.spec_from_file_location('comparison_only_model',D/'2026-Q3.py');production=importlib.util.module_from_spec(spec);spec.loader.exec_module(production)
major_diffs={}
for name,pairs in endpoints.items():
 for idx,(r,g) in enumerate(pairs):
  for horizon in (80,120,160):
   key=f"{name}@{idx}:{horizon}";a=major_results[key]
   if horizon==80:b=o['scenarios'][name][idx]
   else:
    rows=production.run(name,stable=g,max_year=horizon)
    b={'value':production.pv(rows,r,g)['value'],'TV5':production.pv(rows,r,g,5)['value'],'annual_trace':rows}
   major_diffs[key]=compare(a,b)
results['major_scenario_horizon_paths']=major_results
results['comparisons']=diffs;results['major_comparisons']=major_diffs;results['pass']=True
(D/'independent-literal-output.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'existing_comparisons':diffs,'major_comparisons':major_diffs},indent=2))
