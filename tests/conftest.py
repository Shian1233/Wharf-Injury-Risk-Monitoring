import os,tempfile
from pathlib import Path
os.environ['RISK_RUNTIME']=tempfile.mkdtemp(prefix='risk-agent-tests-')
os.environ['DB_BACKEND']='sqlite'
os.environ['STORAGE_BACKEND']='local'
os.environ['AUTH_MODE']='local'
os.environ['SESSION_SECRET']='test-secret-for-risk-tests-0123456789012345'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import db
from app.config import SCHEMAS

@pytest.fixture
def client():
    with TestClient(app) as c:
        for s in SCHEMAS: db.execute(f'DELETE FROM {s["table"]}')
        yield c

def accident(code='A1',**overrides):
    return {'编号':code,'省份':'广东省','地市':'东莞市','行业':'工贸行业','事故名称':code+'事故调查报告','发生时间':'2024-01-10 12:00','事故单位':'企业甲','事故等级':'一般','事故类型':'高处坠落','死亡人数':'1','受伤人数':'2','重伤人数':'报告未区分','轻伤人数':'报告未区分','失踪人数':'0','直接经济损失':'100万元','直接原因':'违规作业','管理原因':'✓','人员原因':'✓',**overrides}
