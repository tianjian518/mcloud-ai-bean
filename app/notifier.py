"""通知推送：Bark / Server酱 / Telegram / 钉钉 / 飞书 / 企业微信 / WxPusher / 自定义 Webhook。"""

import hashlib
import hmac
import base64
import time
import urllib.parse

import requests

from . import db


def _settings():
    return db.all_settings()


def _cfg(s, name, field):
    return (s.get(f'notify_{name}_{field}') or '').strip()


def _post(url, json_data=None, data=None, headers=None, timeout=15):
    return requests.post(url, json=json_data, data=data, headers=headers, timeout=timeout)


def _bark(s, title, content):
    url = _cfg(s, 'bark', 'url').rstrip('/')
    key = _cfg(s, 'bark', 'key')
    if not url and key:
        url = 'https://api.day.app'
    if not url or not key:
        return False, 'Bark 配置不完整'
    r = _post(f'{url}/{key}', json_data={
        'title': title, 'body': content, 'group': '移动云盘', 'isArchive': 1})
    return r.status_code == 200, f'Bark: {r.status_code}'


def _serverchan(s, title, content):
    key = _cfg(s, 'serverchan', 'sendkey')
    if not key:
        return False, 'Server酱 配置不完整'
    # sctp 开头的 key 需要带服务器号，例如 sctp1234tXXXX
    if key.startswith('sctp') and 't' in key[4:]:
        server_no = key[4:].split('t')[0]
        url = f'https://{server_no}.push.ft07.com/send/{key}.send'
    else:
        url = f'https://sctapi.ftqq.com/{key}.send'
    r = requests.post(url, data={'title': title, 'desp': content}, timeout=15)
    return r.status_code == 200, f'Server酱: {r.status_code}'


def _telegram(s, title, content):
    token = _cfg(s, 'telegram', 'token')
    chat = _cfg(s, 'telegram', 'chat_id')
    if not token or not chat:
        return False, 'Telegram 配置不完整'
    r = _post(f'https://api.telegram.org/bot{token}/sendMessage',
              json_data={'chat_id': chat, 'text': f'{title}\n\n{content}',
                         'disable_web_page_preview': True})
    return r.status_code == 200, f'Telegram: {r.status_code}'


def _dingtalk(s, title, content):
    token = _cfg(s, 'dingtalk', 'token')
    secret = _cfg(s, 'dingtalk', 'secret')
    if not token:
        return False, '钉钉 配置不完整'
    url = f'https://oapi.dingtalk.com/robot/send?access_token={token}'
    if secret:
        ts = str(round(time.time() * 1000))
        sign = urllib.parse.quote_plus(
            base64.b64encode(hmac.new(secret.encode(), f'{ts}\n{secret}'.encode(), hashlib.sha256).digest()))
        url += f'&timestamp={ts}&sign={sign}'
    r = _post(url, json_data={'msgtype': 'text', 'text': {'content': f'{title}\n\n{content}'}})
    ok = r.json().get('errcode') == 0
    return ok, f"钉钉: {r.json().get('errmsg', r.status_code)}"


def _feishu(s, title, content):
    token = _cfg(s, 'feishu', 'token')
    secret = _cfg(s, 'feishu', 'secret')
    if not token:
        return False, '飞书 配置不完整'
    payload = {'msg_type': 'text', 'content': {'text': f'{title}\n\n{content}'}}
    if secret:
        ts = str(int(time.time()))
        digest = hmac.new(f'{ts}\n{secret}'.encode(), b'', hashlib.sha256).digest()
        payload['timestamp'] = ts
        payload['sign'] = base64.b64encode(digest).decode()
    r = _post(f'https://open.feishu.cn/open-apis/bot/v2/hook/{token}', json_data=payload)
    return r.status_code == 200, f'飞书: {r.status_code}'


def _wecom(s, title, content):
    key = _cfg(s, 'wecom', 'key')
    if not key:
        return False, '企业微信 配置不完整'
    r = _post(f'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}',
              json_data={'msgtype': 'text', 'text': {'content': f'{title}\n\n{content}'}})
    try:
        ok = r.json().get('errcode') == 0
        return ok, f"企业微信: {r.json().get('errmsg', '')}"
    except Exception:
        return False, f'企业微信: {r.status_code}'


def _wxpusher(s, title, content):
    token = _cfg(s, 'wxpusher', 'token')
    uid = _cfg(s, 'wxpusher', 'uid')
    if not token or not uid:
        return False, 'WxPusher 配置不完整'
    r = _post('https://wxpusher.zjiecode.com/api/send/message', json_data={
        'appToken': token,
        'content': f'<h3>{title}</h3><pre>{content}</pre>',
        'contentType': 2,
        'uids': [uid],
    })
    try:
        ok = r.json().get('success') is True
        return ok, f"WxPusher: {r.json().get('msg', '')}"
    except Exception:
        return False, f'WxPusher: {r.status_code}'


def _webhook(s, title, content):
    url = _cfg(s, 'webhook', 'url')
    method = (_cfg(s, 'webhook', 'method') or 'POST').upper()
    if not url:
        return False, 'Webhook 配置不完整'
    payload = {'title': title, 'content': content, 'text': f'{title}\n\n{content}'}
    if method == 'GET':
        r = requests.get(url, params=payload, timeout=15)
    else:
        r = _post(url, json_data=payload)
    return r.status_code < 400, f'Webhook: {r.status_code}'


_HANDLERS = {
    'bark': _bark,
    'serverchan': _serverchan,
    'telegram': _telegram,
    'dingtalk': _dingtalk,
    'feishu': _feishu,
    'wecom': _wecom,
    'wxpusher': _wxpusher,
    'webhook': _webhook,
}


def send(title, content):
    """向所有已启用的渠道推送，返回 [(渠道, 是否成功, 说明)]"""
    s = _settings()
    if s.get('notify_enabled') != '1':
        return [('全局开关', False, '通知总开关未开启')]
    results = []
    for name, handler in _HANDLERS.items():
        if s.get(f'notify_{name}_enabled') != '1':
            continue
        try:
            ok, msg = handler(s, title, content)
            results.append((name, bool(ok), msg))
        except Exception as e:
            results.append((name, False, f'{type(e).__name__}: {e}'))
    return results


def active_channels():
    s = _settings()
    return [n for n in _HANDLERS if s.get(f'notify_{n}_enabled') == '1']
