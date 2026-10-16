#!/usr/bin/env python3
"""Ithildin: read long documents a piece at a time.

Builds a compact map of a long document (outline with page ranges, a one-line gist per section,
tables, figures and defined terms), then serves only the parts a question needs.

    ithildin.py map  FILE [--budget TOKENS] [--depth N]
    ithildin.py find FILE PATTERN [PATTERN ...] [--regex] [-n MAX] [-C LINES]
    ithildin.py read FILE TARGET [TARGET ...] [--max-tokens N]
    ithildin.py table FILE TABLE_ID

TARGET is a section id from the map (4.2, S17), a page range (p31, p31-34) or a line range (L120-180).
Supports PDF, DOCX, PPTX, Markdown, plain text and HTML (plus anything pandoc reads, if installed).
Standard library only; uses pdftotext, pypdf and pdfplumber when they are available.
Nothing is sent anywhere.
"""
import argparse
import hashlib
import html
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

VERSION = "1.0.0"
DEFAULT_MAP_BUDGET = 2500
DEFAULT_READ_TOKENS = 8000
GIST_WORDS = 28


def est_tokens(text):
    # About 3.5 characters per token: Claude's tokenizer splits code, numbers and symbols finely,
    # so the usual 4 undercounts technical documents.
    return (len(text) * 2 + 6) // 7


def words(text):
    return len(text.split())


def clip_words(text, n):
    w = text.split()
    return " ".join(w[:n]) + (" …" if len(w) > n else "")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# Extraction: every format becomes a list of lines, each with a page (or None)
# ---------------------------------------------------------------------------

class Doc:
    def __init__(self, path, kind):
        self.path = path
        self.kind = kind
        self.lines = []        # [page or None, text]
        self.pages = None      # page count for paged formats
        self.headings = []     # dicts: line, level, num, title
        self.tables = []       # dicts: line, caption, rows (optional, for DOCX/PPTX)
        self.outline_source = "none"
        self.notes = []

    def add(self, text, page=None):
        self.lines.append([page, text])


def _run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def extract_pdf(path):
    doc = Doc(path, "PDF")
    pages = None
    if shutil.which("pdftotext"):
        r = _run(["pdftotext", "-enc", "UTF-8", path, "-"])
        if r.returncode == 0:
            pages = r.stdout.split("\f")
            if pages and not pages[-1].strip():
                pages = pages[:-1]
    if pages is None:
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("ithildin: reading PDF needs pdftotext (poppler-utils) or `pip install pypdf`.")
        reader = PdfReader(path)
        pages = [(p.extract_text() or "") for p in reader.pages]
    doc.pages = len(pages)
    for i, text in enumerate(pages, 1):
        for line in text.splitlines():
            line = norm(line)
            if line:
                doc.add(line, i)
    if sum(len(t) for _, t in doc.lines) < 40 * max(doc.pages, 1):
        doc.notes.append("Little or no text layer: this looks like a scanned PDF. OCR it first "
                         "(for example `ocrmypdf in.pdf out.pdf`) or read pages as images.")
    _strip_running_lines(doc)
    _pdf_outline(doc)
    if not doc.headings:
        _pdf_font_headings(doc)
    return doc


