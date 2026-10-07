# Benchmarks

## Method

Each of the 11 prompts in [`evals/evals.json`](../evals/evals.json) was answered twice by Claude, each time in a fresh session:

- **Baseline:** no skill, the model's normal reply.
- **Lembas:** the skill loaded and active.

Reply length is measured with [`scripts/count_tokens.py`](../scripts/count_tokens.py). Tokens are estimated as characters divided by 4, because the tokenizer download was blocked in the test environment. That is accurate enough for comparing percentages; the absolute counts are estimates. Run with `--tiktoken` for exact counts if you have the tokenizer.

Fact retention is checked with [`scripts/grade.py`](../scripts/grade.py). For every reply it checks the facts listed under `must_contain`, that the reply opens with the answer, that it doesn't end with an offer of help, and that it has no dashes. Replies were also read by hand, which caught several checker false positives (fixed in v1.0.0) and confirmed the safety answer kept every protective step.

## Results for v1.0.0

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

Fact checks: Lembas 65 of 65, baseline 63 of 65 (two baseline replies end with an offer of help).

### Reading the results

- **Explanations, comparisons, advice and troubleshooting** shrink the most (69% to 79%). These are the replies with the most padding: headers, long lists, background and closing offers.
- **Code answers** shrink less (57% to 71%) because the code is most of the reply and is never shortened.
- **Writing tasks** shrink about half. Lembas removes the framing around a draft, not the draft itself.
- **Safety answers** shrink the least by design. Lembas keeps every step and warning for irreversible actions, and only removes padding.

## Version history

All figures are the total reduction against the same baseline replies.

| Version | 5 original prompts | 11 prompts | Skill file (words) | Main change |
|---|---:|---:|---:|---|
| 0.1.0 | 58.1% | | not saved | First draft |
| 0.2.0 | 64.1% | 58.9% | 944 | 40% length target, top causes only, one sentence per item |
| 0.3.0 | | 60.1% | 1,088 | No lead-ins, echoes or repeated closers |
| 0.4.0 | | 67.2% / 65.6% | 1,177 | Word budgets by question type |
| **1.0.0** | | **67.7%** | **848** | Restructured and trimmed the skill file |

Two things stand out:

- **v0.2 looked like it passed 60% but didn't generalize.** It cut 64% on the 5 prompts it was tuned on, then only 59% once 6 new prompts were added. Testing on prompts the skill wasn't tuned on matters.
- **Rewording rules stopped paying off; word budgets didn't.** v0.3's extra rules gained about one point, which is within noise. Giving the model a concrete number of words to aim for gained seven.

## Noise

v0.4 was run twice on the same 11 prompts. The totals were 67.2% and 65.6%. One prompt (tableau-slow-dashboard-debug) swung from 80.9% to 70.5%. Treat any total difference under about 3 points as noise unless it holds across repeated runs.

## Limitations

- One reply per prompt per version, except the v0.4 repeat.
- 11 prompts, mostly technical and analytics topics. Results on creative or very short conversational prompts may differ.
- Token counts are estimates (characters / 4).
- Replies were generated in simulated single-turn sessions. In long conversations, Lembas has to stay on across many turns; that was not measured.
