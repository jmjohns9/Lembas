# Security

Lembas and Ithildin are written instructions for Claude plus small Python scripts. Installing a skill runs nothing. The scripts run when you or Claude call them: `squeeze.py` and the optional hook read command output and files you point them at, and `ithildin.py` reads documents you point it at. All of them work locally, send nothing over the network, and keep their caches (`$TMPDIR/lembas-squeeze`, `$TMPDIR/ithildin`) readable by you only, because logs and documents can contain secrets. Ithildin parses documents with poppler's `pdftotext`, pypdf, pdfplumber and Python's own zip and XML readers; a malicious document is a risk to those parsers as it would be to any PDF or Office reader, so keep them updated. The scripts in `evals/` run only when you run them, for benchmarking.

The main risk with a skill like this is that a change to `SKILL.md` makes Claude drop a safety warning or a protective step. Lembas is designed never to shorten safety warnings, irreversible actions or step-by-step procedures, and the `prod-table-rebuild-safety` benchmark prompt checks for this.

## Reporting

If you find a prompt where Lembas leaves out a safety warning, a backup step or anything else that could cause harm, report it privately through [GitHub security advisories](https://github.com/jmjohns9/lembas/security/advisories/new) rather than a public issue. Include the prompt, the reply and the model you used.

Expect a reply within a week. Fixes ship as a new release with a CHANGELOG entry.
