'CN600570 ordinary offline research model. Pure standard library; billion CNY / billion shares. No network, trading or coordinator permission ticket.'
import copy,json,math,pathlib,hashlib,datetime
ROOT=pathlib.Path(__file__).resolve().parent

def pv(flows,terminal_cash,rate,growth,start=0):
    """Value at start year, all flows paid at year ends; terminal after last flow."""
    if rate<=growth: raise ValueError('non-finite terminal')
    n=len(flows); terminal=terminal_cash/(rate-growth)
    explicit=sum(x/(1+rate)**(i+1-start) for i,x in enumerate(flows) if i+1>start)
    tvpv=terminal/(1+rate)**(n-start)
    return {'value':explicit+tvpv,'explicit_pv':explicit,'terminal_pv':tvpv,'terminal_undiscounted':terminal,'terminal_share':tvpv/(explicit+tvpv) if explicit+tvpv else None}

def opening_k(o):
    return sum(o['operating_assets'])-sum(o['operating_liabilities'])+o['operating_liabilities_capital_payable_exclusion']+o['operating_liabilities_cash_award_exclusion']+o['operating_cash_reserve']

def software(cfg,opening,history):
    rev0=history['revenue_2025']-history['revenue_9m25']+history['revenue_9m26']
    rprev=rev0;k=opening_k(opening);reserve=opening['operating_cash_reserve'];out=[]
    arrays=[]
    for s in cfg['segments']:
        rs=list(s['revenues']);ms=list(s['ebit_margins'])
        for j,g in enumerate(s['later_growth']):
            rs.append(rs[-1]*(1+g));ms.append(s['ebit_margins'][-1]+(s['mature_margin']-s['ebit_margins'][-1])*(j+1)/5)
        rs.append(rs[-1]*(1+cfg['terminal_growth']));ms.append(s['mature_margin']);arrays.append((s,rs,ms))
    for i in range(11):
        seg=[]
        for s,rs,ms in arrays:
            ebit=rs[i]*ms[i];tax=max(ebit,0)*s['tax'];seg.append({'name':s['name'],'revenue':rs[i],'ebit':ebit,'cash_tax':tax,'nopat':ebit-tax})
        rev=sum(x['revenue'] for x in seg);economic_np=sum(x['nopat'] for x in seg)
        legacy=(cfg['legacy_equity_sbc'][i] if i<10 else 0)*(1-cfg['legacy_sbc_tax_rate']);np=economic_np-legacy
        delta=rev-rprev;growth=max(delta,0)*cfg['growth_capital_ratio']
        wc=delta*cfg['growth_wc_ratio']*(1 if delta>=0 else cfg['negative_wc_recovery'])
        wc+=cfg['extra_wc'][i] if i<10 else 0
        project=cfg['project_capex'][i] if i<10 else 0
        restructuring=cfg['restructuring_costs'][i] if i<10 else 0
        maintenance=cfg['maintenance_capex_start']*rev/rev0;depreciation=maintenance
        newreserve=cfg['cash_reserve_ratio']*rev;reserve_delta=newreserve-reserve
        cash_fcf=np+legacy+depreciation-maintenance-growth-wc-project-restructuring
        fcff=cash_fcf-reserve_delta;k+=growth+wc+project+reserve_delta
        out.append({'year':i+1,'segments':seg,'revenue':rev,'nopat':np,'economic_nopat_before_legacy_sbc':economic_np,'legacy_sbc_net_addback':legacy,'maintenance':maintenance,'depreciation':depreciation,'growth_capex':growth,'project_capex':project,'delta_wc':wc,'restructuring':restructuring,'cash_reserve':newreserve,'delta_reserve':reserve_delta,'cash_fcf':cash_fcf,'fcff':fcff,'operating_capital_end':k,'nopat_to_end_capital':np/k if k>0 else None})
        rprev=rev;reserve=newreserve
    return out

def statutory_reserve(profit,legal_before,stat,registered,policy):
    """Equity reclassification only. Recover prior losses before a positive reserve base."""
    base=max(0,min(max(profit,0),legal_before+profit))
    if policy=='continue_ten_percent':return base*.10
    if policy=='stop_when_half':return min(max(.5*registered-stat,0),base*.10)
    raise ValueError('Unknown statutory reserve governance policy')

