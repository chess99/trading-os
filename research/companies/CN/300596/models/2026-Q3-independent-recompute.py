"""独立literal复算；不导入生产代码、不取其inputs；只读结果作对照。"""
import json, pathlib
X=json.loads((pathlib.Path(__file__).parent/'2026-Q3-output.json').read_text())
checks=[]
for bump,key in [(0,'base'),(-.01,'anti_margin_-0.01'),(.01,'anti_margin_0.01')]:
    a=[58,62.5,67,71,75,78,81,84,87,90]; l=[15,16.5,18,19.5,21,22,23,24,25,26]; new=[.7,1,1.4,1.8,2.2,2.5,2.8,3.1,3.4,3.7]
    am=[.12,.122,.124,.125,.125,.124,.123,.122,.121,.12];lm=[.095,.1,.105,.11,.115,.116,.117,.118,.119,.12]
    ne=[-.4,-.35,-.2,0,.1,.15,.2,.25,.3,.35];da=[4.2,4.6,4.9,5.2,5.4,5.5,5.6,5.7,5.8,5.9]
    invest=[8.7,7.5,5.7,5.3,5.4,5.5,5.6,5.7,5.8,5.9];upplan=[1.5,1.8,2.1,2.5,3,3.4,3.8,4.2,4.6,5]
    ownp=[.1,.15,.2,.25,.3,.35,.4,.45,.5,.55];ownc=[0,.1,.15,.2,.25,.3,.35,.4,.45,.5]
    fund=[2,1.5,.8,.5,.4,.4,.4,.4,.4,.4];settle=[-1,-.5,0,0,0,0,0,0,0,0];D=[.45,.5,.6,.7,.8,.9,1,1.1,1.2,1.3]
    minor=[-.12,-.1,-.05,0,.02,.04,.06,.08,.1,.12];rp=[0,0,.5,1,1.5,2,2.5,3,3,3]
    P=8.4999897194;C=20.1010664173-P;A=18.50420146;B=39.8918366226-A;R=3.7588349652;Z=1.0337783199;N=1.3748068389;prev=67
    children=[[0.,0.,1.25,1.4990559776,.5],[0.,0.,.36,1.3426936172,13/30],[0.,0.,.106875,.4223655154,1/15]]
    rr=[]
    for j in range(10):
        sales=a[j]+l[j]+new[j]; profit=(a[j]*(am[j]+bump)+l[j]*lm[j]+ne[j])*.83
        ip=A*.032*.83;isub=B*.032*.83;ii=max(P+C-10,0)*.01
        net=profit+da[j]-invest[j]-(sales-prev)*.22-([.5,.3]+[0]*8)[j]-ip-isub+ii
        pcash=ownc[j]+18.50420146*.032*.83-ip;pprofit=ownp[j]+18.50420146*.032*.83-ip
        before=C+net-pcash+fund[j]-settle[j]
        wants=[]
        for ch in children:
            cp=ch[3]*a[j]/58
            addition=max(0,min(.1*max(cp+min(ch[0],0),0),.5*ch[2]-ch[1]))
            ch[0]+=cp-addition;ch[1]+=addition;wants.append(max(0,min(ch[0],upplan[j]*ch[4])))
        u=max(0,min(sum(wants),before-7,.45*profit))
        for ch,w in zip(children,wants):ch[0]-=w*u/sum(wants)
        parprofit=pprofit+u;add=max(0,min(.1*max(parprofit+min(R,0),0),1.148098335-Z));R+=parprofit-add;Z+=add
        ppre=P+pcash+u-fund[j]+settle[j];cpre=before-u;mn=max(minor[j],0)*.2
        d=max(0,min(D[j]*2.29619667,R,ppre-3,P+C+net-mn-10))
        ab=max(3-ppre+d,0);bb=max(7-cpre+mn,0);ar=max(0,min(A,rp[j],ppre-d-3));br=max(0,min(B,cpre-mn-9))
        mat=min(A,.5*max(A-(8 if j<3 else 0),0)+(8 if j==2 else 0));gross=max(ar,mat);sb_gross=max(br,B*.5)
        P=ppre-d+ab-ar;C=cpre-mn+bb-br;A+=ab-ar;B+=bb-br;R-=d;N+=minor[j]-mn-((.054+(.6-.054)*.4882) if j==1 else 0)
        row={'nopat':profit,'group_free_cash':net,'parent_cash':P,'subsidiary_cash':C,'parent_debt':A,'subsidiary_debt':B,'parent_retained':R,'parent_reserve':Z,'parent_reserve_add':add,'upstream_declared_and_received':u,'common_distribution':d,'group_cash':P+C,'group_debt':A+B,'nci_book':N,'parent_gross_repayment':gross,'parent_gross_borrowing':gross-ar+ab,'sub_gross_repayment':sb_gross,'sub_gross_borrowing':sb_gross-br+bb}
        for field,num in row.items():assert abs(num-X['scenarios'][key]['rows'][j][field])<1e-8,(key,j,field,num)
        rr.append(row);prev=sales
    vals=[]
    for rate in [.11,.1]:
        tv=(rr[-1]['nopat']*1.02*(1-.02/.11)/(rate-.02)+P+C-10+.4545495239-A-B-max(N,.12*1.02/(rate-.02)))
        v=(sum(r['common_distribution']/(1+rate)**(i+1) for i,r in enumerate(rr))+tv/(1+rate)**10)/2.29619667
        tv5=(sum(rr[i]['common_distribution']/(1+rate)**(i-4) for i in range(5,10))+tv/(1+rate)**5)/2.29619667
        q=rr[4];aux=(sum(rr[i]['common_distribution']/(1+rate)**(i+1) for i in range(5))+(q['nopat']/rate+q['group_cash']-10+.4545495239-q['group_debt']-max(q['nci_book'],.02/rate))/(1+rate)**5)/2.29619667
        expected=X['scenarios'][key]['valuation'][0 if rate==.11 else 1]
        for f,n in [('value',v),('terminal_year5',tv5),('auxiliary_value',aux)]:assert abs(n-expected[f])<1e-8,(key,f,n,expected[f])
        vals.append({'k':rate,'value':v,'terminal_year5':tv5,'auxiliary_value':aux})
    checks.append({'scenario':key,'ten_years_cash_debt_legal_and_gross_principal':'pass','valuation':vals})
print(json.dumps({'independent_literal':checks,'production_imported':False,'production_inputs_read':False,'passed':True},ensure_ascii=False,indent=2))
