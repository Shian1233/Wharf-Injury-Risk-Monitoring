"""IDS6.0 统一身份认证（CAS）接入测试。

样本 XML 依据《IDSV6.0 .net应用集成接口说明_V1.3》与 cas_demo 的实际解析
行为构造：属性名取元素名、同名元素表示多值、属性值可为中文。
"""
import httpx
import pytest

from app import cas
from app.auth import cas_set_user_role
from app.db import db

SUCCESS = '''<?xml version="1.0" encoding="UTF-8"?>
<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
  <cas:authenticationSuccess>
    <cas:user>test</cas:user>
    <cas:attributes>
      <cas:cn>张三</cas:cn>
      <cas:alias>zhangsan</cas:alias>
      <cas:role>teacher</cas:role>
      <cas:role>staff</cas:role>
    </cas:attributes>
  </cas:authenticationSuccess>
</cas:serviceResponse>'''

# 少数部署把属性直接挂在 authenticationSuccess 下，不带 attributes 包裹层。
SUCCESS_FLAT = '<serviceResponse><authenticationSuccess><user>test</user><cn>李四</cn></authenticationSuccess></serviceResponse>'

FAILURE = '''<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
  <cas:authenticationFailure code="INVALID_TICKET">Ticket ST-secret not recognized</cas:authenticationFailure>
</cas:serviceResponse>'''

LOGOUT = '''<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="LR-1" Version="2.0"
    IssueInstant="2026-01-01T00:00:00Z">
  <saml:NameID>test</saml:NameID>
  <samlp:SessionIndex>ST-1-abcDEF123</samlp:SessionIndex>
</samlp:LogoutRequest>'''

XXE = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>' \
      '<LogoutRequest><SessionIndex>&xxe;</SessionIndex></LogoutRequest>'


def stub_cas(monkeypatch, body, status=200):
    """把票据校验指向本地假响应，记录真实请求地址。"""
    seen = {}

    def handler(request):
        seen['url'] = str(request.url)
        return httpx.Response(status, text=body, headers={'content-type': 'application/xml'})
    monkeypatch.setattr(cas, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return seen


def platform(monkeypatch, default_role='viewer'):
    monkeypatch.setenv('AUTH_MODE', 'cas')
    monkeypatch.setenv('CAS_SERVER_URL_PREFIX', 'https://ids.example.edu/authserver')
    monkeypatch.setenv('CAS_SERVICE_URL', 'https://risk.example.edu/api/auth/cas/callback')
    monkeypatch.setenv('CAS_DEFAULT_ROLE', default_role)
    db.execute('DELETE FROM RISK_CAS_SESSION')
    db.execute('DELETE FROM RISK_CAS_USER_ROLE')


def test_parse_service_response_reads_ids_attributes():
    assertion = cas.parse_service_response(SUCCESS)
    assert assertion.user == 'test'
    assert assertion.attributes['cn'] == ['张三']
    assert assertion.attributes['alias'] == ['zhangsan']
    assert assertion.attributes['role'] == ['teacher', 'staff']
    flat = cas.parse_service_response(SUCCESS_FLAT)
    assert flat.user == 'test' and flat.attributes['cn'] == ['李四']
    assert cas.subject(assertion) == 'test'
    assert cas.display_name(assertion) == '张三'


def test_parse_service_response_rejects_failure_without_leaking_ticket():
    with pytest.raises(cas.CasError) as failure:
        cas.parse_service_response(FAILURE)
    assert 'INVALID_TICKET' in str(failure.value)
    assert 'ST-secret' not in str(failure.value)
    for bad in ['', 'not xml', '<html><body>oops</body></html>', '<serviceResponse/>']:
        with pytest.raises(cas.CasError):
            cas.parse_service_response(bad)


def test_logout_ticket_extraction():
    assert cas.logout_ticket({'logoutRequest': LOGOUT}) == 'ST-1-abcDEF123'
    assert cas.logout_ticket({}) == ''
    assert cas.logout_ticket({'logoutRequest': '<html>no</html>'}) == ''
    assert cas.logout_ticket({'logoutRequest': XXE}) == ''
    assert cas.logout_ticket({'logoutRequest': 'x' * 8193}) == ''


def test_safe_next_blocks_open_redirect(monkeypatch):
    monkeypatch.setenv('PUBLIC_BASE_PATH', '/risk-agent')
    assert cas.safe_next('') == '/risk-agent/'
    assert cas.safe_next('/risk-agent/reports') == '/risk-agent/reports'
    for bad in ['//evil.example', 'https://evil.example', '/etc/passwd', '/risk-agent\\..', '/other']:
        with pytest.raises(cas.CasError):
            cas.safe_next(bad)
    monkeypatch.setenv('CAS_NEXT_ALLOWLIST', '/risk-agent/reports')
    with pytest.raises(cas.CasError):
        cas.safe_next('/risk-agent/data')


def test_cas_login_callback_and_single_logout(client, monkeypatch):
    platform(monkeypatch)
    seen = stub_cas(monkeypatch, SUCCESS)
    login = client.get('/api/auth/cas/login?next=/reports', follow_redirects=False)
    assert login.status_code == 302
    assert login.headers['location'].startswith('https://ids.example.edu/authserver/login?')
    assert 'service=https%3A%2F%2Frisk.example.edu%2Fapi%2Fauth%2Fcas%2Fcallback' in login.headers['location']
    callback = client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False)
    assert callback.status_code == 302 and callback.headers['location'] == '/reports'
    assert 'service=https%3A%2F%2Frisk.example.edu%2Fapi%2Fauth%2Fcas%2Fcallback' in seen['url']
    assert 'ticket=ST-1-abcDEF123' in seen['url']
    assert client.get('/api/config').json()['auth_mode'] == 'cas'
    assert db.query('SELECT SERVICE_TICKET FROM RISK_CAS_SESSION')[0]['SERVICE_TICKET'] == 'ST-1-abcDEF123'
    assert client.post('/api/auth/cas/slo', data={'logoutRequest': LOGOUT}).status_code == 200
    assert client.get('/api/config').status_code == 401


