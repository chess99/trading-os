"""CN:300693, 2026-Q3. Stdlib-only, CNY million except shares (million) and CNY/share.
Annual years are rolling budgets after 2026-10-26. Long continuation is quadrature,
not a forecast of named distant years. No market price, IRR or trading threshold.
"""
import copy,json,math
from pathlib import Path
P={
 'revenue0':[1050.,1040.,1670.,270.,90.],
 'growth5':[[.22,.20,.12,.06,.05],[.18,.17,.10,.06,.04],[.15,.14,.09,.05,.04],[.12,.12,.08,.05,.03],[.10,.10,.07,.04,.03]],
 'gross5':[[.59,.34,.30,.31,.30],[.58,.335,.295,.31,.30],[.57,.33,.29,.31,.30],[.56,.325,.285,.31,.30],[.55,.32,.28,.31,.30]],
 'gross_mature':[.50,.27,.25,.28,.28], 'opex5':[.245,.241,.238,.235,.232], 'opex_mature':.225,
 'tax':.15,'wc_ratio':.14,'wc0':400.,'fixed0':820.,'depreciation_ratio':.025,'capex_ratio':.035,
 'committed_capex':[80.,40.,0.,0.,0.], 'long_g':.02,'fade_end':15,'capital_allocation_fade_end':15,
 'cash0':[400.,25.,20.,15.,10.,10.,12.], 'excluded_minor_cash':22.50624451,
 'term0':[610.,0.,0.,0.,0.,28.88201449,0.], 'maturity_year':3,
 'debt0':[100.06944556,0.,0.,0.,0.,0.,0.], 'lease0':12.34619662,
 'legal0':[1600.,3.,-21.6641,-23.2001,-1.2582,0.,-36.],
 'reserve0':[210.59477448,.5,0.,0.,0.,0.,0.], 'capital0':[312.795823,5.,180.,50.,5.,60.,50.],
 'loan0':[142.00445104,158.00074483,0.,31.83073359,111.,0.],
 'cash_floor_weights':[.72,.05,.06,.045,.025,.075,.025], 'cash_floor_ratio':.10,
 'reinvest_weights':[.60,.05,.10,.08,.02,.14,.01],
 'subs_profit5':[[.005,-.003,-.025,.015,-.010,-.002],[.008,.002,-.012,.018,-.005,0.],[.012,.010,0.,.020,.005,.003],[.016,.018,.020,.023,.020,.006],[.020,.025,.040,.025,.030,.010]],
 'subs_profit_mature':[.02,.025,.04,.025,.03,.01], 'ownership':[1.,1.,1.,1.,1.,1.,.5],
 'deposit_yield':.018,'debt_rate':.04,'loan_rate':.03,'loan_limit_additional':500.,'external_limit':320.,'equity_support_limit':250.,
 'payout5':.45,'special_start':3,
 'new_shares':[.84864,.84864,1.13152,0.,0.], 'initial_shares':312.042673, 'sbc_path':[25.,14.,5.76330317,0.,0.], 'conversion_year':0,'conversion_limit':0.,'grant_price':31.06,
 'book0':2290.14471334,'discount_low':.11,'discount_high':.10,
 'margin_shock':0.,'shock_start':1,'cash_parent_shift':0.,'maturity_haircut':0.,
 'name':'base','notes':'经营路径相同；核心两端只变股权成本。研究预算，不是公司承诺。'
}
NAMES=['深圳市盛弘电气股份有限公司','惠州盛弘电气有限公司','苏州盛弘技术有限公司','深圳市盛弘新能源设备有限公司','西安盛弘电气有限公司','陕西盛弘电气有限公司','深圳市盛弘艾苏娜能源科技有限公司']

