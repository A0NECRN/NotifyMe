from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable

from .errors import ErrorRecorder


def retry(error_recorder: ErrorRecorder, max_retries: int = 3, delay: float = 2, backoff: float = 2):
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            log = logging.getLogger(func.__module__)
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if attempt >= max_retries:
                        error_recorder.record("API_RETRY_EXHAUSTED", f"{func.__name__}: {exc}")
                        log.error("%s failed after %s attempts: %s", func.__name__, max_retries, exc)
                        raise
                    log.warning("%s retry %s/%s: %s", func.__name__, attempt, max_retries, exc)
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper

    return decorator
