"""Ask Claude Code for real usage counts: same isolation flags as caveman's run_claude,
plus --output-format json so we get usage.output_tokens for the generated reply."""
import json, subprocess, sys, tempfile, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
repo=Path(sys.argv[1]); prompt_idx=[int(x) for x in sys.argv[2].split(",")]
sys.path.insert(0,str(repo/"evals")); import llm_run as L
sys.path.insert(0, sys.argv[3]); import tiktoken; enc=tiktoken.get_encoding("x")
prompts=[p.strip() for p in L.PROMPTS.read_text().splitlines() if p.strip()]
arms={"__terse__":L.TERSE_PREFIX}
for s in os.environ.get("ARMS","lembas,megacave,ultracave").split(","): arms[s]=f"{L.TERSE_PREFIX}\n\n{(L.SKILLS/s/'SKILL.md').read_text()}"
def go(job):
    arm,i=job
    with tempfile.TemporaryDirectory() as cwd:
        cmd=["claude","-p","--setting-sources","project","--strict-mcp-config","--disable-slash-commands","--output-format","json","--model","claude-opus-5-5","--system-prompt",arms[arm],prompts[i]]
        r=json.loads(subprocess.run(cmd,capture_output=True,text=True,cwd=cwd,stdin=subprocess.DEVNULL).stdout)
    text=r.get("result","")
    return arm,i,r["usage"]["output_tokens"],len(enc.encode(text)),len(text)
with ThreadPoolExecutor(12) as ex:
    rows=list(ex.map(go,[(a,i) for a in arms for i in prompt_idx]))
print(f"{'arm':10} {'prompt':>6} {'billed out':>10} {'tokenizer':>9} {'chars':>6}")
for a,i,o,t,c in rows: print(f"{a:10} {i:6} {o:10} {t:9} {c:6}")
json.dump(rows,open(sys.argv[4],"w"))
