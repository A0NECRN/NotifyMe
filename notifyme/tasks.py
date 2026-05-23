from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .watchers import (
    WatchContext,
    watch_command,
    watch_command_in_dir,
    watch_cpu_idle,
    watch_file,
    watch_gpu_idle,
    watch_http,
    watch_log_keyword,
    watch_port,
    watch_process,
)


@dataclass
class TaskInfo:
    run_id: int
    name: str
    kind: str
    detail: str
    started_at: datetime
    thread: threading.Thread
    stop_event: threading.Event


class TaskManager:
    def __init__(self, context: WatchContext):
        self.context = context
        self.tasks: dict[str, TaskInfo] = {}
        self.lock = threading.RLock()
        self.log = logging.getLogger(__name__)

    def add_process_task(self, name: str, keyword: str) -> None:
        self._register(name, "process", f"keyword={keyword}", watch_process, name, keyword)

    def add_log_task(self, name: str, log_path: str, keyword: str) -> None:
        self._register(name, "log", f"{log_path} contains {keyword}", watch_log_keyword, name, log_path, keyword)

    def add_command_task(self, name: str, command: str, cwd: str = "") -> None:
        detail = command if not cwd else f"{command} (cwd={cwd})"
        if cwd:
            self._register(name, "command", detail, watch_command_in_dir, name, command, cwd)
        else:
            self._register(name, "command", detail, watch_command, name, command)

    def add_cpu_task(self, name: str, threshold: float | None = None, duration: int | None = None) -> None:
        threshold = threshold if threshold is not None else self.context.config.cpu_threshold
        duration = duration if duration is not None else self.context.config.cpu_idle_duration
        detail = f"threshold={threshold}, duration={duration}s"
        self._register(name, "cpu", detail, watch_cpu_idle, name, threshold, duration)

    def add_gpu_task(self, name: str, threshold: float | None = None, duration: int | None = None) -> None:
        threshold = threshold if threshold is not None else self.context.config.gpu_threshold
        duration = duration if duration is not None else self.context.config.gpu_idle_duration
        detail = f"threshold={threshold}, duration={duration}s"
        self._register(name, "gpu", detail, watch_gpu_idle, name, threshold, duration)

    def add_file_task(self, name: str, path: str, mode: str = "exists", stable_seconds: int = 10) -> None:
        detail = f"path={path}, mode={mode}, stable={stable_seconds}s"
        self._register(name, "file", detail, watch_file, name, path, mode, stable_seconds)

    def add_port_task(self, name: str, host: str, port: int, mode: str = "open") -> None:
        detail = f"{host}:{port} is {mode}"
        self._register(name, "port", detail, watch_port, name, host, port, mode)

    def add_http_task(self, name: str, url: str, status: int = 200, contains: str = "") -> None:
        detail = f"url={url}, status={status}"
        if contains:
            detail += f", contains={contains}"
        self._register(name, "http", detail, watch_http, name, url, status, contains)

    def remove_task(self, name: str) -> bool:
        with self.lock:
            task = self.tasks.pop(name, None)
        if not task:
            return False
        task.stop_event.set()
        self.context.storage.cancel_run(task.run_id, "removed by user")
        self.log.info("Task removed: %s", name)
        return True

    def list_tasks(self) -> list[TaskInfo]:
        with self.lock:
            finished = [name for name, task in self.tasks.items() if not task.thread.is_alive()]
            for name in finished:
                self.tasks.pop(name, None)
            return list(self.tasks.values())

    def stop_all(self) -> None:
        with self.lock:
            tasks = list(self.tasks.values())
            self.tasks.clear()
        for task in tasks:
            task.stop_event.set()
            self.context.storage.cancel_run(task.run_id, "service stopped")

    def _register(self, name: str, kind: str, detail: str, target: Callable, *args) -> None:
        run_id = self.context.storage.start_run(name, kind, detail, {"args": [str(item) for item in args]})
        stop_event = threading.Event()
        thread = threading.Thread(
            target=target,
            args=(self.context, run_id, *args, stop_event),
            daemon=True,
            name=f"notifyme-{kind}-{name}",
        )
        with self.lock:
            existing = self.tasks.pop(name, None)
            if existing:
                existing.stop_event.set()
                self.context.storage.cancel_run(existing.run_id, "replaced by a new task with the same name")
                self.log.info("Replaced existing task: %s", name)
            self.tasks[name] = TaskInfo(run_id, name, kind, detail, datetime.now(), thread, stop_event)
        thread.start()
        self.log.info("Task added: %s (%s)", name, kind)
