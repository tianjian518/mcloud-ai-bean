"""移动云盘 AI 豆自动化 —— Web 面板服务。"""

import os
import secrets
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, notifier, runner, scheduler
from .config import NOTIFY_FIELDS, WEB_HOST, WEB_PORT
from .core import yunpan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = FastAPI(title='移动云盘 AI 豆助手', version='1.0.0')

# 会话令牌（进程内保存，重启后需重新登录）
_sessions = set()
_boot = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _authorized(request: Request) -> bool:
    token = request.cookies.get('mc_token')
    return bool(token) and token in _sessions


def _need_auth():
    return JSONResponse({'ok': False, 'msg': '未登录或登录已过期'}, status_code=401)


# ---------------------------------------------------------------- 静态页面

@app.get('/', response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))


app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


# ---------------------------------------------------------------- 鉴权

@app.post('/api/login')
async def login(request: Request):
    data = await request.json()
    settings = db.all_settings()
    if data.get('username') == settings.get('panel_user') and data.get('password') == settings.get('panel_pass'):
        token = secrets.token_hex(24)
        _sessions.add(token)
        resp = JSONResponse({'ok': True})
        resp.set_cookie('mc_token', token, httponly=True, samesite='lax', max_age=7 * 86400)
        return resp
    return JSONResponse({'ok': False, 'msg': '用户名或密码错误'}, status_code=401)


@app.post('/api/logout')
async def logout(request: Request):
    _sessions.discard(request.cookies.get('mc_token', ''))
    return {'ok': True}


# ---------------------------------------------------------------- 状态

@app.get('/api/state')
async def state(request: Request):
    if not _authorized(request):
        return _need_auth()
    settings = db.all_settings()
    next_run = scheduler.next_run()
    return {
        'ok': True,
        'version': '1.0.0',
        'core_version': yunpan.SCRIPT_VERSION,
        'boot_time': _boot,
        'stats': db.stats(),
        'accounts': db.list_accounts(),
        'runs': db.list_runs(limit=30),
        'running': runner.snapshot(),
        'cron': settings.get('cron', ''),
        'cron_enabled': settings.get('cron_enabled') == '1',
        'cron_desc': scheduler.describe_cron(settings.get('cron', '')),
        'next_run': next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else '',
        'notify_channels': notifier.active_channels(),
    }


@app.get('/api/logs')
async def logs(request: Request, limit: int = 200, account_id: int = 0):
    if not _authorized(request):
        return _need_auth()
    return {'ok': True, 'items': db.list_runs(account_id=account_id or None, limit=limit)}


@app.get('/api/log/{run_id}')
async def log_detail(run_id: int, request: Request):
    if not _authorized(request):
        return _need_auth()
    row = db.get_run(run_id)
    if not row:
        return JSONResponse({'ok': False, 'msg': '记录不存在'}, status_code=404)
    return {'ok': True, 'item': row}


# ---------------------------------------------------------------- 账号

@app.post('/api/accounts')
async def add_accounts(request: Request):
    if not _authorized(request):
        return _need_auth()
    data = await request.json()
    raw = (data.get('cookie') or '').strip()
    if not raw:
        return JSONResponse({'ok': False, 'msg': '内容为空'}, status_code=400)
    items = yunpan.split_cookies(raw)
    added, skipped = 0, 0
    existing = {a['cookie'] for a in db.list_accounts()}
    for item in items:
        if '#' not in item:
            skipped += 1
            continue
        if item in existing:
            skipped += 1
            continue
        db.add_account(item, phone=yunpan.parse_account_label(item))
        existing.add(item)
        added += 1
    return {'ok': True, 'added': added, 'skipped': skipped}


@app.delete('/api/accounts/{aid}')
async def del_account(aid: int, request: Request):
    if not _authorized(request):
        return _need_auth()
    db.delete_account(aid)
    return {'ok': True}


@app.post('/api/accounts/{aid}/toggle')
async def toggle_account(aid: int, request: Request):
    if not _authorized(request):
        return _need_auth()
    acc = db.get_account(aid)
    if not acc:
        return JSONResponse({'ok': False, 'msg': '账号不存在'}, status_code=404)
    db.update_account(aid, enabled=0 if acc['enabled'] else 1)
    return {'ok': True, 'enabled': 0 if acc['enabled'] else 1}