def annual_business(p,y,rev,wc,fixed):
    if y<=5:
        growth=p['growth5'][y-1]; gross=p['gross5'][y-1]; opex=p['opex5'][y-1]
    else:
        a=min((y-5)/(p['fade_end']-5),1.)
        growth=[v+(p['long_g']-v)*a for v in p['growth5'][-1]]
        gross=[v+(m-v)*a for v,m in zip(p['gross5'][-1],p['gross_mature'])]
        opex=p['opex5'][-1]+(p['opex_mature']-p['opex5'][-1])*a
    gross=[g+(p['margin_shock'] if y>=p['shock_start'] else 0.) for g in gross]
    newrev=[a*(1+b) for a,b in zip(rev,growth)]; sales=sum(newrev)
    gp=sum(a*b for a,b in zip(newrev,gross)); ebit_before_sbc=gp-sales*opex
    sbc=p.get('sbc_path',[0.]*5)[y-1] if y<=5 else 0.
    ebit=ebit_before_sbc-sbc
    nopat=(ebit_before_sbc*(1-p['tax']) if ebit_before_sbc>0 else ebit_before_sbc)-sbc # no cash tax credit for a loss
    newwc=sales*p['wc_ratio']; da=sales*p['depreciation_ratio']
    # Stable growth supports the same fixed asset intensity, no unsupported capex discount.
    if y<=5: capex=sales*p['capex_ratio']+p['committed_capex'][y-1]
    else: capex=da+max(sales-sum(rev),0)*p['fixed_terminal_ratio']
    newfixed=fixed+capex-da
    return dict(revenue=newrev,sales=sales,growth=growth,gross_margins=gross,gross_profit=gp,opex=sales*opex,
       ebit=ebit,nopat=nopat,wc=newwc,delta_wc=newwc-wc,da=da,capex=capex,fixed=newfixed,
       sbc=sbc,fcf=nopat+sbc+da-capex-(newwc-wc),reinvestment=capex-da+newwc-wc)

def legal_add(balance,reserve,capital,profit):
    before=balance; balance+=profit
    provision=min(max(balance-max(before,0.),0.)*.10,max(capital*.5-reserve,0.))
    return balance-provision,reserve+provision,provision

def payment(cash,legal,reserve,capital,profit,floor,target):
    """Shared actual payment gate; used by both live simulation and hand cases."""
    legal,reserve,appropriation=legal_add(legal,reserve,capital,profit)
    paid=min(max(target,0.),max(legal,0.),max(cash-floor,0.))
    return cash-paid,legal-paid,reserve,paid,appropriation

