# Lembas

[![Checks](https://github.com/jmjohns9/lembas/actions/workflows/checks.yml/badge.svg)](https://github.com/jmjohns9/lembas/actions/workflows/checks.yml)
[![Release](https://img.shields.io/github/v/release/jmjohns9/lembas)](https://github.com/jmjohns9/lembas/releases/latest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**A Claude skill for short, dense engineering answers: the problem, the fix, the alternatives and why the fix wins.**

In *The Lord of the Rings*, one small bite of elven bread called lembas feeds a traveler for a day. Lembas answers work the same way: small, because every sentence carries something you need.

Most of a typical AI reply isn't the answer. It's setup, a restated question, hedging, background nobody asked for and an offer to help. Lembas cuts those. What's left reads like a staff engineer's code review comment: the root cause, the exact fix and how to confirm it, the alternatives with when each one wins, and the trade-off that decides it.

Version 2.0 also cuts what Claude **reads**. It queries large files before reading them, and it ships a compressor that turns a 24,000-line log into a 1,500-token summary that keeps every error.

## Results

| | "Answer concisely." | Lembas 1.1 | ultracave | **Lembas 2.0** |
|---|---:|---:|---:|---:|
| Shorter than no prompt (total) | 37% to 38% | 69% | 56% to 60% | **61% to 62%** |
| Shorter than "Answer concisely." (median) | | 47% to 48% | 34% to 35% | **35% to 37%** |
| Complete in blind review | | 12 of 20 | 17 of 20 | **19 of 20** |
| Answers with a factual error | | 2 | 4 | **1** |
| Decision quality (1 to 5) | | 3.90 | 4.45 | **4.85** |

Caveman's 10 developer questions, 2 runs, Claude Opus 5.5, counted with Claude's tokenizer. Blind reviewers scored anonymous answers against the full no-prompt answer. Full method and data in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

**Input tokens.** `squeeze.py` shrinks large logs, JSON and CSV by 95% to 99.8%. In end-to-end Claude Code runs on Opus 5.5, the skill cut total input by 10% to 15% and cost by 10% to 19%, with every answer correct. The optional hook cut input by 25% on Haiku 4.5. See [docs/SQUEEZE.md](docs/SQUEEZE.md).

## Example

**Prompt:** *My cron job works when I run it by hand but does nothing under cron.*

> **Problem.** Cron runs jobs with a minimal environment (`PATH=/usr/bin:/bin`, no shell profile), so `python3` from pyenv or Homebrew and any relative path fail, and cron discards the error.
>
> **Fix.** Use absolute paths and keep the output: `*/5 * * * * /usr/local/bin/python3 /opt/app/job.py >> /var/log/job.log 2>&1`. Wait one cycle and read the log to confirm.
>
> **Alternatives.** Set `PATH=` at the top of the crontab if many jobs share the same tools. Move to a systemd timer if you need retries, journald logging or a dependency on the network being up.
>
> **Why this fix.** It fixes the cause with a one-line change, and the redirect turns the next silent failure into a readable error.

Concept questions ("What's the difference between X and Y?") skip the labels: the mechanism, when to use each, and the common trap. More replies are in [evals/results/v2.0.0](evals/results/v2.0.0).

## Install

**Claude apps (claude.ai, desktop):** download [`lembas.skill`](https://github.com/jmjohns9/lembas/releases/latest/download/lembas.skill) from the [latest release](https://github.com/jmjohns9/lembas/releases/latest), open it in Claude and click **Save skill**. To build it yourself, run `scripts/package.sh` and use `dist/lembas.skill`.

**Claude Code:**

```bash
git clone https://github.com/jmjohns9/lembas.git
cp -r lembas/skills/lembas ~/.claude/skills/
```

**Optional Claude Code hook** (squeezes large tool outputs automatically; worth it on smaller models or with raised output limits, see [docs/SQUEEZE.md](docs/SQUEEZE.md#should-you-install-the-hook)):

```bash
python3 ~/.claude/skills/lembas/hooks/squeeze_hook.py --print-settings
```

Merge the JSON it prints into `~/.claude/settings.json`.

## Use

| You say | What happens |
|---|---|
| `/lembas` or "lembas mode" | Lembas turns on and stays on for the session |
| "be brief", "be concise", "save tokens", "cut the fluff" | Lembas usually triggers on these too |
| "stop lembas" or "normal mode" | Lembas turns off |

The compressor works on its own, with or without the skill:

```bash
python3 skills/lembas/scripts/squeeze.py app.log
npm test 2>&1 | python3 skills/lembas/scripts/squeeze.py
```

## What it does

- **Names the cause, not the symptom.** If the cause is uncertain, it gives the likeliest one and the check that confirms it.
- **Gives the exact fix and how to confirm it worked.** Code, commands, paths and numbers are never shortened.
- **Weighs alternatives.** Each one says when it beats the recommended fix. Alternatives without a condition are dropped.
- **Says why the fix wins.** The deciding trade-off, in a sentence or two, plus the trap people most often hit.
- **Cuts ceremony.** No greetings, praise, restated questions, recaps or offers of help.
- **Sets budgets.** 50 words for a quick fact, 130 for a concept, 200 for a problem or choice. Code doesn't count.
- **Reads less.** It sizes files first, queries them narrowly, batches related queries, and squeezes output it can't narrow.

## When it doesn't cut

Lembas relaxes for safety warnings, irreversible actions, multi-step procedures where a missing step causes failure, a confused user, and anything saved outside the chat (code, commits, docs, emails sent as you). Those answers stay complete. They still skip padding.

## Repository layout

```
skills/lembas/SKILL.md                 The skill
skills/lembas/scripts/squeeze.py       Compressor for logs, JSON and CSV
skills/lembas/hooks/squeeze_hook.py    Optional Claude Code hook
tests/                                 Compressor and hook tests, fixture generator
evals/evals.json                       11 prompts and the facts each reply must keep
evals/results/v2.0.0/                  Replies with and without Lembas
evals/caveman-bench/                   Results on caveman's skill benchmark
evals/squeeze-bench/                   End-to-end input-token benchmark
scripts/                               Token counter, grader, packager
docs/                                  Benchmarks, design notes, compressor guide
```

## Contributing

Found a reply that left out something important? [Open an issue](https://github.com/jmjohns9/lembas/issues/new/choose) with the prompt and the reply. Rule changes need benchmark numbers; [CONTRIBUTING.md](CONTRIBUTING.md) explains how to run them. Safety problems go through [SECURITY.md](SECURITY.md). Please follow the [code of conduct](CODE_OF_CONDUCT.md).

## Credits

Lembas started as a reverse engineering of [caveman](https://github.com/JuliusBrussee/caveman) by Julius Brussee. Several ideas come from it: answer first, keep the payload verbatim, persistence until switched off, and a pre-send check. Lembas drops caveman's fragment style in favor of natural sentences, and adds budgets, the four-part answer shape and input compression. See [NOTICE](NOTICE).

## License

[Apache License 2.0](LICENSE)
