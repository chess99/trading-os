"""当前数学计算组件；输入由必要事实、预算及同次经营计算生成。"""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import sys


def discounted(values, rate):
    return sum(v / (1 + rate) ** (i + 1) for i, v in enumerate(values))


def bridge(cash, funds0, funds5, normal_cash10, growth, rate, shares, distributions):
    if len(cash) != 10 or len(distributions) != 5 or not rate > growth:
        raise ValueError('Invalid saved-state horizon/rate')
    terminal10 = normal_cash10 * (1 + growth) / (rate - growth)
    # Preserve original producer operation order for exact old-value replay.
    current = discounted(cash, rate) + terminal10 / (1 + rate) ** 10 + funds0
    remaining = discounted(cash[5:], rate) + terminal10 / (1 + rate) ** 5
    year5 = funds5 + remaining
    per_share = year5 * 1_000_000_000 / shares
    holding = discounted(distributions, rate) + per_share / (1 + rate) ** 5
    return {'current_resource_equity_bn_reproduced': current,
            'same_base_year5_common_financial_principal_bn': funds5,
            'remaining_operating_equity_value_at_year5_bn': remaining,
            'same_base_year5_resource_equity_bn': year5,
            'same_base_year5_resource_per_share': per_share,
            'D1_D5_actual_saved_per_share': distributions,
            'finite_five_year_holder_PV_per_share_diagnostic': holding,
            'current_resource_per_share_reproduced': current * 1_000_000_000 / shares,
            'future_financial_interest_added_to_resource': False,
            'future_special_release_assumed': False}


def handcases():
    F = Fraction
    r = F(1,10); shares = 10**9
    # Independent literal annuity: ten ordinary operating cash 10, continuation
    # 10 forever, current principal20, five payments5, no financial interest.
    # End-Y5 financial state45 is 20+5*(10-5); no growth capital exists here.
    expected_remaining = F(100)
    expected_current = F(120)
    expected_y5 = F(145)
    x = bridge([F(10)]*10,F(20),F(45),F(10),F(0),r,shares,[F(5)]*5)
    assert x['remaining_operating_equity_value_at_year5_bn'] == expected_remaining
    assert x['current_resource_equity_bn_reproduced'] == expected_current
    assert x['same_base_year5_resource_equity_bn'] == expected_y5
    assert x['finite_five_year_holder_PV_per_share_diagnostic'] == sum(F(5)/(1+r)**i for i in range(1,6)) + expected_y5/(1+r)**5
    # Same operating future, an extra payment7 at the Y5 boundary removes7 from
    # funds/Y5. No second deduction or hidden principal; horizon wealth invariant.
    y = bridge([F(10)]*10,F(20),F(38),F(10),F(0),r,shares,[F(5)]*4+[F(12)])
    assert y['same_base_year5_resource_equity_bn'] == F(138)
    assert y['finite_five_year_holder_PV_per_share_diagnostic'] == x['finite_five_year_holder_PV_per_share_diagnostic']
    # Unequal future operating cash and growth tail: independent explicit powers,
    # not a second call to discounted/bridge as the expected-answer generator.
    tail = F(12)*F(102,100)/F(8,100)
    seq = list(map(F,[1,2,3,4,5,6,7,8,9,10]))
    z = bridge(seq,F(3),F(9),F(12),F(2,100),r,shares,[F(1)]*5)
    target = F(9)+sum(F(k)/(F(11,10)**(k-5)) for k in range(6,11))+tail/(F(11,10)**5)
    assert z['same_base_year5_resource_equity_bn'] == target
    return {'status':'PASS','formal_bridge_closed_form_cases':3,
            'expected_answers':'Independent Fraction annuity, boundary payment conservation, explicit finite growing-tail powers',
            'financial_producer_imports':0}
