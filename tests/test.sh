#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
REWARD_FILE=/logs/verifier/reward.txt
RAW_REWARD_FILE=/logs/verifier/raw-reward.txt
JUNIT_FILE=/logs/verifier/junit.xml
SCORE_REPORT=/logs/verifier/scoring-report.json
STATUS_FILE=/logs/verifier/status.txt

write_reward() {
  chmod 0644 "$REWARD_FILE" 2>/dev/null || true
  printf '%s\n' "$1" > /logs/verifier/reward.txt
  chmod 0444 "$REWARD_FILE"
}

write_incomplete() {
  write_reward '0.000'
  printf 'INCOMPLETE: %s\n' "$1" > "$STATUS_FILE"
}

write_reward '0.000'
printf 'INCOMPLETE: verifier not started\n' > "$STATUS_FILE"
cleanup() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    write_incomplete "verifier exited unexpectedly with status $rc"
  fi
}
trap cleanup EXIT
trap 'write_incomplete "verifier interrupted"; exit 0' INT TERM HUP

set +e
timeout -s TERM 150s python3 -m pytest \
  -p no:cacheprovider \
  --junitxml="$JUNIT_FILE" \
  -rA \
  -vv /tests/test_outputs.py
pytest_rc=$?
set -e

python3 - "$JUNIT_FILE" /tests/test_outputs.py <<'PY'
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

junit = Path(sys.argv[1])
source = Path(sys.argv[2]).read_text(encoding="utf-8")
if junit.is_file():
    for testcase in ET.parse(junit).getroot().iter("testcase"):
        name = testcase.attrib.get("name", "")
        start = source.find(f"def {name}(")
        end = source.find("\ndef test_", start + 1)
        segment = source[start:end if end >= 0 else None]
        status = (
            "FAILED"
            if testcase.find("failure") is not None or testcase.find("error") is not None
            else "PASSED"
        )
        for case_id in sorted(
            set(re.findall(r"[A-Z]+-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{2,}", segment))
        ):
            print(f"{case_id} {status}")
PY

if [ "$pytest_rc" -ne 0 ] || [ ! -s "$JUNIT_FILE" ]; then
  write_incomplete "pytest did not produce a complete report"
  exit 0
fi

set +e
timeout -s TERM 20s python3 /tests/score.py \
  --config /tests/scoring.json \
  --junit "$JUNIT_FILE" \
  --report-out "$SCORE_REPORT" \
  --reward-out "$RAW_REWARD_FILE"
score_rc=$?
set -e

if [ "$score_rc" -ne 0 ] || [ ! -s "$SCORE_REPORT" ]; then
  write_incomplete "weighted scorer did not complete"
  exit 0
fi

python3 - "$SCORE_REPORT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("status") != "COMPLETED":
    raise SystemExit("scoring report is incomplete")
PY

write_reward "$(cat "$RAW_REWARD_FILE")"
printf 'COMPLETED\n' > "$STATUS_FILE"
trap - EXIT INT TERM HUP
exit 0
