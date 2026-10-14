"""Set a local access password without storing or printing the plaintext value."""
from getpass import getpass
from pathlib import Path
import re
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.auth import hash_password

def put(text,key,value):
    line=f'{key}={value}'
    pattern=rf'(?m)^{re.escape(key)}=.*$'
    return re.sub(pattern,line,text) if re.search(pattern,text) else text.rstrip()+f'\n{line}\n'

def main():
    password=getpass('请输入访问密码（至少12个字符）: ')
    confirm=getpass('请再次输入访问密码: ')
    if password!=confirm: raise SystemExit('两次输入不一致，未修改配置。')
    encoded=hash_password(password)
    env_path=ROOT/'.env'
    source=env_path if env_path.exists() else ROOT/'.env.example'
    text=source.read_text(encoding='utf-8')
    text=put(text,'AUTH_MODE','password')
    text=put(text,'APP_PASSWORD_HASH',encoded)
    match=re.search(r'(?m)^SESSION_SECRET=(.*)$',text)
    if not match or len(match.group(1).strip())<32 or match.group(1).startswith('replace-'):
        text=put(text,'SESSION_SECRET',secrets.token_urlsafe(48))
    env_path.write_text(text,encoding='utf-8',newline='\n')
    print('访问密码已加密保存。请重启智能体后使用新密码登录。')

if __name__=='__main__': main()