@app.put('/api/accounts/{aid}')
async def edit_account(aid: int, request: Request):
    if not _authorized(request):
        return _need_auth()
    acc = db.get_account(aid)
    if not acc:
        return JSONResponse({'ok': False, 'msg': '账号不存在'}, status_code=404)
    data = await request.json()
    fields = {}
    if 'cookie' in data and data['cookie'].strip():
        fields['cookie'] = data['cookie'].strip()
        fields['phone'] = yunpan.parse_account_label(data['cookie'].strip())
    if 'remark' in data:
        fields['remark'] = data['remark']
    db.update_account(aid, **fields)
    return {'ok': True}


# ---------------------------------------------------------------- 任务

@app.post('/api/run')
async def run_task(request: Request):
    if not _authorized(request):
        return _need_auth()
    data = await request.json() or {}
    aids = data.get('ids') or []
    accounts = [a for a in db.list_accounts() if a['enabled']]
    if aids:
        accounts = [a for a in accounts if a['id'] in set(aids)]
    if not accounts:
        return JSONResponse({'ok': False, 'msg': '没有可执行的账号'}, status_code=400)
    if not runner.start(accounts, trigger='manual'):
        return JSONResponse({'ok': False, 'msg': '已有任务正在运行'}, status_code=409)
    return {'ok': True, 'count': len(accounts)}


@app.post('/api/run/stop')
async def stop_task(request: Request):
    if not _authorized(request):
        return _need_auth()
    runner.request_stop()
    return {'ok': True}


@app.get('/api/run/live')
async def run_live(request: Request):
    if not _authorized(request):
        return _need_auth()
    snap = runner.snapshot()
    snap['log'] = runner.live_log()
    return {'ok': True, 'state': snap}


@app.delete('/api/run/live')
async def clear_live(request: Request):
    if not _authorized(request):
        return _need_auth()
    runner.clear_log()
    return {'ok': True}


# ---------------------------------------------------------------- 设置

@app.get('/api/settings')
async def get_settings(request: Request):
    if not _authorized(request):
        return _need_auth()
    s = db.all_settings()
    s.pop('panel_pass', None)
    return {'ok': True, 'settings': s, 'fields': NOTIFY_FIELDS}


@app.post('/api/settings')
async def save_settings(request: Request):
    if not _authorized(request):
        return _need_auth()
    data = await request.json() or {}
    allowed = {'cron', 'cron_enabled', 'gap_min', 'gap_max', 'notify_enabled', 'notify_on_failure_only',
               'panel_user', 'panel_pass'}
    for name, _label, fields in NOTIFY_FIELDS:
        allowed.add(f'notify_{name}_enabled')
        for f in fields:
            allowed.add(f'notify_{name}_{f}')
    pairs = {k: v for k, v in data.items() if k in allowed}
    for k in ('cron_enabled', 'notify_enabled', 'notify_on_failure_only'):
        if k in pairs:
            pairs[k] = '1' if str(pairs[k]) in ('1', 'true', True) else '0'
    db.set_settings(pairs)
    scheduler.reload()
    return {'ok': True, 'next_run': _next_run_str()}


def _next_run_str():
    nxt = scheduler.next_run()
    return nxt.strftime('%Y-%m-%d %H:%M:%S') if nxt else ''


@app.post('/api/notify/test')
async def notify_test(request: Request):
    if not _authorized(request):
        return _need_auth()
    results = notifier.send('移动云盘 AI 豆 - 测试通知',
                            '这是一条来自面板的测试消息，收到说明推送配置正常。')
    return {'ok': True, 'results': [{'channel': c, 'ok': o, 'msg': m} for c, o, m in results]}


@app.get('/api/version')
async def version():
    """无需登录：返回最新版本信息（供面板检查更新）"""
    return {'ok': True, 'version': '1.0.0', 'core': yunpan.SCRIPT_VERSION}


# ---------------------------------------------------------------- 启动

@app.on_event('startup')
async def on_startup():
    db.init_db()
    # 环境变量里的账号（MCLD_COOKIES，多个用 & 或换行分隔）自动入库
    env_cookies = os.environ.get('MCLD_COOKIES') or os.environ.get('yunpan') or ''
    if env_cookies.strip():
        existing = {a['cookie'] for a in db.list_accounts()}
        for item in yunpan.split_cookies(env_cookies):
            if '#' in item and item not in existing:
                db.add_account(item, phone=yunpan.parse_account_label(item))
                existing.add(item)
    scheduler.reload()


def serve():
    import uvicorn
    uvicorn.run('app.main:app', host=WEB_HOST, port=WEB_PORT, log_level='info')
