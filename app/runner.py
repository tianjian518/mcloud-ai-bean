"""任务执行器：后台线程串行跑账号，维护实时日志与运行状态。"""

import threading
import time
import traceback
from datetime import datetime

from . import db, notifier
from .config import NOTIFY_FIELDS
from .core import yunpan

MAX_LIVE_LINES = 3000

_state = {
    'running': False,
    'trigger': '',
    'started_at': '',
    'finished_at': '',
    'current': '',
    'progress': [0, 0],
    'lines': [],
    'results': [],
    'stop': False,
    'last_error': '',
}
_lock = threading.RLock()
_log_lock = threading.RLock()


def snapshot():
    with _lock, _log_lock:
        return {
            'running': _state['running'],
            'trigger': _state['trigger'],
            'started_at': _state['started_at'],
            'finished_at': _state['finished_at'],
            'current': _state['current'],
            'done': _state['progress'][0],
            'total': _state['progress'][1],
            'results': list(_state['results']),
            'last_error': _state['last_error'],
        }


def live_log():
    with _log_lock:
        return '\n'.join(_state['lines'])


def _emit(text):
    if text is None:
        return
    with _log_lock:
        for line in str(text).splitlines():
            _state['lines'].append(line)
        if len(_state['lines']) > MAX_LIVE_LINES:
            del _state['lines'][:len(_state['lines']) - MAX_LIVE_LINES]


def clear_log():
    with _log_lock:
        _state['lines'] = []


def request_stop():
    _state['stop'] = True


def _should_stop():
    return _state['stop']


def _run_job(accounts, trigger='manual'):
    started = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with _lock:
        _state['running'] = True
        _state['trigger'] = trigger
        _state['started_at'] = started
        _state['finished_at'] = ''
        _state['results'] = []
        _state['stop'] = False
        _state['last_error'] = ''
        _state['progress'] = [0, len(accounts)]
    clear_log()

    settings = db.all_settings()
    try:
        gap = (float(settings.get('gap_min') or 1), float(settings.get('gap_max') or 3))
    except ValueError:
        gap = (1, 3)

    _emit(f'=== 任务开始 {started}（触发方式: {trigger}）===')
    _emit(f'共 {len(accounts)} 个账号待执行')

    def on_line(text):
        _emit(text)

    def on_done(result):
        with _lock:
            _state['progress'][0] += 1
            _state['results'].append(result)
            _state['current'] = result.get('account', '')
        aid = result.pop('_account_id', None)
        db.add_run(aid, result, trigger=trigger)
        if aid:
            db.update_account(
                aid,
                last_run=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                last_ok=1 if result.get('ok') else 0,
                last_signin=1 if result.get('signin') else 0,
                cloud_total=int(result.get('cloud_total') or 0),
                cloud_received=int(result.get('cloud_received') or 0),
            )
        _emit(f"--- {result.get('account')} 完成：" +
              ('成功' if result.get('ok') else f"失败 {result.get('error', '')}") +
              f"，余额 {result.get('cloud_total')}，本次 +{result.get('cloud_received')} ---")

    results = []
    try:
        # 逐个执行，方便把库里的 account_id 与结果对应起来
        for index, acc in enumerate(accounts, start=1):
            if _should_stop():
                break
            _emit(f'\n======== ▷ 第 {index} 个账号 ◁ ========')
            res = yunpan.run_one(acc['cookie'], on_line=on_line)
            res['started_at'] = started
            results.append(res)
            on_done(dict(res, _account_id=acc['id']))
            if index < len(accounts) and not _should_stop():
                import random
                time.sleep(random.uniform(gap[0], gap[1]))
    except Exception as e:
        _state['last_error'] = f'{type(e).__name__}: {e}'
        _emit('任务异常: ' + traceback.format_exc())
    finally:
        finished = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with _lock:
            _state['running'] = False
            _state['finished_at'] = finished
            _state['current'] = ''
        _emit(f'=== 任务结束 {finished} ===')

        # 推送
        try:
            settings = db.all_settings()
            if settings.get('notify_enabled') == '1' and notifier.active_channels():
                failed = [r for r in results if not r.get('ok')]
                if settings.get('notify_on_failure_only') != '1' or failed:
                    summary = yunpan.build_summary(results)
                    notifier.send('移动云盘 AI 豆任务报告', summary)
                    _emit('已发送通知推送')
        except Exception as e:
            _emit(f'推送失败: {e}')


def start(accounts, trigger='manual'):
    """启动后台任务；已在运行则返回 False"""
    with _lock:
        if _state['running']:
            return False
        _state['running'] = True  # 抢占，避免并发启动
    t = threading.Thread(target=_run_job, args=(accounts, trigger), daemon=True)
    t.start()
    return True


def is_running():
    return _state['running']
