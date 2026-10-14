from pathlib import Path
import os, json
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
RUNTIME = Path(os.getenv('RISK_RUNTIME', str(ROOT / 'runtime'))).resolve()
for d in ['', 'objects', 'staging', 'reports', 'logs']:
    (RUNTIME / d).mkdir(parents=True, exist_ok=True)
SCHEMAS = json.loads((ROOT/'config/schema.json').read_text(encoding='utf-8'))
SCHEMA = {s['id']:s for s in SCHEMAS}
INDICATORS = json.loads((ROOT/'config/indicators.json').read_text(encoding='utf-8'))
INDUSTRIES = ['煤矿','金属非金属矿山','石油天然气开采','化工','烟花爆竹','工贸']
DB_BACKEND = os.getenv('DB_BACKEND','sqlite')
STORAGE_BACKEND = os.getenv('STORAGE_BACKEND','local')
if DB_BACKEND not in {'sqlite','dm8','postgres'}:
    raise ValueError('DB_BACKEND 必须为 sqlite、dm8 或 postgres，不能自动回退数据库')
if STORAGE_BACKEND not in {'local','minio','s3'}:
    raise ValueError('STORAGE_BACKEND 必须为 local、minio 或 s3，不能自动回退存储')
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES',str(10*1024**3)))
ALLOWED_EXT = {'.xlsx','.csv','.pdf','.docx','.html','.htm','.png','.jpg','.jpeg','.tiff','.txt','.json','.mdl','.xmile'}

