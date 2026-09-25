# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from sprite_gen.spec.runio import _pid_alive, acquire_run_dir_lock, release_run_dir_lock, LOCK_FILENAME


def test_pid_alive_current_process() -> None:
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_dead_process() -> None:
    # A PID that cannot exist (very large number or negative/zero)
    assert _pid_alive(9_999_999) is False
    assert _pid_alive(-1) is False
    assert _pid_alive(0) is False


def test_acquire_run_dir_lock_reclaims_dead_pid(tmp_path: Path) -> None:
    run_dir = tmp_path / "test_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_file = run_dir / LOCK_FILENAME

    # Write a stale lock holding a dead PID
    dead_pid = 9_999_999
    lock_file.write_text(
        json.dumps({"owner": "dead_worker", "pid": dead_pid, "started": time.time() - 10}),
        encoding="utf-8",
    )

    # Should successfully reclaim the lock without crashing or being blocked
    acquired_lock = acquire_run_dir_lock(run_dir, owner="new_worker")
    try:
        assert acquired_lock.is_file()
        holder = json.loads(acquired_lock.read_text(encoding="utf-8"))
        assert holder["owner"] == "new_worker"
        assert holder["pid"] == os.getpid()
    finally:
        release_run_dir_lock(run_dir)
