"""New independent arithmetic/date primitives. Definitions only; no model imports."""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from datetime import date
import copy

class Technical(Exception):
    def __init__(self,reason,state=None):
        super().__init__(reason);self.state=copy.deepcopy(state)

def D(value):
    if isinstance(value,(bool,float)):raise Technical('binary float/bool operand forbidden')
    out=Decimal(str(value))
    if not out.is_finite():raise Technical('nonfinite arithmetic operand')
    return out

def F(value):
    if isinstance(value,(bool,float)):raise Technical('fixture must use exact rational operands')
    return Fraction(value)

def positive(x):return max(x,0)

def check(actual,expected,label,q):
    residue=actual-expected;allow=q(0) if isinstance(residue,Fraction) else q('1e-57')
    if abs(residue)>allow:raise Technical(label,{'actual':actual,'expected':expected,'residual':residue})
    return residue

def legal(open_re,reserve,capital,profit,rate,q):
    cure=min(positive(profit),positive(-open_re))
    add=min(positive(profit-cure)*rate,positive(capital/q(2)-reserve))
    return {'opening_re':open_re,'opening_reserve':reserve,'profit':profit,'loss_cured':cure,'reserve_add':add,'pre_distribution_re':open_re+profit-add,'reserve':reserve+add,'ceiling':positive(open_re+profit-add)}

def anniversary(anchor,index):
    d=date.fromisoformat(anchor)
    try:return d.replace(year=d.year+index).isoformat()
    except ValueError as error:raise Technical('unsupported original anniversary; no silent date shift') from error

def dated_pv(anchor,cash_dates,cash_per_share,rate,q,terminal_date=None,terminal_per_share=None):
    """Actual producer PV entry: original annual-anniversary contract, not ACT/daycount."""
    if len(cash_dates)!=len(cash_per_share) or rate<=-1:raise Technical('invalid dated cash interface')
    pieces=[]
    for i,(when,amount) in enumerate(zip(cash_dates,cash_per_share),1):
        if when!=anniversary(anchor,i):raise Technical('cash date is not the admitted annual anniversary',{'index':i,'actual':when})
        pieces.append(amount/(q(1)+rate)**i)
    terminal=q(0)
    if terminal_date is not None:
        if terminal_date!=anniversary(anchor,len(cash_dates)) or terminal_per_share is None:raise Technical('terminal not at last cash anniversary')
        terminal=terminal_per_share/(q(1)+rate)**len(cash_dates)
    return {'anchor_date':anchor,'cash_dates':list(cash_dates),'cash_per_share':list(cash_per_share),'discount_rate':rate,'dividend_pv_terms':pieces,'terminal_date':terminal_date,'terminal_per_share':terminal_per_share,'terminal_pv':terminal,'value':sum(pieces,q(0))+terminal,'basis':'annual anniversaries, not actual-day fractions'}

def cents_half_up(value,q):
    """Exact source 0.01 rounding; Fraction branch is actual production fixture path."""
    if isinstance(value,Fraction):
        x=value*100
        sign=-1 if x<0 else 1;x=abs(x)
        rounded=(2*x.numerator+x.denominator)//(2*x.denominator)
        return q(sign*rounded)/q(100)
    return value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)

def economic(reason,rows,state,diagnostic=None):
    return {'status':'ECONOMIC_INFEASIBLE','reason':reason,'rows':copy.deepcopy(rows),'failure_state':copy.deepcopy(state),'value':None,'terminal5':None,'diagnostic_not_accepted':copy.deepcopy(diagnostic),'no_fabricated_price':True}
