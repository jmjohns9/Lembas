# Design notes

Why Lembas works the way it does. Read this before changing a rule.

## The core idea

Most of a long reply is not the answer. In the baseline replies from the benchmark, the facts a reader needed usually fit in a third of the text. The rest was setup, restated questions, headers, background, extra examples, recaps and offers. Cutting those removes most of the length without touching any fact.

Lembas does not compress language. Caveman, the skill it started from, drops articles and writes in fragments ("Bug in auth middleware. Fix:"). That saves tokens but reads rough and saves less than it seems, because filler words like "the" are single tokens while a whole unneeded paragraph is a hundred. Lembas keeps full sentences and goes after the paragraphs.

## Why each rule exists

| Rule | Reason |
|---|---|
| Answer in the first sentence | Readers stop when they have what they need. Setup sentences delay that and add nothing. |
| Word budgets | The single most effective change in testing (+7 points). "Be concise" is vague; "150 words" is a target the model can check. Code is exempt so answers never lose working code. |
| Pick, don't survey | Baseline troubleshooting replies listed 7 to 9 causes. The top 3 or 4 cover most real cases, and the user can ask for more. |
| One sentence per list item | v0.1's list items ran 3 to 4 sentences each, and this was its biggest source of length. |
| Cut connective tissue | Lead-ins ("Check these in order:") and echoes of the user's details carry no information. |
| Code answers shape | Prose that walks through what the code does repeats the code. Pitfall notes earn their place; walkthroughs don't. |
| Payload stays exact | One changed character breaks a command. Savings must come from prose, never from code, paths or numbers. |
| Keep meaning-bearing words | Dropping "not" or "only" flips the meaning. A wrong answer costs far more than any saved tokens. |
| Writing tasks | A user who asks for an email wants the email. Lembas removes the framing around it, not the draft itself. |
| When to relax | Brevity must never remove a backup step or a safety warning. Relaxing means complete, not padded. |
| Pre-send check | A last pass catches the patterns that slip through: openers, closers, lead-ins and over-budget replies. |

## What didn't work

- **More rules about specific phrases (v0.3).** Banning lead-ins and repeated closers gained about one point, and replies still slipped some through. Concrete targets beat lists of forbidden phrases.
- **Turning off brevity entirely for safety answers (v0.1 to v0.3).** The production database answer came out nearly as long as the baseline. v0.4 changed "write in full" to "complete, not padded", and v1.0 cut it 36% with every step intact.

## Keeping the skill file small

The skill text loads into every session where Lembas is active. v1.0 cut it from 1,177 words to 848 by merging overlapping sections and turning paragraphs into short numbered rules, with no loss in reduction. Any new rule should earn its words.
