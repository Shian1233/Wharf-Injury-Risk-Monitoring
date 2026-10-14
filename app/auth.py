import os, json, hmac, hashlib, base64, time, threading
from urllib.parse import urlparse
from fastapi import HTTPException, Request

ROLES={'viewer':0,'editor':1,'admin':2}
PASSWORD_SCHEME='pbkdf2_sha256'
PASSWORD_ITERATIONS=600_000
_login_failures={}
_login_lock=threading.Lock()
def encode(value): return base64.urlsafe_b64encode(value).decode().rstrip('=')
def hash_password(password,salt=None,iterations=PASSWORD_ITERATIONS):
    if not isinstance(password,str) or len(password)<12: raise ValueError('访问密码至少需要12个字符')
    salt=salt or os.urandom(18)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,iterations)
    return f'{PASSWORD_SCHEME}${iterations}${encode(salt)}${encode(digest)}'
def verify_password(password):
    stored=os.getenv('APP_PASSWORD_HASH','')
    try:
        scheme,rounds,salt,digest=stored.split('$',3); rounds=int(rounds)
        if scheme!=PASSWORD_SCHEME or not 100_000<=rounds<=2_000_000: raise ValueError
        salt=base64.urlsafe_b64decode(salt+'='*(-len(salt)%4))
        expected=base64.urlsafe_b64decode(digest+'='*(-len(digest)%4))
    except (ValueError,TypeError):
        rounds=100_000;salt=b'\0'*18;expected=b'\0'*32
    actual=hashlib.pbkdf2_hmac('sha256',str(password).encode('utf-8'),salt,rounds)
    return bool(stored) and hmac.compare_digest(actual,expected)
def login_retry_after(key):
    now=time.time();window=300;limit=5
    with _login_lock:
        recent=[stamp for stamp in _login_failures.get(key,[]) if now-stamp<window]
        if recent:_login_failures[key]=recent
        else:_login_failures.pop(key,None)
        return max(1,int(window-(now-recent[0]))) if len(recent)>=limit else 0
def record_login(key,success):
    with _login_lock:
        if success:_login_failures.pop(key,None)
        else:_login_failures.setdefault(key,[]).append(time.time())
def signing_key():
    key=os.getenv('SESSION_SECRET','')
    if len(key)<32: raise RuntimeError('SESSION_SECRET必须配置至少32字符')
    return key.encode()
def session_token(role,subject):
    body=encode(json.dumps({'role':role,'sub':subject,'exp':time.time()+8*3600}).encode())
    return body+'.'+encode(hmac.new(signing_key(),body.encode(),hashlib.sha256).digest())
def decode_session(token):
    try:
        body,sig=token.split('.')
        if not hmac.compare_digest(sig,encode(hmac.new(signing_key(),body.encode(),hashlib.sha256).digest())): return None
        value=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if value['exp']<time.time() or value['role'] not in ROLES: return None
        return value
    except (ValueError,KeyError,TypeError): return None
def token_role(token):
    for role,known in json.loads(os.getenv('ROLE_TOKENS','{}')).items():
        if role in ROLES and known and hmac.compare_digest(token,str(known)): return role
    return None
def platform_identity(token):
    """Validate an existing platform HS256 JWT; the platform owns login and users."""
    try:
        head,body,sig=token.split('.')
        header=json.loads(base64.urlsafe_b64decode(head+'='*(-len(head)%4)))
        secret=os.getenv('PLATFORM_JWT_SECRET','')
        if len(secret)<32 or header.get('alg')!='HS256': return None
        expected=encode(hmac.new(secret.encode(),(head+'.'+body).encode(),hashlib.sha256).digest())
        if not hmac.compare_digest(expected,sig): return None
        claims=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if not claims.get('sub') or float(claims.get('exp',0))<time.time() or float(claims.get('nbf',0))>time.time(): return None
        issuer=os.getenv('JWT_ISSUER','');audience=os.getenv('JWT_AUDIENCE','')
        if not issuer or not audience or claims.get('iss')!=issuer: return None
        aud=claims.get('aud',[]);aud=[aud] if isinstance(aud,str) else aud
        if audience not in aud or claims.get('role') not in ROLES: return None
        return {'role':claims['role'],'sub':str(claims['sub'])[:100]}
    except (ValueError,TypeError,KeyError): return None
def authorize(request:Request,minimum='viewer'):
    mode=os.getenv('AUTH_MODE','local'); actor=None
    if mode=='local':
        host=request.url.hostname
        if request.client and request.client.host in ['127.0.0.1','::1','testclient'] and host in ['127.0.0.1','localhost','::1','testserver']:
            actor={'role':'admin','sub':'local-admin'}
    elif mode=='token':
        header=request.headers.get('authorization',''); role=token_role(header[7:]) if header.startswith('Bearer ') else None
        actor={'role':role,'sub':role} if role else decode_session(request.cookies.get('risk_session',''))
    elif mode=='platform':
        header=request.headers.get('authorization','')
        actor=platform_identity(header[7:]) if header.startswith('Bearer ') else decode_session(request.cookies.get('risk_session',''))
    elif mode=='password':
        actor=decode_session(request.cookies.get('risk_session',''))
    else: raise HTTPException(503,'AUTH_MODE配置无效')
    if not actor: raise HTTPException(401,'请先完成访问验证')
    if ROLES[actor['role']]<ROLES[minimum]: raise HTTPException(403,'当前账号无权执行此操作')
    if request.method not in ['GET','HEAD','OPTIONS']:
        origin=request.headers.get('origin')
        allowed={request.url.scheme+'://'+request.url.netloc,*os.getenv('ALLOWED_ORIGINS','').split(',')}
        if origin and origin not in allowed: raise HTTPException(403,'请求来源未授权')
    return actor

