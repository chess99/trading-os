"""Static parameter-to-event interface. Not executed. No economic forecasts.
Two cash endpoints are sensitivity samples, not a proven global valuation envelope.
"""
import copy
from fractions import Fraction as F

def condition_events(source_event):
    c=source_event['h_bounded_conditions']
    if c['status']!='FROZEN_AUTHOR_RESEARCH_CONDITIONS_PENDING_INDEPENDENT_REVIEW':
        return {'status':'PENDING_IDENTIFIABLE_FX_FEES_SETTLEMENT_CONDITIONS','events':[],
                'required':c,'not_missing':'No lifetime H buyback total is required.'}
    assert c['settlement_treatment']==c['permitted_settlement_treatment']
    def interval(z,positive=False,nonnegative=False):
        assert z['lower'] is not None and z['upper'] is not None and z['basis']
        a,b=F(str(z['lower'])),F(str(z['upper']))
        assert a<=b and (not positive or a>0) and (not nonnegative or a>=0)
        return a,b
    x=interval(c['fx_RMB_per_HKD']['2026-10-30'],positive=True)
    y=interval(c['fx_RMB_per_HKD']['2026-11-02'],positive=True)
    fee_rates=interval(c['incremental_fee_rate_on_converted_trade'],nonnegative=True)
    adjustment=interval(c['settlement_adjustment_CNY'])
    q=source_event['h_source_scope']['oct30_HKD_consideration_interval']
    consideration=(F(q['lower']),F(q['upper']))
    nov=F(source_event['h_source_scope']['nov2_HKD_consideration'])
    results=[]
    for i,name in enumerate(('cash_lower','cash_upper')):
        trade=consideration[i]*x[i]+nov*y[i]
        fee=trade*fee_rates[i]
        net=trade+fee+adjustment[i]
        assert net>=0
        e=copy.deepcopy(source_event)
        e['h_increment_cash_RMB_condition']=float(net)
        e['h_issuer_held_excluded_shares']=1514800
        # Both dated cash items, fee and adjustment remain separately attributable.
        e['h_condition_point']={'name':name,'oct30_fx':str(x[i]),'nov2_fx':str(y[i]),
            'trade_cash_CNY_fraction':str(trade),'fees_CNY_fraction':str(fee),
            'settlement_adjustment_CNY_fraction':str(adjustment[i]),'net_CNY_fraction':str(net),
            'conversion_to_float':'Only adapter boundary uses original float type; no exact settlement assertion.',
            'all_H_rights_excluded':1514800,'new_post_Q3_cash_quantity':1214800,
            'September_cash_deducted_again':False,'H_new_future_mandatory_spend':0,
            'valuation_range_claim':False}
        results.append(e)
    return {'status':'ADOPTED_CONDITIONAL_CASH_SENSITIVITY','events':results,
        'range_warning':'Cash bounds are algebraic under the adopted inputs. Financial outputs are two conditional samples, not certified global extrema through nonlinear financing/legal gates.'}
