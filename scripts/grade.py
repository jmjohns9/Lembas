#!/usr/bin/env python3
"""Check that Lembas replies keep key facts, follow the answer shape and drop filler.

Usage: python3 scripts/grade.py evals/evals.json evals/results/v2.0.0

For every eval it checks each reply (baseline.md, lembas.md) for:
  * required: each must_contain regex from evals.json (facts that must survive)
  * required for lembas.md on problem and choice prompts (troubleshooting, comparison, safety,
    advice): the four labeled parts Problem, Fix, Alternatives and Why
  * style: no greeting or praise in the first line, no closing offer of help, no em or en dashes

Exits non-zero if a lembas.md reply misses a required check. Style misses are printed as warnings.
"""
import json
import pathlib
import re
import sys

OPENERS = re.compile(r"^(sure|great|good question|hi!|hello|certainly|absolutely)", re.I)
CLOSERS = re.compile(r"(let me know|happy to|want me to|i can also|hope this helps)", re.I)
PROBLEM_CATEGORIES = {"troubleshooting", "comparison", "safety", "advice"}


def checks(text, ev, variant):
    lines = [line for line in text.strip().splitlines() if line.strip()]
    results = [
        ("style", "opens with the answer", not OPENERS.match(lines[0].strip(" *#"))),
        ("style", "no closing offer", not CLOSERS.search(lines[-1])),
        ("style", "no em or en dashes", "—" not in text and "–" not in text),
    ]
    for pattern in ev["must_contain"]:
        results.append(("required", f"keeps /{pattern}/", re.search(pattern, text, re.I) is not None))
    if variant == "lembas" and ev.get("category") in PROBLEM_CATEGORIES:
        for part in ("Problem", "Fix", "Alternatives", "Why"):
            results.append(("required", f"has the {part} part", re.search(rf"\*\*{part}[^*\n]*\*\*", text) is not None))
    return results


def main():
    evals = json.loads(pathlib.Path(sys.argv[1]).read_text())["evals"]
    results_dir = pathlib.Path(sys.argv[2])
    totals = {}
    failed = False
    for ev in evals:
        for variant in ("baseline", "lembas"):
            reply = results_dir / ev["name"] / f"{variant}.md"
            if not reply.exists():
                continue
            for kind, label, ok in checks(reply.read_text(), ev, variant):
                t = totals.setdefault(variant, [0, 0])
                t[0] += ok
                t[1] += 1
                if not ok:
                    level = "FAIL" if kind == "required" else "warn"
                    print(f"{level} {variant:8} {ev['name']}: {label}")
                    failed |= variant == "lembas" and kind == "required"
    for variant, (passed, total) in totals.items():
        print(f"{variant:8} {passed}/{total} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
