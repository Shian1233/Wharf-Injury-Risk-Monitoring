import io,json,math,time,hashlib
from pathlib import Path
import pytest
from conftest import accident
from app.config import SCHEMAS,SCHEMA,INDICATORS,ROOT,RUNTIME
from app.db import db,uid,now
from app.ingest import validate_record,num,money,normalized_date,parse_to_stage,excel_rows
from app.analytics import statistics,foundation,indicators,forecast_counts,wilson
from app.sd import Formula,default_model,validate,simulate,import_vensim
from app.reports import fallback_prose,render_html,add_quantitative_text

def wait(client,id):
    for _ in range(200):
        job=client.get('/api/jobs/'+id).json()
        if job['status'] in ['completed','failed']: return job
        time.sleep(.025)
    raise AssertionError('job timed out')

def test_original_schema_and_source():
    assert [len(s['fields']) for s in SCHEMAS]==[33,79,70,72]
    assert [s['sheet'] for s in SCHEMAS]==['事故报告','企业数据','气候环境数据','经济社会数据']
    assert len(INDICATORS)==6 and all(len(g['items'])>=11 for g in INDICATORS)
    records=list(excel_rows(ROOT/'reference/data-standard.xlsx'))
    assert len(records)==165
    for ds,line,row in records: validate_record(ds,row)

def test_report_expert_review_is_saved_with_report(client):
    report_id=uid();db.put_doc('report',report_id,{'id':report_id,'title':'测试报告','created_at':now(),'body_hanzi':3200,'count':1,'status':'已生成'})
    saved=client.patch('/api/reports/'+report_id+'/review',json={'conclusion':'风险趋势判断需结合现场复核。','indicator_validation':'综合风险指数方向合理，建议补充暴露量。'})
    assert saved.status_code==200
    review=saved.json();assert review['conclusion'].startswith('风险趋势') and review['updated_by']=='local-admin'
    current=next(r for r in client.get('/api/reports').json() if r['id']==report_id)
    assert current['expert_review']['indicator_validation'].startswith('综合风险指数')
    assert client.patch('/api/reports/'+report_id+'/review',json={'conclusion':'','indicator_validation':''}).status_code==422

def test_missing_units_dates():
    assert num('报告未区分') is None
    assert money('1亿元')==10000 and money('10000元')==1 and money('100万元')==100
    assert normalized_date('2024年2月29日 14:30')=='2024-02-29'
    assert normalized_date('2023-02-29')==''
    with pytest.raises(ValueError): validate_record('accidents',accident(死亡人数='-1'))
    with pytest.raises(ValueError): validate_record('accidents',accident(无关字段='测试'))

def test_crud_permissions_conflict_and_escape(client,monkeypatch):
    assert client.get('/api/config').status_code==200
    a=client.post('/api/data/accidents',json=accident()).json()['id']
    assert client.post('/api/data/accidents',json=accident()).status_code==409
    page=client.get('/api/data/accidents').json();assert page['total']==1
    data=accident(事故名称='<script>alert(1)</script>事故调查报告')
    assert client.put('/api/data/accidents/'+a,json={'version':1,'data':data}).status_code==200
    assert client.put('/api/data/accidents/'+a,json={'version':1,'data':data}).status_code==409
    assert client.get('/api/data/accidents?industry=工贸').json()['total']==1
    assert client.get('/api/data/accidents?q=%27%20OR%201=1--').json()['total']==0
    assert client.get('/api/data/no-such-dataset').status_code==404
    assert client.post('/api/data/accidents',json=accident('A2'),headers={'Origin':'https://evil.example'}).status_code==403
    monkeypatch.setenv('AUTH_MODE','token');monkeypatch.setenv('ROLE_TOKENS',json.dumps({'viewer':'viewer-token','editor':'editor-token','admin':'admin-token'}))
    assert client.get('/api/config').status_code==401
    assert client.get('/api/config',headers={'Authorization':'Bearer viewer-token'}).status_code==200
    assert client.post('/api/data/accidents',json=accident('A2'),headers={'Authorization':'Bearer viewer-token'}).status_code==403
    assert client.delete('/api/data/accidents/'+a,headers={'Authorization':'Bearer editor-token'}).status_code==403
    assert client.post('/api/auth/session',json={'token':'viewer-token'}).status_code==200
    assert client.get('/api/config').status_code==200

