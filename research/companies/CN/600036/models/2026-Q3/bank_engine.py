#!/usr/bin/env python3
'CN600036 research: sole executable entry. Standard library only.\nOrdinary local entry; exact public input integrity is required.\nMoney: CNY million. Monthly allocation is a calendar budget, not reported profit.\n'
from __future__ import annotations
import argparse, calendar, copy, datetime as dt, hashlib, json, math, time
from pathlib import Path
from fractions import Fraction

EPS = 1e-7

def bounded_number(value):return Q(value) if isinstance(value,Fraction) else value
def dot(a,b):
    total=0
    for x,y in zip(a,b):total=bounded_number(total+bounded_number(x*y))
    return total
def mv(a, x): return [dot(row,x) for row in a]
def ident(n): return [[float(i==j) for j in range(n)] for i in range(n)]
def transpose(a): return [list(x) for x in zip(*a)]
def plus(a,b): return [bounded_number(x+y) for x,y in zip(a,b)]
def scale(a,k): return [bounded_number(x*k) for x in a]
def solve(a,b):
    """Independent small dense Gaussian elimination, with scaled pivot protection."""
    n=len(b); z=[list(map(float,a[i]))+[float(b[i])] for i in range(n)]
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(z[j][i]))
        if abs(z[pivot][i])<1e-13: raise ValueError('singular matrix')
        z[i],z[pivot]=z[pivot],z[i]; v=z[i][i]
        z[i]=[q/v for q in z[i]]
        for j in range(n):
            if j!=i:
                v=z[j][i]; z[j]=[z[j][k]-v*z[i][k] for k in range(n+1)]
    return [z[i][-1] for i in range(n)]

def month_end(y,m): return dt.date(y,m,calendar.monthrange(y,m)[1])
def months(first,last):
    y,m=first.year,first.month
    while (y,m)<=(last.year,last.month):
        yield month_end(y,m)
        y,m=(y+1,1) if m==12 else (y,m+1)
def yearfrac(a,b): return (b-a).days/365.25
def pv(amount,date,anchor,ke): return amount/(1+ke)**yearfrac(anchor,date)

class ExactProofBudgetExceeded(RuntimeError):pass

def Q(value):
    """Exact rational for the explicitly represented finite-decimal budget.
    This does not claim measured financial source numbers have infinite precision.
    """
    if isinstance(value,float) and not math.isfinite(value):raise ValueError('nonfinite exact input')
    result=value if isinstance(value,Fraction) else Fraction(str(value))
    if max(result.numerator.bit_length(),result.denominator.bit_length())>8192:raise ExactProofBudgetExceeded('exact rational bit-length budget')
    return result

class QuadraticField:
    def __init__(self,radicand):
        self.d=Q(radicand)
        self.operations=0;self.started=time.monotonic()
        if self.d<0:raise ValueError('negative quadratic radicand')
        n=math.isqrt(self.d.numerator);m=math.isqrt(self.d.denominator)
        self.rational_root=Fraction(n,m) if n*n==self.d.numerator and m*m==self.d.denominator else None
    def value(self,a=0,b=0):
        self.operations+=1
        if self.operations>250000 or time.monotonic()-self.started>8:raise ExactProofBudgetExceeded('fixed exact proof operations/time budget')
        return Quadratic(self,Q(a),Q(b))

class Quadratic:
    """a+b*sqrt(d), with exact rational arithmetic and exact order comparison."""
    def __init__(self,field,a,b=Fraction(0)):
        self.field=field;self.a=Q(a);self.b=Q(b)
        if field.rational_root is not None:self.a=Q(self.a+self.b*field.rational_root);self.b=Fraction(0)
    def coerce(self,other):
        if isinstance(other,Quadratic):
            if other.field.d!=self.field.d:raise ValueError('mixed exact fields')
            return other
        return self.field.value(other)
    def __add__(self,other):
        z=self.coerce(other);return self.field.value(self.a+z.a,self.b+z.b)
    __radd__=__add__
    def __neg__(self):return self.field.value(-self.a,-self.b)
    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self
    def __mul__(self,other):
        z=self.coerce(other);return self.field.value(self.a*z.a+self.b*z.b*self.field.d,self.a*z.b+self.b*z.a)
    __rmul__=__mul__
    def __truediv__(self,other):
        z=self.coerce(other);den=z.a*z.a-z.b*z.b*self.field.d
        if den==0:raise ZeroDivisionError('exact algebraic zero denominator')
        return self.field.value((self.a*z.a-self.b*z.b*self.field.d)/den,(self.b*z.a-self.a*z.b)/den)
    def __rtruediv__(self,other):return self.coerce(other)/self
    def __pow__(self,n):
        if not isinstance(n,int) or n<0:raise ValueError('nonnegative integer power required')
        out=self.field.value(1);base=self
        while n:
            if n&1:out=out*base
            n//=2
            if n:base=base*base
        return out
    def zero(self):return self.a==0 and self.b==0
    def sign(self):
        if self.b==0:return (self.a>0)-(self.a<0)
        if self.a==0:return (self.b>0)-(self.b<0)
        sa=(self.a>0)-(self.a<0)
        if self.a*self.b>0:return sa
        delta=self.a*self.a-self.b*self.b*self.field.d
        return sa*((delta>0)-(delta<0))
    def sign_against_rational(self,other):
        # A bounded final comparison, independent of an already exhausted modal
        # decomposition budget. No new symbolic projection is performed.
        a=Q(self.a-Q(other));b=self.b
        if b==0:return (a>0)-(a<0)
        if a==0:return (b>0)-(b<0)
        sa=(a>0)-(a<0)
        if a*b>0:return sa
        delta=a*a-b*b*self.field.d
        return sa*((delta>0)-(delta<0))
    def report(self):return {'rational_part':str(self.a),'sqrt_coefficient':str(self.b)}
    def approximate(self):return float(self.a)+float(self.b)*math.sqrt(float(self.field.d))

def exactify(value):
    if isinstance(value,dict):return {k:exactify(v) for k,v in value.items()}
    if isinstance(value,list):return [exactify(v) for v in value]
    if isinstance(value,(float,int,Fraction)) and not isinstance(value,bool):return Q(value)
    return value

def floatify(value):
    if isinstance(value,Fraction):return float(value)
    if isinstance(value,Quadratic):return value.approximate()
    if isinstance(value,dict):return {k:floatify(v) for k,v in value.items()}
    if isinstance(value,list):return [floatify(v) for v in value]
    return value

def _prepare_exact_certificate(a,state,eigenvalues,field):
    """Prove a state decomposition, never infer it from small floating residuals.
    Projectors are exact in one quadratic field. Repeated-root/Jordan cases not
    covered by the exact affine identity remain INCONCLUSIVE.
    """
    if not (1<=len(state)<=6 and len(a)==len(state) and all(len(row)==len(state) for row in a)):
        return {'kind':'INCONCLUSIVE','state':[Q(v) for v in state],'reason':'outside reviewed at-most-six-dimensional domain'}
    a=[[Q(v) for v in row] for row in a];s=[Q(v) for v in state]
    drift=plus(mv(a,s),scale(s,-1))
    if mv(a,drift)==drift:
        return {'kind':'EXACT_AFFINE','matrix':a,'state':s,'drift':drift,'field':field,'status':'EXACT_IDENTITY_PROVED'}
    roots=[]
    for lam in eigenvalues:
        if lam.sign()<0:return {'kind':'INCONCLUSIVE','state':s,'reason':'negative eigenmode outside monotone certificate domain'}
        if not any((lam-other).zero() for other in roots):
            i=0
            while i<len(roots) and (lam-roots[i]).sign()>0:i+=1
            roots.insert(i,lam)
    # P(A)s=0 with P the product of DISTINCT proposed factors is mandatory.
    v=[field.value(x) for x in s]
    for lam in roots:
        av=mv(a,v);v=[x-lam*y for x,y in zip(av,v)]
    if any(not x.zero() for x in v):
        return {'kind':'INCONCLUSIVE','state':s,'reason':'exact annihilator identity not proved; Jordan component or wrong modes'}
    modes=[]
    for i,lam in enumerate(roots):
        v=[field.value(x) for x in s];den=field.value(1)
        for j,other in enumerate(roots):
            if i==j:continue
            av=mv(a,v);v=[x-other*y for x,y in zip(av,v)];den=den*(lam-other)
        v=[x/den for x in v]
        if any(not (x-lam*y).zero() for x,y in zip(mv(a,v),v)):
            return {'kind':'INCONCLUSIVE','state':s,'reason':'exact modal eigenvector identity not proved'}
        modes.append({'lambda':lam,'vector':v})
    if any(not (sum(mode['vector'][i] for mode in modes)-s[i]).zero() for i in range(len(s))):
        return {'kind':'INCONCLUSIVE','state':s,'reason':'exact modal state reconstruction not proved'}
    return {'kind':'EXACT_MODES','matrix':a,'state':s,'modes':modes,'field':field,'status':'ANNIHILATOR_AND_RECONSTRUCTION_EXACT'}

