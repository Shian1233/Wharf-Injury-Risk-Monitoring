from pathlib import Path
import sys, hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import ROOT,RUNTIME,SCHEMAS
from app.db import db,uid,now
from app.storage import store
from app.ingest import parse_to_stage,commit_import
from app.sd import initialize_models

def bootstrap():
    db.initialize(); initialize_models()
    path=ROOT/'reference/data-standard.xlsx'
    if not path.exists(): print('No source workbook; empty database initialized'); return
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    existing=db.query('SELECT * FROM RISK_FILES WHERE SHA256=?',[digest])
    if existing and existing[0]['STATUS']=='imported' and '--refresh-source' not in sys.argv: print('Source workbook already imported');return
    id=existing[0]['ID'] if existing else uid()
    if not existing:
        key=digest[:2]+'/'+digest+'.xlsx'; size=store.put(key,path)
        db.execute('INSERT INTO RISK_FILES VALUES (?,?,?,?,?,?,?)',[id,'事故调查报告结构化表-字段已填写(1).xlsx',size,key,digest,'uploaded',now()])
    stage=parse_to_stage(path,path.name);stage.update(file_id=id,committed=False);db.put_doc('stage',stage['id'],stage)
    jobid=uid(); db.put_doc('job',jobid,{'id':jobid,'kind':'initial_import','status':'running','progress':0,'stage':'初始数据导入','created_at':now()})
    result=commit_import(jobid,stage['id'],'bootstrap');job=db.get_doc('job',jobid);job.update(status='completed',progress=100,stage='初始数据导入完成',result=result);db.put_doc('job',jobid,job)
    print(result)
    for s in SCHEMAS: print(s['sheet'],db.query(f'SELECT COUNT(*) AS N FROM {s["table"]}')[0]['N'])
if __name__=='__main__': bootstrap()
