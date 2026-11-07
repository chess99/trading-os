"""Small cash-replay contract, with distinct technical and economic outcomes."""

import copy

import math

class EconomicFailure(Exception):
    def __init__(self, reason, state=None):
        super().__init__(reason)
        self.reason=reason
        self.state=state or {}

class CacheMissing(Exception):
    def __init__(self, reason, state=None):
        super().__init__(reason)
        self.reason=reason
        self.state=state or {}

def require(condition, reason, *, economic=False, state=None):
    if not condition:
        if economic:
            raise EconomicFailure(reason,state)
        raise CacheMissing(reason,state)

def freeze_equal(a,b,label):
    """Exact schema/type/value equality, not a blanket numeric tolerance."""
    if type(a) is not type(b):
        raise AssertionError((label,'type',type(a).__name__,type(b).__name__))
    if isinstance(a,dict):
        if a.keys()!=b.keys():raise AssertionError((label,'keys',list(a),list(b)))
        for k in a:freeze_equal(a[k],b[k],label+'/'+str(k))
    elif isinstance(a,(list,tuple)):
        if len(a)!=len(b):raise AssertionError((label,'length',len(a),len(b)))
        for i,(x,y) in enumerate(zip(a,b)):freeze_equal(x,y,label+'/'+str(i))
    elif a!=b:
        raise AssertionError((label,'value',a,b))
