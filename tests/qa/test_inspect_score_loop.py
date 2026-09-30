# SPDX-License-Identifier: Apache-2.0
"""Automated inspect/score/correction-loop coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from conftest import run_script
from sprite_gen.qa import inspect, score


def test_inspect_scores_extracted_fixture(fixture_run_dir: Path) -> None:
    extract = run_script("extract_sprite_row_frames.py", "--run-dir", str(fixture_run_dir))
    assert extract.returncode == 0, extract.stdout + extract.stderr

    inspected = run_script("inspect_sprite_run.py", "--run-dir", str(fixture_run_dir))
    assert inspected.returncode == 0, inspected.stdout + inspected.stderr
    inspect_report = json.loads((fixture_run_dir / "sprite-inspect.report.json").read_text(encoding="utf-8"))
    assert inspect_report["kind"] == "sprite-gen-inspect-report"
    assert inspect_report["rows"][0]["metrics"]["histogram_intersection"]["min"] <= 1.0
    assert inspect_report["rows"][0]["metrics"]["dhash_similarity"]["min"] <= 1.0
    assert "motion_presence" in inspect_report["rows"][0]["metrics"]
    assert inspect_report["rows"][0]["metrics"]["content_scale"]["median_height"] > 0

    scored = run_script(
        "score_sprite_run.py",
        "--inspect-report", str(fixture_run_dir / "sprite-inspect.report.json"),
    )
    assert scored.returncode == 0, scored.stdout + scored.stderr
    score_report = json.loads((fixture_run_dir / "sprite-score.report.json").read_text(encoding="utf-8"))
    assert score_report["ok"] is True
    assert score_report["overall_score"] >= 90


def test_cross_direction_scale_drift_fails_and_produces_regeneration_hint() -> None:
    request = {"directions": {"set": ["south", "east", "north", "west"]}}
    rows = [
        {
            "state": state,
            "metrics": {
                "content_scale": {
                    "median_height": linear_size,
                    "minimum_to_maximum_height_ratio": 0.8,
                }
            },
            "ok": True,
            "errors": [],
            "warnings": [],
            "expected_frames": 4,
            "found_frames": 4,
        }
        for state, linear_size in (
            ("south_attack", 98.0),
            ("east_attack", 80.5),
            ("north_attack", 103.0),
            ("west_attack", 101.5),
        )
    ]
    errors: list[str] = []

    inspect._apply_cross_direction_scale_gate(rows, request, errors)

    east = next(row for row in rows if row["state"] == "east_attack")
    assert east["ok"] is False
    assert east["metrics"]["cross_direction_scale"]["ratio"] < 0.85
    assert any("cross-direction content scale" in message for message in east["errors"])
    scored = score.score_inspection(
        {
            "run_dir": "/fixture",
            "thresholds": {},
            "rows": rows,
        }
    )
    assert scored["ok"] is False
    assert any("shared body scale" in hint for hint in scored["hints"])


def test_raw_frame_count_defect_produces_correction_hint(fixture_run_dir: Path) -> None:
    request_path = fixture_run_dir / "sprite-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["states"] = {"walk": {**request["states"]["walk"], "frames": 5}}
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    inspected = run_script("inspect_sprite_run.py", "--run-dir", str(fixture_run_dir), "--states", "walk")
    assert inspected.returncode == 1
    scored = run_script(
        "score_sprite_run.py",
        "--inspect-report", str(fixture_run_dir / "sprite-inspect.report.json"),
    )
    assert scored.returncode == 1
    score_report = json.loads((fixture_run_dir / "sprite-score.report.json").read_text(encoding="utf-8"))
    assert score_report["ok"] is False
    assert any("exactly 5 full-body poses" in hint for hint in score_report["hints"])


def test_correction_loop_dry_run_preserves_best_candidate(fixture_run_dir: Path, tmp_path: Path) -> None:
    request_path = fixture_run_dir / "sprite-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["states"] = {"walk": {**request["states"]["walk"], "frames": 5}}
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = tmp_path / "loop"
    result = run_script(
        "run_correction_loop.py",
        "--run-dir", str(fixture_run_dir),
        "--states", "walk",
        "--out-dir", str(out_dir),
        "--dry-run",
    )
    assert result.returncode == 1
    loop_report = json.loads((out_dir / "correction-loop.report.json").read_text(encoding="utf-8"))
    assert loop_report["dry_run"] is True
    assert Path(loop_report["preserved_best"]).is_dir()
    assert "exactly 5 full-body poses" in (out_dir / "attempt-1" / "correction-hints.txt").read_text(encoding="utf-8")


def test_correction_loop_min_attempts_forces_provider_then_converges(fixture_run_dir: Path, tmp_path: Path) -> None:
    extract = run_script("extract_sprite_row_frames.py", "--run-dir", str(fixture_run_dir))
    assert extract.returncode == 0, extract.stdout + extract.stderr
    provider = tmp_path / "copy_provider.py"
    provider.write_text(
        "import shutil,sys\nshutil.copytree(sys.argv[1], sys.argv[2])\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "loop"
    result = run_script(
        "run_correction_loop.py",
        "--run-dir", str(fixture_run_dir),
        "--states", "walk",
        "--out-dir", str(out_dir),
        "--max-passes", "3",
        "--min-attempts", "2",
        "--provider-command", f'"{sys.executable}" "{provider}" "{fixture_run_dir}" "{{next_run_dir}}"',
    )
    assert result.returncode == 0, result.stdout + result.stderr
    loop_report = json.loads((out_dir / "correction-loop.report.json").read_text(encoding="utf-8"))
    assert loop_report["min_attempts"] == 2
    assert len(loop_report["attempts"]) == 2
    assert loop_report["attempts"][1]["ok"] is True
    assert not (out_dir / "candidate-3").exists()


def test_correction_loop_does_not_generate_after_last_attempt(fixture_run_dir: Path, tmp_path: Path) -> None:
    request_path = fixture_run_dir / "sprite-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["states"] = {"walk": {**request["states"]["walk"], "frames": 5}}
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_dir = tmp_path / "loop"
    result = run_script(
        "run_correction_loop.py",
        "--run-dir", str(fixture_run_dir),
        "--states", "walk",
        "--out-dir", str(out_dir),
        "--max-passes", "1",
        "--provider-command", f'"{sys.executable}" -c "raise SystemExit(9)"',
    )
    assert result.returncode == 1
    assert not (out_dir / "attempt-1" / "provider.log").exists()