def test_upload_import_preview_and_delete(client):
    csv='编号,行业,省份,事故名称,发生时间,死亡人数,直接原因,管理原因\nT1,工贸,广东省,测试事故,2024-02-01,1,培训不足,✓\nT2,工贸,广东省,另一事故,2024-02-02,-1,培训不足,✓\n'
    r=client.post('/api/uploads',files={'file':('data.csv',csv.encode('utf-8-sig'),'text/csv')},data={'dataset':'accidents'}).json()
    job=wait(client,r['job']['id']);assert job['status']=='completed';stage=job['result'];assert stage['valid']==1 and stage['rejected']==1
    assert stage['previews']['accidents'][0]['编号']=='T1'
    j=client.post('/api/imports/'+stage['id']+'/commit').json();done=wait(client,j['id']);assert done['status']=='completed' and done['result']['imported']==1
    assert client.post('/api/imports/'+stage['id']+'/commit').status_code==409
    assert client.get('/api/imports/'+stage['id']+'/errors').status_code==200
    duplicate=client.post('/api/uploads',files={'file':('data.csv',csv.encode('utf-8-sig'),'text/csv')},data={'dataset':'accidents'}).json();assert duplicate['duplicate']
    verified=client.post('/api/storage/verify').json();assert verified['all_verified']
    assert client.post('/api/uploads',files={'file':('malware.exe',b'MZ')}).status_code==422
    assert client.delete('/api/files/'+r['file_id']).status_code==200
    assert client.get('/api/data/accidents').json()['total']==0

def test_statistics_deduplication_missingness_and_association(client):
    for a in [accident('A1'),accident('A2',事故名称='A1事故调查报告及处理结果公布'),accident('A3',死亡人数='报告未明确',受伤人数='报告未明确',人员原因=None,发生时间='报告未明确')]: db.add_record('accidents',validate_record('accidents',a))
    s=statistics({});assert s['record_count']==3 and s['count']==2 and s['duplicate_reports']==1
    assert s['known']['死亡人数']==1 and s['totals']['死亡人数']==1
    assert s['dated_count']==1 and s['undated']==1
    metrics=indicators(s,foundation({}));assert metrics['伤亡总人数']['value'] is None
    assert metrics['平均每起死亡人数']['value']==1
    assert metrics['隐患整改率']['value'] is None
    assert s['network']['links'][0]['count']==1
    scope=statistics({'start':'2024-01-01','end':'2024-12-31'});assert scope['count']==1 and scope['undated_excluded']==1
    assert forecast_counts(s,3)['status']=='unavailable'

@pytest.mark.parametrize('formula',["__import__('os')","(1).__class__","[1,2]","open('secret')","2**100","1/0"])
def test_formula_sandbox(formula):
    with pytest.raises(ValueError): Formula(formula,set())({})

def test_rk4_matches_analytic_solution_and_rejects_cycles(client):
    m={'id':uid(),'name':'解析解验证','industry':'煤矿','version':1,'status':'测试模型','parameters':{'initial':{'value':10,'min':0,'max':100},'decay':{'value':.2,'min':0,'max':1}},'variables':[{'name':'risk_index','label':'风险','type':'stock','initial':'initial','rate':'-decay*risk_index'}]}
    s={'count':2,'cause_samples':2,'factor_counts':{},'scope':{}}
    result=simulate(m,s,12); actual=result['scenarios'][0]['points'][-1]['risk_index']
    assert abs(actual-10*math.exp(-.2*12))<1e-5
    points=result['scenarios'][0]['points']
    assert result['sampling_interval_months']==.05 and len(points)==241
    assert points[0]['month']==0 and points[-1]['month']==12
    assert all(abs(p['risk_index']-10*math.exp(-.2*p['month']))<1e-5 for p in points)
    assert all(b['month']-a['month']==pytest.approx(.05) for a,b in zip(points,points[1:]))
    m['variables'] += [{'name':'a','type':'aux','formula':'b'},{'name':'b','type':'aux','formula':'a'}]
    with pytest.raises(ValueError,match='循环'):validate(m)
    with pytest.raises(ValueError,match='没有事故原因'): simulate(default_model('煤矿'),{'count':0,'cause_samples':0},3)

