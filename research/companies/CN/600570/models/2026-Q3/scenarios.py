'Material economic paths and one-factor diagnostics, used by ordinary offline model invocation.'
import copy

def configurations(data):
    base=copy.deepcopy(data['base']);out={'base':base}
    def buckets(c,rs,ms,later=None,mature=None):
        for i,s in enumerate(c['segments']):
            s['revenues']=rs[i];s['ebit_margins']=ms[i]
            if later:s['later_growth']=later[i]
            if mature:s['mature_margin']=mature[i]
    c=copy.deepcopy(base)
    buckets(c,[[3.55,3.50,3.80,4.05,4.30],[.85,.86,.95,1.05,1.15],[.80,.79,.85,.90,.95]],[[.11,.10,.13,.145,.155],[.07,.06,.08,.10,.11],[-.07,-.06,-.03,-.01,0]])
    c.update(project_capex=[.20,.15,.25,.25,.20,0,0,0,0,0],parent_project_capex=[.20,.12272,0,0,0,0,0,0,0,0],ant_revenues=[23,23,25,27,29,30.16,31.36,32.3,33.1,33.76],ant_margins=[.06,.06,.065,.07,.072,.072,.071,.07,.07,.07],dividend_budget=[.10,.10,.15,.20,.23],trading_realization_ratio=.90,parent_trading_realization_ratio=.90,extra_wc=[.20,.10,-.15,-.10,-.05,0,0,0,0,0],debt_rate=.055)
    out['cycle_two_year_delay']=c
    c=copy.deepcopy(base)
    buckets(c,[[3.35,3.10,3,2.95,2.90],[.80,.75,.73,.72,.72],[.80,.70,.60,.50,.45]],[[.07,.03,.02,.04,.06],[.02,-.02,0,.03,.05],[-.12,-.15,-.10,-.05,0]],[[-.01,-.01,0,0,0],[0,0,0,0,0],[-.05,-.05,0,0,0]],[.06,.05,0])
    c.update(project_capex=[.05,.05,.05,.10,.10,.125,.125,0,0,0],parent_project_capex=[0,0,0,.05,.05,.11136,.11136,0,0,0],restructuring_costs=[.25,.15,.05,0,0,0,0,0,0,0],extra_wc=[.25,.15,0,-.10,-.10,-.10,0,0,0,0],ant_revenues=[23,22,22,22.5,23,23,23,23,23,23],ant_margins=[.04,.035,.035,.04,.04,.04,.04,.04,.04,.04],dividend_budget=[0,0,0,.05,.08],trading_realization_ratio=.90,parent_trading_realization_ratio=.90,nci_profit_start=0,terminal_growth=0,allow_existing_debt_roll=False,debt_rate=.07)
    out['permanent_share_loss_restructure']=c
    mandatory=copy.deepcopy(c);mandatory['project_capex']=list(base['project_capex']);mandatory['parent_project_capex']=list(base['parent_project_capex']);mandatory['dividend_budget']=[0]*5;out['permanent_share_loss_full_project_obligations']=mandatory
    c=copy.deepcopy(base)
    buckets(c,[[4.10,4.50,4.95,5.40,5.85],[1.05,1.20,1.38,1.58,1.80],[.90,.92,.95,.98,1.00]],[[.17,.18,.19,.195,.20],[.12,.14,.16,.17,.18],[0,.01,.02,.035,.05]],[[.06,.05,.04,.03,.025],[.08,.07,.06,.04,.03],[.02,.02,.02,.02,.02]],[.18,.15,.04])
    c.update(growth_capital_ratio=.15,growth_wc_ratio=.10,ant_revenues=[28,31,34,37,40,42.4,44.52,46.3,47.69,48.88],ant_margins=[.09,.09,.09,.0875,.085,.083,.081,.08,.08,.08],dividend_budget=[.25,.30,.35,.40,.45])
    out['proven_product_reuse']=c
    # Limited disclosure / parent treasury failure: not a valid continuing valuation if constraints fail.
    c=copy.deepcopy(base);c['parent_cd_redemptions']=[0,.35,.29899426609,0,0];c['group_cd_redemptions']=[.23005700253,.35,.35,.31686639655,0]
    out['parent_no_early_cd_access']=c
    c=copy.deepcopy(base);c['extra_wc']=[.40,0,-.20,-.20,0,0,0,0,0,0];c['parent_seasonal_cash_need']=1.10;c['dividend_budget']=[0,.15,.22,.26,.30];c['parent_project_capex']=[.10,.10,.12272,0,0,0,0,0,0,0];c['project_capex']=[.12,.30,.35,.28,0,0,0,0,0,0];out['collection_delay_with_capex_dividend_cut']=c
    c=copy.deepcopy(base);c['ant_release_start']=11;c['use_endpoint_ant_policy']=False;out['ant_distribution_delayed_to_year11']=c
    c=copy.deepcopy(base);c['ant_permanent_no_cash_rights']=True;out['ant_permanent_no_distribution_and_no_transfer_proceeds']=c
    c=copy.deepcopy(base);c['ant_margins']=[.05]*10;out['ant_permanent_five_percent_margin']=c
    c=copy.deepcopy(base);c['portfolio_cash_yield_net']=0;c['nci_portfolio_cash_yield_net']=0;out['portfolio_no_cash_income']=c
    c=copy.deepcopy(base);c['growth_capital_ratio']=.20;out['physical_growth_capital_twenty_percent']=c
    c=copy.deepcopy(base);c['exercise_schedule']=[];c['option_claims']=[];out['no_future_option_exercise']=c
    c=copy.deepcopy(base);c['option_claims']=[];out['base_capital_path_conditioned_no_other_exercise']=c
    c=copy.deepcopy(base)
    c['exercise_schedule']+= [
      {'year':1,'shares':.003784680,'strike':38.96,'name':'2023_3'},
      {'year':1,'shares':.004266255,'strike':37.73,'name':'2025_1'},
      {'year':2,'shares':.013317000,'strike':16.69,'name':'2024_3_upper'},
      {'year':2,'shares':.004533000,'strike':37.73,'name':'2025_2_upper'},
      {'year':3,'shares':.006044000,'strike':37.73,'name':'2025_3_upper'},
      {'year':1,'shares':.009279900,'strike':22.76,'name':'2026_1'},
      {'year':2,'shares':.009279900,'strike':22.76,'name':'2026_2'},
      {'year':3,'shares':.012373200,'strike':22.76,'name':'2026_3'}]
    c['option_claims']=[];c['capital_action_quantity_status']='registered_count_mathematical_upper_not_verified_current_legal_exercisability';out['all_known_options_conditional_cash_paired_upper']=c
    tight=copy.deepcopy(c)
    for tr in tight['exercise_schedule']:
        if tr['name']=='2024_3_upper':tr['shares']=.012368400
        if tr['name']=='2025_2_upper':tr['shares']=.004357200
        if tr['name']=='2025_3_upper':tr['shares']=.005809600
    tight['capital_action_quantity_status']='old_report_tighter_counts_not_independently_verified';out['all_options_old_unverified_tighter_quantity_case']=tight
    c=copy.deepcopy(base);c['option_claims']=copy.deepcopy(data['option_claims_not_in_main_exercise'])
    for tr in c['option_claims']:
        if tr['name']=='2024_tranche3_registered_upper':tr['shares']=.012368400
        if tr['name']=='2025_later_registered_upper':tr['shares']=.010166800
    out['option_claims_old_unverified_tighter_quantities']=c
    for name,parent_policy,ant_policy in [
        ('parent_reserve_legally_stop_at_half','stop_when_half','continue_ten_percent'),
        ('ant_reserve_legally_stop_at_half','continue_ten_percent','stop_when_half'),
        ('both_reserves_legally_stop_at_half','stop_when_half','stop_when_half')]:
        c=copy.deepcopy(base);c.update(parent_reserve_policy=parent_policy,ant_reserve_policy=ant_policy);out[name]=c
    c=copy.deepcopy(base);c['ant_continue_through_year']=10;out['ant_reserve_continue_ten_years_then_legally_stop']=c
    c=copy.deepcopy(base);c.update(ant_no_dividends_before_exit=True,ant_exit_year=15,ant_exit_equity_ratio=.80);out['ant_no_dividends_conditional_sale_year15_eighty_percent_book']=c
    for ratio in [.15,.25]:
        c=copy.deepcopy(base);c['ant_capital_ratio']=ratio;out['ant_operating_capital_'+str(round(ratio*100))+'_percent']=c
    c=copy.deepcopy(base);c['ant_capital_ratio']=.25;c['ant_margins']=[.05]*10;out['ant_five_percent_margin_twentyfive_percent_capital']=c
    for factor in [.75,1.25]:
        c=copy.deepcopy(base);c['nci_profit_start']=base['nci_profit_start']*factor;out['nci_normalized_profit_'+str(round(factor*100))+'_percent']=c
    return out
