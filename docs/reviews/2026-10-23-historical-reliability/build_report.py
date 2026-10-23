"""Render the Chinese retrospective and reader-facing company tables."""
import csv,gzip,html,json,statistics as st
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from reportlab.graphics.shapes import Drawing,Rect,String,Line

ROOT=Path(__file__).resolve().parent
REPO=Path('/Users/zcs/code/trading-os')
DATA=ROOT/'data';OUT=ROOT/'output/pdf';OUT.mkdir(parents=True,exist_ok=True)
read=lambda n:json.loads((DATA/n).read_text())
summaries=read('price-summary.json');rows=read('price-comparison.json');revisions=read('valuation-revisions.json');manifest=read('manifest.json')
july=summaries[0];buy=july['by_status']['buy'];allj=july['overall']
julyrows=[x for x in rows if x['snapshot']=='2026-07-20'];buyrows=[x for x in julyrows if x['status']=='buy']
snapshots={d:read('snapshot-'+d+'.json') for d in ['2026-07-20','2026-08-18','2026-09-14','2026-10-23']}
bydate={d:{x['symbol']:x for x in xs} for d,xs in snapshots.items()}

# Explicit selection of correction evidence, not a keyword-based correctness score.
reviewrows=[json.loads(t) for t in (REPO/'docs/reviews/2026-09-system-upgrade/audit-results.jsonl').read_text().splitlines() if t]
chosen=['600887','600519','601009','300014','300999','002810','603129','920982','600078','600132','600096','600426','688100','605499','603236','002236','603650','600131','600188','603637','603508','600449','688111','603699','300124','603444','000538','601899','002142','600919','601128','300750']
evidence=[x for x in reviewrows if x['symbol'].split(':')[-1] in chosen]
assert len(evidence)==32
(DATA/'recorded-corrections.json').write_text(json.dumps({'scope':'既有186家公司复核记录中的明确纠错证据下限；本轮不声称逐一重验全部附件','companies':evidence},ensure_ascii=False,indent=2))

cols={'snapshot':'冻结快照日期','symbol':'证券代码','name':'公司','status':'历史标签','low':'原估值下沿_元','high':'原估值上沿_元',
 'information_cutoff':'原资料截止','start_date':'观察起始日','start_close':'起始收盘价_元','end_date':'观察截止日','end_close':'期末收盘价_元',
 'start_normalized_low':'起点扣除已付分红送转后估值下沿_元','start_normalized_high':'起点调整后估值上沿_元',
 'end_normalized_low':'期末调整后旧估值下沿_元','end_normalized_high':'期末调整后旧估值上沿_元','total_return_pct':'含税前分红简单回报_pct',
 'split_adjusted_price_return_pct':'仅处理送转的价格涨跌_pct','benchmark_price_return_pct':'沪深300价格涨跌_pct','excess_vs_csi300_pp':'价格超额_百分点',
 'cash_dividends_per_initial_share':'观察期每初始股现金分红_元','ending_shares':'每初始股期末股数','start_position':'起点相对旧估值','end_position':'期末相对旧估值',
 'reached_lower_from_below':'期间曾从下方触及旧估值下沿','below_lower_ever':'期间最低价曾低于旧估值下沿','wealth_max_drawdown_pct':'含分红收盘财富最大回撤_pct',
 'value_comparable':'旧估值可比','last_raw_date':'最后行情日期','last_event_data_date':'除权数据截止','report_path':'原报告路径'}
def write_csv(path,rs):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(list(cols.values()))
        for x in rs:
            vals=[]
            for k in cols:
                v=x.get(k,'')
                if isinstance(v,float):v=round(v,6)
                if isinstance(v,bool):v='是' if v else '否'
                vals.append(v)
            w.writerow(vals)
write_csv(DATA/'逐股核对表.csv',rows)
write_csv(DATA/'7月买入名单241家.csv',sorted(buyrows,key=lambda x:x.get('total_return_pct',0)))

