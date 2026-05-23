# NotifyMe

NotifyMe 是一个本地任务提醒工具。

它可以帮你运行或监控电脑上的任务，并在任务完成、失败或满足条件时，通过 Telegram Bot 给你发提醒。

适合这些场景：

- 跑 `python train.py`、数据处理脚本、批处理任务
- 等 AI 训练结束或 GPU 空闲
- 等文件下载完成或文件大小稳定
- 等日志里出现 `Done`、`Finished`、`Error` 等关键词
- 等本地服务端口打开
- 等接口健康检查返回正常

提醒内容可以包含：

- 任务名称
- 运行耗时
- 退出码
- 最后几行输出
- CPU / RAM / GPU 峰值
- 当前屏幕截图
- 历史记录

## 目录

- [功能特点](#功能特点)
- [安装依赖](#安装依赖)
- [创建 Telegram Bot](#创建-telegram-bot)
- [获取 Telegram Chat ID](#获取-telegram-chat-id)
- [配置 NotifyMe](#配置-notifyme)
- [启动 NotifyMe](#启动-notifyme)
- [第一次使用：设置工作目录](#第一次使用设置工作目录)
- [Telegram 使用方法](#telegram-使用方法)
- [本地命令行用法](#本地命令行用法)
- [运行数据和隐私保护](#运行数据和隐私保护)
- [常见问题](#常见问题)

## 功能特点

NotifyMe 支持两种使用方式：

1. Telegram 远程控制
   适合离开电脑后远程查看状态、截图、历史记录。

2. 本地命令行控制
   适合输入较长命令，例如训练脚本、构建命令、数据处理命令。

支持的监控类型：

| 类型 | 用途 |
| --- | --- |
| 命令 | 运行命令并在结束后提醒 |
| 进程 | 等某个进程结束 |
| 日志 | 等日志文件出现关键词 |
| 文件 | 等文件出现、消失或大小稳定 |
| 端口 | 等端口打开或关闭 |
| HTTP | 等网页或接口返回指定状态 |
| CPU | 等 CPU 持续空闲 |
| GPU | 等 GPU 持续空闲 |

## 安装依赖

建议使用 Python 3.10 或更高版本。

进入项目目录后执行：

```powershell
pip install -r requirements.txt
```

推荐使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 创建 Telegram Bot

NotifyMe 需要通过 Telegram Bot 给你发送提醒。

### 1. 打开 BotFather

在 Telegram 里搜索：

```text
@BotFather
```

打开后点击 Start。

### 2. 创建新机器人

给 BotFather 发送：

```text
/newbot
```

BotFather 会让你输入：

1. Bot 显示名称
   例如：

```text
NotifyMe Bot
```

2. Bot 用户名
   用户名必须以 `bot` 结尾，例如：

```text
my_notifyme_bot
```

创建成功后，BotFather 会给你一个 Bot Token。

它看起来是一长串字符，这就是后面要填入 `.env` 的：

```env
TELEGRAM_TOKEN
```

请注意：

- 不要把 Bot Token 发给别人。
- 不要把 Bot Token 写进 README。
- 不要把包含 Bot Token 的 `.env` 上传到 GitHub。

## 获取 Telegram Chat ID

NotifyMe 还需要知道消息发给哪个 Telegram 聊天窗口，这个值叫：

```env
TELEGRAM_CHAT_ID
```

### 1. 先给你的 Bot 发消息

打开你刚创建的 Bot，点击 Start，或者发送：

```text
hello
```

### 2. 打开 getUpdates 地址

在浏览器打开：

```text
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```

把 `<BOT_TOKEN>` 换成你的 Bot Token。

页面会显示一段 JSON。找到类似下面的位置：

```json
"chat": {
  "id": 123456789
}
```

这里的数字就是你的 `TELEGRAM_CHAT_ID`。

如果页面没有内容，通常是因为你还没有给 Bot 发过消息。先回 Telegram 给 Bot 发一句 `hello`，再刷新页面。

## 配置 NotifyMe

复制配置模板：

```powershell
copy .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```env
TELEGRAM_TOKEN=你的 Bot Token
TELEGRAM_CHAT_ID=你的 Chat ID

SCREENSHOT_QUALITY=75
SCREENSHOT_MAX_WIDTH=1920

CHECK_INTERVAL=3
CPU_THRESHOLD=15.0
CPU_IDLE_DURATION=30
GPU_THRESHOLD=10.0
GPU_IDLE_DURATION=30

VERIFY_SSL=true
UPDATES_TIMEOUT=30
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `TELEGRAM_TOKEN` | BotFather 给你的 Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Telegram Chat ID |
| `SCREENSHOT_QUALITY` | 截图 JPEG 质量 |
| `SCREENSHOT_MAX_WIDTH` | 截图最大宽度 |
| `CHECK_INTERVAL` | 监控轮询间隔，单位秒 |
| `CPU_THRESHOLD` | CPU 空闲判断阈值 |
| `CPU_IDLE_DURATION` | CPU 持续空闲多久后提醒 |
| `GPU_THRESHOLD` | GPU 空闲判断阈值 |
| `GPU_IDLE_DURATION` | GPU 持续空闲多久后提醒 |
| `VERIFY_SSL` | 是否校验 HTTPS 证书 |
| `UPDATES_TIMEOUT` | Telegram 长轮询超时时间 |

## 启动 NotifyMe

运行：

```powershell
python task_monitor.py
```

也可以：

```powershell
python -m notifyme
```

启动成功后，Telegram Bot 会给你发送启动消息，并显示快捷按钮菜单。

## 第一次使用：设置工作目录

这是最重要的一步。

NotifyMe 本身在一个目录里，但你的脚本通常在另一个项目目录里。

例如你的项目在：

```text
E:\projects\my-train
```

请先在 Telegram 里发送：

```text
工作目录 E:\projects\my-train
```

之后你发送：

```text
运行 python train.py
```

NotifyMe 就会在 `E:\projects\my-train` 里运行这个命令，而不是在 NotifyMe 自己的目录里运行。

如果只想临时指定一次目录，可以发送：

```text
在 E:\projects\my-train 运行 python train.py
```

## Telegram 使用方法

启动后可以直接点按钮：

```text
状态 / 截图 / 系统
历史 / 最后一次 / 帮助
工作目录 / 监控GPU / 监控CPU
```

也可以直接发送短句：

```text
运行 python train.py
监控进程 python
监控日志 train.log Done
监控文件 output.zip
监控端口 127.0.0.1 8000
监控网页 http://127.0.0.1:8000/health ok
停止 Training
任务 Training
历史
最后一次
```

常用示例：

### 运行训练脚本

```text
工作目录 E:\projects\my-train
运行 python train.py
```

### 等 GPU 空闲

```text
监控GPU
```

### 等文件下载完成

```text
监控文件 output.zip
```

### 等日志出现关键词

```text
监控日志 train.log Done
```

### 等服务端口打开

```text
监控端口 127.0.0.1 8000
```

### 等接口健康检查通过

```text
监控网页 http://127.0.0.1:8000/health ok
```

## 本地命令行用法

Telegram 适合远程控制，本地 CLI 更适合输入长命令。

设置默认工作目录：

```powershell
python -m notifyme.cli cwd E:\projects\my-train
```

运行命令：

```powershell
python -m notifyme.cli run python train.py --name Training
```

单次指定工作目录：

```powershell
python -m notifyme.cli run python train.py --cwd E:\projects\my-train --name Training
```

监控文件：

```powershell
python -m notifyme.cli file output.zip --mode stable --name Download
```

监控端口：

```powershell
python -m notifyme.cli port 127.0.0.1 8000 --mode open --name API
```

监控 HTTP：

```powershell
python -m notifyme.cli http http://127.0.0.1:8000/health --contains ok --name Health
```

查看历史：

```powershell
python -m notifyme.cli history -n 10
```

## 高级 Telegram 命令

如果需要更精确控制，可以使用 slash 命令：

```text
/help
/status
/history 10
/last
/task Training
/stats
/screenshot
/remove Training
```

添加监控：

```text
/run python train.py --name Training
/run --cwd E:\projects\my-train python train.py
/watch proc python --name Training
/watch log train.log Done --name TrainLog
/watch file output.zip mode=stable --name Download
/watch port 127.0.0.1 8000 mode=open --name API
/watch http http://127.0.0.1:8000/health contains=ok --name Health
/watch cpu --name CPUIdle threshold=15 duration=30
/watch gpu --name GPUIdle threshold=10 duration=30
```

## 运行数据和隐私保护

NotifyMe 会在本地生成运行数据：

```text
.env
task_monitor.log
errors.json
notifyme.db
task_monitor_offset.txt
```

这些文件都属于个人数据，不应该上传到 GitHub。

项目已经通过 `.gitignore` 忽略它们：

```text
.env
*.log
errors.json
notifyme.db
task_monitor_offset.txt
__pycache__/
```

上传 GitHub 前建议检查：

```powershell
git status --short --ignored
```

也可以扫描是否残留 token：

```powershell
rg "bot[0-9]+:|TELEGRAM_TOKEN=.+|api.telegram.org/bot[0-9]"
```

如果真实 Token 曾经出现在日志或 Git 历史中，建议去 BotFather 重新生成 Token。

## 常见问题

### 运行 `python train.py` 提示找不到文件

先设置工作目录：

```text
工作目录 E:\projects\my-train
```

再运行：

```text
运行 python train.py
```

### Telegram 没收到消息

请检查：

- `.env` 是否存在
- `TELEGRAM_TOKEN` 是否正确
- `TELEGRAM_CHAT_ID` 是否正确
- 是否先给 Bot 发过消息
- 网络是否能访问 Telegram

### getUpdates 页面没有内容

先给你的 Bot 发一条消息：

```text
hello
```

再刷新：

```text
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```

### 截图失败

常见原因：

- 当前环境没有桌面
- 远程服务器没有图形界面
- Linux 缺少截图工具

截图失败不会影响文字提醒。

### GPU 监控不可用

GPU 监控依赖 NVIDIA 环境和 `pynvml`。

如果没有 NVIDIA GPU，或者驱动环境不支持，GPU 监控会不可用，但其他功能仍然可以正常使用。

## 安全提醒

请务必记住：

- 不要上传 `.env`
- 不要上传日志、数据库、错误记录
- 不要把 Telegram Bot Token 发给别人
- 如果 Token 泄露，立刻去 BotFather 重置

仓库里应该只保留代码、依赖文件、`.env.example` 和 README。