def prepare_exact_certificate(a,state,eigenvalues,field):
    try:return _prepare_exact_certificate(a,state,eigenvalues,field)
    except ExactProofBudgetExceeded as error:
        return {'kind':'INCONCLUSIVE','state':state,'reason':str(error)}

def _certify_scalar_exact(proof,h):
    """A sufficient all-future certificate with NO floating sign tolerances.
    No nonzero mode is discarded. Failure to prove is INCONCLUSIVE, not a pass.
    The fixed 0..24 exact inequality budget is not a multi-century forecast.
    """
    h=[Q(x) for x in h];s=proof['state'];level=dot(h,s)
    if level<0:return {'ok':False,'status':'PROVEN_NEGATIVE_AT_N','n':0,'exact_value':str(level),'arithmetic':'EXACT'}
    if proof['kind']=='EXACT_AFFINE':
        slope=dot(h,proof['drift'])
        if slope<0:return {'ok':False,'status':'PROVEN_EVENTUALLY_NEGATIVE','exact_affine_level':str(level),'exact_affine_slope':str(slope)}
        return {'ok':True,'status':'CERTIFIED_NONNEGATIVE','method':'EXACT_AFFINE_IDENTITY','exact_level':str(level),'exact_slope':str(slope)}
    if proof['kind']=='INCONCLUSIVE':return {'ok':False,'status':'INCONCLUSIVE','reason':proof['reason']}
    active=[]
    for i,mode in enumerate(proof['modes']):
        coefficient=dot(h,mode['vector'])
        if not coefficient.zero():active.append((coefficient,mode['lambda'],i))
    if not active:return {'ok':True,'status':'CERTIFIED_NONNEGATIVE','method':'EXACT_ZERO_SEQUENCE'}
    dominant,largest,index=active[-1]
    if dominant.sign()<0:
        return {'ok':False,'status':'PROVEN_EVENTUALLY_NEGATIVE','method':'EXACT_NEGATIVE_FASTEST_NONZERO_MODE','mode_index':index,'coefficient':dominant.report()}
    if largest.zero():return {'ok':True,'status':'CERTIFIED_NONNEGATIVE','method':'ONLY_ZERO_MODE_AFTER_PROVED_N0'}
    field=proof['field'];terms=[c for c,lam,i in active]
    for n in range(25):
        value=sum(terms)
        if value.sign()<0:return {'ok':False,'status':'PROVEN_NEGATIVE_AT_N','n':n,'exact_value':value.report(),'arithmetic':'EXACT_Q_SQRT_D'}
        # Divide by largest^n>0. Negative smaller modes increase toward zero;
        # dropping positive terms gives a valid lower bound for every future n.
        bound=dominant
        for coefficient,lam,i in active[:-1]:
            if coefficient.sign()<0:bound=bound+coefficient*(lam/largest)**n
        if bound.sign()>=0:
            return {'ok':True,'status':'CERTIFIED_NONNEGATIVE','method':'EXACT_NORMALIZED_LOWER_BOUND','from_n':n,
                    'lower_bound_sign':bound.sign(),'nonzero_modes':[i for c,lam,i in active],'arithmetic':'EXACT_Q_SQRT_D'}
        terms=[v*lam for v,(c,lam,i) in zip(terms,active)]
    return {'ok':False,'status':'INCONCLUSIVE','reason':'Exact sufficient lower bound not proved within fixed symbolic budget; no economic failure inferred'}

def certify_scalar(proof,h):
    try:return _certify_scalar_exact(proof,h)
    except ExactProofBudgetExceeded as error:return {'ok':False,'status':'INCONCLUSIVE','reason':str(error)}

