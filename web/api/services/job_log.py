"""Capture stdout/stderr for web-submitted jobs."""

from __future__ import annotations

import io
import sys
import threading
from contextlib import contextmanager
from typing import TextIO


class JobLogBuffer:
    """Thread-safe rolling buffer for job execution output."""

    def __init__(self, *, max_chars: int = 200_000) -> None:
        self._lines: list[str] = []
        self._lock = threading.Lock()
        self._max_chars = max_chars

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            for line in text.splitlines():
                if line:
                    self._lines.append(line)
            while self._char_count() > self._max_chars and self._lines:
                self._lines.pop(0)

    def text(self) -> str:
        with self._lock:
            return "\n".join(self._lines)

    def _char_count(self) -> int:
        return sum(len(line) + 1 for line in self._lines)


class _TeeStream(io.TextIOBase):
    def __init__(self, *, buffer: JobLogBuffer, forward: TextIO) -> None:
        self._buffer = buffer
        self._forward = forward
        self._pending = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._forward.write(text)
        self._forward.flush()
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._buffer.append(line)
        return len(text)

    def flush(self) -> None:
        self._forward.flush()
        if self._pending:
            self._buffer.append(self._pending)
            self._pending = ""


@contextmanager
def capture_job_output(buffer: JobLogBuffer):
    """Mirror process stdout/stderr into a job log buffer."""
    tee_out = _TeeStream(buffer=buffer, forward=sys.__stdout__)
    tee_err = _TeeStream(buffer=buffer, forward=sys.__stderr__)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = tee_out
    sys.stderr = tee_err
    try:
        yield buffer
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        tee_out.flush()
        tee_err.flush()
