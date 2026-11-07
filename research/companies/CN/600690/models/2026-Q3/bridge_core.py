"""当前资本现金与权益计算核；经营输入由同次实际计算生成。"""
from copy import deepcopy
from fractions import Fraction as F


class BadInput(ValueError):
    def __init__(self,message,state=None):
        super().__init__(message);self.state=state


class EconomicShortfall(ValueError):
    """Resources really insufficient, with complete state attached."""
    def __init__(self, message, state):
        super().__init__(message)
        self.state = state


class TechnicalUnsettled(RuntimeError):
    """An unproved program/input boundary, never an economic zero value."""
    def __init__(self,message,state=None):
        super().__init__(message);self.state=state


def snapshot(value):
    """Read-only complete JSON snapshot; aliases/cycles have explicit path refs.

    No financial locals are dropped. Unsupported infrastructure objects are
    identified by type instead of evaluated or executed. Nonfinite floats remain
    visible as invalid numerical states rather than disappearing during JSON IO.
    """
    import math
    import types
    from collections.abc import Iterator
    from decimal import Decimal
    from pathlib import Path
    seen={}
    def visit(x,path):
        if x is None or type(x) in (str,int,bool):return x
        if isinstance(x,float):return x if math.isfinite(x) else {'$nonfinite_float':repr(x)}
        if isinstance(x,F):return {'$fraction':[x.numerator,x.denominator]}
        if isinstance(x,Decimal):return {'$decimal':str(x)}
        if isinstance(x,(dict,list,tuple,set)):
            if id(x) in seen:return {'$ref':seen[id(x)]}
            seen[id(x)]=path
            if isinstance(x,dict):return {str(k):visit(v,path+'/'+str(k)) for k,v in x.items()}
            values=[visit(v,path+'/'+str(i)) for i,v in enumerate(x)]
            return values if isinstance(x,list) else {'$tuple' if isinstance(x,tuple) else '$set':values}
        if isinstance(x,(types.ModuleType,types.FunctionType,types.MethodType,types.CodeType,type)):
            return {'$nonfinancial_infrastructure_type':type(x).__name__,
                    'name':getattr(x,'__qualname__',getattr(x,'__name__','code'))}
        if isinstance(x,(Iterator,types.GeneratorType)):
            return {'$interpreter_control_type':type(x).__qualname__,
                    'handling':'not consumed; complete financial source containers are captured in parent function frames'}
        if isinstance(x,Path):return {'$path':str(x)}
        if isinstance(x,Context):return {'$context_identity':{'code':x.code,'case':x.case_key,'active':x.active}}
        if hasattr(x,'__dict__'):
            return {'$object_type':type(x).__module__+'.'+type(x).__qualname__,
                    '$attributes':visit(vars(x),path+'/$attributes')}
        raise TechnicalUnsettled('Unsupported object in financial evidence snapshot: '+type(x).__qualname__)
    return visit(value,'$')


def exact_terms(event):
    required = ['unit', 'new_paid', 'new_shares', 'registered', 'old_future',
                'new_future', 'event_fee_budget_rate', 'future_fee_budget_rate']
    try:
        q = {k: F(event[k]) for k in required}
    except (KeyError, ValueError, ZeroDivisionError, TypeError) as exc:
        raise BadInput('Missing or invalid exact decimal input') from exc
    if q['unit'] <= 0 or q['registered'] <= 0:
        raise BadInput('Units and registered shares must be positive')
    if any(q[k] < 0 for k in required if k not in ['unit', 'registered']):
        raise BadInput('Negative payment, shares, remaining budget or fee')
    if q['new_shares'] > q['registered']:
        raise BadInput('Purchase exceeds registered shares')
    if event['same_plan_offset']:
        if q['old_future'] != q['new_paid'] + q['new_future']:
            raise BadInput('Same-plan paid plus future budget not conserved')
    elif q['old_future'] != q['new_future']:
        raise BadInput('Unfunded future-policy replacement of actual payment')
    q['event_fee_budget'] = q['new_paid'] * q['event_fee_budget_rate']
    q['future_fee_budget'] = q['new_future'] * q['future_fee_budget_rate']
    q['outlay'] = q['new_paid'] + q['event_fee_budget']
    q['registered_after_actual'] = q['registered']
    q['employee_after_actual'] = F(event['old_employee_treasury']) + (q['new_shares'] if event['new_kind'] == 'employee_treasury' else 0)
    q['pending_cancel_after_actual'] = F(event['old_pending_cancellation']) + (q['new_shares'] if event['new_kind'] == 'pending_cancellation' else 0)
    if q['employee_after_actual'] + q['pending_cancel_after_actual'] >= q['registered']:
        raise BadInput('No participating actual shares remain')
    return q


def opening_external_payment(parent, group, registered, inventory, consideration, fee, quantity):
    """Formal cash/rights chain: one external payment, no legal cancellation.

    Values may be Fraction in hand fixtures or original binary64 in cash adapters.
    The actual economic-negative test is made by the caller with its full ledger.
    """
    return dict(parent=parent-consideration-fee, group=group-consideration-fee,
                registered=registered, inventory=inventory+quantity,
                external_payment=consideration+fee)