def simulate(p,horizon=240):
    p=copy.deepcopy(p); rev=p['revenue0'][:];wc=p['wc0'];fixed=p['fixed0'];cash=p['cash0'][:]
    cash[0]-=p['cash_parent_shift']; cash[1]+=p['cash_parent_shift']
    term=p['term0'][:];debt=p['debt0'][:];legal=p['legal0'][:];reserve=p['reserve0'][:];capital=p['capital0'][:]
    loan=p['loan0'][:];pending=[0.]*6;shares=p['initial_shares'];book=p['book0'];rows=[]
    added_loans=0.;equity_support=0.;borrowed=0.;cumulative_dps=0.; p['fixed_terminal_ratio']=.20
    def move(i,j,a):
        assert a>=-1e-7
        cash[i]-=a;cash[j]+=a
    for y in range(1,horizon+1):
        before_cash=sum(cash)+sum(term);prevbook=book;prevshares=shares;prev_legal=legal[:];prev_reserve=reserve[:]
        b=annual_business(p,y,rev,wc,fixed);rev=b['revenue'];wc=b['wc'];fixed=b['fixed'];sales=b['sales']
        if y==5: p['fixed_terminal_ratio']=fixed/sales
        floors=[sales*p['cash_floor_ratio']*w for w in p['cash_floor_weights']]
        conversion=[0.]*6
        if y==p['conversion_year']:
            remaining=p['conversion_limit']
            for i in [5,2,3,1,4]:
                cv=min(remaining,loan[i-1]);loan[i-1]-=cv;capital[i]+=cv;conversion[i-1]=cv;remaining-=cv
        fin=[(cash[i]+term[i])*p['deposit_yield']*(1-p['tax']) for i in range(7)]
        extint=[d*p['debt_rate']*(1-p['tax']) for d in debt]
        lp=[l*p['loan_rate'] for l in loan]
        sw=p['subs_profit5'][y-1] if y<=5 else p['subs_profit_mature']
        op_profit=[b['nopat']*(1-sum(sw))]+[b['nopat']*w for w in sw]
        profits=[op_profit[i]+fin[i]-extint[i] for i in range(7)]
        internal_parent_tax=sum(lp)*p['tax']
        internal_sub_shield=[min(lp[i-1],max(op_profit[i]+fin[i]-extint[i],0.)/(1-p['tax']))*p['tax'] if legal[i]>=0. else 0. for i in range(1,7)]
        internal_tax=internal_parent_tax-sum(internal_sub_shield)
        profits[0]+=sum(lp)-internal_parent_tax
        for i in range(1,7): profits[i]-=lp[i-1]-internal_sub_shield[i-1]
        # Parent pays cash tax on gross internal interest. Subs with accumulated
        # statutory losses get no immediate interest shield; no historic tax-loss
        # asset is monetized. Positive units get only a current-income-limited shield.
        a=min(max((y-5)/(p['capital_allocation_fade_end']-5),0.),1.)
        mature_weights=[1-sum(p['subs_profit_mature'])]+p['subs_profit_mature']
        investment_weights=[w*(1-a)+z*a for w,z in zip(p['reinvest_weights'],mature_weights)]
        for i in range(7): cash[i]+=op_profit[i]-b['reinvestment']*investment_weights[i]+fin[i]-extint[i]
        cash[0]+=b['sbc']-internal_parent_tax
        for i in range(1,7):cash[i]+=internal_sub_shield[i-1]
        received=pending[:]
        # Declared last year, received this year; do not book new parent legal income.
        for i in range(1,7): move(i,0,received[i-1])
        pending=[0.]*6
        matured=[0.]*7; impairment=0.
        if y==p['maturity_year']:
            for i in range(7):
                matured[i]=term[i]*(1-p['maturity_haircut']); impairment+=term[i]*p['maturity_haircut']
                profits[i]-=term[i]*p['maturity_haircut'];cash[i]+=matured[i];term[i]=0.
        # Known initial debt amortizes in Y1; any capped contingency borrowing paid in Y2/3.
        principal=[debt[i] if y in (1,3) else 0. for i in range(7)]
        lease=p['lease0'] if y==1 else 0.;cash[0]-=lease
        performance_proxy=576. if y==1 else (rows[-1]['common_profit']+rows[-1]['sbc'] if rows else 0.)
        targets=[561.62,673.94,808.73];triggers=[514.82,566.30,622.93]
        vest=(1. if performance_proxy>=targets[y-1] else .6 if performance_proxy>=triggers[y-1] else 0.) if y<=3 else 0.
        issue=p['new_shares'][y-1]*vest if y<=5 else 0.
        issue_price=max(p['grant_price']-cumulative_dps,0.)
        proceeds=issue*issue_price;shares+=issue;capital[0]+=issue;cash[0]+=proceeds
        # All subsidiaries must cover operating liquidity, internal interest and due debt
        # before declaring new cash. Support is a named loan, never unidentified cash.
        support=[0.]*6;equity_injections=[0.]*6;repaid=[0.]*6;external=[0.]*7
        for i in range(1,7):
            need=max(floors[i]+principal[i]+lp[i-1]-cash[i],0.)
            # Bridge against disclosed deposits is capped, explicitly costly, and
            # remains debt until cash repayment. No unlimited credit plug.
            parent_gap=max(need+floors[0]+principal[0]-cash[0],0.)
            draw=min(parent_gap,max(p['external_limit']-borrowed,0.))
            cash[0]+=draw;debt[0]+=draw;borrowed+=draw;external[0]+=draw
            capacity=max(min(sum(p['loan0'])+p['loan_limit_additional']-sum(loan),cash[0]-floors[0]-principal[0]),0.)
            lend=min(need,capacity);move(0,i,lend);loan[i-1]+=lend;support[i-1]=lend;added_loans+=lend
            remaining=max(floors[i]+principal[i]+lp[i-1]-cash[i],0.)
            eq=min(remaining,max(p['equity_support_limit']-equity_support,0.),max(cash[0]-floors[0]-principal[0],0.)) if p['ownership'][i]==1 else 0.
            move(0,i,eq);capital[i]+=eq;equity_support+=eq;equity_injections[i-1]=eq
            if cash[i]+1e-7<floors[i]+principal[i]+lp[i-1]:
                return dict(feasible=False,failure_year=y,failure_entity=NAMES[i],failure='zero-dividend funding deficit',rows=rows,inputs=p,failed_state={'cash':cash[:],'legal':legal[:],'debt':debt[:],'loans':loan[:],'capital':capital[:],'business':b},unfunded=floors[i]+principal[i]+lp[i-1]-cash[i])
            move(i,0,lp[i-1])
        for i in range(7):
            need=max(floors[i]+principal[i]-cash[i],0.)
            avail=max(p['external_limit']-borrowed,0.) if i==0 else 0.
            draw=min(need,avail);cash[i]+=draw;debt[i]+=draw;borrowed+=draw;external[i]+=draw
            if cash[i]+1e-7<floors[i]+principal[i]:
                return dict(feasible=False,failure_year=y,failure_entity=NAMES[i],failure='zero-dividend funding deficit',rows=rows,inputs=p,failed_state={'cash':cash[:],'legal':legal[:],'debt':debt[:],'loans':loan[:],'capital':capital[:],'business':b},unfunded=floors[i]+principal[i]-cash[i])
            cash[i]-=principal[i];debt[i]-=principal[i]
        # Repay pre-existing shareholder loans before distributing profits; never a new
        # parent profit. Some major balances represent operating advances; budget settlement
        # is limited by each debtor's available cash, not legal consolidation set-off.
        for i in range(1,7):
            a=min(max(cash[i]-floors[i],0.),loan[i-1]);move(i,0,a);loan[i-1]-=a;repaid[i-1]=a
        provision=[0.]*7
        for i in range(7): legal[i],reserve[i],provision[i]=legal_add(legal[i],reserve[i],capital[i],profits[i])
        declared=[0.]*6;minority_paid=0.
        for i in range(1,7):
            # A full-year dividend delay is an explicit budget. Reserve the declaration
            # in cash, and do not count it as parent receipt until next annual step.
            a=min(max(legal[i],0.),max(cash[i]-floors[i],0.))
            if y<=5: a*=.45
            parent_part=a*p['ownership'][i]; minority=a-parent_part
            cash[i]-=minority;minority_paid+=minority;legal[i]-=a
            declared[i-1]=parent_part;pending[i-1]=parent_part
        # Parent records declared investment income now, before receipt next year.
        legal[0],reserve[0],extra=legal_add(legal[0],reserve[0],capital[0],sum(declared));provision[0]+=extra
        totalprofit=sum(profits);minority_profit=profits[-1]*.5
        common_profit=totalprofit-minority_profit
        ordinary_target=max(common_profit,0.)*(p['payout5'] if y<=5 else 1.)
        # Ordinary distribution consumes legal profit first. The subsequent sweep is
        # actual cash, subject to remaining statutory earnings, liquidity and debt.
        cash[0],legal[0],reserve[0],ordinary,_=payment(cash[0],legal[0],reserve[0],capital[0],0.,floors[0],ordinary_target)
        special=0.
        if y>=p['special_start']:
            # During first 5 years only matured original deposits are released; after 5
            # all genuinely redundant cash can be returned. No parallel cash add-back.
            target=sum(matured) if y<=5 else max(cash[0]-floors[0],0.)
            special=min(target,max(legal[0],0.),max(cash[0]-floors[0],0.));cash[0]-=special;legal[0]-=special
        paid=ordinary+special;dps=paid/shares;cumulative_dps+=dps
        book=prevbook+common_profit+b['sbc']+proceeds-paid
        expected=before_cash+b['fcf']+sum(fin)-sum(extint)-impairment-internal_tax+proceeds+sum(external)-sum(principal)-lease-paid-minority_paid
        error=sum(cash)+sum(term)-expected
        assert abs(error)<1e-6*max(1,sales/10000),error
        assert min(cash+term+debt+loan)>=-1e-6
        assert all(cash[i]+1e-6>=floors[i]+(pending[i-1] if i else 0.) for i in range(7))
        assert all(reserve[i]>=prev_reserve[i]-1e-8 for i in range(7))
        rows.append(dict(year=y,**b,common_profit=common_profit,group_profit=totalprofit,
          entity_operating_profits=op_profit,reinvestment_weights=investment_weights,entity_statutory_own_profits=profits,cash=cash[:],deposits=term[:],
          deposit_income=fin,deposit_matured=matured,debt=debt[:],external_interest=extint,
          capital=capital[:],legal=legal[:],reserve=reserve[:],reserve_provision=provision,liquidity_floors=floors,
          parent_dividend_receivable=pending[:],subs_declared=declared,subs_cash_received=received,
          internal_loans=loan[:],internal_loan_interest=lp,internal_interest_parent_cash_tax=internal_parent_tax,internal_interest_sub_cash_tax_shield=internal_sub_shield,internal_support=support,internal_equity_injections=equity_injections,internal_debt_to_equity=conversion,internal_repayment=repaid,
          external_draw=external,debt_principal=principal,lease_principal=lease,minority_profit=minority_profit,
          minority_paid=minority_paid,ordinary=ordinary,special=special,distribution=paid,distribution_per_share=dps,
          shares=shares,new_shares=issue,vesting_fraction=vest,performance_proxy=performance_proxy,issue_price=issue_price,issue_proceeds=proceeds,common_book=book,
          book_per_share=book/shares,opening_book_per_share=prevbook/prevshares,cash_identity_error=error))
    return dict(feasible=True,rows=rows,inputs=p,entities=NAMES,excluded_minor_cash=p['excluded_minor_cash'],
       omitted_cash_note='小主体现金22.506百万元不任意上划；零计价至面值上界约0.071元/股，不影响核心取整。',
       shareholder_support_used=added_loans,equity_support_used=equity_support,external_draw_total=borrowed)

