# Ithildin: long documents, a piece at a time

Ithildin is the second skill in the Lembas repo. Lembas cuts what Claude writes, and its compressor cuts the logs and data Claude reads. Ithildin cuts what Claude reads from long documents: manuals, specs, standards, contracts, policies, reports and books.

Ithildin is the moon-letter script on the Doors of Durin, writing that appears only where the light falls. Ithildin shows Claude the shape of a whole document, then lights up only the part that holds the answer.

## Why documents need their own tool

Squeeze works because logs and data repeat: 10,000 lines that differ only by timestamp collapse into one line and a count. Prose doesn't repeat. Every paragraph of a 300-page spec says something different, so compressing it either loses facts or barely shrinks it.

Documents have something logs don't: structure. Chapters, sections, page numbers, tables and defined terms tell you where things are. Ithildin builds a map from that structure and lets Claude read only the pieces a question needs, with page references for every fact.

| Document | Pages | Whole document | Map | Sections found from |
|---|---:|---:|---:|---|
| Maintenance manual (generated test file), PDF | 126 | 88,533 tokens | 2,247 tokens | PDF bookmarks |
| Same manual, Word | | 82,925 | 2,342 | Word heading styles |
| *The Rust Programming Language*, PDF | 395 | 249,857 | 1,699 | type sizes (no bookmarks in the file) |
| Same book, Word | | 240,082 | 1,505 | Word heading styles |
| Same book, Markdown | | 313,434 | 1,660 | Markdown headings |

Counted with Claude's tokenizer. Maps are 37 to 190 times smaller than the documents they describe.

## Commands

```bash
python3 skills/ithildin/scripts/ithildin.py map   manual.pdf                    # outline, pages, gists, tables, terms
python3 skills/ithildin/scripts/ithildin.py find  manual.pdf "coolant" "overheat" # several phrasings, one call
python3 skills/ithildin/scripts/ithildin.py read  manual.pdf 7.3 p108 L40-90      # sections, pages or lines
python3 skills/ithildin/scripts/ithildin.py table manual.pdf T36                  # a table as rows
```

**map** prints one header line (size, section and table counts, where the outline came from), then the outline: section id, title, page range (or line range for formats without pages), word count and a one-line gist, which is the section's first sentence. Then come tables and figures with their pages, and defined terms. It fits the outline to `--budget` tokens (default 2,500) by collapsing deeper levels into "12 subsections" and dropping gists, deepest levels first. `--depth 2` limits the levels shown.

**find** searches case-insensitively and reports, for each pattern, the hit count and the sections hit, then each hit with its page and section. It matches phrases that wrap across lines in a PDF. `-C 2` adds context lines, `--regex` takes regular expressions, and `-n` caps hits per pattern (default 20).

**read** prints the exact text of a section (with its subsections), a page range (`p31-34`) or a line range (`L120-180`), with `[p31]` markers where pages change. It stops at `--max-tokens` (default 8,000) and says exactly where to continue and which subsections remain.

**table** returns one table as rows. Word, PowerPoint and Markdown tables are read directly. PDF tables are found by their caption and extracted with pdfplumber, using the caption's position to pick the right grid on the page.

## How it finds structure

In order of preference:

1. **The file's own outline:** PDF bookmarks, Word heading styles and outline levels, PowerPoint slide titles, Markdown and HTML headings.
2. **Type sizes**, for PDFs without bookmarks: lines set at least 12% larger than the most common body size are headings, and each distinct larger size is a level. This handles most exported reports and books.
3. **Numbering and layout:** numbered headings (`4.2 Fuel System`, `Section 3`, `Appendix B`) that must move forward through the document, which filters out numbered list items and table rows, plus short all-caps lines when nothing is numbered.

Running headers and footers are removed first (lines that recur at the top or bottom of at least 40% of pages, ignoring page numbers), and contents pages are skipped, so neither produces fake sections. The map's header line always says which method was used.

## Formats

