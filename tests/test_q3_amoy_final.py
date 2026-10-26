"""Independent literal reconstruction; never imports the production model or reads its inputs.
Production output is opened only after all paths and years are independently computed.
"""
import json,gzip,copy,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"research/companies/CN/300685/models"
DEFAULT={'growth':[.06,.09],'margin':[.35,.25],'wc':.5,'capex':.045,'tax':.15,
 'cash':[1038.798788,100.,120.],'maturity':1,'special':99,'upstream':99,'delay':3,
 'friction':[0.,.02,.10],'terminal_g':.025,'terminal_margin':.30,'terminal_ic':.8,'terminal_g0':.065,
 'voluntary':0.,'extra':[0.]*5,'redemption':[0.]*5,'payout':.5,'term':[764.908373,0.,0.]}
VARIANTS={'base':{},
 'cyclical':{'gp':[[-.06,0],[.02,.04],[.10,.12],[.08,.10],[.06,.09]],'mp':[[.31,.21],[.33,.23],[.35,.25],[.35,.25],[.35,.25]],'wp':[.60,.57,.54,.52,.50]},
 'structural':{'growth':[0.,.04],'margin':[.25,.20],'wc':.60,'capex':.055,'terminal_g':.015,'terminal_margin':.23,'terminal_ic':1.,'terminal_g0':.025},
 'upside':{'growth':[.09,.13],'margin':[.36,.28],'wc':.48,'capex':.05,'terminal_margin':.32,'terminal_g0':.09},
 'margin_minus2pp':{'margin':[.33,.23],'terminal_margin':.28},
 'release_year3':{'special':3},'release_year5':{'special':5},'term_lock3':{'maturity':3},'term_lock5':{'maturity':5},
 'upstream_year3':{'upstream':3},'terminal_release5':{'delay':5},'parent_cash_minus150':{'cash':[888.798788,175.,195.]},
 'tax_incentive_lapse':{'tax':.25},'access_worse':{'friction':[0.,.1,.3],'delay':5},
 'voluntary10_after_cap':{'voluntary':.1},'paid_capital_return':{'redemption':[0.,0.,10.,0.,0.]},
 'zero_dividend_unfunded':{'cash':[0.,0.,0.],'term':[0.,0.,0.],'payout':0.,'extra':[2000.]*5}}

def law(L,R,K,P,V):
    available=max(P-max(-L,0),0)
    compulsory=min(available/10,max(K/2-R,0));optional=(available-compulsory)*V
    return L+P-compulsory-optional,R+compulsory

