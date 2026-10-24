#!/usr/bin/env python3
"""Reference solver for exact integer span reconstruction."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "integer-span-v1"
TOP_KEYS = {"schema", "point_count", "distances"}
MIN_POINTS = 8
MAX_POINTS = 16
MAX_DISTANCE = 1_000_000_000


class Refused(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise Refused("duplicate object key")
        payload[key] = value
    return payload


def parse_input(path: Path) -> tuple[int, list[int]]:
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except OSError as exc:
        raise Refused("input cannot be read") from exc
    except json.JSONDecodeError as exc:
        raise Refused("input is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != TOP_KEYS:
        raise Refused("top-level keys do not match integer-span-v1")
    if payload.get("schema") != SCHEMA:
        raise Refused("unsupported schema")
    count = payload.get("point_count")
    if isinstance(count, bool) or not isinstance(count, int):
        raise Refused("point_count must be an integer")
    if not MIN_POINTS <= count <= MAX_POINTS:
        raise Refused("point_count is outside the allowed range")
    raw = payload.get("distances")
    expected = count * (count - 1) // 2
    if not isinstance(raw, list) or len(raw) != expected:
        raise Refused("distance count does not match point_count")
    distances: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise Refused("distances must be integers")
        if not 1 <= value <= MAX_DISTANCE:
            raise Refused("distance is outside the allowed range")
        distances.append(value)
    return count, distances


def _reconstruct(count: int, distances: list[int]) -> tuple[int, ...]:
    target = Counter(distances)
    span = max(distances)
    remaining = target.copy()
    remaining[span] -= 1
    if remaining[span] == 0:
        del remaining[span]
    total_left = len(distances) - 1
    solutions: set[tuple[int, ...]] = set()

    def search(positions: list[int], left: int) -> None:
        if len(positions) == count:
            if left == 0:
                solutions.add(tuple(positions))
            return
        if left == 0:
            return
        largest = max(value for value, amount in remaining.items() if amount > 0)
        for candidate in {largest, span - largest}:
            if not 0 < candidate < span or candidate in positions:
                continue
            differences = [abs(candidate - value) for value in positions]
            if any(remaining[value] <= 0 for value in differences):
                continue
            for value in differences:
                remaining[value] -= 1
            search(sorted(positions + [candidate]), left - len(differences))
            for value in differences:
                remaining[value] += 1

    search([0, span], total_left)
    if not solutions:
        raise Refused("no integer span matches the distance multiset")
    return min(
        solutions,
        key=lambda points: (
            sum(
                (points[index + 1] - points[index]) ** 2
                for index in range(len(points) - 1)
            ),
            points,
        ),
    )


def solve(count: int, distances: list[int]) -> dict[str, object]:
    positions = _reconstruct(count, distances)
    gaps = [
        positions[index + 1] - positions[index]
        for index in range(len(positions) - 1)
    ]
    return {
        "positions": list(positions),
        "gaps": gaps,
        "gap_energy": sum(value * value for value in gaps),
        "distance_total": sum(distances),
        "span": positions[-1],
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("REFUSED: expected input and output paths", file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    try:
        count, distances = parse_input(source)
        result = solve(count, distances)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
