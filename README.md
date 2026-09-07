# ☁️ 移动云盘 AI 豆助手（原"云朵"）

全自动领取中国移动云盘 **AI 豆**（原云朵）的容器化方案：多账号、定时任务、Web 图形化面板、消息推送，一次部署长期挂机。

> 核心签到逻辑基于社区脚本 `移动云盘自动签到 v5.1.3`（作者：yaohuo & xiaohai），本仓库在其之上封装了持久化存储、调度器与 Web 面板。

---

## ✨ 功能

| 功能 | 说明 |
| --- | --- |
| 每日签到 | 自动签到、抽奖、摇一摇、戳一戳 |
| 云朵中心任务 | 上传 / 分享 / AI 相机 / 月任务补传等新版任务自动处理 |
| 红包派对 | 签到、浏览、云机使用、安装应用、趣味答题、余额领取 |
| Token 自愈 | Authorization 到期前 5 天自动刷新，deviceId 自动获取并缓存 |
| 多账号 | Web 面板增删，支持逐个启用 / 禁用 / 单独执行 |
| 定时执行 | Cron 表达式自定义，默认每天 8 / 16 / 20 点 |
| 图形化面板 | 概览看板、账号管理、实时日志、历史记录、系统设置 |
| 消息推送 | Bark、Server酱、Telegram、钉钉、飞书、企业微信、WxPusher、自定义 Webhook |
| 多架构 | `linux/amd64` + `linux/arm64`（x86 服务器 / 树莓派 / 香橙派 / Apple Silicon） |

---

## 🚀 快速开始

### Docker Compose（推荐）

```bash
mkdir -p ~/mcloud && cd ~/mcloud
curl -o docker-compose.yml https://raw.githubusercontent.com/tianjian518/mcloud-ai-bean/main/docker-compose.yml
docker compose up -d
```

浏览器打开 `http://<你的IP>:7860`，默认账号 `admin` / `admin`（**登录后请立刻修改**）。

### docker run

```bash
docker run -d \
  --name mcloud-ai-bean \
  --restart unless-stopped \
  -p 7860:7860 \
  -v $(pwd)/data:/data \
  -e TZ=Asia/Shanghai \
  -e MCLD_PANEL_PASS=你的面板密码 \
  tianjian518/mcloud-ai-bean:latest
```

### 本地源码运行

```bash
git clone https://github.com/tianjian518/mcloud-ai-bean.git
cd mcloud-ai-bean
pip install -r requirements.txt
MCLD_DATA_DIR=./data python -m app
```

---

## 🔑 获取账号凭据（Authorization）

1. 手机安装移动云盘 App，用中国移动号码登录；
2. 抓包（推荐 HttpCanary / 小黄鸟 / Stream），过滤 `authTokenRefresh.do`；
3. 复制请求头里的 **`Authorization`** 值（形如 `Basic xxxxxx...`）；
4. 在面板中按格式填入：

```
Authorization值#手机号
```

多个账号用 `&` 或换行分隔：

```
Basic YWJjZGVm...#13800138000
Basic ZmdoaWpr...#13900139000
```

> 也可以启动时通过环境变量 `MCLD_COOKIES` 预置账号，多个用 `&` 分隔。
>
> ⚠️ Authorization 有效期有限，脚本会在到期前 5 天自动刷新并把新 token 写入 `/data`，因此 **务必挂载 `/data` 目录**，否则刷新结果会随容器销毁丢失。

---

## 🖥 面板说明

| 页签 | 内容 |
| --- | --- |
| 概览 | 账号数、AI 豆总余额、今日已领取、今日执行次数、最近执行时间、运行进度与日志 |
| 账号管理 | 批量添加账号、备注、启停开关、单独执行、删除 |
| 实时日志 | 任务执行过程的逐行输出，2 秒自动刷新 |
| 历史记录 | 每次执行的账号、结果、签到状态、余额、本次获得、触发方式，可查看完整日志 |
| 系统设置 | Cron 定时、执行间隔、8 种推送渠道、面板账号密码 |

---

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MCLD_DATA_DIR` | `/data` | 数据与数据库目录（请挂载） |
| `MCLD_PORT` | `7860` | 面板端口 |
| `MCLD_PANEL_USER` | `admin` | 面板用户名（仅首次初始化） |
| `MCLD_PANEL_PASS` | `admin` | 面板密码（仅首次初始化） |
| `MCLD_CRON` | `0 8,16,20 * * *` | 默认定时表达式 |
| `MCLD_COOKIES` | 空 | 预置账号，`&` 分隔 |
| `TZ` | `Asia/Shanghai` | 时区 |

---

## 🔔 推送配置

在「系统设置」页打开对应渠道开关并填参数即可，支持同时启用多个：

- **Bark**：`url`（自建填 `https://xxx`，官方留空）+ `key`
- **Server酱 / PushPlus**：`sendkey`
- **Telegram**：`token`（BotFather 给的）+ `chat_id`
- **钉钉机器人**：`token` + `secret`（加签密钥，可空）
- **飞书机器人**：`token` + `secret`（可空）
- **企业微信机器人**：`key`
- **WxPusher**：`token`（appToken）+ `uid`
- **自定义 Webhook**：`url` + `method`（POST/GET），收到 `{"title":..., "content":..., "text":...}`

可勾选「仅在有账号失败时推送」，避免每天刷屏。

---

## 📦 镜像与构建

```bash
# 拉取（自动匹配架构）
docker pull tianjian518/mcloud-ai-bean:latest

# 手动多架构构建
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t tianjian518/mcloud-ai-bean:latest --push .
```

镜像 tag：`latest`、`v*`、短 SHA、日期（如 `20260907`）。

---

## 🗂 目录结构

```
.
├── app/
│   ├── main.py          # FastAPI 路由
│   ├── core/yunpan.py   # 签到核心逻辑（v5.1.3 + 面板适配层）
│   ├── db.py            # SQLite 存储
│   ├── runner.py        # 后台执行器 + 实时日志
│   ├── scheduler.py     # APScheduler 定时任务
│   ├── notifier.py      # 消息推送
│   └── static/          # 面板前端
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/docker.yml   # 多架构构建推送
```

---

## ❓ 常见问题

**Q：面板打不开？**
检查端口映射与防火墙；容器日志 `docker logs mcloud-ai-bean`。

**Q：账号一直显示"异常/未跑"？**
Authorization 已彻底过期且无法自动刷新，需重新抓包。刷新只在「即将过期」时有效，过期后无解。

**Q：AI 豆余额显示 0？**
任务执行到「领取」步骤才会更新余额，确认日志里有「当前云朵数量」行；首次添加账号后请手动执行一次。

**Q：多久跑一次合适？**
默认每天 8 / 16 / 20 点三次已足够，跑太频繁没有额外收益，反而可能被风控。

---

## ⚠️ 免责声明

本项目仅供学习交流使用，请勿用于商业用途。使用时请遵守中国移动云盘的用户协议，因使用本项目产生的任何后果由使用者自行承担。请在下载后 24 小时内删除。

## 📄 License

MIT