def test_model_versions_and_scenarios(client):
    db.add_record('accidents',validate_record('accidents',accident()))
    m=next(x for x in client.get('/api/models').json() if x['industry']=='工贸')
    assert client.post('/api/models/validate',json=m).json()['valid']
    m['parameters']['prevention_rate']['value']=.08
    saved=client.put('/api/models/'+m['id'],json=m).json();assert saved['version']==m['version']+1
    assert client.put('/api/models/'+m['id'],json=m).status_code==409
    r=client.post('/api/simulations',json={'model_id':m['id'],'filters':{'industry':'工贸'},'months':3}).json()
    assert r['scenarios'][1]['points'][-1]['risk_index']>r['scenarios'][0]['points'][-1]['risk_index']
    assert r['scenarios'][2]['points'][-1]['risk_index']>r['scenarios'][0]['points'][-1]['risk_index']
    assert next(p['value'] for p in r['calibration'] if p['parameter']=='height_reference')==1
    exported=client.get('/api/simulations/'+r['id']+'/export')
    assert exported.status_code==200
    assert len(exported.text.splitlines())==1+3*61

def test_vensim_supported_subset():
    m=import_vensim('initial=10~~|decay=0.2~~|risk_index=INTEG(-decay*risk_index,initial)~~|','煤矿','进口模型')
    assert validate(m)['valid']
    with pytest.raises(ValueError):import_vensim('risk_index=DELAY FIXED(x,1,0)~~|','煤矿','不支持')

def test_forecast_temporal_validation_and_interval_semantics():
    monthly={f'{2020+i//12}-{i%12+1:02}':3+(i%3) for i in range(48)}
    stats={'monthly':monthly,'scope':{'start':'2020-01-01','end':'2023-12-31'},'dated_count':sum(monthly.values())}
    r=forecast_counts(stats,3,True);assert r['status']=='available' and len(r['points'])==3
    assert r['points'][0]['month']=='2024-01'
    assert r['validation']['holdout_months']==12 and r['validation']['interval_level']==90
    assert r['validation']['accepted'] is False
    assert all(p['upper90']>=p['lower90']>=0 for p in r['points'])
    assert wilson(8,10)[0]<80<wilson(8,10)[1]

def test_report_a4_body_sources_and_expert_honesty(client):
    db.add_record('accidents',validate_record('accidents',accident()))
    model=next(m for m in db.list_docs('model') if m['industry']=='工贸')
    body={'industry':'工贸','region':'广东省','start':'2024-01-01','end':'2024-12-31','months':3,'model_id':model['id'],'indicators':[x for g in INDICATORS for x in g['items']],'use_llm':False}
    response=client.post('/api/reports',json=body);assert response.status_code==200,response.text
    job=wait(client,response.json()['id']);assert job['status']=='completed',job
    report=job['result'];assert report['body_hanzi']>=3000 and report['status']=='规则文本草稿'
    from bs4 import BeautifulSoup
    text=client.get('/api/reports/'+report['id']+'/html').text;soup=BeautifulSoup(text,'html.parser')
    assert len(soup.select('h2[data-section-number]'))==7
    assert '【' not in soup.get_text() and {s.get('id') for s in soup.select('script')} == {'report-echarts-library','report-echarts-init'}
    assert len(soup.select('[data-echart] svg')) == 5
    assert soup.select_one('.report-watermark')
    assert len(soup.select('[data-chart] svg'))==3
    assert '广东省工贸' in soup.select_one('.cover-section h1').get_text()
    assert soup.select_one('.cover-meta').get_text().count('数据不足')==0
    actual_body=''.join(e.get_text() for e in soup.select('.report-body p[data-field]'))
    import re
    assert len(re.findall(r'[\u4e00-\u9fff]',actual_body))>=3000
    evidence=client.get('/api/reports/'+report['id']+'/evidence').json();assert evidence['statistics']['count']==1
    a=client.get('/api/acceptance').json();assert not a['records']['met'] and not a['storage']['met'] and a['expert'] is None
    assert client.post('/api/acceptance/expert',json={'reviewer':'审核专家','cases':[{'case_id':'C1','recommendations_match':True,'content_match':True,'evidence':'审核记录'}]}).status_code==200