def ant_policy(cfg,year):
    review=cfg.get('ant_continue_through_year')
    return 'stop_when_half' if review is not None and year>review else cfg['ant_reserve_policy']

def ant_tail_state(cfg,opening,row):
    """A proven legal/capital regime, not an empirical long-range business forecast."""
    if row['exit_proceeds_to_owner']>0:return {'kind':'sale_completed','cash_tail':0}
    if cfg.get('ant_permanent_no_cash_rights',False):return {'kind':'no_distribution_no_exit','cash_tail':0}
    if cfg.get('ant_exit_year') is not None:return None
    end=max(10,cfg['ant_release_start']+cfg['ant_release_years']-1,cfg.get('ant_continue_through_year') or 0)
    if row['year']<end:return None
    E=row['equity_end'];R=row['revenue'];K=row['required_capital'];L=row['legal_retained_end'];S=row['statutory_reserve'];registered=opening['ant_registered_capital']
    g=cfg['terminal_growth'];y=cfg['ant_idle_yield'];alpha=cfg['ant_capital_ratio'];m=cfg['ant_margins'][-1]
    if g<0 or E<K-1e-9 or E<registered+S-1e-9 or L<-1e-9:return None
    policy=ant_policy(cfg,row['year']+1)
    if policy=='stop_when_half' and S>=.5*registered-1e-9:
        return {'kind':'reserve_stopped_fixed_idle_capital','growth_cash_coefficient':(m*(1+g)-alpha*g)*R,'constant_cash':y*max(E-K,0),'growth':g,'idle_capital':max(E-K,0),'retained_principal_exit_assumed':False}
    if policy=='continue_ten_percent' and abs(L)<1e-8:
        q=.1;A=m*(1+g)-y*alpha;ratio=E/R if R else 0
        if A<0:return None
        minratio=min(ratio,q*A/(g-q*y)) if g>q*y else ratio
        # With these inequalities the legal pool remains binding and operating capital is funded.
        if minratio<alpha-1e-9 or q*(y*minratio+A)<alpha*g-1e-9 or E-S<registered-1e-9:return None
        return {'kind':'continuing_reserve_legal_pool_binding','equity':E,'revenue':R,'reserve_rate':q,'idle_yield':y,'A':A,'growth':g,'minimum_future_equity_to_revenue':minratio,'retained_principal_exit_assumed':False}
    if policy=='continue_ten_percent' and L>1e-8 and m*(1+g)-alpha*g>=0 and E-L-S>=registered-1e-9:
        return {'kind':'continuing_reserve_before_legal_binding','equity':E,'revenue':R,'legal_retained':L,'statutory_reserve':S,'registered_capital':registered,'operating_capital_ratio':alpha,'margin':m,'reserve_rate':.1,'idle_yield':y,'growth':g,'retained_principal_exit_assumed':False}
    return None

