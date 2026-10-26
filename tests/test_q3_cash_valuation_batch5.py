"""第五批独立现金复算；不调用正式模型函数。"""
import json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN"

def amoy_recalc(r,g,end,ic,shift=0):
 c=[1038.798788,100.,120.];d=[150.242611,5.,5.];legal=[1189.407493,0.,0.];reserve=[195.0525845,0.,0.];caps=[195.0525845,20,10];loan=[8.327219/2]*2;rev=[870.,350.];wc=610;divs=[]
 for t in range(5):
  rev=[rev[0]*1.06,rev[1]*1.09];sales=sum(rev);op=(rev[0]*(.35+shift)+rev[1]*(.25+shift))*.85;fc=op-sales*.02-(sales/2-wc);wc=sales/2
  interest=[x*.03 for x in loan];ni=[]
  for i in range(3):
   fin=c[i]*.0153;debtint=d[i]*.0255;earn=op*[.92,.04,.04][i]+fin-debtint+(sum(interest) if i==0 else -interest[i-1]);ni.append(earn)
   old=legal[i];legal[i]+=earn;prov=min(max(legal[i]-max(old,0),0)*.1,max(caps[i]-reserve[i],0));legal[i]-=prov;reserve[i]+=prov
   c[i]+=fc*[.90,.05,.05][i]+fin-debtint
   principal=[150.242611,5,5][i]*[.1,.45,.45,0,0][t];c[i]-=principal;d[i]-=principal
  for i in (1,2):
   c[i]-=interest[i-1];c[0]+=interest[i-1];rep=min(max(c[i]-30,0),loan[i-1]);c[i]-=rep;c[0]+=rep;loan[i-1]-=rep
  pay=min(sum(ni)/2,legal[0],c[0]-180);c[0]-=pay;legal[0]-=pay;divs.append(pay)
  assert min(c)>=0
 current_op=op;startmargin=op/.85/sales;tail=[];ev=0
 for k in range(1,11):
  prev=sales;sales*=1+.065+(g-.065)*k/10;m=startmargin+(end-startmargin)*k/10;np=sales*m*.85;fc=np-(sales-prev)*ic;tail.append((np,fc));ev+=fc/(1+r)**k
 ev+=(np*(1+g)-sales*(1+g)*g*ic)/(r-g)/(1+r)**10
 c=[c[i]-[180,30,30][i] for i in range(3)];c[0]+=53
 for i in (1,2):
  repay=min(c[i],loan[i-1]);c[i]-=repay;c[0]+=repay;loan[i-1]-=repay;up=min(c[i],max(legal[i],0));c[i]-=up;c[0]+=up;legal[i]-=up;legal[0]+=up
 pay=min(c[0],legal[0]);c[0]-=pay;legal[0]-=pay;financial=pay
 for y in range(1,1001):
  if sum(c)<1e-8 and sum(loan)<1e-8:break
  before=sum(c);np,flow=tail[min(y-1,9)];scale=(1+g)**max(y-10,0);np*=scale;flow*=scale;fin=[x*.0153 for x in c];intr=[x*.03 for x in loan]
  for i in range(3):
   earn=np*[.92,.04,.04][i]+fin[i]+(sum(intr) if i==0 else -intr[i-1]);old=legal[i];legal[i]+=earn;provision=min(max(legal[i]-max(old,0),0)*.1,max(caps[i]-reserve[i],0));reserve[i]+=provision;legal[i]-=provision;c[i]+=flow*[.92,.04,.04][i]+fin[i]
  for i in (1,2):
   c[i]-=intr[i-1];c[0]+=intr[i-1];repay=min(max(c[i]-flow*.04,0),loan[i-1]);c[i]-=repay;c[0]+=repay;loan[i-1]-=repay
   assert min(c[i],legal[i])+1e-8>=flow*.04
   c[i]-=flow*.04;c[0]+=flow*.04;legal[i]-=flow*.04;legal[0]+=flow*.04
  assert min(c[0],legal[0])+1e-8>=flow
  c[0]-=flow;legal[0]-=flow;special=0
  if y>=3:
   for i in (1,2):
    up=min(c[i],max(legal[i],0));c[i]-=up;c[0]+=up;legal[i]-=up;legal[0]+=up
   special=min(c[0],max(legal[0],0));c[0]-=special;legal[0]-=special
  assert abs(sum(c)-before-sum(fin)+special)<1e-6 and min(c)>=-1e-8
  financial+=special/(1+r)**y
 assert sum(c)<1e-7
 return (sum(v/(1+r)**i for i,v in enumerate(divs,1))+(ev+financial)/(1+r)**5)/380.985869

@pytest.mark.parametrize("rate,g,end,ic,shift",[(.095,.02,.29,.85,0),(.085,.025,.31,.75,0),(.09,.025,.28,.8,-.02)])
def test_amoy_independent_cash_legal_and_permanent_margin(rate,g,end,ic,shift):
 out=json.loads((ROOT/"300685/models/2026-Q3-output.json").read_text())['scenarios']
 expected=out['margin_minus2pp']['valuation']['per_share'] if shift else out['base']['low' if rate==.095 else 'high']['per_share']
 assert amoy_recalc(rate,g,end,ic,shift)==pytest.approx(expected,abs=1e-8)