def _pdf_font_headings(doc, max_pages=2000):
    """Headings from type size: lines set noticeably larger than the body text."""
    if doc.pages > max_pages:
        return
    try:
        from pypdf import PdfReader
        import math
    except ImportError:
        return
    try:
        reader = PdfReader(doc.path)
    except Exception:
        return
    runs = []          # (page, size, text)
    sizes = {}
    for pno, page in enumerate(reader.pages, 1):
        buf = []

        def visit(text, cm, tm, fd, fs, pno=pno, buf=buf):
            if not text:
                return
            scale = (math.hypot(tm[0], tm[1]) or 1) * (math.hypot(cm[0], cm[1]) or 1)
            size = round(fs * scale, 1)
            for part in text.split("\n"):
                if part.strip():
                    buf.append((size, part))
                    sizes[size] = sizes.get(size, 0) + len(part)
                else:
                    buf.append((None, ""))

        try:
            page.extract_text(visitor_text=visit)
        except Exception:
            continue
        cur_size, cur = None, []
        for size, part in buf + [(None, "")]:
            if size is not None and size == cur_size:
                cur.append(part)
                continue
            if cur:
                runs.append((pno, cur_size, norm(" ".join(cur))))
            cur_size, cur = size, ([part] if size is not None else [])
    if not sizes:
        return
    body = max(sizes, key=sizes.get)
    big = sorted({s for s in sizes if s >= body * 1.12}, reverse=True)
    if not big:
        return
    cands = [(p, s, t) for p, s, t in runs if s in big and 2 <= len(t) <= 140 and words(t) <= 16
             and re.search(r"[A-Za-z]", t) and not re.search(r"[.,;:]$", t)]
    if len(cands) < 3:
        return
    used = sorted({s for _, s, _ in cands}, reverse=True)[:4]
    level_of = {s: i + 1 for i, s in enumerate(used)}
    first_line_of_page = {}
    for idx, (p, _) in enumerate(doc.lines):
        first_line_of_page.setdefault(p, idx)
    taken = set()
    for p, s, t in cands:
        if s not in level_of:
            continue
        start = first_line_of_page.get(p)
        if start is None:
            continue
        want = re.sub(r"\W+", "", t.lower())[:30]
        i = start
        while i < len(doc.lines) and doc.lines[i][0] == p:
            have = re.sub(r"\W+", "", doc.lines[i][1].lower())
            if i not in taken and have and (want.startswith(have[:30]) or have.startswith(want)):
                taken.add(i)
                m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", t)
                doc.headings.append({"line": i, "level": level_of[s], "num": m.group(1) if m else "", "title": t})
                break
            i += 1
    doc.headings.sort(key=lambda h: h["line"])
    if len(doc.headings) >= 3:
        doc.outline_source = "type sizes (no bookmarks in the file)"
    else:
        doc.headings = []


def _strip_running_lines(doc):
    """Drop page headers and footers: lines that recur at the top or bottom of many pages."""
    if not doc.pages or doc.pages < 4:
        return
    by_page = {}
    for idx, (p, t) in enumerate(doc.lines):
        by_page.setdefault(p, []).append(idx)
    counts = {}
    for p, idxs in by_page.items():
        edge = idxs[:3] + idxs[-3:]
        seen = set()
        for i in edge:
            key = re.sub(r"\d+", "#", doc.lines[i][1].lower())
            if key not in seen:
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
    running = {k for k, c in counts.items() if c >= max(3, 0.4 * doc.pages)}
    if not running:
        return
    keep = []
    for p, idxs in by_page.items():
        edge = set(idxs[:3] + idxs[-3:])
        for i in idxs:
            key = re.sub(r"\d+", "#", doc.lines[i][1].lower())
            if i in edge and key in running:
                continue
            keep.append(i)
    keep.sort()
    doc.lines = [doc.lines[i] for i in keep]


def _pdf_outline(doc):
    try:
        from pypdf import PdfReader
    except ImportError:
        return
    try:
        reader = PdfReader(doc.path)
        outline = reader.outline
    except Exception:
        return
    found = []

    def walk(items, level):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
                title = norm(str(item.title))
            except Exception:
                continue
            if title:
                found.append((page, level, title))

    walk(outline or [], 1)
    if len(found) < 2:
        return
    first_line_of_page = {}
    for idx, (p, _) in enumerate(doc.lines):
        first_line_of_page.setdefault(p, idx)
    for page, level, title in found:
        start = first_line_of_page.get(page)
        if start is None:
            continue
        line_idx = start
        want = re.sub(r"\W+", "", title.lower())[:40]
        i = start
        while i < len(doc.lines) and doc.lines[i][0] == page:
            have = re.sub(r"\W+", "", doc.lines[i][1].lower())
            if want and (have.startswith(want[:25]) or want.startswith(have[:25]) and len(have) > 3):
                line_idx = i
                break
            i += 1
        m = re.match(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)*)\.?\s+(.*)$", title)
        num = m.group(1) if m and re.match(r"^\d", title) else ""
        doc.headings.append({"line": line_idx, "level": level, "num": num, "title": title})
    doc.headings.sort(key=lambda h: h["line"])
    doc.outline_source = "PDF bookmarks"


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_text(el):
    out = []
    for node in el.iter():
        tag = node.tag
        if tag == W + "t" and node.text:
            out.append(node.text)
        elif tag == W + "tab":
            out.append("\t")
        elif tag in (W + "br", W + "cr"):
            out.append(" ")
    return "".join(out)