pdfmetrics.registerFont(TTFont('STSong-Light','/System/Library/Fonts/STHeiti Light.ttc',subfontIndex=0))
NAVY=colors.HexColor('#18364A');TEAL=colors.HexColor('#087E8B');RUST=colors.HexColor('#B15B43');MUTED=colors.HexColor('#526675');PALE=colors.HexColor('#F0F5F6')
S={
 'title':ParagraphStyle('title',fontName='STSong-Light',fontSize=27,leading=37,textColor=NAVY,wordWrap='CJK',spaceAfter=18),
 'h1':ParagraphStyle('h1',fontName='STSong-Light',fontSize=19,leading=27,textColor=NAVY,wordWrap='CJK',spaceAfter=15),
 'h2':ParagraphStyle('h2',fontName='STSong-Light',fontSize=12.5,leading=18,textColor=TEAL,wordWrap='CJK',spaceBefore=13,spaceAfter=6),
 'p':ParagraphStyle('p',fontName='STSong-Light',fontSize=10.2,leading=15.4,textColor=NAVY,wordWrap='CJK',spaceAfter=9),
 'small':ParagraphStyle('small',fontName='STSong-Light',fontSize=8.3,leading=12.2,textColor=MUTED,wordWrap='CJK',spaceAfter=7),
 'cell':ParagraphStyle('cell',fontName='STSong-Light',fontSize=8.5,leading=12.1,textColor=NAVY,wordWrap='CJK'),
 'metric':ParagraphStyle('metric',fontName='STSong-Light',fontSize=20,leading=27,textColor=TEAL,wordWrap='CJK'),
}
story=[];textlog=[]
def p(t,kind='p'):
    story.append(Paragraph(t,S[kind]));textlog.append(html.unescape(__import__('re').sub('<[^>]+>','',t)))
def h(t):p(t,'h2')
def page(t):
    if story:story.append(PageBreak())
    p(t,'h1')
def table(headers,data,widths):
    cells=[[Paragraph(html.escape(str(v)),S['cell']) for v in r] for r in [headers]+data]
    t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('LINEBELOW',(0,0),(-1,0),.8,TEAL),
      ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DBE5E9')),('VALIGN',(0,0),(-1,-1),'TOP'),
      ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(t);story.append(Spacer(1,9));textlog.extend(' | '.join(str(v) for v in r) for r in [headers]+data)
def pct(v):return '-' if v is None else f'{v:+.2f}%'
def vr(v):return '暂不估值' if not v else f"{v['low']:g}-{v['high']:g}"
def link(label,url):return f'<link href="{html.escape(url,quote=True)}" color="#087E8B">{label}</link>'
def src(label,url):p('来源：'+link(label,url),'small')

p('历史研究，究竟有多可靠？','title')
p('Trading OS 公司研究全面复盘<br/>报告日期：2026年10月23日 | 统一行情截止：2026年10月22日','small')
p('结论：早期报告值得作为研究线索保存，数值估值和“安全边际”判断需要明显降权；后期研究改进了现金、资本和归属口径，但还没有足够的事后样本证明其长期定价准确。')
table(['观察对象','结果','含义'],[
 ['7月明确“买入”241家','92涨 / 148跌 / 1平；平均 -1.44%','绝对收益兑现偏弱；并非全部跑输市场'],
 ['其中有估值236家','210家期末低于旧估值下沿','许多“便宜”判断没有兑现'],
 ['初始低于旧估值225家','122家期间触及；仅20家期末仍达下沿','短暂触及与持续兑现差别很大'],
 ['9月已有复核186家','174修订 / 12保留；32家有明确纠错记录','修订率不是错误率；32是证据下限'],
 ['7月与当前均有估值781家','297家估值中枢下修超过25%','需分新事实、方法变化与原错误'],
 ],[119,173,207])
h('最重要的三个判断')
p('第一，存在可以直接确认的研究错误，不能用“股市不可预测”解释。青岛啤酒季报利润抄错、伊利每股压力放大十倍、银行估值公式及现金权益桥不闭合，都属于研究过程问题。')
p('第二，商业方向正确仍可能买贵、估值失真或现金预测过于乐观。宁德的份额与收入增长没有阻止利润率和现金转换恶化；星宇的产品升级没有保证供应商取得更多股东现金。')
p('第三，这轮价格表现只能检验约一至三个月的兑现，不能裁定五年现金路径。必须保留未证实、未到期和资料不足的结论。')
p('本次已恢复5个历史快照，完成7月全部买入名单的行情核对，并复核186份既有质量记录。对关键案例重新读取9份公司原始财报；未对5,435家公司逐一重做基本面研究。','small')

