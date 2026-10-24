from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_outputs import ENTRY, _payload, _run, _write_json  # noqa: E402


def _solve(tmp_path: Path, label: str, points: list[int]) -> dict[str, object]:
    source = tmp_path / f"{label}.json"
    output = tmp_path / f"{label}-result.json"
    _write_json(source, _payload(points))
    completed = _run(source, output)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    return json.loads(output.read_text(encoding="utf-8"))


def test_two_unseen_distance_tables_cannot_use_fixed_results(tmp_path: Path) -> None:
    first_points = [0, 3, 8, 17, 29, 44, 62, 83]
    second_points = [0, 5, 12, 21, 35, 52, 74, 101]

    first = _solve(tmp_path, "span-a", first_points)
    second = _solve(tmp_path, "span-b", second_points)

    assert first["positions"] == first_points
    assert first["span"] == first_points[-1]
    assert second["positions"] == second_points
    assert second["span"] == second_points[-1]
    assert first["positions"] != second["positions"]
    assert first["gap_energy"] != second["gap_energy"]

