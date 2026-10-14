"""DM8/SQLite DB-API repositories. Public field names remain the workbook's names."""
import sqlite3, json, os, uuid, hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import SCHEMA, SCHEMAS, RUNTIME, DB_BACKEND

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
def dumps(value): return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def quote(name): return '"'+name.replace('"','""')+'"'
def text_value(v):
    if hasattr(v,'read'): v=v.read()
    return v.decode('utf-8') if isinstance(v,bytes) else v

class Database:
    def connect(self):
        if DB_BACKEND == 'postgres':
            import psycopg
            return psycopg.connect(host=os.getenv('PG_HOST','127.0.0.1'),port=int(os.getenv('PG_PORT','5432')),
                dbname=os.environ['PG_DATABASE'],user=os.environ['PG_USER'],password=os.environ['PG_PASSWORD'],connect_timeout=5)
        if DB_BACKEND == 'dm8':
            import dmPython
            return dmPython.connect(user=os.environ['DM_USER'],password=os.environ['DM_PASSWORD'],
                server=os.environ['DM_HOST'],port=int(os.getenv('DM_PORT','5236')),autoCommit=False)
        conn=sqlite3.connect(RUNTIME/'risk.db',timeout=60)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    @contextmanager
    def transaction(self):
        conn=self.connect()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback(); raise
        finally: conn.close()

    def query(self,sql,params=(),conn=None):
        own=conn is None
        conn=conn or self.connect()
        try:
            cur=conn.cursor(); cur.execute(sql.replace('?', '%s') if DB_BACKEND=='postgres' else sql,tuple(params) or None if DB_BACKEND=='postgres' else tuple(params))
            keys=[d[0].upper() if DB_BACKEND=='postgres' and not d[0].startswith('_') else d[0] for d in cur.description]
            return [{k:text_value(v) for k,v in zip(keys,row)} for row in cur.fetchall()]
        finally:
            if own: conn.close()

    def execute(self,sql,params=(),conn=None):
        if conn is not None:
            cur=conn.cursor(); cur.execute(sql.replace('?', '%s') if DB_BACKEND=='postgres' else sql,tuple(params) or None if DB_BACKEND=='postgres' else tuple(params)); return cur.rowcount
        with self.transaction() as c: return self.execute(sql,params,c)

    def initialize(self):
        large='CLOB' if DB_BACKEND=='dm8' else 'TEXT'
        statements=[
            f'CREATE TABLE RISK_DOCUMENTS (KIND VARCHAR(40), ID VARCHAR(64), PAYLOAD {large}, CREATED_AT VARCHAR(40), PRIMARY KEY(KIND,ID))',
            'CREATE TABLE RISK_FILES (ID VARCHAR(64) PRIMARY KEY, NAME VARCHAR(512), SIZE_BYTES BIGINT, OBJECT_KEY VARCHAR(512), SHA256 VARCHAR(64) UNIQUE, STATUS VARCHAR(40), CREATED_AT VARCHAR(40))',
            f'CREATE TABLE RISK_AUDIT (ID VARCHAR(64) PRIMARY KEY, ACTOR VARCHAR(100), ACTION VARCHAR(100), TARGET VARCHAR(100), DETAIL {large}, CREATED_AT VARCHAR(40))']
        for schema in SCHEMAS:
            columns=[]
            for f in schema['fields']:
                long=any(k in f for k in ['原因','经过','整改','救援','备注','说明','来源链接'])
                columns.append(f'{quote(f)} {large if long else "VARCHAR(2000)"}')
            statements.append(f'CREATE TABLE {schema["table"]} ("_id" VARCHAR(64) PRIMARY KEY, "_file_id" VARCHAR(64), "_hash" VARCHAR(64) UNIQUE, "_industry" VARCHAR(100), "_region" VARCHAR(200), "_date" VARCHAR(32), "_version" INTEGER, "_created_at" VARCHAR(40), '+','.join(columns)+')')
        with self.transaction() as c:
            if DB_BACKEND=='postgres':
                existing={r['TABLE_NAME'].upper() for r in self.query("SELECT table_name FROM information_schema.tables WHERE table_schema='public'",conn=c)}
            else:
                existing={r['TABLE_NAME'] for r in self.query('SELECT TABLE_NAME FROM USER_TABLES',conn=c)} if DB_BACKEND=='dm8' else {r['name'].upper() for r in self.query("SELECT name FROM sqlite_master WHERE type='table'",conn=c)}
            for sql in statements:
                if sql.split()[2].upper() not in existing: self.execute(sql,conn=c)
            for s in SCHEMAS:
                for field in ['_date','_industry','_region','_file_id']:
                    name=s['table']+field.upper()+'_IDX'
                    if DB_BACKEND in {'sqlite','postgres'}: self.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {s["table"]} ({quote(field)})',conn=c)
                    elif not self.query('SELECT INDEX_NAME FROM USER_INDEXES WHERE INDEX_NAME=?',[name],c):
                        self.execute(f'CREATE INDEX {name} ON {s["table"]} ({quote(field)})',conn=c)

    def put_doc(self,kind,id,payload,conn=None):
        if conn is None:
            with self.transaction() as c: return self.put_doc(kind,id,payload,c)
        if self.query('SELECT ID FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',[kind,id],conn):
            self.execute('UPDATE RISK_DOCUMENTS SET PAYLOAD=? WHERE KIND=? AND ID=?',[dumps(payload),kind,id],conn)
        else: self.execute('INSERT INTO RISK_DOCUMENTS (KIND,ID,PAYLOAD,CREATED_AT) VALUES (?,?,?,?)',[kind,id,dumps(payload),now()],conn)
        return payload

    def get_doc(self,kind,id):
        rows=self.query('SELECT PAYLOAD FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?',[kind,id])
        return json.loads(rows[0]['PAYLOAD']) if rows else None

    def list_docs(self,kind):
        return [json.loads(r['PAYLOAD']) for r in self.query('SELECT PAYLOAD FROM RISK_DOCUMENTS WHERE KIND=? ORDER BY CREATED_AT DESC',[kind])]

    def audit(self,actor,action,target,detail=None):
        self.execute('INSERT INTO RISK_AUDIT VALUES (?,?,?,?,?,?)',[uid(),actor,action,target,dumps(detail or {}),now()])

    def where(self,dataset,industry='',region='',start='',end='',q=''):
        schema=SCHEMA[dataset]; parts=[]; vals=[]
        for field,value,op in [('_industry',industry,'='),('_region',region,'LIKE'),('_date',start,'>='),('_date',end,'<=')]:
            if value and value not in ['全部','全国']:
                parts.append(f'{quote(field)} {op} ?'); vals.append('%'+value+'%' if op=='LIKE' else value)
        if q:
            key=next((f for f in ['事故名称','企业名称','省份','地市','区县'] if f in schema['fields']),schema['fields'][0])
            parts.append(f'({quote(key)} LIKE ? OR {quote(schema["fields"][0])} LIKE ?)'); vals.extend(['%'+q+'%']*2)
        return (' WHERE '+' AND '.join(parts) if parts else ''),vals

    def records(self,dataset,limit=20,offset=0,**filters):
        s=SCHEMA[dataset]; where,args=self.where(dataset,**filters)
        total=self.query(f'SELECT COUNT(*) AS N FROM {s["table"]}'+where,args)[0]['N']
        page=' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY' if DB_BACKEND=='dm8' else ' LIMIT ? OFFSET ?'
        page_args=[offset,limit] if DB_BACKEND=='dm8' else [limit,offset]
        rows=self.query(f'SELECT * FROM {s["table"]}'+where+' ORDER BY "_date" DESC,"_id"'+page,args+page_args)
        return {'total':total,'items':rows,'fields':s['fields']}

    def iter_records(self,dataset,**filters):
        s=SCHEMA[dataset]; where,args=self.where(dataset,**filters); conn=self.connect()
        try:
            sql=f'SELECT * FROM {s["table"]}'+where
            cur=conn.cursor(); cur.execute(sql.replace('?', '%s') if DB_BACKEND=='postgres' else sql,tuple(args) or None if DB_BACKEND=='postgres' else tuple(args)); keys=[x[0].upper() if DB_BACKEND=='postgres' and not x[0].startswith('_') else x[0] for x in cur.description]
            while True:
                batch=cur.fetchmany(500)
                if not batch: break
                for row in batch: yield {k:text_value(v) for k,v in zip(keys,row)}
        finally: conn.close()

    def add_record(self,dataset,data,file_id='',conn=None):
        if conn is None:
            with self.transaction() as c: return self.add_record(dataset,data,file_id,c)
        s=SCHEMA[dataset]; data={f:data.get(f) for f in s['fields']}
        digest=hashlib.sha256(dumps(data).encode()).hexdigest()
        if self.query(f'SELECT "_id" FROM {s["table"]} WHERE "_hash"=?',[digest],conn): return None
        from .ingest import derived
        industry,region,date=derived(dataset,data)
        values={'_id':uid(),'_file_id':file_id,'_hash':digest,'_industry':industry,'_region':region,'_date':date,'_version':1,'_created_at':now(),**data}
        self.execute(f'INSERT INTO {s["table"]} ('+','.join(quote(k) for k in values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()),conn)
        return values['_id']

db=Database()