def test_csv_formula_injection_safe(client):
    a=accident(事故名称='=HYPERLINK("evil")');db.add_record('accidents',validate_record('accidents',a))
    exported=client.get('/api/data/accidents/export').text;assert "'=HYPERLINK" in exported

def test_no_key_in_public_configuration(client):
    value=client.get('/api/config').text
    import os
    key=os.getenv('LLM_API_KEY');assert not key or key not in value

def test_password_login_uses_hash_and_session_cookie(client,monkeypatch):
    from app.auth import hash_password,verify_password
    encoded=hash_password('correct-horse-battery-staple')
    assert 'correct-horse' not in encoded
    monkeypatch.setenv('AUTH_MODE','password');monkeypatch.setenv('APP_PASSWORD_HASH',encoded)
    assert verify_password('correct-horse-battery-staple') and not verify_password('incorrect-password')
    assert client.get('/api/config').status_code==401
    assert client.post('/api/auth/session',json={'password':'incorrect-password'}).status_code==401
    session=client.post('/api/auth/session',json={'password':'correct-horse-battery-staple'})
    assert session.status_code==200 and session.json()['role']=='admin'
    assert 'HttpOnly' in session.headers['set-cookie'] and 'SameSite=strict' in session.headers['set-cookie']
    config=client.get('/api/config')
    assert config.status_code==200 and config.json()['auth_mode']=='password'

def test_platform_identity_and_expiry(client,monkeypatch):
    import hmac,base64
    from app.auth import encode
    monkeypatch.setenv('AUTH_MODE','platform')
    secret='platform-test-secret-01234567890123456789'
    monkeypatch.setenv('PLATFORM_JWT_SECRET',secret)
    monkeypatch.setenv('JWT_ISSUER','cumt-platform')
    monkeypatch.setenv('JWT_AUDIENCE','risk-agent')
    def jwt(**extra):
        head=encode(b'{"alg":"HS256","typ":"JWT"}')
        body=encode(json.dumps({'sub':'user-123','role':'viewer','iss':'cumt-platform','aud':'risk-agent','exp':time.time()+60,**extra}).encode())
        return head+'.'+body+'.'+encode(hmac.new(secret.encode(),(head+'.'+body).encode(),hashlib.sha256).digest())
    assert client.get('/api/config').status_code==401
    assert client.get('/api/config',headers={'Authorization':'Bearer '+jwt()}).json()['role']=='viewer'
    assert client.post('/api/data/accidents',json=accident(),headers={'Authorization':'Bearer '+jwt()}).status_code==403
    for token in [jwt(exp=time.time()-1),jwt(iss='other'),jwt(aud='other'),jwt(role='root'),jwt(nbf=time.time()+500),jwt()+'tamper']:
        assert client.get('/api/config',headers={'Authorization':'Bearer '+token}).status_code==401
    assert client.post('/api/auth/session',json={'token':jwt()}).status_code==200
    assert client.get('/api/config').status_code==200

