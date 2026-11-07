"""Exact original production checker definitions; no finance at import."""
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

def check_proya_same_base(base,side):
    """Current production wrapper and fixture share this full-state check."""
    freeze_equal(base['operating_path'][:5],side['operating_path'][:5],'Proya base operating years1-5')
    for field in ('cash_legal_share_path','distributions_per_share'):
        freeze_equal(base[field],side[field],'Proya full base '+field)
    return {'status':'SAME_FULL_Y5_STATE','full_r_and_tail_cache_applied':True}
