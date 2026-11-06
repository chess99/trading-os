import concurrent.futures as cf
import json
from pathlib import Path
import subprocess
import urllib.request
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
(ROOT/'tmp/pdfs').mkdir(parents=True,exist_ok=True)
SOURCES={
'catl-q3': 'https://static.cninfo.com.cn/finalpage/2026-10-21/1225613175.PDF',
'xingyu-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-27/1225509977.PDF',
'wuliangye-h1': 'https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-29/54759c03-9537-4b38-8e23-c98946014e59.PDF',
'cmb-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-29/1225530237.PDF',
'moutai-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-15/1225475868.PDF',
'yili-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-27/1225511409.PDF',
'wanhua-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-25/1225497561.PDF',
'midea-h1': 'https://static.cninfo.com.cn/finalpage/2026-08-28/1225533135.PDF',
'tsingtao-q1': 'https://www.hkexnews.hk/listedco/listconews/sehk/2026/0427/2026042703016_c.pdf',
}
def get(item):
 k,u=item;p=ROOT/'tmp/pdfs'/(k+'.pdf')
 try:
  if not p.exists(): p.write_bytes(urllib.request.urlopen(u,timeout=30).read())
  if p.read_bytes()[:4]!=b'%PDF': raise ValueError('Not PDF')
  txt=p.with_suffix('.txt')
  reader=PdfReader(str(p))
  txt.write_text('\n\f\n'.join(page.extract_text(extraction_mode='layout') for page in reader.pages))
  return {'id':k,'url':u,'local_pdf':str(p),'text_path':str(txt),'identity_excerpt':txt.read_text()[:650]}
 except Exception as e:return {'id':k,'url':u,'error':str(e)}
r=list(cf.ThreadPoolExecutor(max_workers=8).map(get,SOURCES.items()))
(ROOT/'data/primary-sources.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
for x in r:print(x['id'],x.get('error') or x['identity_excerpt'][:220].replace('\n',' '))
