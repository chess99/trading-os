"""Huaming current-null contract, distinct from retained historical finance.
Static preparation is not runtime or financial qualification.
"""
import ast,hashlib,json,math,shutil,stat,struct,subprocess,sys
from pathlib import Path
CODE="002270"
BASE='research/companies/CN/002270/models/'
HIST='research/companies/CN/002270/models/2026-Q3-evidence/historical/'
EXPECTED={'research/companies/CN/002270/models/2026-Q3-evidence/ADOPTION-STATUS.json': {'bytes': 10281, 'sha256': 'b12b7b09db01512ecd8e42329bdbf7d22932a67c6a424cee2e3b33f244817896', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/CURRENT-CONSUMERS.json': {'bytes': 22031, 'sha256': '284a6278962fcc03da98038d08b3069882a2d105b81c2ac3193f95f19e35f0f0', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/EVENT-FACTS.json': {'bytes': 786, 'sha256': 'bbbc699455c8893a74f57caa884182c8e5700e127329d74f5986bddb76ec647a', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/HISTORICAL-SOURCE-IDENTITIES.json': {'bytes': 923, 'sha256': 'bb4f5a5d5678925767d3765c79ed563a5adb8d8026fbd43ab267e5a88fa1a72d', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/2026-Q3-independent-recompute.py': {'bytes': 3999, 'sha256': 'b2126070970e49649cb646c81f5ca5e1b1e331091c925202a94c378aec37239c', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/2026-Q3.py': {'bytes': 30488, 'sha256': 'fa849a3170ad67e0eeafe0ed79fdd4ef57bc780e0dd5fe848ed8aa6ef08c41d3', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/README.md': {'bytes': 328, 'sha256': '1def26614f392d88d1b9160e1c3f47fbc49d5451ce6220b21af1f0146979194b', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-independent-recompute.py': {'bytes': 898, 'sha256': 'a02270867a986afedf0fb303edb98bc216e03bcedd0d7e8f51b87adb845198e9', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-output.json': {'bytes': 1971, 'sha256': '6913e1e81e043f06088076c59603faff22cd2f60af0bef14f4e96ed0742a2b91', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-sources-assumptions.md': {'bytes': 5610, 'sha256': '385e12d3d11ef4b13bab6cb2f43b76eb7b25d61532d40dc5a4f50bf90b98e9af', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3.py': {'bytes': 898, 'sha256': 'a02270867a986afedf0fb303edb98bc216e03bcedd0d7e8f51b87adb845198e9', 'mode': 420}, 'research/companies/CN/002270/reports/2026-Q3.md': {'bytes': 26102, 'sha256': 'e54d09bc7eebde93c34ce02cd386d4c75f67bdab9e04a0788e939c3e52d470fc', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/2026-Q3-output.json': {'bytes': 11032105, 'sha256': 'd50997fe77dddc81df56ee0a18c203f5728e3105641b5faf285217e6990fb921', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/previous-2026-Q3.md': {'bytes': 26905, 'sha256': '1ba89b10516f5082ebde07b068bae9a535c247d998c50ba7a51d242d9cfca70b', 'mode': 420}, 'research/companies/CN/002270/models/2026-Q3-evidence/historical/previous-2026-Q3-sources-assumptions.md': {'bytes': 15002, 'sha256': '967832ca859c08e76d8b7cf05853e5338f897443830b45505dd656a57efb8774', 'mode': 420}}
CURRENT_OUTPUT={'schema': 'current-research-numeric-status-v1', 'symbol': 'CN:002270', 'report_period': '2026-Q3', 'information_cutoff': '2026-11-03T00:00:00Z', 'operating_and_original_pv_anchor': '2026-10-26T11:31:00Z', 'status': 'UNPRICED_PENDING_ECONOMIC_ADOPTION_STOPPED', 'value_range': None, 'return_model': None, 'valuation_note': '暂不提交核心合理价值区间。已有固定经营输入下事件前后各一条600年精确现金路径满足生产严格约束，但核心端点、支配性假设变化及长期经济解释的独立采用尚未闭合，本次停止补证。不是已证最新精确现金经济不可行。核心方法为普通股实际可得现金折现，原经营及PV锚为2026-10-26、资本信息更新至2026-11-03固定批次；辅助成熟盈利与有限升级法约7.62—9.92元仅是原保存条件参考，非当前核心或清算底。', 'return_model_note': '当前完整基准普通股分配及第五年末权益消费资格尚未闭合，暂不提供五项年度分配或第五年终值，也不计算IRR。旧五D/Y5、保存的精确账和辅助参考均不能补位。已付10月股息退出未来现金；896,225,431股注册基数、库存享权、激励再授和未来资本动作须同步；终值应来自同基准第五年分配后完整状态及全部以后现金，不重复本金。留空是待证停止，不是企业价值或未来分配为零。', 'numeric_model_usable': False, 'economic_adoption': False, 'current_independent_numeric_pass': False, 'latest_exact_cash_strict_production_success': True, 'latest_exact_cash_typed_economic_failure_observed': False, 'fallback_allowed': False, 'historical_numeric_values_currently_adopted': False, 'auxiliary_role': 'CONDITIONAL_SAVED_REFERENCE_ONLY_NOT_CORE_OR_HOLDER', 'notes': 'No numeric valuation, distribution, Y5 or IRR is exported. Null is pending economic adoption, not zero company value or inferred exact-cash infeasibility.'}
CURRENT_RESULT={'symbol': 'CN:002270', 'name': '华明装备', 'outcome': 'covered', 'report_period': '2026-Q3', 'information_cutoff': '2026-11-03T00:00:00+00:00', 'summary': '可靠性验证、制造工艺与服务支持长期拥有，海外需求已兑现，但竞争恢复、资本效率和母子分配约束普通股价值。精确现金计算已有严格通过的有限证据，核心端点及完整持有人路径的经济与独立采用尚未闭合，本次停止补证，价值区间和回报模型留空；未核现价，不评价价格吸引力。', 'key_logic': ['海外用户前三季收入7.09亿元、增长45.91%，国内终端近持平；采纳已有市场温和扩张，不能外推海外单项增速或把全球电网投资直接变成公司收入。', '制造、验证和服务能力支撑盈利，但MR扩产和交付恢复限制短缺溢价；原经营预算采用净率逐步回落并保留必要资本，不把历史ROE当成新增项目回报。', '新增回购成交20,953,119元提前占用现金或付款准备，最低总预算余款104,048,778元；库存股未注销，母现金位置与集团外付须守恒，旧应收到账不能再增母利润。', '主法仍是普通股可取得现金折现，辅助成熟盈利能力仅保留条件参考；精确现金严格通过不替代核心端点、支配性变化和完整分配及第五年权益的采用证据，当前两项数值接口均留空。'], 'risks': ['竞争者交付恢复、同型号降价或重大质量问题，使认证和制造优势不能维持单位利润；收入增长仍可能伴随低回报扩产。', '海外回款、库存、少数归属和税收优惠变化增加必要资金，上划延迟或关联资金配置使合并利润不能成为普通股现金。', '光伏和非核心投资长期占用核心设备现金，激励再授或未来低价融资改变普通股权利；现有完整经济采用缺口不应由旧估值或辅助数值替补。'], 'value_range': None, 'valuation_note': '暂不提交核心合理价值区间。已有固定经营输入下事件前后各一条600年精确现金路径满足生产严格约束，但核心端点、支配性假设变化及长期经济解释的独立采用尚未闭合，本次停止补证。不是已证最新精确现金经济不可行。核心方法为普通股实际可得现金折现，原经营及PV锚为2026-10-26、资本信息更新至2026-11-03固定批次；辅助成熟盈利与有限升级法约7.62—9.92元仅是原保存条件参考，非当前核心或清算底。', 'return_model': None, 'return_model_note': '当前完整基准普通股分配及第五年末权益消费资格尚未闭合，暂不提供五项年度分配或第五年终值，也不计算IRR。旧五D/Y5、保存的精确账和辅助参考均不能补位。已付10月股息退出未来现金；896,225,431股注册基数、库存享权、激励再授和未来资本动作须同步；终值应来自同基准第五年分配后完整状态及全部以后现金，不重复本金。留空是待证停止，不是企业价值或未来分配为零。', 'source_urls': ['https://static.cninfo.com.cn/finalpage/2026-10-27/1225622378.PDF', 'https://static.cninfo.com.cn/finalpage/2026-08-29/1225528484.PDF', 'https://static.cninfo.com.cn/finalpage/2026-02-27/1224986242.PDF', 'https://static.cninfo.com.cn/finalpage/2025-04-11/1223055875.PDF', 'https://www1.hkexnews.hk/app/sehk/2026/108266/documents/sehk26030600645_c.pdf', 'https://static.cninfo.com.cn/finalpage/2026-09-03/1225545297.PDF', 'https://onload.reinhausen.com/en/12-2025/future-factory-expansions-at-reinhausen-worldwide/', 'https://www.reinhausen.com/impulses/optimizing-the-service-life-of-equipment/retrofit-breathing-new-life-into-old-transformers-thanks-to-new-tap-changers', 'https://www.iea.org/reports/electricity-mid-year-update-2026/executive-summary', 'https://www.nea.gov.cn/20260902/6a6147bd0a244735af4c28e3e285af6f/c.html', 'https://static.cninfo.com.cn/finalpage/2022-06-01/1213571762.PDF', 'https://static.cninfo.com.cn/finalpage/2026-04-27/1225181771.PDF', 'https://www.samr.gov.cn/xyjgs/flfg/art/2024/art_d4e84936a8a744f8928ac7aec7594345.html', 'https://static.cninfo.com.cn/finalpage/2026-11-03/1225653764.PDF']}
CURRENT_OUTPUT_SHA="6913e1e81e043f06088076c59603faff22cd2f60af0bef14f4e96ed0742a2b91"
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
    assert len(EXPECTED)==15
    assert EXPECTED[BASE+'2026-Q3.py']==EXPECTED[BASE+'2026-Q3-independent-recompute.py']
    assert EXPECTED[BASE+'2026-Q3.py']['bytes']==898
    assert EXPECTED[BASE+'2026-Q3.py']['sha256']=='a02270867a986afedf0fb303edb98bc216e03bcedd0d7e8f51b87adb845198e9'
    assert EXPECTED[BASE+'2026-Q3-output.json']['bytes']==1971
    assert EXPECTED[BASE+'2026-Q3-output.json']['sha256']==CURRENT_OUTPUT_SHA

def assert_null_current(root,tmp):
    models=Path(root)/BASE
    raw=(models/'2026-Q3-output.json').read_bytes()
    assert len(raw)==1971 and hashlib.sha256(raw).hexdigest()==CURRENT_OUTPUT_SHA
    expected=json.loads(raw)
    exact(expected,CURRENT_OUTPUT)  # Every key, type, value, and time anchor is fixed.
    exact(json.loads((Path(root)/'tests/q3_final_helpers/002270/expected-result.json').read_bytes()),CURRENT_RESULT)
    assert expected['value_range'] is None and expected['return_model'] is None
    assert expected['valuation_note'].strip() and expected['return_model_note'].strip()
    for key in ('numeric_model_usable','economic_adoption','current_independent_numeric_pass',
                'latest_exact_cash_typed_economic_failure_observed','fallback_allowed',
                'historical_numeric_values_currently_adopted'):
        assert expected[key] is False
    assert expected['latest_exact_cash_strict_production_success'] is True
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
    # The original Huaming tiny rejects changed identity with ValueError and exit 1.
    # This is a technical invalid-metadata case, not an economic rejection.
    original=evidence/(BASE+'2026-Q3.py');regular(original,EXPECTED[BASE+'2026-Q3.py'])
    bad=tmp/'bad-metadata';bad.mkdir();shutil.copyfile(original,bad/'2026-Q3.py')
    invalid=dict(expected);invalid['value_range']={'low':0,'high':0,'currency':'CNY'}
    (bad/'2026-Q3-output.json').write_text(json.dumps(invalid,ensure_ascii=False))
    rejected=invoke(bad/'2026-Q3.py',[],1)
    assert not rejected.stdout
    assert rejected.stderr.decode('utf-8').splitlines()[-1]=='ValueError: current status identity mismatch'
    return {'metadata_expected_exit':2,'model_numeric_pass':False,'historical_financial_executions':0}

def historical_root(root,tmp):
    from compact_null_history import restore_history
    target = restore_history(root, tmp, '002270')
    for path in target.iterdir():
        regular(path, EXPECTED[HIST + path.name])
    return target
