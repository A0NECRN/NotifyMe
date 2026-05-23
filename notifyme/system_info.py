from __future__ import annotations

import logging
import warnings

import psutil


class GpuMonitor:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.pynvml = None
        self.available = False
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                import pynvml

            pynvml.nvmlInit()
            self.pynvml = pynvml
            self.available = True
        except ImportError:
            self.log.info("pynvml is not installed; GPU monitoring disabled")
        except Exception as exc:
            self.log.warning("GPU initialization failed: %s", exc)

    def usage(self, index: int = 0) -> int:
        if not self.available or self.pynvml is None:
            return 0
        handle = self.pynvml.nvmlDeviceGetHandleByIndex(index)
        return int(self.pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)

    def stats(self) -> list[dict]:
        if not self.available or self.pynvml is None:
            return []
        items: list[dict] = []
        for index in range(self.pynvml.nvmlDeviceGetCount()):
            handle = self.pynvml.nvmlDeviceGetHandleByIndex(index)
            name = self.pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            utilization = self.pynvml.nvmlDeviceGetUtilizationRates(handle)
            memory = self.pynvml.nvmlDeviceGetMemoryInfo(handle)
            items.append(
                {
                    "index": index,
                    "name": name,
                    "usage": int(utilization.gpu),
                    "mem_used": int(memory.used // (1024 * 1024)),
                    "mem_total": int(memory.total // (1024 * 1024)),
                }
            )
        return items


def cpu_stats() -> dict:
    return {
        "usage": psutil.cpu_percent(interval=1),
        "cores": psutil.cpu_count(logical=True),
    }