page('01 评估范围与时间纪律')
p('以Git中的真实历史版本冻结当时判断，避免拿今天已修订的报告冒充最初预测。公司为统计单位；不同快照存在重叠，不能相加成独立样本。')
table(['快照','公司记录','有估值','本次可比行情/估值'],[
 [m['date'],m['company_records'],m['valued'],summaries[i]['overall']['comparable_value_n']] for i,m in enumerate(manifest)
 ],[112,121,121,145])
p('7月20日快照含241家“买入”，其中236家有估值；另外5家仍纳入收益统计。8月8日已经经历旧研究重置，只有16家保留结构化估值，不能把这个小样本与7月5,435家直接当作同一研究策略。')
h('如何观察“后来怎样了”')
p('7月、8月和9月快照原则上分别从7月21日、8月19日和9月15日收盘开始观察，统一结束于10月22日。个别无当天行情的公司从首个可观察交易日开始，具体日期保留在逐股表。7月买入名单241家起点完全一致。此举给历史版本留出可见时间；它不是最优成交价，也不是账户实际买入价。')
p('个股税前简单总回报 =（期末股价 × 送转后股数 + 期间已除息现金分红 - 起始股价）/ 起始股价。现金不再投资，不扣手续费、税负或流动性成本。价格超额用仅处理送转的价格涨跌，对比沪深300价格指数；没有把含息个股回报和不含息指数混为同一口径。')
p('旧估值按其原资料截止日至观察起点之间已经发生的分红送转调整；观察期内的分红和股数变化也联动处理。未把后复权价格比值当成总回报。配股或公司行为信息不明者保留缺口。')
h('研究可靠性分四层')
table(['层次','本次可下的结论'],[
 ['事实与计算','数字、单位、期间、公式、权益归属能够核验；明确错误直接记为过程缺陷。'],
 ['经营认知','用随后披露检验关键因果链；区分已被削弱与尚未证明。'],
 ['估值方法','检查是否能复算、是否随规则大幅改变、有没有把乐观恢复当基准。'],
 ['价格兑现','统计涨跌、相对市场、期间触及和期末位置；不能替代内在价值判断。']],[104,395])

page('02 7月买入名单：没有证明选股优势')
p(f"241家公司中，{buy['up']}家上涨、{buy['down']}家下跌、{buy['flat']}家持平；上涨比例{buy['up']/241:.1%}。等权平均税前简单回报{pct(buy['mean_pct'])}，中位数{pct(buy['median_pct'])}。这是名单质量的事后观察，不是对条件式交易计划的完整回测。")
d=Drawing(499,66);left=0
for n,c,label in [(92,TEAL,'上涨92'),(148,RUST,'下跌148'),(1,colors.grey,'')]:
    width=499*n/241;d.add(Rect(left,27,width,23,fillColor=c,strokeColor=None));
    if label:d.add(String(left+8,7,label,fontName='STSong-Light',fontSize=11,fillColor=NAVY))
    left+=width
story.append(d);story.append(Spacer(1,12))
peer=[]
for key,label in [('buy','买入'),('hold','持有'),('watch','观察'),('avoid','回避'),('research_only','仅研究')]:
    s=july['by_status'][key];peer.append([label,s['n'],s['return_n'],pct(s['mean_pct']),pct(s['median_pct'])])
table(['历史标签','记录数','可比收益数','平均回报','中位回报'],peer,[88,78,95,119,119])
p(f"相同历史估值样本的全体可比公司平均回报为{pct(allj['mean_pct'])}；买入名单比这一简单对照低约{allj['mean_pct']-buy['mean_pct']:.2f}个百分点。旧“回避”组并没有表现更差。这不支持把早期标签直接当作有效的选股排序。")
h('市场背景不能省略')
p('同一窗口沪深300价格指数下跌14.83%。241家中211家的送转调整价格表现好于该指数。因此，“买入名单绝对亏损”成立，“绝大多数跑输沪深300”不成立。')
p('但全体历史估值样本也普遍好于沪深300：该指数的大盘风格与全市场名单不同。未经行业、规模、估值风格和风险暴露控制，不能把跑赢沪深300称为研究创造的超额收益。')
p('均值受少数大涨公司影响：澳弘电子约+171.63%，而买入名单中位数为负。判断可靠性时应同时看中位数、失败个数和亏损原因，不能只选成功案例。')

