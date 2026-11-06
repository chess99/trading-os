"""Typed economics and strict comparison. No catch-all converts bugs to economic null."""
import math

class EconomicRefusal(Exception):
    def __init__(self,code,details=None):
        self.code=code;self.details=details or {};super().__init__(code)
    def output(self):
        return {'status':'ECONOMIC_REFUSAL','feasible':False,'reason':self.code,'details':self.details,
                'value':None,'return_model':None,'value_range':None}

def differences(expected,actual,path='',exact_structure=False):
    """Compare every expected leaf exactly; optional same-key structural equivalence.
    New bridge metadata may be extra when exact_structure=False. Bool is not a number.
    """
    result=[]
    def visit(e,a,p):
        if isinstance(e,dict):
            if not isinstance(a,dict):result.append({'path':p,'reason':'mapping type','expected':e,'actual':a});return
            for k,v in e.items():
                if k not in a:result.append({'path':p+'/'+k,'reason':'missing'})
                else:visit(v,a[k],p+'/'+k)
            if exact_structure:
                for k in a.keys()-e.keys():result.append({'path':p+'/'+k,'reason':'extra'})
        elif isinstance(e,list):
            if not isinstance(a,list) or len(e)!=len(a):result.append({'path':p,'reason':'list length/type','expected_length':len(e),'actual_type':type(a).__name__,'actual_length':len(a) if isinstance(a,list) else None});return
            for i,(x,y) in enumerate(zip(e,a)):visit(x,y,p+'/'+str(i))
        elif isinstance(e,bool):
            if type(a) is not bool or e!=a:result.append({'path':p,'reason':'bool mismatch','expected':e,'actual':a})
        elif isinstance(e,(int,float)):
            if isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(e) or not math.isfinite(a) or e!=a:
                result.append({'path':p,'reason':'exact finite number mismatch','expected':e,'actual':a})
        elif type(e) is not type(a) or e!=a:result.append({'path':p,'reason':'type/value mismatch','expected':e,'actual':a})
    visit(expected,actual,path);return result

def require_exact(expected,actual,path='',exact_structure=False):
    diff=differences(expected,actual,path,exact_structure)
    if diff:raise AssertionError({'count':len(diff),'first':diff[0]})

def discount_finite_rows(rows,rate,dps_key,year_key=None):
    if rate<=0:raise ValueError('nonpositive discount rate')
    return sum(x[dps_key]/(1+rate)**(i-4) for i,x in enumerate(rows) if i>=5)

def core_and_holder_status(paths,value_key):
    """Diagnostics never veto adopted base. A failed core endpoint is not replaced."""
    for name in ['core_low','core_high','base']:
        if paths[name].get('feasible'):
            v=paths[name].get(value_key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('successful path has invalid value: '+name)
    endpoints={label:{'source_path':'core_'+label,'feasible':bool(paths['core_'+label].get('feasible')),
      'value':paths['core_'+label].get(value_key) if paths['core_'+label].get('feasible') else None,
      'reason':paths['core_'+label].get('reason')} for label in ['low','high']}
    value_range=({'low':endpoints['low']['value'],'high':endpoints['high']['value'],'currency':'CNY'}
      if all(x['feasible'] for x in endpoints.values()) else None)
    return {'core_endpoints':endpoints,'value_range':value_range,
      'core_condition':('both adopted endpoints feasible' if value_range else 'At least one adopted core endpoint is economically infeasible; do not manufacture a replacement interval.'),
      'base_holder_eligible':bool(paths['base'].get('feasible')),
      'diagnostic_failures':{k:{'reason':v.get('reason'),'status':v.get('status')} for k,v in paths.items() if k not in ['base','core_low','core_high','return_low','return_high'] and not v.get('feasible')}}
