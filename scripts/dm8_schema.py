from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
schemas=json.loads((ROOT/'config/schema.json').read_text(encoding='utf-8'))
ddl=['-- DM8: connect as the dedicated RISK_AGENT schema owner. UTF-8.',
 'CREATE TABLE RISK_DOCUMENTS (KIND VARCHAR(40), ID VARCHAR(64), PAYLOAD CLOB, CREATED_AT VARCHAR(40), PRIMARY KEY(KIND,ID));',
 'CREATE TABLE RISK_FILES (ID VARCHAR(64) PRIMARY KEY, NAME VARCHAR(512), SIZE_BYTES BIGINT, OBJECT_KEY VARCHAR(512), SHA256 VARCHAR(64) UNIQUE, STATUS VARCHAR(40), CREATED_AT VARCHAR(40));',
 'CREATE TABLE RISK_AUDIT (ID VARCHAR(64) PRIMARY KEY, ACTOR VARCHAR(100), ACTION VARCHAR(100), TARGET VARCHAR(100), DETAIL CLOB, CREATED_AT VARCHAR(40));']
for s in schemas:
    cols=['"_id" VARCHAR(64) PRIMARY KEY','"_file_id" VARCHAR(64)','"_hash" VARCHAR(64) UNIQUE','"_industry" VARCHAR(100)','"_region" VARCHAR(200)','"_date" VARCHAR(32)','"_version" INTEGER','"_created_at" VARCHAR(40)']
    for f in s['fields']:
        long=any(k in f for k in ['原因','经过','整改','救援','备注','说明','来源链接'])
        cols.append('"'+f+'" '+('CLOB' if long else 'VARCHAR(2000)'))
    ddl.append('-- '+s['sheet']+' ('+str(len(s['fields']))+' original fields)\nCREATE TABLE '+s['table']+' (\n  '+',\n  '.join(cols)+'\n);')
    for f in ['_date','_industry','_region','_file_id']:ddl.append(f'CREATE INDEX {s["table"]}{f.upper()}_IDX ON {s["table"]} ("{f}");')
(ROOT/'database/dm8.sql').write_text('\n\n'.join(ddl),encoding='utf-8')
print('DM8 schema exported')