page('03 有多少跌破旧估值，有多少兑现？')
p('以下“低于估值”表示市场价格低于冻结的旧合理价值，经现金分红与送转调整；它既可能是市场继续低估，也可能是原估值过高。只有结合基本面证据才能区分。')
table(['7月有估值样本','起点','10月22日期末'],[
 ['旧买入236家：低于下沿',225,210],['旧买入236家：区间内',11,22],['旧买入236家：高于上沿',0,4],
 ['全部估值样本：低于下沿',860,1175],['全部估值样本：区间内',2155,1822],['全部估值样本：高于上沿',2407,2425]
 ],[265,117,117])
p('全体旧估值5,435家中有5,422家可作严格比较；13家保留行情或公司行为缺口。不能把缺失者当作没有下跌。')
h('把“涨了”与“达到旧估值”分开')
table(['起点低于下沿的旧买入225家','家数'],[
 ['期末达到或超过旧估值下沿',20],['上涨，但期末仍低于下沿',66],['下跌，期末仍低于下沿',138],['持平，期末仍低于下沿',1]
 ],[407,92])
p('这225家中，122家曾以期间最高价触及估值下沿，但只有20家期末仍达到；其余102家又回到下沿以下。“曾经达到目标”不能直接算成持续正确，也没有假定能够在最高价卖出。')
p('另有5家原买入公司起点在合理区间内，期末跌到了下沿以下。全体旧估值样本有461家公司从起点不低于下沿，变成期末低于下沿；这是比“今天低于旧估值”更严格的新增跌破统计。')
h('“按预期上涨”的可检验定义')
p('本报告把“起点低于估值、随后达到下沿”作为价格向估值收敛的描述，不宣称旧报告承诺过三个月兑现。旧报告普遍没有统一预测期限、概率或容许偏差，因此无法诚实地给出一个全库“预测命中率”。')

page('04 关键公司：价格结果与研究结论并列')
casecodes=['600519','300750','601799','000858','600036','600887','600309','601899','000333','300308','300502','600600']
data=[]
for c in casecodes:
    sym='CN:'+c;x=next(z for z in julyrows if z['symbol']==sym);old=bydate['2026-07-20'][sym]['value_range'];new=bydate['2026-10-23'][sym]['value_range']
    data.append([x['name'],vr(old),vr(new),f"{x['end_close']:.2f}",pct(x['total_return_pct'])])
table(['公司','7月估值','当前报告估值','10月22日价','7月起回报'],data,[89,103,117,91,99])
p('单位：元/股；回报含观察期税前现金分红。估值列展示各版原文数值，送转和分红标准化见逐股表。当前报告并未统一吸收10月全部新财报；例如宁德时代9月版尚未吸收本次复盘读取的10月三季报。','small')
h('应当怎样读这张表')
p('星宇是旧乐观预测被后续经营削弱、股价也下跌的案例；招商银行体现商业机制较有支持、价格也上涨，但旧估值并未充分兑现；青岛啤酒则说明价格落在旧估值内仍不能证明报告数字正确。')
p('宁德、中际旭创、新易盛原为“观察”，价格下跌说明当时对高预期的谨慎有价值，但不能据此认证当时给出的估值下沿就是可靠的底部。')
p('紫金当前报告的8-15元显著低于市场价。有限矿山现金模型和持续转储、并购、扩产能力之间的边界仍需检验；不能因为新估值更低，就把它自动称为比旧24-35元更准确。')