def prepare_award_budget(p):
    p=copy.deepcopy(p)
    if sum(p['new_shares'])==0:
        p['sbc_path']=[-15.67174636,0.,0.,0.,0.]
        p['award_note']='全部失效，冲回截至Q3约15.672百万元已认费用；不是额外现金收益。'
        return p
    for _ in range(6):
        trial=simulate(p,5)
        if not trial['feasible']:return p
        vest=[a['vesting_fraction'] for a in trial['rows'][:3]]
        total=60.43504953*sum(a*b for a,b in zip([.3,.3,.4],vest))
        remaining=total-15.67174636
        shape=[25.,14.,5.76330317]
        target=[remaining*w/sum(shape) for w in shape]+[0.,0.]
        if max(abs(a-b) for a,b in zip(p['sbc_path'],target))<1e-10:break
        p['sbc_path']=target
    p['award_note']='预期归属比例决定最终股份费用总额；扣已确认部分后分摊未来费用，未达标份额不持续保留全部费用。'
    p['expected_vesting']=vest;p['expected_total_award_cost']=total
    return p

def value(run,r):
    if not run['feasible']: return None
    rows=run['rows'];dpv=sum(a['distribution_per_share']/(1+r)**a['year'] for a in rows)
    tv=sum(a['distribution_per_share']/(1+r)**(a['year']-5) for a in rows if a['year']>5)
    near=sum(a['distribution_per_share']/(1+r)**a['year'] for a in rows[:5])
    ri=run['inputs']['book0']/run['inputs']['initial_shares']
    residual_rows=[]
    for a in rows:
        residual=a['book_per_share']-a['opening_book_per_share']+a['distribution_per_share']-r*a['opening_book_per_share']
        ri+=residual/(1+r)**a['year'];residual_rows.append(residual)
    terminal_book=rows[-1]['book_per_share']/(1+r)**rows[-1]['year']
    assert abs(ri-terminal_book-dpv)<1e-8
    tail_bound=abs(rows[-1]['distribution_per_share'])*(1.02)/(r-.02)/(1+r)**rows[-1]['year']
    return dict(discount=r,per_share=dpv,year5_terminal_per_share=tv,first5_pv=near,
       terminal_pv_fraction=(dpv-near)/dpv,residual_income_value=ri,
       residual_income_per_year=residual_rows,terminal_book_pv=terminal_book,tail_upper_diagnostic=tail_bound)

