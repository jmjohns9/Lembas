# Contributing to Lembas

Changes to Lembas are changes to `skills/lembas/SKILL.md`. Each one should make replies shorter, keep more facts, or make the skill file itself shorter. A change that helps one prompt and hurts others is not an improvement, so every change gets benchmarked.

## How to propose a change

1. **Open an issue first** if the change is more than a wording fix. Include a prompt where Lembas does badly and say what a good reply would look like.
2. **Edit `skills/lembas/SKILL.md`.** Explain the reason behind a rule rather than adding ALWAYS or NEVER. The model follows reasons better than commands.
3. **Run the benchmark** (below) and put the numbers in your pull request.
4. **Update `CHANGELOG.md`** under an "Unreleased" heading.

## Running the benchmark

Every prompt in `evals/evals.json` is answered twice: once with no skill (`baseline.md`) and once with the skill active (`lembas.md`). Generate the replies in a fresh session for each one, so earlier answers don't influence later ones. Save them as:

```
evals/results/<version>/<eval-name>/baseline.md
evals/results/<version>/<eval-name>/lembas.md
```

You can reuse the existing baseline files if you're only changing the skill. Then run:

```bash
python3 scripts/count_tokens.py evals/results/<version>
python3 scripts/grade.py evals/evals.json evals/results/<version>
```

`count_tokens.py` prints the reduction for each prompt and the total. `grade.py` checks that each reply keeps its required facts, opens with the answer, doesn't end with an offer of help, and uses no dashes. It exits with an error if any Lembas reply fails.

## What a pull request needs

- The total reduction before and after your change.
- `grade.py` passing for every Lembas reply. If a check fails, read the reply. A failure is sometimes a checker problem (for example, the reply says "stop training when validation error rises" instead of "early stopping"). Fix the regex in `evals.json` in that case and say so.
- A look at the safety prompt (`prod-table-rebuild-safety`). It must still include a backup, a transaction and a verification step before anything is dropped.

## Things to keep in mind

- **Single runs are noisy.** The same skill run twice on the same prompts varied by about 1.6 points in total and up to 10 points on one prompt. Run twice before claiming a gain under 3 points.
- **Shorter skill text is a feature.** The skill loads into every session that uses it.
- **Don't trade grammar for tokens.** Fragments and abbreviations save little and make replies harder to read. That is what separates Lembas from caveman.

## Adding a benchmark prompt

Add an entry to `evals/evals.json` with a unique `id`, a descriptive `name`, a `category`, the `prompt`, an `expected_output` summary, and `must_contain` regexes for the facts a good answer can't leave out. Prefer prompts that real users would type, and cover the categories already present: code, troubleshooting, concept, comparison, advice, writing and safety.

## Releasing

1. Move the "Unreleased" changelog entries under a new version heading.
2. Copy the final replies to `evals/results/<version>/` and update the tables in `README.md` and `docs/BENCHMARKS.md`.
3. Run `scripts/package.sh`, tag the commit (`git tag v1.1.0`) and attach `dist/lembas.skill` to the GitHub release.
