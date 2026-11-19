#!/usr/bin/env python3
"""Tests for ithildin.py's PDF handling. Run: python3 tests/test_ithildin_pdf.py

The first half needs nothing installed: poppler's pdftotext and the pypdf library are replaced
with stand-ins, so the "present", "missing" and "failed" paths all run on any machine.
The second half builds small real PDFs and is skipped without reportlab and pypdf.
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import ithildin  # noqa: E402

PAGE = "This page holds enough ordinary text to count as a real text layer, number {}."


def fake_pdftotext(stdout, returncode=0):
    """Patches that make ithildin believe pdftotext is installed and printed `stdout`."""
    result = types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")
    return (mock.patch.object(ithildin.shutil, "which", lambda name: "/usr/bin/pdftotext" if name == "pdftotext" else None),
            mock.patch.object(ithildin, "_run", return_value=result))


def no_pdftotext():
    return mock.patch.object(ithildin.shutil, "which", return_value=None)


def fake_pypdf(pages):
    """A stand-in pypdf module whose reader returns the given page texts and no bookmarks."""
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self, **kwargs):
            return self.text

    class PdfReader:
        outline = []

        def __init__(self, path):
            self.pages = [Page(t) for t in pages]

    return mock.patch.dict(sys.modules, {"pypdf": types.SimpleNamespace(PdfReader=PdfReader)})


def without(module):
    """Make `import <module>` raise ImportError, as if it were not installed."""
    return mock.patch.dict(sys.modules, {module: None})


class WithPdftotext(unittest.TestCase):
    def extract(self, stdout):
        which, run = fake_pdftotext(stdout)
        with which, run as run_mock, without("pypdf"):
            doc = ithildin.extract_pdf("/fake/report.pdf")
        return doc, run_mock

    def test_pages_are_split_on_form_feeds(self):
        doc, run = self.extract(PAGE.format(1) + "\nSecond   line\n\f" + PAGE.format(2) + "\n\f")
        self.assertEqual(run.call_args[0][0], ["pdftotext", "-enc", "UTF-8", "/fake/report.pdf", "-"])
        self.assertEqual((doc.kind, doc.pages), ("PDF", 2))
        self.assertEqual(doc.lines, [[1, PAGE.format(1)], [1, "Second line"], [2, PAGE.format(2)]])
        self.assertEqual(doc.notes, [])

    def test_a_blank_page_in_the_middle_still_counts(self):
        doc, _ = self.extract(PAGE.format(1) + "\f\f" + PAGE.format(3) + "\f")
        self.assertEqual(doc.pages, 3)
        self.assertEqual([p for p, _ in doc.lines], [1, 3])

    def test_a_pdf_with_almost_no_text_gets_a_scanned_note(self):
        doc, _ = self.extract("x\f\f\f\f")
        self.assertEqual(doc.pages, 4)
        self.assertEqual(len(doc.notes), 1)
        self.assertIn("scanned PDF", doc.notes[0])
        self.assertIn("ocrmypdf", doc.notes[0])

    def test_running_headers_and_footers_are_removed(self):
        topics = ["pumps", "valves", "filters", "belts", "gauges", "seals"]
        pages = "".join(f"ACME Manual  Rev C\nThis page is about {t} and how to inspect them properly.\n"
                        f"Replace worn {t} before the next shift begins.\nPage {i}\n\f" for i, t in enumerate(topics, 1))
        doc, _ = self.extract(pages)
        texts = [t for _, t in doc.lines]
        self.assertFalse(any("Rev C" in t for t in texts))
        self.assertFalse(any(t.startswith("Page ") for t in texts))
        self.assertEqual(len(texts), 12)
        self.assertEqual(texts[0], "This page is about pumps and how to inspect them properly.")

    def test_without_pypdf_the_outline_steps_are_skipped_quietly(self):
        doc, _ = self.extract(PAGE.format(1) + "\f")
        self.assertEqual((doc.headings, doc.outline_source), ([], "none"))


class WithoutPdftotext(unittest.TestCase):
    def test_pypdf_is_used_instead(self):
        with no_pdftotext(), fake_pypdf([PAGE.format(1) + "\nline two", None, PAGE.format(3)]):
            doc = ithildin.extract_pdf("/fake/report.pdf")
        self.assertEqual(doc.pages, 3)
        self.assertEqual(doc.lines, [[1, PAGE.format(1)], [1, "line two"], [3, PAGE.format(3)]])

    def test_a_failed_pdftotext_run_also_falls_back_to_pypdf(self):
        which, run = fake_pdftotext("", returncode=1)
        with which, run, fake_pypdf([PAGE.format(1)]):
            doc = ithildin.extract_pdf("/fake/report.pdf")
        self.assertEqual(doc.lines, [[1, PAGE.format(1)]])

    def test_with_neither_tool_the_message_says_what_to_install(self):
        for patches in ((no_pdftotext(),), fake_pdftotext("", returncode=1)):
            with self.assertRaises(SystemExit) as cm:
                with without("pypdf"):
                    for p in patches:
                        p.start()
                    try:
                        ithildin.extract_pdf("/fake/report.pdf")
                    finally:
                        for p in patches:
                            p.stop()
            self.assertEqual(str(cm.exception),
                             "ithildin: reading PDF needs pdftotext (poppler-utils) or `pip install pypdf`.")


class StripRunningLines(unittest.TestCase):
    def doc(self, pages):
        doc = ithildin.Doc("x.pdf", "PDF")
        doc.pages = len(pages)
        for number, lines in enumerate(pages, 1):
            for line in lines:
                doc.add(line, number)
        return doc

    def test_short_documents_are_left_alone(self):
        doc = self.doc([["Header", "body a"], ["Header", "body b"], ["Header", "body c"]])
        ithildin._strip_running_lines(doc)
        self.assertEqual(len(doc.lines), 6)

    def test_lines_that_differ_only_by_a_number_count_as_the_same(self):
        doc = self.doc([[f"body line {i} here", f"more body for page {i}", f"- {i} -"] for i in range(1, 9)])
        ithildin._strip_running_lines(doc)
        self.assertFalse(any(t.startswith("- ") for _, t in doc.lines))
        self.assertEqual(len(doc.lines), 0, "these body lines also differ only by a number, so they go too")

    def test_a_line_that_recurs_in_the_middle_of_pages_is_kept(self):
        pages = [["top a%d" % i, "x", "y", "z", "Recurring middle line", "p", "q", "bottom b%d" % i] for i in range(8)]
        doc = self.doc(pages)
        ithildin._strip_running_lines(doc)
        self.assertEqual(sum(t == "Recurring middle line" for _, t in doc.lines), 8)

    def test_nothing_recurring_means_nothing_removed(self):
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
        doc = self.doc([[f"{w} one", f"{w} two"] for w in words])
        ithildin._strip_running_lines(doc)
        self.assertEqual(len(doc.lines), 12)


try:
    import pypdf  # noqa: F401
    import reportlab  # noqa: F401
    HAVE_PDF_LIBS = True
except ImportError:
    HAVE_PDF_LIBS = False


def build_pdf(path, bookmarks):
    """Four chapters with one subsection each, one captioned table and one figure caption.

    Chapters flow on from one another, so headings fall wherever the text puts them. A heading
    that opens every page, numbered like the pages, looks like a running header and is removed (review I-43).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()

    class Template(SimpleDocTemplate):
        count = 0

        def afterFlowable(self, flowable):
            if bookmarks and isinstance(flowable, Paragraph) and flowable.style.name in ("Heading1", "Heading2"):
                key = f"k{self.count}"
                self.count += 1
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(flowable.getPlainText(), key, level=0 if flowable.style.name == "Heading1" else 1,
                                          closed=False)

    story = []
    for c in range(1, 5):
        story += [Paragraph(f"{c} Chapter {c}", ss["Heading1"]),
                  Paragraph(f"Chapter {c} begins with this sentence. " + "Filler words keep the page busy. " * 70, ss["BodyText"]),
                  Paragraph(f"{c}.1 Detail {c}", ss["Heading2"]),
                  Paragraph(f"Detail {c} is described here. " + "More filler words follow along. " * 70, ss["BodyText"])]
        if c == 2:
            story += [Paragraph("Table 1. Operating limits", ss["BodyText"]),
                      Table([["Item", "Limit"], ["Pressure", "10 bar"], ["Speed", "900 rpm"]],
                            style=TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)])),
                      Spacer(1, 12), Paragraph("Figure 1. Cooling loop layout", ss["BodyText"])]
    Template(path, pagesize=letter).build(story)
    return path


