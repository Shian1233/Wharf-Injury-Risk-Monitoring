"""金智 IDS6.0 统一身份认证平台（CAS）接入协议。

只实现 IDS6.0 集成手册覆盖的 CAS 子集：登录跳转、服务票据校验
（CAS 2.0 ``serviceValidate``）、单点登出跳转，以及 CAS 反向推送的
``logoutRequest`` 通知。协议本身不落库，会话状态由 :mod:`app.auth` 维护。

票据等同于口令：本模块的任何异常消息都不得包含票据内容。校验请求的
目标地址只能来自 :data:`SERVER_PATTERN` 允许的配置项，绝不采纳请求参数。
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from defusedxml.ElementTree import fromstring as parse_xml

ORIGIN_PATTERN = re.compile(r'^https?://[^\s/?#]+$')
URL_PATTERN = re.compile(r'^https?://[^\s?#]+$')
PATH_PATTERN = re.compile(r'^[A-Za-z0-9_./-]{1,80}$')
# 可打印 ASCII、不含空白：覆盖 CAS 实际签发的 ST/PGT 票据，同时挡住控制字符。
TICKET_PATTERN = re.compile(r'^[\x21-\x7e]{1,512}$')
DEFAULT_CALLBACK = '/api/auth/cas/callback'
_ATTRIBUTE_SKIP = {'user', 'proxygrantingticket', 'proxies', 'attributes'}


class CasError(RuntimeError):
    """CAS 配置或协议错误。消息中不得包含票据内容。"""


@dataclass(frozen=True)
class CasAssertion:
    """一次成功的票据校验结果。``attributes`` 的键统一为小写。"""
    user: str
    attributes: dict
    raw: str = ''


def _env(name, default=''):
    return str(os.getenv(name, default) or '').strip()


def base_path():
    return _env('PUBLIC_BASE_PATH').rstrip('/')


def _endpoint(suffix_env, default_suffix):
    suffix = _env(suffix_env, default_suffix).strip('/')
    if not PATH_PATTERN.match(suffix) or '..' in suffix:
        raise CasError(f'{suffix_env} 不是合法的相对路径')
    return f'{server_prefix()}/{suffix}'


def server_prefix():
    prefix = _env('CAS_SERVER_URL_PREFIX').rstrip('/')
    if not prefix:
        raise CasError('CAS_SERVER_URL_PREFIX 未配置')
    if not URL_PATTERN.match(prefix):
        raise CasError('CAS_SERVER_URL_PREFIX 必须以 http:// 或 https:// 开头')
    return prefix


def _timeout():
    value = _env('CAS_TIMEOUT', '8')
    try:
        seconds = float(value)
    except ValueError:
        raise CasError('CAS_TIMEOUT 必须是秒数') from None
    return max(1.0, min(seconds, 60.0))


def _verify_ssl():
    return _env('CAS_VERIFY_SSL', 'true').lower() not in {'false', '0', 'no'}


def _client():
    """校验票据用的 HTTP 客户端。不跟随跳转，避免票据被转发到第三方。"""
    return httpx.Client(timeout=_timeout(), verify=_verify_ssl(), follow_redirects=False)


def _registered_hosts():
    return [h.strip().lower() for h in _env('CAS_SERVICE_HOSTS').split(',') if h.strip()]


def origin(request):
    """本应用对外的 ``协议://主机``。优先显式配置，其次校验代理头。"""
    configured = _env('CAS_SERVICE_ORIGIN').rstrip('/')
    if configured:
        if not ORIGIN_PATTERN.match(configured):
            raise CasError('CAS_SERVICE_ORIGIN 必须是不含路径的 http:// 或 https:// 地址')
        return configured
    hosts = _registered_hosts()
    host = (request.headers.get('host') or request.url.netloc or '').strip()
    forwarded = (request.headers.get('x-forwarded-host') or '').split(',')[0].strip()
    if forwarded:
        if forwarded.lower() not in hosts:
            raise CasError('X-Forwarded-Host 未在 CAS_SERVICE_HOSTS 中登记')
        host = forwarded
    if not host:
        raise CasError('无法确定本应用对外地址，请配置 CAS_SERVICE_ORIGIN')
    if hosts and host.lower() not in hosts:
        raise CasError('当前 Host 未在 CAS_SERVICE_HOSTS 中登记')
    scheme = (request.headers.get('x-forwarded-proto') or '').split(',')[0].strip().lower()
    if scheme not in {'http', 'https'}:
        scheme = request.url.scheme
    if scheme not in {'http', 'https'}:
        scheme = 'https'
    return f'{scheme}://{host}'


def service_url(request):
    """CAS 回调地址，也就是注册到 IDS 管控台的 ``service``。"""
    configured = _env('CAS_SERVICE_URL')
    if configured:
        if not URL_PATTERN.match(configured):
            raise CasError('CAS_SERVICE_URL 必须以 http:// 或 https:// 开头')
        return configured
    return f'{origin(request)}{base_path()}{DEFAULT_CALLBACK}'


