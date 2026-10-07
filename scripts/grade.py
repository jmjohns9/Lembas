#!/usr/bin/env python3
"""Check that Lembas replies keep key facts and drop filler.

Usage: python3 scripts/grade.py evals/evals.json evals/results/v1.0.0

For every eval it checks the reply against:
  * each must_contain regex from evals.json (facts that must survive)
  * no greeting or praise in the first line
  * no closing offer of help in the last line
  * no em or en dashes
Exits non-zero if any lembas.md reply fails a check.
"""
import json
import pathlib
import re
import sys

OPENERS = re.compile(r"^(sure|great|good question|hi!|hello|certainly|absolutely)", re.I)
CLOSERS = re.compile(r"(let me know|happy to|want me to|i can also|hope this helps)", re.I)


def checks(text, must_contain):
    lines = [line for line in text.strip().splitlines() if line.strip()]
    results = [
        ("opens with the answer", not OPENERS.match(lines[0].strip())),
        ("no closing offer", not CLOSERS.search(lines[-1])),
        ("no em or en dashes", "—" not in text and "–" not in text),
    ]
    for pattern in must_contain:
        results.append((f"keeps /{pattern}/", re.search(pattern, text, re.I) is not None))
    return results


def main():
    evals = json.loads(pathlib.Path(sys.argv[1]).read_text())["evals"]
    results_dir = pathlib.Path(sys.argv[2])
    totals = {"baseline": [0, 0], "lembas": [0, 0]}
    failed_lembas = False
    for ev in evals:
        for variant in ("baseline", "lembas"):
            reply = results_dir / ev["name"] / f"{variant}.md"
            if not reply.exists():
                continue
            for label, ok in checks(reply.read_text(), ev["must_contain"]):
                totals[variant][0] += ok
                totals[variant][1] += 1
                if not ok:
                    print(f"FAIL {variant:8} {ev['name']}: {label}")
                    failed_lembas |= variant == "lembas"
    for variant, (passed, total) in totals.items():
        print(f"{variant:8} {passed}/{total} checks passed")
    sys.exit(1 if failed_lembas else 0)


if __name__ == "__main__":
    main()
