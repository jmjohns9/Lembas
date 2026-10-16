# Benchmarks

Lembas is measured three ways: reply length and quality on caveman's skill benchmark, fact checks on this repo's own prompts, and an end-to-end test of how much Claude Code reads while investigating large files. All runs used `claude-opus-5-5` unless noted.

## Replies: caveman's skill benchmark (v2.0.0)

Ten developer questions, answered in fresh `claude -p` sessions. Arms: no system prompt, a plain `Answer concisely.` control, and each skill added to that control. Tokens counted with Claude's tokenizer. Raw data in [evals/caveman-bench](../evals/caveman-bench) (runs 11 and 12).

### Length

| Arm | Shorter than "Answer concisely." (median), run 11 / run 12 | Shorter than no prompt (total), run 11 / run 12 |
|---|---:|---:|
| Lembas 1.1.0 | 48% / 47% | 69% / 69% |
| **Lembas 2.0.0** | **37% / 35%** | **61% / 62%** |
| ultracave | 34% / 35% | 56% / 60% |
| "Answer concisely." alone | | 37% / 38% |

### Quality (blind review)

Four reviewers, two per run, each saw anonymous, shuffled answers next to the full no-prompt answer. For each answer they recorded errors, missing points, a verdict, whether it explains why its fix is right, whether it gives alternatives with conditions, and a 1 to 5 score for how well it equips the asker to choose and act.

| Arm | Complete | Minor gap | Major gap | Answers with an error | Explains why | Alternatives with conditions | Decision quality |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Lembas 2.0.0** | **19 of 20** | 1 | 0 | **1** | **20 of 20** | **19 of 20** | **4.85** |
| ultracave | 17 of 20 | 3 | 0 | 4 | 18 of 20 | 15 of 20 | 4.45 |
| Lembas 1.1.0 | 12 of 20 | 8 | 0 | 2 | 17 of 20 | 14 of 20 | 3.90 |

The errors found: Lembas 2.0 said CORS is "enforced by the server's policy" (the browser enforces it; the server declares it). Ultracave twice overstated what debouncing prevents, implied queues give exactly-once delivery, and gave an imprecise React Compiler version requirement. Lembas 1.1 wrote ANALYZE where it meant EXPLAIN ANALYZE, and called congestion control "flow control".

**Reading it:** 2.0 gives up about 12 points of savings against 1.1 and buys back most of what 1.1 lost: completeness from 12 to 19 of 20, and decision quality from 3.90 to 4.85. It saves slightly more than ultracave while scoring higher on every quality measure.

## Replies: this repo's prompts (v2.0.0)

The 11 prompts in [`evals/evals.json`](../evals/evals.json), one reply per arm, graded by [`scripts/grade.py`](../scripts/grade.py). Replies are in [`evals/results/v2.0.0`](../evals/results/v2.0.0). Tokens are billed output tokens.

| Arm | Average reply | Key facts kept | Four-part structure on problem prompts |
|---|---:|---:|---:|
| No skill | 1,104 tokens | all | n/a |
| Lembas 1.1.0 | 414 tokens | all | 0 of 5 (not part of 1.1) |
| **Lembas 2.0.0** | **616 tokens** | **all** | **5 of 5** |

2.0 replies are 44% shorter than no-skill replies. Advice prompts grow the most under the four-part shape: the interview-prep reply is 948 tokens against 413 for 1.1. One 2.0 reply used two dashes, which the style rules forbid; no-skill replies had dashes in 6 of 11.

## Squeeze

### Compression

[`squeeze.py`](../skills/lembas/scripts/squeeze.py) on real and generated files, counted with Claude's tokenizer. Every planted fact (the root-cause traceback, failed order IDs and error codes, the exact revenue total, null counts, the one bad row) is present in the summary; [`tests/test_squeeze.py`](../tests/test_squeeze.py) checks them.

