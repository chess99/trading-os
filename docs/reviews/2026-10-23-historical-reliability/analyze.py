"""Frozen cohorts. Gross simple returns use raw prices and actual corporate actions.
HFQ response prices are not used; only its dividend and split metadata is used.
"""
import collections,csv,gzip,json,re,statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parent
END='2026-10-22'
DATES=['2026-07-20','2026-08-08','2026-08-18','2026-09-14','2026-10-23']
def read(n):return json.loads((ROOT/'data'/n).read_text())
def write(n,x):(ROOT/'data'/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def pos(p,lo,hi):return '低于下沿' if p<lo-1e-8 else '高于上沿' if p>hi+1e-8 else '区间内'
def events(m):
    if m.get('events_complete'):return sorted(m['sina_events'],key=lambda x:x['date'])
    es={}
    for row in m.get('hfq',[]):
        for e in row[6:]:
            if not isinstance(e,dict):continue
            day=e.get('cqr',row[0]);t=e.get('FHcontent','')
            es[day]={'date':day,'cash':float(e.get('fh_sh') or 0)/10,'split':1+sum(float(n) for n in re.findall(r'[送转]([0-9.]+)股',t))/10,
                     'unknown':not t or bool(re.search(r'配|缩|合股',t)),'description':t}
    return sorted(es.values(),key=lambda x:x['date'])
def bridge(es,start,end):
    shares,cash,unknown=1.,0.,False;selected=[]
    for e in es:
        if start<e['date']<=end:
            cash+=shares*e['cash'];shares*=e['split'];unknown|=e['unknown'];selected.append(e)
    return shares,cash,unknown,selected
def describe(rows):
    r=[x['total_return_pct'] for x in rows if x.get('total_return_pct') is not None]
    e=[x['excess_vs_csi300_pp'] for x in rows if x.get('excess_vs_csi300_pp') is not None]
    v=[x for x in rows if x.get('value_comparable')]
    return dict(n=len(rows),return_n=len(r),up=sum(t>0 for t in r),down=sum(t<0 for t in r),flat=sum(t==0 for t in r),
      mean_pct=st.mean(r) if r else None,median_pct=st.median(r) if r else None,
      beat_csi300_price_index=sum(t>0 for t in e),excess_n=len(e),mean_price_excess_pp=st.mean(e) if e else None,
      fresh_raw_n=sum(x.get('fresh_raw',False) for x in rows),corporate_action_n=sum(bool(x.get('period_events')) for x in rows),
      comparable_value_n=len(v),end_position=dict(collections.Counter(x['end_position'] for x in v)),
      start_position=dict(collections.Counter(x['start_position'] for x in v if x.get('start_position'))),
      below_lower_ever=sum(x.get('below_lower_ever',False) for x in v),
      up_into_old_range=sum(x.get('reached_lower_from_below',False) for x in v),
      up_into_old_range_still=sum(x.get('start_position')=='低于下沿' and x.get('end_position')!='低于下沿' for x in v),
      from_below_up_unreached=sum(x.get('start_position')=='低于下沿' and x.get('end_position')=='低于下沿' and (x.get('total_return_pct') or 0)>0 for x in v),
      from_below_down=sum(x.get('start_position')=='低于下沿' and (x.get('total_return_pct') or 0)<0 for x in v),
      fell_through_lower=sum(x.get('start_position') in ['区间内','高于上沿'] and x.get('end_position')=='低于下沿' for x in v))

def main():
    with gzip.open(ROOT/'data/market.jsonl.gz','rt') as f:market={x['symbol']:x for x in map(json.loads,f)}
    benchmark={r[0]:float(r[2]) for r in market['BENCH:000300']['raw']}
    summaries=[];allrows=[]
    for date in DATES:
        source=read('snapshot-'+date+'.json');rows=[]
        for x in source:
            v=x.get('value_range')
            if not v and not (date==DATES[0] and x['status']=='buy'):continue
            m=market.get(x['symbol'],{});raw={r[0]:r for r in m.get('raw',[])};es=events(m)
            cutoff=str(x.get('information_cutoff') or date)[:10];complete=m.get('events_complete') or m.get('hfq_last_date')==END
            z=dict(snapshot=date,symbol=x['symbol'],name=x['name'],status=x['status'],low=v['low'] if v else None,high=v['high'] if v else None,
              information_cutoff=x.get('information_cutoff'),report_path=x.get('basis_report_path') or x.get('report_path'),
              end_date=END,end_close=float(raw[END][2]) if END in raw else None,fresh_raw=END in raw,value_comparable=False,
              last_raw_date=max(raw) if raw else None,last_event_data_date=m.get('event_data_asof',m.get('hfq_last_date')))
            starts=sorted(d for d in raw if date<d<=END)
            if starts:
                start=starts[0];p0=float(raw[start][2]);z.update(start_date=start,start_close=p0)
                sh,ca,un,period=bridge(es,start,END);z.update(period_events=period,ending_shares=sh,cash_dividends_per_initial_share=ca)
                if END in raw and complete and not un:
                    p1=float(raw[END][2]);z['total_return_pct']=((p1*sh+ca)/p0-1)*100
                    z['split_adjusted_price_return_pct']=(p1*sh/p0-1)*100
                    if start in benchmark and END in benchmark:
                        z['benchmark_price_return_pct']=(benchmark[END]/benchmark[start]-1)*100
                        z['excess_vs_csi300_pp']=z['split_adjusted_price_return_pct']-z['benchmark_price_return_pct']
                    if v:
                        prevsh,prevca,prevun,_=bridge(es,cutoff,start)
                        lo=(v['low']-prevca)/prevsh;hi=(v['high']-prevca)/prevsh
                        z.update(start_normalized_low=lo,start_normalized_high=hi,start_position=pos(p0,lo,hi),
                          end_normalized_low=(lo-ca)/sh,end_normalized_high=(hi-ca)/sh,end_position=pos(p1*sh+ca,lo,hi),value_comparable=not prevun)
                        high=[];low=[];close=[]
                        for d,r in sorted(raw.items()):
                            if start<=d<=END:
                                ds,dc,_,_=bridge(es,start,d);high.append(float(r[3])*ds+dc);low.append(float(r[4])*ds+dc);close.append(float(r[2])*ds+dc)
                        z['below_lower_ever']=min(low)<lo;z['reached_lower_from_below']=p0<lo and max(high)>=lo
                        peak=close[0];mdd=0
                        for price in close:peak=max(peak,price);mdd=min(mdd,price/peak-1)
                        z['wealth_max_drawdown_pct']=mdd*100
            elif date==DATES[-1] and END in raw and v and complete:
                sh,ca,un,period=bridge(es,cutoff,END)
                z.update(end_normalized_low=(v['low']-ca)/sh,end_normalized_high=(v['high']-ca)/sh,
                   end_position=pos(z['end_close']*sh+ca,v['low'],v['high']),value_comparable=not un,period_events=period)
            rows.append(z)
        summaries.append(dict(snapshot=date,valued_records=sum(z['low'] is not None for z in rows),
          information_after_snapshot=sum(str(x.get('information_cutoff') or '')[:10]>date for x in source),
          overall=describe([z for z in rows if z['low'] is not None]),by_status={k:describe([z for z in rows if z['status']==k]) for k in sorted(set(z['status'] for z in rows))}))
        allrows+=rows
    write('price-summary.json',summaries);write('price-comparison.json',allrows)
    keys=list(dict.fromkeys(k for r in allrows for k in r))
    with (ROOT/'data/price-comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in allrows)
    latest={x['symbol']:x for x in read('snapshot-'+DATES[-1]+'.json')};revisions=[]
    for date in [DATES[0],DATES[2],DATES[3]]:
        old=[x for x in read('snapshot-'+date+'.json') if x.get('value_range')];matched=[];withdrawn=[]
        for x in old:
            n=latest.get(x['symbol']);v=n.get('value_range') if n else None
            z=dict(symbol=x['symbol'],name=x['name'],old=x['value_range'],latest=v,old_cutoff=x.get('information_cutoff'),new_cutoff=n.get('information_cutoff') if n else None)
            if v:
                sh,ca,un,_=bridge(events(market.get(x['symbol'],{})),str(z['old_cutoff'] or date)[:10],min(str(z['new_cutoff'] or END)[:10],END))
                oldmid=((x['value_range']['low']+x['value_range']['high'])/2-ca)/sh
                z['midpoint_change_pct']=((v['low']+v['high'])/2/oldmid-1)*100;z['corporate_actions_unknown']=un;matched.append(z)
            else:withdrawn.append(z)
        revisions.append(dict(snapshot=date,n=len(old),matched=len(matched),no_current_value=len(withdrawn),
          midpoint_down_gt25=sum(z['midpoint_change_pct']< -25 for z in matched),midpoint_up_gt25=sum(z['midpoint_change_pct']>25 for z in matched),
          median_change_pct=st.median(z['midpoint_change_pct'] for z in matched),rows=matched,withdrawn=withdrawn))
    write('valuation-revisions.json',revisions)
    for x in summaries:print(x['snapshot'],json.dumps(x['overall'],ensure_ascii=False));print('BUY',x['by_status'].get('buy'))
    print('REVISIONS',[{k:v for k,v in x.items() if k not in ['rows','withdrawn']} for x in revisions])
    assert len({(x['snapshot'],x['symbol']) for x in allrows})==len(allrows)
    for x in summaries:
        d=x['overall'];assert d['up']+d['down']+d['flat']==d['return_n'];assert sum(d['end_position'].values())==d['comparable_value_n']
    assert bridge([],DATES[0],END)[:3]==(1.,0.,False)
    assert bridge([dict(date='2026-08-01',cash=1,split=2,unknown=False)],DATES[0],END)[:3]==(2.,1.,False)

if __name__=='__main__':main()