def huaneng_recalc(side,out):
 S=18.631094257
 low=side=='low';r=.06 if low else .05;cost=1.03 if low else .97;solar=1.2 if low else .92
 # engineering before future financing, historical CIP/interest, capacity, generation, tariff, first year, technology
 raw=[(49.06,8.28299014527,.39785046984,2.6,11.281,.40 if low else .45,2033,'hydro'),(50.40133460819*.85,4.42357346965,.07648238126,2.2,8.8 if low else 10.2,.28 if low else .32,2033,'hydro'),(23.4922659*.85,3.44129553187,.11422327861,1.5,6.149,.31 if low else .35,2032,'hydro'),(31.7*.85,2.27377883062,.12294163552,2.1,9.036,.31 if low else .35,2033,'hydro'),(15.85*.85,.44507355036,0,.72,3.096,.31 if low else .35,2036,'hydro'),(4.95*.85,.82378837876,0,.195,1.162,.25 if low else .27,2031,'hydro'),(8.75,6.25152322764,0,2.5,3.5,.27 if low else .31,2028,'solar')]
 def project(a,q3=True):
  eng,cip,oldi,gw,gen,price,first,kind=a;eng*=cost*(solar if kind=='solar' else 1);paid=cip-oldi+(2.4*cip/28.59711873621 if q3 else 0);remaining=eng-paid;v=0
  life=45 if kind=='hydro' else 25;deplife=45 if kind=='hydro' else 20
  for y in range(2027,first+life):
   if y<first:flow=-remaining/(first-2027)
   else:
    age=y-first;ramp=.5 if not age else 1;revenue=gen*price*.992/1.13*ramp*({'solar':.995,'wind':.997}.get(kind,1)**age)
    op=gw*{'hydro':.20,'solar':.05,'wind':.08}[kind]*ramp;maint=gw*{'hydro':.12,'solar':.035,'wind':.05}[kind]*ramp;da=(eng+oldi)/deplife if age<deplife else 0
    flow=revenue-op-maint-max(revenue-op-da,0)*.25
   v+=flow/(1+r)**(y-2026)
  return v
 new=sum(project(a) for a in raw);mature=0
 for age in range(1,51 if low else 61):
  inf=1.005**(age-1);foreign=min(1,max(0,(25-age)/10));rev=(25.6+1.6*foreign)*inf;da=7.5*inf;f=(rev-6.2*inf-da)*(.85 if age<=4 else .75)+da-(4.5 if low else 3.5)*inf-(8*inf if age in(20,40) else 0);mature+=f/(1+r)**age
 acq=0
 for age in range(45):
  factor=.7+(.3*.995**age if age<25 else 0);inf=1.005**age
  acq+=((1.15-.28-.14)*factor*inf-(1.15-.28-.4)*factor*inf*(.15 if age<4 else .25))/(1+r)**(age+1)
 acq+=sum(project(a,False) for a in [(18.617*.85,3.91921463674,.11426267834,.6,2.7,.35,2028,'hydro'),(.81*.95,.01261966514,0,.1,.26,.34,2028,'wind'),(.5331218*.95,.33226816921,.00358063057,.13,.338,.34,2028,'wind')])
 acq-=sum([.44109644445,.69873486464,6.8483,.10548456367])-.04648791615+.1+sum([.17722204944,.04125958114,.00036734884])+8.7012044/(1+r)
 # Minority schedule separately discounted: no assumption 11% enterprise value equals equity claim.
 gx=out['scenarios']['core_'+side]['projects']['GX']['rows'];minor=.11*(sum((z['dividend']-z['equity_call'])/(1+r+.02)**(z['year']-2026) for z in gx)+(gx[-1]['cash']-gx[-1]['debt'])/(1+r+.02)**(gx[-1]['year']-2026))
 equity=mature+new+acq+sum(2.7*.22*.75/(1+r)**(y-2026) for y in range(2035,2078))-sum((2/3)/(1+r)**i for i in(1,2,3))-minor
 equity+=-126.50412978373-16.217-.8*(1-1.075**-30)/.075-7.68024741949+3.72253673088-2.0296755+5.41473511562
 return equity/S

@pytest.mark.parametrize("side",['low','high'])
def test_huaneng_full_project_and_acquisition_cash(side):
 out=json.loads((ROOT/"600025/models/2026-Q3-output.json").read_text())
 assert huaneng_recalc(side,out)==pytest.approx(out['complete_valuation']['core_'+side]['per_share'],abs=1e-8)

