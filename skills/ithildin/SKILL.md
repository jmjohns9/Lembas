---
name: ithildin
description: >
  Answer questions about long documents without reading them whole: map the
  outline first, search for the facts, then read only the sections or pages
  that answer the question, with page citations. Use whenever the user asks
  about a long PDF, Word file, PowerPoint deck, Markdown, HTML or text document
  (manuals, specs, standards, contracts, policies, reports, books, anything
  over about 30 pages), whether it is uploaded, on disk or downloaded, and
  whenever they say /ithildin or "use ithildin". Part of the Lembas family.
---

# Ithildin

Ithildin is the moon-letter script on the Doors of Durin: writing that shows only where the light falls on it. This skill reads long documents the same way: see the shape of the whole, then light up only the part that holds the answer.

Reading a 400-page book whole costs about 250,000 input tokens, and every later turn pays for that again. Its map costs about 2,000. Most questions are answered by one or two sections.

## When to use it

Use it when the document is long (over about 30 pages or 15,000 words) and its text is not already in the conversation. If the document's content is already visible to you, answer from that; don't read it again.

Skip it for short documents, and for tasks that need every word (proofreading, translating, a summary of everything). For those, read the document section by section in order.

## How

The script is `scripts/ithildin.py` in this skill's folder. It reads PDF, DOCX, PPTX, Markdown, HTML and plain text, runs locally, and caches what it parses, so repeat calls are fast.

1. **Map it.** `python3 scripts/ithildin.py map FILE`
   You get the outline with section ids, page ranges and word counts, a one-line gist per section, the tables and figures with their pages, and defined terms. Read the header line: it tells you where the outline came from (bookmarks, heading styles, type sizes or numbering). If the map says there is no structure or the PDF is scanned, follow its note.

2. **Search for specifics.** `python3 scripts/ithildin.py find FILE "term" "synonym" "abbreviation"`
   Put every phrasing in one call; each gets its own hit count and the sections it appears in. Hits show the page and section of each match. Use `-C 2` for surrounding lines and `--regex` for patterns like `"late fee.*\$[0-9]+"`.

3. **Read the smallest piece that answers.** `python3 scripts/ithildin.py read FILE 7.3` (a section id from the map), `read FILE p71-73` (pages) or `read FILE L120-180` (lines). Several targets can go in one call. A section includes its subsections, so prefer the subsection when the map shows one. Long reads stop at `--max-tokens` (default 8,000) and tell you exactly where to continue.

4. **Get tables as rows.** `python3 scripts/ithildin.py table FILE T12` returns the table under that caption as rows, which is more reliable than reading a table from flowing text.

5. **Answer with citations.** Cite the page or section for each fact ("p72, §7.3"). Quote numbers, limits, part numbers and obligations from text you read, never from a gist or a search snippet that cut off mid-sentence.

## Judgment

- **Choose sections from the map before searching** when the question is broad ("what does this policy cover?"). Search first when it is narrow ("what is the late fee?").
- **Check the context around a hit.** Requirements often have exceptions in the next sentence or a later section ("unless", "except", "notwithstanding"). For anything with legal, safety or money consequences, read the whole clause or subsection, and check the definitions section for defined terms.
- **"Not in the document" needs evidence.** Say it only after `find` with two or three phrasings and a look at the sections where it would belong, and say what you searched.
- **Keep reads small.** Read one subsection, decide, then read the next if needed. Don't read a whole chapter to find one number.
- **Several documents:** map each one, then compare the matching sections directly.

## Example

User: "Can I sublet my apartment under this lease, and how much notice do I need to give to leave?"

1. `map lease.pdf` shows 9 Assignment and Subletting (p14-15) and 18 Termination (p27-29), plus a defined term "Landlord's Consent".
2. `find lease.pdf "sublet" "sublease" "assign" "notice"` confirms §9 and §18, and finds a mention in §22 Rules on p33.
3. `read lease.pdf 9 18.2 p33` returns the exact clauses.
4. Answer with the clause text behind each point: subletting needs written consent that "shall not be unreasonably withheld" (p14, §9.1); notice to leave is 60 days, in writing, ending on the last day of a month (p28, §18.2); and the rules on p33 cap guest stays at 14 nights, which matters for short-term subletting.

Reading the lease whole would cost about ten times as many tokens and would answer no better.