def test_cas_single_logout_arrives_at_service_url(client, monkeypatch):
    """IDS 把登出通知推送到 service 地址，回调路径必须能接收。"""
    platform(monkeypatch)
    stub_cas(monkeypatch, SUCCESS)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 302
    assert client.get('/api/config').status_code == 200
    assert client.post('/api/auth/cas/callback', data={'logoutRequest': LOGOUT}).status_code == 200
    assert client.get('/api/config').status_code == 401


def test_cas_callback_needs_ticket_and_rejects_bad_ticket(client, monkeypatch):
    platform(monkeypatch)
    assert client.get('/api/auth/cas/callback', follow_redirects=False).status_code == 400
    stub_cas(monkeypatch, FAILURE)
    rejected = client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False)
    assert rejected.status_code == 401 and 'ST-1' not in rejected.text
    stub_cas(monkeypatch, SUCCESS, status=500)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 401


def test_cas_role_mapping_and_authorization(client, monkeypatch):
    platform(monkeypatch, default_role='none')
    stub_cas(monkeypatch, SUCCESS)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 403
    cas_set_user_role('test', 'editor', 'local-admin')
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 302
    assert client.get('/api/config').json()['role'] == 'editor'
    with pytest.raises(ValueError):
        cas_set_user_role('test', 'root')


def test_cas_logout_revokes_session_and_clears_cookie(client, monkeypatch):
    platform(monkeypatch)
    stub_cas(monkeypatch, SUCCESS)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 302
    assert client.get('/api/config').status_code == 200
    out = client.get('/api/auth/cas/logout', follow_redirects=False)
    assert out.status_code == 302
    assert out.headers['location'].startswith('https://ids.example.edu/authserver/logout?')
    assert db.query("SELECT REVOKED_AT FROM RISK_CAS_SESSION WHERE REVOKED_AT<>''")
    assert client.get('/api/config').status_code == 401


def test_cas_entry_exposes_service_and_login_url(client, monkeypatch):
    """门户配置需要 service 与 IDS 登录地址，接口直接给出可复制的值。"""
    platform(monkeypatch)
    entry = client.get('/api/auth/cas/entry?next=/agent').json()
    assert entry['service'] == 'https://risk.example.edu/api/auth/cas/callback'
    assert entry['next'] == '/agent'
    assert entry['login_url'] == '/api/auth/cas/login?next=%2Fagent'
    assert entry['ids_login_url'].startswith('https://ids.example.edu/authserver/login?service=')


def test_anonymous_page_redirects_to_ids(client, monkeypatch):
    """门户直接链接到首页时，未登录应自动跳认证，而不是停在弹窗上。"""
    platform(monkeypatch)
    res = client.get('/', follow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == '/api/auth/cas/login?next=%2F'


def test_page_renders_without_redirect_after_login(client, monkeypatch):
    platform(monkeypatch)
    stub_cas(monkeypatch, SUCCESS)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 302
    assert client.get('/', follow_redirects=False).status_code == 200


def test_local_logout_mode_skips_ids_logout(client, monkeypatch):
    """CAS_LOGOUT_MODE=local 只注销本系统，不影响门户的单点会话。"""
    platform(monkeypatch)
    monkeypatch.setenv('CAS_LOGOUT_MODE', 'local')
    stub_cas(monkeypatch, SUCCESS)
    assert client.get('/api/auth/cas/callback?ticket=ST-1-abcDEF123', follow_redirects=False).status_code == 302
    out = client.get('/api/auth/cas/logout', follow_redirects=False)
    assert out.status_code == 302 and out.headers['location'] == '/?sso=off'
    assert db.query("SELECT REVOKED_AT FROM RISK_CAS_SESSION WHERE REVOKED_AT<>''")
    assert client.get('/?sso=off', follow_redirects=False).status_code == 200