page('05 能够直接确认的错误')
h('青岛啤酒：原始事实抄错，估值恰巧接近也不能免责')
p('7月8日旧报告把2026Q1扣非净利润写成41.30亿元。正式一季报为17.0581亿元，旧数约为实际的2.42倍；同一报告还混用了季度ROE与其他利润率口径。这些数据在研究时已经公开，属于当时可避免的错误。')
p('截至10月22日股价49.71元，仍在旧45-65元区间内。这个案例直接说明：价格“在区间内”与研究过程可靠是两个不同结论。')
src('青岛啤酒2026年一季报，PDF第2页（公司报告第1页）','https://www.hkexnews.hk/listedco/listconews/sehk/2026/0427/2026042703016_c.pdf')
h('伊利：每股流动性压力被放大十倍')
p('9月复核记录保留了原错误与修正：50亿元净偿债压力除以63.25360667亿股，应为0.790468元/股，原稿写成7.90元/股。这里不涉及未来预测，直接除法就能判定。主PE估值没有因此改变，也不代表错误可以忽略。')
p('这类过度悲观错误尤其值得警惕：更低的估值、更多扣减和更复杂的模型，都不能代替正确的单位与现金守恒。')
h('银行与矿业：模型关系和物理约束没有闭合')
p('宁波银行既有复核记录明确指出：原PB区间与给定ROE、资本成本和增长不相容，分配与终值路径也不能复算原估值。江苏、南京、常熟等银行另有终值算术、权益或规模口径修正。')
p('紫金的既有复核则发现，含金含铜储量被当作100%可售产品，个别矿尾年产量超过现有储量约束；并存在已支付投资款未配上取得股权资产的问题。它们是具体约束错误，而不是因为后来的金价变了。')
h('茅台：时间先后关系错误')
p('既有H1复核纠正了用上半年结果判断7月第二次提价有效与否的时序矛盾。发生在6月30日之后的行为，不能由截至6月30日的经营期结果验证；报告发布日期晚于7月也不能改变这一点。')
p('以上伊利、银行、矿业和茅台细节以仓库既有复核记录为直接证据。本轮独立重读了相关关键财报，但没有逐一重跑这些公司当时全部模型或重验全部附件。','small')

page('06 旧认知被后续经营削弱的案例')
h('星宇：把高价值产品增长过快等同为股东价值增长')
p('7月报告采用2026年归母19亿元，并期待H1/Q3收入继续12%以上增长，给118-145元。实际H1收入仅增1.87%，归母下降5.26%，经营现金流下降17.30%；旧稿设定的利润增长和现金条件没有满足。')
p('更关键的认知缺口是年降、客户车型和前置资本投入如何吞掉智能车灯增量毛利。后来报告补进了产品与产能证据，并把价值降至50-70元。但“毛利率没升，所以产品升级没价值”又会走向另一端：智能灯毛利额增长约49%的正面证据仍须纳入。')
src('星宇股份2026年半年报，PDF第7页主要财务指标','https://static.cninfo.com.cn/finalpage/2026-08-27/1225509977.PDF')
h('五粮液：风险已经识别，恢复幅度仍缺少约束')
p('7月旧稿已经知道收入确认更正、渠道倒挂和库存问题，却采用约170亿元正常化利润；8月研究进一步给出200-250亿元恢复路径、85-125元估值。H1利润87.53亿元符合当时业绩预告，不能称“利润预告落空”。真正的问题是：从这点利润恢复，跳到了可持续高盈利。')
p('H1经营现金流为-21.54亿元，Q2扣非仅约4.47亿元，促销与履约义务需要解释。9月新稿还承认旧超额现金出现70-90亿元与700-900亿元的十倍差异，并存在金融收益和现金本金重复计价风险。撤回核心估值，比继续下调一个数字更诚实。')
src('五粮液2026年半年报，PDF第6-7页及收入/现金附注','https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-29/54759c03-9537-4b38-8e23-c98946014e59.PDF')
h('宁德：竞争力维持，现金转换的风险正在兑现')
p('旧8月版以份额、收入和账面现金支持330-460元；9月版已更认真处理税费、客户让利和再投资，将区间重建为290-345元。这项改进应记功。')
p('10月披露的Q3收入同比+58.58%，归母仅+14.54%；前三季CFO同比-23.60%。用H1的602.17亿元与前三季616.25亿元相减，Q3单季仅约14.08亿元。这支持现金转换和资本效率担忧，尚不足以宣判长期制造优势消失，也没有验证五年后的终值。')
src('宁德时代2026年三季报，PDF第1页；H1金额来自正式半年报','https://static.cninfo.com.cn/finalpage/2026-10-21/1225613175.PDF')

