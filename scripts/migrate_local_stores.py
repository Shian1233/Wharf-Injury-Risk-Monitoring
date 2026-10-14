"""Copy an immutable SQLite snapshot and local objects into empty PostgreSQL/S3.

Environment must select the destination stores. Does not modify the source.
"""
from pathlib import Path
import argparse, hashlib, json, sqlite3, sys, tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import db, quote
from app.config import DB_BACKEND, STORAGE_BACKEND
from app.storage import store


def migrate(source):
    if DB_BACKEND!='postgres' or STORAGE_BACKEND!='s3':raise ValueError('Destination must be postgres + s3')
    source=Path(source).resolve()
    db.initialize()
    conn=sqlite3.connect(f'{(source/"risk.db").as_uri()}?mode=ro',uri=True);conn.row_factory=sqlite3.Row
    names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'RISK_%'")]
    result={}
    with db.transaction() as target:
        for name in names:
            if db.query(f'SELECT COUNT(*) AS N FROM {name}',conn=target)[0]['N']:
                raise ValueError('Destination table is not empty: '+name)
            rows=conn.execute(f'SELECT * FROM {name}').fetchall()
            for row in rows:
                # Unquoted metadata names in PostgreSQL fold to lower case;
                # workbook and internal underscore fields retain exact spelling.
                columns=[quote(k if k.startswith('_') or not k.isascii() else k.lower()) for k in row.keys()]
                db.execute(f'INSERT INTO {name} ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(row),target)
            actual=db.query(f'SELECT * FROM {name}',conn=target)
            encode=lambda items:sorted(json.dumps(dict(x),sort_keys=True,ensure_ascii=False) for x in items)
            if encode(actual)!=encode(rows):raise ValueError('Row content mismatch: '+name)
            result[name]=len(rows)
        if not store.client.bucket_exists(store.bucket):store.client.make_bucket(store.bucket)
        objects=[]
        for row in conn.execute('SELECT * FROM RISK_FILES'):
            path=source/'objects'/row['OBJECT_KEY']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row['SHA256']:raise ValueError('Source checksum mismatch')
            store.put(row['OBJECT_KEY'],path)
            with tempfile.TemporaryDirectory() as temp:
                fetched=store.fetch(row['OBJECT_KEY'],Path(temp)/'object')
                if hashlib.sha256(fetched.read_bytes()).hexdigest()!=row['SHA256']:raise ValueError('S3 checksum mismatch')
            objects.append({'id':row['ID'],'bytes':row['SIZE_BYTES'],'sha256_verified':True})
    conn.close()
    return {'tables':result,'objects':objects,'all_rows_verified':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',help='Backup directory containing risk.db and objects/')
    args=parser.parse_args()
    print(json.dumps(migrate(args.source),ensure_ascii=False,indent=2))