def home_url(request):
    return _env('CAS_LOGOUT_SERVICE') or f'{origin(request)}{base_path()}/'


def safe_next(value):
    """校验登录后的回跳地址，只允许本应用范围内的站内路径。"""
    default = f'{base_path()}/' if base_path() else '/'
    value = str(value or '').strip()
    if not value:
        return default
    if not value.startswith('/') or value.startswith('//') or '\\' in value or '\r' in value or '\n' in value:
        raise CasError('回跳地址无效')
    prefix = base_path()
    if prefix and not (value == prefix or value.startswith(prefix + '/')):
        raise CasError('回跳地址不在本应用范围内')
    allowed = [a.strip() for a in _env('CAS_NEXT_ALLOWLIST').split(',') if a.strip()]
    if allowed and not any(value == a or value.startswith(a.rstrip('/') + '/') for a in allowed):
        raise CasError('回跳地址不在允许列表中')
    return value


def login_redirect_url(service, renew=False, gateway=False):
    if renew and gateway:
        raise CasError('renew 与 gateway 不能同时启用')
    params = {'service': service}
    if renew:
        params['renew'] = 'true'
    if gateway:
        params['gateway'] = 'true'
    return f'{_endpoint("CAS_LOGIN_SUFFIX", "login")}?{urlencode(params)}'


def logout_redirect_url(service):
    return f'{_endpoint("CAS_LOGOUT_SUFFIX", "logout")}?{urlencode({"service": service})}'


def validate_ticket(ticket, service):
    """校验服务票据。成功返回 :class:`CasAssertion`，失败抛出 :class:`CasError`。"""
    if not ticket or not TICKET_PATTERN.match(ticket):
        raise CasError('服务票据格式无效')
    query = urlencode({'service': service, 'ticket': ticket})
    url = f'{_endpoint("CAS_VALIDATE_SUFFIX", "serviceValidate")}?{query}'
    try:
        with _client() as client:
            response = client.get(url, headers={'Accept': 'application/xml,text/xml,*/*'})
    except httpx.HTTPError as error:
        raise CasError(f'无法连接统一身份认证平台（{type(error).__name__}）') from None
    if response.status_code != 200:
        raise CasError(f'统一身份认证平台返回 HTTP {response.status_code}')
    return parse_service_response(decode(response.content))


def decode(content):
    encoding = _env('CAS_ENCODING', 'utf-8') or 'utf-8'
    return content.decode(encoding, errors='replace')


def parse_service_response(text):
    root = _parse(text)
    if root is None or _local(root.tag) != 'serviceResponse':
        raise CasError('统一身份认证平台返回内容不是合法的 serviceResponse')
    success = _child(root, 'authenticationSuccess')
    if success is None:
        failure = _child(root, 'authenticationFailure')
        code = (failure.get('code') if failure is not None else '') or 'UNKNOWN'
        raise CasError(f'票据校验未通过（{code}）')
    user = _child(success, 'user')
    return CasAssertion(user=((user.text or '').strip() if user is not None else ''),
        attributes=_attributes(success), raw=text)


def logout_ticket(form):
    """从 CAS 反向登出通知中取出 ``SessionIndex``，即当初的服务票据。"""
    raw = form.get('logoutRequest') if hasattr(form, 'get') else None
    if not isinstance(raw, str) or not raw or len(raw) > 8192:
        return ''
    root = _parse(raw)
    if root is None or _local(root.tag) != 'LogoutRequest':
        return ''
    for element in root.iter():
        if _local(element.tag) == 'SessionIndex':
            value = (element.text or '').strip()
            if value and TICKET_PATTERN.match(value):
                return value
    return ''


def subject(assertion):
    """用户唯一标识。默认取 ``<cas:user>``，可用 CAS_ATTR_ID 指定其他属性。"""
    return claim(assertion, 'CAS_ATTR_ID', 'user') or assertion.user


def display_name(assertion):
    return claim(assertion, 'CAS_ATTR_NAME', 'cn')


def claim(assertion, env_name, default=''):
    """按属性名取第一个值；``user``/``uid`` 等保留名表示 CAS 登录名。"""
    key = (_env(env_name, default) or default).lower()
    if key in {'', 'user', 'uid'}:
        return assertion.user
    values = assertion.attributes.get(key) or []
    return values[0] if values else ''


def _attributes(success):
    """读取用户属性。IDS 用元素名作属性名，同名元素表示多值。"""
    holder = _child(success, 'attributes')
    result = {}
    for element in (holder if holder is not None else success):
        if not isinstance(element.tag, str):
            continue
        key = _local(element.tag).lower()
        if key in _ATTRIBUTE_SKIP:
            continue
        result.setdefault(key, []).append((element.text or '').strip())
    return result


def _parse(text):
    if not isinstance(text, str) or not text or len(text) > 1_000_000:
        return None
    try:
        return parse_xml(text)
    except Exception:
        return None


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _child(element, name):
    for child in element:
        if _local(child.tag) == name:
            return child
    return None