page('07 哪些判断值得保留，哪些仍未证实？')
h('招商银行：负债成本优势有事实支持')
p('旧报告对低成本存款、零售基础和资本缓冲的判断，得到H1经营证据支持：存款成本率0.97%，归母利润同比+2.02%；同期仍存在信用卡和消费贷风险。7月观察起点37.99元，期末41.82元，回报约+10.08%。这是可保留的机制判断，但不能把上涨当作长期ROE路径已获认证。')
src('招商银行2026年半年报，主要经营与平均存款成本表','https://static.cninfo.com.cn/finalpage/2026-08-29/1225530237.PDF')
h('美的：需从会计分类穿透到经济结果')
p('旧稿认可制造平台和业务组合，同时提示扣非压力。H1归母同比+1.66%，扣非-25.31%，公司解释汇兑损失列经常性、风险管理衍生品收益列非经常性。若只盯扣非下降而忽略对冲，就会误判主业损伤；若把全部衍生收益当稳定经营利润，也会反向高估。')
src('美的集团2026年半年报，PDF第9页及指标说明','https://static.cninfo.com.cn/finalpage/2026-08-28/1225533135.PDF')
h('万华：盈利修复判断部分成立，股东价值仍取决于资本')
p('H1归母同比+64.35%、扣非+54.96%，支持旧稿对盈利修复的方向判断。但CFO仅+11.93%，扩产、融资、少数权益和未付工程款仍决定普通股现金。原来72-86元与后来38.4-59.1元的分歧，不能简单说成“利润预测错了”；要检查完整资本代价是否被旧估值漏掉。')
src('万华化学2026年半年报，PDF第6页及资本、融资附注','https://static.cninfo.com.cn/finalpage/2026-08-25/1225497561.PDF')
h('伊利与茅台：成熟品牌的价值不能仅用高ROE外推')
p('伊利H1利润下降20.02%、澳优减值与库存压力强化了资本配置风险；CFO大增也不能抵消并购回报损失。茅台H1归母下降1.95%，品牌经济性与高增长前景应分别判断。后续模型加强现金分配与必要资本是合理改进，但成熟品牌能保持多久、现金何时归股东仍需跨周期验证。')
src('伊利2026年半年报','https://static.cninfo.com.cn/finalpage/2026-08-27/1225511409.PDF')
src('贵州茅台2026年半年报','https://static.cninfo.com.cn/finalpage/2026-08-15/1225475868.PDF')

page('08 估值大幅重写，透露了什么？')
table(['历史快照','原有估值','当前仍有估值','中枢下修>25%','上修>25%'],[
 [r['snapshot'],r['n'],r['matched'],r['midpoint_down_gt25'],r['midpoint_up_gt25']] for r in revisions
 ],[108,87,104,108,92])
p('7月与当前均有估值的781家公司中，297家中枢下修超过25%，占38.0%；仅11家上修超过25%。配对样本中位变化约-17.91%。送转与分红在可得记录范围内进行了时点标准化。')
p('另有4,654家旧估值在当前状态中没有对应的非空估值。这大部分反映了研究重置、覆盖收缩与重新筛选，不能宣称它们全部研究错误；但也不能继续把这些旧数字当作当前可信估值库。')
p('9月14日与当前配对中，765家公司资料截止日期相同，仍有50家估值中枢下修超过25%。这部分尤其需要回查原有口径、漏用信息和经营假设，不能笼统归因于后来新出了财报。')
h('四种变化必须分别记账')
table(['变化性质','判断方法'],[
 ['新事实','旧截止后出现的需求、成本、税费、治理与融资变化；评价旧研究是否合理预留风险。'],
 ['旧信息漏用','当时已公开，却没有进入关键判断，如重要合同或政策；属于研究过程缺陷。'],
 ['事实/公式纠错','单位、股数、少数权益、可转债、分红、储量或公式错误；无需等待市场判决。'],
 ['方法/假设改变','资本成本、长期增长、再投资、资产回收与有限寿命的取舍；可能更合理，也可能过度保守。']],[108,391])
p('7月茅台1150-1350元，7月后续重置到750-1100元，当前1020-1220元；宁德从290-370元，上调到330-460元，再降至290-345元。这类来回变化说明不能把每一次改写都描述成“发现新事实后更准确”。需要解释改变的参数与证据。')
h('当前版本仍未获得事后认证')
p('10月两个批次覆盖191家公司，记录显示46家重做、145家保留。复核明确复用既有财报和底稿，属于方法与表达检查，不能当作191家独立重新取证，更不能当作191家预测正确。很多现行稿刚改完几天，没有足够新经营结果检验。')

