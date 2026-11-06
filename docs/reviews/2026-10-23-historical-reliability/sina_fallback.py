import concurrent.futures as cf,gzip,html,json,re,urllib.request,datetime as dt
from market import ROOT,DEST,code,END
def fetch(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
def rows(t):
    return [[html.unescape(re.sub('<[^>]+>','',v)).strip() for v in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',r,re.S)] for r in re.findall('<tr[^>]*>(.*?)</tr>',t,re.S)]
def get(old):
    x=dict(old);symbol=x['symbol'];c=code(symbol);ticker=symbol.split(':')[-1]
    try:
        u=f'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={c}&scale=240&ma=no&datalen=120'
        result=json.loads(fetch(u));raw=[[z['day'],z['open'],z['close'],z['high'],z['low'],z['volume']] for z in result if '2026-07-01'<=z['day']<=END]
        x.update(raw=raw,raw_last_date=raw[-1][0] if raw else None,raw_provider='Sina')
        x['urls']['raw']=u
        u=f'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/{ticker}.phtml'
        t=fetch(u).decode('gbk',errors='replace')
        table=re.search(r'<table id="sharebonus_1">(.*?)</table>',t,re.S)
        if not table:raise ValueError('No dividend table')
        es=[]
        for r in rows(table.group(1)):
            if len(r)<8 or not re.fullmatch(r'\d{4}-\d\d-\d\d',r[0]) or r[4]!='实施':continue
            if re.fullmatch(r'\d{4}-\d\d-\d\d',r[5]) and '2026-07-01'<=r[5]<=END:
                es.append(dict(date=r[5],cash=float(r[3])/10,split=1+(float(r[1])+float(r[2]))/10,unknown=False,description='每10股送'+r[1]+'转'+r[2]+'派'+r[3]))
        rights=re.search(r'<table id="sharebonus_2">(.*?)</table>',t,re.S)
        if rights:
            for r in rows(rights.group(1)):
                if any(re.fullmatch(r'2026-\d\d-\d\d',v) and '2026-07-01'<=v<=END for v in r):
                    es.append(dict(date=next(v for v in r if re.fullmatch(r'2026-\d\d-\d\d',v)),cash=0,split=1,unknown=True,description='配股待人工核实'))
        x.update(sina_events=es,events_complete=True,event_data_asof=END,event_source_url=u,sina_retrieved_at=dt.datetime.now().isoformat())
    except Exception as e:x['sina_error']=str(e)
    return x
with gzip.open(DEST,'rt') as f:m={x['symbol']:x for x in map(json.loads,f)}
todo=[x for x in m.values() if x.get('raw_last_date')!=END or x.get('hfq_last_date')!=END]
print('Fallback',len(todo),flush=True)
with cf.ThreadPoolExecutor(max_workers=12) as executor,gzip.open(DEST,'at') as out:
    for i,x in enumerate(executor.map(get,todo),1):
        out.write(json.dumps(x,ensure_ascii=False)+'\n')
        if i%100==0:print('Fetched',i,flush=True)
