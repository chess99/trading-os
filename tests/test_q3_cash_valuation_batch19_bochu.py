#!/usr/bin/env python3
"""Independent numerical audit. Literal assumptions independently transcribed
from source/assumption sheet. Does not import/read/parse production code or
parameters. Only after completing all arithmetic does it read final outputs
for comparison. Units RMB million. Different array-state implementation.
"""
import math,json,pathlib
HERE=pathlib.Path(__file__).resolve().parents[1]/"research/companies/CN/688188/models"

def calculate(growth,start_margin,end_margin,discount,initial_return,terminal_return,sweep,shock=0.,finalmargin=None,tail=0.02,prefix=False,capital_return_amount=0.,cancel_fraction=0.,return_year=10,horizon=600,up_start=3,cycle=False,historical_fraction=1.,current_fraction=1.):
    cash=[4500.,806.0990022124001,380.,25.0034]; earned=[1881.70389523,200.,300.,-1.9109]; reserve=[144.3649635,0.,0.,0.]; capital=[405.984426,60.,32.,55.]
    borrowing=[28.99906365,0.,0.,0.]; owing=[236.28293593,0.,0.,0.]; revenue=2500.; oldprofit=1150.; stock=405.984426
    loans=[0.,0.]
    previous_routes=[0.,0.]; forwarding=[0.,0.]; waiting=[0.,0.]
    protected=[999.4403,24.984,0.,11.2534]
    precision_profit=-4.; original_units=1.; capital_surplus=2891.00726931
    dividend_adjustment=.582; total=0.; remainder=0.; first=[]; snapshots=[]
    # Independently transcribed calendar/contract arithmetic; no production imports.
    annual=[];sale=2500.
    for k in range(4):
        gr=[.15,.14,.12,.10][k] if prefix else growth[k]
        sale*=1+gr
        mm=.46-.06*k/9 if prefix else start_margin+(end_margin-start_margin)*k/9
        if cycle and k<3:mm=[.38,.41,.44][k]
        annual.append([sale,sale*mm])
    ratio=(1+(.15 if prefix else growth[0]))/1.15
    qop=625*(.46 if prefix else start_margin)*ratio
    fy={2026:[1879.56668264+(2195.63231292-1619.59650409)*1.1651*ratio,1109.20652312+qop+25-27.1691,1100.46452148+(9.02684536+5.25)*current_fraction+qop*.99275+25]}
    for k in range(3):
        op=(annual[k][1]*5+annual[k+1][1])/6
        fy[2027+k]=[(annual[k][0]*5+annual[k+1][0])/6,op+100-[60,40,20][k],op*.99275+100]
    personal_old=117752/(611520*.3*.85)
    # plan-index, payment-year, fiscal-year, amount, thresholds, rates, sales-base, profit-base, personal, profit-column
    lots=[(0,1,2026,.3424512,(.4,1.2,2),(.7,.85,1),898.49194944,492.09851191,personal_old,1),
      (1,1,2026,.516852,(.3,.9,1.5),(.8,.9,1),1407.11318352,753.52430130,337842/(1722840*.3*.8),1),
      (1,1,2026,.10185,(.3,.9,1.5),(.8,.9,1),1407.11318352,753.52430130,89241/(339500*.4*.8),1),
      (1,2,2027,.10185,(.4,1.2,2),(.8,.9,1),1407.11318352,753.52430130,89241/(339500*.4*.8),1)]
    for k in range(3):
        lots.append((2,k+1,2026+k,[1.05942,1.05942,1.41256][k],[(.15,.25,.4),(.3,.5,.8),(.45,.75,1.2)][k],(.8,.9,1),2195.63231292,1112.54760775+53.76309984*historical_fraction,personal_old,2))
        lots.append((3,k+2,2027+k,[.24117,.24117,.32156][k],[(.3,.5,.8),(.45,.75,1.2),(.6,1,1.6)][k],(.8,.9,1),2195.63231292,1112.54760775+53.76309984*historical_fraction,personal_old,2))
    future={i:[0.,0.,0.,0.] for i in range(1,5)};nominal=[0.]*4;earnedshares=[0.]*4
    for plan,yr,calendar,q,th,rt,baser,basep,personal,column in lots:
        scale=max(fy[calendar][0]/baser-1,fy[calendar][column]/basep-1)
        rate=0
        for cutoff,frac in zip(th,rt):
            if scale>=cutoff-1e-12:rate=frac
        qty=q*rate*personal;future[yr][plan]+=qty;nominal[plan]+=q;earnedshares[plan]+=qty
    expected=[a/b for a,b in zip(earnedshares,nominal)]
    for t in range(1,horizon+1):
        g=growth[t-1] if t<=10 else tail
        if prefix and t<=5:g=[.15,.14,.12,.10,.08][t-1]
        oldsales=revenue;revenue=revenue*(1+g)
        m=start_margin+(end_margin-start_margin)*min(t-1,9)/9
        if prefix:
            m=.46-.06*(t-1)/9 if t<=5 else (.46-.06*4/9)+(end_margin-(.46-.06*4/9))*min(t-5,5)/5
        if cycle and t<=3:m=[.38,.41,.44][t-1]
        profit=revenue*m
        ret=initial_return+(terminal_return-initial_return)*min(t-1,9)/9
        if prefix and t<=5:ret=.60-.35*(t-1)/9
        netcapital=max(max(profit-oldprofit,0)/ret, (698.8312/3 if t<=3 else 0)+.15*max(revenue-oldsales,0))
        if g<0:netcapital+=.06*(revenue-oldsales)
        fees=([3/.68,5/.68,22.1691*2/3+77.2294*5/6,5/.68] if t==1 else [0,1/.68,77.2294/6+37.2243*5/6,10/.68] if t==2 else [0,0,37.2243/6+15.1744*5/6,7/.68] if t==3 else [0,0,15.1744/6,3/.68] if t==4 else [0]*4)
        charge=sum(a*b for a,b in zip(fees,expected))
        quantities=future.get(t,[0.,0.,0.,0.])
        issue=sum(quantities)
        subscription=sum(q*max(price-dividend_adjustment,1.000001) for q,price in zip(quantities,[20.36,44.62,50.7,50.7]))
        stock+=issue;capital[0]+=issue;capital_surplus+=subscription-issue+charge*.8
        initialcash=cash[:];initialdebt=borrowing[:]
        old_common=owing[0];receipts=[owing[1]+owing[3]*.75+previous_routes[0],previous_routes[1],0,0]
        route_now=waiting[:];waiting=[0.,0.]
        for j in range(4):cash[j]=cash[j]+receipts[j]-owing[j]
        if t<4:
            draw=max(104.984/3-protected[1],0)
            loans[0]+=draw
            cash[0]-=draw;cash[1]+=draw
            protected[0]=(protected[0]-draw)*1.02-754.9289/3
            protected[1]=(protected[1]+draw)*1.02-104.984/3
            protected[3]=max(protected[3]*1.02-17/3,0)
        else:
            repay=min(loans[0],loans[0]/max(9-t,1),max(cash[1]-protected[1]*1.02-revenue*.04-netcapital*.34,0))
            loans[0]-=repay;cash[0]+=repay;cash[1]-=repay
            protected[0]+=repay
            protected=[v*1.02 for v in protected]
        if t==8:protected=[0.,0.,0.,0.]
        precision_profit=[-4,0,2,4,6][t-1] if t<=5 else precision_profit*(1+g)
        operating=[profit*.779,profit*.12-precision_profit,profit*.1,precision_profit]
        own=[operating[j]+cash[j]*.02-initialdebt[j]*.04-charge*[.8,.1,.1,0][j] for j in range(4)]
        netpay=[0.,0.,0.,0.];journal=[]
        for j in range(3,-1,-1):
            dividend_income=netpay[1]+netpay[3]*.75+route_now[0] if j==0 else route_now[1] if j==1 else 0
            accounting=own[j]+dividend_income
            earnings_available=earned[j]+accounting
            setaside=min(max(earnings_available,0)*.1,max(accounting,0)*.1,max(capital[j]/2-reserve[j],0))
            reserve[j]+=setaside;earnings_available-=setaside
            capex=([608.8312/3+(netcapital-698.8312/3)*.35,80/3+(netcapital-698.8312/3)*.34,(netcapital-698.8312/3)*.30,10/3+(netcapital-698.8312/3)*.01][j] if t<=3 else netcapital*[.35,.34,.30,.01][j])
            liquid=cash[j]+own[j]+charge*[.8,.1,.1,0][j]-capex+(subscription if j==0 else 0)
            required=revenue*[.06,.04,.025,.001][j]+protected[j]
            increase=min(max(required-liquid,0),max([200,100,50,10][j]-borrowing[j],0))
            liquid+=increase;borrowing[j]+=increase
            failure=max(required-liquid,0)
            decrease=min(borrowing[j],max(liquid-required,0));liquid-=decrease;borrowing[j]-=decrease
            if j==0:normal=max(own[0]+own[1]+own[2]*.9275+own[3]*.946964,0)*.55
            else:normal=max(own[j],0)*.65 if t>=up_start else 0
            if t>5:normal=max(own[j]+dividend_income-capex,0)
            release=sweep*max(cash[j]+own[j]+charge*[.8,.1,.1,0][j]-capex+(subscription if j==0 else 0)-required-normal,0) if t>5 else 0
            payment=min(normal+release,max(earnings_available,0),max(liquid-required,0)) if failure<1e-8 else 0
            earned[j]=earnings_available-payment
            cash[j]=liquid-(payment if j==0 else 0)
            netpay[j]=payment
            journal.append([j,cash[j],earned[j],reserve[j],payment,dividend_income,receipts[j],borrowing[j]])
        waiting=[netpay[3]*.196964,netpay[2]*.9275]
        previous_routes=route_now[:]
        owing=[0,netpay[1],netpay[2],netpay[3]]
        payout=original_units*netpay[0]/stock+(old_common/405.984426 if t==1 else 0)
        dividend_adjustment+=netpay[0]/stock
        if t==return_year and capital_return_amount:
            payout+=original_units*capital_return_amount/stock
            capital_surplus-=capital_return_amount-capital[0]*cancel_fraction+capital_return_amount*.01
            cash[0]-=capital_return_amount*1.01
            capital[0]*=1-cancel_fraction;stock*=1-cancel_fraction;original_units*=1-cancel_fraction
        total+=payout/((1+discount)**t)
        if t>5:remainder+=payout/((1+discount)**(t-5))
        if t<=5:first.append(payout)
        snapshots.append({'year':t,'cash_legal_journal':journal,'payout':payout,'shares':stock,'capital_surplus':capital_surplus})
        oldprofit=profit
    return {'pv':total,'terminal_year5':remainder,'distributions':first,'snapshots':snapshots}


