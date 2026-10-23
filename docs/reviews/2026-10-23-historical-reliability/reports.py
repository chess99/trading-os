import gzip
import json
from pathlib import Path
from collect import OUT, git, objects, read_objects, dump

manifests=json.loads((OUT/'data/manifest.json').read_text())
stats=[]
for m in manifests:
    rows=json.loads((OUT/'data'/('snapshot-'+m['date']+'.json')).read_text())
    paths=set()
    for x in rows:
        p=x.get('basis_report_path') or x.get('report_path')
        if p and (x.get('value_range') or x.get('status')=='covered'):
            paths.add(p)
    tree=objects(m['revision'])
    chosen=[(p,o) for p,o in tree if p in paths]
    contents=read_objects(chosen)
    with gzip.open(OUT/'data'/('reports-'+m['date']+'.jsonl.gz'),'wt') as out:
        for p,t in contents.items():out.write(json.dumps({'path':p,'text':t},ensure_ascii=False)+'\n')
    stats.append({'date':m['date'],'requested':len(paths),'recovered':len(contents),'missing':sorted(paths-set(contents))})
    print(m['date'],len(contents), 'missing',len(paths-set(contents)),flush=True)
dump('report-recovery.json',stats)
