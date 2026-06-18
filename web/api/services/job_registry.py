"""In-memory registry for web-submitted jobs."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

RuntimeStatus = Literal["queued", "running", "succeeded", "failed", "idle"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class RegistryEntry:
    id: str
    job_type: str
    status: RuntimeStatus
    source_url: str | None = None
    source_path: str | None = None
    job_dir: str | None = None
    error: str | None = None
    error_code: str | None = None
    hint: str | None = None
    log: str = ""
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)


class JobRegistry:
    """Thread-safe in-memory job registry."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        job_type: str,
        source_url: str | None = None,
        source_path: str | None = None,
    ) -> RegistryEntry:
        entry = RegistryEntry(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status="queued",
            source_url=source_url,
            source_path=source_path,
        )
        with self._lock:
            self._entries[entry.id] = entry
        return entry

    def get(self, job_id: str) -> RegistryEntry | None:
        with self._lock:
            return self._entries.get(job_id)

    def update(self, job_id: str, **fields: Any) -> RegistryEntry | None:
        with self._lock:
            entry = self._entries.get(job_id)
            if entry is None:
                return None
            for key, value in fields.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            entry.updated_at = _utc_now()
            return entry

    def list_entries(self) -> list[RegistryEntry]:
        with self._lock:
            return list(self._entries.values())

    def entry_by_job_dir(self, job_dir: str) -> RegistryEntry | None:
        normalized = job_dir.replace("\\", "/")
        with self._lock:
            for entry in self._entries.values():
                if entry.job_dir and entry.job_dir.replace("\\", "/") == normalized:
                    return entry
        return None


_registry = JobRegistry()


def get_registry() -> JobRegistry:
    return _registry
