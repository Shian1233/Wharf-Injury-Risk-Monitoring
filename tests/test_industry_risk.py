import copy
import math
import pytest
from conftest import accident
from app.industry_risk import PROFILES, extract_features, summarize_features, PROFILE_VERSION
from app.sd import default_model, legacy_model, validate, simulate, initialize_legacy_models as initialize_models
from app.analytics import statistics, high_risk_duration
from app.ingest import validate_record
from app.db import db


@pytest.mark.parametrize('industry,kind,expected',[
    ('煤矿','煤与瓦斯突出','gas'),('金属非金属矿山','坍塌','slope'),
    ('石油天然气开采','井喷','well'),('化工','反应釜超压爆炸','reaction'),
    ('烟花爆竹','装药过程中静电引燃','press'),('工贸','高处坠落','height')])
def test_profile_extract_calibrate_and_run(industry,kind,expected):
    row={'_industry':industry,'事故类型':kind,'_date':'2025-01-01','_id':'one','编号':'A1'}
    row['_risk_features']=extract_features(row)
    assert expected in row['_risk_features']
    stats={'count':1,'cause_samples':1,'factor_counts':{'管理':1},'scope':{'industry':industry},
        'industry_evidence':summarize_features([row],{}),'source_manifest_sha256':'test-evidence'}
    model=default_model(industry); assert validate(model)['valid']
    result=simulate(model,stats,12)
    found=next(c for c in result['calibration'] if c['parameter']==expected+'_initial')
    assert found['value']==100 and found['numerator']==found['denominator']==1
    assert result['industry_evidence']['trend_status']=='insufficient'
    assert all(c['trend'] is None for c in result['industry_evidence']['channels'])
    assert math.isclose(sum(c['weight'] for c in result['industry_evidence']['channels']),1)
    assert result['source_manifest_sha256']=='test-evidence'
    assert all(0<=p['risk_index']<=100 for s in result['scenarios'] for p in s['points'])
    assert result['scenarios'][2]['points'][-1]['risk_index']>result['scenarios'][0]['points'][-1]['risk_index']


def test_dictionary_avoids_prevention_text_and_local_negation():
    row={'_industry':'化工','事故类型':'其他伤害','事故名称':'测试事故',
         '直接原因':'未发生爆炸，排除泄漏，未发现超温。','事故防范与整改':'加强反应釜管理，预防中毒窒息'}
    assert extract_features(row)=={}
    row['直接原因']='未发生爆炸，但现场存在有毒气体并导致中毒。'
    assert set(extract_features(row))=={'toxic'}


def test_duration_uses_time_and_crossings_instead_of_sample_count():
    # Risk rises linearly from 40 to 80 in three months: 1.5 months above 60.
    coarse=[{'month':t,'risk_index':40+40*t/3} for t in [0,1,2,3]]
    irregular=[{'month':t,'risk_index':40+40*t/3} for t in [0,.05,.3,1.2,1.6,2.85,3]]
    dense=[{'month':i/20,'risk_index':40+40*(i/20)/3} for i in range(61)]
    for points in [coarse,irregular,dense]:
        assert high_risk_duration(points,60)==pytest.approx(1.5)
        assert high_risk_duration(points,40)==pytest.approx(3)
        assert high_risk_duration(points,80)==pytest.approx(0)
        falling=[{**p,'risk_index':120-p['risk_index']} for p in points]
        assert high_risk_duration(falling,60)==pytest.approx(1.5)
    assert high_risk_duration([{'month':0,'risk_index':60},{'month':3,'risk_index':60}],60)==3


def test_deduplication_preserves_features_once(client):
    first=accident('F1',事故名称='某企业高坠事故调查报告',直接原因='人员高处坠落')
    second=accident('F2',事故名称='某企业高坠事故处理通报',直接原因='同时发生物体打击')
    for row in [first,second]: db.add_record('accidents',validate_record('accidents',row))
    stats=statistics({'industry':'工贸'})
    assert stats['count']==1 and stats['record_count']==2
    profile=stats['industry_evidence']['工贸']
    assert profile['counts']['height']==1
    assert profile['samples']==1 and profile['matched_samples']==1
    assert profile['channels'][1]['evidence'][0]['record_id']


def test_trend_uses_fixed_half_year_windows_and_requires_samples():
    rows=[]
    for month in range(1,13):
        row={'_industry':'工贸','_date':f'2025-{month:02d}-10','事故类型':'高处坠落' if month<=6 else '机械伤害'}
        row['_risk_features']=extract_features(row);rows.append(row)
    p=summarize_features(rows,{'end':'2025-12-31'})['工贸']
    assert p['trend_status']=='available'
    assert next(c['trend'] for c in p['channels'] if c['key']=='height')==pytest.approx(-100/6)
    assert next(c['trend'] for c in p['channels'] if c['key']=='mechanical')==pytest.approx(100/6)
    # Explicit analysis end wins over the last reported incident (no silent stale trend).
    stale=summarize_features(rows,{'end':'2026-12-31'})['工贸']
    assert stale['trend_status']=='insufficient'


def test_no_industry_evidence_and_automatic_override_are_rejected():
    m=default_model('工贸')
    stats={'count':1,'cause_samples':1,'factor_counts':{},'scope':{'industry':'工贸'},'industry_evidence':{}}
    with pytest.raises(ValueError,match='缺少可识别'):simulate(m,stats)
    row={'_industry':'工贸','事故类型':'高处坠落','_date':'2025-01-01'};row['_risk_features']=extract_features(row)
    stats['industry_evidence']=summarize_features([row],{})
    with pytest.raises(ValueError,match='不能手动覆盖'):simulate(m,stats,overrides={'height_initial':99})
    with pytest.raises(ValueError,match='参数越界'):simulate(m,stats,overrides={'production_pressure':10})


def test_different_industries_and_validation():
    models=[default_model(i) for i in PROFILES]
    assert len({tuple(v['label'] for v in m['variables']) for m in models})==6
    m=models[0];m['industry']='化工'
    with pytest.raises(ValueError,match='所属行业不匹配'):validate(m)


def test_builtin_upgrade_is_versioned_idempotent_and_keeps_custom(client):
    for kind in ['model','model_version']:db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=?',[kind])
    original=legacy_model('煤矿'); custom=legacy_model('工贸');custom['name']='教学模型';custom['parameters']['prevention_rate']['value']=.2
    for m in [original,custom]:db.put_doc('model',m['id'],m)
    initialize_models()
    upgraded=db.get_doc('model',original['id'])
    assert upgraded['version']==2 and upgraded['profile_version']==PROFILE_VERSION
    assert db.get_doc('model_version',original['id']+':1')==original
    assert db.get_doc('model',custom['id'])==custom
    snapshot=db.list_docs('model');assert len(snapshot)==7
    initialize_models();assert db.list_docs('model')==snapshot