def configs():
    d={'base':copy.deepcopy(P)}
    q=copy.deepcopy(P);q.update(name='cyclical_weak',notes='Y1-2库存/项目延迟，Y3开始恢复，Y5仍低于基准。',wc_ratio=.18)
    q['growth5']=[[-.05,-.15,-.08,-.12,0.],[.05,.05,.03,0.,.02],[.20,.20,.14,.08,.04],[.14,.14,.10,.06,.03],[.11,.11,.08,.05,.03]]
    q['gross5']=[[g-.03 for g in row] if j<2 else row for j,row in enumerate(q['gross5'])];q['committed_capex']=[80.,40.,0.,0.,0.];d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='structural_adverse',notes='Y1起充电/PCS永久商品化，工业接口优势减弱，无自动均值回归。',wc_ratio=.20,opex_mature=.235,conversion_year=3,conversion_limit=250.)
    q['growth5']=[[.08,.02,.02,-.05,.02],[.06,.02,.02,0.,.02],[.05,.02,.02,.02,.02],[.04,.02,.02,.02,.02],[.03,.02,.02,.02,.02]]
    q['gross5']=[[.51,.25,.23,.27,.28]]*5;q['gross_mature']=[.47,.23,.22,.26,.27];q['opex5']=[.245,.242,.24,.238,.235];q['capex_ratio']=.03;d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='optimistic',notes='Y1起工业/海外份额提升，仍保留资本和远期竞争衰减。',wc_ratio=.15)
    q['growth5']=[[g+.04 for g in a] for a in q['growth5']];q['gross5']=[[a[0]+.01,a[1]+.02,*a[2:]] for a in q['gross5']];q['committed_capex']=[120.,60.,20.,0.,0.];d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='margin_minus_2pp',margin_shock=-.02,shock_start=2,notes='Y2起所有分部毛利率永久减2点，其余商业假设冻结；整链诊断敏感性。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='wc_plus_5pp',wc_ratio=.19,notes='Y1起净营运资本占收入永久+5点；经营/资金/分配全链重算。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='deposit_delay',maturity_year=5,notes='原定Y3本金释放延后至Y5，期间利息和现金/法定利润继续滚动。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='parent_cash_shift',cash_parent_shift=100.,notes='初始母公司现金少1亿元，改放惠州；同一集团现金，资金必须通过还款或宣派到账。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='no_exercise',new_shares=[0.]*5,sbc_path=[0.]*5,notes='Y1起激励全部失效：无认款无新增股份，未归属费用不再承担；经营费用其他部分不变。');d[q['name']]=q
    q=copy.deepcopy(P);q.update(name='funding_failure',wc_ratio=.75,external_limit=0.,loan_limit_additional=0.,equity_support_limit=0.,notes='Y1极端回款冻结：即使零分配仍现金不足，必须不可行且不输出价值。');d[q['name']]=q
    return d

