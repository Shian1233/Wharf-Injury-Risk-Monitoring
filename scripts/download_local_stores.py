"""Download official Windows runtimes used by scripts/local_stores.ps1."""
from pathlib import Path
import hashlib, shutil, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'runtime' / 'services'
DOWNLOADS = TARGET / 'downloads'
POSTGRES_URL = 'https://get.enterprisedb.com/postgresql/postgresql-17.11-5-windows-x64-binaries.zip'
SEAWEED_URL = 'https://github.com/seaweedfs/seaweedfs/releases/download/4.48/windows_amd64.zip'
SEAWEED_SHA256 = 'fe90c04c0620ad1a1c756f86cd5e1443773f56a446688077a4bb5ec04c3cc874'


def download(url, path):
    temporary = path.with_suffix(path.suffix + '.part')
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    temporary.replace(path)


def install():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    weed_archive = DOWNLOADS / 'seaweedfs.zip'
    postgres_archive = DOWNLOADS / 'postgresql.zip'
    if not weed_archive.exists(): download(SEAWEED_URL, weed_archive)
    if hashlib.sha256(weed_archive.read_bytes()).hexdigest() != SEAWEED_SHA256:
        raise ValueError('SeaweedFS publisher SHA-256 mismatch')
    if not postgres_archive.exists(): download(POSTGRES_URL, postgres_archive)
    with zipfile.ZipFile(weed_archive) as archive:
        archive.extractall(TARGET / 'seaweedfs')
    destination = TARGET / 'postgresql'
    with zipfile.ZipFile(postgres_archive) as archive:
        selected = [item for item in archive.infolist() if item.filename.startswith(('pgsql/bin/', 'pgsql/lib/', 'pgsql/share/'))]
        for item in selected:
            archive.extract(item, destination)
    if not (destination / 'pgsql' / 'bin' / 'initdb.exe').exists():
        raise ValueError('PostgreSQL runtime extraction is incomplete')
    print('PostgreSQL 17.11 and SeaweedFS 4.48 runtimes are ready.')


if __name__ == '__main__':
    install()