def extract_docx(path):
    doc = Doc(path, "Word document")
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
        styles = {}
        if "word/styles.xml" in z.namelist():
            for st in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
                sid = st.get(W + "styleId")
                name = st.find(W + "name")
                lvl = st.find(f"{W}pPr/{W}outlineLvl")
                styles[sid] = ((name.get(W + "val") if name is not None else sid) or "",
                               int(lvl.get(W + "val")) + 1 if lvl is not None else None)
    for child in body:
        if child.tag == W + "p":
            text = norm(_docx_text(child))
            if not text:
                continue
            level = None
            ppr = child.find(W + "pPr")
            if ppr is not None:
                ps = ppr.find(W + "pStyle")
                ol = ppr.find(W + "outlineLvl")
                if ol is not None:
                    level = int(ol.get(W + "val")) + 1
                elif ps is not None:
                    name, slvl = styles.get(ps.get(W + "val"), (ps.get(W + "val"), None))
                    m = re.match(r"(?i)heading\s*(\d)", name or "")
                    if m:
                        level = int(m.group(1))
                    elif (name or "").lower() == "title":
                        level = 1
                    elif slvl:
                        level = slvl
            if level and level <= 9 and len(text) <= 200:
                m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", text)
                doc.headings.append({"line": len(doc.lines), "level": level,
                                     "num": m.group(1) if m else "", "title": text})
            doc.add(text)
        elif child.tag == W + "tbl":
            rows = []
            for tr in child.iter(W + "tr"):
                cells = [norm(_docx_text(tc)) for tc in tr.findall(W + "tc")]
                rows.append(cells)
            _add_table(doc, rows)
    if doc.headings:
        doc.outline_source = "Word heading styles"
    return doc


def _add_table(doc, rows, page=None):
    if not rows:
        return
    caption = ""
    for back in range(1, 3):
        if len(doc.lines) >= back and re.match(r"(?i)^table\s+[\w.\-]+", doc.lines[-back][1]):
            caption = doc.lines[-back][1]
            break
    doc.tables.append({"line": len(doc.lines), "caption": caption, "rows": rows, "page": page})
    width = max(len(r) for r in rows)
    for r in rows:
        r = r + [""] * (width - len(r))
        doc.add("| " + " | ".join(c.replace("|", "/") for c in r) + " |", page)


P = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def extract_pptx(path):
    doc = Doc(path, "PowerPoint deck")
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        names.sort(key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
        for i, name in enumerate(names, 1):
            root = ET.fromstring(z.read(name))
            title_done = False
            for sp in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
                is_title = any(ph.get("type") in ("title", "ctrTitle")
                               for ph in sp.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}ph"))
                for para in sp.iter(P + "p"):
                    text = norm("".join(t.text or "" for t in para.iter(P + "t")))
                    if not text:
                        continue
                    if is_title and not title_done:
                        doc.headings.append({"line": len(doc.lines), "level": 1, "num": "", "title": text})
                        title_done = True
                    doc.add(text, i)
            for tbl in root.iter(P + "tbl"):
                rows = [[norm("".join(t.text or "" for t in tc.iter(P + "t"))) for tc in tr.iter(P + "tc")]
                        for tr in tbl.iter(P + "tr")]
                _add_table(doc, rows, i)
        doc.pages = len(names)
    doc.outline_source = "slide titles"
    return doc


def extract_markdown(path, text=None, kind="Markdown"):
    doc = Doc(path, kind)
    if text is None:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    fence = False
    pending = []          # rows of a Markdown table being read

    def flush_table():
        rows = [[norm(c) for c in r.strip().strip("|").split("|")] for r in pending
                if not re.match(r"^\s*\|?\s*:?-{2,}", r)]
        pending.clear()
        if rows:
            _add_table(doc, rows)

    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        if not fence and line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            pending.append(line)
            continue
        if pending:
            flush_table()
        if not line.strip():
            continue
        m = None if fence else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            title = m.group(2).strip()
            n = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", title)
            doc.headings.append({"line": len(doc.lines), "level": len(m.group(1)),
                                 "num": n.group(1) if n else "", "title": title})
            doc.add(title)
        else:
            doc.add(line if fence else norm(line))
    if pending:
        flush_table()
    if doc.headings:
        doc.outline_source = "Markdown headings"
    return doc


class _HTMLText(html.parser.HTMLParser):
    BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "section",
             "article", "table", "blockquote", "dd", "dt"}

    def __init__(self):
        super().__init__()
        self.out = []
        self.buf = []
        self.skip = 0
        self.head = None

    def flush(self):
        text = norm("".join(self.buf))
        if text:
            self.out.append(("#" * self.head + " " + text) if self.head else text)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "noscript"):
            self.skip += 1
        if tag in self.BLOCK:
            self.flush()
            self.head = int(tag[1]) if re.match(r"h[1-6]$", tag) else None
        if tag in ("td", "th"):
            self.buf.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "noscript") and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.flush()
            self.head = None

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


