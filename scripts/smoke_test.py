#!/usr/bin/env python3
"""Quick smoke test – start the app and verify the health endpoint."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.request import urlopen


def main() -> int:
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "council.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd="/Users/bartu/Desktop/council",
    )

    try:
        for _ in range(30):
            time.sleep(0.5)
            try:
                with urlopen("http://127.0.0.1:8000/health", timeout=2) as resp:
                    if resp.status == 200:
                        print("OK – health endpoint returned 200")
                        print(resp.read().decode())
                        return 0
            except Exception:
                continue
        print("FAIL – health endpoint did not respond in time")
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        if stderr:
            print("--- uvicorn stderr ---")
            print(stderr)


if __name__ == "__main__":
    sys.exit(main())