def test_frontend_versions_and_cache_headers(client,monkeypatch,tmp_path):
    import re,shutil
    from app import main
    html=client.get('/agent')
    assert html.headers['cache-control']=='no-store'
    assert 'id="startup-state"' in html.text and 'id="startup-retry"' in html.text
    urls=re.findall(r'(?:href|src)="(/assets/[^"?]+\?v=[a-f0-9]{16})"',html.text)
    assert len(urls)==5
    for url in urls:
        asset=client.get(url)
        assert asset.status_code==200 and asset.headers['cache-control']=='no-cache'
        assert url.split('?v=')[1]==hashlib.sha256(asset.content).hexdigest()[:16]
    source=tmp_path/'frontend'
    (source/'vendor').mkdir(parents=True)
    for name in ['index.html','app.js','sd-workbench.js','style.css','design.css','vendor/tokens.css','vendor/echarts.min.js']:
        shutil.copyfile(ROOT/'frontend'/name,source/name)
    monkeypatch.setattr(main,'ROOT',tmp_path)
    before=re.search(r'src="(/assets/app.js\?v=[a-f0-9]{16})"',client.get('/agent').text)[1]
    with (source/'app.js').open('a',encoding='utf-8') as file: file.write('\n// new release\n')
    after=re.search(r'src="(/assets/app.js\?v=[a-f0-9]{16})"',client.get('/agent').text)[1]
    assert before!=after

def test_subpath_auth_assets_and_links(client,monkeypatch):
    from app.main import app
    monkeypatch.setattr(app,'root_path','/risk-agent')
    monkeypatch.setenv('PUBLIC_BASE_PATH','/risk-agent')
    monkeypatch.setenv('AUTH_MODE','token')
    monkeypatch.setenv('ROLE_TOKENS','{"viewer":"subpath-test"}')
    assert client.get('/risk-agent/api/config').status_code==401
    assert client.get('/risk-agent/api/config',headers={'Authorization':'Bearer subpath-test'}).status_code==200
    html=client.get('/risk-agent/agent').text
    assert 'content="/risk-agent"' in html and 'src="/risk-agent/assets/app.js?v=' in html
    assert client.get('/risk-agent/assets/style.css').status_code==200
    session=client.post('/risk-agent/api/auth/session',json={'token':'subpath-test'})
    assert session.status_code==200 and 'Path=/risk-agent' in session.headers['set-cookie']
    assert client.get('/risk-agent/api/config').status_code==200

def test_all_datasets_search_and_invalid_file_signature(client):
    for s in SCHEMAS:
        response=client.get('/api/data/'+s['id'],params={'q':'测试','region':'广东','start':'2024-01-01','end':'2024-12-31'})
        assert response.status_code==200,response.text
    response=client.post('/api/uploads',files={'file':('fake.pdf',b'not a real pdf','application/pdf')})
    assert response.status_code==422

def test_report_numeric_text_and_selected_scenario(client,monkeypatch):
    from app.llm import report_prose,LLMError
    db.add_record('accidents',validate_record('accidents',accident()))
    stats=statistics({'industry':'工贸'});base=foundation({});sim=simulate(default_model('工贸'),stats,3)
    baseline=indicators(stats,base,sim);pressure=indicators(stats,base,sim,selected_scenario='生产压力增大')
    assert pressure['预测末期风险指数']['value']>baseline['预测末期风险指数']['value']
    assert pressure['生产压力场景变化率']['value']==baseline['生产压力场景变化率']['value']
    qualitative='建议基于已记录的事故原因开展复核，加强作业风险识别与治理措施落实，事故样本不能直接代表区域总体风险。'*6
    clean={f'paragraph_{i:03}':qualitative for i in range(1,29)}
    calls=[]
    def completion(*args,**kwargs):
        calls.append(1)
        return {'content':json.dumps({**clean,'paragraph_001':'死亡人数为999人'} if len(calls)==1 else clean,ensure_ascii=False)}
    monkeypatch.setattr('app.llm.complete',completion)
    prose,meta=report_prose(stats,baseline,sim,{'status':'unavailable','reason':'采集完整性未确认'})
    assert len(calls)==2 and meta['attempts']==2 and '999' not in prose['paragraph_001']
    params={'industry':'工贸','region':'广东省','start':'2024-01-01','end':'2024-12-31','scenario':'生产压力增大','indicators':['死亡人数','预测末期风险指数']}
    final=add_quantitative_text(prose,params,stats,pressure,sim,{'status':'unavailable','reason':'采集完整性未确认'})
    assert '死亡人数为1.0人' in final['paragraph_011'] and '生产压力增大' in final['paragraph_018']

