"""Small, dependency-free startup timing instrumentation.

The marker is opt-in (``--startup-marker <path>``) so normal launches do not
perform disk I/O for telemetry.  Timestamps are monotonic and expressed as
milliseconds from process start, which makes source and frozen measurements
directly comparable.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def marker_path_from_argv(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--startup-marker" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--startup-marker="):
            return arg.split("=", 1)[1]
    return None


class StartupClock:
    def __init__(self, marker_path: str | None = None):
        self.started = time.perf_counter()
        self.marker_path = marker_path
        self.stages: dict[str, float] = {}
        self.extra: dict = {}
        self.mark("process_start")

    def mark(self, name: str) -> float:
        elapsed_ms = round((time.perf_counter() - self.started) * 1000, 3)
        self.stages[name] = elapsed_ms
        return elapsed_ms

    def write(self, extra: dict | None = None) -> None:
        if not self.marker_path:
            return
        payload = {
            "pid": os.getpid(),
            "stages_ms": dict(self.stages),
            "total_ms": round((time.perf_counter() - self.started) * 1000, 3),
        }
        if extra:
            self.extra.update(extra)
        payload.update(self.extra)
        target = Path(self.marker_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(payload, output, indent=2)
            os.replace(temporary, target)
        finally:
            try:
                os.unlink(temporary)
            except OSError:
                pass
