# Security

Lembas and Ithildin are written instructions for Claude plus small Python scripts. Installing a skill runs nothing. The scripts run when you or Claude call them: `squeeze.py` and the optional hook read command output and files you point them at, and `ithildin.py` reads documents you point it at. The scripts in `evals/` run only when you run them, for benchmarking.

## What the scripts do with your data

- **Nothing leaves your machine.** The scripts contain no network code. The only programs they start are `pdftotext` and `pandoc`, with a fixed argument list and no shell, so a file name can't inject a command. What Claude itself sends to Anthropic is governed by your agreement with Anthropic; Lembas reduces it, because Claude reads a summary instead of the whole output.
- **Copies kept on disk, and for how long.** `squeeze.py` saves the full original of what it summarises in `$TMPDIR/lembas-squeeze`, so the summary can point at it. Ithildin caches the text of each document it parses in `$TMPDIR/ithildin`. Both folders and every file in them are readable by you only, because logs and documents can contain secrets. Copies are deleted after 24 hours: set `LEMBAS_SQUEEZE_KEEP_HOURS` and `ITHILDIN_CACHE_HOURS` to change that, or to `0` to keep nothing on disk. Deletion happens the next time each tool saves or loads something; the operating system's temp-folder cleanup is the backstop. The copies are not encrypted.
- **Folder ownership.** If another user created the cache folder first, the scripts don't use it and fall back to a private one. On Windows this ownership check is skipped; Windows temp folders are already per-user.

## Untrusted documents and output

- **Parsers.** Ithildin parses documents with poppler's `pdftotext`, pypdf, pdfplumber and Python's own zip and XML readers. A malicious document is a risk to those parsers as it would be to any PDF or Office reader, so keep them updated. Python's XML reader does not resolve external entities. Word and PowerPoint parts that unpack past 100 MB, or files past 500 MB in total, are refused, so a zip bomb can't exhaust memory.
- **pandoc.** Formats read through pandoc (`.rst`, `.tex`, `.org` and others) run with `--sandbox`, so a document can't use an include directive to pull other files from your computer into what Claude reads. A pandoc older than 2.15 has no sandbox and is refused.
- **Prompt injection.** Squeeze summaries keep error lines word for word and Ithildin returns document text, so instructions planted in a log or document reach Claude, as with any tool that shows Claude file contents. Both skills tell Claude to treat that text as data and to report instructions found in it instead of following them. This lowers the risk; it does not remove it.

## Verifying a download

Each release has a `SHA256SUMS` file. In the folder holding the downloads, `sha256sum -c SHA256SUMS` (or `shasum -a 256 -c SHA256SUMS` on macOS) checks that `lembas.skill` and `ithildin.skill` are the files that were published. To review exactly what you install, build the files yourself from a tagged commit with `bash scripts/package.sh`.

## Safety of the answers

The main risk with a skill like this is that a change to `SKILL.md` makes Claude drop a safety warning or a protective step. Lembas is designed never to shorten safety warnings, irreversible actions or step-by-step procedures, and the `prod-table-rebuild-safety` benchmark prompt checks for this.

## Reporting

If you find a security problem in the scripts, or a prompt where Lembas leaves out a safety warning, a backup step or anything else that could cause harm, report it privately through [GitHub security advisories](https://github.com/jmjohns9/lembas/security/advisories/new) rather than a public issue. Include the steps or the prompt, the reply and the model you used.

Expect a reply within a week. Fixes ship as a new release with a CHANGELOG entry.
