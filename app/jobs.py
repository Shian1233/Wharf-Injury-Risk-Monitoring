from concurrent.futures import ThreadPoolExecutor
import traceback, logging
from .db import db, uid, now
pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='risk')
log=logging.getLogger('risk.jobs')

def update(id,**changes):
    job=db.get_doc('job',id)
    job.update(changes); job['updated_at']=now(); db.put_doc('job',id,job)
    return job

def submit(kind,fn,*args):
    id=uid(); db.put_doc('job',id,{'id':id,'kind':kind,'status':'queued','progress':0,'stage':'等待执行','created_at':now()})
    def run():
        try:
            update(id,status='running',stage='开始执行',progress=1)
            result=fn(id,*args)
            update(id,status='completed',progress=100,stage='执行完成',result=result)
        except Exception as e:
            log.error('job %s failed: %s',id,type(e).__name__,exc_info=True)
            update(id,status='failed',stage='执行失败',error=str(e)[:600])
    pool.submit(run)
    return db.get_doc('job',id)

def recover():
    for job in db.list_docs('job'):
        if job['status'] in ['queued','running']:
            update(job['id'],status='failed',stage='服务已重启，请重新执行',error='任务中断。已提交的导入批次保留，重新导入按行摘要去重。')

