"""Cold-start benchmark for the startup acceptance gate.

Usage (from the project root):
    python tests/startup_benchmark.py --source --runs 10
    python tests/startup_benchmark.py --packaged dist/YoutubeBatchDownloader/YouTubeBatchDownloader.exe --runs 10
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_once(command: list[str]) -> dict:
    temp_dir = ROOT / "tests" / "runtime_tmp" / ("startup-benchmark-" + uuid.uuid4().hex)
    temp_dir.mkdir(parents=True, exist_ok=True)
    marker = temp_dir / "startup.json"
    process = subprocess.Popen(
        command + ["--startup-marker", str(marker)],
        cwd=ROOT,
        env=dict(
            os.environ,
            QT_QPA_PLATFORM="offscreen",
            TEMP=str(ROOT / "tests" / "runtime_tmp"),
            TMP=str(ROOT / "tests" / "runtime_tmp"),
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    start = time.perf_counter()
    try:
        while time.perf_counter() - start < 30 and not marker.exists():
            time.sleep(0.025)
        if not marker.exists():
            raise RuntimeError("startup marker was not written within 30 seconds")
        for _ in range(40):
            try:
                return json.loads(marker.read_text(encoding="utf-8"))
            except (PermissionError, json.JSONDecodeError):
                time.sleep(0.025)
        raise RuntimeError("startup marker could not be read")
    finally:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        shutil.rmtree(temp_dir, ignore_errors=True)


def summarize(samples: list[dict]) -> None:
    values = [float(item["stages_ms"]["first_paint"]) / 1000 for item in samples]
    ordered = sorted(values)
    p90 = ordered[max(0, int(len(ordered) * 0.9) - 1)]
    print(json.dumps({
        "runs": len(values),
        "median_seconds": round(statistics.median(values), 3),
        "p90_seconds": round(p90, 3),
        "maximum_seconds": round(max(values), 3),
        "raw_seconds": [round(value, 3) for value in values],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", action="store_true")
    group.add_argument("--packaged", type=Path)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 10:
        parser.error("--runs must be at least 10 for the acceptance benchmark")
    command = ["python", "app/main.py"] if args.source else [str(args.packaged.resolve())]
    samples = [run_once(command) for _ in range(args.runs)]
    summarize(samples)


if __name__ == "__main__":
    main()
