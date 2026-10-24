from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path


ENTRY = os.environ.get("SPAN_ENTRY", "/app/predict.py")

SAFE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
}
SCHEMA = "integer-span-v1"
PRIMARY = [0, 3, 7, 12, 20, 31, 45, 58, 76, 95, 119, 150]
FOUR_WAY_MIN = [0, 7, 15, 40, 44, 48, 73, 80]
REFLECTION_MIN = [0, 1, 3, 6, 10, 15, 21, 28]
UPPER = [0, 2, 5, 9, 14, 20, 27, 35, 44, 54, 65, 77, 90, 104, 119, 135]


def _run(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-S", "-P", "-B", ENTRY, str(source), str(output)],
        text=True,
        capture_output=True,
        env=SAFE_ENV,
        timeout=20,
        check=False,
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _distances(points: list[int]) -> list[int]:
    values = [
        points[right] - points[left]
        for left in range(len(points))
        for right in range(left + 1, len(points))
    ]
    random.Random(sum(points)).shuffle(values)
    return values


def _payload(points: list[int]) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "point_count": len(points),
        "distances": _distances(points),
    }


def _gaps(points: list[int]) -> list[int]:
    return [points[index + 1] - points[index] for index in range(len(points) - 1)]


def test_gate_reconstructs_integer_span(tmp_path: Path) -> None:
    """题面：「存在一组严格递增的整数坐标」"""
    # SPAN-GATE-01 SPAN-ENTRY-01 SPAN-CONTEXT-01 SPAN-CONTEXT-02 SPAN-STDLIB-01 SPAN-SOURCE-01
    source = tmp_path / "span.json"
    output = tmp_path / "result.json"
    _write_json(source, _payload(PRIMARY))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == PRIMARY
    assert result["span"] == 150


def test_primary_distance_table_recovers_exact_positions(tmp_path: Path) -> None:
    """题面：「按多重集恰好等于 `distances`」"""
    # SPAN-MAPPING-01 SPAN-MULTISET-01
    source = tmp_path / "span-a.json"
    output = tmp_path / "result-a.json"
    _write_json(source, _payload(PRIMARY))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == PRIMARY


def test_four_way_distance_table_minimizes_gap_energy(tmp_path: Path) -> None:
    """题面：「先比较全部可行序列的间隔平方和 `gap_energy = sum(gaps[i]^2)`，取最小者；」"""
    # SPAN-LEX-01
    source = tmp_path / "span-b.json"
    output = tmp_path / "result-b.json"
    _write_json(source, _payload([0, 7, 40, 44, 48, 65, 73, 80]))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == FOUR_WAY_MIN


def test_reflected_twin_uses_lexicographic_minimum(tmp_path: Path) -> None:
    """题面：「仍有并列时，再按 `positions[0]`、`positions[1]`、直到末项逐项比较，取字典序最小的那一组。」"""
    # SPAN-LEX-02 SPAN-ZERO-ANCHOR-01
    source = tmp_path / "span-c.json"
    output = tmp_path / "result-c.json"
    _write_json(source, _payload([0, 1, 3, 6, 10, 15, 21, 28]))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == REFLECTION_MIN


def test_gaps_span_and_distance_total_follow_positions(tmp_path: Path) -> None:
    """题面：「`gaps` 是相邻两点的正向间隔数组。」"""
    # SPAN-DERIVED-01
    source = tmp_path / "span-d.json"
    output = tmp_path / "result-d.json"
    payload = _payload(PRIMARY)
    _write_json(source, payload)
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["gaps"] == _gaps(PRIMARY)
    assert result["gap_energy"] == sum(value * value for value in _gaps(PRIMARY))
    assert result["span"] == PRIMARY[-1]
    assert result["distance_total"] == sum(payload["distances"])


def test_upper_bound_16_points_is_reconstructed(tmp_path: Path) -> None:
    """题面：「`point_count` 是 8 到 16 的整数」"""
    # SPAN-BOUND-HIGH
    source = tmp_path / "span-e.json"
    output = tmp_path / "result-e.json"
    _write_json(source, _payload(UPPER))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == UPPER
    assert len(result["positions"]) == 16