def tail_calendar_operator(t):
    """Compose the SAME monthly opening-balance earnings and June/December
    declarations into one fiscal-year affine operator. This is not a separate
    annual-opening-balance economic model. State is (1,K,Eg,Em,L,J); E includes
    the common payable claim, while book equity excludes J.
    """
    t=exactify(t)
    g,r,p,u=t['growth'],t['excess_aftertax_yield'],t['payout'],t['incremental_upstream_share']
    rho,rhom,alpha=t['core_group_pre_at1_return'],t['core_parent_pre_at1_return'],t['parent_core_fraction']
    if not (0<=p<=1 and 0<=u<=t['subsidiary_cash_available_fraction']<=1):raise ValueError('unbounded upstream/payout')
    coupons={m:Q(t.get('at1_monthly_coupons',{}).get(str(m),0)) for m in range(1,13)}
    if sum(coupons.values())!=t['at1_coupon']:raise ValueError('tail coupon calendar does not match exact annual total')
    if not (0<=g<=Q('.10') and 0<=r<=Q('.12')):raise ValueError('outside reviewed nonnegative-growth/excess-yield domain')
    monthly_core=Q((1+float(g))**(1/12));annual_rounding_delta=monthly_core**12-(1+g)
    if abs(annual_rounding_delta)>Q('1e-12'):raise ExactProofBudgetExceeded('monthly/annual core-growth rounding bridge outside declared bound')
    core_factors={m:monthly_core**m for m in range(12)};core_factors[12]=1+g
    if any(core_factors[m]<core_factors[m-1] for m in range(1,13)):
        raise ExactProofBudgetExceeded('core-growth rounding profile would imply unreviewed negative general-reserve increment')
    bg=[0,1,1,0,0,-1];bm=[0,alpha,0,1,0,-1]
    cumulative_g=[0]*6;cumulative_m=[0]*6;h1=[0]*6;declarations=[0]*6
    final=[0,0,0,0,p,-1];interim=[0]*6;coupon_so_far=Q(0)
    constraints={'prior_fiscal_final_cash_nonnegative':final,'opening_interim_payable_nonnegative':[0,0,0,0,0,1]};records=[]
    def add_capital(prefix,bg_now,bm_now,core_factor):
        for entity,bv in [('group',bg_now),('parent',bm_now)]:
            cp=t['capital'][entity]
            for tier,extra in [('cet1',0),('tier1',cp['net_at1']),('total',cp['net_at1']+cp['tier2'])]:
                h=list(bv);h[0]+=extra;h[1]-=core_factor*(cp['deduction_per_core']+cp['floors'][tier]*cp['rwa_per_core'])
                constraints[prefix+'_'+entity+'_'+tier]=h
                if 'weight_rwa_per_core' in cp:
                    wx=0 if tier=='cet1' else cp['net_at1']+(cp['weight_tier2'] if tier=='total' else 0)
                    wh=list(bv);wh[0]+=wx;wh[1]-=core_factor*(cp['deduction_per_core']+cp['parallel_reg_floors'][tier]*cp['weight_rwa_per_core'])
                    constraints[prefix+'_'+entity+'_parallel_'+tier]=wh
            h=list(bv);h[0]+=cp['net_at1'];h[1]-=core_factor*(cp['deduction_per_core']+cp['floors']['leverage']*cp['exposure_per_core'])
            constraints[prefix+'_'+entity+'_leverage_'+cp['exposure_status']]=h
    add_capital('opening',bg,bm,1)
    for month in range(1,13):
        previous_core=core_factors[month-1];current_core=core_factors[month]
        grossg=plus([0,rho/12,0,0,0,0],scale(plus(bg,[0,-previous_core,0,0,0,0]),r/12))
        ownm=plus([0,rhom/12,0,0,0,0],scale(plus(bm,[0,-alpha*previous_core,0,0,0,0]),r/12))
        gap=plus(grossg,scale(ownm,-1))
        grossm=plus(ownm,scale(gap,u))
        pg=plus(grossg,[-coupons[month],0,0,0,0,0]);pm=plus(grossm,[-coupons[month],0,0,0,0,0])
        cumulative_g=plus(cumulative_g,pg);cumulative_m=plus(cumulative_m,pm)
        if month<=6:h1=plus(h1,pg)
        bg=plus(bg,pg);bm=plus(bm,pm);coupon_so_far+=coupons[month]
        declared=[0]*6
        if month==6:declared=final
        elif month==12:
            interim=scale(h1,p);declared=interim
        bg=plus(bg,scale(declared,-1));bm=plus(bm,scale(declared,-1));declarations=plus(declarations,declared)
        prefix='month_'+str(month)
        add_capital(prefix,bg,bm,current_core)
        # These are sufficient within-year pool-increment conditions. They do not
        # consume or relabel the large opening legal/funding buffers as new cash.
        pre_at1_parent=plus(cumulative_m,[coupon_so_far,0,0,0,0,0])
        legal=plus(plus(cumulative_m,scale(pre_at1_parent,-t['statutory_rate'])),scale(declarations,-1))
        legal[1]-=(current_core-1)*t['parent_general_reserve_per_core']
        funding=plus(scale(pre_at1_parent,t['liquidity_budget_fraction']),[-coupon_so_far,0,0,0,0,0])
        funding=plus(funding,scale(declarations,-1))
        constraints[prefix+'_parent_legal_increment_after_reserves_declarations']=legal
        constraints[prefix+'_parent_funding_increment_after_declarations']=funding
        constraints[prefix+'_parent_pre_at1_cumulative_profit']=pre_at1_parent
        constraints[prefix+'_parent_pre_at1_monthly_profit_for_funding_branch']=grossm
        constraints[prefix+'_group_parent_gap_before_extra_upstream']=gap
        records.append({'month':month,'group_profit_vector':pg,'parent_profit_vector':pm,
                        'group_book_vector':list(bg),'parent_book_vector':list(bm),'declaration_vector':list(declared),
                        'parent_legal_increment_vector':legal,'parent_funding_increment_vector':funding})
    a=[[Q(int(i==j)) for j in range(6)] for i in range(6)];a[1]=[0,1+g,0,0,0,0]
    a[2]=plus(plus(bg,interim),[0,-(1+g),0,0,0,0])
    a[3]=plus(plus(bm,interim),[0,-alpha*(1+g),0,0,0,0])
    a[4]=cumulative_g;a[5]=interim
    constraints['annual_common_profit']=cumulative_g;constraints['annual_parent_common_profit']=cumulative_m
    constraints['next_interim_cash_nonnegative']=interim
    # Eigenvalues retain a closed form. Put z=(1+r/12)^6. The group (Eg,L,J)
    # block has one zero root, trace z^2-2p(z-1), and second elementary coefficient
    # p^2(z-1)^2; the parent-vs-group difference compounds monthly at 1+(1-u)r/12.
    z=(1+r/12)**6;trace=z*z-2*p*(z-1);determinant=p*p*(z-1)*(z-1)
    disc=trace*trace-4*determinant
    if disc<0:raise ValueError('complex tail mode')
    field=QuadraticField(disc)
    exact_eigen=[field.value(1),field.value(1+g),field.value(trace/2,Q('0.5')),field.value(trace/2,Q('-0.5')),field.value((1+(1-u)*r/12)**12),field.value(0)]
    eigen=[lam.approximate() for lam in exact_eigen]
    # Historical annual-opening approximation retained ONLY as a transparent
    # first-year bridge, never as the adopted tail or another value endpoint.
    s=t['state'];c=t['at1_coupon']
    old_pg=-c+rho*s[1]+r*(s[2]-s[5])
    old_pm=-c+((1-u)*rhom+u*rho)*s[1]+u*r*s[2]+(1-u)*r*s[3]-r*s[5]
    old_j=p*(.5*old_pg+.5*c-t['at1_h1_coupon'])
    next_state=mv(a,s)
    bridge={'status':'EXACT_MONTHLY_COMPOSITION_ADOPTED_OLD_ANNUAL_BUDGET_COMPARISON_ONLY',
            'old_annual_opening_group_profit':old_pg,'monthly_group_profit':dot(cumulative_g,s),
            'old_annual_opening_parent_profit':old_pm,'monthly_parent_profit':dot(cumulative_m,s),
            'old_equal_halfyear_interim':old_j,'monthly_interim':dot(interim,s),
            'group_profit_delta':dot(cumulative_g,s)-old_pg,'parent_profit_delta':dot(cumulative_m,s)-old_pm,
            'interim_delta':dot(interim,s)-old_j,'monthly_h1_group_profit':dot(h1,s),
            'monthly_group_book_end':dot(bg,s),'monthly_parent_book_end':dot(bm,s),
            'next_july_final_cash':p*next_state[4]-next_state[5]}
    result=floatify({'matrix':a,'eigenvalues':eigen,'constraints':constraints,'annual_profit_vector':cumulative_g,'core_growth_factors':core_factors,
            'annual_parent_profit_vector':cumulative_m,'monthly_vectors':records,'calendar_bridge':bridge})
    result.update(_exact_matrix=a,_exact_state=t['state'],_exact_constraints=constraints,_exact_eigenvalues=exact_eigen,_exact_field=field,
                  exact_core_growth_rounding_delta=str(annual_rounding_delta),exact_core_growth_rounding_bound='1e-12 relative per annual closure')
    return result

def tail_two_year_bridge(t,op):
    """Two fiscal years only: quantify the replaced convention, not a second
    adopted valuation. Both columns keep Jan/July cash and actual coupon months.
    """
    output={};g=t['growth'];p=t['payout'];alpha=t['parent_core_fraction'];c=t['at1_coupon']
    for method in ['adopted_monthly','old_annual_opening_reference']:
        s=list(t['state']);legal_open=t['parent_legal_profit_pool'];funding_open=t['free_dividend_funding_budget'];years=[]
        for year in [1,2]:
            K=s[1];bg0=K+s[2]-s[5];bm0=alpha*K+s[3]-s[5];final=p*s[4]-s[5]
            if method=='adopted_monthly':
                pg=dot(op['annual_profit_vector'],s);pm=dot(op['annual_parent_profit_vector'],s);nxt=mv(op['matrix'],s);newj=nxt[5]
            else:
                r=t['excess_aftertax_yield'];u=t['incremental_upstream_share'];rho=t['core_group_pre_at1_return'];rhom=t['core_parent_pre_at1_return']
                pg=-c+rho*K+r*(s[2]-s[5]);pm=-c+((1-u)*rhom+u*rho)*K+u*r*s[2]+(1-u)*r*s[3]-r*s[5]
                newj=p*(.5*pg+.5*c-t['at1_h1_coupon'])
                nxt=[1,K*(1+g),s[2]+pg-p*s[4]-g*K,s[3]+pm-p*s[4]-alpha*g*K,pg,newj]
            month_rows=[];coupon_sum=0.0;decl_sum=0.0;pgsum=pmsum=0.0
            for m in range(1,13):
                coupon=float(t.get('at1_monthly_coupons',{}).get(str(m),0.0));coupon_sum+=coupon
                declared=final if m==6 else newj if m==12 else 0.0;decl_sum+=declared
                if method=='adopted_monthly':
                    row=op['monthly_vectors'][m-1];bg=dot(row['group_book_vector'],s);bm=dot(row['parent_book_vector'],s)
                    pgsum+=dot(row['group_profit_vector'],s);pmsum+=dot(row['parent_profit_vector'],s)
                else:
                    pgsum=m/12*(pg+c)-coupon_sum;pmsum=m/12*(pm+c)-coupon_sum
                    bg=bg0+pgsum-decl_sum;bm=bm0+pmsum-decl_sum
                km=K*(op['core_growth_factors'][m] if method=='adopted_monthly' else (1+g)**(m/12))
                legal=legal_open+pmsum-t['statutory_rate']*(pmsum+coupon_sum)-(km-K)*t['parent_general_reserve_per_core']-decl_sum
                funding=funding_open+t['liquidity_budget_fraction']*(pmsum+coupon_sum)-coupon_sum-decl_sum
                capital={}
                for e,cp in t['capital'].items():
                    capital[e]={'rwa':cp['rwa_per_core']*km,'deduction':cp['deduction_per_core']*km,'net_at1':cp['net_at1'],'tier2':cp['tier2'],
                                'exposure':cp['exposure_per_core']*km,'exposure_status':cp['exposure_status']}
                    if 'weight_rwa_per_core' in cp:
                        capital[e].update(weight_rwa=cp['weight_rwa_per_core']*km,weight_tier2=cp['weight_tier2'],parallel_reg_floors=cp['parallel_reg_floors'])
                headroom,ratios=capital_capacity({'bg':bg,'bm':bm},capital,t['capital']['group']['floors'])
                month_rows.append({'month':m,'core_capital':km,'group_common_book':bg,'parent_common_book':bm,'at1_cash':coupon,
                                   'ordinary_declaration':declared,'ordinary_cash_paid':s[5] if m==1 else final if m==7 else 0.0,
                                   'ordinary_payable':final if m==6 else newj if m==12 else 0.0,'parent_legal_pool':legal,'parent_free_funding_budget':funding,
                                   'minimum_capital_headroom':headroom,'group_cet1_ratio':ratios['group']['cet1'],'parent_cet1_ratio':ratios['parent']['cet1']})
            years.append({'future_fiscal_year_index':year,'opening_state':s,'closing_state':nxt,'group_common_profit':pg,'parent_common_profit':pm,
                          'h1_group_common_profit':newj/p if p else None,'january_cash':s[5],'july_cash':final,'december_interim_declaration':newj,
                          'parent_legal_open':legal_open,'parent_funding_open':funding_open,'monthly_bridge':month_rows})
            s=nxt;legal_open=month_rows[-1]['parent_legal_pool'];funding_open=month_rows[-1]['parent_free_funding_budget']
        output[method]=years
    output['status']='OLD_CONVENTION_COMPARISON_ONLY_NOT_AN_ALTERNATIVE_ADOPTED_VALUE'
    return output

