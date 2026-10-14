"""Consistent SQLite snapshot plus local artifacts. Run while app is stopped."""
from pathlib import Path
import argparse, hashlib, json, shutil, sqlite3, sys
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import DB_BACKEND, STORAGE_BACKEND, RUNTIME


def backup(destination):
    if (DB_BACKEND, STORAGE_BACKEND) != ('sqlite', 'local'):
        raise ValueError('This backup command requires sqlite + local; use native backup for DM8/MinIO')
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(RUNTIME/'risk.db') as source, sqlite3.connect(target/'risk.db') as snapshot:
        source.backup(snapshot)
        assert snapshot.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    for name in ('objects', 'reports'):
        shutil.copytree(RUNTIME/name, target/name)
    manifest = {'created_at': datetime.now().astimezone().isoformat(), 'database': 'sqlite', 'objects': 'local', 'sha256': {}}
    for file in sorted(target.rglob('*')):
        if file.is_file():
            digest = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
            manifest['sha256'][file.relative_to(target).as_posix()] = digest.hexdigest()
    (target/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(RUNTIME/'backups'/datetime.now().strftime('%Y%m%d-%H%M%S')))
    args = parser.parse_args()
    print(backup(args.output))
