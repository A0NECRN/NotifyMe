from __future__ import annotations

import logging
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil
import requests

from .config import AppConfig
from .errors import ErrorRecorder
from .notifier import Notifier
from .storage import Storage
from .system_info import GpuMonitor
from .telegram_client import TelegramClient
from .text import truncate
from .workdir import get_default_workdir


@dataclass(frozen=True)
class WatchContext:
    config: AppConfig
    notifier: Notifier
    telegram: TelegramClient
    gpu: GpuMonitor
    errors: ErrorRecorder
    storage: Storage


@dataclass
class ResourceTracker:
    gpu: GpuMonitor
    start_time: datetime
    max_cpu: float = 0.0
    max_memory: float = 0.0
    max_gpu: int = 0
    samples: int = 0

    def sample(self) -> None:
        try:
            self.max_cpu = max(self.max_cpu, float(psutil.cpu_percent(interval=None)))
            self.max_memory = max(self.max_memory, float(psutil.virtual_memory().percent))
            if self.gpu.available:
                self.max_gpu = max(self.max_gpu, int(self.gpu.usage()))
            self.samples += 1
        except Exception:
            return

    def metrics(self) -> dict:
        return {
            "duration": max(0.0, (datetime.now() - self.start_time).total_seconds()),
            "max_cpu": round(self.max_cpu, 1),
            "max_memory": round(self.max_memory, 1),
            "max_gpu": self.max_gpu,
            "samples": self.samples,
        }


def finish_task(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    success: bool,
    summary: str,
    tracker: ResourceTracker,
    exit_code: int | None = None,
) -> None:
    tracker.sample()
    metrics = tracker.metrics()
    status = "success" if success else "failed"
    ctx.storage.finish_run(run_id, status, summary, metrics, exit_code)
    ctx.notifier.task_done(task_name, summary, success=success, metrics=metrics)


def safe_process_iter(attrs=None) -> list[dict]:
    results: list[dict] = []
    for proc in psutil.process_iter(attrs):
        try:
            results.append(proc.as_dict(attrs=attrs))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return results


def find_processes_by_keyword(keyword: str) -> list[dict]:
    keyword_lower = keyword.lower()
    matched: list[dict] = []
    for info in safe_process_iter(["name", "cmdline", "pid"]):
        name = info.get("name") or ""
        cmdline = info.get("cmdline") or []
        if keyword_lower in name.lower() or any(part and keyword_lower in part.lower() for part in cmdline):
            matched.append(info)
    return matched


def watch_process(ctx: WatchContext, run_id: int, task_name: str, keyword: str, stop_event: threading.Event) -> None:
    log = logging.getLogger(__name__)
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    log.info("[Process] Watching keyword: %s", keyword)
    appeared = False
    first_seen: list[dict] = []

    while not stop_event.is_set():
        tracker.sample()
        processes = find_processes_by_keyword(keyword)
        if processes:
            appeared = True
            first_seen = processes
            log.info("[Process] Found %s process(es) for %s", len(processes), keyword)
            break
        time.sleep(ctx.config.check_interval)

    while not stop_event.is_set():
        tracker.sample()
        processes = find_processes_by_keyword(keyword)
        if appeared and not processes:
            names = ", ".join(str(p.get("name") or p.get("pid")) for p in first_seen[:5])
            finish_task(ctx, run_id, task_name, True, f"Process keyword '{keyword}' ended. First seen: {names}", tracker)
            return
        time.sleep(ctx.config.check_interval)


def watch_log_keyword(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    log_path: str,
    keyword: str,
    stop_event: threading.Event,
) -> None:
    log = logging.getLogger(__name__)
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    path = _resolve_path(ctx, log_path)
    log.info("[Log] Watching %s for %s", path, keyword)

    while not path.exists() and not stop_event.is_set():
        time.sleep(2)
    if stop_event.is_set():
        return

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(0, 2)
            while not stop_event.is_set():
                tracker.sample()
                line = handle.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                if keyword.lower() in line.lower():
                    finish_task(ctx, run_id, task_name, True, f"Keyword '{keyword}' found.\nLast line: {line.strip()}", tracker)
                    return
    except Exception as exc:
        ctx.errors.record("LOG_WATCH", str(exc))
        finish_task(ctx, run_id, task_name, False, f"Log watch failed: {exc}", tracker)


def watch_command(ctx: WatchContext, run_id: int, task_name: str, command: str, stop_event: threading.Event) -> None:
    return watch_command_in_dir(ctx, run_id, task_name, command, "", stop_event)


