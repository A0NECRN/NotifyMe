from __future__ import annotations

import logging
import platform
import shlex
import time
from datetime import datetime

import requests

from .menu import MAIN_MENU, menu_text
from .notifier import Notifier
from .system_info import GpuMonitor, cpu_stats
from .tasks import TaskManager
from .telegram_client import TelegramClient
from .text import html_escape
from .workdir import get_default_workdir, resolve_workdir, set_default_workdir


class CommandHandler:
    def __init__(self, manager: TaskManager, telegram: TelegramClient, notifier: Notifier, gpu: GpuMonitor):
        self.manager = manager
        self.telegram = telegram
        self.notifier = notifier
        self.gpu = gpu
        self.log = logging.getLogger(__name__)

    def handle(self, text: str) -> None:
        text = text.strip()
        shortcut = self._shortcut_to_command(text)
        if shortcut:
            text = shortcut
        command, rest = self._split_command(text)
        command = command.lower()
        try:
            if command in {"/help", "/start", "/menu"}:
                self.telegram.send_message(self.help_text(), reply_markup=MAIN_MENU)
            elif command == "/status":
                self._status()
            elif command == "/screenshot":
                self.notifier.screenshot_now()
            elif command == "/stats":
                self._stats()
            elif command == "/history":
                self._history(rest)
            elif command == "/last":
                self._last()
            elif command == "/task":
                self._task(rest)
            elif command == "/cwd":
                self._cwd(rest)
            elif command in {"/watch", "/add"}:
                self._watch(rest, legacy=command == "/add")
            elif command == "/run":
                self._watch("cmd " + rest, legacy=False)
            elif command == "/remove":
                self._remove(rest)
            else:
                self.telegram.send_message(
                    f"没识别这句：{html_escape(text)}\n\n点下面按钮，或发送“帮助”查看例子。",
                    reply_markup=MAIN_MENU,
                )
        except ValueError as exc:
            self.telegram.send_message(f"没添加成功：{html_escape(exc)}\n\n发送“帮助”看例子。", reply_markup=MAIN_MENU)
        except Exception as exc:
            self.log.exception("Command failed")
            self.telegram.send_message(f"执行失败：{html_escape(exc)}", reply_markup=MAIN_MENU)

    def help_text(self) -> str:
        return (
            menu_text()
            + "\n\n<b>常用短句</b>\n"
            "状态 / 截图 / 系统 / 历史 / 最后一次\n"
            "运行 python train.py\n"
            "工作目录 E:\\projects\\my-train\n"
            "在 E:\\projects\\my-train 运行 python train.py\n"
            "监控进程 python\n"
            "监控日志 C:\\logs\\build.log Done\n"
            "监控文件 output.zip\n"
            "监控端口 127.0.0.1 8000\n"
            "监控网页 http://127.0.0.1:8000/health ok\n"
            "停止 Training\n\n"
            "高级命令仍然支持：/watch、/run、/history、/task。"
        )

    def _status(self) -> None:
        tasks = self.manager.list_tasks()
        if not tasks:
            self.telegram.send_message("当前没有活跃任务。", reply_markup=MAIN_MENU)
            return
        lines = ["<b>Active tasks</b>"]
        for task in tasks:
            age = int((datetime.now() - task.started_at).total_seconds())
            lines.append(
                f"- <b>{html_escape(task.name)}</b> "
                f"({html_escape(task.kind)}, {age}s)\n  {html_escape(task.detail)}"
            )
        self.telegram.send_message("\n".join(lines), reply_markup=MAIN_MENU)

    def _stats(self) -> None:
        cpu = cpu_stats()
        lines = [
            "<b>System stats</b>",
            f"<b>Host:</b> {html_escape(platform.node())}",
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"<b>CPU:</b> {cpu['usage']:.1f}% ({cpu['cores']} cores)",
            "",
            "<b>GPU:</b>",
        ]
        gpu_items = self.gpu.stats()
        if not gpu_items:
            lines.append("Not available")
        else:
            for item in gpu_items:
                lines.append(
                    f"- {html_escape(item['name'])}: {item['usage']}%, "
                    f"{item['mem_used']}MB / {item['mem_total']}MB"
                )
        self.telegram.send_message("\n".join(lines), reply_markup=MAIN_MENU)

    def _watch(self, rest: str, legacy: bool) -> None:
        subcommand, body = self._split_command(rest)
        subcommand = subcommand.lower()
        if subcommand in {"proc", "process"}:
            self._watch_process(body, legacy)
        elif subcommand in {"cmd", "command", "run"}:
            self._watch_command(body, legacy)
        elif subcommand == "log":
            self._watch_log(body, legacy)
        elif subcommand == "file":
            self._watch_file(body)
        elif subcommand == "port":
            self._watch_port(body)
        elif subcommand == "http":
            self._watch_http(body)
        elif subcommand == "cpu":
            self._watch_cpu(body)
        elif subcommand == "gpu":
            self._watch_gpu(body)
        else:
            raise ValueError("watch type must be one of: proc, cmd, log, file, port, http, cpu, gpu")

    def _watch_process(self, body: str, legacy: bool) -> None:
        if legacy:
            parts = body.split(maxsplit=1)
            if not parts:
                raise ValueError("missing process keyword")
            keyword = parts[0]
            name = parts[1] if len(parts) > 1 else keyword
        else:
            target, name = self._extract_name(body)
            parts = self._split_args(target)
            if not parts:
                raise ValueError("missing process keyword")
            keyword = parts[0]
            name = name or keyword
        self.manager.add_process_task(name, keyword)
        self.telegram.send_message(f"已开始监控进程：<b>{html_escape(name)}</b> ({html_escape(keyword)})", reply_markup=MAIN_MENU)

    def _watch_command(self, body: str, legacy: bool) -> None:
        command, name = self._extract_name(body)
        command, cwd = self._extract_cwd(command)
        if legacy and not name:
            parts = body.split(maxsplit=1)
            if not parts:
                raise ValueError("missing command")
            command = parts[0]
            name = parts[1] if len(parts) > 1 else command
            command, cwd = self._extract_cwd(command)
        if not command:
            raise ValueError("missing command")
        name = name or command[:60]
        workdir = resolve_workdir(self.manager.context.config, self.manager.context.storage, cwd)
        self.manager.add_command_task(name, command, str(workdir))
        self.telegram.send_message(
            f"已开始运行：<b>{html_escape(name)}</b>\n目录：{html_escape(workdir)}",
            reply_markup=MAIN_MENU,
        )

    def _watch_log(self, body: str, legacy: bool) -> None:
        target, name = self._extract_name(body)
        parts = self._split_args(target)
        if len(parts) < 2:
            raise ValueError("log watch needs a path and keyword")
        log_path, keyword = parts[0], parts[1]
        if legacy and len(parts) > 2 and not name:
            name = " ".join(parts[2:])
        name = name or f"Log: {keyword}"
        self.manager.add_log_task(name, log_path, keyword)
        self.telegram.send_message(f"已开始监控日志：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _watch_cpu(self, body: str) -> None:
        target, name = self._extract_name(body)
        options, words = self._parse_options(self._split_args(target))
        name = name or " ".join(words) or "CPU idle"
        threshold = float(options.get("threshold", options.get("t", self.manager.context.config.cpu_threshold)))
        duration = int(options.get("duration", options.get("d", self.manager.context.config.cpu_idle_duration)))
        self.manager.add_cpu_task(name, threshold, duration)
        self.telegram.send_message(f"已开始监控 CPU：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _watch_gpu(self, body: str) -> None:
        target, name = self._extract_name(body)
        options, words = self._parse_options(self._split_args(target))
        name = name or " ".join(words) or "GPU idle"
        threshold = float(options.get("threshold", options.get("t", self.manager.context.config.gpu_threshold)))
        duration = int(options.get("duration", options.get("d", self.manager.context.config.gpu_idle_duration)))
        self.manager.add_gpu_task(name, threshold, duration)
        self.telegram.send_message(f"已开始监控 GPU：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _watch_file(self, body: str) -> None:
        target, name = self._extract_name(body)
        options, words = self._parse_options(self._split_args(target))
        if not words:
            raise ValueError("file watch needs a path")
        path = words[0]
        mode = options.get("mode", "exists")
        stable = int(options.get("stable", options.get("duration", 10)))
        if mode not in {"exists", "stable", "missing"}:
            raise ValueError("file mode must be exists, stable, or missing")
        name = name or f"File: {path}"
        self.manager.add_file_task(name, path, mode, stable)
        self.telegram.send_message(f"已开始监控文件：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _watch_port(self, body: str) -> None:
        target, name = self._extract_name(body)
        options, words = self._parse_options(self._split_args(target))
        if len(words) < 2:
            raise ValueError("port watch needs host and port")
        host = words[0]
        port = int(words[1])
        mode = options.get("mode", "open")
        if mode not in {"open", "closed"}:
            raise ValueError("port mode must be open or closed")
        name = name or f"Port: {host}:{port}"
        self.manager.add_port_task(name, host, port, mode)
        self.telegram.send_message(f"已开始监控端口：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _watch_http(self, body: str) -> None:
        target, name = self._extract_name(body)
        options, words = self._parse_options(self._split_args(target))
        if not words:
            raise ValueError("http watch needs a URL")
        url = words[0]
        status = int(options.get("status", 200))
        contains = options.get("contains", "")
        name = name or f"HTTP: {url}"
        self.manager.add_http_task(name, url, status, contains)
        self.telegram.send_message(f"已开始监控网页：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _history(self, rest: str) -> None:
        limit = 10
        if rest.strip():
            limit = max(1, min(25, int(rest.strip())))
        records = self.manager.context.storage.recent_runs(limit)
        if not records:
            self.telegram.send_message("还没有任务历史。", reply_markup=MAIN_MENU)
            return
        self.telegram.send_message(self._format_records("Recent runs", records), reply_markup=MAIN_MENU)

    def _last(self) -> None:
        record = self.manager.context.storage.last_run()
        if not record:
            self.telegram.send_message("还没有任务历史。", reply_markup=MAIN_MENU)
            return
        self.telegram.send_message(self._format_records("Last run", [record], verbose=True), reply_markup=MAIN_MENU)

    def _task(self, rest: str) -> None:
        name = rest.strip()
        if not name:
            self.telegram.send_message("发送：任务 Training", reply_markup=MAIN_MENU)
            return
        records = self.manager.context.storage.find_runs(name, 5)
        if not records:
            self.telegram.send_message(f"没有找到这个任务的历史：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)
            return
        self.telegram.send_message(self._format_records(f"Task: {name}", records, verbose=True), reply_markup=MAIN_MENU)

    def _format_records(self, title: str, records, verbose: bool = False) -> str:
        lines = [f"<b>{html_escape(title)}</b>"]
        for record in records:
            duration = f"{record.duration:.1f}s" if record.duration else "-"
            line = (
                f"#{record.id} <b>{html_escape(record.name)}</b> "
                f"[{html_escape(record.kind)}] {html_escape(record.status)} {duration}"
            )
            if record.exit_code is not None:
                line += f" exit={record.exit_code}"
            lines.append(line)
            if verbose:
                if record.summary:
                    lines.append(f"  {html_escape(record.summary[:500])}")
                if record.metrics:
                    lines.append(
                        "  "
                        f"peak CPU {record.metrics.get('max_cpu', 0)}%, "
                        f"RAM {record.metrics.get('max_memory', 0)}%, "
                        f"GPU {record.metrics.get('max_gpu', 0)}%"
                    )
        return "\n".join(lines)

    def _remove(self, rest: str) -> None:
        name = rest.strip()
        if not name:
            self.telegram.send_message("发送：停止 Training", reply_markup=MAIN_MENU)
            return
        if self.manager.remove_task(name):
            self.telegram.send_message(f"已停止：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)
        else:
            self.telegram.send_message(f"没找到任务：<b>{html_escape(name)}</b>", reply_markup=MAIN_MENU)

    def _cwd(self, rest: str) -> None:
        value = rest.strip().strip('"')
        if not value:
            cwd = get_default_workdir(self.manager.context.config, self.manager.context.storage)
            self.telegram.send_message(f"当前工作目录：\n<code>{html_escape(cwd)}</code>", reply_markup=MAIN_MENU)
            return
        try:
            cwd = set_default_workdir(self.manager.context.storage, value)
        except ValueError as exc:
            self.telegram.send_message(f"工作目录设置失败：{html_escape(exc)}", reply_markup=MAIN_MENU)
            return
        self.telegram.send_message(f"已设置工作目录：\n<code>{html_escape(cwd)}</code>", reply_markup=MAIN_MENU)

    def _shortcut_to_command(self, text: str) -> str:
        normalized = text.strip()
        lower = normalized.lower()
        simple = {
            "菜单": "/menu",
            "menu": "/menu",
            "帮助": "/help",
            "help": "/help",
            "状态": "/status",
            "任务": "/status",
            "status": "/status",
            "截图": "/screenshot",
            "系统": "/stats",
            "统计": "/stats",
            "stats": "/stats",
            "历史": "/history 10",
            "最后一次": "/last",
            "最后": "/last",
            "监控gpu": "/watch gpu --name GPU idle",
            "gpu": "/watch gpu --name GPU idle",
            "监控cpu": "/watch cpu --name CPU idle",
            "cpu": "/watch cpu --name CPU idle",
            "停止任务": "/status",
            "工作目录": "/cwd",
            "cwd": "/cwd",
        }
        compact = lower.replace(" ", "")
        if compact in simple:
            return simple[compact]
        if lower.startswith(("运行 ", "run ")):
            command = normalized.split(maxsplit=1)[1]
            return f"/run {command}"
        if lower.startswith(("工作目录 ", "设置目录 ", "目录 ", "cwd ")):
            path = normalized.split(maxsplit=1)[1]
            return f"/cwd {path}"
        if lower.startswith("在 ") and " 运行 " in normalized:
            cwd, command = normalized[2:].split(" 运行 ", 1)
            return f"/run --cwd {cwd} {command}"
        if lower.startswith("in ") and " run " in lower:
            body = normalized[3:]
            marker = body.lower().find(" run ")
            cwd = body[:marker]
            command = body[marker + 5 :]
            return f"/run --cwd {cwd} {command}"
        if lower.startswith(("监控进程 ", "进程 ", "process ")):
            keyword = normalized.split(maxsplit=1)[1]
            return f"/watch proc {keyword} --name {keyword}"
        if lower.startswith(("监控日志 ", "日志 ", "log ")):
            body = normalized.split(maxsplit=1)[1]
            return f"/watch log {body}"
        if lower.startswith(("监控文件 ", "文件 ", "file ")):
            path = normalized.split(maxsplit=1)[1]
            return f"/watch file {path} mode=stable --name {path}"
        if lower.startswith(("监控端口 ", "端口 ", "port ")):
            body = normalized.split(maxsplit=1)[1]
            return f"/watch port {body}"
        if lower.startswith(("监控网页 ", "网页 ", "监控网站 ", "网站 ", "http ")):
            body = normalized.split(maxsplit=1)[1]
            parts = body.split(maxsplit=1)
            if len(parts) == 2 and "=" not in parts[1]:
                return f"/watch http {parts[0]} contains={parts[1]} --name {parts[0]}"
            return f"/watch http {body}"
        if lower.startswith(("停止 ", "取消 ", "remove ")):
            name = normalized.split(maxsplit=1)[1]
            return f"/remove {name}"
        if lower.startswith(("任务 ", "task ")):
            name = normalized.split(maxsplit=1)[1]
            return f"/task {name}"
        return ""

    @staticmethod
    def _extract_cwd(text: str) -> tuple[str, str]:
        stripped = text.strip()
        lower = stripped.lower()
        if lower.startswith("--cwd="):
            rest = stripped[len("--cwd=") :].lstrip()
            cwd, command = CommandHandler._consume_value(rest)
            return command.strip(), cwd
        if lower.startswith("--cwd "):
            rest = stripped[len("--cwd ") :].lstrip()
            cwd, command = CommandHandler._consume_value(rest)
            return command.strip(), cwd
        return stripped, ""

    @staticmethod
    def _consume_value(text: str) -> tuple[str, str]:
        if not text:
            return "", ""
        quote = text[0] if text[0] in {"'", '"'} else ""
        if quote:
            end = text.find(quote, 1)
            if end >= 0:
                return text[1:end], text[end + 1 :].lstrip()
        parts = text.split(maxsplit=1)
        return parts[0].strip('"'), parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _split_command(text: str) -> tuple[str, str]:
        stripped = text.strip()
        if not stripped:
            return "", ""
        parts = stripped.split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _extract_name(text: str) -> tuple[str, str]:
        lower = text.lower()
        equals_marker = " --name="
        equals_index = lower.rfind(equals_marker)
        if equals_index >= 0:
            body = text[:equals_index].strip()
            name = text[equals_index + len(equals_marker) :].strip().strip("'\"")
            return body, name
        for marker in (" --name ", " as "):
            index = lower.rfind(marker)
            if index >= 0:
                body = text[:index].strip()
                name = text[index + len(marker) :].strip().strip("'\"")
                return body, name
        return text.strip(), ""

    @staticmethod
    def _split_args(text: str) -> list[str]:
        if not text:
            return []
        try:
            return shlex.split(text, posix=False)
        except ValueError:
            return text.split()

    @staticmethod
    def _parse_options(tokens: list[str]) -> tuple[dict[str, str], list[str]]:
        options: dict[str, str] = {}
        words: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if "=" in token:
                key, value = token.split("=", 1)
                options[key.lstrip("-").lower()] = value
            elif token.startswith("--") and index + 1 < len(tokens):
                options[token[2:].lower()] = tokens[index + 1]
                index += 1
            else:
                words.append(token)
            index += 1
        return options, words


class TelegramCommandReceiver:
    def __init__(self, telegram: TelegramClient, handler: CommandHandler):
        self.telegram = telegram
        self.handler = handler
        self.config = telegram.config
        self.errors = telegram.errors
        self.last_update_id = self._load_offset()
        self.log = logging.getLogger(__name__)

    def run_forever(self, stop_event) -> None:
        self.log.info("Listening for Telegram commands")
        while not stop_event.is_set():
            self.poll()

    def poll(self) -> None:
        try:
            updates = self.telegram.get_updates(self.last_update_id + 1)
            for update in updates:
                update_id = int(update.get("update_id", 0))
                self.last_update_id = max(self.last_update_id, update_id)
                self._save_offset(self.last_update_id)
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                if chat_id != self.config.telegram_chat_id:
                    continue
                text = str(message.get("text", "")).strip()
                if text:
                    self.log.info("Telegram command received: %s", text.split(maxsplit=1)[0])
                    self.handler.handle(text)
        except requests.exceptions.Timeout:
            return
        except Exception as exc:
            self.log.error("Telegram poll error: %s", exc)
            self.errors.record("BOT_POLL", str(exc))
            time.sleep(5)

    def _load_offset(self) -> int:
        try:
            if self.config.offset_file.exists():
                return int(self.config.offset_file.read_text(encoding="utf-8").strip())
        except Exception:
            return 0
        return 0

    def _save_offset(self, update_id: int) -> None:
        self.config.offset_file.write_text(str(update_id), encoding="utf-8")
