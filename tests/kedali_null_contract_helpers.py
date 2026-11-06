"""Kedali current-null metadata contract, separate from historical finance.
Prepared statically. Runtime calls below require separate execution admission.
"""
import ast,hashlib,json,math,shutil,stat,struct,subprocess,sys
from pathlib import Path
CODE="002850"
BASE='research/companies/CN/002850/models/'
HIST='research/companies/CN/002850/models/2026-Q3-evidence/historical/'
EXPECTED={'research/companies/CN/002850/models/2026-Q3-evidence/AUX-LIMITED-ACTUAL-REVIEW.json': {'bytes': 8018, 'sha256': 'd5a45bec26ff5caf3b911001c8d734356f7086719c6da036e04545b9c4db99ec', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/CONSUMER-DECISION-MATRIX.json': {'bytes': 626967, 'sha256': '543d92ab948a674409e5d37a39d87dea2ef371f24b7004d3189f0f4a942af018', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/CURRENT-COMPONENTS-RETAINED.json': {'bytes': 77193, 'sha256': 'a74ba19dbc9f5dd05ca3a0a63d0c0fe4ff41c4b4544349cd9916ac39b39ff4d7', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/HISTORICAL-OUTPUT-IDENTITY.json': {'bytes': 391, 'sha256': '5602dc552c5343dbd59d99e31bfc75d6a687804d849348f96e111ecd51b3104f', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/ORIGINAL-ARTIFACT-IDENTITIES.json': {'bytes': 106810, 'sha256': '1c8286c9604a183368820941a36c7ab97d755554664ef69cddb6770d6c17bdf3', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/PUBLIC-MANIFEST.json': {'bytes': 3501, 'sha256': 'b5882d96e2090113f6a54f663c086d8815a849f7d9f9fc6ef898bcaabe90ba3a', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/README.md': {'bytes': 2810, 'sha256': 'bb0abb40dea655ba5ce7ab995fff044d9b969daf81d43adc900aed005ebc68a8', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/TYPED-FAILURES.json': {'bytes': 59541, 'sha256': 'd007bf9f136530a78a4247e049f054f8e1e40b57d6fa84984dbf4f67e31b9cf8', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/auxiliary-basis/SOURCE-IDENTITIES.json': {'bytes': 3270, 'sha256': '5d4de23c15b8ab6925c094b5aa139a98229cf79294e06a1839279a31b4226d23', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/auxiliary-basis/Y1-OPERATING-INPUT.json': {'bytes': 1846, 'sha256': 'd49403e55519a4cf307d8c63be4de59b6f7144396c6f4224e8f77333f3b7c935', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/auxiliary-basis/production-source-excerpts.txt': {'bytes': 5325, 'sha256': '51af8c77e3f04e3783794bbe42db6fe86b41b50a4ef96c63e02dcadfd3a01530', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/historical/2026-Q3.py': {'bytes': 51790, 'sha256': '808fa7b064fce0bac7c286ae28659ace3f8072e754d7740cb1a4343f94881e5c', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/historical/previous-2026-Q3.md': {'bytes': 31033, 'sha256': 'ddfa5441ca11fa48c376e92785f43af6376a1149899d5e24c7c678d71f5761a0', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/sources/1225652012.pdf': {'bytes': 86600, 'sha256': '76dfd31e385ee1d03d218693395462fa673488870df0378c29b1c55c653b28a1', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/sources/1225652012.txt': {'bytes': 3775, 'sha256': '66cae44ef9db4c6dc09e957f492631c07f22975e0e140be914a18f394d39c381', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/sources/OFFICIAL-SOURCES.json': {'bytes': 526, 'sha256': '5deb5b80f9abe49b8d78b603395fab74da3ed5a71a40247d534a65ca8ae05455', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-independent-recompute.py': {'bytes': 1056, 'sha256': '4ffcec3f3ec40b1bb46eef6982613324f04a13848a6bff8fc962f4b031dc5ccd', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-output.json': {'bytes': 3531, 'sha256': 'ffe51d2c0511513e45a75786ff36da5774fd1ef27c4f9c2dcb28f5354c5c47ad', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3.py': {'bytes': 1056, 'sha256': '4ffcec3f3ec40b1bb46eef6982613324f04a13848a6bff8fc962f4b031dc5ccd', 'mode': 420}, 'research/companies/CN/002850/reports/2026-Q3.md': {'bytes': 36103, 'sha256': 'e9d237cbe4f2667e508bf488211774bdd794e25307a68f1d8c5a89cd1696690a', 'mode': 420}, 'research/companies/CN/002850/models/2026-Q3-evidence/historical/2026-Q3-output.json': {'bytes': 11501848, 'sha256': '8a75d6543b5482599825b5e97ed546c5357f1ed0dc5c1dcb06e4922ddf50431f', 'mode': 420}}
CURRENT_OUTPUT={'schema': 'kedali-current-null-with-role-specific-auxiliary-v1', 'symbol': 'CN:002850', 'report_period': '2026-Q3', 'information_cutoff': '2026-11-03T00:00:00Z', 'model_as_of': '2026-11-03T00:00:00Z', 'operating_budget_anchor': '2026-10-26T08:56:00+00:00', 'annual_PV_origin': '2026-10-26', 'status': 'PRIMARY_AND_HOLDER_UNPROVEN_AUXILIARY_ONLY_ADOPTED', 'value_range': None, 'valuation_note': '主方法为五年条件现金加有限实现经济终值；核心low/high的完整尾期现金、分配及PV独立覆盖未闭合，value_range留空，不是全公司资金不足或零价值。仅原structural Y4/J为typed经济拒绝。正常化8/10倍EV/EBIT加超额净现金的独立辅助80.34—99.95元/股按限定角色采用，不升核心或Y5；费用未知、225m仅方案150—300m中点预算、期权现金/股数条件成对。', 'return_model': None, 'return_model_note': '独立基准五年现金组件与同base完整Y5状态已有证据；核心Y5端点的完整长期采用仍未闭合，return_model留空，不拼接IRR或回退旧/辅助/乐观/未审own终值。286448468条件全摊薄股与60126期权及6337881.66元认款配对，激励回购非持有人分红、不预设注销。Nov3是信息版本，原Oct26经营/周年PV起点不移动。', 'numeric_model_pass': False, 'primary_adoption': False, 'holder_adoption': False, 'accepted_auxiliary': {'case': 'new/auxiliary', 'role': 'conditional auxiliary only; not core or Y5', 'display_range_CNY_per_share': ['80.34', '99.95'], 'full_precision_original_independent': {'ebit1': '2.808683999999999824', 'net_cash': '0.54415470770669797256', 'low': '80.341245559416629746331895201478263797172760581843991569192124288128502052243477', 'high': '99.951641939682834025699868640945218809827951322818734712171684576787472991477127', 'components': {'opening_common_cash_before_options': '2.28846428434969797256', 'restricted': '1.089220', 'necessary_operating_cash': '0.51717350', 'common_debt': '0.0683027607130', 'future_buyback': '0.07595119759', 'option_proceeds': '0.00633788166', 'already_paid': '0.14904880241', 'incremental_paid': '0.09926114452'}, 'shares': '0.286448468', 'cash_timing': 'All selected buyback cash deducted at inception for auxiliary only'}, 'units': {'ebit1': 'CNY billion', 'net_cash': 'CNY billion', 'components': 'CNY billion', 'shares': 'billion shares', 'low': 'CNY per share', 'high': 'CNY per share'}, 'whole_C_pairwise_pass': False}, 'independent_cash_components': {'file': '2026-Q3-evidence/CURRENT-COMPONENTS-RETAINED.json', 'pointer': '/base_annual', 'complete_conditional_paths': 13, 'future_cash_not_promised': True, 'not_a_holder_interface': True}, 'current_typed_refusal': {'source': 'new/scenarios/structural', 'dependent_consumer': 'new/values/structural', 'independent_sources': 1, 'year': 4, 'entity': 'J'}, 'current_consumers': 34, 'previous_consumers_historical_only': 34, 'fallback_to_historical_own_aux_optimistic': False, 'original_false_preserved': True, 'new_financial_execution': False, 'dependencies': ['2026-Q3-evidence/README.md', '2026-Q3-evidence/CONSUMER-DECISION-MATRIX.json', '2026-Q3-evidence/TYPED-FAILURES.json', '2026-Q3-evidence/ORIGINAL-ARTIFACT-IDENTITIES.json']}
CURRENT_RESULT={'symbol': 'CN:002850', 'name': '科达利', 'outcome': 'covered', 'report_period': '2026-Q3', 'information_cutoff': '2026-11-03T00:00:00+00:00', 'summary': '量产工程优势支持持续覆盖，客户议价与扩产资本约束普通股现金。核心及holder尾链未证，均暂缺；独立条件辅助80.34—99.95元/股仅作辅助，原结构弱Y4江苏为真实预算拒绝。', 'key_logic': ['安全量产、客户协同与跨基地复制有经营证据，二供和客户集中限制永久定价权', '原243—366亿元五年收入与资本/税负预算保留，13条独立五年现金路径完成但不是未来付款承诺', '当前回购事实按已付/未付及库存/发行分开，条件辅助现金组成完整，主核心尾链仍未完成采用'], 'risks': ['客户降价与扩建资本使增长无法转换为普通股现金', '核心尾期资金与分配完整覆盖未闭合；不能把缺键认作现金短缺或用辅助替代', '结构弱Y4/J有限授信不能覆盖必要现金，其他路径不因此被判失败', '税惠续期、跨层资金实现与海外/机器人追加投入均有条件', '费用未知，激励回购非注销；期权最终登记与配对认款仍待确认'], 'value_range': None, 'valuation_note': '主方法为五年条件现金加有限实现经济终值；核心low/high的完整尾期现金、分配及PV独立覆盖未闭合，value_range留空，不是全公司资金不足或零价值。仅原structural Y4/J为typed经济拒绝。正常化8/10倍EV/EBIT加超额净现金的独立辅助80.34—99.95元/股按限定角色采用，不升核心或Y5；费用未知、225m仅方案150—300m中点预算、期权现金/股数条件成对。', 'return_model': None, 'return_model_note': '独立基准五年现金组件与同base完整Y5状态已有证据；核心Y5端点的完整长期采用仍未闭合，return_model留空，不拼接IRR或回退旧/辅助/乐观/未审own终值。286448468条件全摊薄股与60126期权及6337881.66元认款配对，激励回购非持有人分红、不预设注销。Nov3是信息版本，原Oct26经营/周年PV起点不移动。', 'source_urls': ['https://static.cninfo.com.cn/finalpage/2026-10-24/1225618092.PDF', 'https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-15/65231f12-3ff0-4bd6-ae7b-3f56d01c8eae.PDF', 'https://pdf.dfcfw.com/pdf/H2_AN202603271820802676_1.pdf', 'https://static.cninfo.com.cn/finalpage/2024-04-13/1219594078.PDF', 'https://static.cninfo.com.cn/finalpage/2025-04-18/1223126375.PDF', 'https://static.cninfo.com.cn/finalpage/2026-04-23/1225151030.PDF', 'https://static.cninfo.com.cn/finalpage/2026-06-17/1225374370.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-15/1225473167.PDF', 'https://static.cninfo.com.cn/finalpage/2026-10-21/1225613175.PDF', 'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12548782&stockid=300953', 'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12497397&stockid=002850', 'https://static.cninfo.com.cn/finalpage/2026-04-28/1225198890.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-13/1225470152.PDF', 'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12632558&stockid=002850', 'https://static.cninfo.com.cn/finalpage/2026-04-28/1225198893.PDF', 'https://www.samr.gov.cn/xyjgs/flfg/art/2024/art_d4e84936a8a744f8928ac7aec7594345.html', 'https://static.cninfo.com.cn/finalpage/2026-11-03/1225652012.PDF']}
CURRENT_OUTPUT_SHA="ffe51d2c0511513e45a75786ff36da5774fd1ef27c4f9c2dcb28f5354c5c47ad"
HISTORY_NAMES=("2026-Q3.py","2026-Q3-output.json","previous-2026-Q3.md")
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        while b:=f.read(1048576):h.update(b)
    return h.hexdigest()
def exact(a,b):
    assert type(a)is type(b)
    if isinstance(a,dict):
        assert set(a)==set(b)
        for k in a:exact(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):exact(x,y)
    elif isinstance(a,float):assert math.isfinite(a)and math.isfinite(b)and struct.pack('!d',a)==struct.pack('!d',b)
    else:assert a==b

def regular(p,row):
    st=Path(p).lstat();assert stat.S_ISREG(st.st_mode)and not Path(p).is_symlink()and st.st_nlink==1
    assert(st.st_size,digest(p),stat.S_IMODE(st.st_mode))==(row['bytes'],row['sha256'],row['mode'])
def invoke(script,args,expected):
    run=subprocess.run([sys.executable,'-B',str(script),*map(str,args)],cwd=script.parent,capture_output=True,check=False)
    assert run.returncode==expected,run.stderr
    return run



def flat_contract(script, role):
    assert role in ('main', 'independent')
    ast.parse(script.read_bytes(), filename=str(script))
    regular(script, EXPECTED[BASE + script.name])
    assert len(EXPECTED)==21
    assert EXPECTED[BASE+'2026-Q3.py']==EXPECTED[BASE+'2026-Q3-independent-recompute.py']
    assert EXPECTED[BASE+'2026-Q3.py']['bytes']==1056
    assert EXPECTED[BASE+'2026-Q3.py']['sha256']=='4ffcec3f3ec40b1bb46eef6982613324f04a13848a6bff8fc962f4b031dc5ccd'
    assert EXPECTED[BASE+'2026-Q3-output.json']['bytes']==3531
    assert EXPECTED[BASE+'2026-Q3-output.json']['sha256']==CURRENT_OUTPUT_SHA

def assert_null_current(root,tmp):
    models=Path(root)/BASE
    raw=(models/'2026-Q3-output.json').read_bytes()
    assert len(raw)==3531 and hashlib.sha256(raw).hexdigest()==CURRENT_OUTPUT_SHA
    expected=json.loads(raw)
    # Full recursive type/value/key-set/list-order equality includes every Decimal
    # auxiliary string, 13-path declaration, structural Y4/J refusal and time anchor.
    exact(expected,CURRENT_OUTPUT)
    exact(json.loads((Path(root)/'tests/q3_final_helpers/002850/expected-result.json').read_bytes()),CURRENT_RESULT)
    assert expected['value_range'] is None and expected['return_model'] is None
    assert expected['valuation_note'].strip() and expected['return_model_note'].strip()
    for key in ('numeric_model_pass','primary_adoption','holder_adoption',
                'fallback_to_historical_own_aux_optimistic','new_financial_execution'):
        assert expected[key] is False
    assert expected['accepted_auxiliary']['whole_C_pairwise_pass'] is False
    assert expected['independent_cash_components']['complete_conditional_paths']==13
    assert expected['current_typed_refusal']['independent_sources']==1
    for name,role in [('2026-Q3.py','main'),('2026-Q3-independent-recompute.py','independent')]:
        flat_contract(models/name,role)
        isolated=tmp/name.replace('.py','');isolated.mkdir()
        copied=isolated/name;shutil.copyfile(models/name,copied);copied.chmod(0o644)
        shutil.copyfile(models/'2026-Q3-output.json',isolated/'2026-Q3-output.json')
        actual=invoke(copied,[],2)
        assert not actual.stderr
        assert actual.stdout==raw
        exact(json.loads(actual.stdout),expected)
        assert set(p.name for p in isolated.iterdir())=={name, '2026-Q3-output.json'}
    evidence=Path(root)
    # All current scientific evidence retains the original identity. Reports and
    # README layout guidance changed, and historical objects live in immutable Git.
    for rel,row in EXPECTED.items():
        if '/historical/' not in rel and not rel.endswith('.md'):
            regular(evidence/rel,row)
    # Exercise both original tiny roles, not a fabricated hard-SHA validator.
    # Invalid null metadata is a technical error, never an economic rejection.
    for name in ('2026-Q3.py','2026-Q3-independent-recompute.py'):
        original=evidence/(BASE+name);regular(original,EXPECTED[BASE+name])
        bad=tmp/('bad-metadata-'+name);bad.mkdir();shutil.copyfile(original,bad/name)
        invalid=dict(expected);invalid['value_range']={'low':0,'high':0,'currency':'CNY'}
        (bad/'2026-Q3-output.json').write_text(json.dumps(invalid,ensure_ascii=False))
        rejected=invoke(bad/name,[],1)
        assert not rejected.stdout
        exact(json.loads(rejected.stderr),{'status':'TECHNICAL_METADATA_ERROR','reason':''})
    return {'metadata_expected_exit':2,'model_numeric_pass':False,'historical_financial_executions':0}

def historical_root(root,tmp):
    from compact_null_history import restore_history
    target = restore_history(root, tmp, '002850')
    for path in target.iterdir():
        regular(path, EXPECTED[HIST + path.name])
    return target
