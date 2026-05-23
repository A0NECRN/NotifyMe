from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig, load_config
from .errors import ErrorRecorder
from .logging_setup import setup_logging
from .notifier import Notifier
from .screenshot import Screenshotter
from .storage import Storage
from .system_info import GpuMonitor
from .tasks import TaskManager
from .telegram_client import TelegramClient
from .watchers import WatchContext


@dataclass
class Runtime:
    config: AppConfig
    errors: ErrorRecorder
    storage: Storage
    telegram: TelegramClient
    notifier: Notifier
    gpu: GpuMonitor
    manager: TaskManager


def build_runtime(with_logging: bool = True) -> Runtime:
    config = load_config()
    if with_logging:
        setup_logging(config.log_file, [config.telegram_token])
    errors = ErrorRecorder(config.errors_file, [config.telegram_token])
    storage = Storage(config.database_file)
    telegram = TelegramClient(config, errors)
    screenshotter = Screenshotter(config, errors)
    notifier = Notifier(telegram, screenshotter)
    gpu = GpuMonitor()
    context = WatchContext(config=config, notifier=notifier, telegram=telegram, gpu=gpu, errors=errors, storage=storage)
    manager = TaskManager(context)
    return Runtime(config, errors, storage, telegram, notifier, gpu, manager)