def ant(cfg,opening):
    eq=opening['ant_equity_estimate'];out=[];release_annual=None
    legal=opening['ant_initial_legal_retained_assumption'];stat=opening['ant_initial_legal_reserve_assumption'];registered=opening['ant_registered_capital']
    if stat<0 or eq-legal-stat<registered-1e-9:raise ValueError('Ant opening legal/capital classification inconsistent')
    initial_req=cfg['ant_capital_ratio']*cfg['ant_revenues'][0]
    # Ten economic budget years, then only legal/capital transition to an auditable tail.
    # A finite guard rejects an unproved tail; it is not a 30-year operating precision claim.
    for i in range(30):
        y=i+1;rev=cfg['ant_revenues'][i] if i<10 else cfg['ant_revenues'][-1]*(1+cfg['terminal_growth'])**(i-9)
        margin=cfg['ant_margins'][i] if i<10 else cfg['ant_margins'][-1]
        required=rev*cfg['ant_capital_ratio'];oldreq=initial_req if i==0 else out[-1]['required_capital']
        excess=max(eq-oldreq,0);op_profit=rev*margin;idle_profit=excess*cfg['ant_idle_yield'];profit=op_profit+idle_profit
        beginning=eq;legal_begin=legal;policy=ant_policy(cfg,y)
        reserve_add=statutory_reserve(profit,legal,stat,registered,policy);stat+=reserve_add;legal+=profit-reserve_add
        pre=eq+profit;call=max(required-pre,0);pre+=call
        if y==cfg['ant_release_start']:release_annual=max(eq-oldreq,0)/cfg['ant_release_years']
        if y<cfg['ant_release_start'] or cfg.get('ant_permanent_no_cash_rights',False) or cfg.get('ant_no_dividends_before_exit',False):dividend=0
        else:
            recurring=max(profit-(required-oldreq),0)
            release=release_annual if y<cfg['ant_release_start']+cfg['ant_release_years'] else 0
            dividend=min(max(pre-max(required,registered+stat),0),max(legal,0),recurring+(release or 0))
        eq=pre-dividend;legal-=dividend
        sale=.241*eq*cfg.get('ant_exit_equity_ratio',0) if cfg.get('ant_exit_year')==y else 0
        row={'year':y,'revenue':rev,'margin':margin,'operating_profit':op_profit,'idle_profit':idle_profit,'profit':profit,'equity_begin':beginning,'legal_retained_begin':legal_begin,'legal_retained_end':legal,'statutory_reserve':stat,'reserve_add':reserve_add,'reserve_policy_applied':policy,'required_capital':required,'capital_call':call,'dividend':dividend,'equity_end':eq,'idle_equity_end':max(eq-required,0),'exit_proceeds_to_owner':sale,'share_cash':.241*(dividend-call)+sale}
        out.append(row);tail=ant_tail_state(cfg,opening,row)
        if tail is not None and (y>=10 or cfg.get('ant_exit_year')==y):
            row['tail_state']=tail;return out
    raise ValueError('Ant legal/capital tail not established within finite transition budget; no adopted terminal')

def ant_tail_cash_value(state,rate):
    """Exact cash tail of stated steady economics/policy; not evidence they will persist."""
    kind=state['kind']
    if kind in ['sale_completed','no_distribution_no_exit']:return 0
    if kind=='reserve_stopped_fixed_idle_capital':
        if rate<=state['growth']:raise ValueError('Non-finite Ant cash tail')
        return .241*(state['growth_cash_coefficient']/(rate-state['growth'])+state['constant_cash']/rate)
    q=state['reserve_rate'];y=state['idle_yield'];g=state['growth'];E=state['equity'];R=state['revenue']
    if rate<=max(g,q*y):raise ValueError('Non-finite Ant legal tail')
    if kind=='continuing_reserve_legal_pool_binding':
        A=state['A']
        # Bellman coefficients retain both the operating and idle-capital income streams.
        return .241*(1-q)*(y*E/(rate-q*y)+A*R*rate/((rate-q*y)*(rate-g)))
    if kind!='continuing_reserve_before_legal_binding':raise ValueError('Unproved Ant tail')
    alpha=state['operating_capital_ratio'];m=state['margin'];L=state['legal_retained'];S=state['statutory_reserve'];X=max(E-alpha*R,0);b=1+g
    # Until the legal pool binds, E=alpha*R+fixed X; reserve reclassification is not cash loss.
    if g==0:
        loss=q*(m*R+y*X)
        legal=lambda n:L-loss*n
        upper=math.ceil(L/loss) if loss>0 else None
    else:
        B=R*(alpha-q*m*b/g);linear=q*y*X
        legal=lambda n:L+B*math.expm1(n*math.log1p(g))-linear*n
        if B<0:upper=math.ceil(math.log1p(L/(-B))/math.log1p(g))
        elif abs(B)<1e-14:upper=math.ceil(L/linear) if linear>0 else None
        elif linear<=B*math.log1p(g):upper=None
        else:
            lowpoint=math.log(linear/(B*math.log1p(g)))/math.log1p(g)
            choices=[max(1,math.floor(lowpoint)),max(1,math.ceil(lowpoint))];upper=min(choices,key=legal)
            if legal(upper)>1e-8:upper=None
    recurring=(m*b-alpha*g)*R
    if upper is None:
        state['analytic_switch']='legal_pool_never_binds_under_stated_steady_policy'
        return .241*(recurring/(rate-g)+y*X/rate)
    upper=max(1,upper)
    if legal(upper)>1e-8:upper+=1
    low=0
    while low+1<upper:
        mid=(low+upper)//2
        if legal(mid)<=1e-8:upper=mid
        else:low=mid
    n=upper;deficit=legal(n);Rn=R*b**n;En=alpha*Rn+X-deficit;A=m*b-y*alpha
    ratio=En/Rn;minratio=min(ratio,q*A/(g-q*y)) if g>q*y else ratio
    if minratio<alpha-1e-8 or q*(y*minratio+A)<alpha*g-1e-8:raise ValueError('Analytic Ant legal transition does not establish a permanent funded regime')
    pv_recurring=recurring/(rate-g)*(1-(b/(1+rate))**n)+y*X/rate*(1-(1+rate)**(-n))
    bound={'kind':'continuing_reserve_legal_pool_binding','equity':En,'revenue':Rn,'reserve_rate':q,'idle_yield':y,'A':A,'growth':g}
    tail_at_n=ant_tail_cash_value(bound,rate)
    state.update(analytic_switch_year_offset=n,legal_pool_without_payout_reduction_at_switch=deficit,equity_after_actual_payout_at_switch=En,analytic_switch_is_not_a_forecast_date=True)
    return .241*(pv_recurring+deficit/(1+rate)**n)+tail_at_n/(1+rate)**n

