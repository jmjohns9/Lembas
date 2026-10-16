# Design notes

Why Lembas works the way it does. Read this before changing a rule.

## The core idea

Most of a long reply is not the answer. In the baseline replies from the benchmark, the facts a reader needed usually fit in a third of the text. The rest was setup, restated questions, headers, background, extra examples, recaps and offers. Cutting those removes most of the length without touching any fact.

Lembas does not compress language. Caveman, the skill it started from, drops articles and writes in fragments ("Bug in auth middleware. Fix:"). That saves tokens but reads rough and saves less than it seems, because filler words like "the" are single tokens while a whole unneeded paragraph is a hundred. Lembas keeps full sentences and goes after the paragraphs.

## Why 2.0 changed the answer shape

Versions 1.0 and 1.1 cut hard and lost judgment. In blind review, 1.1 was complete on 12 of 20 answers, and the gaps were rarely missing facts. They were missing reasoning: the answer named a fix but not why it beat the obvious alternative, or listed options without saying when each one wins. A senior engineer's answer is short because it is selective, and it still shows the decision.

2.0 makes that decision visible with four parts for problems and choices:

| Part | What it must contain | Why |
|---|---|---|
| Problem | The root cause as a mechanism, or the likeliest cause plus the check that confirms it | A symptom restated ("it's slow") gives the reader nothing to act on. Naming the mechanism is what makes the fix make sense. |
| Fix | Exact code, commands or settings, then how to confirm it worked | A fix without a confirmation step leaves the reader guessing whether it worked. |
| Alternatives | One to three, each with the condition under which it beats the fix | "You could also use X" is noise. "Use X if Y" lets the reader overrule the recommendation when their situation differs. |
| Why this fix | The deciding trade-off: risk, cost, reversibility, or fit | This is the part 1.1 dropped most. It is what turns an answer into advice. |

Concept questions don't get the labels. Forcing "Problem" onto "What is a hash table?" reads badly and adds tokens. They get the mechanism, when to use each option, and the trap.

The cost is length. 2.0 replies are about 49% longer than 1.1's. The result is still about 60% shorter than an answer with no prompt, and blind review rated 2.0 higher than both 1.1 and ultracave on completeness, errors and decision quality.

## Why each rule exists

| Rule | Reason |
|---|---|
| Answer first | Readers stop when they have what they need. Setup sentences delay that and add nothing. |
| Word budgets (50, 130, 200) | The most effective single change in 1.0 testing. "Be concise" is vague; "200 words" is a target the model can check. 2.0 raised them to make room for alternatives and reasoning. Code is exempt so answers never lose working code. |
| Detail means specificity | "Increase the timeout" is short and useless. "Set `statement_timeout = '30s'`" is short and actionable. Specific beats long. |
| Alternatives need conditions | Without a condition, an alternative is a survey item. With one, it is a decision rule. |
| What to cut | Ceremony, connective tissue and surveys carry no information. |
| What never to cut | One changed character breaks a command, and dropping "not" flips the meaning. Savings come from prose, never from payload. |
| When to relax | Brevity must never remove a backup step or a safety warning. Relaxing means complete, not padded. |
| One worked example | Models follow an example more reliably than a description of a format. The example uses cron, a topic in no benchmark, so it can't inflate scores. |

## Input tokens: what testing showed

Lembas 2.0 also tries to cut what Claude reads. Three findings shaped the design:

1. **The compressor works; the question is when it runs.** `squeeze.py` shrinks raw logs, JSON and CSV by 95% to 99.8% and keeps every planted fact. But compression only saves tokens when a large output would otherwise reach the model.
2. **Claude Opus 5.5 in Claude Code rarely lets large outputs reach the model.** It runs `grep | head`, pipes test runs through `tail -100`, or redirects output to a file and queries it. Claude Code also caps Bash output at 30,000 characters and Read at 256 KB. Across 88 runs on Opus, most tool results were 1 to 6 KB.
3. **Turns matter more than output size.** Each turn re-sends the whole conversation, including a fixed 30,000 to 37,000 tokens of system prompt and tools. A run with 6 turns reads that 6 times. The skill's advice to batch related queries into one command cut turns and saved more on Opus than the hook did.

An early hook squeezed every output over 2,000 tokens, including narrow `grep` results Claude had asked for. Claude worked around the summaries with extra commands and spent more. The hook now leaves narrowed commands alone. That is the general lesson: compress bulk output, never a deliberate query.

The hook pays off where the model does read raw output. On Haiku 4.5 it cut input by 25%. It is shipped as an optional install with that guidance, not as a default.

## What didn't work

- **More rules about specific phrases (v0.3).** Banning lead-ins and repeated closers gained about one point. Concrete targets beat lists of forbidden phrases.
- **Turning off brevity entirely for safety answers (v0.1 to v0.3).** The production database answer came out nearly as long as the baseline. "Complete, not padded" fixed it.
- **Cutting harder than 1.1 (Lembas Full drafts, 2026-10).** Longer budgets with 1.1's rules gave ultracave-level completeness at lower savings than ultracave. The fix was a different answer shape, not a different budget.
- **Squeezing everything (2.0 development).** See above.

## Keeping the skill file small

The skill text loads into every session where Lembas is active. 2.0 is about 1,040 words, up from 909 in 1.1, and the increase is the input-token section and the worked example. Any new rule should earn its words.