def extract_html(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        p = _HTMLText()
        p.feed(f.read())
        p.flush()
    return extract_markdown(path, "\n".join(p.out), "HTML page")


def extract_with_pandoc(path):
    r = _run(["pandoc", path, "-t", "gfm", "--wrap=none"])
    if r.returncode != 0:
        sys.exit(f"ithildin: pandoc could not read {path}: {r.stderr.strip()[:300]}")
    return extract_markdown(path, r.stdout, os.path.splitext(path)[1].lstrip(".").upper() + " document")


def extract_text(path):
    doc = extract_markdown(path, kind="Text")
    doc.headings = []
    doc.outline_source = "none"
    return doc


# ---------------------------------------------------------------------------
# Structure: heading detection when the file has none, sections, tables, terms
# ---------------------------------------------------------------------------

NUM_HEAD = re.compile(r"^(?:(?:section|chapter|article|part)\s+)?(\d{1,2}(?:\.\d{1,2}){0,4})\.?\s+(\S.{1,95})$", re.I)
NAMED_HEAD = re.compile(r"^(chapter|appendix|annex|part)\s+([A-Z0-9IVX]{1,5})\b[.:]?\s*(.{0,90})$", re.I)
TOC_LINE = re.compile(r"(\.{4,}|\s\.\s\.\s\.|…{2,})\s*\d+\s*$")


def _num_tuple(num):
    return tuple(int(x) for x in num.split("."))


def detect_headings(doc):
    """Find headings from numbering and casing when the file carries no outline."""
    toc_pages = set()
    if doc.pages:
        per_page = {}
        for p, t in doc.lines:
            c = per_page.setdefault(p, [0, 0])
            c[0] += 1
            if TOC_LINE.search(t) or (NUM_HEAD.match(t) and re.search(r"\s\d{1,4}$", t)):
                c[1] += 1
        toc_pages = {p for p, (n, k) in per_page.items() if n >= 5 and k / n >= 0.4}
    cands = []
    for idx, (p, t) in enumerate(doc.lines):
        if p in toc_pages or len(t) > 110 or TOC_LINE.search(t) or t.startswith("|"):
            continue
        m = NUM_HEAD.match(t)
        if m:
            title = m.group(2)
            if (title[0].isupper() and words(title) <= 14 and not re.search(r"[.,;:]$", title)
                    and sum(ch.isdigit() for ch in title) <= 0.3 * len(title)):
                cands.append({"line": idx, "num": m.group(1), "title": t,
                              "level": m.group(1).count(".") + 1})
                continue
        m = NAMED_HEAD.match(t)
        if m and (not m.group(3) or (m.group(3)[0].isupper() and words(t) <= 10
                                     and not re.search(r"[.,;]\s", m.group(3)))):
            cands.append({"line": idx, "num": "", "title": t, "level": 1})
            continue
        letters = re.sub(r"[^A-Za-z]", "", t)
        if (len(letters) >= 4 and t.upper() == t and 1 <= words(t) <= 8
                and not re.search(r"[.,;]$", t) and sum(ch.isdigit() for ch in t) <= 2):
            cands.append({"line": idx, "num": "", "title": t, "level": 1, "caps": True})
    # Numbered headings must move forward: drop list items and table rows that look like headings.
    out, last = [], None
    numbered = [c for c in cands if c["num"]]
    for c in cands:
        if not c["num"]:
            if c.get("caps") and len(numbered) >= 5:
                continue
            out.append(c)
            continue
        t = _num_tuple(c["num"])
        if last is None:
            ok = t[0] <= 3
        else:
            ok = t > last and t[0] <= last[0] + 2 and (len(t) <= len(last) + 1)
            if ok and len(t) > 1 and t[:-1] != last[:len(t) - 1] and t[-1] != 1:
                ok = t[:-1] == last[:len(t) - 1]
        if ok:
            out.append(c)
            last = t
    if numbered:
        caps_levels = 1
        for c in out:
            if c.get("caps") or not c["num"]:
                c["level"] = caps_levels
    for c in out:
        c.pop("caps", None)
    doc.headings = out
    if out:
        doc.outline_source = "numbering and layout (no bookmarks in the file)"


def finish(doc):
    if not doc.headings:
        detect_headings(doc)
    # Section ids: the document's own number when unique, otherwise S1, S2...
    seen = {}
    for h in doc.headings:
        if h["num"]:
            seen[h["num"]] = seen.get(h["num"], 0) + 1
    for i, h in enumerate(doc.headings, 1):
        h["id"] = h["num"] if h["num"] and seen.get(h["num"]) == 1 else f"S{i}"
    n = len(doc.lines)
    for i, h in enumerate(doc.headings):
        nxt_any = doc.headings[i + 1]["line"] if i + 1 < len(doc.headings) else n
        end = n
        for later in doc.headings[i + 1:]:
            if later["level"] <= h["level"]:
                end = later["line"]
                break
        h["end"] = end                 # exclusive, includes subsections
        h["body_end"] = nxt_any        # exclusive, own text only
        body = [t for _, t in doc.lines[h["line"] + 1:nxt_any] if not t.startswith("| ")]
        h["gist"] = _gist(" ".join(body))
        h["words"] = sum(words(t) for _, t in doc.lines[h["line"]:end])
    # PDF tables and figures are found by caption; DOCX and PPTX tables were read directly.
    if doc.kind == "PDF":
        for idx, (p, t) in enumerate(doc.lines):
            m = re.match(r"^(Table|Figure|Fig\.)\s+([A-Z]?\d+(?:[.\-]\d+)*)[.:]?\s*(.{0,100})$", t)
            if m and m.group(3) and not TOC_LINE.search(t):
                kind = "table" if m.group(1) == "Table" else "figure"
                if kind == "table":
                    doc.tables.append({"line": idx, "caption": t, "page": p})
                else:
                    doc.tables.append({"line": idx, "caption": t, "page": p, "figure": True})
    for i, tb in enumerate([t for t in doc.tables if not t.get("figure")], 1):
        tb["id"] = f"T{i}"
    for i, tb in enumerate([t for t in doc.tables if t.get("figure")], 1):
        tb["id"] = f"F{i}"
    doc.terms = []
    seen_terms = set()
    for idx, (p, t) in enumerate(doc.lines):
        for m in re.finditer(r"[“\"]([A-Z][A-Za-z0-9 /&\-]{1,40})[”\"]\s*(?:\)|,)?\s*(?:means|shall mean|refers to|is defined as|has the meaning)", t):
            term = m.group(1).strip()
            if term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                doc.terms.append({"term": term, "line": idx})
        for m in re.finditer(r"\((?:the|each,? a|collectively,? the)?\s*[“\"]([A-Z][A-Za-z0-9 /&\-]{1,40})[”\"]\)", t):
            term = m.group(1).strip()
            if term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                doc.terms.append({"term": term, "line": idx})


def _gist(text):
    text = norm(text)
    if not text:
        return ""
    m = re.match(r"(.+?[.!?])(?:\s+[A-Z(\"“]|$)", text)
    first = m.group(1) if m else text
    return clip_words(first, GIST_WORDS)


# ---------------------------------------------------------------------------
# Loading with a cache
# ---------------------------------------------------------------------------

def cache_dir():
    d = os.environ.get("ITHILDIN_CACHE") or os.path.join(tempfile.gettempdir(), "ithildin")
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        os.chmod(d, 0o700)   # parsed documents can hold confidential text
    except OSError:
        pass
    return d


def load(path):
    if not os.path.isfile(path):
        sys.exit(f"ithildin: no such file: {path}")
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    with open(os.path.abspath(__file__), "rb") as f:
        h.update(f.read())   # a new script version never reuses an old cache entry
    cpath = os.path.join(cache_dir(), h.hexdigest() + ".json")
    if os.path.exists(cpath):
        try:
            with open(cpath) as f:
                d = json.load(f)
            doc = Doc(path, d["kind"])
            doc.__dict__.update(d)
            doc.path = path
            return doc
        except Exception:
            pass
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        doc = extract_pdf(path)
    elif ext in (".docx", ".docm"):
        doc = extract_docx(path)
    elif ext == ".pptx":
        doc = extract_pptx(path)
    elif ext in (".md", ".markdown", ".mdx"):
        doc = extract_markdown(path)
    elif ext in (".html", ".htm", ".xhtml"):
        doc = extract_html(path)
    elif ext in (".txt", ".text", ".log", ""):
        doc = extract_text(path)
    elif shutil.which("pandoc") and ext in (".rst", ".odt", ".epub", ".rtf", ".org", ".tex", ".adoc", ".textile"):
        doc = extract_with_pandoc(path)
    elif ext in (".doc", ".ppt", ".odp", ".rtf") and shutil.which("soffice"):
        sys.exit(f"ithildin: convert first: soffice --headless --convert-to "
                 f"{'docx' if ext in ('.doc', '.rtf') else 'pptx'} {path}")
    else:
        doc = extract_text(path)
    finish(doc)
    try:
        with open(cpath, "w") as f:
            json.dump({k: v for k, v in doc.__dict__.items() if k != "path"}, f)
    except OSError:
        pass
    return doc


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def loc(doc, line_idx):
    if line_idx >= len(doc.lines):
        line_idx = len(doc.lines) - 1
    p = doc.lines[line_idx][0]
    return f"p{p}" if p is not None else f"L{line_idx + 1}"


def span(doc, start, end):
    a, b = loc(doc, start), loc(doc, max(start, end - 1))
    if a == b:
        return a
    if a.startswith("p") and b.startswith("p"):
        return f"{a}-{b[1:]}"
    return f"{a}-{b[1:]}"


def section_of(doc, line_idx):
    best = None
    for h in doc.headings:
        if h["line"] <= line_idx:
            best = h
        else:
            break
    return best


def render_map(doc, budget, depth=None):
    total_words = sum(words(t) for _, t in doc.lines)
    total_tokens = est_tokens("\n".join(t for _, t in doc.lines))
    name = os.path.basename(doc.path)
    tables = [t for t in doc.tables if not t.get("figure")]
    figures = [t for t in doc.tables if t.get("figure")]
    size = f"{doc.pages} {'slides' if doc.kind.startswith('PowerPoint') else 'pages'}, " if doc.pages else ""
    head = (f"[ithildin map: {name} ({doc.kind}, {size}{total_words:,} words, ~{total_tokens:,} tokens). "
            f"{len(doc.headings)} sections, {len(tables)} tables, {len(figures)} figures. "
            f"Outline from {doc.outline_source}. "
            f"Read parts: ithildin.py read FILE <id|p12-14|L40-90>. Search: ithildin.py find FILE \"term\" \"other term\".]")
    out = [head]
    for n in doc.notes:
        out.append("NOTE: " + n)
    if not doc.headings:
        out.append("No section structure found. Use find to locate topics, then read page or line ranges.")
        step = max(1, len(doc.lines) // 20)
        out.append("Text samples by location:")
        for i in range(0, len(doc.lines), step):
            out.append(f"  {loc(doc, i)}: {clip_words(doc.lines[i][1], 14)}")
        return "\n".join(out)

    levels = sorted({h["level"] for h in doc.headings})
    max_level = depth or levels[-1]

    def build(max_lvl, gist_lvl):
        rows = []
        hidden = {}
        for h in doc.headings:
            if h["level"] > max_lvl:
                parent = None
                for p in reversed(rows):
                    if p[0]["level"] < h["level"]:
                        parent = p
                        break
                if parent is not None:
                    hidden[id(parent[0])] = hidden.get(id(parent[0]), 0) + 1
                continue
            rows.append((h, h["level"] <= gist_lvl))
        lines = []
        rel = min(levels)
        for h, show_gist in rows:
            ind = "  " * (h["level"] - rel)
            title = h["title"]
            if h["num"] and title.startswith(h["num"]):
                title = title[len(h["num"]):].lstrip(" .")
            label = h["id"]
            txt = f"{ind}{label} {title} | {span(doc, h['line'], h['end'])} | {h['words']:,}w"
            extra = hidden.get(id(h))
            if extra:
                txt += f" | {extra} subsections"
            if show_gist and h["gist"]:
                txt += f" | {h['gist']}"
            lines.append(txt)
        return lines

    plans = [(max_level, max_level)] + [(lvl, g) for lvl in range(max_level, rel_min(levels) - 1, -1)
                                        for g in range(lvl, rel_min(levels) - 2, -1)]
    body = None
    for max_lvl, gist_lvl in plans:
        body = build(max_lvl, gist_lvl)
        if est_tokens("\n".join(body)) <= budget * 0.8:
            break
    if est_tokens("\n".join(body)) > budget * 0.8:
        body = body[: max(10, int(len(body) * (budget * 0.8) / max(est_tokens("\n".join(body)), 1)))]
        body.append(f"… outline cut to fit the budget; use --depth or find for the rest.")
    out.extend(body)
    rest = budget - est_tokens("\n".join(out))
    if tables or figures:
        out.append("Tables and figures:")
        for t in (tables + figures)[: max(5, rest // 30)]:
            cap = t["caption"] or ("columns: " + " | ".join(t["rows"][0])[:100] if t.get("rows") else "")
            dims = f" ({len(t['rows'])} rows)" if t.get("rows") else ""
            out.append(f"  {t['id']} {loc(doc, t['line'])}: {clip_words(cap, 16)}{dims}")
        shown = min(len(tables + figures), max(5, rest // 30))
        if shown < len(tables + figures):
            out.append(f"  … {len(tables + figures) - shown} more; find \"Table\" lists them.")
    if doc.terms:
        terms = ", ".join(f"{t['term']} ({loc(doc, t['line'])})" for t in doc.terms[:30])
        out.append(f"Defined terms: {terms}" + (f", … {len(doc.terms) - 30} more" if len(doc.terms) > 30 else ""))
    return "\n".join(out)


def rel_min(levels):
    return min(levels)


def _label(h):
    return h["title"] if h["title"].startswith(h["id"]) else f"{h['id']} {h['title']}"


def resolve(doc, target):
    t = target.strip()
    m = re.match(r"^[pP](\d+)(?:\s*-\s*[pP]?(\d+))?$", t)
    if m:
        if not doc.pages:
            sys.exit("ithildin: this document has no pages; use a section id or a line range like L40-90.")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        idxs = [i for i, (p, _) in enumerate(doc.lines) if p is not None and a <= p <= b]
        if not idxs:
            sys.exit(f"ithildin: no text on pages {a}-{b} (document has {doc.pages} pages).")
        return idxs[0], idxs[-1] + 1, f"pages {a}-{b}" if a != b else f"page {a}"
    m = re.match(r"^[lL](\d+)(?:\s*-\s*[lL]?(\d+))?$", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        return max(a - 1, 0), min(b, len(doc.lines)), f"lines {a}-{b}"
    for h in doc.headings:
        if h["id"].lower() == t.lower().lstrip("§"):
            return h["line"], h["end"], _label(h)
    for h in doc.headings:
        if h["num"] == t.lstrip("§"):
            return h["line"], h["end"], _label(h)
    low = t.lower()
    hits = [h for h in doc.headings if low in h["title"].lower()]
    if len(hits) == 1:
        h = hits[0]
        return h["line"], h["end"], _label(h)
    if hits:
        sys.exit("ithildin: several sections match; pick one id: " +
                 "; ".join(f"{h['id']} {h['title']}" for h in hits[:10]))
    sys.exit(f"ithildin: no section, page or line range matches {target!r}. Run map to see ids.")


def render_read(doc, targets, max_tokens):
    out = []
    budget = max_tokens
    for target in targets:
        a, b, label = resolve(doc, target)
        out.append(f"[ithildin read: {label}, {span(doc, a, b)}]")
        cur = None
        used = 0
        for i in range(a, b):
            p, text = doc.lines[i]
            marker = f"p{p}" if p is not None else None
            if marker and marker != cur:
                out.append(f"[{marker}]")
                cur = marker
            cost = est_tokens(text) + 1
            if used + cost > budget:
                nxt = loc(doc, i)
                subs = [h for h in doc.headings if a < h["line"] < b and h["line"] >= i]
                hint = f" Continue with: read FILE L{i + 1}-{b}"
                if subs:
                    hint += " or by subsection: " + ", ".join(h["id"] for h in subs[:8])
                out.append(f"[truncated at {nxt} to stay under {max_tokens:,} tokens.{hint}]")
                return "\n".join(out)
            out.append(text)
            used += cost
        budget -= used
    return "\n".join(out)


def render_find(doc, patterns, regex, limit, context):
    flags = re.I
    compiled = [(p, re.compile(p if regex else re.escape(p), flags)) for p in patterns]
    out = []
    summary = []
    for label, rx in compiled:
        hits = []
        for i, (_, t) in enumerate(doc.lines):
            if rx.search(t):
                hits.append(i)
            elif i + 1 < len(doc.lines) and rx.search(t + " " + doc.lines[i + 1][1]):
                if not rx.search(doc.lines[i + 1][1]):
                    hits.append(i)   # the phrase wraps onto the next line
        secs = []
        for i in hits:
            s = section_of(doc, i)
            sid = s["id"] if s else "-"
            if sid not in secs:
                secs.append(sid)
        summary.append(f"{label!r}: {len(hits)} hits in {len(secs)} sections" +
                       (f" ({', '.join(secs[:12])}{', …' if len(secs) > 12 else ''})" if secs and secs != ['-'] else ""))
        out.append(f"== {label!r} ({len(hits)} hits)")
        shown = set()
        for i in hits[:limit]:
            s = section_of(doc, i)
            sid = f"§{s['id']}" if s else ""
            lo, hi = max(0, i - context), min(len(doc.lines), i + context + 1)
            for j in range(lo, hi):
                if j in shown:
                    continue
                shown.add(j)
                mark = ">" if j == i else " "
                out.append(f"{mark}{loc(doc, j)} {sid} | {doc.lines[j][1][:240]}")
        if len(hits) > limit:
            out.append(f"  … {len(hits) - limit} more; narrow the pattern or raise -n.")
    return "[ithildin find: " + "; ".join(summary) + "]\n" + "\n".join(out)


def _caption_top(page, caption):
    """Vertical position of a caption on a pdfplumber page, or None."""
    want = caption.split()[:4]
    if not want:
        return None
    ws = page.extract_words()
    for i in range(len(ws) - len(want) + 1):
        if all(ws[i + k]["text"] == want[k] for k in range(len(want))):
            return ws[i]["top"]
    return None


def render_table(doc, tid):
    match = [t for t in doc.tables if t["id"].lower() == tid.lower()]
    if not match:
        sys.exit(f"ithildin: no table {tid!r}. Tables: " + ", ".join(t["id"] for t in doc.tables[:40]))
    t = match[0]
    if t.get("rows"):
        rows = t["rows"]
        head = f"[ithildin table {t['id']} at {loc(doc, t['line'])}: {t['caption'] or 'no caption'}, {len(rows)} rows]"
        return head + "\n" + "\n".join("| " + " | ".join(r) + " |" for r in rows)
    if doc.kind == "PDF":
        try:
            import pdfplumber
        except ImportError:
            pdfplumber = None
        if pdfplumber is not None:
            page_no = t["page"]
            pick = None
            with pdfplumber.open(doc.path) as pdf:
                cap_top = _caption_top(pdf.pages[page_no - 1], t["caption"]) if page_no <= len(pdf.pages) else None
                for pn in (page_no, page_no + 1):
                    if not 1 <= pn <= len(pdf.pages):
                        continue
                    page = pdf.pages[pn - 1]
                    tables = sorted(page.find_tables(), key=lambda x: x.bbox[1])
                    for tb in tables:
                        # The table under this caption: first grid below it, or first grid on the next page.
                        if pn == page_no and cap_top is not None and tb.bbox[1] < cap_top - 2:
                            continue
                        data = tb.extract()
                        if data and len(data) > 1:
                            pick = (pn, data)
                            break
                    if pick:
                        break
            if pick:
                pn, tb = pick
                rows = [[norm(c or "") for c in r] for r in tb]
                head = f"[ithildin table {t['id']} ({t['caption']}), extracted from p{pn}, {len(rows)} rows]"
                return head + "\n" + "\n".join("| " + " | ".join(r) + " |" for r in rows)
        a, b, _ = resolve(doc, f"p{t['page']}")
        start = t["line"]
        return (f"[ithildin table {t['id']}: no table grid detected; text after the caption follows]\n" +
                "\n".join(x for _, x in doc.lines[start:min(b, start + 60)]))
    sys.exit("ithildin: no rows stored for this table.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ithildin.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map", help="outline, page ranges, gists, tables, terms")
    m.add_argument("file")
    m.add_argument("--budget", type=int, default=int(os.environ.get("ITHILDIN_MAP_BUDGET", DEFAULT_MAP_BUDGET)))
    m.add_argument("--depth", type=int)
    f = sub.add_parser("find", help="search; several patterns in one call")
    f.add_argument("file")
    f.add_argument("patterns", nargs="+")
    f.add_argument("--regex", action="store_true")
    f.add_argument("-n", type=int, default=20)
    f.add_argument("-C", type=int, default=0)
    r = sub.add_parser("read", help="exact text of sections, pages or lines")
    r.add_argument("file")
    r.add_argument("targets", nargs="+")
    r.add_argument("--max-tokens", type=int, default=DEFAULT_READ_TOKENS)
    t = sub.add_parser("table", help="one table as rows")
    t.add_argument("file")
    t.add_argument("table_id")
    sub.add_parser("version")
    args = ap.parse_args(argv)
    if args.cmd == "version":
        print(VERSION)
        return
    doc = load(args.file)
    if args.cmd == "map":
        print(render_map(doc, args.budget, args.depth))
    elif args.cmd == "find":
        print(render_find(doc, args.patterns, args.regex, args.n, args.C))
    elif args.cmd == "read":
        print(render_read(doc, args.targets, args.max_tokens))
    elif args.cmd == "table":
        print(render_table(doc, args.table_id))


if __name__ == "__main__":
    main()