def prepare_tail_analysis(t):
    """One bounded certificate preparation shared by the two discount rates.
    Preconditions select the same branches used in the explicit cash ledger.
    """
    if Q(t['parent_legal_profit_pool'])<0 or Q(t['free_dividend_funding_budget'])<0:
        return {'op':None,'status':'PROVEN_NEGATIVE_INITIAL_POOL','reason':'negative represented opening legal/funding pool'}
    if Q(t.get('parent_loss_carry',0))!=0:
        return {'op':None,'status':'INCONCLUSIVE','reason':'positive opening loss carry requires separate piecewise legal-reserve path'}
    if Q(t.get('opening_reserved_cash',t['state'][5]))!=Q(t['state'][5]):
        return {'op':None,'status':'INCONCLUSIVE','reason':'opening payable not exactly matched by previously earmarked funding'}
    try:
        op=tail_calendar_operator(t)
        proof=prepare_exact_certificate(op['_exact_matrix'],op['_exact_state'],op['_exact_eigenvalues'],op['_exact_field'])
        certificates={k:certify_scalar(proof,h) for k,h in op['_exact_constraints'].items()}
    except ExactProofBudgetExceeded as error:return {'op':None,'status':'INCONCLUSIVE','reason':str(error)}
    counts={}
    for cert in certificates.values():counts[cert['status']]=counts.get(cert['status'],0)+1
    exact_record={'domain':'CURRENT_SIX_STATE_MONTHLY_BUDGET_AND_DECLARED_HAND_CASES_ONLY',
                  'rational_representation':'Fraction of displayed finite-decimal budget; no claim of exact source measurement',
                  'quadratic_radicand':str(op['_exact_field'].d),'exact_matrix':[[str(v) for v in row] for row in op['_exact_matrix']],
                  'exact_state':[str(v) for v in op['_exact_state']],
                  'exact_constraints':{k:[str(v) for v in h] for k,h in op['_exact_constraints'].items()},
                  'exact_modes':[lam.report() for lam in op['_exact_eigenvalues']],
                  'decomposition_status':proof.get('status',proof.get('reason',proof['kind'])),'certificate_status_counts':counts,
                  'symbolic_limit':{'rational_bits':8192,'field_constructions':250000,'seconds_per_analysis':8,'finite_inequality_steps':25},
                  'runtime_observation':{'field_constructions':op['_exact_field'].operations,'seconds_at_certificate_end':time.monotonic()-op['_exact_field'].started},
                  'core_annual_rounding_delta':op['exact_core_growth_rounding_delta'],'core_annual_rounding_bound':op['exact_core_growth_rounding_bound']}
    return {'op':op,'certificates':certificates,'exact_proof':exact_record,'status':'CERTIFICATES_PREPARED_NOT_ECONOMIC_VALIDATION'}

def tail_value(t,ke,prepared=None):
    """Exact composition of monthly budgets; closed sum of future Jan/July cash.
    All monthly capital/legal/funding conditions are sufficient certificates,
    not claims that company monthly earnings or liquidity are publicly disclosed.
    """
    analysis=prepare_tail_analysis(t) if prepared is None else prepared
    if analysis['op'] is None:return {'value':None,'feasible':False,'status':analysis['status'],'reason':analysis['reason'],'certificates':{}}
    op=analysis['op'];a=op['matrix'];eigen=op['eigenvalues'];s=t['state'];p=t['payout']
    if any(lam.sign_against_rational(1+Q(ke))>=0 for lam in op['_exact_eigenvalues']):
        return {'value':None,'feasible':False,'status':'NO_TRANSVERSALITY','certificates':analysis['certificates']}
    f1,f2=t['interim_payment_year_fraction'],t['final_payment_year_fraction']
    d=[0,0,0,0,p/(1+ke)**f2,(1/(1+ke)**f1-1/(1+ke)**f2)]
    sys=[[float(i==j)-a[i][j]/(1+ke) for j in range(6)] for i in range(6)]
    value=dot(d,solve(sys,s))
    certificates=analysis['certificates']
    ok=all(x['ok'] for x in certificates.values()) and Q(t['parent_legal_profit_pool'])>=0 and Q(t['free_dividend_funding_budget'])>=0
    statuses=[x['status'] for x in certificates.values()]
    status='CERTIFIED_BUDGET_PATH' if ok else 'PROVEN_NEGATIVE_CONSTRAINT_IN_REPRESENTED_BUDGET' if any(x.startswith('PROVEN_') for x in statuses) else 'INCONCLUSIVE'
    return {'value':value if ok else None,'unconstrained_value_for_diagnosis_only':value,'feasible':ok,
            'status':status,'certificates':certificates,'exact_proof':analysis['exact_proof'],'matrix':a,'state':s,'eigenvalues':eigen,'dividend_discount_vector':d,
            'annual_profit_vector':op['annual_profit_vector'],'annual_parent_profit_vector':op['annual_parent_profit_vector'],
            'calendar_bridge':op['calendar_bridge'],'monthly_vectors':op['monthly_vectors'],
            'two_year_calendar_bridge':tail_two_year_bridge(t,op),
            'capital_status':'parent leverage includes declared proxy limitation'}

def coupon_for_year(year,notes,reset_yield,fee_rate):
    payments={m:0.0 for m in range(1,13)};fees={m:0.0 for m in range(1,13)}
    for n in notes:
        # At first call/reset, equal principal replacement is a forecast, NOT an
        # exercised redemption. Later resets continue the same perpetual without
        # another issuance. New constant-budget coupon begins next payment year.
        rate=n['coupon'] if year<=n['first_reset_year'] else reset_yield
        if year>=n['first_payment_year']:payments[n['payment_month']]+=n['principal']*rate
        if year==n['first_reset_year']:fees[n['payment_month']]+=n['principal']*fee_rate+n.get('redemption_book_discount',0)
    return payments,fees