def test_bochu_independent_literal_entity_distributions():
 checks={
  'capital_return_y10_300m':calculate([.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],.46,.40,.09,.60,.25,.15,capital_return_amount=300.,cancel_fraction=.1),
  'capital_return_y10_600m':calculate([.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],.46,.40,.09,.60,.25,.15,capital_return_amount=600.,cancel_fraction=.2),
  'core_low':calculate([.13,.12,.10,.09,.07,.055,.045,.035,.025,.02],.45,.39,.095,.55,.25,.10),
  'core_high':calculate([.17,.15,.13,.11,.09,.07,.055,.04,.03,.02],.47,.41,.085,.65,.28,.20),
  'base':calculate([.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],.46,.40,.09,.60,.25,.15),
  'r_plus_1pp':calculate([.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],.46,.40,.10,.60,.25,.15),
  'long_margin_minus_5pp':calculate([.15,.14,.12,.10,.08,.065,.05,.04,.03,.02],.46,.35,.09,.60,.25,.15),
  'holder_low':calculate([.13,.12,.10,.09,.07,.055,.045,.035,.025,.02],.45,.39,.095,.55,.25,.15,prefix=True),
  'holder_high':calculate([.17,.15,.13,.11,.09,.07,.055,.04,.03,.02],.47,.41,.085,.65,.28,.15,prefix=True)
 }
 # Output only is read after all independent calculations finish.
 production=load_output()
 for label,calc in checks.items():
     target=(production['holder_conditionals']['core_'+label.split('_')[1]] if label.startswith('holder_') else production['scenarios'].get(label,production['sensitivities'].get(label)))
     calc['comparison']={field:calc[field]-target[field] for field in ['pv','terminal_year5']}
     calc['distribution_max_error']=max(abs(a-b) for a,b in zip(calc['distributions'],target['distributions']))
     assert max(abs(v) for v in calc['comparison'].values())<1e-8,(label,calc['comparison'])
     assert calc['distribution_max_error']<1e-10