@unittest.skipUnless(HAVE_PDF_LIBS, "reportlab and pypdf are needed to build and read real PDFs")
class RealPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.marked = build_pdf(support.tmp("ithildin-pdf", "marked.pdf"), bookmarks=True)
        cls.flat = build_pdf(support.tmp("ithildin-pdf", "flat.pdf"), bookmarks=False)

    def outline(self, path):
        doc = ithildin.load(path)
        return doc, [(h["level"], h["id"], h["title"]) for h in doc.headings]

    def test_bookmarks_give_the_outline(self):
        doc, outline = self.outline(self.marked)
        self.assertEqual(doc.outline_source, "PDF bookmarks")
        self.assertEqual(outline[:4], [(1, "1", "1 Chapter 1"), (2, "1.1", "1.1 Detail 1"), (1, "2", "2 Chapter 2"),
                                       (2, "2.1", "2.1 Detail 2")])
        self.assertEqual(len(outline), 8)

    def test_type_sizes_give_the_same_outline_when_there_are_no_bookmarks(self):
        marked, with_bookmarks = self.outline(self.marked)
        flat, from_sizes = self.outline(self.flat)
        self.assertEqual(flat.outline_source, "type sizes (no bookmarks in the file)")
        self.assertEqual(from_sizes, with_bookmarks)
        self.assertEqual([h["line"] for h in flat.headings], [h["line"] for h in marked.headings])

    def test_both_text_backends_agree_on_pages_and_sections(self):
        with mock.patch.dict(os.environ, {"ITHILDIN_CACHE": support.tmp("ithildin-pdf", "cache-pypdf", "c")}), no_pdftotext():
            fallback = ithildin.load(self.marked)
        default = ithildin.load(self.marked)
        self.assertEqual(fallback.pages, default.pages)
        self.assertEqual([(h["id"], fallback.lines[h["line"]][0]) for h in fallback.headings],
                         [(h["id"], default.lines[h["line"]][0]) for h in default.headings])

    def test_type_size_detection_is_skipped_for_enormous_documents(self):
        doc = ithildin.Doc(self.flat, "PDF")
        doc.pages = 5
        ithildin._pdf_font_headings(doc, max_pages=4)
        self.assertEqual(doc.headings, [])

    def test_outline_helpers_tolerate_a_file_that_is_not_a_pdf(self):
        doc = ithildin.Doc(support.write(support.tmp("ithildin-pdf", "not.pdf"), "not a pdf"), "PDF")
        doc.pages = 1
        ithildin._pdf_outline(doc)
        ithildin._pdf_font_headings(doc)
        self.assertEqual((doc.headings, doc.outline_source), ([], "none"))

    def test_captions_become_table_and_figure_entries(self):
        doc = ithildin.load(self.marked)
        self.assertEqual([(t["id"], t["caption"]) for t in doc.tables],
                         [("T1", "Table 1. Operating limits"), ("F1", "Figure 1. Cooling loop layout")])
        m = support.ithildin_out("map", self.marked)
        self.assertIn("8 sections, 1 tables, 1 figures", m)
        self.assertRegex(m, r"(?m)^  T1 p\d+: Table 1\. Operating limits$")

    def test_table_rows_are_extracted_from_the_grid_under_the_caption(self):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("pdfplumber is not installed")
        text = support.ithildin_out("table", self.marked, "T1")
        self.assertRegex(text.split("\n")[0], r"^\[ithildin table T1 \(Table 1\. Operating limits\), extracted from p\d+, 3 rows\]$")
        self.assertEqual(text.split("\n")[1:4], ["| Item | Limit |", "| Pressure | 10 bar |", "| Speed | 900 rpm |"])

    def test_without_pdfplumber_the_text_after_the_caption_is_returned(self):
        with without("pdfplumber"):
            text = support.ithildin_out("table", self.marked, "T1")
        lines = text.split("\n")
        self.assertEqual(lines[0], "[ithildin table T1: no table grid detected; text after the caption follows]")
        self.assertEqual(lines[1], "Table 1. Operating limits")

    def test_read_marks_each_page(self):
        doc = ithildin.load(self.marked)
        first, last = doc.lines[0][0], doc.lines[-1][0]
        text = support.ithildin_out("read", self.marked, f"p{first}-{last}", "--max-tokens", "100000")
        for page in sorted({p for p, _ in doc.lines}):
            self.assertIn(f"[p{page}]", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