def operating_plan(inp,scenario):
    """Returns fiscal-quarter/year pre-AT1 net profit, not externally observed forecasts."""
    result={}; q=copy.deepcopy(inp['q4_2026_budget']); ov=scenario.get('q4_override',{});q.update(ov)
    def compute(row,fraction):
        nii=row['average_earning_assets']*row['nim']*fraction
        revenue=nii+row['net_fees']+row['other_net_income']
        expense=row.get('opex_absolute',revenue*row.get('cost_income_ratio',0))
        loanloss=row['average_loans']*row['loan_credit_cost']*fraction
        pretax=revenue-expense-row['surtax']-row['other_business_cost']-loanloss-row['nonloan_impairment']
        net=pretax*(1-row['effective_tax'])-row['minority_profit']
        return dict(row,net_interest_income=nii,revenue=revenue,opex=expense,loan_impairment=loanloss,pretax=pretax,
                    group_pre_at1_net_profit=net,parent_pre_at1_core_net_profit=net*row['parent_core_share'])
    result[2026]=compute(q,.25)
    last=copy.deepcopy(inp['forecast_2027'])
    for year in range(2027,inp['explicit_last_year']+1):
        schedule=copy.deepcopy(inp['annual_assumptions'][str(year)]);schedule.update(scenario.get('annual_overrides',{}).get(str(year),{}))
        if year==2027:
            factors=scenario.get('initial_2027_level_factors',{})
            for field,factor in factors.items():last[field]*=factor
            last.update(scenario.get('initial_2027_levels',{}))
        if year>2027:
            last['average_earning_assets']*=1+schedule['earning_asset_growth'];last['average_loans']*=1+schedule['loan_growth']
            last['net_fees']*=1+schedule['fee_growth'];last['other_net_income']*=1+schedule['other_income_growth']
            last['other_business_cost']*=1+schedule['other_income_growth'];last['nonloan_impairment']*=1+schedule['earning_asset_growth'];last['minority_profit']*=1+schedule['earning_asset_growth']
        for k in ['nim','loan_credit_cost','cost_income_ratio','parent_core_share','effective_tax']:
            if k in schedule:last[k]=schedule[k]
        last['nim']+=scenario.get('parallel_nim_delta',0)
        last['loan_credit_cost']+=scenario.get('parallel_credit_cost_delta',0)
        last['surtax']=(last['average_earning_assets']*last['nim']+last['net_fees']+last['other_net_income'])*inp['surtax_revenue_fraction']
        # Preserve the actually used shocked NIM/credit cost in the output, rather
        # than overwriting them with the unshocked schedule after calculating P&L.
        result[year]=dict(compute(last,1.0),**{k:v for k,v in schedule.items() if k not in last})
    return result

def settle_payment(group_book,parent_book,payable,reserved_cash,amount):
    if amount>payable+EPS or amount>reserved_cash+EPS:raise ValueError('unfunded payable')
    return group_book,parent_book,payable-amount,reserved_cash-amount

def approve_dividend(desired,legal,capital,funding):
    return max(0.0,min(desired,max(0.0,legal),max(0.0,capital),max(0.0,funding)))

def statutory_appropriation(net_profit,opening_loss,rate):
    return rate*max(0.0,net_profit-opening_loss),max(0.0,opening_loss-net_profit)

def capital_capacity(st,capital,floors):
    caps=[];ratios={}
    for e,b in [('group',st['bg']),('parent',st['bm'])]:
        c=capital[e];cet=b-c['deduction'];t1=cet+c['net_at1'];total=t1+c['tier2']
        ratios[e]={'cet1':cet/c['rwa'],'tier1':t1/c['rwa'],'total':total/c['rwa'],'leverage':t1/c['exposure'],
                   'exposure_status':c['exposure_status']}
        caps.extend([cet-floors['cet1']*c['rwa'],t1-floors['tier1']*c['rwa'],total-floors['total']*c['rwa'],t1-floors['leverage']*c['exposure']])
        if 'weight_rwa' in c:
            wf=c['parallel_reg_floors'];wt=t1+c['weight_tier2']
            ratios[e]['weight_method']={'cet1':cet/c['weight_rwa'],'tier1':t1/c['weight_rwa'],'total':wt/c['weight_rwa']}
            caps.extend([cet-wf['cet1']*c['weight_rwa'],t1-wf['tier1']*c['weight_rwa'],wt-wf['total']*c['weight_rwa']])
    return min(caps),ratios

