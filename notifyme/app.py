from __future__ import annotations

import logging
import platform
import signal
import sys
import threading
from datetime import datetime

from .commands import CommandHandler, TelegramCommandReceiver
from .config import validate_config
from .menu import MAIN_MENU
from .runtime import build_runtime
from .text import html_escape


def main() -> int:
    runtime = build_runtime()
    config = runtime.config
    log = logging.getLogger("notifyme")
    errors = runtime.errors

    config_errors = validate_config(config)
    if config_errors:
        for item in config_errors:
            print(f"ERROR: {item}")
        return 1

    handler = CommandHandler(runtime.manager, runtime.telegram, runtime.notifier, runtime.gpu)
    receiver = TelegramCommandReceiver(runtime.telegram, handler)
    stop_event = threading.Event()

    def shutdown(signum=None, frame=None):
        log.info("Shutdown requested")
        stop_event.set()
        runtime.manager.stop_all()
        try:
            runtime.telegram.send_message("NotifyMe stopped.")
        except Exception as exc:
            logging.getLogger(__name__).debug("Stop notification failed: %s", exc)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 55)
    print("  NotifyMe - Telegram Task Monitor")
    print("=" * 55)

    try:
        runtime.telegram.send_message(
            "<b>NotifyMe started</b>\n"
            f"<b>Host:</b> {html_escape(platform.node())}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "点下面按钮，或直接发：运行 python train.py",
            reply_markup=MAIN_MENU,
        )
    except Exception as exc:
        log.error("Startup notification failed: %s", exc)
        errors.record("STARTUP_NOTIFY", str(exc))

    receiver.run_forever(stop_event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
