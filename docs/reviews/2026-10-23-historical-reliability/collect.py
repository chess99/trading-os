"""Historical research audit. Read-only repository access except Git lazy fetching.
Outputs are frozen by revision, with source paths and raw provider responses.
"""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path('/Users/zcs/code/trading-os')
OUT = Path(__file__).resolve().parent
(OUT/'data').mkdir(parents=True,exist_ok=True)
FROZEN_REFS = {
    '2026-07-20': '2ab0a41d394a232bbfe5100477d9da82fcfb359d',
    '2026-08-08': '9b319449087c4fcc8fce341939710bbaaba91bfe',
    '2026-08-18': '10d8f798af191b1f7a2a6db82460da484ca38e02',
    '2026-09-14': 'a781bae1fd2b10f1fb5dc58a7172e41a94496e09',
    '2026-10-23': '408184b095ad5fa6acbfe66174f07dc2acc6e94d',
}

def git(*args, binary=False, input=None, env=None):
    return subprocess.check_output(['git', *args], cwd=REPO, text=not binary, input=input, env=env)

def dump(name, data):
    (OUT / 'data' / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))

def objects(rev):
    result = []
    for line in git('ls-tree', '-r', rev).splitlines():
        props, path = line.split('\t', 1)
        mode, kind, oid = props.split()
        result.append((path, oid))
    return result

def read_objects(items):
    oids = list(dict.fromkeys(oid for _, oid in items))
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1')
    check = git('cat-file', '--batch-check', input='\n'.join(oids)+'\n', env=env)
    missing = [line.split()[0] for line in check.splitlines() if line.endswith(' missing')]
    if missing:
        print('Fetching historical blobs:', len(missing), flush=True)
        subprocess.run(['git', 'fetch', '--no-tags', '--no-write-fetch-head', 'origin', '--stdin'],
                       cwd=REPO, input='\n'.join(missing)+'\n', text=True, check=True,
                       stdout=subprocess.DEVNULL)
    payload = git('cat-file', '--batch', binary=True, input=('\n'.join(oids)+'\n').encode())
    parsed, offset = {}, 0
    for oid in oids:
        end = payload.index(b'\n', offset)
        header = payload[offset:end].decode().split()
        size = int(header[2])
        parsed[oid] = payload[end+1:end+1+size].decode('utf-8')
        offset = end+size+2
    return {path: parsed[oid] for path, oid in items}

def main():
    manifests = []
    for date in ['2026-07-20', '2026-08-08', '2026-08-18', '2026-09-14', '2026-10-23']:
        rev = FROZEN_REFS[date]
        tree = objects(rev)
        old = date < '2026-08-09'
        chosen = [(p, o) for p, o in tree if (p.startswith('research/companies/') and p.endswith('/meta.json'))] if old else [(p, o) for p, o in tree if p=='coverage/cn-a/research_state.jsonl']
        contents = read_objects(chosen)
        data = []
        if old:
            for p, text in contents.items():
                x = json.loads(text)
                identity = x.get('identity', x)
                if identity.get('market') != 'CN':
                    continue
                val = x.get('valuation', x)
                interval = val.get('fair_value_range')
                reports = x.get('reports', {})
                reports = reports if isinstance(reports, dict) else {}
                report = reports.get('latest') or x.get('latest_report')
                if not report:
                    hist = reports.get('historical_artifacts', [])
                    report = hist[-1]['path'] if hist else None
                data.append(dict(symbol=identity.get('symbol'), name=identity.get('name'),
                    value_range=({'low':interval[0], 'high':interval[1], 'currency':identity.get('currency','CNY')} if interval and len(interval)==2 else None),
                    status=x.get('research',{}).get('coverage_status') or x.get('current_rating') or x.get('rating'),
                    information_cutoff=x.get('research',{}).get('information_cutoff') or x.get('updated_at'),
                    summary=x.get('current_thesis'),
                    basis_report_path=str(Path(p).parent / report) if report else None,
                    source_meta_path=p, raw=x))
        else:
            data = [json.loads(t) for t in next(iter(contents.values())).splitlines() if t]
        dump('snapshot-'+date+'.json', data)
        reports = [p for p, _ in tree if p.startswith('research/companies/') and '/reports/' in p and p.endswith('.md')]
        manifest = dict(date=date, revision=rev, company_records=len(data), reports=len(reports),
            valued=sum(bool(x.get('value_range')) for x in data),
            status=dict(collections.Counter(x['status'] for x in data)),
            source_paths=[p for p,_ in chosen])
        manifests.append(manifest)
        print(date, 'records', len(data), 'valued',manifest['valued'],'reports',len(reports),flush=True)
    dump('manifest.json',manifests)

if __name__=='__main__':
    main()