class Context:
    def __init__(self, code, case_key, saved, event, active, allow_hq=False,allow_aux=False,frozen_aux=None):
        self.code, self.case_key, self.saved = code, case_key, deepcopy(saved)
        self.event, self.active, self.allow_hq = event, active, allow_hq
        self.allow_aux=allow_aux
        self.frozen_aux=deepcopy(frozen_aux)
        if code=='688100' and active and frozen_aux is None:
            raise TechnicalUnsettled('New Wasion cash run requires frozen auxiliary primitives from verified baseline proof; no regeneration allowed')
        self.last_state=None
        self.last_opening=[]
        self.terms = exact_terms(event)
        self.row_key = {'300750':'rows', '688100':'operations', '600887':'states',
                        '600690':'states', '688008':'years'}[code]
        self.rows = self.saved[self.row_key]
        self.used = set()

    def row(self, year):
        if not 1 <= year <= len(self.rows):
            raise TechnicalUnsettled('Frozen horizon exhausted; no forecast extension authorized')
        r = self.rows[year-1]
        if r['year'] != year:
            raise BadInput('Frozen annual row identity mismatch')
        self.used.add(year)
        return deepcopy(r)

    def amount(self, key):
        return float(self.terms[key] / self.terms['unit']) if self.active else 0.

    def capture_return_state(self,state):
        # A shallow locals dictionary only. No arithmetic, mutation or replay.
        self.last_state=state

    def debit(self, cash, state):
        if not self.active:
            return cash
        # Freeze pre-payment subjects now, not aliases to mutable future states.
        self.last_opening.append(snapshot({'complete_pre_payment_subjects':state,
                                           'payer_cash_before':cash,'event':self.event}))
        # The same formal external-payment function is exercised by Fraction fixtures.
        result = opening_external_payment(cash, cash, 1., 0., self.amount('new_paid'),
                                          self.amount('event_fee_budget'), 0.)['parent']
        if result < 0:
            raise EconomicShortfall('Opening external payment exceeds allocated payer cash',
                                    {'complete_opening_subjects':state,'opening_payer_cash':cash,
                                     'event':self.event,'closing_payer_cash':result})
        return result

    def guard_nonnegative(self, values, state, original_bound, original_comparison, aggregation):
        import math
        if not all(math.isfinite(v) for v in values):
            raise TechnicalUnsettled('Nonfinite cash is a numerical boundary, not a funded/underfunded conclusion',state)
        if original_comparison=='>' and aggregation=='min':valid=min(values)>original_bound
        elif original_comparison=='>=' and aggregation=='all':valid=all(v>=original_bound for v in values)
        else:raise BadInput('Unsupported original comparison')
        if not valid:
            raise EconomicShortfall('Cash violates original company financing boundary',
                                    {'complete_state':state,'values':values,'bound':original_bound,
                                     'comparison':original_comparison,'aggregation':aggregation})

    def guard_hq_branch(self, actual_stop, frozen_stop, states, year, need, capacity):
        if bool(actual_stop)==bool(frozen_stop):return
        payload={'year':year,'states':deepcopy(states),'required_support':need,
                 'support_capacity':capacity,'original_exit':bool(frozen_stop)}
        if actual_stop:
            raise EconomicShortfall('New payer cash cannot fund the frozen adopted HQ operating path',payload)
        raise TechnicalUnsettled('HQ continuation differs from frozen exit: scope incompatible, not an economic failure',payload)

    def require_wasion_aux(self,p):
        if not self.allow_aux:
            raise TechnicalUnsettled('Three original Wasion auxiliary expressions are not saved; separate narrow admission required',
                                    {'dependencies':{k:p[k] for k in ['aux_normal_owner_cash','aux_growth','discount_rate']},
                                     'source':'source/688100-model.py:evaluate_case aux_flows/aux_ev three statements'})

    def future(self, original):
        return float(self.terms['new_future']/self.terms['unit']) if self.active else original

    def original_plan_compensation(self, original):
        # Do not introduce binary rounding by adding paid + remainder back.
        return float(self.terms['old_future']/self.terms['unit']) if self.active else original

    def montage_attempt(self, year, previous):
        r = self.row(year)
        if year == 3 and r['exits']:
            if not self.allow_hq:
                raise TechnicalUnsettled('Montage saved Y3 omitted rejected HQ revenue/R&D. No economic result; reviewer must admit exactly two original-source primitive expressions.')
            # EXACT source order, only the two omitted rejected-budget primitives.
            # All six selected paths have original growth_hq=.55, terminal_g=.02.
            g = .02 + (.55-.02)*max(0, 1-(year-2)/10)
            attempted_revenue = previous['revenue'][2] * (1+g)
            attempted_expense = .28*(1.10**min(year-1,5))*(1+.02)**max(year-6,0)
            return attempted_revenue, attempted_expense
        return r['revenue'][2], r['hq_cash_rd_sga']


def exact_selected_equal(expected, actual, path='selected'):
    """No tolerance or dropped metadata; compares every selected saved leaf."""
    if type(expected) is not type(actual):
        raise TechnicalUnsettled(f'{path}: type mismatch {type(expected)} != {type(actual)}')
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            raise TechnicalUnsettled(f'{path}: field set differs')
        for k in expected:
            exact_selected_equal(expected[k], actual[k], f'{path}/{k}')
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            raise TechnicalUnsettled(f'{path}: row count differs')
        for i, (a,b) in enumerate(zip(expected, actual)):
            exact_selected_equal(a,b,f'{path}/{i}')
    elif isinstance(expected, float):
        if expected.hex() != actual.hex():
            raise TechnicalUnsettled(f'{path}: binary64 mismatch {expected.hex()} != {actual.hex()}')
    elif expected != actual:
        raise TechnicalUnsettled(f'{path}: value mismatch')


def exact_string(q):
    return f'{q.numerator}/{q.denominator}' if isinstance(q, F) else q