def test_output_is_compact_sorted_and_repeatable(tmp_path: Path) -> None:
    """题面：「把结果压成单行 JSON，键名按字典序落位，并用换行收尾；重复处理同一档案时，写出的字节要完全相同。」"""
    # SPAN-FORMAT-01 SPAN-REPEAT-01 SPAN-OUTPUT-KEYS-01 SPAN-OUTPUT-EXACT-01 SPAN-OUTPUT-TYPES-01
    source = tmp_path / "span-f.json"
    first = tmp_path / "result-f1.json"
    second = tmp_path / "result-f2.json"
    _write_json(source, _payload(REFLECTION_MIN))
    first_run = _run(source, first)
    second_run = _run(source, second)
    raw = first.read_bytes()
    parsed = json.loads(raw)
    canonical = (
        json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    assert first_run.returncode == 0
    assert second_run.returncode == 0
    assert set(parsed) == {
        "positions",
        "gaps",
        "gap_energy",
        "distance_total",
        "span",
    }
    assert raw == canonical
    assert raw == second.read_bytes()


def test_7_points_are_refused(tmp_path: Path) -> None:
    """题面：「`point_count` 是 8 到 16 的整数」"""
    # SPAN-BOUND-LOW-REJECT SPAN-BOUND-LOW-01 SPAN-INPUT-BOUNDARY-01 SPAN-REJECT-CHANNEL-01 SPAN-NO-OUTPUT-01
    source = tmp_path / "span-g.json"
    output = tmp_path / "result-g.json"
    _write_json(source, _payload([0, 1, 3, 6, 10, 15, 21]))
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_17_points_are_refused(tmp_path: Path) -> None:
    """题面：「`point_count` 是 8 到 16 的整数」"""
    # SPAN-BOUND-HIGH-REJECT SPAN-BOUND-HIGH-01
    points = [index * index + index for index in range(17)]
    source = tmp_path / "span-h.json"
    output = tmp_path / "result-h.json"
    _write_json(source, _payload(points))
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_wrong_distance_count_is_refused(tmp_path: Path) -> None:
    """题面：「`distances` 的长度必须等于 `point_count * (point_count - 1) / 2`。」"""
    # SPAN-COUNT-01
    payload = _payload(PRIMARY)
    payload["distances"] = payload["distances"][:-1]
    source = tmp_path / "span-i.json"
    output = tmp_path / "result-i.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_zero_distance_is_refused(tmp_path: Path) -> None:
    """题面：「每个距离都是 1 到 1000000000 的整数」"""
    # SPAN-RANGE-ZERO SPAN-RANGE-ZERO-01
    payload = _payload(PRIMARY)
    payload["distances"][0] = 0
    source = tmp_path / "span-j.json"
    output = tmp_path / "result-j.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_oversized_distance_is_refused(tmp_path: Path) -> None:
    """题面：「每个距离都是 1 到 1000000000 的整数」"""
    # SPAN-RANGE-HIGH SPAN-RANGE-HIGH-01
    payload = _payload(PRIMARY)
    payload["distances"][0] = 1_000_000_001
    source = tmp_path / "span-k.json"
    output = tmp_path / "result-k.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_distance_upper_bound_is_accepted(tmp_path: Path) -> None:
    """题面：「每个距离都是 1 到 1000000000 的整数」"""
    # SPAN-RANGE-HIGH-ACCEPT SPAN-RANGE-HIGH-ACCEPT-01
    points = [
        0,
        125_000_000,
        250_000_001,
        375_000_009,
        500_000_011,
        625_000_017,
        750_000_023,
        1_000_000_000,
    ]
    source = tmp_path / "span-range.json"
    output = tmp_path / "result-range.json"
    _write_json(source, _payload(points))
    completed = _run(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert result["positions"] == points
    assert result["span"] == 1_000_000_000


def test_boolean_distance_is_refused(tmp_path: Path) -> None:
    """题面：「布尔值不算整数」"""
    # SPAN-BOOL-01
    payload = _payload(PRIMARY)
    payload["distances"][0] = True
    source = tmp_path / "span-l.json"
    output = tmp_path / "result-l.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_impossible_distance_multiset_is_refused(tmp_path: Path) -> None:
    """题面：「没有任何整数坐标能复原这组距离，就不要落盘」"""
    # SPAN-NO-SOLUTION SPAN-NO-SOLUTION-01
    payload = {
        "schema": SCHEMA,
        "point_count": 8,
        "distances": [1] * 28,
    }
    source = tmp_path / "span-m.json"
    output = tmp_path / "result-m.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_extra_top_level_key_is_refused(tmp_path: Path) -> None:
    """题面：「顶层只允许 `schema`、`point_count`、`distances` 三个键；」"""
    # SPAN-TOP-EXTRA-01 SPAN-ROOT-01
    payload = _payload(PRIMARY)
    payload["station"] = "unexpected"
    source = tmp_path / "span-n.json"
    output = tmp_path / "result-n.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_missing_top_level_key_is_refused(tmp_path: Path) -> None:
    """题面：「顶层只允许 `schema`、`point_count`、`distances` 三个键；」"""
    # SPAN-TOP-MISSING-01 SPAN-ROOT-02
    payload = _payload(PRIMARY)
    del payload["schema"]
    source = tmp_path / "span-o.json"
    output = tmp_path / "result-o.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_wrong_schema_is_refused(tmp_path: Path) -> None:
    """题面：「`schema` 固定为 `"integer-span-v1"`。」"""
    # SPAN-SCHEMA-01
    payload = _payload(PRIMARY)
    payload["schema"] = "integer-span-v0"
    source = tmp_path / "span-p.json"
    output = tmp_path / "result-p.json"
    _write_json(source, payload)
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()


def test_duplicate_top_level_key_is_refused(tmp_path: Path) -> None:
    """题面：「同一个对象里重复写同名键也按损坏处理。」"""
    # SPAN-TOP-DUPLICATE-01 SPAN-ROOT-DUPLICATE-01
    encoded = json.dumps(_payload(PRIMARY))
    source = tmp_path / "span-q.json"
    output = tmp_path / "result-q.json"
    source.write_text(
        encoded[:-1] + ',"schema":"integer-span-v1"}',
        encoding="utf-8",
    )
    completed = _run(source, output)
    assert completed.returncode == 2
    assert completed.stderr.startswith("REFUSED: ")
    assert not output.exists()