| Format | Read with | Locations |
|---|---|---|
| PDF | `pdftotext` (poppler) if installed, otherwise pypdf; pypdf for bookmarks and type sizes; pdfplumber for tables | pages |
| DOCX | standard library (zip and XML) | lines |
| PPTX | standard library | slides |
| Markdown, HTML, text | standard library | lines |
| RST, ODT, EPUB, RTF, LaTeX, AsciiDoc | pandoc, if installed | lines |

`.doc` and `.ppt` need converting first; Ithildin prints the LibreOffice command. Scanned PDFs have no text layer; the map says so and suggests OCR (`ocrmypdf`).

Parsed documents are cached in `$ITHILDIN_CACHE` (default `$TMPDIR/ithildin`, readable by you only), keyed on the file's contents and the script's own code, so a changed file or a new version never reuses a stale entry. Nothing leaves your machine.

## Results in Claude Code

[`evals/ithildin-bench/run_e2e.py`](../evals/ithildin-bench/run_e2e.py) runs Claude Code (Opus 5.5) headless on six questions: three about the 126-page manual (two on the PDF, one on the Word file) and three about the 395-page Rust book PDF. Each answer sits in one or two sections. Two arms, 2 runs each: plain Claude Code, and Claude Code with Ithildin's SKILL.md and script.

| Question | Plain Claude Code | With Ithildin | Change | Turns (plain / Ithildin) |
|---|---:|---:|---:|---:|
| Coolant limit and warranty exclusions (PDF) | 249,786 | 173,839 | −30% | 6.5 / 4.0 |
| Head bolt torque and sequence, from a table (PDF) | 204,623 | 151,956 | −26% | 5.0 / 3.5 |
| Oil filter part number and service interval (Word) | 179,962 | 151,408 | −16% | 4.5 / 3.5 |
| Default integer type and overflow behavior (Rust book) | 154,028 | 101,728 | −34% | 4.0 / 2.5 |
| The ownership rules, word for word (Rust book) | 135,086 | 83,134 | −38% | 3.5 / 2.0 |
| Recoverable and unrecoverable errors (Rust book) | 133,704 | 120,128 | −10% | 3.5 / 3.0 |
| **Total** | **2,114,380** | **1,564,387** | **−26%** | **4.5 / 3.1** |

Mean total input tokens per run (fresh input, cache writes and cache reads all count). Both arms answered all 12 runs correctly.

What this shows:

- **Fewer turns is where the saving comes from.** Every Claude Code turn re-sends about 30,000 tokens of system prompt and tool definitions. Plain Claude Code converts the PDF, greps it, reads around the hits and often greps again; with the map, Claude goes to the right section in one or two calls.
- **Cost fell less than input: 3% ($2.48 to $2.39 across 24 runs).** Runs share Claude's prompt cache, so which runs got cheap cache reads depends on timing; and the skill's text adds about 1,000 tokens to each turn. Treat cost here as noise and input tokens as the measure.
- **Plain Claude Code is already frugal in a terminal.** It never read either document whole; it used `pdftotext` and `grep`. The bigger saving is where a document would otherwise enter the conversation whole, as a long upload can in the Claude apps. There a 395-page book costs about 250,000 tokens on every turn, against about 2,000 for its map plus a few thousand for the sections read.

## Limits

- **Gists are first sentences.** They help Claude choose sections; they are not summaries, and a section that opens with boilerplate gets an uninformative gist. Facts must come from `read`.
- **Two-column PDFs and unusual layouts** can come out of text extraction in the wrong order. Page references stay correct; reading order within a page may not be.
- **PDF tables need a caption** ("Table 3. …") to be listed in the map. Uncaptioned tables are still in the text and can be read by page.
- **Headings that are bold but not larger, unnumbered and not in capitals** aren't detected in PDFs without bookmarks. The map then has fewer sections; `find` and page reads still work.
- **Tasks that need every word** (proofreading, translation, a full summary) don't benefit; read section by section instead.
