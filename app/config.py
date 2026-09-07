"""全局配置：所有持久化设置都存在 SQLite 的 settings 表里，环境变量只提供初始值。"""

import os

# 数据目录（容器里挂载到 /data）
DATA_DIR = os.environ.get('MCLD_DATA_DIR') or '/data'
os.environ.setdefault('MCLD_DATA_DIR', DATA_DIR)

WEB_PORT = int(os.environ.get('MCLD_PORT') or os.environ.get('PORT') or '7860')
WEB_HOST = os.environ.get('MCLD_HOST', '0.0.0.0')
TZ_NAME = os.environ.get('TZ', 'Asia/Shanghai')

# 面板账号，环境变量仅作为首次初始化种子
DEFAULT_PANEL_USER = os.environ.get('MCLD_PANEL_USER', 'admin')
DEFAULT_PANEL_PASS = os.environ.get('MCLD_PANEL_PASS', 'admin')

# 默认定时：每天 8/16/20 点
DEFAULT_CRON = os.environ.get('MCLD_CRON', '0 8,16,20 * * *')
DEFAULT_CRON_ENABLED = (os.environ.get('MCLD_CRON_ENABLED', '1') == '1')

# 账号执行间隔（秒）
DEFAULT_GAP = [1, 3]

# 通知开关：只有 enabled=1 的渠道才会发
NOTIFY_FIELDS = [
    ('bark', 'Bark', ['url', 'key']),
    ('serverchan', 'Server酱 / PushPlus', ['sendkey']),
    ('telegram', 'Telegram', ['token', 'chat_id']),
    ('dingtalk', '钉钉机器人', ['token', 'secret']),
    ('feishu', '飞书机器人', ['token', 'secret']),
    ('wecom', '企业微信机器人', ['key']),
    ('wxpusher', 'WxPusher', ['token', 'uid']),
    ('webhook', '自定义 Webhook', ['url', 'method']),
]

DEFAULT_SETTINGS = {
    'cron': DEFAULT_CRON,
    'cron_enabled': '1' if DEFAULT_CRON_ENABLED else '0',
    'gap_min': str(DEFAULT_GAP[0]),
    'gap_max': str(DEFAULT_GAP[1]),
    'notify_enabled': '1',
    'notify_on_failure_only': '0',
    'panel_user': DEFAULT_PANEL_USER,
    'panel_pass': DEFAULT_PANEL_PASS,
}

for _name, _label, _fields in NOTIFY_FIELDS:
    DEFAULT_SETTINGS[f'notify_{_name}_enabled'] = '0'
    for _f in _fields:
        DEFAULT_SETTINGS[f'notify_{_name}_{_f}'] = ''