def reconstruct(c,r=.09,gg=None,mm=None,ii=None):
    c=copy.deepcopy(c);tax=c['tax'];cash=[c['cash'][i]-c['term'][i] for i in range(3)];term=c['term'][:]
    debt=[150.242611,5.,5.];rec=[8.15444172,.17277681];L=1189.40749267;R=195.0525845;K=390.105169;shares=380.985869
    rev=[870.,350.];wc=610.;five=[];pending=600.
    for y in range(5):
        rev=[rev[i]*(1+c.get('gp',[c['growth']]*5)[y][i]) for i in range(2)]
        ebit=sum(rev[i]*c.get('mp',[c['margin']]*5)[y][i] for i in range(2));nop=ebit-max(ebit,0)*tax
        n=sum(rev)*c.get('wp',[c['wc']]*5)[y];fcf=nop+sum(rev)*(.025-c['capex'])-c['extra'][y]-(n-wc);wc=n
        interest=[debt[i]*.03*(1-tax) if max(0,nop*w)/(1-tax)>=debt[i]*.03 else debt[i]*.03-max(0,nop*w)/(1-tax)*tax for i,w in enumerate([.92,.04,.04])]
        fin=[(cash[i]+term[i])*.018*(1-tax) for i in range(3)]
        parent_profit=.92*nop+fin[0]-interest[0]
        for i,w in enumerate([.90,.05,.05]):
            cash[i]+=fcf*w+fin[i]-interest[i]
            if y+1>=c['maturity']:cash[i]+=term[i];term[i]=0.
        if min(cash[1:])<0:raise ValueError('unfunded')
        repayment=[x*[.10,.45,.45,0,0][y] for x in [150.242611,5.,5.]]
        for i in [1,2]:
            support=min(max([180.,30.,30.][i]+repayment[i]-cash[i],0),max(cash[0]-repayment[0]-180,0))
            cash[0]-=support;cash[i]+=support;rec[i-1]+=support
        for i in range(3):
            if cash[i]+1e-8<repayment[i]:raise ValueError('unfunded')
            cash[i]-=repayment[i];debt[i]-=repayment[i]
        costs=0
        for i in [1,2]:
            a=min(max(cash[i]-30,0),rec[i-1]);cash[i]-=a;cash[0]+=a;rec[i-1]-=a
            if y+1>=c['upstream']:
                raw=max(cash[i]-30,0);net=raw*(1-c['friction'][i]);cash[i]-=raw;cash[0]+=net;parent_profit+=net;costs+=raw-net
        L,R=law(L,R,K,parent_profit,c['voluntary'])
        d=min(max(nop+sum(fin)-sum(interest)-costs,0)*c['payout'],max(L,0),max(cash[0]-180,0));cash[0]-=d;L-=d
        sp=min(pending,max(L,0),max(cash[0]-180,0)) if y+1>=c['special'] else 0.;cash[0]-=sp;L-=sp;pending-=sp
        red=c['redemption'][y];cash[0]-=red;shares-=red;K-=red
        five.append(dict(year=y+1,revenue=rev[:],ebit=ebit,nopat=nop,fcf=fcf,wc=wc,cash=cash[:],term=term[:],debt=debt[:],
          parent_legal=L,parent_reserve=R,parent_profit=parent_profit,old_receivable=rec[:],distribution=d+sp+red,shares=shares,registered=K))
    # Only surplus cash is realized; necessary240 is still required and earns throughout.
    surplus=[cash[i]+term[i]-[180.,30.,30.][i]-debt[i] for i in range(3)]
    if min(surplus)<-1e-8:raise ValueError('unfunded terminal')
    # Independent direct sale arithmetic: gross53, fee0.53, taxable gain2.47, tax variable.
    sale=53-.53-2.47*tax;surplus[0]+=sale;L,R=law(L,R,K,-.53-2.47*tax,c['voluntary'])
    for i in [1,2]:
        paid=min(surplus[i],rec[i-1]);surplus[i]-=paid;surplus[0]+=paid;rec[i-1]-=paid
    pay0=min(surplus[0],max(L,0));L-=pay0;surplus[0]-=pay0
    finpv=pay0;oppv=0.;tail=[];sales=sum(rev);margin=ebit/sales
    g=c['terminal_g'] if gg is None else gg;m=c['terminal_margin'] if mm is None else mm;ic=c['terminal_ic'] if ii is None else ii
    for k in range(1,201):
        growth=c['terminal_g0']+(g-c['terminal_g0'])*min(k,10)/10
        new=sales*(1+growth);mar=margin+(m-margin)*min(k,10)/10;np=new*mar-max(new*mar,0)*tax
        free=np-(new-sales)*ic;inc=[x*.018*(1-tax) for x in [180.,30.,30.]]
        fins=[x*.018*(1-tax) for x in surplus];oper=[free*w+inc[i] for i,w in enumerate([.92,.04,.04])]
        net=sum(oper[i]*(1-c['friction'][i]) for i in range(3))
        pp=np*.92+inc[0]+fins[0]+sum(oper[i]*(1-c['friction'][i]) for i in [1,2])
        surplus=[surplus[i]+fins[i] for i in range(3)];L,R=law(L,R,K,pp,c['voluntary'])
        if L+1e-7<net:raise ValueError('tail legal capacity')
        L-=net
        if k>=c['delay']:
            up=sum(surplus[i]*(1-c['friction'][i]) for i in [1,2]);surplus[1:]=[0.,0.];surplus[0]+=up;L,R=law(L,R,K,up,c['voluntary'])
        release=min(surplus[0],max(L,0));L-=release;surplus[0]-=release
        finpv+=release/(1+r)**k;oppv+=net/(1+r)**k
        tail.append(dict(year=k+5,revenue=new,nopat=np,operating_distribution=net,financial_distribution=release,
          distribution=net+release,parent_legal=L,parent_reserve=R,unreleased_financial=surplus[:]))
        sales=new
    access=sum(w*(1-c['friction'][i]) for i,w in enumerate([.92,.04,.04]));fixed=sum(inc[i]*(1-c['friction'][i]) for i in range(3))
    oppv+=(free*access*(1+g)/(r-g)+fixed/r)/(1+r)**200
    dpv=sum(row['distribution']/(1+r)**row['year'] for row in five)
    return dict(rows=five,tail=tail,per_share=(dpv+(oppv+finpv)/(1+r)**5)/380.985869,
      terminal_per_share=(oppv+finpv)/380.985869,terminal_financial=finpv,terminal_operating=oppv)


