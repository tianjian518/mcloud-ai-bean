"""定时任务：基于 APScheduler 的 cron 调度。"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db, runner
from .config import TZ_NAME

scheduler = None
logger = logging.getLogger('mcloud.scheduler')


def normalize_cron(expr):
    """兼容 6 段（含秒）写法，统一转成 APScheduler 的 5 段表达式"""
    parts = (expr or '').split()
    if not parts:
        return None
    if len(parts) == 6:
        parts = parts[1:]
    if len(parts) != 5:
        return None
    return ' '.join(parts)


def describe_cron(expr):
    cron = normalize_cron(expr)
    if not cron:
        return '未设置'
    minute, hour, day, month, dow = cron.split()
    if all(p == '*' for p in (day, month, dow)):
        if hour == '*' and minute.startswith('*/'):
            return f'每 {minute[2:]} 分钟'
        if minute.startswith('*/'):
            return f'{hour} 时，每 {minute[2:]} 分钟'
        return f'每天 {hour}:{minute.zfill(2)}'
    return f'cron: {cron}'


def _job():
    from . import db as _db
    accounts = [a for a in _db.list_accounts() if a['enabled']]
    if not accounts:
        logger.info('定时任务触发，但没有启用的账号')
        return
    if runner.is_running():
        logger.info('上一轮任务仍在运行，本次跳过')
        return
    runner.start(accounts, trigger='cron')


def reload():
    """根据设置重建定时任务"""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(timezone=TZ_NAME)
        if not scheduler.running:
            scheduler.start()

    scheduler.remove_all_jobs()
    settings = db.all_settings()
    if settings.get('cron_enabled') != '1':
        return None

    cron = normalize_cron(settings.get('cron', ''))
    if not cron:
        logger.warning('cron 表达式无效: %s', settings.get('cron'))
        return None
    try:
        trigger = CronTrigger.from_crontab(cron, timezone=TZ_NAME)
        job = scheduler.add_job(_job, trigger, id='mcloud_task', replace_existing=True, max_instances=1)
        return job.next_run_time
    except Exception as e:
        logger.error('注册定时任务失败: %s', e)
        return None


def next_run():
    if scheduler is None:
        return None
    job = scheduler.get_job('mcloud_task')
    return job.next_run_time if job else None


def shutdown():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
