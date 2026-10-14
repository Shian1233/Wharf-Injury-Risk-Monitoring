"""Check the configured stores; never expose endpoints or credentials."""
from .config import DB_BACKEND, STORAGE_BACKEND, RUNTIME, SCHEMAS
from .db import db
from .storage import store


def status(details=False):
    database = {'backend': DB_BACKEND, 'ready': False}
    objects = {'backend': STORAGE_BACKEND, 'ready': False}
    try:
        db.query('SELECT COUNT(*) AS N FROM RISK_DOCUMENTS')
        database['ready'] = True
        if details:
            database['datasets'] = {s['id']: db.query(f'SELECT COUNT(*) AS N FROM {s["table"]}')[0]['N'] for s in SCHEMAS}
    except Exception:
        database['ready'] = False
    try:
        objects['ready'] = store.client.bucket_exists(store.bucket) if STORAGE_BACKEND in {'minio','s3'} else (RUNTIME / 'objects').is_dir()
    except Exception:
        pass
    return {'status': 'ok' if database['ready'] and objects['ready'] else 'unavailable', 'database': database, 'objects': objects}
