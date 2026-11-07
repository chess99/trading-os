"""Exact finite first-hit geometry only. No company constants or execution."""
from fractions import Fraction as F


class EconomicUnproved(RuntimeError):
    def __init__(self,code,detail):
        self.code=code;self.detail=detail
        super().__init__(code+': '+str(detail))


class ReleaseBudgetExceeded(RuntimeError):
    pass


def first_hit(S,F0,A,g,max_index=256):
    """Minimum n>=0 for E_n=S-A*sum(q**k)-F0*q**n <=0.
    The classification is analytic; exact doubling/bisection locates a proven
    finite root. No repeated simulation/year-horizon guessing; no float log.
    """
    S,F0,A,g=map(F,(S,F0,A,g));q=1+g;E0=S-F0
    if q<=0:raise ValueError('q=1+g must be positive; no logarithm or economic continuation for g<=-1')
    if E0<=0:return {'kind':'FINITE','n':0,'E_before':None,'E_at':E0,'reason':'AT_OR_BELOW_FLOOR'}
    def E(n):
        return E0-n*A if g==0 else E0-(A+g*F0)*(q**n-1)/g
    if g==0:
        if A<=0:return {'kind':'NO_FINITE_HIT','reason':'ZERO_GROWTH_NONPOSITIVE_RELEASE','E0':E0,'A':A}
        quotient=E0/A;n=(quotient.numerator+quotient.denominator-1)//quotient.denominator
        if n>max_index:raise ReleaseBudgetExceeded('Proven finite linear first hit exceeds exact-index implementation budget')
    else:
        d=A+g*F0
        if d<=0:return {'kind':'NO_FINITE_HIT','reason':'EXCESS_NONDECREASING','E0':E0,'net_release_including_floor_growth':d}
        if g<0:
            limit=E0+d/g
            if limit>=0:return {'kind':'NO_FINITE_HIT','reason':'ASYMPTOTIC_ZERO_ONLY' if limit==0 else 'POSITIVE_LIMIT','limit':limit,'E0':E0}
        high=1
        while E(high)>0:
            if high>=max_index:raise ReleaseBudgetExceeded('Analytically finite geometric hit exceeds exact-index implementation budget')
            high=min(high*2,max_index)
        low=0
        while high-low>1:
            middle=(low+high)//2
            if E(middle)<=0:high=middle
            else:low=middle
        n=high
    before,at=E(n-1),E(n)
    if not(before>0 and at<=0):raise AssertionError('Exact first-hit neighbor proof failed')
    return {'kind':'FINITE','n':n,'E_before':before,'E_at':at,'E0':E0,'q':q,'A1':A,'F0':F0,'S0':S,'reason':'EXACT_MINIMAL_NEIGHBOR_PROOF'}