def test_amoy_literal_complete():
    independent={}
    for name,changes in VARIANTS.items():
        c=copy.deepcopy(DEFAULT);c.update(changes)
        try:independent[name]=dict(feasible=True,**reconstruct(c))
        except ValueError as e:independent[name]=dict(feasible=False,failure=str(e))
    independent['base_low']=reconstruct(DEFAULT,.095,.02,.29,.85)
    independent['base_high']=reconstruct(DEFAULT,.085,.025,.31,.75)
    # Only now read formal output for comparison, not as a reconstruction dependency.
    production=json.loads((ROOT/'2026-Q3-output.json').read_text())
    errors=[];count=0;maxerr=0.
    def check(a,b,path):
        nonlocal count,maxerr
        if isinstance(a,list):
            assert len(a)==len(b),path
            for i,(x,y) in enumerate(zip(a,b)):check(x,y,path+'/'+str(i))
        elif isinstance(a,(int,float)):
            count+=1;err=abs(a-b);maxerr=max(maxerr,err)
            if err>1e-7*max(1,abs(a)):errors.append([path,a,b])
    for name,data in independent.items():
        target=production['scenarios']['base']['low' if name=='base_low' else 'high'] if name in ['base_low','base_high'] else production['scenarios'][name].get('valuation')
        if name not in ['base_low','base_high']:
            assert data['feasible']==production['scenarios'][name]['feasible'],name
            if not data['feasible']:continue
        for k in ['per_share','terminal_per_share','terminal_financial','terminal_operating']:check(data[k],target[k],name+'/'+k)
        for i,row in enumerate(data['rows']):
            other=production['scenarios']['base' if name in ['base_low','base_high'] else name]['rows'][i]
            for k,v in row.items():check(v,other[k],name+'/Y'+str(i+1)+'/'+k)
        for i,row in enumerate(data['tail']):
            for k,v in row.items():check(v,target['tail'][i][k],name+'/tail'+str(i+1)+'/'+k)
    assert not errors,errors[:5]

import runpy,subprocess,sys
from functools import lru_cache
@lru_cache(None)
def model():return runpy.run_path(str(ROOT/'2026-Q3.py'))
@lru_cache(None)
def output():return json.loads((ROOT/'2026-Q3-output.json').read_text())
def test_amoy_actual_capital_creditor_tax():
 m=model();m['tests']()
 q=m['capital_return'](100,10,100,390,380,par_value=1.);assert q['shares']==370 and q['registered']==380
 for kw in [dict(required_exit=3),dict(external_debt=3)]:
  try:m['realize'](2,2,2,.25,0,shares=10,**kw)
  except ValueError:pass
  else:raise AssertionError('insolventexit succeeds')
 assert m['net_interest'](.07,.01,.15)>.068
 assert m['net_interest'](.07,-1,.15)==.07
 assert abs(m['net_interest'](.07,.01,.15)-(.07-.01/.85*.15))<1e-12
 # actual simulation uses capped source current-tax shield
 p=copy.deepcopy(m['INPUT']);p['margin']=[.000001,.000001];p['payout']=0
 try:rows=m['simulate'](p)
 except ValueError:pass
 else:
  first=rows[0];gross=sum(p['opening_debt'])*p['debt_rate'];assert first['interest']>=gross-max(first['nopat'],0)/(1-p['tax'])*p['tax']-1e-9

def test_amoy_actual_regeneration_all_scenarios():
 assert model()['run']()==output()
 for n,v in output()['scenarios'].items():
  if not v['feasible']:continue
  q=v.get('valuation')
  if q is None:continue
  assert q['per_share']>0

def test_amoy_singlefile_expanded_reproducible(tmp_path):
 (tmp_path/'2026-Q3.py').write_bytes((ROOT/'2026-Q3.py').read_bytes());subprocess.run([sys.executable,'-I',str(tmp_path/'2026-Q3.py'),'--expand'],cwd=tmp_path,check=True,stdout=subprocess.DEVNULL)
 assert (tmp_path/'2026-Q3-output.json').read_bytes()==(ROOT/'2026-Q3-output.json').read_bytes()
 assert json.loads(gzip.decompress((tmp_path/'2026-Q3-output.json.gz').read_bytes()))==output()