page('09 “多少可靠”应怎样诚实回答')
table(['能够量化的部分','数量与边界'],[
 ['已有186家质量复核','174修订、12保留。至少32家记录了具体事实、口径或模型纠错，见证据清单。'],
 ['其余142家修订','包括经营假设重建、补证、分配桥和表达修正；本次不把它们统一算作错误。'],
 ['12家当时保留','仅表示当时复核未发现需改内容；不等于长期研究正确，也不是随机样本的正确率。'],
 ['全库可靠率','无法给出有效单一百分比：观察窗口短，报告期限不一，复核样本有选择且版本重写频繁。']],[141,358])
p('32家是对既有复核记录逐项归类的明确纠错下限；不是本轮对32家公司全部附件完成独立再审的声明。它与174家修订重叠，也与10月46家重做重叠，不能相加。')
h('主要的认知偏差')
p('1. 把高份额、高毛利或产品升级直接外推成普通股现金增长，低估客户议价与必要资本。<br/>2. 识别了风险，却仍在基准里放进较强恢复；风险章节与估值互不约束。<br/>3. 把合并现金、存款、预收款或监管资本混同为普通股可分现金，或把金融收益和本金重复计价。<br/>4. 把未来尚未承诺等同于完全不能估计，或为了“保守”忽略已有资产与未来成长；这会造成反向低估。<br/>5. 两种估值共用同一乐观假设，却把两者接近当成独立证明。')
h('今后使用历史研究的权重')
p('早期7月稿：保留公司线索、竞争机制和风险问题，所有决定估值的数字回到原件；不沿用旧“买入区间”与仓位表。8月至9月稿：更重视财务与现金桥，但先核实有无后续纠错。10月稿：按当前信息截止阅读，其长期商业假设仍作为待检验的预测。')
p('每轮真正应保留的是原预测、随后实际、偏差原因和估值影响；在下一版模型中吸收实际数据后，不能反过来宣布旧模型得到验证。对未到期的长期判断，保留“尚未证实”；对明确的单位或公式错，不用等到五年后才判错。')

page('10 价格上最成功与最失败的旧买入样本')
ordered=sorted(buyrows,key=lambda x:x['total_return_pct'])
def extreme_table(rs):
    return [[x['name'],x['symbol'].split(':')[-1],pct(x['total_return_pct']),vr(bydate['2026-07-20'][x['symbol']]['value_range']),x.get('end_position','无估值')] for x in rs]
h('观察窗口表现最弱的10家')
table(['公司','代码','税前回报','旧估值','期末位置'],extreme_table(ordered[:10]),[103,84,99,114,99])
h('观察窗口表现最强的10家')
table(['公司','代码','税前回报','旧估值','期末位置'],extreme_table(list(reversed(ordered[-10:]))),[103,84,99,114,99])
p('以上只按同一窗口回报排序。没有把最强10家标成基本面研究正确，也没有把最弱10家全部判为长期生意失效。逐股表保留全部241家，便于同时看成功与失败。','small')

page('11 数据覆盖、局限与可复核材料')
h('覆盖与独立核对')
p('已从Git恢复5个快照，对7月5,435份估值关联报告、8月707份、9月811份及当前814份报告建立可读底稿。7月有1,597份报告正文没有可直接打开的HTTP来源链接，占29.4%；这只是可追溯性缺口，不能据此宣布内容全错。')
p('累计采集5,463个证券/指数的公开行情与公司行为资料。7月241家买入收益全部覆盖；全体估值样本5,435家中5,422家可比。八家重点公司10月22日收盘价在腾讯与新浪逐一交叉核对，全部一致。')
p('重新读取9份公司财报原件的关键财务表和相关上下文；财报原件身份已核对。青岛啤酒、星宇和美的关键页另作视觉核对；美的及港交所部分字体文本抽取乱码，采用原表视觉和公告全文共同确认。没有将链接存在等同于来源验证。')
h('仍然无法回答的部分')
p('观察窗只有约一至三个月，没有足够样本估计五年终值预测的准确率；未逐一获取5,435家最新财报并重算全部模型；没有账户交易、买入条件满足时点和执行数据，不能归因实际账户损益；缺失或停牌样本没有伪造期末价，也没有用末次交易价混入主统计。')
p('本文基本面证据收口到10月22日；三季报披露进度不一致。宁德已使用10月21日正式三季报；其他案例按实际已核验材料使用H1。搜索出现的10月24日紫金三季报未纳入，避免未来资料污染。')
h('交付材料')
table(['材料','用途'],[
 ['本报告PDF','结论、错误与认知案例、口径和局限。'],['7月买入名单241家.csv','完整名单，原估值、实际回报、期间触及和期末位置。'],
 ['逐股核对表.csv','五个快照的逐股统计；重复公司是不同版本，不能简单汇总行数。'],
 ['recorded-corrections.json','32家公司明确纠错记录及原有取证范围。'],['price-summary.json / valuation-revisions.json','统计汇总与配对估值变化，便于重算。'],
 ['脚本与原始响应压缩文件','复现计算；大型原件和行情留在本次工作目录，Git中保存小型结果与程序。']],[174,325])
