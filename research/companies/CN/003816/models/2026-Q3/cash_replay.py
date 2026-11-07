"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
import copy
from common import EconomicRefusal

class TerminalScheduleUnclosed(RuntimeError):
    """Technical model stop, never an EconomicRefusal or a feasible cash settlement."""
    def __init__(self,details):
        self.code='terminal_debt_settlement_contract_unclosed'
        self.details=details
        super().__init__(self.code)

def legal_step(retained,reserve,capital,profit,cash,requested):
    # Losses must be covered first; allocation only to net post-loss current profits.
    opening=retained
    retained+=profit
    eligible=max(0.,profit-max(0.,-opening))
    appropriation=min(max(0.,capital*.5-reserve),eligible*.10)
    reserve+=appropriation;retained-=appropriation
    paid=min(max(0.,requested),max(0.,retained),max(0.,cash))
    retained-=paid;cash-=paid
    return retained,reserve,cash,paid,appropriation

def cash_step(cash,operating,capex,interest,draw,principal,distribution):
    end=cash+operating-capex-interest+draw-principal-distribution
    assert abs(end-(cash+operating-capex-interest+draw-principal-distribution))<1e-8
    return end

def bridge(saved,event=None,checkpoint=None):
    checkpoint=checkpoint or (lambda state:None)
    historical_mode=event is None
    input_parameters=copy.deepcopy(saved['parameters'])
    p=copy.deepcopy(input_parameters);years=len(saved['rows']);event=event or {}
    checkpoint({'phase':'input','parameters':input_parameters,'event':event,'historical_mode':historical_mode})
    opening_face=4.8992182
    face=event.get('remaining_face',opening_face)
    shares0=event.get('shares',50.498824311)
    if face<0 or face>opening_face:raise ValueError('invalid remaining face')
    unchanged_general_loan=p['debt']-opening_face-25.
    p['debt']-=opening_face-face
    p['parent_capital']=event.get('parent_capital',p['parent_capital'])
    opening_parameters=copy.deepcopy(p);parent_capital=p['parent_capital']
    # Explicit budget mapping: 27.5 contains the old parent-issued bond face.
    # Nonbond parent loans retain old 30-year schedule; total debt is NOT reduced again.
    parent_nonbond_opening=27.5-opening_face
    debt=p['debt']; parent_cash=p['parent_open_cash']; sub_cash=p['sub_open_cash']
    retained=p['parent_retained']; reserve=p['parent_reserve']; subret=p['sub_retained_budget']
    subreserve=0.; receivable=p['receivable']; shares=shares0
    rows=[]; loans=[dict(balance=unchanged_general_loan,annual=unchanged_general_loan/30,start=1),dict(balance=face,annual=0.,start=1),dict(balance=25.,annual=25./30,start=1,owner='taishan')]
    obligations=copy.deepcopy(saved['retirement_obligations']) # frozen source only; never regenerated
    decomm=0.; bridge=0.; total_ext_equity=0.
    ts_cash=.5;sub_cash-=ts_cash;ts_ret=-p['taishan_deficit']*.51;ts_res=0.
    mid_cash=0.;mid_res=0.
    for t in range(1,years+1):
        checkpoint({'phase':'year_open','year':2026+t,'parent_cash':parent_cash,'sub_cash':sub_cash,'taishan_cash':ts_cash,'debt':debt,'parent_bridge':bridge,'loans':copy.deepcopy(loans),'parent_capital':parent_capital,'parent_retained':retained,'parent_reserve':reserve,'decommission_fund':decomm,'completed_rows':len(rows)})
        yr=2026+t; d0=debt; s0=sub_cash; pc0=parent_cash;ts0=ts_cash;mid0=mid_cash;fund0=decomm;opening_mid_res=mid_res
        ts_debt_open=sum(l['balance'] for l in loans if l.get('owner')=='taishan')
        parent_bond_refinance_open=sum(l['balance'] for l in loans if l.get('owner')=='parent_bond_refinance')
        frozen=saved['rows'][t-1]
        if frozen['year']!=yr:raise ValueError('noncontiguous frozen operating rows')
        nopat=frozen['nopat'];da=frozen['da'];maint=frozen['maintenance'];capex=frozen['capex']
        finance_principal=frozen['financial_principal_received'];project_rows=frozen['projects']
        ts_nopat=frozen['taishan_nopat'];funding=frozen['decommission_funding']
        retirement_payment=frozen['decommission_payment'];ts_retirement_deposit=frozen['taishan_retirement_deposit']
        # Only the immutable original cash-allocation coefficient is needed below for TS D&A.
        # No revenue, margin, NOPAT, capex, projects, CODs or retirement obligations are forecast.
        mature=1. if t<=p['mature_plateau'] else max(0.,(p['mature_end']-t)/(p['mature_end']-p['mature_plateau']))
        active=bool(da or maint)
        fund_income=decomm*.02
        decomm+=fund_income+funding-retirement_payment
        if decomm < -1e-6:raise EconomicRefusal('decommission_fund_shortfall',{'failure_row':{'year':yr,'decommission_fund':decomm,'unpaid_obligation':-decomm,'parent_cash':parent_cash,'sub_cash':sub_cash,'debt':debt,'bridge':bridge,'loans':copy.deepcopy(loans),'funding':funding,'retirement_payment':retirement_payment},'rows_before_failure':rows})
        assert abs(decomm-(fund0+fund_income+funding-retirement_payment))<1e-6
        draw=.80*capex
        if draw>0:loans.append(dict(balance=draw,annual=draw/30,start=t+1))
        principal=0.;ts_principal=0.
        for l in loans:
            if t>=l['start']:
                v=min(l['balance'],l['annual']);l['balance']-=v;principal+=v
                if l.get('owner')=='taishan':ts_principal+=v
        # Construction interest already in full cost/capex: separate current expense from IDC.
        construction=p['construction_debt']*max(0.,1-t/10)
        interest=max(0.,d0-construction)*p['rate']
        bond_refinance=0.;bond_redemption=0.
        if t<=5:
            interest+=face*([.008,.012,.016,.020,.020][t-1]-p['rate'])
        if t==5 and not p['convertible']:
            # 106% including last 2% coupon: 4% premium is incremental to interest above.
            bond_refinance=face*1.04;bond_redemption=face*1.04
            loans[1]['balance']=0.
            loans.append(dict(balance=bond_refinance,annual=bond_refinance/20,start=6,owner='parent_bond_refinance'))
        debt=d0+draw-principal+(bond_refinance-face if bond_refinance else 0.)
        # Op cash calculated after tax; interest tax shield only at earning operating subsidiaries.
        legacy_parent_no_shield=27.5*max(0.,1-(t-1)/30)*p['rate']
        parent_nonbond_interest=parent_nonbond_opening*max(0.,1-(t-1)/30)*p['rate']
        parent_bond_interest=(face*[.008,.012,.016,.020,.020][t-1] if t<=5 else parent_bond_refinance_open*p['rate'])
        parent_existing_interest=(legacy_parent_no_shield if historical_mode else parent_nonbond_interest+parent_bond_interest)
        # Existing parent financing, like the incremental bridge, has no presumed current tax shield.
        ts_interest_gross=ts_debt_open*p['rate']
        ts_interest_tax_shield=min(ts_interest_gross*p['tax'],max(0.,ts_nopat)/(1-p['tax'])*p['tax'])
        ts_interest=ts_interest_gross-ts_interest_tax_shield
        # No immediate shield on TS interest beyond its own positive operating tax base.
        ts_unavailable_shield=ts_interest-ts_interest_gross*(1-p['tax'])
        if not historical_mode and parent_existing_interest+ts_interest_gross>interest+1e-8:
            raise EconomicRefusal('financing_tax_ownership_budget_incompatible',{'failure_row':{'year':yr,'total_gross_interest':interest,'parent_no_shield_interest':parent_existing_interest,'taishan_gross_interest':ts_interest_gross,'parent_cash':parent_cash,'sub_cash':sub_cash,'debt':debt,'bridge':bridge,'loans':copy.deepcopy(loans)},'rows_before_failure':rows})
        no_shield_interest=min(interest,parent_existing_interest) if historical_mode else parent_existing_interest
        interest_after_tax=interest*(1-p['tax'])+no_shield_interest*p['tax']+ts_unavailable_shield
        other_interest=interest_after_tax-ts_interest
        ts_profit=ts_nopat-ts_interest-ts_retirement_deposit
        net_profit=nopat-interest_after_tax-funding-(face*.04 if bond_refinance else 0.)
        operating=nopat+da-maint-funding+finance_principal
        # Group common-share cash net of project loans; parent equity injection is an internal transfer.
        injection=capex-draw
        ts_flow=ts_profit+(1.5-.51)*mature-ts_principal
        # Taishan attributable debt service is allocated within, not added to, group debt.
        ts_cash+=ts_flow
        ts_short=max(0.,-ts_cash)
        if ts_short:
            ts_cash+=ts_short;debt+=ts_short;loans.append(dict(balance=ts_short,annual=ts_short/15,start=t+1,owner='taishan'))
        other_operating=operating-(ts_nopat+(1.5-.51)*mature-ts_retirement_deposit)
        raw_sub=cash_step(sub_cash,other_operating,0,other_interest,0,principal-ts_principal,0)
        ts_ret,ts_res,ts_cash,ts_decl,ts_alloc=legal_step(ts_ret,ts_res,28.6*.51,ts_profit,ts_cash,max(0.,ts_profit)*p['upstream'])
        if t>=12:
            ts_ret,ts_res,ts_cash,ts_extra,_=legal_step(ts_ret,ts_res,28.6*.51,0.,ts_cash,max(0.,ts_cash-.2)/max(1,22-t))
            ts_decl+=ts_extra
        # 12.5/51 direct; 38.5/51 indirect. Intermediate cash takes one additional year.
        mid_receipt=mid_cash;mid_cash=0.
        via_mid=ts_decl*38.5/51
        mid_alloc=min(max(0.,.009-mid_res),ts_decl*28.5/51*.1)
        mid_res+=mid_alloc;mid_cash+=via_mid-mid_alloc
        # Capped intermediate reserve remains a cash asset, returned on capital exit.
        ts_receipt=ts_decl*12.5/51+mid_receipt
        ts_capital_return=0.;ts_exit_call=0.;ts_exit_repayment=0.;ts_midreserve_return=0.
        if t==p['mature_end']:
            # Exit capital pays ALL Taishan residual obligations first. Parent bears any deficit.
            ts_exit_repayment=sum(l['balance'] for l in loans if l.get('owner')=='taishan')
            ts_exit_call=max(0.,ts_exit_repayment-ts_cash)
            ts_cash+=ts_exit_call-ts_exit_repayment
            parent_cash-=ts_exit_call
            debt-=ts_exit_repayment;principal+=ts_exit_repayment;ts_principal+=ts_exit_repayment
            for l in loans:
                if l.get('owner')=='taishan':l['balance']=0.
            ts_midreserve_return=mid_res
            ts_capital_return=ts_cash+mid_res
            ts_receipt+=ts_capital_return;ts_cash=0.;mid_res=0.
        # Existing receivable collection only uses cash; never credited to current profit.
        old_receipt=min(receivable,max(0.,raw_sub-2.0)) if t>p['receipt_delay'] else 0.
        receivable-=old_receipt;raw_sub-=old_receipt
        declaration=max(0.,net_profit-ts_profit)*p['upstream']
        # Consolidated common-share distributable buffer is a research budget, not a legal statement.
        subret,subreserve,sub_cash,declared,sub_alloc=legal_step(subret,subreserve,70.,net_profit-ts_profit,raw_sub,declaration)
        receipt=declared if t>p['receipt_delay'] else 0.
        if not receipt:receivable+=declared;sub_cash+=declared
        # Cash retained in intermediate/operating companies released over 10 years after building phase,
        # subject to available legal profit budget. This is not a year-5 mark-to-par release.
        extra=0.
        if t>=12:
            request=max(0.,sub_cash-2.)/max(1,22-t)
            subret,subreserve,sub_cash,extra,extra_alloc=legal_step(subret,subreserve,70.,0.,sub_cash,request)
        receipt+=extra
        receipt+=ts_receipt
        # If cash shortage: operating company shortfall loan, included in all common-share debt.
        short=max(0.,2.-sub_cash) if active else max(0.,-sub_cash)
        if short:
            sub_cash+=short;debt+=short;loans.append(dict(balance=short,annual=short/15,start=t+1))
        holding_cost=.55 if active else 0.
        bridge_interest=bridge*p['rate'] # only incremental parent bridge; not in original debt.
        parent_profit=declared+extra+ts_receipt-ts_capital_return-ts_exit_call-holding_cost-bridge_interest
        parent_cash+=receipt+old_receipt-injection-holding_cost-bridge_interest
        # Shareholder payout request follows earnings, limited by legal profit and cash.
        target=max(0.,net_profit-holding_cost-bridge_interest)*(p['early_payout'] if t<=10 else .70)
        if t>12:target+=max(0.,parent_cash-2.)/max(1,22-t)
        # No borrowing to maintain arbitrary dividends; bridge funds committed equity capex only.
        deficit=max(0.,-parent_cash)
        if deficit:bridge+=deficit;parent_cash+=deficit
        bridge_repay=min(bridge,max(0.,parent_cash-2.))
        bridge-=bridge_repay;parent_cash-=bridge_repay
        conversion_price=None;converted_shares=0.;converted_face=0.
        if not historical_mode and p['convertible'] and t==5:
            # Year-5 full-year coupon first; conversion BEFORE reserve/payout/record date.
            # Price adjustment uses prior four distributions, as in the old forecast rule.
            conversion_price=max(.1,3.58-sum(x['dps'] for x in rows))
            converted_face=face;converted_shares=face/conversion_price
            shares+=converted_shares;parent_capital+=converted_shares
            loans[1]['balance']=0.;debt-=face
        retained,reserve,parent_cash,paid,alloc=legal_step(retained,reserve,parent_capital,parent_profit,parent_cash,min(target,max(0.,parent_cash-1.)))
        # Retirement liquidation of residual cash and legally returnable capital; no asset resale premium.
        liquidation=0.
        if t==years and saved.get('liquidate_at_horizon',True):
            # All plant lives ended by 2095. Decommission funds consumed, not paid to shareholders.
            assert not active
            if debt+bridge>=1e-7:
                # No terminal debt settlement contract is invented here. The sum below
                # is only an optimistic UPPER BOUND, not permission to transfer entity cash.
                # Receivables, plant, financial assets and new borrowing are NOT cash resources.
                # Restricted decommission cash is reserved for its existing obligations.
                terminal_cash_by_ledger={'parent':parent_cash,'other_subsidiaries':sub_cash,
                  'taishan':ts_cash,'intermediate':mid_cash,'intermediate_reserve_cash':mid_res}
                terminal_obligation=debt+bridge
                terminal_cash_upper_bound=sum(max(0.,v) for v in terminal_cash_by_ledger.values())
                terminal_shortfall_lower_bound=max(0.,terminal_obligation-terminal_cash_upper_bound)
                proven_cash_shortfall=terminal_shortfall_lower_bound>1e-7
                terminal_failure={'failure_row':{'year':yr,'debt':debt,'bridge':bridge,
                  'terminal_debt_obligation':terminal_obligation,
                  'cash_by_ledger':terminal_cash_by_ledger,'cash_resource_upper_bound':terminal_cash_upper_bound,
                  'payment_resource_shortfall_lower_bound':terminal_shortfall_lower_bound,
                  'unpaid_obligation':terminal_shortfall_lower_bound if proven_cash_shortfall else None,
                  'unpaid_obligation_basis':'Proven minimum aggregate cash gap; entity transfer rights may make the actual gap larger. No settlement has been executed.',
                  'parent_cash':parent_cash,'sub_cash':sub_cash,'taishan_cash':ts_cash,
                  'intermediate_cash':mid_cash,'intermediate_reserve':mid_res,'loans':copy.deepcopy(loans),
                  'paid_before_liquidation':paid,'parent_capital':parent_capital,'parent_retained':retained,
                  'parent_reserve':reserve,'sub_retained':subret,'sub_reserve':subreserve,
                  'taishan_retained':ts_ret,'taishan_reserve':ts_res,'receivable':receivable,
                  'decommission_fund':decomm,'liquidation_executed':False,
                  'year_opening_state':{'debt':d0,'parent_cash':pc0,'sub_cash':s0,'taishan_cash':ts0,
                    'intermediate_cash':mid0,'intermediate_reserve':opening_mid_res,'decommission_fund':fund0},
                  'operating_cash':operating,'interest_after_tax':interest_after_tax,'principal_paid':principal,
                  'project_draw':draw,'sub_shortfall_draw':short,'taishan_shortfall_draw':ts_short,
                  'parent_bridge_draw':deficit,'parent_bridge_repaid':bridge_repay},
                  'rows_before_failure':rows,
                  'settlement_contract':'Not supplied; no inter-entity cash transfer, new financing, asset realization, debt payment or shareholder liquidation is added.'}
                checkpoint({'phase':'terminal_debt_stop',
                  'classification':'PROVEN_CASH_SHORTFALL' if proven_cash_shortfall else 'TECHNICAL_SETTLEMENT_CONTRACT_UNCLOSED',
                  **terminal_failure})
                if proven_cash_shortfall:
                    raise EconomicRefusal('terminal_debt_cash_resources_insufficient',terminal_failure)
                # Enough total ledger cash does not establish that every debtor can use it.
                # Even parent cash alone > debt cannot create a missing settlement schedule.
                raise TerminalScheduleUnclosed(terminal_failure)
            assert abs(decomm)<1e-5
            liquidation=parent_cash+sub_cash+ts_cash+mid_cash+mid_res
            paid+=liquidation;parent_cash=0.;sub_cash=0.;ts_cash=0.;mid_cash=0.;mid_res=0.
        if historical_mode and p['convertible'] and t==5:
            # Alternative full conversion at adjusted price; no conversion assumed in core.
            conversion_price=max(.1,3.58-sum(x['dps'] for x in rows))
            converted_shares=face/conversion_price;shares+=converted_shares
            # Conversion reduces initial-loan principal, avoiding debt AND dilution counted together.
            loans[1]['balance']=0.;debt-=face
        if min(parent_cash,sub_cash,ts_cash)<-1e-7:raise EconomicRefusal('negative_payment_cash',{'failure_row':{'year':yr,'parent_cash':parent_cash,'sub_cash':sub_cash,'taishan_cash':ts_cash,'unpaid_obligation':max(0.,-min(parent_cash,sub_cash,ts_cash)),'debt':debt,'bridge':bridge,'loans':copy.deepcopy(loans),'parent_retained':retained,'parent_reserve':reserve,'paid':paid},'rows_before_failure':rows})
        assert abs(debt-sum(l['balance'] for l in loans))<1e-6
        # All cash movements are reconciled including declared-but-unreceived internal transfers.
        total_expected=s0+pc0+ts0+mid0+opening_mid_res+operating-interest_after_tax-principal-injection-holding_cost-bridge_interest+short+ts_short+deficit-bridge_repay-paid
        assert abs(sub_cash+parent_cash+ts_cash+mid_cash+mid_res-total_expected)<1e-6,(yr,total_expected,sub_cash+parent_cash+ts_cash+mid_cash+mid_res)
        assert abs(sub_cash+parent_cash+ts_cash+mid_cash+mid_res+decomm-(total_expected+fund0+funding+fund_income-retirement_payment))<1e-6
        ts_operating_cash=ts_nopat+(1.5-.51)*mature-ts_retirement_deposit-ts_interest
        assert abs(ts_cash-(ts0+ts_operating_cash-ts_principal+ts_short-ts_decl+ts_exit_call-ts_capital_return+ts_midreserve_return))<1e-6
        assert abs(interest_after_tax-ts_interest-other_interest)<1e-8
        if t>=p['mature_end']:assert sum(l['balance'] for l in loans if l.get('owner')=='taishan')<1e-7
        rows.append(dict(year=yr,nopat=nopat,profit=net_profit,da=da,maintenance=maint,
            capex=capex,equity_injection=injection,project_draw=draw,principal=principal,
            interest=interest_after_tax,bond_refinance=bond_refinance,bond_redemption=bond_redemption,financial_principal_received=finance_principal,debt=debt,parent_bridge=bridge,shortfall_draw=short,
            sub_cash=sub_cash,declared=declared,receipt=receipt,old_receipt=old_receipt,
            receivable=receivable,parent_profit=parent_profit,parent_cash=parent_cash,
            parent_retained=retained,parent_reserve=reserve,sub_retained_budget=subret,
            payout=paid,dps=paid/shares,shares=shares,parent_capital=parent_capital,parent_reserve_addition=alloc,
            parent_nonbond_interest=parent_nonbond_interest,parent_bond_interest=parent_bond_interest,parent_no_shield_interest_budget=parent_existing_interest,
            parent_legacy_no_shield_budget=legacy_parent_no_shield,conversion_price=conversion_price,converted_shares=converted_shares,converted_face=converted_face,
            decommission_opening=fund0,decommission_funding=funding,decommission_fund=decomm,decommission_payment=retirement_payment,decommission_income=fund_income,taishan_nopat=ts_nopat,taishan_debt_opening=ts_debt_open,taishan_debt_closing=sum(l['balance'] for l in loans if l.get('owner')=='taishan'),taishan_principal=ts_principal,taishan_interest_gross=ts_interest_gross,taishan_interest_tax_shield=ts_interest_tax_shield,taishan_interest_after_tax=ts_interest,other_interest_after_tax=other_interest,other_operating_cash=other_operating,taishan_operating_cash=ts_nopat+(1.5-.51)*mature-ts_retirement_deposit-ts_interest,taishan_exit_call=ts_exit_call,taishan_exit_debt_repayment=ts_exit_repayment,taishan_retirement_deposit=ts_retirement_deposit,taishan_capital_return=ts_capital_return,taishan_shortfall_draw=ts_short,taishan_profit=ts_profit,taishan_cash=ts_cash,taishan_retained=ts_ret,taishan_declared=ts_decl,intermediate_cash=mid_cash,intermediate_reserve=mid_res,projects=project_rows))
        checkpoint({'phase':'year_close','year':yr,'row':rows[-1],'loans':copy.deepcopy(loans),'sub_reserve':subreserve,'taishan_reserve':ts_res})
    # Truncated hand fixtures use this same recurrence but must never claim a complete value.
    if not saved.get('liquidate_at_horizon',True):
        return {'feasible':True,'status':'PARTIAL_LEDGER_ONLY','value':None,'terminal_year5':None,'rows':rows,'opening_parameters':opening_parameters,'input_parameters':input_parameters,'source_event':event,'final_parent_capital':parent_capital}
    pv=sum(x['dps']/(1+p['r'])**(i+1) for i,x in enumerate(rows))
    tv5=sum(x['dps']/(1+p['r'])**(i-4) for i,x in enumerate(rows) if i>=5)
    return dict(feasible=True,value=pv,terminal_year5=tv5,terminal_share=tv5/(1+p['r'])**5/pv if pv else 0.,
                dps=[x['dps'] for x in rows[:5]],rows=rows,parameters=opening_parameters,retirement_obligations=obligations,opening_parameters=opening_parameters,input_parameters=input_parameters,source_event=copy.deepcopy(event),final_parent_capital=parent_capital,
                parent_finance_mapping={'old_total_parent_debt_budget':27.5,'old_parent_bond_face':opening_face,'unchanged_parent_nonbond_budget':parent_nonbond_opening,'historical_mode':historical_mode,'current_bond_has_immediate_tax_shield':False},
                future_conversion_timing=('historical_as_published' if historical_mode else 'Year5 coupon first, conversion before statutory reserve and dividend record date; year5 D uses post-conversion shares'))
