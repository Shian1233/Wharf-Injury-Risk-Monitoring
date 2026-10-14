from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
import os, re, json, hashlib, logging, csv, io, tempfile, shutil
import threading
from starlette.concurrency import run_in_threadpool
from starlette._utils import get_route_path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from .config import ROOT,RUNTIME,SCHEMAS,SCHEMA,INDICATORS,INDUSTRIES,ALLOWED_EXT,MAX_UPLOAD_BYTES,DB_BACKEND,STORAGE_BACKEND
from .db import db, uid, now, dumps, quote
from .storage import store
from .jobs import submit, recover, update
from .ingest import parse_to_stage, commit_import, extract_raw, validate_record, derived
from .analytics import statistics,foundation,indicators,forecast_counts,wilson
from .sd import initialize_models,validate,simulate,import_vensim
from .sd_feedback import PROFILE_VERSION as FEEDBACK_VERSION
from .sd_factors import extract as extract_sd_factors
from .reports import create_report,render_pdf
from .auth import authorize, token_role, session_token, platform_identity, verify_password, login_retry_after, record_login
from .llm import ask,configured,complete,LLMError,available_models,resolve_model

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s',handlers=[logging.FileHandler(RUNTIME/'logs/app.log',encoding='utf-8'),logging.StreamHandler()])
# HTTP client log lines must never include request payloads or authorization headers.
logging.getLogger('httpx').setLevel(logging.WARNING)
@asynccontextmanager
async def lifespan(app):
    db.initialize(); recover(); initialize_models()
    yield

app=FastAPI(title='安全生产风险研判与预测智能体',version='1.0.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json',root_path=os.getenv('PUBLIC_BASE_PATH','').rstrip('/'))
import_lock=threading.Lock()
@app.middleware('http')
async def guard(request,call_next):
    route_path=get_route_path(request.scope)
    try:
        if route_path.startswith('/api/') and route_path not in ['/api/auth/session','/api/health']:
            authorize(request)
        response=await call_next(request)
    except HTTPException as e: response=JSONResponse({'detail':e.detail},status_code=e.status_code)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    if route_path.startswith('/api/') or route_path in ['/', '/agent']: response.headers['Cache-Control']='no-store'
    elif route_path.startswith('/assets/') and route_path.endswith(('.js', '.css')): response.headers['Cache-Control']='no-cache'
    return response
@app.exception_handler(ValueError)
async def bad_input(request,e): return JSONResponse({'detail':str(e)},status_code=422)
@app.exception_handler(Exception)
async def server_error(request,e):
    logging.getLogger('risk').exception('Unhandled %s',type(e).__name__)
    return JSONResponse({'detail':'服务执行失败，请查看运行日志'},status_code=500)

def schema_for(dataset):
    if dataset not in SCHEMA: raise HTTPException(404,'数据集不存在')
    return SCHEMA[dataset]
def get_or_404(kind,id):
    d=db.get_doc(kind,id)
    if not d: raise HTTPException(404,'对象不存在')
    return d
def filters_from(industry='',region='',start='',end='',q=''):
    if industry and industry not in INDUSTRIES: raise ValueError('行业无效')
    if len(region)>100 or len(q)>200: raise ValueError('筛选文本过长')
    from datetime import date
    for v in [start,end]:
        if v: date.fromisoformat(v)
    if start and end and start>end: raise ValueError('起始时间晚于结束时间')
    return {'industry':industry,'region':region,'start':start,'end':end,'q':q}

class Filters(BaseModel):
    industry:str=''
    region:str=''
    start:str=''
    end:str=''
    q:str=''
    @model_validator(mode='after')
    def check(self): filters_from(**{k:getattr(self,k) for k in ['industry','region','start','end','q']}); return self
class SimulationInput(BaseModel):
    model_id:str
    filters:Filters=Field(default_factory=Filters)
    months:int=Field(default=3,ge=1,le=36)
    parameters:dict[str,float]=Field(default_factory=dict)
    threshold:float=Field(default=60,ge=0,le=100)
