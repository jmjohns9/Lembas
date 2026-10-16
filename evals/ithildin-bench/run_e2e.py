#!/usr/bin/env python3
"""End-to-end benchmark: Claude Code answering questions about long documents, with and without Ithildin.

Each run starts Claude Code headless (`claude -p`) in a fresh folder holding one document, with Bash,
Read, Grep and Glob allowed, and asks a question whose answer is in one or two sections. Two arms:

    default    plain Claude Code (it can use pdftotext, grep, Read with page ranges, and so on)
    ithildin   Ithildin's SKILL.md appended to the system prompt, ithildin.py available

Records billed usage from --output-format json and grades the answer against facts in the document.

Usage: python3 run_e2e.py DOC_DIR OUT.json [--reps 2] [--workers 6] [--arms default,ithildin]
DOC_DIR needs manual.pdf and manual.docx (tests/ithildin_fixtures.py) and rust-book.pdf
(The Rust Programming Language, built from github.com/rust-lang/book; see docs/ITHILDIN.md).
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
SKILL_DIR = os.path.join(ROOT, "skills", "ithildin")
SCRIPT = os.path.join(SKILL_DIR, "scripts", "ithildin.py")
MODEL = os.environ.get("LEMBAS_EVAL_MODEL", "claude-opus-5-5")


def all_of(*pats):
    return lambda t: all(re.search(p, t, re.I | re.S) for p in pats)


TASKS = [
    {"id": "manual-limits-warranty", "file": "manual.pdf",
     "prompt": "manual.pdf is the maintenance manual for our generator. What is the maximum coolant outlet "
               "temperature, and under what conditions is the warranty void?",
     "check": all_of(r"104", r"3,?200", r"high.altitude|altitude kit", r"coolant")},
    {"id": "manual-torque-table", "file": "manual.pdf",
     "prompt": "Per manual.pdf, what torque do the cylinder head bolts take, and in what tightening sequence?",
     "check": all_of(r"\b85\b", r"spiral", r"3 passes|three passes")},
    {"id": "manual-docx-parts", "file": "manual.docx",
     "prompt": "Using manual.docx: what's the part number for the oil filter, and how is the service interval defined?",
     "check": all_of(r"OF-7731-B", r"500", r"twelve months|12 months")},
    {"id": "rust-integers", "file": "rust-book.pdf",
     "prompt": "rust-book.pdf is The Rust Programming Language. According to the book, what integer type does Rust "
               "default to, and what happens on integer overflow in debug builds versus release builds?",
     "check": all_of(r"i32", r"panic", r"wrap")},
    {"id": "rust-ownership-rules", "file": "rust-book.pdf",
     "prompt": "rust-book.pdf is The Rust Programming Language. What are the ownership rules the book lists, word for word?",
     "check": all_of(r"each value in rust has an owner", r"only be one owner at a time",
                     r"owner goes out of scope, the value will be dropped")},
    {"id": "rust-errors", "file": "rust-book.pdf",
     "prompt": "In rust-book.pdf (The Rust Programming Language), how does the book divide errors into two kinds, "
               "and what does Rust provide for each?",
     "check": all_of(r"recoverable", r"unrecoverable", r"Result<T, ?E>|Result", r"panic!")},
]


def skill_prompt():
    text = open(os.path.join(SKILL_DIR, "SKILL.md")).read()
    text = text.split("---", 2)[2] if text.startswith("---") else text
    return text.replace("scripts/ithildin.py", SCRIPT)


def run_one(task, arm, rep, docs):
    work = tempfile.mkdtemp(prefix=f"ithildin-e2e-{task['id']}-")
    shutil.copy(os.path.join(docs, task["file"]), work)
    os.makedirs(os.path.join(work, ".claude"))
    json.dump({}, open(os.path.join(work, ".claude", "settings.json"), "w"))
    args = ["claude", "-p", "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
            "--model", MODEL, "--output-format", "json", "--allowedTools=Bash,Read,Grep,Glob"]
    if arm == "ithildin":
        args += ["--append-system-prompt", skill_prompt()]
    args.append(task["prompt"])
    env = dict(os.environ, ITHILDIN_CACHE=os.path.join(work, ".ithildin-cache"))
    t0 = time.time()
    try:
        p = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=900, env=env, stdin=subprocess.DEVNULL)
        r = json.loads(p.stdout)
    except Exception as exc:  # record the failure instead of losing the batch
        return {"task": task["id"], "arm": arm, "rep": rep, "error": repr(exc)[:300]}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    u = r.get("usage", {})
    answer = r.get("result", "") or ""
    total_in = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return {"task": task["id"], "arm": arm, "rep": rep, "seconds": round(time.time() - t0, 1),
            "input_tokens": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0), "total_input": total_in,
            "output_tokens": u.get("output_tokens", 0), "cost_usd": r.get("total_cost_usd"),
            "turns": r.get("num_turns"), "correct": bool(task["check"](answer)), "answer": answer}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docs")
    ap.add_argument("out")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--arms", default="default,ithildin")
    ap.add_argument("--tasks", default="")
    a = ap.parse_args()
    tasks = [t for t in TASKS if not a.tasks or t["id"] in a.tasks.split(",")]
    jobs = [(t, arm, rep) for rep in range(a.reps) for t in tasks for arm in a.arms.split(",")]
    results = []
    with ThreadPoolExecutor(a.workers) as ex:
        for res in ex.map(lambda j: run_one(j[0], j[1], j[2], a.docs), jobs):
            results.append(res)
            print(json.dumps({k: res.get(k) for k in ("task", "arm", "rep", "total_input", "cost_usd", "turns",
                                                        "correct", "error")}), flush=True)
            json.dump(results, open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
