"""Exercise a temporary object and rolled-back document against configured stores."""
from pathlib import Path
import hashlib, json, sys, tempfile, time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import db, uid
from app.readiness import status
from app.storage import store


def check():
    result = None
    for _ in range(40):
        result = status(details=True)
        if result['status'] == 'ok': break
        time.sleep(.25)
    if result['status'] != 'ok':
        raise RuntimeError('Configured database or object store is unavailable')
    identifier = uid()
    class RollbackProbe(Exception): pass
    try:
        with db.transaction() as conn:
            db.put_doc('storage_probe', identifier, {'text': '中文持久化验证', 'value': 1}, conn)
            assert db.query('SELECT ID FROM RISK_DOCUMENTS WHERE KIND=? AND ID=?', ['storage_probe', identifier], conn)
            raise RollbackProbe()
    except RollbackProbe:
        pass
    assert db.get_doc('storage_probe', identifier) is None
    key = '_health/' + identifier
    try:
        with tempfile.TemporaryDirectory(prefix='risk-storage-') as tmp:
            source, target = Path(tmp)/'source', Path(tmp)/'target'
            payload = '安全生产对象存储读写验证'.encode('utf-8')
            source.write_bytes(payload)
            assert store.put(key, source) == len(payload)
            store.fetch(key, target)
            assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(payload).digest()
    finally:
        store.delete(key)
    result.update(database_transaction_rollback=True, object_roundtrip=True)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