class ReportInput(Filters):
    industry:str
    start:str
    end:str
    months:int=Field(default=3,ge=1,le=36)
    scenario:str='基准场景'
    model_id:str=''
    parameters:dict[str,float]=Field(default_factory=dict)
    indicators:list[str]
    threshold:float=Field(default=60,ge=0,le=100)
    coverage_confirmed:bool=False
    use_llm:bool=True
    llm_model:str=Field(default='',max_length=120)
    @model_validator(mode='after')
    def check_report(self):
        filters_from(self.industry,self.region,self.start,self.end,self.q)
        allowed={x for g in INDICATORS for x in g['items']}
        if not self.indicators or set(self.indicators)-allowed: raise ValueError('报告指标无效或为空')
        if self.scenario not in ['基准场景','生产压力增大','安全投入减少']: raise ValueError('预测情景无效')
        if len(self.indicators)!=len(set(self.indicators)): raise ValueError('报告指标重复')
        self.llm_model=resolve_model(self.llm_model)
        return self
class ReportReviewInput(BaseModel):
    conclusion:str=Field(default='',max_length=4000)
    indicator_validation:str=Field(default='',max_length=4000)
    reviewer:str=Field(default='',max_length=100)
    recommendations_match_percent:float|None=Field(default=None,ge=0,le=100)
    content_match_percent:float|None=Field(default=None,ge=0,le=100)
    @model_validator(mode='after')
    def check_review(self):
        self.conclusion=self.conclusion.strip();self.indicator_validation=self.indicator_validation.strip()
        self.reviewer=self.reviewer.strip()
        if not self.conclusion and not self.indicator_validation and self.recommendations_match_percent is None and self.content_match_percent is None: raise ValueError('请至少填写一项验证结果')
        return self

@app.get('/api/health')
def health():
    from .readiness import status
    result=status()
    result.update(version='1.0.0',model_engine_version=FEEDBACK_VERSION,simulation_samples_per_month=20)
    return JSONResponse(result,status_code=200 if result['status']=='ok' else 503)

@app.get('/api/system/status')
def system_status(request:Request):
    authorize(request,'admin')
    from .readiness import status
    return status(details=True)
@app.post('/api/auth/session')
async def login(request:Request):
    origin=request.headers.get('origin')
    if origin and origin!=request.url.scheme+'://'+request.url.netloc: raise HTTPException(403,'请求来源未授权')
    body=await request.json(); mode=os.getenv('AUTH_MODE','local'); token=str(body.get('token',''));identity=None;role=None;subject=''
    if mode=='platform': identity=platform_identity(token);role=identity['role'] if identity else None;subject=identity['sub'] if identity else ''
    elif mode=='token': role=token_role(token);subject=role or ''
    elif mode=='password':
        key=request.client.host if request.client else 'unknown';retry=login_retry_after(key)
        if retry: raise HTTPException(429,f'登录尝试过多，请在{retry}秒后重试')
        valid=verify_password(str(body.get('password','')));record_login(key,valid)
        if valid: role='admin';subject='password-admin'
    else: raise HTTPException(503,'当前认证模式不支持登录')
    if not role: raise HTTPException(401,'访问凭据无效')
    response=JSONResponse({'role':role}); response.set_cookie('risk_session',session_token(role,subject),httponly=True,secure=request.url.scheme=='https',samesite='strict',max_age=8*3600,path=os.getenv('PUBLIC_BASE_PATH','') or '/')
    return response
@app.get('/api/config')
def config(request:Request):
    actor=authorize(request)
    return {'schemas':SCHEMAS,'industries':INDUSTRIES,'indicator_groups':INDICATORS,'role':actor['role'],'auth_mode':os.getenv('AUTH_MODE','local'),'db_backend':DB_BACKEND,'storage_backend':STORAGE_BACKEND,'llm':{'provider':os.getenv('LLM_PROVIDER','DeepSeek'),'model':os.getenv('LLM_MODEL','deepseek-flash'),'models':available_models(),'configured':configured()},'platform_base_url':os.getenv('PLATFORM_BASE_URL','')}

