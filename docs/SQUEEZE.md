# Squeeze: smaller tool outputs

Lembas 2.0 ships `squeeze.py`, a compressor for large logs, JSON and CSV, and an optional Claude Code hook that applies it automatically. Lembas's reply rules cut **output** tokens. Squeeze cuts **input** tokens: what Claude reads from tools before it answers.

Standard library only, Python 3.8 or later. Nothing is sent anywhere.

## What it keeps

| Input | Summary keeps | Typical size |
|---|---|---|
| Logs, test runs, build and install output | First and last lines, every distinct error with its stack trace and 3 lines of context, every distinct warning, counts for repeats, and the most common line patterns with counts | 1,000 to 1,500 tokens |
| JSON and JSONL | The structure with `jq` paths, every field with its type, how often it's present, its value range or top values, the first item, and every item that looks like a failure (an `error` field, a `status` of failed, a 4xx or 5xx code) with its identifying and error fields first | 500 to 1,500 tokens |
| CSV and TSV | Row and column counts, a profile per column (type, nulls, distinct values, min, max, mean, median and exact sum), rows with the wrong number of fields, a value that is 5× or more the next largest, and the first and last rows | 300 to 650 tokens |

Every summary starts with one line that says it is a summary, gives the original's size, and names the file holding the full original. Lines marked `L123` are line numbers in the original, so Claude can `sed -n '120,140p'` or `grep -n` it for anything the summary leaves out.

## Guarantees

- **Errors are never dropped silently.** Every distinct error message is shown with its trace, or the summary says how many more exist and how to list them.
- **The original is never changed.** Piped input is saved to `$LEMBAS_SQUEEZE_DIR` (default `$TMPDIR/lembas-squeeze`). The folder is readable by you only, because command output can contain secrets.
- **Code, diffs and prose pass through unchanged** unless you force a type. Squeezing code would break edits.
- **Small inputs pass through unchanged.** The default threshold is about 2,000 tokens.
- **If squeezing fails or saves less than 30%, the input is printed unchanged.** A parser bug can never hide output.
- **Output is deterministic**, so repeated reads don't break prompt caching.

## Use it by hand

```bash
python3 skills/lembas/scripts/squeeze.py app.log
./run_tests.sh 2>&1 | python3 skills/lembas/scripts/squeeze.py
curl -s https://api.example.com/orders | python3 skills/lembas/scripts/squeeze.py --type json
python3 skills/lembas/scripts/squeeze.py data.csv --budget 800 --stats
```

When the skill is active, Claude does this on its own for output it can't narrow in advance. The skill's "Reading large outputs" section tells it when.

## The Claude Code hook

`skills/lembas/hooks/squeeze_hook.py` runs after every Bash and Read call. When the result is a large log, JSON or CSV, Claude sees the summary instead of the raw text. Claude Code hooks can replace a tool's result before the model reads it; the hook returns a copy of the result with only the text replaced.

| Event | What the hook does |
|---|---|
| Bash finished | Squeezes stdout and stderr when they are large data. If Claude Code saved a huge output to a file, the hook summarizes the full file, not the truncated preview. |
| Read finished | Squeezes `.log`, `.out`, `.json`, `.jsonl`, `.ndjson`, `.csv` and `.tsv` files. Reads with an offset or limit are left alone, because they ask for exact lines. |
| Read about to run | A data file over Read's 256 KB limit would fail. The hook declines the read and gives Claude the summary and the path. |

Commands that already narrow their output (`grep`, `head`, `tail`, `sed`, `awk`, `cut`, `jq`, `sort`, `uniq`, `wc` and similar) are deliberate queries. The hook leaves them alone unless the result is over Claude Code's 30,000-character inline limit. Testing showed why this matters: an early version squeezed narrowed `grep` results, and Claude worked around it with extra commands that cost more than they saved.

### Install

```bash
python3 ~/.claude/skills/lembas/hooks/squeeze_hook.py --print-settings
```

Merge the JSON it prints into `~/.claude/settings.json` (all projects) or `.claude/settings.json` (one project).

### Turn it off or bypass it

- Prefix one command with `LEMBAS_RAW=1` to get its raw output: `LEMBAS_RAW=1 cat app.log`.
- Set `LEMBAS_SQUEEZE=0` to switch the hook off.
- `LEMBAS_SQUEEZE_BUDGET` and `LEMBAS_SQUEEZE_THRESHOLD` change the summary size and the size at which squeezing starts, in tokens.

## Should you install the hook?

Measured on 8 investigation tasks (details in [BENCHMARKS.md](BENCHMARKS.md#squeeze)):

- **Claude Opus 5.5 in Claude Code: the hook alone doesn't pay off.** Claude Code already queries before reading (`grep`, `| tail -100`, redirecting to a file) and caps what reaches the model, so large outputs rarely arrive whole. Total input with the hook was within 4% of plain Claude Code on large files and within 1% on mid-size files.
- **Claude Haiku 4.5: the hook cut input by 25% and cost by 17%,** and it answered 8 of 8 correctly against 7 of 8. Haiku reads raw output more often, and one task fell from 13 turns to 2.
- **The skill's guidance helped on Opus:** 10% to 15% less input and 10% to 19% lower cost across two rounds, mostly from fewer turns and shorter replies.

Install the hook if you use smaller models, raise Claude Code's output limits (`bashOutputMaxChars`), or regularly run commands with huge output such as test suites and builds. On Opus with default settings, the skill alone gets most of the benefit.

## Why a hook and not an HTTP proxy

The other way to compress tool output is a local HTTP proxy: point `ANTHROPIC_BASE_URL` at it, and it rewrites large `tool_result` blocks in each request before forwarding it to the API. That works with any client, but it has four problems the hook avoids.

- **It sees too little.** A request carries only the result text. Telling a log from source code you're about to edit means matching each result back to its `tool_use` block and guessing from there. The hook gets the tool name, the command and the file path directly, which is how it knows to leave `grep | head` and code alone.
- **It rewrites history on every turn.** The API is stateless, so the proxy has to re-squeeze every past result on every request, identically, or the prompt cache misses. The hook changes a result once, when it's produced, and Claude Code stores the squeezed version.
- **It sits in the credential path.** It handles your API key and every request, and it has to pass streaming responses through untouched. A hook only touches tool output.
- **It doesn't reach the Claude apps.** Neither does the hook, but the skill does: the "Reading large outputs" rules and `squeeze.py` work anywhere Claude can run code, including file uploads in the Claude apps.

A proxy is the better choice for one case: your own API application, where you control the tool loop. There, run each tool result through `squeeze.squeeze()` before appending it to `messages`. It does the same job without a proxy in the middle:

```python
from squeeze import squeeze
view, info = squeeze(result_text, name="orders.json")
content = view if view is not None else result_text  # None means pass through unchanged
```

## Limits

- Summaries are for finding things. Exact counts, sums and filters should be computed on the original; the CSV profile's sums are exact, but anything else needs the original.
- Detection is heuristic. A log in an unusual format may pass through unchanged; force it with `--type log`.
- MCP tool results are not squeezed yet. They are a likely next target, since connector results can't be narrowed with `grep` before they arrive.
