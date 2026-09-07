"""版本信息：全项目唯一来源，发版只需改这里 + 打同名 git tag。

版本号规则：语义化版本 MAJOR.MINOR.PATCH
- MAJOR：不兼容的结构性变更
- MINOR：新增功能、面板改动
- PATCH：核心脚本修复、问题修正
"""

PANEL_VERSION = '1.2.0'
PANEL_RELEASED = '2026-09-07'

REPO = 'tianjian518/mcloud-ai-bean'
DOCKER_IMAGE = 'tianjian518/mcloud-ai-bean'

RELEASE_URL = f'https://github.com/{REPO}/releases/latest'
COMMIT_URL = f'https://github.com/{REPO}/commits/main'

# 更新日志：面板会展示最近几条
CHANGELOG = [
    {
        'version': '1.2.0',
        'date': '2026-09-07',
        'items': [
            '修复领取云朵接口返回 405 的问题：该接口仅支持 POST，原先误用 GET 导致待领取云朵一直领不到',
            '新增版本号体系：面板显示版本、「关于 / 更新」页可一键检测新版本',
            '红包派对 404/418 给出明确区分提示，不再笼统报错',
            '抽奖失败时打印服务端返回的具体原因',
        ],
    },
    {
        'version': '1.1.0',
        'date': '2026-09-07',
        'items': [
            '修复 AI 相机任务因缺少样图无法完成的问题（内置样图）',
            '领取云朵失败时增加诊断、重试与余额差量核对',
            '红包派对登录更换 UA、补齐请求头并自动重试',
            '公众号任务接口空响应不再抛 NoneType 异常',
        ],
    },
    {
        'version': '1.0.0',
        'date': '2026-09-07',
        'items': [
            '首个版本：Web 面板、多账号、定时任务、8 种消息推送',
            '支持 amd64 / arm64 双架构镜像',
            '核心签到逻辑基于社区脚本 v5.1.3',
        ],
    },
]