@app.get('/api/overview')
def overview():
    counts={s['id']:db.query(f'SELECT COUNT(*) AS N FROM {s["table"]}')[0]['N'] for s in SCHEMAS}
    files=db.query('SELECT * FROM RISK_FILES'); bytes=sum(r['SIZE_BYTES'] for r in files)
    bounds=db.query('SELECT MIN("_date") AS START_DATE,MAX("_date") AS END_DATE FROM RISK_ACCIDENTS WHERE "_date"<>\'\'')[0]
    regions=[r['省份'] for r in db.query('SELECT DISTINCT "省份" FROM RISK_ACCIDENTS WHERE "省份" IS NOT NULL ORDER BY "省份"')]
    return {'counts':counts,'total_records':sum(counts.values()),'file_count':len(files),'bytes':bytes,'industry_count':len(INDUSTRIES),'model_count':len({m['industry'] for m in db.list_docs('model')}),'report_count':len(db.list_docs('report')),'dates':bounds,'regions':regions,'services':{'database':DB_BACKEND,'objects':STORAGE_BACKEND},'requirements':{'records_target':200000,'bytes_target':3*10**12,'records_met':sum(counts.values())>200000,'bytes_met':bytes>3*10**12}}

@app.get('/api/data/{dataset}')
def list_data(dataset:str,industry:str='',region:str='',start:str='',end:str='',q:str='',limit:int=Query(10,ge=1,le=200),offset:int=Query(0,ge=0)):
    schema_for(dataset); return db.records(dataset,limit,offset,**filters_from(industry,region,start,end,q))