def test_bochu_actual_functions_complete_restricted_fund_roundtrip():
 import gzip,base64,hashlib,math
 P=HERE
 x=load_output();tables=x['annual_tables']
 s=x['table_schema'];count=0
 for group,cases in tables.items():
  for key,values in cases.items():
   previous_reserve=[144.3649635,0.,0.,0.]
   for v in values:
    row=dict(zip(s['row_columns'],v));nodes=[dict(zip(s['node_columns'],n)) for n in row['nodes']];count+=1
    for i,n in enumerate(nodes):
     def near(a,b):assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-7),(group,key,row['year'],i,a,b)
     near(n['restricted_close'],n['restricted_open']+n['restricted_transfer']+n['restricted_financial_income']-n['qualified_project_spending']-n['conditional_authorised_release'])
     near(n['cash_close'],n['financial_interest_base']+n['own_profit']+n['noncash_compensation']-n['investment']+n['capital_inflow']+n['debt_draw']-n['debt_repaid']-(n['new_declaration'] if i==0 else 0)-((row['capital_return_event']['capital_return']+row['capital_return_event']['friction']) if i==0 and row['capital_return_event'] else 0))
     near(n['retained_close'],n['retained_open']+n['own_profit']+n['declared_investment_income']-n['reserve_appropriation']-n['new_declaration'])
     assert n['reserve']<=max(previous_reserve[i],n['registered_capital_budget']*.5)+1e-7
     previous_reserve[i]=n['reserve']
     assert n['new_declaration']<=max(n['legal_profit_before_distribution'],0)+1e-7
     if i==0:
      assert n['intercompany_loan_receivable']<=80+1e-7
      if row['year']>=4:near(n['restricted_transfer'],n['internal_project_cash_flow'])
   assert x[group][key]['feasible'] or (group=='diagnostics' and x[group][key]['maximum_funding_failure']>0 and x[group][key]['pv'] is None)
 for key in tables['holder_conditionals']:assert tables['holder_conditionals'][key][:5]==tables['scenarios']['base'][:5]
 f=x['production_hand_tests']['full_run_zero_dividend_capital_failure'];assert len(f['rows'])==1 and f['pv'] is None and f['terminal_year5'] is None
 
 import runpy
 m=runpy.run_path(str(HERE/'2026-Q3.py'));t=m['tests']()
 assert t['loss_recovery']['appropriation']==1
 assert t['zero_dividend_failure']['funding_failure']==90

 for group,cases in tables.items():
  for key,values in cases.items():
   for v in values:
    row=dict(zip(s['row_columns'],v))
    for n in row['nodes']:
     n=dict(zip(s['node_columns'],n))
     assert n['cash_close']-n['dividend_payable']>=n['liquidity_floor']-1e-7*max(1,n['liquidity_floor'])
 for name,c in x['convergence'].items():
  for field in ['pv','terminal_year5']:
   assert abs(c['600'][field]-c['1200'][field])<1e-6


