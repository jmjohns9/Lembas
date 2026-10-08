# Security

Lembas is a set of written instructions for Claude. It runs no code of its own when installed. The scripts in `scripts/` and `evals/caveman-bench/scripts/` run only when you run them, for benchmarking.

The main risk with a skill like this is that a change to `SKILL.md` makes Claude drop a safety warning or a protective step. Lembas is designed never to shorten safety warnings, irreversible actions or step-by-step procedures, and the `prod-table-rebuild-safety` benchmark prompt checks for this.

## Reporting

If you find a prompt where Lembas leaves out a safety warning, a backup step or anything else that could cause harm, report it privately through [GitHub security advisories](https://github.com/jmjohns9/lembas/security/advisories/new) rather than a public issue. Include the prompt, the reply and the model you used.

Expect a reply within a week. Fixes ship as a new release with a CHANGELOG entry.