def simulate(inp,scenario):
    plan=operating_plan(inp,scenario);o=inp['opening_20260930'];asof=dt.date.fromisoformat(inp['valuation_date'])
    st={'bg':o['group_common_equity'],'bm':o['parent_common_equity'],'up':o['parent_retained_profit'],
        'statutory_total_lower_bound':o['statutory_known_lower_bound'],'surplus_total':o['parent_surplus_total'],
        'general':o['parent_general_reserve'],'funding':inp['initial_dividend_funding_budget'],'loss_carry':0.0,
        'kg':o['group_common_equity'],'km':o['parent_common_equity'],'reserved_cash':0.0}
    cap=copy.deepcopy(inp['capital_opening']);floors=copy.deepcopy(inp['capital_floors']);floors.update(scenario.get('capital_floors',{}))
    for e in cap:
        # Only the ratio itself is disclosed exactly to 2 decimals. Inferred RWA
        # is labelled approximate and separately tested at its rounding bounds.
        advanced_mid=cap[e]['cet1_net']/cap[e]['reported_cet1_ratio'];weight_mid=cap[e]['cet1_net']/cap[e]['reported_weight_cet1_ratio']
        cap[e]['rwa']=advanced_mid*(1+scenario.get('rwa_rounding_stress',0))
        cap[e]['weight_rwa']=weight_mid*(1+scenario.get('rwa_rounding_stress',0))
        # A denominator stress cannot manufacture new Tier2 capital by reusing
        # the reported total ratio against the stressed denominator.
        cap[e]['weight_tier2']=cap[e]['reported_weight_total_ratio']*weight_mid-cap[e]['cet1_net']-cap[e]['net_at1']
    pending=[];events=[];ledger=[];fiscal={};snapshots={};violations=[];declared={}
    olddate=dt.date(2026,9,30);fp=o['ytd_group_common_profit'];mp=o['ytd_parent_net_profit'];h1=o['h1_group_common_profit'];gen_start=st['general'];loss_start=0.0
    cash_total=0.0;declaration_total=0.0;common_income_total=0.0;capital_fee_total=0.0;oci_total=0.0
    for date in months(dt.date(2026,10,1),dt.date(inp['explicit_last_year'],12,31)):
        y,m=date.year,date.month;row=plan[y]
        if m==1:fp=mp=h1=0.0;gen_start=st['general'];loss_start=st['loss_carry']
        p=scenario['payout_by_year'].get(str(y),scenario['terminal_payout'])
        upstream_share=scenario['upstream_by_year'].get(str(y),scenario['terminal_upstream_share'])
        if upstream_share>inp['subsidiary_cash_available_fraction']+EPS:raise ValueError('unsupported unlimited subsidiary upstream')
        coupons,fees=coupon_for_year(y,inp['at1_notes'],scenario['at1_reset_yield'],inp['at1_refinancing_fee_rate'])
        frac=1/3 if y==2026 else 1/12
        eg=st['bg']-st['kg'];em=st['bm']-st['km']
        coreg=row['group_pre_at1_net_profit']*frac;corem=row['parent_pre_at1_core_net_profit']*frac
        extra_g=scenario['excess_aftertax_yield']*eg/12;extra_m=scenario['excess_aftertax_yield']*em/12
        grossg=coreg+extra_g;ownm=corem+extra_m
        gap=max(grossg-ownm,0.0);upstream=upstream_share*gap
        grossm=ownm+upstream
        profitg=grossg-coupons[m];profitm=grossm-coupons[m]
        fee=fees[m];old=copy.deepcopy(st);old_pending=sum(x['amount'] for x in pending)
        at1_book_step=sum(n.get('redemption_book_discount',0) for n in inp['at1_notes'] if n['first_reset_year']==y and n['payment_month']==m)
        for e in cap:cap[e]['net_at1']+=at1_book_step
        oci=scenario.get('oci_shocks',{}).get(date.isoformat(),{'group':0.0,'parent':0.0})
        st['bg']+=profitg-fee+oci['group'];st['bm']+=profitm-fee+oci['parent'];st['up']+=profitm
        oci_total+=oci['group']
        liq=scenario.get('liquidity_budget_fraction',inp['liquidity_budget_fraction'])
        st['funding']+=(liq*grossm if grossm>=0 else grossm)-coupons[m]-fee
        shock=scenario.get('funding_shocks',{}).get(date.isoformat(),0.0);st['funding']-=shock
        fp+=profitg;mp+=grossm
        if m<=6:h1+=profitg
        common_income_total+=profitg;capital_fee_total+=fee
        growth=row.get('rwa_growth',inp['q4_2026_rwa_growth']);gmonth=(1+growth)**(1/12)
        for e in cap:
            cap[e]['rwa']*=gmonth;cap[e]['weight_rwa']*=gmonth;cap[e]['exposure']*=(1+row.get('exposure_growth',growth))**(1/12)
            cap[e]['deduction']*=(1+row.get('deduction_growth',growth))**(1/12)
        st['kg']*=gmonth;st['km']*=gmonth
        statutory_rate=0.0 if y>=scenario.get('statutory_stop_from_year',9999) else scenario.get('statutory_rate',inp['statutory_rate'])
        pending_stat,forecast_loss=statutory_appropriation(mp,loss_start,statutory_rate)
        gg=row.get('general_reserve_growth',growth)
        # 2026 YTD report contains no new parent general reserve; full year's
        # appropriation is forecast from the prior-year balance at year end.
        target_general=gen_start*(1+gg)**(m/12)
        pending_gen=max(0.0,target_general-st['general'])
        if m==12:
            st['up']-=pending_stat+pending_gen;st['surplus_total']+=pending_stat;st['statutory_total_lower_bound']+=pending_stat;st['general']+=pending_gen
            st['loss_carry']=forecast_loss;pending_stat=pending_gen=0.0
            fiscal[y]={'group_common_profit':fp,'parent_net_profit':mp,'h1_group_common_profit':h1,'payout_budget':p,
                       'other_equity_distribution':(o['ytd_other_equity_distribution']+sum(v for mo,v in coupons.items() if mo>=10)) if y==2026 else sum(coupons.values()),
                       'other_equity_distribution_status':'2026 actual YTD includes redeemed preference; future AT1 only' if y==2026 else 'AT1 budget only',
                       'upstream_budget_share':upstream_share}
        # Pay already declared obligations. Funding was reserved on declaration;
        # payment reduces reserved cash/payable, not equity a second time.
        paid=0.0
        for item in list(pending):
            if item['pay_date']==date:
                st['bg'],st['bm'],remaining_payable,st['reserved_cash']=settle_payment(st['bg'],st['bm'],sum(v['amount'] for v in pending),st['reserved_cash'],item['amount'])
                paid+=item['amount'];cash_total+=item['amount'];pending.remove(item)
                assert abs(remaining_payable-sum(v['amount'] for v in pending))<1e-5
                events.append({'date':date.isoformat(),'kind':'ordinary_cash_paid_budget','amount':item['amount'],'fiscal_year':item['fiscal_year'],'part':item['part']})
        desired=0.0;part=None;fy=None
        if m==12:
            desired=max(0.0,p*h1);part='interim';fy=y
        elif m==6 and y-1 in fiscal:
            fy=y-1;prior=fiscal[fy];desired=max(0.0,prior['payout_budget']*prior['group_common_profit']-declared.get((fy,'interim'),0.0));part='final'
        declared_now=0.0;cap_avail,ratios=capital_capacity(st,cap,floors)
        if part:
            legal=max(0.0,st['up']-pending_stat-pending_gen)
            declared_now=approve_dividend(desired,legal,cap_avail,st['funding'])
            st['bg']-=declared_now;st['bm']-=declared_now;st['up']-=declared_now;st['funding']-=declared_now;st['reserved_cash']+=declared_now
            declared[(fy,part)]=declared_now;declaration_total+=declared_now
            paydate=month_end(y+1,1) if part=='interim' else month_end(y,7)
            pending.append({'amount':declared_now,'pay_date':paydate,'fiscal_year':fy,'part':part})
            events.append({'date':date.isoformat(),'kind':'ordinary_declaration_budget_not_announced','amount':declared_now,'desired':desired,
                           'fiscal_year':fy,'part':part,'pay_date':paydate.isoformat(),'legal_capacity':legal,'capital_capacity':cap_avail})
        cap_after,ratios=capital_capacity(st,cap,floors)
        if cap_after<-EPS:violations.append({'date':date.isoformat(),'kind':'capital_requires_operating_or_funding_replan','shortfall':-cap_after})
        if st['funding']<-EPS:violations.append({'date':date.isoformat(),'kind':'normal_dividend_funding_budget_exhausted','shortfall':-st['funding']})
        new_pending=sum(x['amount'] for x in pending)
        # Exact common-equity vs cumulative-dividend-claim conservation.
        expected=old['bg']+old_pending+profitg-fee-paid+oci['group']
        if abs(st['bg']+new_pending-expected)>1e-5:raise AssertionError('common claim cash conservation')
        if abs(st['bm']-(old['bm']+profitm-fee-declared_now+oci['parent']))>1e-5:raise AssertionError('parent common bridge')
        rec={'date':date.isoformat(),'state':copy.deepcopy(st),'group_common_profit':profitg,'parent_common_profit':profitm,
             'parent_net_profit_before_at1':grossm,'incremental_subsidiary_upstream_budget':upstream,'at1_cash':coupons[m],
             'capital_fee':fee,'group_oci':oci['group'],'parent_oci':oci['parent'],'ordinary_declared':declared_now,'ordinary_paid':paid,'ordinary_payable':new_pending,
             'pending_statutory':pending_stat,'pending_general':pending_gen,'capital':copy.deepcopy(cap),'capital_ratios':ratios,
             'capital_capacity':cap_after,'ordinary_cumdiv_claim':st['bg']+new_pending}
        rec['parent_common_equity_components']={'retained_profit':st['up'],'surplus_total':st['surplus_total'],'general_reserve':st['general'],
                                                'other_common_components':st['bm']-st['up']-st['surplus_total']-st['general']}
        ledger.append(rec)
        if date==asof or (m==10 and y in range(asof.year+1,asof.year+6)):snapshots[date.isoformat()]=copy.deepcopy(rec)
        olddate=date
    # Source Q3 ordinary book roll-forward must be distinct from cash already paid before the anchor.
    assert abs(st['bg']-(o['group_common_equity']+common_income_total+oci_total-capital_fee_total-declaration_total))<1e-4
    assert abs(declaration_total-cash_total-sum(x['amount'] for x in pending))<1e-4
    last=ledger[-1];K=st['kg'];J=last['ordinary_payable'];lastplan=plan[inp['explicit_last_year']]
    lastcoupons,_=coupon_for_year(inp['explicit_last_year']+1,inp['at1_notes'],scenario['at1_reset_yield'],inp['at1_refinancing_fee_rate'])
    tailcap={}
    for e,c in cap.items():
        tailcap[e]={'rwa_per_core':c['rwa']/K,'deduction_per_core':c['deduction']/K,'net_at1':c['net_at1'],'tier2':c['tier2'],
                    'exposure_per_core':c['exposure']/K,'exposure_status':c['exposure_status'],'floors':floors,
                    'weight_rwa_per_core':c['weight_rwa']/K,'weight_tier2':c['weight_tier2'],'parallel_reg_floors':c['parallel_reg_floors']}
    tail={'growth':scenario['terminal_growth'],'excess_aftertax_yield':scenario['excess_aftertax_yield'],
          'payout':scenario['terminal_payout'],'incremental_upstream_share':scenario['terminal_upstream_share'],
          'subsidiary_cash_available_fraction':inp['subsidiary_cash_available_fraction'],
          'core_group_pre_at1_return':lastplan['group_pre_at1_net_profit']*(1+scenario['terminal_growth'])/K,
          'core_parent_pre_at1_return':lastplan['parent_pre_at1_core_net_profit']*(1+scenario['terminal_growth'])/K,'parent_core_fraction':st['km']/K,
          'at1_coupon':sum(lastcoupons.values()),'at1_h1_coupon':sum(v for m,v in lastcoupons.items() if m<=6),'at1_max_month_coupon':max(lastcoupons.values()),
          'at1_monthly_coupons':{str(m):v for m,v in lastcoupons.items()},
          'state':[1,K,st['bg']+J-K,st['bm']+J-st['km'],fiscal[inp['explicit_last_year']]['group_common_profit'],J],
          'capital':tailcap,'statutory_rate':statutory_rate,
          'parent_general_reserve_per_core':st['general']/K,'parent_legal_profit_pool':st['up'],
          'parent_loss_carry':st['loss_carry'],'opening_reserved_cash':st['reserved_cash'],
          'free_dividend_funding_budget':st['funding'],'liquidity_budget_fraction':liq,
          'interim_payment_year_fraction':31/365.25,'final_payment_year_fraction':212/365.25}
    cash=[e for e in events if e['kind']=='ordinary_cash_paid_budget' and dt.date.fromisoformat(e['date'])>asof]
    anchor=snapshots[asof.isoformat()];year5=dt.date(asof.year+5,asof.month,asof.day)
    distributions=[]
    for n in range(1,6):
        lo=dt.date(asof.year+n-1,asof.month,asof.day);hi=dt.date(asof.year+n,asof.month,asof.day)
        distributions.append(sum(e['amount'] for e in cash if lo<dt.date.fromisoformat(e['date'])<=hi)/inp['shares_million'])
    values={};tail_analysis=prepare_tail_analysis(tail)
    for ke in scenario['equity_costs']:
        tv=tail_value(tail,ke,tail_analysis);feasible=tv['feasible'] and not violations
        lastdate=dt.date.fromisoformat(last['date']);v0=v5=ri=None
        if feasible:
            v0=sum(pv(e['amount'],dt.date.fromisoformat(e['date']),asof,ke) for e in cash)+pv(tv['value'],lastdate,asof,ke)
            v5=sum(pv(e['amount'],dt.date.fromisoformat(e['date']),year5,ke) for e in cash if dt.date.fromisoformat(e['date'])>year5)+pv(tv['value'],lastdate,year5,ke)
            # RI/DDM equality is an arithmetic check, not independent economic evidence.
            ri=anchor['ordinary_cumdiv_claim'];prev=anchor;prevdate=asof
            for rec in ledger:
                date=dt.date.fromisoformat(rec['date'])
                if date<=asof:continue
                period_ke=(1+ke)**yearfrac(prevdate,date)-1
                comprehensive=rec['group_common_profit']-rec['capital_fee']+rec['group_oci']
                residual=comprehensive-period_ke*prev['ordinary_cumdiv_claim']
                ri+=pv(residual,date,asof,ke);prev=rec;prevdate=date
            ri+=pv(tv['value']-last['ordinary_cumdiv_claim'],lastdate,asof,ke)
            if abs(ri-v0)>1e-4:raise AssertionError('same-path RI/DDM identity')
        values[str(ke)]={'feasible':feasible,'current_per_share':None if v0 is None else v0/inp['shares_million'],
                        'path_status':'EXPLICIT_PATH_VIOLATION' if violations else tv['status'],
                        'tail_certificate_status':tv['status'],'tail_certificate_status_counts':tv.get('exact_proof',{}).get('certificate_status_counts',{}),
                        'year5_terminal_per_share':None if v5 is None else v5/inp['shares_million'],
                        'same_path_ri_per_share':None if ri is None else ri/inp['shares_million'],
                        'tail_current_value_share':None if v0 is None else pv(tv['value'],lastdate,asof,ke)/v0,'tail':tv}
    # Auxiliary normalized P/B is a deliberately different economic benchmark:
    # all book earns the stated ROE and payout equals 1-g/ROE immediately. It is
    # NOT used in core DDM, not a second proof of its capital/cash feasibility.
    pb_reference=[]
    for roe in inp['auxiliary_pb_normalized_roe_grid']:
        g=scenario['terminal_growth']
        for ke in scenario['equity_costs']:
            pb_reference.append({'normalized_all_book_roe':roe,'growth':g,'equity_cost':ke,'implied_payout':1-g/roe,
                                 'justified_pb':(roe-g)/(ke-g),'reference_per_share':anchor['state']['bg']/inp['shares_million']*(roe-g)/(ke-g),
                                 'status':'COUNTERFACTUAL_BENCHMARK_NOT_CORE_VALUE_OR_INDEPENDENT_CAPITAL_PROOF'})
    annual_economics=[];december={int(rec['date'][:4]):rec for rec in ledger if rec['date'][5:7]=='12'}
    for y in range(2027,inp['explicit_last_year']+1):
        first=december[y-1];end=december[y];fy=fiscal[y];row=plan[y]
        avg_bg=(first['state']['bg']+end['state']['bg'])/2;avg_bm=(first['state']['bm']+end['state']['bm'])/2
        avg_kg=(first['state']['kg']+end['state']['kg'])/2;avg_rwa=(first['capital']['group']['rwa']+end['capital']['group']['rwa'])/2
        annual_economics.append({'year':y,'group_common_profit':fy['group_common_profit'],
            'parent_common_profit':fy['parent_net_profit']-fy['other_equity_distribution'],
            'ordinary_roe_two_point_equity_average':fy['group_common_profit']/avg_bg,
            'parent_ordinary_roe_two_point_equity_average':(fy['parent_net_profit']-fy['other_equity_distribution'])/avg_bm,
            'core_budget_ordinary_return_before_excess_capital_income':(row['group_pre_at1_net_profit']-fy['other_equity_distribution'])/avg_kg,
            'two_point_average_RWA_over_average_earning_assets_proxy':avg_rwa/row['average_earning_assets'] if row['average_earning_assets'] else None,
            'end_group_common_book':end['state']['bg'],'end_parent_common_book':end['state']['bm'],
            'end_core_capital':end['state']['kg'],'rwa_growth_budget':row['rwa_growth'],
            'status':'FORECAST_TWO_POINT_AVERAGES_NOT_REPORTED_WEIGHTED_ROE_OR_RISK_WEIGHT'})
    return {'scenario':scenario['name'],'operating_plan':plan,'fiscal_profit':fiscal,'monthly_ledger':ledger,'events':events,
            'snapshots':snapshots,'five_actual_distribution_buckets_per_share':distributions,'values':values,'tail_inputs':tail,
            'auxiliary_normalized_pb_reference':pb_reference,
            'annual_economics':annual_economics,
            'violations':violations,'model_limitation':'Parent leverage denominator and normal dividend funding envelope are explicit research proxies/budgets, not full regulatory LCR forecasts.'}

