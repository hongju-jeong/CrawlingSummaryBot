from __future__ import annotations

import os
from pathlib import Path

from ...config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_runtime_profile() -> dict[str, object]:
    logical_cores = os.cpu_count() or 1
    physical_cores = _detect_physical_cores() or max(1, logical_cores // 2)
    memory_gb = _detect_memory_gb()

    recommended = {
        "crawler_processes": min(4, max(2, physical_cores // 2 or 1)),
        "crawler_concurrency_per_process": 8 if logical_cores >= 8 else 6 if logical_cores >= 4 else 4,
        "crawler_host_concurrency": 2,
        "report_worker_threads": min(8, max(4, physical_cores)),
    }

    explicit = {
        "crawler_processes": _is_explicit("APP_CRAWLER_PROCESSES"),
        "crawler_concurrency_per_process": _is_explicit("APP_CRAWLER_CONCURRENCY_PER_PROCESS"),
        "crawler_host_concurrency": _is_explicit("APP_CRAWLER_HOST_CONCURRENCY"),
        "report_worker_threads": _is_explicit("APP_REPORT_WORKER_THREADS"),
    }

    configured = {
        "crawler_processes": settings.crawler_processes,
        "crawler_concurrency_per_process": settings.crawler_concurrency_per_process,
        "crawler_host_concurrency": settings.crawler_host_concurrency,
        "report_worker_threads": settings.report_worker_threads,
    }

    effective = {
        key: configured[key] if explicit[key] else recommended[key]
        for key in recommended
    }

    return {
        "system": {
            "logical_cores": logical_cores,
            "physical_cores": physical_cores,
            "memory_gb": memory_gb,
        },
        "recommended": recommended,
        "configured": configured,
        "effective": effective,
        "explicit": explicit,
    }


def get_effective_crawler_processes() -> int:
    return int(get_runtime_profile()["effective"]["crawler_processes"])


def get_effective_crawler_concurrency_per_process() -> int:
    return int(get_runtime_profile()["effective"]["crawler_concurrency_per_process"])


def get_effective_crawler_host_concurrency() -> int:
    return int(get_runtime_profile()["effective"]["crawler_host_concurrency"])


def get_effective_report_worker_threads() -> int:
    return int(get_runtime_profile()["effective"]["report_worker_threads"])


def _is_explicit(env_key: str) -> bool:
    if env_key in os.environ:
        return True

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False

    prefix = f"{env_key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(prefix):
            return True
    return False


def _detect_memory_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None

    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                kb = int(parts[1])
                return round(kb / 1024 / 1024, 1)
    return None


def _detect_physical_cores() -> int | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return None

    physical_pairs: set[tuple[str, str]] = set()
    current_physical: str | None = None
    current_core: str | None = None

    for line in cpuinfo.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if current_physical is not None and current_core is not None:
                physical_pairs.add((current_physical, current_core))
            current_physical = None
            current_core = None
            continue

        if line.startswith("physical id"):
            current_physical = line.split(":", 1)[1].strip()
        elif line.startswith("core id"):
            current_core = line.split(":", 1)[1].strip()

    if current_physical is not None and current_core is not None:
        physical_pairs.add((current_physical, current_core))

    return len(physical_pairs) or None