| File | Source | Tokens | Squeezed | Smaller |
|---|---|---:|---:|---:|
| app.log (24,000 lines, one incident) | generated | 859,037 | 1,555 | 99.8% |
| events.jsonl (5,000 events) | generated | 223,451 | 525 | 99.8% |
| sales.csv (9,000 rows) | generated | 249,942 | 639 | 99.7% |
| orders.json (640 orders) | generated | 119,406 | 1,500 | 98.7% |
| dpkg.log (9,413 lines) | real system log | 306,815 | 1,113 | 99.6% |
| airports.csv (3,376 rows) | real public data | 94,728 | 623 | 99.3% |
| npm package metadata (typescript) | real API response | 174,398 | 1,251 | 99.3% |
| seattle-weather.csv (1,461 rows) | real public data | 35,546 | 521 | 98.5% |
| npm search results (250 packages) | real API response | 87,397 | 1,405 | 98.4% |
| npm install, verbose (598 lines) | real build log | 19,879 | 1,011 | 94.9% |

A 1.9 MB log takes about 0.7 seconds.

### End to end in Claude Code

[`evals/squeeze-bench/run_e2e.py`](../evals/squeeze-bench/run_e2e.py) starts Claude Code headless in a fresh folder with one file, allows Bash, Read, Grep and Glob, and asks a realistic question: find the cause of an incident in a log, list failed orders in an API response, total a CSV and find bad rows, list failing tests from a 4,000-test run, and so on. It records billed usage (fresh input, cache writes and cache reads all count as input) and grades the answer against planted facts. Arms: plain Claude Code, the skill, the hook, and both.

**Opus 5.5, 8 tasks on large files (57 KB to 1.9 MB), 2 runs each**

| Arm | Total input | Cost | Correct | Mean turns |
|---|---:|---:|---:|---:|
| Plain Claude Code | 2.80M | $2.28 | 16 of 16 | 4.4 |
| Skill | 2.51M (−10%) | $1.85 (−19%) | 16 of 16 | 3.8 |
| Hook | 2.92M (+4%) | $2.23 (−2%) | 16 of 16 | 4.5 |
| Skill and hook | 2.61M (−7%) | $1.80 (−21%) | 16 of 16 | 4.0 |

A confirmation round with the final skill wording (1 run each) gave: skill 1.19M input and $1.02, skill and hook 1.23M and $0.97, against plain Claude Code's 1.40M and $1.14 per round. All 16 answers correct.

