from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .storage import Storage


WORKDIR_KEY = "default_workdir"


def get_default_workdir(config: AppConfig, storage: Storage) -> Path:
    value = storage.get_setting(WORKDIR_KEY, "")
    if value:
        return Path(value).expanduser()
    return config.app_dir


def set_default_workdir(storage: Storage, path_text: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"directory does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    storage.set_setting(WORKDIR_KEY, str(path))
    return path


def resolve_workdir(config: AppConfig, storage: Storage, cwd: str = "") -> Path:
    if cwd:
        path = Path(cwd).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"invalid working directory: {path}")
        return path
    return get_default_workdir(config, storage)
