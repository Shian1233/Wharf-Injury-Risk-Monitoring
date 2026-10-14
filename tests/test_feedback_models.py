import copy
import math
import json
import pytest
from conftest import accident
from app.config import INDUSTRIES,RUNTIME
from app.sd_feedback import default_model,PROFILE_VERSION
from app.sd_factors import extract,FACTORS,summarize
from app.sd import validate,simulate,initialize_models,default_model as report_model_v2,preferred_model
from app.analytics import statistics
from app.ingest import validate_record
from app.db import db,uid
from app.reports import create_report

CLUES={'煤矿':'局部通风机停运，顶板支护不足，违规采掘。',
       '金属非金属矿山':'井下采空区冒顶，运输提升失效，排水不畅。',
       '石油天然气开采':'高压管线腐蚀泄漏，硫化氢暴露，井喷。',
       '化工':'反应釜超压，设备腐蚀穿孔，密封失效，动火时未安装报警。',
       '烟花爆竹':'超员超药量，混药中静电火花引燃，库存混存。',
       '工贸':'高处作业未系安全带，机械防护罩缺失，有限空间通风不足。'}

def sample(industry):
    row={'_industry':industry,'_id':'source-record','编号':'真实编号-1','直接原因':CLUES[industry]}
    row['_sd_features']=extract(row)
    return {'count':1,'cause_samples':1,'scope':{'industry':industry},'sd_evidence':summarize([row])}

@pytest.mark.parametrize('industry',INDUSTRIES)
@pytest.mark.parametrize('months',[1,3,6,12])
def test_six_industries_horizons_and_mechanism(industry,months):
    m=default_model(industry); assert validate(m)['valid']
    r=simulate(m,sample(industry),months)
    assert len(r['scenarios'])==3 and len(r['scenarios'][0]['points'])==months*20+1
    for s in r['scenarios']:
        assert s['points'][-1]['month']==months
        assert s['summary']['expected_accidents'] is None
        assert s['summary']['prediction_interval'] is None
        assert all(math.isfinite(v) and v>=0 for p in s['points'] for v in p.values())
        assert all(0<=p['risk_index']<=100 for p in s['points'])
        assert s['summary']['peak']==max(p['risk_index'] for p in s['points'])
        for name in r['stock_names']:
            assert s['points'][0][name]==r['scenarios'][0]['points'][0][name]
    baseline,pressure,safety=r['scenarios']
    assert pressure['points'][0]['hazard_formation']>baseline['points'][0]['hazard_formation']
    assert pressure['summary']['final']>baseline['summary']['final']
    assert safety['summary']['final']>baseline['summary']['final']
    assert not r['qualification']['count_prediction']

@pytest.mark.parametrize('industry',INDUSTRIES)
def test_sensitivity_and_delay(industry):
    m=default_model(industry); s=sample(industry)
    base=simulate(m,s,12)['scenarios'][0]['points']
    stronger=simulate(m,s,12,{'safety_effort':1.5})['scenarios'][0]['points']
    assert stronger[0]['hazard_removal']>base[0]['hazard_removal']
    assert stronger[-1]['risk_index']<base[-1]['risk_index']
    slow=simulate(m,s,3,{'response_time':12})['scenarios'][0]['points']
    fast=simulate(m,s,3,{'response_time':1})['scenarios'][0]['points']
    assert slow[0]['feedback_signal']==fast[0]['feedback_signal']==0
    assert slow[1]['feedback_signal']<fast[1]['feedback_signal']
    assert slow[-1]['risk_index']>fast[-1]['risk_index']
    none=simulate(m,s,12,{'safety_effort':0})['scenarios'][0]['points']
    assert all(p['hazard_removal']==0 for p in none)
    assert none[-1]['hazard_pressure']>none[0]['hazard_pressure']
    # At a zero stock boundary, formation is nonnegative; the integrator preserves it.
    m['variables'][0]['initial']='0'
    zero=simulate(m,s,1)['scenarios'][0]['points']
    assert zero[0]['accident_intensity']==0 and zero[-1]['hazard_pressure']>0

def test_mapping_traceability_and_protection():
    for industry in INDUSTRIES:
        result=extract({'_industry':industry,'_id':'r1','编号':'A1','直接原因':CLUES[industry]})
        assert len(result['hits'])>=2
        for matches in result['hits'].values():
            assert matches[0]['record_id']=='r1' and matches[0]['number']=='A1'
            assert matches[0]['excerpt'] and matches[0]['reason']
    assert extract({'_industry':'化工','直接原因':'未发生超压，排除腐蚀，未涉及动火。','事故防范与整改':'防止反应釜超温'})['hits']=={}
    m=default_model('化工');m['parameters']['detection_reference'].pop('calibrate')
    low=simulate(m,sample('化工'),6,{'detection_reference':.2})['scenarios'][0]['summary']['final']
    high=simulate(m,sample('化工'),6,{'detection_reference':.9})['scenarios'][0]['summary']['final']
    assert high<low

def test_scope_exclusions_and_special_processes():
    m=default_model('金属非金属矿山')
    r=simulate(m,sample(m['industry']),3,{'mine_scope':3})
    assert all(p['stope_factor']==p['blast_factor']==p['transport_factor']==0 for s in r['scenarios'] for p in s['points'])
    r=simulate(default_model('工贸'),sample('工贸'),3)
    assert not next(c for c in r['sd_evidence']['channels'] if c['key']=='special')['enabled']
    enabled=simulate(default_model('工贸'),sample('工贸'),3,{'process_dust':1})
    assert next(c for c in enabled['sd_evidence']['channels'] if c['key']=='special')['enabled']
    assert enabled['scenarios'][0]['points'][0]['special_factor']>0
    model=default_model('金属非金属矿山');model['parameters']['stope_enabled'].pop('calibrate')
    excluded=simulate(model,sample(model['industry']),1,{'mine_scope':3})
    assert excluded['scenarios'][0]['points'][0]['stope_factor']==0