def watch_command_in_dir(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    command: str,
    cwd: str,
    stop_event: threading.Event,
) -> None:
    log = logging.getLogger(__name__)
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    log.info("[Command] Running task %s in %s", task_name, cwd or ctx.config.app_dir)
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        output_lines: list[str] = []
        if proc.stdout is not None:
            for line in proc.stdout:
                tracker.sample()
                output_lines.append(line.rstrip())
                print(line, end="")
                if stop_event.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    ctx.storage.cancel_run(run_id, "cancelled by user")
                    return

        proc.wait()
        tracker.sample()
        last_output = "\n".join(output_lines[-8:])
        detail = f"Working dir: {cwd or ctx.config.app_dir}\nExit {proc.returncode}\nLast output:\n{truncate(last_output, 1000)}"
        finish_task(ctx, run_id, task_name, proc.returncode == 0, detail, tracker, proc.returncode)
    except Exception as exc:
        ctx.errors.record("COMMAND_EXEC", str(exc))
        finish_task(ctx, run_id, task_name, False, f"Command error: {exc}", tracker)


def watch_cpu_idle(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    threshold: float,
    duration: int,
    stop_event: threading.Event,
) -> None:
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    logging.getLogger(__name__).info("[CPU] Waiting for CPU < %s%% for %ss", threshold, duration)
    idle_seconds = 0
    while not stop_event.is_set():
        usage = psutil.cpu_percent(interval=1)
        tracker.sample()
        if usage < threshold:
            idle_seconds += 1
            if idle_seconds >= duration:
                finish_task(ctx, run_id, task_name, True, f"CPU stayed below {threshold}% for {duration}s", tracker)
                return
        else:
            idle_seconds = 0


def watch_gpu_idle(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    threshold: float,
    duration: int,
    stop_event: threading.Event,
) -> None:
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    if not ctx.gpu.available:
        finish_task(ctx, run_id, task_name, False, "GPU monitoring is not available.", tracker)
        return

    logging.getLogger(__name__).info("[GPU] Waiting for GPU < %s%% for %ss", threshold, duration)
    idle_seconds = 0
    while not stop_event.is_set():
        try:
            usage = ctx.gpu.usage()
            tracker.sample()
        except Exception as exc:
            ctx.errors.record("GPU_USAGE", str(exc))
            finish_task(ctx, run_id, task_name, False, f"GPU monitor failed: {exc}", tracker)
            return
        if usage < threshold:
            idle_seconds += 1
            if idle_seconds >= duration:
                finish_task(ctx, run_id, task_name, True, f"GPU stayed below {threshold}% for {duration}s", tracker)
                return
        else:
            idle_seconds = 0
        time.sleep(1)


def watch_file(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    path_text: str,
    mode: str,
    stable_seconds: int,
    stop_event: threading.Event,
) -> None:
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    path = _resolve_path(ctx, path_text)
    mode = mode.lower()
    last_size: int | None = None
    stable_count = 0
    while not stop_event.is_set():
        tracker.sample()
        exists = path.exists()
        if mode == "exists" and exists:
            finish_task(ctx, run_id, task_name, True, f"File exists: {path}", tracker)
            return
        if mode == "missing" and not exists:
            finish_task(ctx, run_id, task_name, True, f"File is missing: {path}", tracker)
            return
        if mode == "stable" and exists:
            size = path.stat().st_size
            if last_size == size:
                stable_count += 1
                if stable_count >= stable_seconds:
                    finish_task(ctx, run_id, task_name, True, f"File size stable for {stable_seconds}s: {path} ({size} bytes)", tracker)
                    return
            else:
                stable_count = 0
                last_size = size
        time.sleep(1)


def watch_port(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    host: str,
    port: int,
    mode: str,
    stop_event: threading.Event,
) -> None:
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    mode = mode.lower()
    while not stop_event.is_set():
        tracker.sample()
        open_now = _is_port_open(host, port)
        if mode == "open" and open_now:
            finish_task(ctx, run_id, task_name, True, f"Port is open: {host}:{port}", tracker)
            return
        if mode == "closed" and not open_now:
            finish_task(ctx, run_id, task_name, True, f"Port is closed: {host}:{port}", tracker)
            return
        time.sleep(ctx.config.check_interval)


def watch_http(
    ctx: WatchContext,
    run_id: int,
    task_name: str,
    url: str,
    expected_status: int,
    contains: str,
    stop_event: threading.Event,
) -> None:
    tracker = ResourceTracker(ctx.gpu, datetime.now())
    last_error = ""
    while not stop_event.is_set():
        tracker.sample()
        try:
            response = requests.get(url, timeout=10, verify=ctx.config.verify_ssl)
            body_match = not contains or contains in response.text
            if response.status_code == expected_status and body_match:
                summary = f"HTTP matched: {url} returned {response.status_code}"
                if contains:
                    summary += f" and contained '{contains}'"
                finish_task(ctx, run_id, task_name, True, summary, tracker)
                return
            last_error = f"status={response.status_code}, contains={body_match}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(ctx.config.check_interval)

    if last_error:
        ctx.errors.record("HTTP_WATCH_STOPPED", last_error)


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _resolve_path(ctx: WatchContext, path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return get_default_workdir(ctx.config, ctx.storage) / path