def earnings_power_crosscheck(base):
    # Economic alternative, not a different multiple applied to an unfunded tail.
    # Same end-Y5 state, then immediate 2% growth and mature segment economics.
    p=copy.deepcopy(base['inputs']);p.update(name='earnings_power_crosscheck',fade_end=6,capital_allocation_fade_end=6,
       gross_mature=[.52,.29,.26,.29,.29],opex_mature=.23,
       notes='第二法：第6年立即成熟，工业52/PCS29/充电26/检测29/其他29%毛利，2%增长；按必要再投资资本化盈利能力，法律和金融过渡用同一实际支付预算桥接。')
    run=simulate(p);assert run['feasible']
    for k in ['cash','legal','reserve','debt','shares','common_book','revenue','fixed','wc']:
        assert run['rows'][4][k]==base['rows'][4][k]
    s5,s6=run['rows'][4:6];shares=s6['shares'];ownership=p['ownership']
    capacity=sum((s6['entity_operating_profits'][i]-s6['reinvestment']*s6['reinvestment_weights'][i]
       -(s6['liquidity_floors'][i]-s5['liquidity_floors'][i])
       +s5['liquidity_floors'][i]*p['deposit_yield']*(1-p['tax']))*ownership[i] for i in range(7))/shares
    run['earnings_power_capacity_per_share']=capacity;run['method_results']={}
    for label,r in [('low',.11),('high',.10)]:
        operating=capacity/(r-p['long_g'])
        bridge=sum((a['distribution_per_share']-capacity*(1+p['long_g'])**(a['year']-6))/(1+r)**(a['year']-5) for a in run['rows'][5:])
        first=sum(a['distribution_per_share']/(1+r)**a['year'] for a in run['rows'][:5])
        result=first+(operating+bridge)/(1+r)**5
        direct=value(run,r)['per_share']
        assert abs(result-direct)<.00001
        run['method_results'][label]={'normalised_operating_capitalisation_at_y5':operating,
          'actual_legal_financial_bridge_at_y5':bridge,'per_share':result,'year5_terminal':operating+bridge,
          'normalised_nopat_y6':s6['nopat'],'necessary_reinvestment_y6':s6['reinvestment'],
          'liquidity_increment_y6':sum(s6['liquidity_floors'])-sum(s5['liquidity_floors']),
          'first5_pv':first,'full_budget_check':direct}
    return run