def ant_value(rows,rate,start=0):
    """Discount actual owner cash, then a legally supported tail; retained assets never vanish."""
    t=rows[-1]['year'];state=copy.deepcopy(rows[-1]['tail_state']);tail=ant_tail_cash_value(state,rate)
    explicit=sum(x['share_cash']/(1+rate)**(x['year']-start) for x in rows if x['year']>start);tpv=tail/(1+rate)**(t-start)
    return {'value':explicit+tpv,'explicit_pv':explicit,'terminal_pv':tpv,'terminal_undiscounted':tail,'terminal_share':tpv/(explicit+tpv) if explicit+tpv else None,'explicit_horizon':t,'tail_state':state}

def bs_call(spot,strike,t,vol,rate):
    if t<=0 or vol<=0:return max(spot-strike*math.exp(-rate*t),0)
    d1=(math.log(spot/strike)+(rate+vol*vol/2)*t)/(vol*math.sqrt(t));d2=d1-vol*math.sqrt(t)
    nd=lambda x:0.5*(1+math.erf(x/math.sqrt(2)))
    return spot*nd(d1)-strike*math.exp(-rate*t)*nd(d2)

def financial_assets(opening,end):
    ant_book=opening['ant_equity_estimate']*.241+opening['ant_book_adjustment']
    other_assoc=opening['associate_total']-ant_book-opening['winsh_book_h1']
    other=opening['financial_noncurrent']+opening['financial_other_bonds']+other_assoc
    winsh=(opening['winsh_direct_shares']+opening['winsh_indirect_shares_estimate'])*opening['winsh_quote']
    return {'ant_book_removed':ant_book,'other_associates':other_assoc,'other_book':other,'winsh_mark':winsh,'value':other*end['other_asset_ratio']+winsh*end['winsh_ratio']-opening['financial_deferred_tax']}