def test_fixture():
    floors={'cet1':.10,'tier1':.11,'total':.13,'leverage':.04}
    cp={'rwa_per_core':2,'deduction_per_core':0,'net_at1':0,'tier2':0,'exposure_per_core':3,'exposure_status':'test_exact','floors':floors}
    return {'growth':0,'excess_aftertax_yield':0,'payout':1,'incremental_upstream_share':0,'subsidiary_cash_available_fraction':.5,
            'core_group_pre_at1_return':.1,'core_parent_pre_at1_return':.1,'parent_core_fraction':1,
            'at1_coupon':0,'at1_h1_coupon':0,'state':[1,100,0,0,10,5],
            'capital':{'group':copy.deepcopy(cp),'parent':copy.deepcopy(cp)},'statutory_rate':0,
            'parent_general_reserve_per_core':0,'parent_legal_profit_pool':100,'free_dividend_funding_budget':100,
            'liquidity_budget_fraction':1,'interim_payment_year_fraction':1,'final_payment_year_fraction':1}

def run_checks(expected):
    """The checks call the SAME production functions. Expected values are external
    hand-derived numbers in independent-checks.json, never generated by the model.
    """
    out=[]
    def check(name,actual,target,tol=1e-8):
        ok=(actual==target) if isinstance(target,(bool,str)) else abs(actual-target)<=tol
        out.append({'name':name,'actual':actual,'independent_expected':target,'passed':ok})
        if not ok:raise AssertionError(name)
    f=test_fixture();r=tail_value(f,.1)
    check('zero_growth_full_payout_feasible',r['feasible'],True)
    check('zero_growth_full_payout_value',r['value'],expected['zero_growth_full_payout_value'])
    f=test_fixture();f['payout']=.5;f['state'][-1]=2.5;r=tail_value(f,.1)
    check('zero_yield_retained_principal_feasible',r['feasible'],True)
    check('zero_yield_retained_principal_value',r['value'],expected['half_payout_zero_reinvestment_yield_value'])
    f['statutory_rate']=.1;r2=tail_value(f,.1)
    check('reserve_reclassification_not_cash_loss',r2['value'],expected['half_payout_zero_reinvestment_yield_value'])
    f=test_fixture();f['core_parent_pre_at1_return']=.03;r=tail_value(f,.1)
    check('parent_constraint_rejects_group_only_value',r['feasible'],False)
    check('proven_tail_violation_status_propagates',r['status'],'PROVEN_NEGATIVE_CONSTRAINT_IN_REPRESENTED_BUDGET')
    f=test_fixture();f['parent_loss_carry']=1;r=tail_value(f,.1)
    check('unreviewed_piecewise_tail_is_inconclusive',r['status'],'INCONCLUSIVE')
    check('inconclusive_tail_has_no_adopted_value',r['value'] is None,True)
    check('inconclusive_tail_not_feasible',r['feasible'],False)
    check('approved_dividend_limited_by_parent_legal',approve_dividend(10,4,20,20),expected['parent_legal_cap_dividend'])
    check('approved_dividend_limited_by_cash_funding',approve_dividend(10,20,20,3),expected['funding_cap_dividend'])
    settled=settle_payment(90,80,10,10,10)
    for i,(a,e) in enumerate(zip(settled,expected['settle_already_declared'])):check('settle_no_double_book_deduction_'+str(i),a,e)
    s,l=statutory_appropriation(100,20,.1);check('losses_before_statutory',s,expected['statutory_after_loss']);check('loss_carry_after_profit',l,0)
    s,l=statutory_appropriation(-10,20,.1);check('no_statutory_on_loss',s,0);check('loss_carry_increases',l,30)
    cap={'group':{'deduction':10,'rwa':500,'net_at1':10,'tier2':0,'exposure':700,'exposure_status':'test_exact'},
         'parent':{'deduction':5,'rwa':400,'net_at1':5,'tier2':3,'exposure':500,'exposure_status':'test_exact'}}
    v,_=capital_capacity({'bg':100,'bm':80},cap,{'cet1':.1,'tier1':.12,'total':.14,'leverage':.05})
    check('dual_entity_capital_capacity',v,expected['dual_entity_capital_capacity'])
    note=[{'principal':43000,'coupon':.0369,'first_reset_year':2026,'payment_month':12,'first_payment_year':2022}]
    pays,fees=coupon_for_year(2026,note,.025,.0002);check('pre_reset_coupon',pays[12],expected['pre_reset_coupon']);check('refinancing_fee',fees[12],expected['refinancing_fee'])
    pays,_=coupon_for_year(2027,note,.025,.0002);check('budget_post_reset_coupon',pays[12],expected['post_reset_coupon'])
    # Positive growth/extra return, unequal entities, nonzero coupon and two
    # separate cash dates. External numbers come from geometric sums, not A*s.
    nd=expected['nondegenerate_monthly_tail'];z=nd['fixture'];f=test_fixture()
    f.update(growth=z['growth'],excess_aftertax_yield=z['excess_aftertax_yield'],payout=z['payout'],
             incremental_upstream_share=z['incremental_upstream_share'],core_group_pre_at1_return=z['group_core_pre_at1_return'],
             core_parent_pre_at1_return=z['parent_core_pre_at1_return'],parent_core_fraction=z['parent_core_fraction'],
             at1_coupon=z['at1_coupon'],at1_h1_coupon=0,at1_max_month_coupon=z['at1_coupon'],
             at1_monthly_coupons={str(z['at1_payment_month']):z['at1_coupon']},state=z['state'],
             interim_payment_year_fraction=z['interim_payment_year_fraction'],final_payment_year_fraction=z['final_payment_year_fraction'])
    op=tail_calendar_operator(f);bridge=tail_two_year_bridge(f,op)['adopted_monthly']
    for i,ex in enumerate(nd['years']):
        got=bridge[i];last=got['monthly_bridge'][-1]
        fields={'january_cash':got['january_cash'],'july_cash':got['july_cash'],'group_common_profit':got['group_common_profit'],
                'parent_common_profit':got['parent_common_profit'],'h1_group_profit':got['h1_group_common_profit'],
                'interim_declaration':got['december_interim_declaration'],'group_book_end':last['group_common_book'],
                'parent_book_end':last['parent_common_book'],'core_capital_end':last['core_capital']}
        for key,target in ex.items():check('nondegenerate_year'+str(i+1)+'_'+key,fields[key],target)
    check('nondegenerate_separate_cash_dates',f['interim_payment_year_fraction']<f['final_payment_year_fraction'],True)
    # Independently frozen exact counterexamples target false infinite-horizon
    # passes, not financial parameter fitting or a larger finite forecast horizon.
    for case in expected['exact_certificate_counterexamples']:
        field=QuadraticField(0);a=[[Q(v) for v in row] for row in case['matrix']];state=[Q(v) for v in case['state']]
        proof=prepare_exact_certificate(a,state,[field.value(v) for v in case['eigenvalues']],field)
        cert=certify_scalar(proof,case['constraint'])
        check('exact_certificate_'+case['name']+'_ok',cert['ok'],case['expected_ok'])
        check('exact_certificate_'+case['name']+'_status',cert['status'],case['expected_status'])
    f0=QuadraticField(0);check('quadratic_zero_radicand_canonical_zero',f0.value(0,1).zero(),True)
    f4=QuadraticField(4);check('quadratic_perfect_square_canonical_zero',(f4.value(3)-f4.value(1,1)).zero(),True)
    f2=QuadraticField(2);check('quadratic_exact_conjugate_product',(f2.value(1,1)*f2.value(-1,1)-1).zero(),True)
    check('quadratic_exact_positive_sign',f2.value(-1,1).sign(),1)
    check('quadratic_exact_negative_sign',f2.value(1,-1).sign(),-1)
    # Generic matrix solution independently hand checked: 2x+y=5, x+3y=10.
    v=solve([[2,1],[1,3]],[5,10]);check('linear_solver_x',v[0],1);check('linear_solver_y',v[1],3)
    return out

