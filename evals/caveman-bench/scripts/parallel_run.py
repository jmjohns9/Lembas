"""Parallel wrapper around caveman's evals/llm_run.py.
Uses its run_claude() unchanged (same isolation flags, same system prompts),
just runs (prompt, arm) calls concurrently. Writes the same snapshot format."""
import datetime as dt, json, os, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
repo = Path(sys.argv[1]); out = Path(sys.argv[2]); skills = sys.argv[3].split(",")
sys.path.insert(0, str(repo / "evals"))
import llm_run as L
prompts = [p.strip() for p in L.PROMPTS.read_text().splitlines() if p.strip()]
systems = {"__baseline__": None, "__terse__": L.TERSE_PREFIX}
for s in skills:
    systems[s] = f"{L.TERSE_PREFIX}\n\n{(L.SKILLS / s / 'SKILL.md').read_text()}"
jobs = [(arm, i) for arm in systems for i in range(len(prompts))]
results = {arm: [None]*len(prompts) for arm in systems}
def work(job):
    arm, i = job
    with tempfile.TemporaryDirectory(prefix="caveman-eval-") as cwd:
        return arm, i, L.run_claude(prompts[i], cwd, system=systems[arm])
with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "10"))) as ex:
    for arm, i, text in ex.map(work, jobs):
        results[arm][i] = text
        print(f"done {arm} #{i}", flush=True)
snap = {"metadata": {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "claude_cli_version": L.claude_version(), "model": os.environ.get("CAVEMAN_EVAL_MODEL", "default"),
        "n_prompts": len(prompts), "terse_prefix": L.TERSE_PREFIX}, "prompts": prompts, "arms": results}
out.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
print("wrote", out)
