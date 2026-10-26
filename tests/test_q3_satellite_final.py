"""独立literal重建，不导入生产代码、不读取其配置；先完成所有预测再比较生产结果。"""
import json,copy,math,gzip,base64
from pathlib import Path

def reconstruct():
    # 以下为人工录入的原始预算，不能从正式输出或正式常量赋值。
    raw={'rev':[580,600,630,655,675],'pre':[132,138,148,158,163],'rent':[30,32,34,35,36],'da':[28,29,31,33,35],'maint':[30,31,33,35,37],'project':[26,22,13.29,0,0],'growth':[5,6,8,10,12],'wc':[4,4,5,5,5],'pay':[12,10.64941641,0,0,0],'dps':[.65,.75,.85,.95,1.05],'scale':[1,1,1,1,1],'cap':[1,1,1,1,1],'er':[0,0,0,0,0],'ew':[0,0,0,0,0],'rate':.033,'delay':0,'freeze':False,'avail':.95,'otax':.21,'fric':.05,'ctax':.15,'ibasis':20.77026500151,'block':0,'delta':0,'cont':False,'legacy':9.0996638532,'window':3,'statutory':9.2269774471,'bookadj':.5}
    cases={'base':copy.deepcopy(raw)}
    x=copy.deepcopy(raw);x.update(scale=[.78,.80,.90,1,1],cap=[1,1,1.05,1.05,1.05],ew=[8,3,-4,-3,0],delay=1);cases['cyclical']=x
    x=copy.deepcopy(raw);x.update(scale=[.65,.65,.62,.60,.60],cap=[1.1]*5,er=[5]*5,ew=[8,3,2,2,2],rate=.045,delay=1);cases['structural_unmitigated']=x
    x=copy.deepcopy(x);x.update(scale=[.65,.65,.60,.58,.58],project=[15,18,18,10.29,0],growth=[0,0,2,3,3],freeze=True);cases['structural']=x
    x=copy.deepcopy(raw);x.update(scale=[1.08,1.1,1.12,1.15,1.15],cap=[1.05,1.05,1.1,1.1,1.1],ew=[2]*5);cases['upside']=x
    for name,change in [('delay3',{'delay':3}),('delay5',{'delay':5}),('zero_parent_legacy',{'legacy':0}),('availability80',{'avail':.8}),('availability100',{'avail':1}),('overseas_friction30',{'fric':.3}),('tax25',{'ctax':.25}),('investment_zero_tax_basis',{'ibasis':0}),('block5',{'block':5}),('tail_ebit_minus10',{'delta':-10}),('continue_parent_reserve',{'cont':True}),('special_window8',{'window':8}),('parent_statutory_zero',{'statutory':0}),('book_adjustment_minus5',{'bookadj':-5}),('book_adjustment_plus5',{'bookadj':5})]:
        x=copy.deepcopy(raw);x.update(change);cases[name]=x
    predictions={}
    for name,a in cases.items():
        predictions[name]={}
        for ep in ['low','high']:
            ke=.11 if ep=='low' else .10;g=.015 if ep=='low' else .02;roi=.10 if ep=='low' else .12
            if name.startswith('structural'):g=.005;roi=.08
            equity_shares=33.68645690;debt0=100.5906153862;restricted=14.0396143021
            weights=[.70,0,.13,.10,.02,.05];capital=[.65,0,.10,.10,0,.15];debtshare=[.48,0,.24,.20,.02,.06]
            cash=[70,0,20,10,27.213399688,.9016081171];debt=[debt0*x for x in debtshare];floor0=[7,0,1.5,1,20,.5]
            # cash中27.213399688由128.1150078051-100-.9016081171手算。
            book=a['legacy'];reserve=a['statutory'];cap=[0]*5;loss=[0]*5;queued=[];borrowing=0.;parent_borrow=0.;sec=9.118;inv=23.0780722239;rows=[];pv=0.;d5=0.
            for year in range(1,401):
                ix=min(year-1,4);factor=(1+g)**max(0,year-5);floor=[x*factor for x in floor0]
                floor_delta=sum(floor)-sum(floor0)*(1+g)**max(0,year-6)
                ebit=a['pre'][ix]*a['scale'][ix]-a['rent'][ix]-a['er'][ix]
                if year>5:ebit=(ebit+a['delta'])*factor
                da=a['da'][ix]*factor;maint=a['maint'][ix]*a['cap'][ix]*factor
                if year<6:invest=(a['project'][ix]+a['growth'][ix])*a['cap'][ix];working=a['wc'][ix]+a['ew'][ix];oldpay=a['pay'][ix]
                else:
                    reinv=max(0,ebit*(1-a['ctax']))*g/roi;invest=.6*reinv;working=.4*reinv-floor_delta;oldpay=0
                if year==8:debt=[max(0,x-restricted*w) for x,w in zip(debt,debtshare)]
                net=[];cf=[];taxes=[];interest=[];newdebt=0.;remitcost=0.;decl=[0.]*5
                for j in range(6):
                    interest.append(debt[j]*a['rate']);inc=max(0,cash[j]-floor[j])*.01
                    if j==2:inc+=sec*.01+inv*.04
                    taxable=ebit*weights[j]+inc-interest[-1]+a['bookadj']*weights[j]*factor
                    rate=a['otax'] if j==4 else a['ctax'];taxes.append(max(0,taxable)*rate)
                    net.append(taxable-taxes[-1]-(.02*factor if j==3 else 0))
                    cf.append(net[-1]-a['bookadj']*weights[j]*factor+da*capital[j]-maint*capital[j]-invest*capital[j]-working*weights[j])
                    cash[j]+=cf[-1]-oldpay*capital[j]
                    if j==5:
                        eligible=max(0,net[-1]-max(0,-book));res=.1*eligible if a['cont'] else min(.1*eligible,max(0,equity_shares*.5-reserve));reserve+=res;book+=net[-1]-res
                    else:
                        signed=cap[j]/a['avail']-loss[j]+net[-1]
                        cap[j]=a['avail']*signed if signed>0 else 0.;loss[j]=-signed if signed<0 else 0.
                sale_cash=0
                if year==1:cash[2]+=9.118;sale_cash+=9.118;sec=0
                if year==10:
                    inv=0
                    price=23.0780722239*.9;tx=max(0,price-a['ibasis'])*.25;cash[2]+=price-tx;sale_cash+=price-tx;gain=price-23.0780722239-tx
                    signed=cap[2]/a['avail']-loss[2]+gain
                    cap[2]=max(0,signed)*a['avail'];loss[2]=max(0,-signed)
                for due,amount in list(queued):
                    if due<=year:cash[5]+=amount;queued.remove((due,amount))
                if year>a['block']:
                    for j in range(5):
                        amount=min(max(0,cash[j]-floor[j]),cap[j]);cash[j]-=amount;cap[j]-=amount;decl[j]=amount
                        netreceipt=amount*(1-a['fric'] if j==4 else 1);remitcost+=amount-netreceipt
                        eligible=max(0,netreceipt-max(0,-book));res=.1*eligible if a['cont'] else min(.1*eligible,max(0,equity_shares*.5-reserve));book+=netreceipt-res;reserve+=res
                        if a['delay']==0:cash[5]+=netreceipt
                        elif netreceipt:queued.append((year+a['delay'],netreceipt))
                bad=None
                for j in range(6):
                    need=max(0,floor[j]-cash[j]);room=max(0,min(40-borrowing,12-parent_borrow if j==5 else 40-borrowing));loan=min(need,room)
                    cash[j]+=loan;debt[j]+=loan;borrowing+=loan;newdebt+=loan
                    if j==5:parent_borrow+=loan
                    if cash[j]<floor[j]-1e-7:bad={'feasible':False,'failed_year':year,'failed_bucket':['L','I','E','H','O','P'][j],'shortfall':floor[j]-cash[j],'rows':rows};break
                if bad:break
                want=(0 if a['freeze'] else a['dps'][ix]*equity_shares) if year<6 else max(0,cash[5]-floor[5])
                if 5<year<=5+a['window']:want/=5+a['window']-year+1
                dividend=min(want,max(0,book),max(0,cash[5]-floor[5]));book-=dividend;cash[5]-=dividend
                discounted=dividend/equity_shares/(1+ke)**year;pv+=discounted
                if year<6:d5+=discounted
                rows.append({'cash':cash[:],'debt':debt[:],'parent_legal_profit':book,'parent_statutory_reserve':reserve,'capacity':cap[:],'loss':loss[:],'profit':sum(net),'tax':sum(taxes),'interest':sum(interest),'cash_generated':sum(cf),'dividend':dividend,'declared':decl[:],'pending_cash':sum(x[1] for x in queued),'growth':invest,'trade_wc':working,'maintenance':maint,'ebit':ebit,'remittance_friction':remitcost,'debt_added':newdebt})
            predictions[name][ep]=bad if bad else {'feasible':True,'rows':rows,'value_per_share':pv,'terminal_equity_per_share':(pv-d5)*(1+ke)**5}
    return predictions

