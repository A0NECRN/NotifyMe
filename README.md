# NotifyMe

NotifyMe 是一个本地任务提醒工具。

你可以让它帮你运行或监控电脑上的任务，例如：

- 跑 `python train.py`
- 等 GPU 空闲
- 等某个文件下载完成
- 等日志里出现 `Done`
- 等本地服务端口打开
- 等网页接口返回正常

任务完成后，NotifyMe 会通过 Telegram Bot 给你发消息，还可以附带截图、耗时、退出码、最后输出、CPU/RAM/GPU 峰值等信息。

项目地址：

[https://github.com/A0NECRN/NotifyMe](https://github.com/A0NECRN/NotifyMe)

## 1. 准备环境

需要：

- Windows / macOS / Linux
- Python 3.10 或更高版本
- 一个 Telegram 账号

安装依赖：

```powershell
pip install -r requirements.txt
```

如果你使用虚拟环境，可以这样：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux 激活虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 创建 Telegram Bot

NotifyMe 通过 Telegram Bot 给你发消息，所以你需要先创建一个 bot。

### 第 1 步：打开 BotFather

在 Telegram 搜索：

```text
@BotFather
```

注意：认准 Telegram 官方的 BotFather。

### 第 2 步：创建新 Bot

给 BotFather 发送：

```text
/newbot
```

它会让你输入两个东西：

1. Bot 显示名称，例如：

```text
My NotifyMe Bot
```

2. Bot 用户名，必须以 `bot` 结尾，例如：

```text
my_notifyme_123_bot
```

创建成功后，BotFather 会给你一串 token，格式大概是：

```text
<一长串由 BotFather 生成的 token>
```

这就是你的：

```env
TELEGRAM_TOKEN
```

不要把这个 token 发给别人，也不要上传到 GitHub。

## 3. 获取 Telegram Chat ID

NotifyMe 还需要知道“消息发给谁”，这就是 `TELEGRAM_CHAT_ID`。

### 第 1 步：先给你的 Bot 发一句话

打开刚创建的 bot，点击 Start，或者发送：

```text
hello
```

### 第 2 步：在浏览器打开下面的网址

把 `<你的BOT_TOKEN>` 换成 BotFather 给你的 token：

```text
https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates
```

例如：

```text
https://api.telegram.org/bot你的BOT_TOKEN/getUpdates
```

页面里会出现一段 JSON，找到类似下面的位置：

```json
"chat":{"id":123456789,...}
```

里面的数字就是：

```env
TELEGRAM_CHAT_ID
```

如果页面里没有内容，通常是因为你还没有先给 bot 发消息。回 Telegram 给 bot 发一句 `hello`，再刷新网页。

## 4. 配置 NotifyMe

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
TELEGRAM_TOKEN=你的bot token
TELEGRAM_CHAT_ID=你的chat id

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

重要提醒：

- `.env` 是你的私人配置文件。
- 不要上传 `.env` 到 GitHub。
- 仓库里只保留 `.env.example`。

本项目已经在 `.gitignore` 里忽略了 `.env`、日志、数据库和缓存文件。

## 5. 启动 NotifyMe

在项目目录运行：

```powershell
python task_monitor.py
```

也可以：

```powershell
python -m notifyme
```

启动成功后，你的 Telegram Bot 会收到启动消息，并出现按钮菜单。

## 6. 第一次使用：先设置工作目录

这是最重要的一步。

NotifyMe 安装在自己的目录里，但你的任务通常在别的项目目录里。

例如你的训练项目在：

```text
E:\projects\my-train
```

你应该先在 Telegram 里发送：

```text
工作目录 E:\projects\my-train
```

以后你再发送：

```text
运行 python train.py
```

它就会在 `E:\projects\my-train` 里运行，而不是在 NotifyMe 目录里运行。

如果你只想临时指定一次目录，也可以发送：

```text
在 E:\projects\my-train 运行 python train.py
```

## 7. Telegram 常用操作

启动后，Telegram 里会有按钮菜单。

你可以直接点：

```text
状态 / 截图 / 系统
历史 / 最后一次 / 帮助
工作目录 / 监控GPU / 监控CPU
```

也可以直接发短句：

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

## 8. 常见场景示例

### 场景 1：运行训练脚本

```text
工作目录 E:\projects\my-train
运行 python train.py
```

完成后会收到 Telegram 提醒。

### 场景 2：等 GPU 空闲

```text
监控GPU
```

默认规则来自 `.env`：

```env
GPU_THRESHOLD=10.0
GPU_IDLE_DURATION=30
```

意思是：GPU 使用率低于 10%，持续 30 秒，就提醒你。

### 场景 3：等文件下载完成

```text
监控文件 output.zip
```

如果你设置过工作目录，相对路径 `output.zip` 会按工作目录查找。

### 场景 4：等日志出现关键词

```text
监控日志 train.log Done
```

当 `train.log` 里出现 `Done`，NotifyMe 会提醒你。

### 场景 5：等本地服务启动

```text
监控端口 127.0.0.1 8000
```

端口打开后提醒你。

### 场景 6：等接口健康检查通过

```text
监控网页 http://127.0.0.1:8000/health ok
```

当网页内容包含 `ok` 时提醒你。

## 9. 本地命令行用法

Telegram 适合远程控制，本地 CLI 适合输入长命令。

设置工作目录：

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

查看历史：

```powershell
python -m notifyme.cli history -n 10
```

## 10. 高级 Telegram 命令

如果你想更精确控制，也可以使用 slash 命令：

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

## 11. 运行数据保存在哪里

NotifyMe 会生成一些本地运行文件：

```text
.env
task_monitor.log
errors.json
notifyme.db
task_monitor_offset.txt
```

这些都是本地私人文件，不应该上传 GitHub。

它们已经被 `.gitignore` 忽略。

说明：

- `.env`：你的 Telegram token 和 chat id
- `task_monitor.log`：运行日志
- `errors.json`：错误记录
- `notifyme.db`：任务历史和默认工作目录
- `task_monitor_offset.txt`：Telegram 消息偏移量

## 12. 上传 GitHub 前请检查

上传到 GitHub 前，确认不要包含：

```text
.env
*.log
errors.json
notifyme.db
task_monitor_offset.txt
__pycache__/
```

可以用下面命令检查是否还有 token：

```powershell
rg "bot[0-9]+:|TELEGRAM_TOKEN=.+|AAG|api.telegram.org"
```

如果真实 token 曾经出现在日志或 Git 历史里，建议去 BotFather 重新生成 token。

## 13. 常见问题

### 1. 运行 `python train.py` 提示找不到文件

先设置工作目录：

```text
工作目录 E:\projects\my-train
```

再运行：

```text
运行 python train.py
```

### 2. Telegram 没收到消息

检查：

- `.env` 是否存在
- `TELEGRAM_TOKEN` 是否正确
- `TELEGRAM_CHAT_ID` 是否正确
- 是否先给 bot 发过消息
- 网络是否能访问 Telegram

### 3. `getUpdates` 页面是空的

先打开你的 bot，发送：

```text
hello
```

然后再刷新：

```text
https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates
```

### 4. 截图失败

可能原因：

- 电脑没有桌面环境
- 远程服务器没有图形界面
- Linux 缺少截图工具

截图失败不影响文字提醒。

### 5. GPU 监控不可用

GPU 监控依赖 NVIDIA 和 `pynvml`。

如果没有 NVIDIA GPU，或者驱动环境不支持，GPU 监控会不可用，但其他功能仍然可以使用。

## 14. 安全提醒

请务必注意：

- 不要把 `.env` 上传 GitHub。
- 不要把 Telegram token 发给别人。
- 如果 token 泄露，立刻去 BotFather 重置。
- 日志、数据库、错误记录都属于个人运行数据，不要上传。

本仓库只应该上传代码、README、`.env.example` 和依赖文件。