def test_ten_record_pagination(client):
    for i in range(12):
        db.add_record('accidents',validate_record('accidents',accident(f'PAGE{i:02}')))
    first=client.get('/api/data/accidents').json()
    second=client.get('/api/data/accidents?offset=10').json()
    assert first['total']==second['total']==12
    assert len(first['items'])==10 and len(second['items'])==2
    assert {r['编号'] for r in first['items']}.isdisjoint({r['编号'] for r in second['items']})
    assert len(client.get('/api/data/accidents?limit=3').json()['items'])==3

def test_application_model_catalog_and_request_validation(client,monkeypatch):
    from app.llm import resolve_model
    monkeypatch.setenv('LLM_MODEL','default-model')
    monkeypatch.setenv('LLM_MODELS','second-model,default-model,second-model,invalid model')
    config=client.get('/api/config').json()
    assert [m['id'] for m in config['llm']['models']]==['default-model','second-model']
    assert resolve_model()=='default-model'
    assert resolve_model('second-model')=='second-model'
    with pytest.raises(ValueError):resolve_model('unlisted-model')
    body={'industry':'工贸','start':'2024-01-01','end':'2024-12-31','indicators':['事故总数'],'llm_model':'unlisted-model'}
    assert client.post('/api/reports',json=body).status_code==422
    assert client.post('/api/chat',json={'content':'查询风险','llm_model':'unlisted-model'}).status_code==422

def test_model_specific_completion_payload(monkeypatch):
    from app.llm import complete,resolve_model
    monkeypatch.setenv('LLM_MODEL','default-model');monkeypatch.setenv('LLM_MODELS','second-model')
    monkeypatch.setenv('LLM_API_KEY','test-only-key')
    captured=[]
    class Response:
        status_code=200
        def json(self):return {'choices':[{'message':{'content':'成功'}}]}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):captured.append(json);return Response()
    monkeypatch.setattr('app.llm.httpx.Client',Client)
    complete([{'role':'user','content':'查询'}],model='second-model')
    complete([{'role':'user','content':'查询'}])
    assert [p['model'] for p in captured]==['second-model','default-model']
    assert resolve_model()=='default-model'

def test_report_and_chat_forward_application_model(client,monkeypatch):
    monkeypatch.setenv('LLM_MODEL','default-model');monkeypatch.setenv('LLM_MODELS','second-model')
    received=[]
    def ask_mock(content,filters,session_id,actor,model):
        received.append(model)
        return {'answer':'测试回答','sessionId':'isolated-test-session'}
    monkeypatch.setattr('app.main.ask',ask_mock)
    assert client.post('/api/chat',json={'content':'查询风险','llm_model':'second-model'}).json()['answer']=='测试回答'
    db.add_record('accidents',validate_record('accidents',accident()))
    def prose_mock(stats,metrics,simulation,forecast,model=''):
        received.append(model)
        return fallback_prose(stats,foundation({}),metrics,simulation,forecast),{'status':'generated','model':model}
    monkeypatch.setattr('app.reports.report_prose',prose_mock)
    body={'industry':'工贸','start':'2024-01-01','end':'2024-12-31','indicators':['事故总数'],'llm_model':'second-model','use_llm':True}
    result=client.post('/api/reports',json=body)
    assert result.status_code==200,result.text
    job=wait(client,result.json()['id'])
    assert job['status']=='completed',job
    assert job['result']['parameters']['llm_model']=='second-model'
    assert job['result']['llm']['model']=='second-model'
    assert received==['second-model','second-model']

