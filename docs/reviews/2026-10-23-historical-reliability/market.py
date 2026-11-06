import concurrent.futures as cf
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'data/market.jsonl.gz'
END='2026-10-22'

def code(symbol):
    t=symbol.split(':')[-1]
    return ('bj' if t.startswith(('4','8','920')) else 'sh' if t.startswith(('5','6','9')) else 'sz')+t

def get(symbol):
    c='sh000300' if symbol=='BENCH:000300' else code(symbol)
    result={'symbol':symbol,'provider':'Tencent','retrieved_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),'urls':{}}
    for mode in ['raw','hfq']:
        suffix='' if mode=='raw' else mode
        host='proxy.finance.qq.com/ifzqgtimg' if os.environ.get('MARKET_REPAIR') else 'web.ifzq.gtimg.cn'
        url=f'https://{host}/appstock/app/fqkline/get?param={c},day,2026-07-01,2026-10-23,120,{suffix}'
        result['urls'][mode]=url
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
                data=json.load(urllib.request.urlopen(req,timeout=15))
                z=data.get('data',{}).get(c,{})
                rows=z.get('day' if mode=='raw' else 'hfqday',z.get('day',[]))
                result[mode]=[r for r in rows if r[0]<=END]
                result[mode+'_last_date']=result[mode][-1][0] if result[mode] else None
                break
            except Exception as e:
                if attempt==2: result[mode+'_error']=str(e)
                else: time.sleep(.3*(attempt+1))
    return result

def main():
    symbols=set()
    for f in (ROOT/'data').glob('snapshot-*.json'):
        symbols.update(x['symbol'] for x in json.loads(f.read_text()) if x.get('value_range') or x.get('status')=='buy')
    symbols.add('BENCH:000300')
    done=set();existing={}
    if DEST.exists():
        with gzip.open(DEST,'rt') as f:
            existing={x['symbol']:x for x in map(json.loads,f)}
            done={s for s,x in existing.items() if not os.environ.get('MARKET_REPAIR') or (x.get('raw') and x.get('hfq') and not (x.get('raw_last_date')=='2026-10-22' and x.get('hfq_last_date')!='2026-10-22'))}
    todo=sorted(symbols-done)
    print('Securities',len(symbols),'remaining',len(todo),flush=True)
    with gzip.open(DEST,'at',compresslevel=6) as out,cf.ThreadPoolExecutor(max_workers=20) as executor:
        for i,r in enumerate(executor.map(get,todo),1):
            old=existing.get(r['symbol'],{})
            for mode in ['raw','hfq']:
                if not r.get(mode) and old.get(mode):
                    r[mode]=old[mode];r[mode+'_last_date']=old.get(mode+'_last_date');r['urls'][mode]=old['urls'][mode]
            out.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
            if i%200==0:
                out.flush(); print('Fetched',i,'/',len(todo),flush=True)
    print('Done',flush=True)

if __name__=='__main__':main()