def test_huaneng_permanent_tariff_and_fixed_year5_state():
 out=json.loads((ROOT/"600025/models/2026-Q3-output.json").read_text())
 expected=sum(-25.6*.05*1.005**(i-1)*(.85 if i<=4 else .75)/1.055**i for i in range(1,51))/18.631094257
 assert expected==pytest.approx(out['sensitivity']['mature_domestic_tariff_minus5pct_per_share'],abs=1e-8)
 base=out['holder_diagnostic'][-1]
 for result in out['terminal_year5'].values():assert result['debt']==pytest.approx(base['group_debt'])
 for case,rows in out['construction_funding_cases'].items():
  assert len(rows)==15 and rows[-1]['year']==2041
  for row in rows:
   assert min(row['parent_cash'],row['mature_sub_cash'],row['project_cash'],row['target_cash'],row['parent_retained'],row['mature_sub_retained'])>=0
   assert row['parent_new_general_debt']<= (9 if case=='cyclical' else 7)+1e-8


def livzon_recalc(r,g,roic):
 own=[1,1,.51,.906443,.47425,.6787,.6752];cash=[3.8,1.1,.45,.75,.2,(7.14989826687-.65273064722)-3.8-2.5,0];debt=[0,2.6,0,.6,0,.18441458806,0];d0=debt[:]
 legal=[6.73840844216,0,.2,0,.2,.1,-3];res=[0]*7;caps=[0,1,.04366445,.11994385,.1,.5,.65];weights=[.03,.45,.12,.27,.04,.09,0];buffers=[.6,.35,.12,.25,.08,.1,0];loan=2;portfolio=3.1;divs=[]
 profits=[[-.06,-.06,-.055,-.05,-.05],[1.05,1.10,1.16,1.22,1.28],[.60,.61,.625,.64,.66],[.52,.55,.575,.60,.63],[.09,.095,.10,.11,.12],[.04,.05,.06,.07,.08],[-.18,-.16,-.13,-.10,-.07]]
 for y in range(1,41):
  buff=[b*(1+g)**max(0,y-5) for b in buffers]
  op=[a[y-1] if y<=5 else a[-1]*(1+g)**(y-5) for a in profits]
  if y>5:op[-1]=-.05 if y==6 else -.025 if y==7 else 0
  invest=[.31,.33,.35,.38,.4][y-1] if y<=5 else sum(o*max(p,0) for o,p in zip(own,op))*g/roic/max(.8,sum(o*w for o,w in zip(own,weights)))
  earnings=[op[i]+cash[i]*.01 for i in range(7)]
  for i in range(7):cash[i]+=earnings[i]-invest*weights[i]
  intr=loan*.02;cash[0]-=intr;cash[1]+=intr;earnings[0]-=intr;earnings[1]+=intr
  for i in range(7):
   interest=debt[i]*.03;cash[i]-=interest;earnings[i]-=interest;rep=min(debt[i],d0[i]/8,max(0,cash[i]-buff[i]));cash[i]-=rep;debt[i]-=rep
  income=portfolio*.02;cash[0]+=income;earnings[0]+=income;realize={8:.65,9:.65,10:.65,11:.575,12:.575}.get(y,0);portfolio-=realize;cash[0]+=realize
  cash[0]-=([.20,.15,.10,0,0][y-1] if y<=5 else 0)+(.1066958 if y==1 else 0)
  inject=max(.48 if y==1 else 0,-cash[-1],0);cash[0]-=inject;cash[-1]+=inject
  for i in range(7):
   alloc=min(max(0,min(earnings[i],legal[i]+earnings[i]))*.1,max(0,caps[i]-res[i])) if i else 0
   legal[i]+=earnings[i]-alloc;res[i]+=alloc
  for i in range(1,7):
   target=max(earnings[i],0)*.8 if y<=5 else max(cash[i]-buff[i],0);planned=min(target,max(legal[i],0));offset=min(.2,loan,planned) if i==1 and y<=5 else 0;paid=min(max(planned-offset,0),max(cash[i]-buff[i],0))
   cash[i]-=paid;cash[0]+=paid*own[i];legal[i]-=paid+offset;legal[0]+=(paid+offset)*own[i];loan-=offset
  target=.887907171*[2.1,1.5,1.6,1.7,1.8][y-1] if y<=5 else max(cash[0]-buff[0],0)
  dividend=min(target,max(legal[0],0),max(cash[0]-buff[0],0));cash[0]-=dividend;legal[0]-=dividend;divs.append(dividend);assert min(cash)>=-1e-9
 assert sum(debt)<1e-8 and all(abs(cash[i]-buff[i])<1e-8 for i in range(7))
 assert abs(divs[-1]/divs[-2]-1-g)<1e-8
 return (sum(d/(1+r)**y for y,d in enumerate(divs,1))+divs[-1]*(1+g)/(r-g)/(1+r)**40)/.887907171

@pytest.mark.parametrize("rate,g,roic,key",[(.102,.015,.12,'core_low'),(.092,.02,.15,'core_high'),(.1075,.0175,.135,'r_plus1pct')])
def test_livzon_independent_40year_entity_cash(rate,g,roic,key):
 out=json.loads((ROOT/"000513/models/2026-Q3-output.json").read_text())
 assert livzon_recalc(rate,g,roic)==pytest.approx(out[key]['value_per_share'],abs=1e-8)
