from __future__ import annotations

import argparse
import sys
import time

from .runtime import build_runtime
from .workdir import get_default_workdir, resolve_workdir, set_default_workdir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notifyme", description="NotifyMe local task monitor CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run a command and notify when it finishes")
    run_p.add_argument("cmd", nargs=argparse.REMAINDER)
    run_p.add_argument("--name", default="")
    run_p.add_argument("--cwd", default="")

    proc_p = sub.add_parser("proc", help="watch a process keyword")
    proc_p.add_argument("keyword")
    proc_p.add_argument("--name", default="")

    log_p = sub.add_parser("log", help="watch a log file for a keyword")
    log_p.add_argument("path")
    log_p.add_argument("keyword")
    log_p.add_argument("--name", default="")

    file_p = sub.add_parser("file", help="watch a file")
    file_p.add_argument("path")
    file_p.add_argument("--mode", choices=["exists", "stable", "missing"], default="exists")
    file_p.add_argument("--stable", type=int, default=10)
    file_p.add_argument("--name", default="")

    port_p = sub.add_parser("port", help="watch a TCP port")
    port_p.add_argument("host")
    port_p.add_argument("port", type=int)
    port_p.add_argument("--mode", choices=["open", "closed"], default="open")
    port_p.add_argument("--name", default="")

    http_p = sub.add_parser("http", help="watch an HTTP endpoint")
    http_p.add_argument("url")
    http_p.add_argument("--status", type=int, default=200)
    http_p.add_argument("--contains", default="")
    http_p.add_argument("--name", default="")

    cpu_p = sub.add_parser("cpu", help="watch CPU idle")
    cpu_p.add_argument("--threshold", type=float, default=None)
    cpu_p.add_argument("--duration", type=int, default=None)
    cpu_p.add_argument("--name", default="CPU idle")

    gpu_p = sub.add_parser("gpu", help="watch GPU idle")
    gpu_p.add_argument("--threshold", type=float, default=None)
    gpu_p.add_argument("--duration", type=int, default=None)
    gpu_p.add_argument("--name", default="GPU idle")

    hist_p = sub.add_parser("history", help="show recent task runs")
    hist_p.add_argument("-n", "--limit", type=int, default=10)

    sub.add_parser("status", help="show active tasks for this CLI process")

    cwd_p = sub.add_parser("cwd", help="show or set default working directory")
    cwd_p.add_argument("path", nargs="?")

    args = parser.parse_args(argv)
    runtime = build_runtime()

    if args.command == "history":
        for record in runtime.storage.recent_runs(args.limit):
            print(f"#{record.id} {record.name} [{record.kind}] {record.status} {record.duration:.1f}s {record.summary}")
        return 0

    if args.command == "status":
        tasks = runtime.manager.list_tasks()
        if not tasks:
            print("No active tasks in this CLI process.")
            return 0
        for task in tasks:
            print(f"{task.name} [{task.kind}] {task.detail}")
        return 0

    if args.command == "cwd":
        if args.path:
            path = set_default_workdir(runtime.storage, args.path)
            print(f"Default working directory set to: {path}")
        else:
            print(get_default_workdir(runtime.config, runtime.storage))
        return 0

    if args.command == "run":
        command = " ".join(args.cmd).strip()
        if not command:
            parser.error("run requires a command")
        cwd = resolve_workdir(runtime.config, runtime.storage, args.cwd)
        runtime.manager.add_command_task(args.name or command[:60], command, str(cwd))
    elif args.command == "proc":
        runtime.manager.add_process_task(args.name or args.keyword, args.keyword)
    elif args.command == "log":
        runtime.manager.add_log_task(args.name or f"Log: {args.keyword}", args.path, args.keyword)
    elif args.command == "file":
        runtime.manager.add_file_task(args.name or f"File: {args.path}", args.path, args.mode, args.stable)
    elif args.command == "port":
        runtime.manager.add_port_task(args.name or f"Port: {args.host}:{args.port}", args.host, args.port, args.mode)
    elif args.command == "http":
        runtime.manager.add_http_task(args.name or f"HTTP: {args.url}", args.url, args.status, args.contains)
    elif args.command == "cpu":
        runtime.manager.add_cpu_task(args.name, args.threshold, args.duration)
    elif args.command == "gpu":
        runtime.manager.add_gpu_task(args.name, args.threshold, args.duration)

    print("Watch started. Press Ctrl+C to stop.")
    try:
        while runtime.manager.list_tasks():
            time.sleep(1)
    except KeyboardInterrupt:
        runtime.manager.stop_all()
        print("Stopped.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
