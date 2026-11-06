"""本地假 IDS6.0（CAS 2.0）服务，仅用于联调单点登录，切勿用于生产。

启动（另开一个终端）：
    .venv\\Scripts\\python.exe -m uvicorn scripts.mock_cas:app --host 127.0.0.1 --port 8099

配合应用 .env：
    AUTH_MODE=cas
    CAS_SERVER_URL_PREFIX=http://127.0.0.1:8099/authserver
    CAS_SERVICE_URL=http://127.0.0.1:8001/api/auth/cas/callback
    CAS_ATTR_ID=alias
    CAS_ATTR_NAME=cn
    CAS_DEFAULT_ROLE=viewer

提供的端点与真实 IDS 一致：
    GET  /authserver/login?service=...       登录页（输入任意账号）
    GET  /authserver/serviceValidate         校验票据（一次性，含 service 比对）
    GET  /authserver/logout?service=...      平台登出后回跳
    POST /authserver/admin/slo               模拟 IDS 反向推送单点登出通知
    POST /authserver/admin/reset             清空已签发票据，便于重复测试
"""
import html
import secrets

import httpx
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

app = FastAPI(title='mock IDS6.0 CAS', docs_url=None, openapi_url=None)

PENDING = {}  # ticket -> 待校验的断言；校验成功后立即移除（票据一次性）
ISSUED = {}   # ticket -> 已签发记录，用于模拟单点登出

_ENVELOPE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">{}</cas:serviceResponse>')
_SUCCESS = ('<cas:authenticationSuccess><cas:user>{user}</cas:user>'
            '<cas:attributes><cas:cn>{cn}</cas:cn><cas:alias>{alias}</cas:alias></cas:attributes>'
            '</cas:authenticationSuccess>')
_FAILURE = '<cas:authenticationFailure code="{code}">{message}</cas:authenticationFailure>'
_SLO = ('<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
        'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="LR-{id}" Version="2.0" '
        'IssueInstant="2026-01-01T00:00:00Z"><saml:NameID>{user}</saml:NameID>'
        '<samlp:SessionIndex>{ticket}</samlp:SessionIndex></samlp:LogoutRequest>')


def _text(value):
    """XML/HTML 转义，避免属性值破坏响应结构。"""
    return html.escape(str(value or ''), quote=False)


def _failure(code, message):
    return Response(_ENVELOPE.format(_FAILURE.format(code=code, message=_text(message))),
                    media_type='application/xml')


@app.get('/authserver/login')
def login_page(service: str = '', renew: str = '', gateway: str = ''):
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Mock IDS 登录</title>
<style>body{{font-family:system-ui;max-width:460px;margin:80px auto}}
label{{display:block;margin:12px 0}}input{{width:100%;padding:8px;box-sizing:border-box}}
button{{padding:10px 18px}}code{{word-break:break-all}}</style>
<h3>Mock IDS6.0 统一身份认证</h3>
<form method="post" action="/authserver/login">
  <input type="hidden" name="service" value="{_text(service)}">
  <label>登录名 <input name="username" value="test"></label>
  <label>姓名 <input name="cn" value="测试用户"></label>
  <label>别名 <input name="alias" value="test"></label>
  <button type="submit">登录</button>
</form>
<p>service: <code>{_text(service)}</code></p></body></html>'''
    return HTMLResponse(page)


@app.post('/authserver/login')
def login_submit(service: str = Form(''), username: str = Form(''),
                 cn: str = Form(''), alias: str = Form('')):
    username = (username or '').strip()
    if not username:
        return Response('缺少登录名', status_code=400)
    if not service:
        return Response('缺少 service 参数', status_code=400)
    ticket = 'ST-' + secrets.token_urlsafe(18)
    record = {'service': service, 'user': username,
              'cn': cn or username, 'alias': alias or username}
    PENDING[ticket] = record
    ISSUED[ticket] = record
    joiner = '&' if '?' in service else '?'
    return RedirectResponse(f'{service}{joiner}ticket={ticket}', status_code=302)


@app.get('/authserver/serviceValidate')
def service_validate(service: str = '', ticket: str = '', format: str = ''):
    record = PENDING.pop(ticket, None)
    if not record:
        return _failure('INVALID_TICKET', 'ticket not recognized')
    if record['service'] != service:
        return _failure('INVALID_SERVICE', 'service mismatch')
    body = _SUCCESS.format(user=_text(record['user']), cn=_text(record['cn']),
                           alias=_text(record['alias']))
    return Response(_ENVELOPE.format(body), media_type='application/xml')


@app.get('/authserver/logout')
def logout(service: str = ''):
    return RedirectResponse(service or '/', status_code=302)


@app.post('/authserver/admin/slo')
def push_single_logout(ticket: str = Form('')):
    """按 service 地址回推 logoutRequest，等价于 IDS 端统一注销。"""
    record = ISSUED.get(ticket)
    if not record:
        return Response('unknown ticket', status_code=404)
    body = _SLO.format(id=secrets.token_hex(4), user=_text(record['user']), ticket=_text(ticket))
    try:
        with httpx.Client(timeout=5) as client:
            result = client.post(record['service'], data={'logoutRequest': body})
    except httpx.HTTPError as error:
        return Response(f'push failed: {type(error).__name__}', status_code=502)
    return {'target': record['service'], 'status': result.status_code}


@app.post('/authserver/admin/reset')
def reset():
    PENDING.clear()
    ISSUED.clear()
    return {'cleared': True}
