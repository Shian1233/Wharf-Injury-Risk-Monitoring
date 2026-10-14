import json
import pytest
from app.llm import complete,LLMError,report_prose


@pytest.mark.parametrize('choice',[
    {'finish_reason':'length','message':{'content':'{"paragraph_001":"尚未结束'}},
    {'finish_reason':'stop','message':{'content':None}},
])
def test_incomplete_completion_is_not_treated_as_report(monkeypatch,choice):
    monkeypatch.setenv('LLM_MODEL','test-model');monkeypatch.setenv('LLM_API_KEY','test-only')
    class Response:
        status_code=200
        def json(self):return {'choices':[choice]}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr('app.llm.httpx.Client',Client)
    with pytest.raises(LLMError):complete([{'role':'user','content':'生成报告'}])


@pytest.mark.parametrize('base,official',[
    ('https://api.deepseek.com',True),('http://localhost:9000/v1',False),
])
def test_report_prose_accepts_wrapped_object_and_scopes_provider_options(monkeypatch,base,official):
    monkeypatch.setenv('LLM_BASE_URL',base);monkeypatch.setenv('LLM_MODEL','deepseek-flash')
    text='建议依据已记录的事故原因开展现场复核，明确作业风险和管理责任，落实设备检查与人员培训，现有资料仅反映已收集的调查样本，不能替代完整的区域监测。'*4
    paragraphs={f'paragraph_{i:03}':text for i in range(1,29)}
    captured=[]
    def completion(*args,**options):
        captured.append(options)
        return {'content':'```json\n'+json.dumps(paragraphs,ensure_ascii=False)+'\n```'}
    monkeypatch.setattr('app.llm.complete',completion)
    stats={'scope':{'industry':'工贸'},'factor_counts':{},'network':[]}
    result,meta=report_prose(stats,{},None,{'status':'unavailable','reason':'缺少连续样本'})
    assert result==paragraphs and meta['status']=='generated'
    assert captured[0]['response_format']=={'type':'json_object'}
    assert ('thinking' in captured[0])==official
    if official:
        assert captured[0]['thinking']=={'type':'disabled'} and captured[0]['max_tokens']==16000


def test_valid_json_with_missing_paragraphs_is_rejected(monkeypatch):
    monkeypatch.setattr('app.llm.complete',lambda *args,**kwargs:{'content':'{"paragraph_001":"缺少其余段落"}'})
    stats={'scope':{},'factor_counts':{},'network':[]}
    with pytest.raises(LLMError,match='段落数量不完整'):report_prose(stats,{},None,{'status':'unavailable'})