def verify(production):
    predictions=reconstruct() # 全预测先完成，下面才触碰正式预测结果。
    checks=0;maxdiff=0.
    def cmp(a,b):
        nonlocal checks,maxdiff
        checks+=1;maxdiff=max(maxdiff,abs(a-b));assert abs(a-b)<2e-7*max(1,abs(a),abs(b)),(a,b)
    for name,endpoints in predictions.items():
        for ep,r in endpoints.items():
            official=production['scenarios'][name][ep];assert official['feasible']==r['feasible']
            if not r['feasible']:assert official['failed_year']==r['failed_year'];cmp(official['shortfall'],r['shortfall'])
            else:
                for key in ['value_per_share','terminal_equity_per_share']:cmp(official[key],r[key])
            assert len(official['rows'])==len(r['rows'])
            for a,b in zip(official['rows'],r['rows']):
                for key in ['parent_legal_profit','parent_statutory_reserve','profit','tax','interest','cash_generated','dividend','pending_cash','growth','trade_wc','maintenance','ebit','remittance_friction','debt_added']:cmp(a[key],b[key])
                for j,k in enumerate(['L','I','E','H','O','P']):
                    cmp(a['cash'][k],b['cash'][j]);cmp(a['debt'][k],b['debt'][j])
                    if j<5:
                        cmp(a['economic_capacity_not_legal'][k],b['capacity'][j]);cmp(a['unrecovered_budget_losses'][k],b['loss'][j]);cmp(a['declared'][k],b['declared'][j])
    return {'checks':checks,'max_absolute_difference':maxdiff,'independent_literal_all_scenarios_full_tail':'pass','predictions':predictions}