def load_output():
    """Closed single-XZ transport; validate every compressed/expanded byte."""
    import hashlib, lzma, tempfile
    descriptor=json.loads((HERE/'2026-Q3-output.json').read_text())
    assert descriptor['schema']=='trading_os_lossless_json_xz_v1'
    assert descriptor['artifact_kind']=='transport_manifest_not_model_result'
    assert descriptor['compression']=='xz' and descriptor['file']=='2026-Q3-output.json.xz'
    assert 0<descriptor['compressed_bytes']<=100*1024**2
    assert 0<descriptor['expanded_bytes']<=512*1024**2
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=256*1024**2)
    encoded_hash=hashlib.sha256();decoded_hash=hashlib.sha256();encoded_size=decoded_size=0
    with (HERE/descriptor['file']).open('rb')as source,tempfile.TemporaryFile()as decoded:
        while chunk:=source.read(65536):
            assert not decoder.eof
            encoded_size+=len(chunk);encoded_hash.update(chunk)
            assert encoded_size<=descriptor['compressed_bytes']
            data=chunk
            while True:
                part=decoder.decompress(data,max_length=1048576);data=b''
                decoded_size+=len(part);assert decoded_size<=descriptor['expanded_bytes']
                decoded_hash.update(part);decoded.write(part)
                if decoder.needs_input or decoder.eof:break
            assert not decoder.unused_data
        assert decoder.eof and not decoder.unused_data
        assert encoded_size==descriptor['compressed_bytes'] and encoded_hash.hexdigest()==descriptor['compressed_sha256']
        assert decoded_size==descriptor['expanded_bytes'] and decoded_hash.hexdigest()==descriptor['expanded_sha256']
        decoded.seek(0);return json.load(decoded)