def self_tests():
    # Real payment gate: cash12, legal-3, profit10, reserve0, capital10: loss absorbed,
    # reserve .7, legal6.3; liquidity floor2, target20 => dividend6.3, cash5.7.
    a=payment(12.,-3.,0.,10.,10.,2.,20.)
    assert all(abs(x-y)<1e-10 for x,y in zip(a,[5.7,0.,.7,6.3,.7]))
    # Ordinary cash consumes profits; principal cannot reuse same 6.3 statutory budget.
    b=payment(a[0]+100,a[1],a[2],10.,0.,2.,100.)
    assert b[3]==0. and b[0]==105.7
    c=payment(10.,-20.,0.,10.,5.,0.,10.);assert c[3]==0. and c[1]==-15.
    # Same business function, manually: sales100, 20% gross, opex10%, tax0,
    # da2, capex3, no growth/working capital change => profit10, FCF9.
    p=copy.deepcopy(P);p.update(growth5=[[0.]*5]*5,gross5=[[.2]*5]*5,opex5=[.1]*5,tax=0.,wc_ratio=.1,
       depreciation_ratio=.02,capex_ratio=.03,committed_capex=[0.]*5,sbc_path=[0.]*5)
    z=annual_business(p,1,[100.,0.,0.,0.,0.],10.,20.)
    assert z['nopat']==10. and z['fcf']==9.
    p.update(revenue0=[100.,0.,0.,0.,0.],cash0=[10.]+[0.]*6,term0=[0.]*7,debt0=[0.]*7,lease0=0.,legal0=[100.]+[0.]*6,reserve0=[1.]+[0.]*6,capital0=[2.]+[0.]*6,loan0=[0.]*6,cash_floor_ratio=0.,deposit_yield=0.,new_shares=[0.]*5,subs_profit5=[[0.]*6]*5,subs_profit_mature=[0.]*6,reinvest_weights=[1.]+[0.]*6,wc0=10.,fixed0=20.,payout5=.5,special_start=99)
    trial=simulate(p,1);row=trial['rows'][0]
    assert trial['feasible'] and abs(row['distribution']-5.)<1e-9 and abs(row['cash'][0]-14.)<1e-9 and abs(row['legal'][0]-105.)<1e-9
    taxcase=copy.deepcopy(p);taxcase.update(gross5=[[.1]*5]*5,capex_ratio=0.,depreciation_ratio=0.,cash0=[10.,1.,0.,0.,0.,0.,0.],loan0=[10.,0.,0.,0.,0.,0.],legal0=[100.,-2.,0.,0.,0.,0.,0.],tax=.15,loan_rate=.03)
    taxrow=simulate(taxcase,1)['rows'][0]
    assert abs(taxrow['internal_interest_parent_cash_tax']-.045)<1e-12
    assert sum(taxrow['internal_interest_sub_cash_tax_shield'])==0.
    assert abs(sum(taxrow['cash'])-10.955)<1e-9
    return {'internal_interest_cash_tax_hand_case':{'parent_cash_tax':taxrow['internal_interest_parent_cash_tax'],'subs_shield':sum(taxrow['internal_interest_sub_cash_tax_shield']),'ending_group_cash':sum(taxrow['cash'])},'full_simulator_hand_case':{'distribution':row['distribution'],'cash':row['cash'][0],'legal':row['legal'][0]},'payment_gate_hand_case':list(a),'no_double_legal_principal':b[3],'loss_carry':c[1],'business_hand_case_fcf':z['fcf']}

