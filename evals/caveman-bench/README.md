# Caveman skill benchmark

Lembas tested on the skill benchmark that ships with [caveman](https://github.com/JuliusBrussee/caveman) (`evals/` in that repo). It asks 10 developer questions under three conditions:

| Arm | System prompt |
|---|---|
| `__baseline__` | none |
| `__terse__` | `Answer concisely.` |
| skill | `Answer concisely.` plus the skill's SKILL.md |

The honest score for a skill is how much it cuts **beyond the `Answer concisely.` control**, not beyond the baseline.

## Arm names in the snapshots

| File | `lembas` arm | `lembas10` arm | Other skill arms |
|---|---|---|---|
| `run1.json`, `run2.json` | v1.0.0 | | caveman, ultracave, megacave |
| `run3.json`, `run4.json` | v1.1.0 | v1.0.0 | ultracave |

## How it was run

1. Clone caveman and copy `skills/lembas/SKILL.md` into its `skills/lembas/` (and v1.0.0 into `skills/lembas10/` for a comparison arm).
2. Generate replies with `scripts/parallel_run.py`. It imports caveman's `evals/llm_run.py` and calls its `run_claude()` unchanged, with the same isolation flags and system prompts, only in parallel:
   ```bash
   CAVEMAN_EVAL_MODEL=claude-opus-5-5 python3 scripts/parallel_run.py <caveman-repo> run.json ultracave,lembas10,lembas
   ```
3. Score with caveman's own `evals/measure.py`.

### Tokenizer

Caveman's `measure.py` counts with OpenAI's `o200k_base` tokenizer. That download was blocked in the test environment, and it also misjudges non-English output. Megacave answers in Classical Chinese, and Chinese costs Claude far more tokens per idea than English, so `o200k_base` and character estimates both overstate megacave's savings.

The scores here use Anthropic's published Claude tokenizer instead. `scripts/tiktoken_claude_stub.py` stands in for the `tiktoken` module. To use it, save it as `tiktoken.py` in a folder, put `claude_tokenizer.json` beside it (extract `litellm/litellm_core_utils/tokenizers/anthropic_tokenizer.json` from the `litellm` wheel), `pip install tokenizers`, and run `measure.py` with that folder on `PYTHONPATH`.

That tokenizer is an older Claude version, so `scripts/live_usage.py` also asks Claude Code for real billed output tokens (`--output-format json`) on 3 of the questions. Those are the most reliable numbers here.

### Fidelity review

Caveman's benchmark doesn't check whether answers stay correct. In `fidelity/`, each packet shows the `Answer concisely.` reply as a reference plus anonymous, shuffled candidates. A separate reviewer graded each candidate as complete, minor gap or major gap, and listed errors. `key*.json` maps letters back to skills.

## Results

See [docs/BENCHMARKS.md](../../docs/BENCHMARKS.md#caveman-skill-benchmark).