import runpy,subprocess,sys,shutil,hashlib
from functools import lru_cache
D=Path(__file__).resolve().parents[1]/'research/companies/CN/002648/models'
@lru_cache(None)
def model():return runpy.run_path(str(D/'2026-Q3.py'))
@lru_cache(None)
def output():
 w=json.loads((D/'2026-Q3-output.json').read_text());raw=gzip.decompress(base64.b64decode(w['full_payload_gzip_base64']))
 assert hashlib.sha256(raw).hexdigest()==w['full_payload_sha256']
 return json.loads(raw)
def test_satellite_independent_full_400year_paths():
 r=verify(output());assert r['checks']==656080 and r['max_absolute_difference']<1e-6

def test_satellite_actual_loss_disposal_and_funding():
 m=model();m['tests']()
 c,l=m['economic_profit'](9.5,0,-4,.95);assert abs(c-5.7)<1e-9 and l==0
 c,l=m['economic_profit'](c,l,-9,.95);assert c==0 and abs(l-3)<1e-12
 c,l=m['economic_profit'](c,l,2,.95);assert c==0 and abs(l-1)<1e-12
 c,l=m['economic_profit'](c,l,5,.95);assert abs(c-3.8)<1e-12 and l==0
 assert not m['disposal'](0,0,0,0,5,0,1,0,0)['feasible']
 c=copy.deepcopy(m['BASE']);c.update(scale=[1,0,0,1,1],release_block=1,max_debt=400,parent_limit=400,freeze=True)
 r=m['run'](c,m['PARAM']['low'],2,False);assert r['feasible']
 p=sum(x['flows']['E']['profit'] for x in r['rows']);d=sum(x['declared']['E'] for x in r['rows'])
 assert abs(p-8.041941462258322)<1e-9 and abs(d-7.639844389145406)<1e-9

def test_satellite_all_profit_balances_and_financial_births():
 m=model();o=output();m['cohort_checks'](o['scenarios'])
 for eps in o['scenarios'].values():
  for r in eps.values():
   a=r['config']['availability'];balance={k:r['config']['initial_capacity']/a for k in m['K'][:-1]}
   for row in r['rows']:
    for k in balance:
     before=balance[k]+row['flows'][k]['profit']+(row['sale_book_gain'] if k=='E' else 0)
     assert row['declared'][k]<=max(0,before)*a+1e-7
     balance[k]=before-row['declared'][k]/a
     actual=row['economic_capacity_not_legal'][k]/a-row['unrecovered_budget_losses'][k]
     assert abs(actual-balance[k])<1e-6*max(1,abs(actual))
     assert row['economic_capacity_not_legal'][k]*row['unrecovered_budget_losses'][k]==0

def test_satellite_single_file_complete_reproduction(tmp_path):
 f=tmp_path/'2026-Q3.py';shutil.copy2(D/'2026-Q3.py',f)
 subprocess.run([sys.executable,str(f)],check=True,stdout=subprocess.DEVNULL)
 assert f.with_name('2026-Q3-output.json').read_bytes()==(D/'2026-Q3-output.json').read_bytes()
 subprocess.run([sys.executable,str(f),'--expand'],check=True,stdout=subprocess.DEVNULL)
 assert json.loads(f.with_name('2026-Q3-expanded.json').read_text())==output()
 for n,key in [('independent-literal-output.json.gz','independent_predictions_artifact'),('loss-ledger-same-budget.json.gz','loss_ledger_same_budget')]:
  assert f.with_name(n).exists()
