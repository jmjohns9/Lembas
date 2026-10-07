# Changelog

All notable changes to Lembas are listed here. Versions follow [Semantic Versioning](https://semver.org). Reduction figures are the average token cut against the same prompts answered without Lembas.

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

[1.0.0]: https://github.com/<your-account>/lembas/releases/tag/v1.0.0