def funding(cfg,o,sw,antrows):
    cash=o['group_cce_9m']-o['paid_october_dividend']+o['post_9m_known_exercise_cash']
    mother=o['parent_cash_h1']-o['paid_october_dividend']+o['post_9m_known_exercise_cash']
    legal=o['parent_retained_h1']-o['paid_october_dividend'];stat=o['parent_statutory_reserve'];shares=o['shares'];debt=o['borrowings_and_leases']
    cd=o['cd_short']+o['cd_long'];mcd=o['parent_cd_short_h1']+o['parent_cd_long_h1'];nci=o['nci_equity']-o['nci_put_overlap'];rows=[];cumdiv=0
    oldclaims=o['old_capital_payable']+o['old_cash_award']+o['old_put_obligation']+o['old_nci_dividend']
    for i in range(5):
        y=i+1;s=sw[i];a=antrows[i];cb=cash;mb=mother;ob=cb-mb;lb=legal;db=debt;sb=shares;ncib=nci
        traded=o['trading_assets']*cfg['trading_realization_ratio'] if y==1 else 0
        mtraded=o['parent_trading_h1']*cfg['parent_trading_realization_ratio'] if y==1 else 0
        redeem=cfg['group_cd_redemptions'][i]
        mredeem=(o['parent_cd_short_h1'] if y==1 else 0)+cfg['parent_cd_redemptions'][i]
        # Parent redemptions are a subset of the explicit group schedule, not additional money.
        redeem=min(cd,redeem);mredeem=min(mcd,mredeem)
        portfolio_income=(o['financial_noncurrent']+o['financial_other_bonds'])*cfg['portfolio_cash_yield_net']
        parent_portfolio_income=o['parent_financial_noncurrent_h1']*cfg['portfolio_cash_yield_net']
        interest=max(cb,0)*cfg['cash_yield']+max(cd-redeem/2,0)*cfg['cd_yield']+portfolio_income
        minterest=max(mb,0)*cfg['cash_yield']+max(mcd-mredeem/2,0)*cfg['cd_yield']+parent_portfolio_income
        earlycost=cfg['parent_cd_redemptions'][0]*cfg['parent_cd_early_cost'] if y==1 else 0
        interest-=earlycost;minterest-=earlycost;cd-=redeem;mcd-=mredeem
        exercise=0;newshares=0
        for tr in cfg['exercise_schedule']:
            if tr['year']==y:
                q=tr['shares'];k=max(1.000001,tr['strike']-cumdiv);newshares+=q;exercise+=q*k
        shares+=newshares;cancelcash=0;cancelshares=0
        if cfg['proposed_cancellation_year']==y:
            cancelcash=cfg['proposed_cancellation_cash'];cancelshares=cfg['proposed_cancellation_shares'];shares-=cancelshares
        debtinterest=db*cfg['debt_rate'];principal=min(db,cfg['debt_principal_schedule'][i])
        nciprofit=cfg['nci_profit_start']*s['revenue']/sw[0]['revenue']+max(o['nci_equity']-o['nci_put_overlap']-o['nci_known_operating_book_h1'],0)*cfg['nci_portfolio_cash_yield_net']-o['nci_growth_capital_fraction']*s['restructuring'];ncidiv=max(nciprofit,0)*cfg['nci_payout'];nci+=nciprofit-ncidiv
        call=.241*a['capital_call'];antdiv=.241*a['dividend']
        claims=oldclaims if y==1 else 0;mclaims=o['parent_old_claims_estimate'] if y==1 else 0
        parent_cf=cfg['parent_software_fraction']*(s['economic_nopat_before_legacy_sbc']-s['growth_capex']-s['delta_wc']-s['restructuring'])-cfg['parent_project_capex'][i]
        mrealized_loss=o['parent_trading_h1']-mtraded if y==1 else 0
        motherprofit=cfg['parent_software_fraction']*(s['nopat']-s['restructuring'])+.241*a['profit']+minterest-mrealized_loss
        legal+=motherprofit
        reserve_add=statutory_reserve(motherprofit,lb,stat,shares,cfg['parent_reserve_policy']);legal-=reserve_add;stat+=reserve_add
        pre_group=cb+s['cash_fcf']+traded+redeem+interest+exercise+antdiv-claims-cancelcash-debtinterest-principal-ncidiv-call
        pre_mother=mb+parent_cf+mtraded+mredeem+minterest+exercise+antdiv-mclaims-cancelcash-call
        rolled=0
        if pre_group<s['cash_reserve'] and cfg['allow_existing_debt_roll']:
            rolled=min(principal,s['cash_reserve']-pre_group);principal-=rolled;pre_group+=rolled
        debt-=principal
        budget=cfg['dividend_budget'][i]*shares
        mother_min=cfg['parent_annual_cash_floor']
        if i<4:
            next_peak=cfg['parent_seasonal_cash_need']*sw[i+1]['revenue']/sw[0]['revenue']
            mother_min=max(mother_min,next_peak+cfg['parent_cash_floor']-cfg['parent_cd_redemptions'][i+1])
        actual=min(budget,max(pre_group-s['cash_reserve'],0),max(pre_mother-mother_min,0),max(legal,0))
        cash=pre_group-actual;mother=pre_mother-actual;legal-=actual;dps=actual/shares;cumdiv+=dps
        other_cf=s['cash_fcf']-parent_cf;other_redemption=traded+redeem-mtraded-mredeem;other_income=interest-minterest;other_claims=claims-mclaims
        other_cash=ob+other_cf+other_redemption+other_income-other_claims-debtinterest-principal-ncidiv
        seasonal=mb+mtraded+mredeem-(cfg['parent_seasonal_cash_need']*s['revenue']/sw[0]['revenue'])
        conditions={'group_operating_cash_floor':cash>=s['cash_reserve']-1e-9,'parent_annual_cash_floor':mother>=cfg['parent_annual_cash_floor']-1e-9,'parent_seasonal_cash_floor':seasonal>=cfg['parent_cash_floor']-1e-9,'other_group_entities_cash_nonnegative':other_cash>=-1e-9,'parent_cash_is_group_subset':mother<=cash+1e-9,'parent_cd_is_group_subset':mcd<=cd+1e-9}
        feasible=all(conditions.values())
        rows.append({'year':y,'group_cash_begin':cb,'group_cash_end':cash,'parent_cash_begin':mb,'parent_cash_end':mother,'other_cash_begin':ob,'other_cash_end':other_cash,'other_cash_from_operations_after_capital':other_cf,'other_investment_redemption':other_redemption,'other_financial_income':other_income,'other_claims_paid':other_claims,'assumed_intercompany_cash_transfers':0,'parent_cash_retention_target':mother_min,'parent_seasonal_min':seasonal,'parent_legal_begin':lb,'parent_profit':motherprofit,'parent_legal_end':legal,'parent_reserve_add':reserve_add,'parent_statutory_reserve':stat,'parent_reserve_policy':cfg['parent_reserve_policy'],'shares_begin':sb,'shares_end':shares,'exercise_cash':exercise,'exercise_shares':newshares,'cancel_cash':cancelcash,'cancel_shares':cancelshares,'dividend_budget_cash':budget,'common_dividend':actual,'dps':dps,'group_investment_redemption':traded+redeem,'parent_investment_redemption':mtraded+mredeem,'group_financial_income':interest,'parent_financial_income':minterest,'group_portfolio_cash_income':portfolio_income,'parent_portfolio_cash_income':parent_portfolio_income,'group_claims_paid':claims,'parent_claims_paid':mclaims,'parent_cash_from_operations_after_capital':parent_cf,'group_software_cash':s['cash_fcf'],'debt_begin':db,'debt_end':debt,'debt_interest':debtinterest,'debt_repaid':principal,'debt_rolled':rolled,'nci_begin':ncib,'nci_profit':nciprofit,'nci_dividend':ncidiv,'nci_end':nci,'ant_cash':antdiv-call,'group_cd_end':cd,'parent_cd_end':mcd,'feasibility_conditions':conditions,'feasible':feasible})
    return rows

