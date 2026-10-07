# Lembas

**A Claude skill that cuts reply length by about two thirds without losing facts.**

In *The Lord of the Rings*, one small bite of elven bread called lembas fills a traveler for a whole day. Lembas replies work the same way: small, complete, nothing extra to carry.

Most of a typical AI reply isn't the answer. It's setup, a restated question, hedging, background nobody asked for, three examples where one would do, a recap and an offer to help. Lembas cuts those and keeps everything that matters: facts, numbers, code, commands, caveats and safety warnings. Sentences stay whole and natural. It reads like a sharp colleague, not a telegram.

| | Without Lembas | With Lembas |
|---|---|---|
| Average reply (11 test prompts) | 689 tokens | 222 tokens |
| Reduction | | **67.7%** |
| Key facts kept | 65 of 65 checks | 65 of 65 checks |

See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for the method and per-prompt results.

## Example

**Prompt:** *My Tableau Server dashboard takes 45 seconds to load but runs in 5 seconds in Desktop. It uses a live connection to SQL Server and has 8 sheets with a few LOD calcs. What should I check?*

Without Lembas the reply is about 1,130 tokens: a six-part checklist with headers, sub-bullets and a summary. With Lembas it is about 240 tokens: one sentence naming the first move, four ranked checks in one sentence each, and nothing after. Both versions are in [evals/results/v1.0.0/tableau-slow-dashboard-debug](evals/results/v1.0.0/tableau-slow-dashboard-debug).

## Install

**Claude apps (claude.ai, desktop, Cowork):** download `lembas.skill` from the latest release, open it in Claude and click **Save skill**. To build it yourself, run `scripts/package.sh` and use `dist/lembas.skill`.

**Claude Code:** copy the skill folder into your skills directory.

```bash
git clone https://github.com/<your-account>/lembas.git
cp -r lembas/skills/lembas ~/.claude/skills/
```

## Use

| You say | What happens |
|---|---|
| `/lembas` or "lembas mode" | Lembas turns on and stays on for the session |
| "be brief", "be concise", "save tokens", "cut the fluff" | Lembas usually triggers on these too |
| "stop lembas" or "normal mode" | Lembas turns off |

## What it does

- **Answers in the first sentence.** The verdict or fix comes first.
- **Cuts ceremony.** No greetings, praise, restated questions, recaps or "hope this helps".
- **Picks instead of surveying.** The three or four most likely causes, not every possible one. One example, not three.
- **Sets word budgets.** 60 words for a quick fact, 120 for an explanation, 150 for how-to or advice. Code doesn't count.
- **Keeps the payload exact.** Code, commands, paths, numbers and error messages are never shortened.
- **Writes in plain language.** Full sentences and normal grammar. No fragments, invented abbreviations or caveman voice.

## When it doesn't cut

Lembas relaxes for safety warnings, irreversible actions, multi-step procedures where a missing step causes failure, a confused user, and anything saved outside the chat (code, commits, docs, emails sent as you). Those answers stay complete. They still skip padding, so they usually come out somewhat shorter.

In testing, a question about rebuilding a production Postgres table came back at 36% shorter instead of 68%, and it kept every protective step: a tested backup, a single-transaction swap, keeping the old table until verified, and a rehearsal on staging.

## Repository layout

```
skills/lembas/SKILL.md      The skill itself
evals/evals.json            11 benchmark prompts and the facts each reply must keep
evals/results/v1.0.0/       Baseline and Lembas replies for each prompt
scripts/count_tokens.py     Measures the reduction
scripts/grade.py            Checks facts kept and filler removed
scripts/package.sh          Builds dist/lembas.skill
docs/BENCHMARKS.md          Method, results and version history
docs/DESIGN.md              Why each rule exists
```

## Credits

Lembas started as a reverse engineering of [caveman](https://github.com/JuliusBrussee/caveman) by Julius Brussee. Several ideas come from it: answer first, keep the payload verbatim, persistence until switched off, and a pre-send check. Lembas drops caveman's fragment style in favor of natural sentences and adds word budgets. See [NOTICE](NOTICE).

## License

[Apache License 2.0](LICENSE)