p('正式公司报告、覆盖状态、研究队列和筛选池均未改写。当前未建立价格触发、自动交易或新的研究评级体系。','small')

page('12 来源与复现定位')
p('Git仓库：chess99/trading-os。以下提交固定快照版本；原报告与状态路径保留在逐股表和manifest中。工作区同期存在其他修改，本次只提交独立复盘目录。')
table(['快照','Git提交'],[[m['date'],m['revision']] for m in manifest],[112,387])
h('仓库证据')
for label,path in [
 ('9月186家公司复核记录','docs/reviews/2026-09-system-upgrade/audit-results.jsonl'),
 ('核心池10月复核记录','docs/reviews/2026-10-core-moat-h1/progress.json'),
 ('质量池10月复核记录','docs/reviews/2026-10-quality-h1/progress.json'),
 ('星宇研究质量样本审查','docs/reviews/2026-09-15-xingyu-research-quality-review.md')]:
    p(link(label,'https://github.com/chess99/trading-os/blob/'+manifest[-1]['revision']+'/'+path),'small')
h('公司原件')
sourceitems=read('primary-sources.json')
names={'catl-q3':'宁德时代2026Q3','xingyu-h1':'星宇2026H1','wuliangye-h1':'五粮液2026H1','cmb-h1':'招商银行2026H1','moutai-h1':'贵州茅台2026H1','yili-h1':'伊利2026H1','wanhua-h1':'万华2026H1','midea-h1':'美的2026H1','tsingtao-q1':'青岛啤酒2026Q1'}
for x in sourceitems:p(link(names.get(x['id'],x['id']),x['url']),'small')
h('公开行情')
p('腾讯日线主接口与备用接口提供未复权价格、分红送转元数据；新浪日线与分红配送表补齐北交所等缺失。具体每只股票的URL、抓取时间与响应保存在market.jsonl.gz；八家交叉核对见cross-provider-check.json。','small')
p('可重算顺序：collect.py固定历史快照；reports.py恢复正文；market.py与sina_fallback.py获取行情和公司行为；analyze.py生成统计；build_report.py生成本报告及中文核对表。复现时应先使用已冻结数据，重新抓取的供应商历史可能发生更正。','small')
p('最终判断：目前有足够证据降低对早期数值结论的信任，保留一部分商业机制和风险洞察；还没有足够证据给整个研究库颁发一个“正确率”。后续应围绕冻结假设的经营兑现检验，而不是以更新次数、章节数量或估值变低作为质量证明。')

def footer(canvas,doc):
    canvas.saveState();w,h=A4
    canvas.setStrokeColor(colors.HexColor('#D5E1E6'));canvas.line(48,43,w-48,43)
    canvas.setFont('STSong-Light',8);canvas.setFillColor(MUTED)
    canvas.drawString(48,29,'Trading OS | 历史研究可靠性评估 | 2026-10-23')
    canvas.drawRightString(w-48,29,str(doc.page));canvas.restoreState()
dest=OUT/'trading-os-历史研究可靠性评估-2026-10-23.pdf'
doc=SimpleDocTemplate(str(dest),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=43,bottomMargin=57,
 title='Trading OS 历史研究可靠性评估',author='研究复盘',allowSplitting=True)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
(ROOT/'output/报告正文.txt').write_text('\n\n'.join(textlog))
print(dest)
