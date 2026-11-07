"""NEW_RECONSTRUCTION: no original-code equivalence. Standard library only."""
from decimal import Decimal, getcontext, ROUND_HALF_EVEN, ROUND_CEILING
from datetime import date
import calendar
import copy
import hashlib
import json
from pathlib import Path

getcontext().prec = 50
ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal('0.01')

def D(v):
    return v if isinstance(v, Decimal) else Decimal(str(v))

def M(v):
    return D(v).quantize(CENT, rounding=ROUND_HALF_EVEN)

def ceil_money(v):
    return D(v).quantize(CENT, rounding=ROUND_CEILING)

def ds(v): return date.fromisoformat(v)
def iso(v): return v.isoformat()
def month_end(y,m): return date(y,m,calendar.monthrange(y,m)[1])
def add_months(d,n):
    k=d.year*12+d.month-1+n
    return month_end(k//12,k%12+1)
def tax_due(d):
    q=(d.month-1)//3+1
    return month_end(d.year+q//4, (q%4+1)*3)
def yearfrac(a,b): return D((b-a).days)/D(365)
def df(rate, years):
    if D(rate)<=-1: raise ValueError('invalid discount rate')
    return (ONE+D(rate)) ** (-D(years))
def pv(amount, when, at, rate): return D(amount)*df(rate,yearfrac(at,when))
def load(path): return json.loads(Path(path).read_text(),parse_float=Decimal)
def encode(v):
    if isinstance(v,Decimal): return str(v)
    if isinstance(v,date): return iso(v)
    raise TypeError(type(v).__name__)
def dump(path,obj,mode='x'):
    with Path(path).open(mode) as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,default=encode,allow_nan=False);f.write('\n');f.flush()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def merge(base,patch):
    out=copy.deepcopy(base)
    for k,v in patch.items():
        out[k]=merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else copy.deepcopy(v)
    return out

class EconomicRejection(Exception): pass
class FundingIncompatibility(EconomicRejection): pass
class TerminalCapitalIncompatibility(EconomicRejection): pass
class ClaimIncompatibility(EconomicRejection): pass

class Journal:
    """Exclusive attempt. Raw checkpoint precedes each economic check."""
    def __init__(self,path):
        self.root=Path(path);self.root.mkdir(parents=True,exist_ok=False)
        self.handle=(self.root/'raw-stages.jsonl').open('x');self.index=0
    def event(self,stage,payload):
        self.index+=1
        self.handle.write(json.dumps({'seq':self.index,'stage':stage,'payload':payload},default=encode,ensure_ascii=False,allow_nan=False)+'\n')
        self.handle.flush()
    def save(self,name,obj): dump(self.root/name,obj)
    def close(self): self.handle.close()