def deep_merge(base,changes):
    out=copy.deepcopy(base)
    for k,v in changes.items():
        out[k]=deep_merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else copy.deepcopy(v)
    return out

def run_whole_chain_checks(fixture):
    """Send synthetic inputs through the FULL adopted simulate/valuation chain.
    No bespoke toy dividend engine; expectations are independently frozen.
    """
    checked=[];current_values=[]
    for case in fixture['cases']:
        inp=deep_merge(fixture['input'],case['input_overrides']);scenario=copy.deepcopy(fixture['scenario']);scenario['name']=case['name']
        result=simulate(inp,scenario);ex=case['expected'];rows={r['date']:r for r in result['monthly_ledger']}
        declarations=[e for e in result['events'] if e['kind']=='ordinary_declaration_budget_not_announced']
        paid=[e for e in result['events'] if e['kind']=='ordinary_cash_paid_budget']
        actual={'five_distributions':result['five_actual_distribution_buckets_per_share'],
                'first_four_declarations':[e['amount'] for e in declarations[:4]],'first_two_cash':[e['amount'] for e in paid[:2]],
                'first_january_parent_book':rows['2027-01-31']['state']['bm'],'first_january_group_book':rows['2027-01-31']['state']['bg'],
                'first_january_payable':rows['2027-01-31']['ordinary_payable'],'first_june_parent_book':rows['2027-06-30']['state']['bm'],
                'year5_parent_book':rows['2031-10-31']['state']['bm'],'year5_group_book':rows['2031-10-31']['state']['bg'],
                'year5_terminal_value':result['values']['0.1']['year5_terminal_per_share']}
        for key,target in ex.items():
            a=actual[key]
            if isinstance(target,list) and len(a)!=len(target):raise AssertionError('whole_chain_list_length_'+key)
            error=max(abs(v-w) for v,w in zip(a,target)) if isinstance(target,list) else abs(a-target)
            if error>1e-8:raise AssertionError('whole_chain_'+case['name']+'_'+key)
        if [e['date'] for e in paid[:2]]!=fixture['cash_dates']:raise AssertionError('whole_chain_cash_dates')
        if result['violations'] or not all(v['feasible'] for v in result['values'].values()):raise AssertionError('whole_chain_fixture_feasibility')
        current_values.append(result['values']['0.1']['current_per_share'])
        checked.append({'case':case['name'],'actual':actual,'independent_expected':ex,'first_cash_dates':[e['date'] for e in paid[:2]],'passed':True})
    difference=current_values[0]-current_values[1]
    if abs(difference-fixture['expected_current_value_difference_unbound_minus_bound'])>1e-8:raise AssertionError('whole_chain_current_value_difference')
    checked.append({'case':'only_first_january_cash_differs','actual':difference,'independent_expected':fixture['expected_current_value_difference_unbound_minus_bound'],'passed':True})
    return checked
