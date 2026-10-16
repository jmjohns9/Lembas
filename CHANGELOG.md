# Changelog

All notable changes to Lembas are listed here. Versions follow [Semantic Versioning](https://semver.org). Reduction figures are the average token cut against the same prompts answered without Lembas.

## [2.1.0] - 2026-10-16

Adds Ithildin, a second skill for long documents.

### Added
- **`skills/ithildin`:** answers questions about long PDFs, Word files, PowerPoint decks, Markdown, HTML and text without reading them whole. It maps the document, searches for the facts and reads only the sections that answer, citing pages.
- **`ithildin.py`** with four commands: `map` (outline with page ranges, gists, tables, figures and defined terms, fitted to a token budget), `find` (several patterns in one call, with hit counts per section, matching phrases that wrap across PDF lines), `read` (exact text of sections, pages or lines, with a precise continuation point) and `table` (one table as rows).
- Structure comes from bookmarks, heading styles and slide titles, then from type sizes in PDFs without bookmarks, then from section numbering. Running headers, footers and contents pages are removed so they don't become fake sections.
- `tests/test_ithildin.py` (20 tests) and `tests/ithildin_fixtures.py`, which builds a 126-page manual as a PDF with and without bookmarks, a Word file and Markdown, with five planted facts.
- `evals/ithildin-bench/`: an end-to-end Claude Code benchmark and its results.
- `scripts/package.sh` builds `dist/ithildin.skill` alongside `dist/lembas.skill`.

### Results
- **Maps are 37 to 190 times smaller than the documents:** 2,247 tokens for a 126-page manual (88,533 tokens whole) and 1,699 for a 395-page book (249,857 tokens whole), counted with Claude's tokenizer.
- **Claude Code, Opus 5.5, 6 questions, 2 runs:** 26% less input (10% to 38% by question), 4.5 to 3.1 turns on average, and 12 of 12 correct in both arms. Cost fell 3%, within the noise from shared prompt caching.

## [2.0.0] - 2026-10-15

A rewrite. Answers to problems and choices now give the problem, the fix, the alternatives and why the fix wins. Lembas also cuts input tokens now, with a compressor for large logs, JSON and CSV.

### Changed
- **New answer shape.** Debugging, how-to and design questions get four labeled parts: **Problem** (the root cause as a mechanism), **Fix** (exact code or commands plus how to confirm it worked), **Alternatives** (each with the condition under which it wins) and **Why this fix** (the deciding trade-off). Concept questions give the mechanism, when to use each option and the common trap, without labels.
- **Budgets** are 50 words for quick facts, 130 for concepts and 200 for problems and choices, up from 60, 120 and 150, to make room for alternatives and reasoning.
- **Detail now means specificity:** the exact flag, version, limit, error text or command.
- The 13 numbered rules became four short sections (answer shapes, what to cut, what never to cut, when to relax), plus one worked example on a topic outside every benchmark.

### Added
- **`scripts/squeeze.py`:** shrinks large logs, JSON, JSONL and CSV by 95% to 99.8% while keeping every error, stack trace, failing record and column profile. The original is saved and the summary gives its path and line numbers.
- **`hooks/squeeze_hook.py`:** an optional Claude Code hook that squeezes large Bash and Read results before Claude reads them. Commands that already narrow their output (`grep`, `head`, a `jq` filter) are left alone.
- **"Reading large outputs" in the skill:** size data first, query it narrowly, batch related queries into one command, and squeeze only output that can't be narrowed in advance.
- `tests/`: 23 tests for the compressor and hook, plus a fixture generator with planted answers.
- `evals/squeeze-bench/`: an end-to-end benchmark that runs Claude Code on 11 investigation tasks with and without the skill and hook.
- `evals/generate_replies.py`: generates and grades replies for `evals/evals.json`.

### Results
- **Replies:** 35% to 37% shorter than with "Answer concisely." alone and about 60% shorter than with no prompt (Claude tokenizer, caveman's 10 prompts, 2 runs). Lembas 1.1 cut more (47% to 48%) but dropped detail.
- **Blind review, 20 answers:** complete on 19 (1.1: 12; ultracave: 17), one factual error (1.1: 2; ultracave: 4), and decision quality 4.85 of 5 (1.1: 3.90; ultracave: 4.45).
- **Input tokens:** with Opus 5.5 in Claude Code, the skill cut total input by 10% to 15% and cost by 10% to 19%. The hook alone was neutral on Opus, because Claude Code already queries before reading, and cut input by 25% on Haiku 4.5.

### Notes
- `grade.py` now fails only on missing facts or a missing four-part structure. Style misses (an opener, a closing offer, dashes) are reported as warnings. One 2.0 reply used two dashes; it is recorded, not hidden.

## [1.1.0] - 2026-10-08

Tested on caveman's skill benchmark. Cuts 49% to 52% beyond a plain "Answer concisely." instruction (median), and 58% in Claude's billed output tokens.

### Changed
- "Pick, don't survey" now always keeps the gotcha: the one mistake or trap people most often hit on the topic. A blind review had found v1.0.0 most often dropped exactly that.
- "Keep meaning-bearing words" now says not to round "usually" up to "always".
- The pre-send check asks whether the main gotcha is still there.

### Results
- Blind review: complete answers rose from 9 of 20 to 12 of 20, and errors fell from 5 to 2, at a cost of about 2 points of savings.
- The 11-prompt benchmark in `evals/results/` was measured on v1.0.0 and not rerun.

### Added
- `evals/caveman-bench/`: snapshots, review packets and scripts for the caveman benchmark.

## [1.0.0] - 2026-10-07

First public release. Average reduction 67.7% across 11 prompts, with every fact check passing.

### Changed
- Rewrote and restructured `SKILL.md`. It is 28% shorter (848 words, down from 1,177), so it costs less context in every session, with no loss in reduction.
- Word budgets now have their own section instead of sitting inside a bullet list.
- Rules are a single numbered list of 13 short, bold-titled rules.
- Code answers follow a fixed shape: one sentence, the code, at most two notes on real pitfalls, and no walkthrough of what the code does.
- A requested email marked "short" is kept under 100 words.

### Notes
- Long safety answers got tighter (36% shorter than baseline, up from about 21%) and still kept every protective step.

## [0.4.0] - 2026-10-07 (pre-release)

Average reduction 67.2% (second run: 65.6%).

### Added
- Prose word budgets: 60 words for quick facts, 120 for explanations and comparisons, 150 for how-to and advice. Code doesn't count.
- "Relaxing means complete, not padded": safety and multi-step answers keep every step and warning but still skip ceremony.

## [0.3.0] - 2026-10-07 (pre-release)

Average reduction 60.1%.

### Added
- Rules against connective tissue: lead-in lines before lists, echoing the user's details back, and closing lines that repeat advice.
- Code answers put the code right after a one-sentence answer.

## [0.2.0] - 2026-10-07 (pre-release)

Average reduction 64.1% on the original 5 prompts and 58.9% on the expanded 11-prompt set.

### Added
- Target of about 40% of normal length.
- Troubleshooting limited to the three or four most likely causes.
- One sentence per list item.

## [0.1.0] - 2026-10-07 (pre-release)

Average reduction 58.1% on 5 prompts.

### Added
- First draft: answer first, cut ceremony, shortest complete answer, prose over formatting, plain language, exact payload, keep negations, writing-task exemption, relax rules and a pre-send check.

[2.1.0]: https://github.com/jmjohns9/lembas/releases/tag/v2.1.0
[2.0.0]: https://github.com/jmjohns9/lembas/releases/tag/v2.0.0
[1.1.0]: https://github.com/jmjohns9/lembas/releases/tag/v1.1.0
[1.0.0]: https://github.com/jmjohns9/lembas/releases/tag/v1.0.0