@app.get('/api/data/{dataset}/export')
def export_data(dataset:str,industry:str='',region:str='',start:str='',end:str='',q:str=''):
    s=schema_for(dataset); filters=filters_from(industry,region,start,end,q)
    def generate():
        yield '\ufeff'; buf=io.StringIO(); writer=csv.writer(buf)
        def safe(v):
            t=str(v or '')
            return "'"+t if t.lstrip().startswith(('=','+','-','@','\t','\r')) else t
        writer.writerow(s['fields']); yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        for row in db.iter_records(dataset,**filters):
            writer.writerow([safe(row.get(f)) for f in s['fields']]); yield buf.getvalue(); buf.seek(0); buf.truncate(0)
    return StreamingResponse(generate(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{dataset}.csv"'})
@app.post('/api/data/{dataset}')
async def create_record(dataset:str,request:Request):
    actor=authorize(request,'editor'); schema_for(dataset); data=validate_record(dataset,await request.json()); id=db.add_record(dataset,data)
    if id is None: raise HTTPException(409,'记录已存在')
    db.audit(actor['sub'],'create_record',id); return {'id':id}
@app.put('/api/data/{dataset}/{id}')
async def edit_record(dataset:str,id:str,request:Request):
    actor=authorize(request,'editor'); s=schema_for(dataset); body=await request.json(); data=validate_record(dataset,body['data']); version=int(body['version'])
    i,r,d=derived(dataset,data); digest=hashlib.sha256(dumps({f:data.get(f) for f in s['fields']}).encode()).hexdigest()
    with db.transaction() as c:
        existing=db.query(f'SELECT * FROM {s["table"]} WHERE "_id"=?',[id],c)
        if not existing: raise HTTPException(404,'记录不存在')
        if existing[0]['_version']!=version: raise HTTPException(409,'记录已被修改，请刷新后重试')
        if db.query(f'SELECT "_id" FROM {s["table"]} WHERE "_hash"=? AND "_id"<>?',[digest,id],c): raise HTTPException(409,'修改后与已有记录重复')
        values={**{f:data.get(f) for f in s['fields']},'_industry':i,'_region':r,'_date':d,'_hash':digest,'_version':version+1}
        count=db.execute(f'UPDATE {s["table"]} SET '+','.join(quote(f)+'=?' for f in values)+' WHERE "_id"=? AND "_version"=?',list(values.values())+[id,version],c)
        if count!=1: raise HTTPException(409,'记录已被修改')
    db.audit(actor['sub'],'edit_record',id,{'version':version+1}); return {'id':id,'version':version+1}
@app.delete('/api/data/{dataset}/{id}')
def delete_record(dataset:str,id:str,request:Request):
    actor=authorize(request,'admin'); s=schema_for(dataset); count=db.execute(f'DELETE FROM {s["table"]} WHERE "_id"=?',[id]); db.audit(actor['sub'],'delete_record',id); return {'deleted':count}

def prepare_upload(job_id,file_id,dataset):
    file=db.query('SELECT * FROM RISK_FILES WHERE ID=?',[file_id])[0]; path=RUNTIME/'staging'/f'{file_id}{Path(file["NAME"]).suffix.lower()}'
    update(job_id,stage='解析原始资料',progress=15)
    store.fetch(file['OBJECT_KEY'],path)
    try:
        stage=parse_to_stage(path,file['NAME'],dataset)
        if stage['raw']:
            db.put_doc('file_text',file_id,{'id':file_id,'text':extract_raw(path,file['NAME']),'ocr_status':'未配置OCR' if Path(file['NAME']).suffix.lower() in ['.png','.jpg','.jpeg','.tiff'] else '不适用'})
        stage['file_id']=file_id; stage['committed']=stage['raw']; db.put_doc('stage',stage['id'],stage)
        db.execute('UPDATE RISK_FILES SET STATUS=? WHERE ID=?',['stored' if stage['raw'] else 'staged',file_id])
        return stage
    finally: path.unlink(missing_ok=True)

@app.post('/api/uploads')
async def upload(request:Request,file:UploadFile=File(...),dataset:str=Form('')):
    actor=authorize(request,'editor'); name=Path((file.filename or '').replace('\\','/')).name
    name=re.sub(r'[\x00-\x1f]','',name)[:240]; ext=Path(name).suffix.lower()
    if ext not in ALLOWED_EXT: raise ValueError('文件类型不受支持')
    id=uid(); temp=RUNTIME/'staging'/f'{id}.upload'; size=0; hasher=hashlib.sha256()
    try:
        with temp.open('wb') as out:
            while chunk:=await file.read(1024**2):
                size+=len(chunk)
                if size>MAX_UPLOAD_BYTES: raise HTTPException(413,'文件超过上传上限')
                hasher.update(chunk); out.write(chunk)
        if not size: raise ValueError('空文件')
        digest=hasher.hexdigest(); existing=db.query('SELECT * FROM RISK_FILES WHERE SHA256=?',[digest])
        if existing:
            id=existing[0]['ID']
            if existing[0]['STATUS']=='imported': return {'duplicate':True,'file_id':id,'message':'文件已导入，无需重复提交'}
        else:
            with temp.open('rb') as f: magic=f.read(16)
            signatures={'.pdf':b'%PDF-','.xlsx':b'PK','.docx':b'PK','.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8','.jpeg':b'\xff\xd8'}
            if ext in signatures and not magic.startswith(signatures[ext]): raise ValueError('文件内容与扩展名不一致')
            key=digest[:2]+'/'+digest+ext; real_size=await run_in_threadpool(store.put,key,temp)
            if real_size!=size: raise ValueError('对象存储大小校验失败')
            try: db.execute('INSERT INTO RISK_FILES VALUES (?,?,?,?,?,?,?)',[id,name,size,key,digest,'uploaded',now()])
            except Exception:
                existing=db.query('SELECT * FROM RISK_FILES WHERE SHA256=?',[digest])
                if not existing: store.delete(key); raise
                id=existing[0]['ID']
        db.audit(actor['sub'],'upload',id,{'size':size})
        return {'job':submit('parse',prepare_upload,id,dataset or None),'file_id':id}
    finally: temp.unlink(missing_ok=True); await file.close()
@app.post('/api/imports/{id}/commit')
def import_commit(id:str,request:Request):
    actor=authorize(request,'editor')
    with import_lock:
        stage=get_or_404('stage',id)
        if stage.get('committed'): raise HTTPException(409,'批次已提交')
        if not stage['valid']: raise ValueError('没有通过校验的记录')
        if stage.get('active_job'):
            active=db.get_doc('job',stage['active_job'])
            if active and active['status'] in ['queued','running']: raise HTTPException(409,'批次正在导入')
        job=submit('import',commit_import,id,actor['sub'])
        current=get_or_404('stage',id);current['active_job']=job['id'];db.put_doc('stage',id,current)
        return job
@app.get('/api/imports/{id}/errors')
def import_errors(id:str):
    get_or_404('stage',id); p=RUNTIME/'staging'/f'{id}.errors.jsonl'
    if not p.exists(): raise HTTPException(404,'无错误清单')
    return FileResponse(p,filename='import-errors.jsonl')
@app.get('/api/files')
def files(): return db.query('SELECT * FROM RISK_FILES ORDER BY CREATED_AT DESC')
@app.get('/api/files/{id}/preview')
def file_preview(id:str): return db.get_doc('file_text',id) or {'text':'结构化文件请在数据表中预览；图片请下载原件。'}
@app.get('/api/files/{id}/download')
def file_download(id:str):
    rows=db.query('SELECT * FROM RISK_FILES WHERE ID=?',[id])
    if not rows: raise HTTPException(404,'文件不存在')
    f=rows[0]; target=RUNTIME/'staging'/f'{id}.download'; store.fetch(f['OBJECT_KEY'],target)
    from starlette.background import BackgroundTask
    return FileResponse(target,filename=f['NAME'],media_type='application/octet-stream',background=BackgroundTask(target.unlink,missing_ok=True))
@app.delete('/api/files/{id}')
def file_delete(id:str,request:Request):
    actor=authorize(request,'admin'); rows=db.query('SELECT * FROM RISK_FILES WHERE ID=?',[id])
    if not rows: raise HTTPException(404,'文件不存在')
    db.execute('UPDATE RISK_FILES SET STATUS=? WHERE ID=?',['deleting',id]); store.delete(rows[0]['OBJECT_KEY'])
    with db.transaction() as c:
        for s in SCHEMAS: db.execute(f'DELETE FROM {s["table"]} WHERE "_file_id"=?',[id],c)
        db.execute('DELETE FROM RISK_FILES WHERE ID=?',[id],c); db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',['file_text',id],c)
    db.audit(actor['sub'],'delete_file_and_records',id); return {'deleted':True}
@app.post('/api/storage/verify')
def verify_storage(request:Request):
    authorize(request,'admin'); result=[]
    for f in db.query('SELECT * FROM RISK_FILES'):
        try:
            size=store.size(f['OBJECT_KEY']); result.append({'id':f['ID'],'name':f['NAME'],'bytes':size,'matches':size==f['SIZE_BYTES']})
        except Exception: result.append({'id':f['ID'],'name':f['NAME'],'bytes':None,'matches':False})
    return {'objects':result,'verified_bytes':sum(x['bytes'] or 0 for x in result),'all_verified':all(x['matches'] for x in result)}

@app.post('/api/analysis')
def analysis(body:Filters):
    stats=statistics(body.model_dump()); base=foundation(body.model_dump()); return {'statistics':stats,'foundation':base,'indicators':indicators(stats,base)}
@app.get('/api/models')
def models(): return db.list_docs('model')
@app.post('/api/models/validate')
async def model_validate(request:Request):
    model=await request.json(); result=validate(model)
    if model.get('profile_version')==FEEDBACK_VERSION:
        simulate(model,{'count':0,'cause_samples':0,'scope':{'industry':model['industry']}},12)
        result['stability_check']='三场景12个月非负与数值检查通过；不代表经过历史数据验证'
    return result
@app.post('/api/models')
async def model_create(request:Request):
    actor=authorize(request,'editor'); model=await request.json(); model['id']=uid(); model['version']=1; model['created_at']=now(); validate(model)
    with db.transaction() as c: db.put_doc('model',model['id'],model,c); db.put_doc('model_version',model['id']+':1',model,c)
    db.audit(actor['sub'],'create_model',model['id']); return model
@app.post('/api/models/import')
async def model_import(request:Request,file:UploadFile=File(...),industry:str=Form(...)):
    actor=authorize(request,'editor'); data=await file.read(1024*1024+1)
    if len(data)>1024*1024: raise ValueError('模型文件需小于1MB')
    name=file.filename or 'import.json'; ext=Path(name).suffix.lower(); text=data.decode('utf-8-sig')
    if ext=='.json': model=json.loads(text); model.update(id=uid(),version=1,created_at=now()); model['industry']=industry; validate(model)
    elif ext=='.mdl': model=import_vensim(text,industry,Path(name).stem)
    else: raise ValueError('支持risk-sd JSON和Vensim数值/INTEG子集；复杂原模型请使用外部运行适配接口')
    with db.transaction() as c: db.put_doc('model',model['id'],model,c); db.put_doc('model_version',model['id']+':1',model,c)
    db.audit(actor['sub'],'import_model',model['id']); return model
@app.put('/api/models/{id}')
async def model_save(id:str,request:Request):
    actor=authorize(request,'editor'); model=await request.json(); old=get_or_404('model',id)
    if model.get('version')!=old['version']: raise HTTPException(409,'模型版本已更新，请刷新')
    model.update(id=id,version=old['version']+1,updated_at=now()); validate(model)
    if old.get('model_family'): model['model_family']=old['model_family']
    if model.get('profile_version')==FEEDBACK_VERSION: simulate(model,{'count':0,'cause_samples':0,'scope':{'industry':model['industry']}},12)
    with db.transaction() as c:
        db.put_doc('model_version',id+':'+str(old['version']),old,c)
        db.put_doc('model',id,model,c); db.put_doc('model_version',id+':'+str(model['version']),model,c)
    db.audit(actor['sub'],'save_model',id,{'version':model['version']}); return model
@app.get('/api/models/{id}/versions')
def versions(id:str):
    get_or_404('model',id); return [m for m in db.list_docs('model_version') if m['id']==id]
@app.get('/api/models/{id}/export')
def model_export(id:str,version:int=0):
    model=get_or_404('model_version',id+':'+str(version)) if version else get_or_404('model',id)
    return StreamingResponse(iter([json.dumps(model,ensure_ascii=False,indent=2)]),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="model-v{model["version"]}.json"'})
@app.delete('/api/models/{id}')
def model_delete(id:str,request:Request):
    actor=authorize(request,'admin'); model=get_or_404('model',id)
    if sum(m['industry']==model['industry'] for m in db.list_docs('model'))<=1: raise ValueError('每个行业至少保留一个模型')
    db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',['model',id]); db.audit(actor['sub'],'delete_model',id); return {'deleted':True}
@app.post('/api/simulations')
def run_simulation(body:SimulationInput,request:Request):
    actor=authorize(request,'editor'); m=get_or_404('model',body.model_id); filters=body.filters.model_dump()
    if filters['industry'] and filters['industry']!=m['industry']: raise ValueError('模型行业与查询范围不一致')
    filters['industry']=m['industry']; stats=statistics(filters); result=simulate(m,stats,body.months,body.parameters,body.threshold)
    result['actor']=actor['sub']; db.put_doc('simulation',result['id'],result); db.audit(actor['sub'],'simulate',result['id']); return result
@app.get('/api/simulations')
def simulations(): return db.list_docs('simulation')
@app.get('/api/simulations/{id}/export')
def simulation_export(id:str):
    s=get_or_404('simulation',id); buf=io.StringIO(); w=csv.writer(buf)
    fields=['scenario','month',*(s['output_metrics'].keys() if s.get('output_metrics') else [*s['stock_names'],'risk_index'])]; w.writerow(fields)
    for scenario in s['scenarios']:
        for p in scenario['points']: w.writerow([scenario['name'],*[p.get(f) for f in fields[1:]]])
    return StreamingResponse(iter(['\ufeff'+buf.getvalue()]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="simulation.csv"'})

@app.get('/api/models/{id}/factor-evidence')
def model_factor_evidence(id:str,region:str='',start:str='',end:str='',factor:str='',page:int=0):
    model=get_or_404('model',id); filters=filters_from(model['industry'],region,start,end)
    if page<0: raise ValueError('页码无效')
    rows=[];total=0
    for source in db.iter_records('accidents',**filters):
        features=extract_sd_factors(source)
        hits={k:v for k,v in features['hits'].items() if not factor or k==factor}
        if not hits: continue
        if page*20<=total<(page+1)*20:
            rows.append({'record_id':source['_id'],'number':source.get('编号'),'title':source.get('事故名称'),
                'contexts':features['contexts'],'matches':hits})
        total+=1
    return {'rows':rows,'total':total,'page':page,'page_size':20,'note':'此处按原始报告列出命中依据；事故统计按系统去重规则归并。'}

@app.post('/api/reports')
def report_generate(body:ReportInput,request:Request):
    actor=authorize(request,'editor'); return submit('report',create_report,body.model_dump(),actor['sub'])
@app.get('/api/reports')
def report_list(): return db.list_docs('report')
@app.get('/api/reports/{id}/html')
def report_html(id:str,download:bool=False):
    get_or_404('report',id); return FileResponse(RUNTIME/'reports'/f'{id}.html',media_type='text/html',filename=f'report-{id[:8]}.html' if download else None,content_disposition_type='attachment' if download else 'inline')
@app.get('/api/reports/{id}/evidence')
def report_evidence(id:str):
    get_or_404('report',id); return FileResponse(RUNTIME/'reports'/f'{id}.json',filename='calculation-evidence.json')
@app.patch('/api/reports/{id}/review')
def report_review(id:str,body:ReportReviewInput,request:Request):
    actor=authorize(request,'editor'); report=get_or_404('report',id)
    values=body.model_dump(exclude_none=True)
    if 'recommendations_match_percent' in values: values['recommendations_target_met']=values['recommendations_match_percent']>70
    if 'content_match_percent' in values: values['content_target_met']=values['content_match_percent']>80
    review={**values,'updated_at':now(),'updated_by':actor['sub']}
    report['expert_review']=review;db.put_doc('report',id,report)
    db.audit(actor['sub'],'review_report',id,{'fields':[k for k,v in body.model_dump().items() if v]})
    return review
@app.post('/api/reports/{id}/pdf')
def report_pdf(id:str,request:Request):
    authorize(request,'editor'); get_or_404('report',id)
    def work(job_id,id):
        update(job_id,progress=30,stage='渲染A4与核对目录页码'); path=render_pdf(id); return {'report_id':id,'bytes':path.stat().st_size,'url':f'/api/reports/{id}/pdf'}
    return submit('pdf',work,id)
@app.get('/api/reports/{id}/pdf')
def report_pdf_download(id:str):
    get_or_404('report',id); path=RUNTIME/'reports'/f'{id}.pdf'
    if not path.exists(): raise HTTPException(404,'请先生成PDF')
    return FileResponse(path,filename=f'report-{id[:8]}.pdf')
@app.delete('/api/reports/{id}')
def report_delete(id:str,request:Request):
    actor=authorize(request,'admin'); get_or_404('report',id)
    for ext in ['html','json','pdf']: (RUNTIME/'reports'/f'{id}.{ext}').unlink(missing_ok=True)
    db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',['report',id]); db.audit(actor['sub'],'delete_report',id); return {'deleted':True}

@app.get('/api/jobs')
def jobs(): return db.list_docs('job')[:100]
@app.get('/api/jobs/{id}')
def job(id:str): return get_or_404('job',id)
@app.post('/api/llm/test')
def llm_test(request:Request):
    authorize(request,'admin')
    m=complete([{'role':'user','content':'仅回复：连接成功'}],max_tokens=30)
    return {'connected':True,'reply':m.get('content',''),'model':os.getenv('LLM_MODEL','deepseek-flash')}
@app.post('/api/chat')
async def chat(request:Request):
    actor=authorize(request,'viewer'); body=await request.json(); content=str(body.get('content','')).strip()
    if not content or len(content)>4000: raise ValueError('问题需在1至4000字符')
    filters=Filters(**body.get('filters',{})).model_dump()
    model=resolve_model(str(body.get('llm_model','')))
    return await run_in_threadpool(ask,content,filters,str(body.get('sessionId','')),actor['sub'],model)
@app.get('/api/history')
def history(request:Request):
    actor=authorize(request); return [s for s in db.list_docs('chat') if s['actor']==actor['sub']]
@app.patch('/api/history/{id}')
async def history_edit(id:str,request:Request):
    actor=authorize(request); s=get_or_404('chat',id)
    if s['actor']!=actor['sub']: raise HTTPException(403,'无权访问会话')
    body=await request.json()
    if 'title' in body: s['title']=str(body['title'])[:80]
    if 'pinned' in body: s['pinned']=bool(body['pinned'])
    return db.put_doc('chat',id,s)
@app.delete('/api/history/{id}')
def history_delete(id:str,request:Request):
    actor=authorize(request); s=get_or_404('chat',id)
    if s['actor']!=actor['sub']: raise HTTPException(403,'无权访问会话')
    db.execute('DELETE FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',['chat',id]); return {'deleted':True}

@app.get('/api/acceptance')
def acceptance():
    o=overview(); s=statistics({}); expert=db.list_docs('expert_evaluation'); latest=expert[0] if expert else None
    return {'records':{'actual':o['total_records'],'target':'>200000','met':o['requirements']['records_met']},'storage':{'actual_bytes':o['bytes'],'target_bytes':3*10**12,'met':o['requirements']['bytes_met'],'status':'元数据实测字节，需对象核验'},
        'industries':{'actual':6,'met':True,'status':'六行业初始模型与查询入口，机理模型待接入'},'indicators':{'groups':len(INDICATORS),'counts':[len(g['items']) for g in INDICATORS],'met':True,'status':'候选内容实现；实际可计算性取决于有效数据'},
        'coverage':{'actual_percent':s['coverage'],'met':bool(s['coverage'] and s['coverage']>95),'definition':'发生时间、省份、行业、事故类型、事故等级、死亡人数、直接原因七个基础字段完整；最终需按约定指标口径复核'},
        'prediction':{'status':'待约定统计口径及独立样本验证','met':False},'expert':latest,'expert_status':'未提供专家样本' if latest is None else '已录入人工标注评价，样本独立性待核验',
        'reports':[{'id':r['id'],'body_hanzi':r['body_hanzi'],'length_met':r['body_hanzi']>=3000,'status':r['status']} for r in db.list_docs('report')]}
@app.post('/api/acceptance/expert')
async def expert_evaluation(request:Request):
    actor=authorize(request,'admin'); body=await request.json(); cases=body.get('cases',[])
    if not cases or len(cases)>10000: raise ValueError('专家样本需1至10000条')
    names=[c.get('case_id') for c in cases]
    if any(not n for n in names) or len(set(names))!=len(names): raise ValueError('专家样本编号为空或重复')
    result={'id':uid(),'created_at':now(),'sample_count':len(cases),'definition':'每例由人工独立标注建议一致、关键内容一致；比例为二元标注均值，区间为90% Wilson区间','reviewer':str(body.get('reviewer',''))[:100]}
    if not result['reviewer']: raise ValueError('需填写专家审核人')
    for key,target in [('recommendations_match',70),('content_match',80)]:
        if any(type(c.get(key)) is not bool or not c.get('evidence') for c in cases): raise ValueError('每例需布尔一致性标记及审核证据说明')
        matches=sum(c[key] for c in cases); ci=wilson(matches,len(cases)); result[key]={'matches':matches,'total':len(cases),'percent':round(matches/len(cases)*100,2),'ci90':ci,'point_threshold_met':matches/len(cases)*100>target,'lower_bound_met':ci[0]>target}
    result['cases']=cases; db.put_doc('expert_evaluation',result['id'],result); db.audit(actor['sub'],'expert_evaluation',result['id']); return result
@app.get('/api/audit')
def audit(request:Request):
    authorize(request,'admin'); rows=db.query('SELECT * FROM RISK_AUDIT ORDER BY CREATED_AT DESC'); return rows[:200]

app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
@app.get('/agent')
@app.get('/')
def page():
    base=os.getenv('PUBLIC_BASE_PATH','').rstrip('/')
    if base and not re.fullmatch(r'(?:/[A-Za-z0-9_-]+)+',base): raise ValueError('PUBLIC_BASE_PATH格式无效')
    text=(ROOT/'frontend/index.html').read_text(encoding='utf-8').replace('content="APP_BASE"',f'content="{base}"')
    def asset_link(match):
        attribute,relative=match.groups()
        version=hashlib.sha256((ROOT/'frontend'/relative).read_bytes()).hexdigest()[:16]
        return f'{attribute}="{base}/assets/{relative}?v={version}"'
    text=re.sub(r'(href|src)="/assets/([^"?]+)"',asset_link,text)
    return HTMLResponse(text)
