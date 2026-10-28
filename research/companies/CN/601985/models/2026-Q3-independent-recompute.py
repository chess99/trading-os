"""Literal-input second implementation; no production output/balance arrays read.
Two-variable Newton funding solution instead of production fixed-point iteration.
"""
import json, importlib.util
from pathlib import Path

def independent(mode):
    data=[(466.7883,397.9091,2.53,.46,1,1),(482.6090,378.3657,2.55,.54,2,1),
    (461.7521,317.7687,2.5,.56,2,1),(389.3578,245.3087,2.5,.54,3,1),
    (360.9005,149.7120,2.42,.51,4,1),(414.4716,158.8516,2.46,.51,5,1),
    (678.7293,127.1264,3.09,.46,6,1),(405.1699,63.0218,2.5,.56,6,1),
    (1410.5079,510.5079,5.085,.51,8,0),(400,206.0095,9.2406,.50,2,0)]
    low=mode=='low'; k=.092 if low else .086;g=.005 if low else .0075
    r=.026 if low else .024; over=1.04 if low else 1
    price=.325 if low else (.323 if mode=='price_down' else .333)
    oldprice=-.005 if low else (-.0125 if mode=='price_down' else -.0025)
    unit=.14 if low else .135; hours=7100 if low else 7300
    renewprice=.29 if low else .30; renewhours=1800 if low else 1900
    cap0=35.393165244+(15 if low else 10); recovery=0 if low else 5
    rem=sum((p[0]-p[1])*over for p in data)
    cohorts=[]
    for cost,paid,gw,share,first,vat in data:
        rest=(cost-paid)*over; advance=140*rest/rem
        cohorts.append((paid+rest,paid+advance,rest-advance,gw,share,first,vat))
    opening_cip=sum(p[1] for p in cohorts)
    shares=205.68002074; debt=4980.52; parent=204.590962185; loans=0
    book=1205.2045634206; nci=1164.9038483641; cum=0
    olde=60.660476185*4/3; oldn=120.4824133592*4/3; ratio=olde/oldn
    dep0=2*(107.850361536+2.461898966+2.874038899+.985422893)
    results=[]; maxerr=0
    for t in range(1,21):
        growth=depr=op=ownop=vat=ownvat=capitalint=inject=minorcap=maint=0
        for i,(cost,paid,rest,gw,share,first,vatflag) in enumerate(cohorts):
            f=max(0,min(1,(t-first+1)/2)); prior=max(0,min(1,(t-first)/2))
            paidnow=rest/(first+1) if t<=first+1 else 0
            capitalint+=(cap0*paid/opening_cip+.024*.8*(rest*min(t-1,first+1)/(first+1)+paidnow/2))*(1-(f+prior)/2)
            growth+=paidnow; inject+=paidnow*.2*share;minorcap+=paidnow*.2*(1-share)
            volume=gw*(renewhours if i==9 else hours)*f/100
            p=renewprice if i==9 else price;c=.07 if i==9 else unit
            dd=cost*f/(20 if i==9 else 40); e=volume*(p-c)-dd
            v=volume*p*.03 if vatflag and t-first<10 else 0
            depr+=dd;op+=e;ownop+=e*share;vat+=v;ownvat+=v*share
            maint+=dd*min(1,.5+max(0,t-first)*.05)
        extra=capitalint*(r/.024-1);capitalint+=extra
        growth+=extra;inject+=extra*.106;minorcap+=extra*.094
        op-=cum/40;ownop-=cum/40*.53;depr+=cum/40;cum+=extra
        depreciation=dep0+depr;capex=growth+maint+dep0*min(1,.5+.05*t)
        wc=10 if t<=10 else 0;buffer=6.2754993335 if t==1 else 0
        if t<=5: loan=40
        else:
            last=results[-1];loan=-min(loans,max(0,last['net']+last['da']-last['capex']-last['div']-last['md'])*.3)
        avgloan=loans+loan/2
        fade=26.5566913547*min(1,t/10)
        operatingchange=1910.16*oldprice+recovery*min(1,t/3)-fade
        release=.0172131317 if t==1 else 0
        def calculate(dnext,pnext):
            totalinterest=66.6217166852+cap0+((debt+dnext)/2-4980.52)*r+(r-.024)*4980.52*min(t/5,1)
            interest=max(0,totalinterest-capitalint)
            ip=r*((parent+pnext)/2-204.590962185-avgloan)
            ni=oldn+.75*(operatingchange+op-interest+66.6217166852)+vat-.25*fade
            ce=olde+.75*(operatingchange*ratio+ownop-(interest-66.6217166852)*.53-ip*.47)+ownvat-.3-.25*fade*ratio
            mi=ni-ce-.3
            div=min([.16,.18,.20,.22,.24][t-1]*shares,max(0,ce)*.5) if t<=5 else max(0,ce)*(.45 if t<=10 else .6)
            md=max(0,mi)*(.5 if t<=10 else .6)
            pe=5+ip;up=max(0,min(.85*max(0,ce+5+ip),parent+inject+loan+div+pe-release))
            wantd=debt+capex+div+md+.3-ni-depreciation+wc+buffer-minorcap
            wantp=parent+inject+loan+div+pe-up-release
            return (dnext-wantd,pnext-wantp),(ni,ce,mi,div,md,up,pe)
        x,y=debt,parent
        for _ in range(12):
            f,vals=calculate(x,y)
            if max(abs(v) for v in f)<1e-9:break
            fx,_=calculate(x+.01,y);fy,_=calculate(x,y+.01)
            a,b=(fx[0]-f[0])/.01,(fy[0]-f[0])/.01
            c,d=(fx[1]-f[1])/.01,(fy[1]-f[1])/.01;det=a*d-b*c
            x-=(d*f[0]-b*f[1])/det;y-=(-c*f[0]+a*f[1])/det
        _,(ni,ce,mi,div,md,up,pe)=calculate(x,y)
        residual=ni+depreciation-wc+minorcap+x-debt-buffer-capex-div-md-.3
        maxerr=max(maxerr,abs(residual));book+=ce-div;nci+=mi-md+minorcap
        results.append(dict(t=t,profit=ce,net=ni,da=depreciation,capex=capex,div=div,md=md,book=book,debt=x,parent=y,up=up))
        debt,parent,loans=x,y,loans+loan
    terminal=(results[-1]['profit']*(1+g)-g*book)/(k-g)
    value=(sum(z['div']/(1+k)**z['t'] for z in results)+terminal/(1+k)**20)/shares
    tv5=(sum(z['div']/(1+k)**(z['t']-5) for z in results[5:])+terminal/(1+k)**15)/shares
    return dict(value=value,terminal5=tv5,max_cash_error=maxerr,y1=results[0],y5=results[4],y20=results[-1])

if __name__=='__main__':
    independent_values={n:independent(n) for n in ['low','base','price_down']}
    spec=importlib.util.spec_from_file_location('production',Path(__file__).with_name('2026-Q3.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    params={'low':p.LOW,'base':p.BASE,'price_down':{**p.BASE,'price':.323,'existing_price_change':-.0125}}
    for name,v in independent_values.items():
        prod=p.model(params[name]);assert abs(v['value']-prod['value'])<1e-9
        assert abs(v['terminal5']-prod['terminal_year5'])<1e-9
        for year in [1,5,20]:
            assert abs(v['y'+str(year)]['debt']-prod['rows'][year-1]['debt_end'])<1e-7
            assert abs(v['y'+str(year)]['parent']-prod['rows'][year-1]['parent_debt_end'])<1e-7
    Path(__file__).with_name('independent-check-output.json').write_text(json.dumps(independent_values,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(independent_values,ensure_ascii=False,indent=2))