def test_stock_flow_mass_balance_and_accumulation():
    r=simulate(default_model('煤矿'),sample('煤矿'),12)
    for scenario in r['scenarios']:
        points=scenario['points']
        load=sum((b['month']-a['month'])*(a['accident_intensity']+b['accident_intensity'])/2 for a,b in zip(points,points[1:]))
        change=sum((b['month']-a['month'])*((a['hazard_formation']-a['hazard_removal'])+(b['hazard_formation']-b['hazard_removal']))/2 for a,b in zip(points,points[1:]))
        assert points[-1]['cumulative_load']==pytest.approx(load,abs=2e-4)
        assert points[-1]['hazard_pressure']-points[0]['hazard_pressure']==pytest.approx(change,abs=2e-4)
        assert all(b['cumulative_load']>=a['cumulative_load'] for a,b in zip(points,points[1:]))

def test_empty_industry_has_explicit_assumptions():
    r=simulate(default_model('石油天然气开采'),{'count':0,'cause_samples':0,'scope':{}},12)
    assert r['sd_evidence']['samples']==0
    assert any(c['status']=='assumption' for c in r['calibration'])
    assert r['qualification']['out_of_sample_validation'] is None

def test_unsafe_or_dimensionally_invalid_formulas_rejected():
    m=default_model('工贸')
    next(v for v in m['variables'] if v['name']=='hazard_formation')['formula']='production_pressure+response_time'
    with pytest.raises(ValueError,match='量纲'):validate(m)
    m=default_model('工贸');m['industry']='煤矿'
    with pytest.raises(ValueError,match='所属行业'):validate(m)
    m=default_model('工贸');next(v for v in m['variables'] if v['name']=='hazard_formation')['formula']='-formation_rate'
    with pytest.raises(ValueError,match='负'):simulate(m,sample('工贸'))
    m=default_model('工贸');next(v for v in m['variables'] if v['name']=='hazard_formation')['formula']='hazard_removal'
    next(v for v in m['variables'] if v['name']=='hazard_removal')['formula']='hazard_formation'
    with pytest.raises(ValueError,match='代数循环'):validate(m)

def test_model_save_restore_and_migration(client):
    for kind in ['model','model_version']:db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=?',[kind])
    old=report_model_v2('煤矿');custom=report_model_v2('工贸');custom['parameters']['prevention_rate']['value']=.3;custom['name']='教学自定义'
    for m in [old,custom]:db.put_doc('model',m['id'],m)
    initialize_models();assert db.get_doc('model_version',old['id']+':1')==old
    assert db.get_doc('model',custom['id'])==custom
    assert preferred_model('工贸')['parameters']['prevention_rate']['value']==.3
    upgraded=db.get_doc('model',old['id']); assert upgraded['profile_version']==PROFILE_VERSION
    before=db.list_docs('model');initialize_models();assert db.list_docs('model')==before
    changed=copy.deepcopy(upgraded);changed['variables'][0]['label']='教学隐患压力'
    flow=next(v for v in changed['variables'] if v['name']=='hazard_formation');flow['formula']='formation_rate*production_pressure'
    result=client.post('/api/models/validate',json=changed);assert result.status_code==200,result.text
    assert not any(e['source']=='factor_load' and e['target']=='hazard_formation' for e in result.json()['edges'])
    saved=client.put('/api/models/'+old['id'],json=changed);assert saved.status_code==200,saved.text
    assert client.put('/api/models/'+old['id'],json=changed).status_code==409
    restored={**old,'version':saved.json()['version']}
    assert client.put('/api/models/'+old['id'],json=restored).status_code==200
    snapshot=db.list_docs('model');initialize_models();assert db.list_docs('model')==snapshot
    assert db.get_doc('model_version',old['id']+':1')==old

@pytest.mark.parametrize('industry',INDUSTRIES)
def test_report_pipeline_and_exports(client,industry):
    row=accident('SD1',行业=industry,直接原因=CLUES[industry]);db.add_record('accidents',validate_record('accidents',row))
    m=default_model(industry);db.put_doc('model',m['id'],m)
    data={'industry':industry,'region':'','start':'2024-01-01','end':'2024-12-31','months':3,'model_id':m['id'],
          'scenario':'基准场景','parameters':{},'indicators':['事故总数','预测末期风险指数','预测事故起数'],
          'use_llm':False,'coverage_confirmed':True}
    job=uid();db.put_doc('job',job,{'id':job,'status':'running'})
    report=create_report(job,data,'test');assert not report['simulation_error']
    evidence=json.loads((RUNTIME/'reports'/f'{report["id"]}.json').read_text(encoding='utf-8'))
    assert evidence['forecast']['status']=='unavailable'
    assert evidence['indicators']['预测事故起数']['value'] is None
    html=(RUNTIME/'reports'/f'{report["id"]}.html').read_text(encoding='utf-8')
    assert '隐患形成' in html and FACTORS[industry][0]['label'] in html
    assert '缺少' in html and '累计相对' in html
    assert report['body_hanzi']>=3000
    response=client.post('/api/simulations',json={'model_id':m['id'],'filters':{'industry':industry},'months':1})
    assert response.status_code==200,response.text
    exported=client.get('/api/simulations/'+response.json()['id']+'/export')
    assert 'accident_intensity' in exported.text and 'hazard_formation' in exported.text
    trace=client.get(f'/api/models/{m["id"]}/factor-evidence').json()
    assert trace['rows'][0]['number']=='SD1'
