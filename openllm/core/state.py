"""状态管理 — 原子文件读写（参考 FreeRide 设计）"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path | str, default: Any = None) -> Any:
    """读取 JSON 文件，失败返回 default"""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path | str, data: Any) -> None:
    """原子写入 JSON 文件（tmp + rename），防止写中断导致文件损坏"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_data_dir() -> Path:
    """获取数据目录 ~/.openllm/"""
    data_dir = Path.home() / ".openllm"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def load_env_file(env_path: Path | str | None = None) -> dict[str, str]:
    """简易 .env 解析器（无外部依赖，参考 FreeRide 纯 Python 实现）"""
    if env_path is None:
        env_path = Path.cwd() / ".env"
    env_path = Path(env_path)
    if not env_path.exists():
        return {}
    
    result = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key:
                result[key] = val
    return result
