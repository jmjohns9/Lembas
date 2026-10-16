#!/usr/bin/env python3
"""End-to-end benchmark: Claude Code investigating large files, with and without Lembas.

Each run starts Claude Code headless (`claude -p`) in a fresh folder holding one test file,
with Bash, Read, Grep and Glob allowed, and asks a realistic question about it. Four arms:

    default      plain Claude Code
    skill        Lembas SKILL.md appended to the system prompt (query-first guidance, squeeze.py available)
    hook         the squeeze hook installed in the project's .claude/settings.json, no skill
    skill+hook   both

Records billed usage (input, cache write, cache read, output tokens, cost, turns) from
--output-format json, and grades the final answer against facts planted in the file.

Usage: python3 run_e2e.py FIXTURE_DIR OUT.json [--reps 2] [--workers 6] [--arms default,skill,hook,skill+hook]
FIXTURE_DIR needs the generated files (tests/make_fixtures.py) plus real-npm-install.log and real-dpkg.log.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_DIR = next(p for p in (os.path.join(ROOT, "skills", "lembas"), os.path.join(ROOT, "lembas")) if os.path.isdir(p))
SQUEEZE = os.path.join(SKILL_DIR, "scripts", "squeeze.py")
HOOK = os.path.join(SKILL_DIR, "hooks", "squeeze_hook.py")
MODEL = os.environ.get("LEMBAS_EVAL_MODEL", "claude-opus-5-5")


def all_of(*pats):
    return lambda t: all(re.search(p, t, re.I | re.S) for p in pats)


TASKS = [
    {"id": "incident-log", "file": "app.log",
     "prompt": "Our payment service had an incident sometime yesterday; the service log is app.log in this folder. "
               "What was the first error, what caused it, and what happened after it? Give line numbers.",
     "check": all_of(r"customer_id", r"settle\.py|line 142", r"15,?87[45]", r"redis|6379", r"23[34]")},
    {"id": "failed-orders", "file": "orders.json",
     "prompt": "orders.json is a page of orders from our API. Which orders failed, and why did each one fail?",
     "check": all_of(r"ord_100037", r"ord_100211", r"ord_100402", r"ord_100588", r"card.declined",
                     r"fraud.check.timeout", r"address.invalid")},
    {"id": "sales-total", "file": "sales.csv",
     "prompt": "What is the total revenue in sales.csv, and is there anything wrong with the data I should fix before reporting it?",
     "check": all_of(r"25,?994,?741\.67|25\.99 ?(million|M)", r"987,?654|606[23]", r"\b12\b")},
    {"id": "event-errors", "file": "events.jsonl",
     "prompt": "events.jsonl is our analytics event stream. Were there any server errors in it? If so, when, and what was the message?",
     "check": all_of(r"upstream timeout", r"10:20|120[01]", r"14:25|330[01]")},
    {"id": "test-failures", "file": "run_tests.py",
     "prompt": "Run ./run_tests.py (our test suite) and tell me which tests fail and why.",
     "check": all_of(r"vat_rounding", r"23\.78|23\.79|rounding", r"retry_backoff", r"640", r"refresh_token_rotation",
                     r"\b500\b|kid")},
    {"id": "api-failures", "file": "fetch_orders.py",
     "prompt": "Run ./fetch_orders.py to pull today's orders from the API, then tell me which orders failed and why.",
     "check": all_of(r"ord_100037", r"ord_100211", r"ord_100402", r"ord_100588", r"card.declined",
                     r"fraud.check.timeout", r"address.invalid")},
    {"id": "npm-deprecations", "file": "real-npm-install.log",
     "prompt": "real-npm-install.log is the verbose output of an npm install. Which packages did npm warn are deprecated, and did the install succeed?",
     "check": all_of(r"acorn-import-assertions", r"har-validator", r"uuid", r"left-pad", r"request@?2\.88|\brequest\b",
                     r"188 packages|succe")},
    {"id": "dpkg-failures", "file": "real-dpkg.log",
     "prompt": "Check real-dpkg.log: did any package fail to install or configure? When was the last time packages were installed?",
     "check": all_of(r"\b(no|none|didn't|did not|zero|0)\b[^.]{0,80}(fail|error)|(fail|error)[^.]{0,40}\b(no|none)\b",
                     r"2026-10-0[27]|Oct(ober)? (2|7)")},
]


# Mid-size files sit under Claude Code's 256 KB Read limit and 30,000-character Bash limit,
# so nothing in Claude Code stops them from entering the context whole.
TASKS_MID = [
    {"id": "mid-incident-log", "file": "mid-app.log",
     "prompt": "mid-app.log is an excerpt of our payment service log around an incident. What was the first error, "
               "what caused it, and what happened after it?",
     "check": all_of(r"customer_id", r"settle\.py|line 142", r"redis|6379", r"23[34]")},
    {"id": "mid-failed-orders", "file": "mid-orders.json",
     "prompt": "mid-orders.json is a page of orders from our API. Which orders failed, and why did each one fail?",
     "check": all_of(r"ord_100037", r"ord_100211", r"card.declined", r"fraud.check.timeout")},
    {"id": "mid-sales-total", "file": "mid-sales.csv",
     "prompt": "What is the total revenue in mid-sales.csv, and is there anything wrong with the data I should fix before reporting it?",
     "check": all_of(r"5,?663,?877\.62|5\.66 ?(million|M)", r"\b3\b[^.]{0,60}(rep|blank|empty|missing|null)|(rep|blank|empty|missing|null)[^.]{0,60}\b3\b")},
]


def skill_prompt():
    text = open(os.path.join(SKILL_DIR, "SKILL.md")).read()
    text = text.split("---", 2)[2] if text.startswith("---") else text
    return text.replace("scripts/squeeze.py", SQUEEZE)


def run_one(task, arm, rep, fixtures):
    work = tempfile.mkdtemp(prefix=f"lembas-e2e-{task['id']}-")
    shutil.copy(os.path.join(fixtures, task["file"]), work)
    os.makedirs(os.path.join(work, ".claude"))
    settings = {}
    if "hook" in arm:
        cmd = f'python3 "{HOOK}"'
        settings = {"hooks": {
            "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": cmd}]}],
            "PostToolUse": [{"matcher": "Bash|Read", "hooks": [{"type": "command", "command": cmd}]}]}}
    json.dump(settings, open(os.path.join(work, ".claude", "settings.json"), "w"))
    args = ["claude", "-p", "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
            "--model", MODEL, "--output-format", "json", "--allowedTools=Bash,Read,Grep,Glob"]
    if "skill" in arm:
        args += ["--append-system-prompt", skill_prompt()]
    args.append(task["prompt"])
    env = dict(os.environ, LEMBAS_SQUEEZE_DIR=os.path.join(work, ".squeeze-cache"))
    t0 = time.time()
    try:
        p = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=900, env=env, stdin=subprocess.DEVNULL)
        r = json.loads(p.stdout)
    except Exception as exc:  # record the failure instead of losing the whole batch
        return {"task": task["id"], "arm": arm, "rep": rep, "error": repr(exc)[:300]}
    u = r.get("usage", {})
    answer = r.get("result", "") or ""
    total_in = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    shutil.rmtree(work, ignore_errors=True)
    return {"task": task["id"], "arm": arm, "rep": rep, "seconds": round(time.time() - t0, 1),
            "input_tokens": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0), "total_input": total_in,
            "output_tokens": u.get("output_tokens", 0), "cost_usd": r.get("total_cost_usd"),
            "turns": r.get("num_turns"), "correct": bool(task["check"](answer)), "answer": answer}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixtures")
    ap.add_argument("out")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--arms", default="default,skill,hook,skill+hook")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--suite", default="large", choices=["large", "mid"])
    a = ap.parse_args()
    pool = TASKS_MID if a.suite == "mid" else TASKS
    tasks = [t for t in pool if not a.tasks or t["id"] in a.tasks.split(",")]
    jobs = [(t, arm, rep) for rep in range(a.reps) for t in tasks for arm in a.arms.split(",")]
    results = []
    with ThreadPoolExecutor(a.workers) as ex:
        for res in ex.map(lambda j: run_one(j[0], j[1], j[2], a.fixtures), jobs):
            results.append(res)
            print(json.dumps({k: res.get(k) for k in ("task", "arm", "rep", "total_input", "cost_usd", "turns", "correct", "error")}), flush=True)
            json.dump(results, open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
