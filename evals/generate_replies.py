#!/usr/bin/env python3
"""Generate and grade replies for evals/evals.json in the skill-creator workspace layout.

For each prompt it runs `claude -p` once per arm and writes
    <out>/<eval-name>/<arm>/outputs/response.md, timing.json, grading.json
plus <out>/<eval-name>/eval_metadata.json. Arms:
    with_skill     the skill under test (--skill)
    old_skill      the previous version (--old-skill), optional
    without_skill  no system prompt (Claude Code's default)

Usage: python3 generate_replies.py OUT_DIR --skill path/SKILL.md [--old-skill path/SKILL.md] [--workers 8]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("LEMBAS_EVAL_MODEL", "claude-opus-5-5")
PROBLEM_CATEGORIES = {"troubleshooting", "comparison", "safety", "advice"}
OPENERS = re.compile(r"^(great|good|excellent) question|^(sure|certainly|absolutely|of course)\b|^i'?d be happy|^let me", re.I)
CLOSERS = re.compile(r"(let me know|hope this helps|feel free to|happy to help|any (other )?questions)[^\n]*\s*$", re.I)


def body(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return text.split("---", 2)[2].strip() if text.startswith("---") else text


def call(prompt, system):
    args = ["claude", "-p", "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
            "--model", MODEL, "--output-format", "json"]
    if system:
        args += ["--system-prompt", system]
    args.append(prompt)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as cwd:
        p = subprocess.run(args, capture_output=True, text=True, cwd=cwd, stdin=subprocess.DEVNULL, timeout=600)
    r = json.loads(p.stdout)
    return r.get("result", ""), r.get("usage", {}).get("output_tokens", 0), time.time() - t0


def grade(ev, text):
    exp = []
    first = text.strip().split("\n", 1)[0]
    exp.append({"text": "Opens with the answer, no greeting or praise", "passed": not OPENERS.search(first.strip("*# ")),
                "evidence": first[:140]})
    exp.append({"text": "No closing offer of further help", "passed": not CLOSERS.search(text.strip()[-200:]),
                "evidence": text.strip()[-120:]})
    dashes = len(re.findall(r"[—–]", text))
    exp.append({"text": "No em or en dashes", "passed": dashes == 0, "evidence": f"dash count {dashes}"})
    for pat in ev.get("must_contain", []):
        m = re.search(pat, text, re.I)
        exp.append({"text": f"Keeps key fact: {pat}", "passed": bool(m), "evidence": m.group(0) if m else "not found"})
    if ev.get("category") in PROBLEM_CATEGORIES:
        parts = {p: bool(re.search(rf"\*\*{p}[^*\n]*\*\*", text)) for p in ("Problem", "Fix", "Alternatives", "Why")}
        exp.append({"text": "Has Problem, Fix, Alternatives and Why parts", "passed": all(parts.values()),
                    "evidence": ", ".join(f"{k}: {'yes' if v else 'no'}" for k, v in parts.items())})
        alt = re.search(r"\*\*Alternatives[^*]*\*\*(.*?)(\*\*Why|\Z)", text, re.S)
        cond = bool(alt and re.search(r"\b(if|when|unless|only)\b", alt.group(1), re.I))
        exp.append({"text": "Each alternative says when it wins", "passed": cond,
                    "evidence": (alt.group(1).strip()[:160] if alt else "no Alternatives section")})
    passed = sum(e["passed"] for e in exp)
    return {"expectations": exp, "summary": {"passed": passed, "failed": len(exp) - passed, "total": len(exp),
                                             "pass_rate": round(passed / len(exp), 3)}}


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--skill", required=True)
    ap.add_argument("--old-skill")
    ap.add_argument("--evals", default=os.path.join(HERE, "evals.json"))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    with open(a.evals, encoding="utf-8") as fh:
        data = json.load(fh)
    evals = data["evals"] if isinstance(data, dict) else data
    arms = {"with_skill": body(a.skill), "without_skill": None}
    if a.old_skill:
        arms["old_skill"] = body(a.old_skill)
    jobs = [(ev, arm) for ev in evals for arm in arms]

    def work(job):
        ev, arm = job
        name = ev.get("name") or ev.get("eval_name") or f"eval-{ev['id']}"
        d = os.path.join(a.out, name)
        os.makedirs(os.path.join(d, arm, "outputs"), exist_ok=True)
        write_json(os.path.join(d, "eval_metadata.json"), {"eval_id": ev["id"], "eval_name": name, "prompt": ev["prompt"],
                                                           "assertions": ev.get("must_contain", [])})
        try:
            text, out_tokens, secs = call(ev["prompt"], arms[arm])
        except Exception as exc:  # a timeout or a reply that is not JSON must not stop the other jobs
            return name, arm, f"error: {type(exc).__name__}"
        with open(os.path.join(d, arm, "outputs", "response.md"), "w", encoding="utf-8") as f:
            f.write(text)
        write_json(os.path.join(d, arm, "timing.json"),
                   {"total_tokens": out_tokens, "duration_ms": int(secs * 1000), "total_duration_seconds": round(secs, 1)})
        g = grade(ev, text)
        write_json(os.path.join(d, arm, "grading.json"), g)
        return name, arm, f"{out_tokens:6} out tokens  pass {g['summary']['pass_rate']:.0%}"

    with ThreadPoolExecutor(a.workers) as ex:
        for name, arm, status in ex.map(work, jobs):
            print(f"{name:34} {arm:14} {status}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