**Opus 5.5, 3 tasks on mid-size files (94 KB to 143 KB, under Claude Code's read limits), 2 runs each**

| Arm | Total input | Cost | Correct |
|---|---:|---:|---:|
| Plain Claude Code | 1.10M | $0.93 | 6 of 6 |
| Skill | 1.10M | $0.79 | 6 of 6 |
| Hook | 1.11M | $0.95 | 6 of 6 |
| Skill and hook | 1.08M | $0.75 | 5 of 6 |

The one miss found four duplicate rows that the fixture generator had produced by chance and reported those, but left out the three blank sales-rep cells the grader looked for.

**Haiku 4.5, 8 tasks on large files, 1 run each**

| Arm | Total input | Cost | Correct |
|---|---:|---:|---:|
| Plain Claude Code | 1.59M | $0.65 | 7 of 8 |
| Hook | 1.20M (−25%) | $0.54 (−17%) | 8 of 8 |

### What the end-to-end runs show

- **Opus 5.5 rarely lets a large output reach the model.** It queries with `grep | head`, pipes test runs through `tail -100`, and redirects big output to a file before reading parts of it. Claude Code also caps Bash output at 30,000 characters and Read at 256 KB. So the hook seldom has anything to squeeze, and on Opus it is neutral.
- **Turns drive input cost.** Every turn re-sends a fixed 30,000 to 37,000 tokens of system prompt and tool definitions plus the conversation so far. Fewer, batched queries saved more than compressing outputs.
- **Squeezing a deliberate query backfires.** An early hook squeezed narrow `grep` results. Claude worked around the summary with extra commands and used more tokens (477,000 against 269,000 on the incident task). The shipped hook leaves narrowed commands alone.
- **The hook helps models that read raw output.** On Haiku 4.5 one task fell from 13 turns to 2.
- **Cost falls more than input** for the skill arms, because Lembas replies are shorter and output tokens cost more than input tokens.

## Ithildin

Ithildin, the long-document skill added in 2.1.0, has its own results in [ITHILDIN.md](ITHILDIN.md#results-in-claude-code): maps 37 to 190 times smaller than the documents, and 26% less input in Claude Code on six document questions, with every answer correct. Raw runs are in [`evals/ithildin-bench/results-opus-5-5.json`](../evals/ithildin-bench/results-opus-5-5.json).

## History: v1.x

### 11 prompts, v1.0.0

| Prompt | Category | Baseline | Lembas | Cut |
|---|---|---:|---:|---:|
| tableau-slow-dashboard-debug | troubleshooting | 1,133 | 240 | 78.8% |
| explain-concept-overfitting | concept | 822 | 182 | 77.9% |
| compare-powerbi-tableau | comparison | 796 | 202 | 74.6% |
| ds-interview-prep | advice | 914 | 240 | 73.7% |
| python-venv | code | 613 | 177 | 71.1% |
| left-vs-inner-join | concept | 616 | 184 | 70.1% |
| p0420-captiva | troubleshooting | 852 | 262 | 69.2% |
| sql-top3-per-region | code | 394 | 150 | 61.9% |
| python-dedupe-howto | code | 337 | 144 | 57.3% |
| write-followup-email | writing | 232 | 108 | 53.4% |
| prod-table-rebuild-safety | safety | 874 | 558 | 36.2% |
| **Total** | | **7,583** | **2,447** | **67.7%** |

Tokens estimated as characters divided by 4. Fact checks: Lembas 65 of 65, baseline 63 of 65.

### Versions

| Version | Cut on 11 prompts | Skill file (words) | Main change |
|---|---:|---:|---|
| 0.2.0 | 58.9% | 944 | 40% length target, top causes only, one sentence per item |
| 0.3.0 | 60.1% | 1,088 | No lead-ins, echoes or repeated closers |
| 0.4.0 | 67.2% / 65.6% | 1,177 | Word budgets by question type |
| 1.0.0 | 67.7% | 848 | Restructured and trimmed |
| 1.1.0 | not rerun | 909 | Always keep the main gotcha |
| **2.0.0** | see above | 1,043 | Four-part answers, input-token section, squeeze |

### Caveman benchmark, v1.x

| Arm | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---:|---:|---:|---:|
| Lembas 1.1.0 | | | 49% | 52% |
| Lembas 1.0.0 | 54% | 55% | 52% | 53% |
| ultracave | 34% | 41% | 29% | 45% |
| megacave | 7% | 18% | | |
| caveman | 5% | 12% | | |

Median cut beyond "Answer concisely.". Megacave answers in Classical Chinese, which looks cheap under OpenAI's tokenizer (caveman's default scorer) but saves little in Claude's tokenizer and billing.

## Noise and limits

- Runs vary. v0.4 run twice on the same prompts gave 67.2% and 65.6%, and single prompts swing by up to 10 points. Reviewers also disagree: in v1.1 testing, one reviewer passed 3 of 10 answers and another passed 9 of 10. Treat differences under about 3 points, and single-run results, as directional.
- The end-to-end benchmark has 11 tasks and 1 or 2 runs per arm. The Haiku result is one run.
- The fixtures are generated with known answers, plus six real files: two logs from one Linux machine, two npm registry responses and two public CSV datasets. Logs from other systems may detect or summarize differently.
- Replies were single-turn. Staying in Lembas mode across a long conversation was not measured.