def main():
    out={'symbol':'CN:300693','period':'2026-Q3','as_of':'2026-10-26','unit':'CNY million; shares million; per-share CNY',
       'entity_parameters_are_budgets_not_disclosed_Q3_legal_accounts':True,'tests':self_tests(),'scenarios':{}}
    for name,p in configs().items():
        p=prepare_award_budget(p);run=simulate(p);run['low']=value(run,p['discount_low']);run['high']=value(run,p['discount_high']);out['scenarios'][name]=run
    base=out['scenarios']['base'];assert base['feasible']
    out['earnings_power_crosscheck']=earnings_power_crosscheck(base)
    longer=simulate(prepare_award_budget(P),320);out['convergence']={}
    for r in [.10,.11]:
        a=value(base,r);b=value(longer,r);out['convergence'][str(r)]={'horizon240':a['per_share'],'horizon320':b['per_share'],'difference':b['per_share']-a['per_share']}
        assert abs(b['per_share']-a['per_share'])<.00001
    assert not out['scenarios']['funding_failure']['feasible']
    out['value_range']={'low':round(base['low']['per_share'],2),'high':round(base['high']['per_share'],2),'currency':'CNY'}
    out['return_model']={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY','model_as_of':'2026-10-26T09:30:00+00:00',
       'base_case_distributions_per_share':[round(x['distribution_per_share'],6) for x in base['rows'][:5]],
       'base_case_terminal_equity_value_range_per_share':{'year_5':{'low':round(base['low']['year5_terminal_per_share'],6),'high':round(base['high']['year5_terminal_per_share'],6)}}}
    path=Path(__file__).with_name('2026-Q3-output.json');path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'value_range':out['value_range'],'return_model':out['return_model'],'scenarios':{k:{'feasible':v['feasible'],'value':v['low']['per_share'] if v['low'] else None,'failure':v.get('failure')} for k,v in out['scenarios'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
