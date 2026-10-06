"""Batched, append-only decision log (flushes every 50 rows or 5 seconds)."""

from __future__ import annotations

import atexit
import logging
import threading
from typing import Any

from pecca.connectors.base import Registry

log = logging.getLogger("pecca")
BATCH = 50
INTERVAL_S = 5.0


class LogSink:
    def __init__(
        self, registry: Registry, path_key: str, batch: int = BATCH, interval_s: float = INTERVAL_S
    ) -> None:
        self.registry, self.key, self.batch, self.interval = registry, path_key, batch, interval_s
        self._rows: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        atexit.register(self.flush)

    def add(self, row: dict[str, Any]) -> None:
        with self._lock:
            self._rows.append(row)
            full = len(self._rows) >= self.batch
        if full:
            self.flush()
        else:
            self._ensure_thread()

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True, name="pecca-log-flush")
            self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self.flush()

    def flush(self) -> None:
        with self._lock:
            rows, self._rows = self._rows, []
        if not rows:
            return
        try:
            self.registry.append_logs(self.key, rows)
        except Exception as e:  # noqa: BLE001 - logging must never break user code
            log.error("pecca: failed to write %d log rows: %s", len(rows), e)

    def close(self) -> None:
        self._stop.set()
        self.flush()


_sinks: dict[tuple[int, str], LogSink] = {}
_lock = threading.Lock()


def get_sink(registry: Registry, path_key: str) -> LogSink:
    k = (id(registry), path_key)
    with _lock:
        if k not in _sinks:
            _sinks[k] = LogSink(registry, path_key)
        return _sinks[k]


def flush_all() -> None:
    with _lock:
        sinks = list(_sinks.values())
    for s in sinks:
        s.flush()


def reset() -> None:
    with _lock:
        for s in _sinks.values():
            s.close()
        _sinks.clear()