def analyze(data,cfg=None):
    cfg=copy.deepcopy(cfg if cfg is not None else data['base']);o=data['opening'];sw=software(cfg,o,data['history']);ar=ant(cfg,o);fund=funding(cfg,o,sw,ar);ends={}
    for name,e in data['valuation_ends'].items():
        sv=pv([x['fcff'] for x in sw[:10]],sw[10]['fcff'],e['software_r'],cfg['terminal_growth'])
        sv5=pv([x['fcff'] for x in sw[:10]],sw[10]['fcff'],e['software_r'],cfg['terminal_growth'],5)
        antcfg=copy.deepcopy(cfg)
        if cfg.get('use_endpoint_ant_policy',True):antcfg['ant_release_start']=e['ant_release_start']
        aend=ant(antcfg,o)
        av=ant_value(aend,e['ant_r'])
        av5=ant_value(aend,e['ant_r'],5)
        assets=financial_assets(o,e)
        oldclaims=o['old_capital_payable']+o['old_cash_award']+o['old_put_obligation']+o['old_nci_dividend']
        liquid=(o['group_cce_9m']-o['paid_october_dividend']+o['post_9m_known_exercise_cash']+o['trading_assets']*cfg['trading_realization_ratio']+o['cd_short']+o['cd_long']-o['borrowings_and_leases']-oldclaims-o['operating_cash_reserve'])
        # Current value includes cash/shares from main scheduled exercises, not past exercises.
        capital_pv=sum((f['exercise_cash']-f['cancel_cash'])/(1+e['software_r'])**f['year'] for f in fund)
        nci_other=o['nci_equity']-o['nci_put_overlap']-o['nci_known_operating_book_h1']
        nci_np=cfg['nci_profit_start']
        nci_restruct_pv=o['nci_growth_capital_fraction']*sum(s['restructuring']/(1+e['software_r'])**s['year'] for s in sw[:10])
        nci=nci_np*e['nci_pe']+nci_other*e['other_asset_ratio']-nci_restruct_pv
        nci_retained=fund[-1]['nci_end']-(o['nci_equity']-o['nci_put_overlap'])
        nci_reinvest=o['nci_growth_capital_fraction']*(sw[4]['operating_capital_end']-opening_k(o))
        nci_restruct_pv5=o['nci_growth_capital_fraction']*sum(s['restructuring']/(1+e['software_r'])**(s['year']-5) for s in sw[5:10])
        nci5=nci_np*sw[4]['revenue']/sw[0]['revenue']*e['nci_pe']+(nci_other+nci_retained-nci_reinvest)*e['other_asset_ratio']-nci_restruct_pv5
        optionvalue=sum(t['shares']*t['vesting']*bs_call(data['option_mark_reference']['spot'],t['strike'],t['years'],e['option_sigma'],data['option_mark_reference']['risk_free']) for t in cfg.get('option_claims',data['option_claims_not_in_main_exercise']))
        shares=fund[-1]['shares_end'];gross=sv['value']+av['value']+assets['value']+liquid-nci+capital_pv-optionvalue
        f5=fund[-1];liquid5=f5['group_cash_end']+f5['group_cd_end']-f5['debt_end']-sw[4]['cash_reserve']
        gross5=sv5['value']+av5['value']+assets['value']+liquid5-nci5
        # Auxiliary normalized earnings: construction separately deducted, no blanket return of retained capital.
        projectpv=sum(s['project_capex']/(1+e['software_r'])**s['year'] for s in sw[:10])
        auxiliary=sw[0]['economic_nopat_before_legacy_sbc']*e['software_pe']-projectpv+ar[0]['operating_profit']*.241*e['ant_pe']+assets['value']+liquid-nci+capital_pv-optionvalue
        ends[name]={'software':sv,'ant':av,'ant_projection':aend,'assets':assets,'liquid_bridge':liquid,'nci_value':nci,'nci_restructure_pv':nci_restruct_pv,'nci_restructure_pv_year5':nci_restruct_pv5,'capital_action_pv':capital_pv,'option_claim':optionvalue,'shares':shares,'equity_value':gross,'per_share':gross/shares,'conditional_value_before_remaining_option_claim':(gross+optionvalue)/shares,'software_year5':sv5,'ant_year5':av5,'liquid_bridge_year5':liquid5,'nci_year5':nci5,'equity_year5':gross5,'per_share_year5':gross5/shares,'auxiliary_per_share':auxiliary/shares,'auxiliary_software_profit':sw[0]['economic_nopat_before_legacy_sbc'],'auxiliary_ant_profit':ar[0]['operating_profit'],'auxiliary_project_pv':projectpv}
    return {'software':sw,'ant':ar,'funding':fund,'endpoints':ends,'all_funding_feasible':all(x['feasible'] for x in fund),'dps':[x['dps'] for x in fund],'incremental_return_y1_to_y5':(sw[4]['economic_nopat_before_legacy_sbc']-sw[0]['economic_nopat_before_legacy_sbc'])/(sw[4]['operating_capital_end']-sw[0]['operating_capital_end']) if sw[4]['operating_capital_end']!=sw[0]['operating_capital_end'] else None}

# Only the separately authorized recorder invokes run.py; importing this module does not execute forecasts.
