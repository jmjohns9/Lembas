#!/usr/bin/env python3
"""Unit tests for every public function in ithildin.py. Run: python3 tests/test_ithildin_units.py

tests/test_ithildin.py checks a generated manual end to end and needs reportlab and python-docx.
These tests need only the standard library: they use Markdown, HTML and text, plus Word and
PowerPoint files assembled by hand (tests/support.py). PDF handling is in tests/test_ithildin_pdf.py.
"""
import json
import os
import re
import stat
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import ithildin  # noqa: E402

out = support.ithildin_out

MD = '''# Guide

Intro paragraph. Second sentence here.

## 1 Setup

Install the tool first. Then configure it.

```
# not a heading
  indented code
```

### 1.1 Options ###

Table 1. Flags

| Flag | Meaning |
|---|---|
| -v | verbose |
| -q | quiet |

## 2 Usage

Run it. "Dry Run" means nothing is written.
'''

TXT = """ACME WIDGET MANUAL

1 Introduction
This manual describes the widget. It is short.
1.1 Scope
Covers models A and B.
1. Remove the cover.
2. Lift the tray.
2 Installation
Mount the unit on a flat surface.
2.1 Tools Required
A screwdriver.
Appendix A Spare Parts
Order from the dealer.
"""


def path_of(name, text):
    return support.write(support.tmp("ithildin-units", name), text)


def doc_of(name, text):
    return ithildin.load(path_of(name, text))


class SmallHelpers(unittest.TestCase):
    def test_est_tokens(self):
        for text, want in [("", 0), ("a", 1), ("x" * 7, 2), ("x" * 35, 10), ("x" * 3500, 1000)]:
            self.assertEqual(ithildin.est_tokens(text), want, len(text))

    def test_words(self):
        self.assertEqual(ithildin.words("a b  c\n d"), 4)
        self.assertEqual(ithildin.words(""), 0)
        self.assertEqual(ithildin.words("   "), 0)

    def test_clip_words(self):
        self.assertEqual(ithildin.clip_words("a b c d", 2), "a b …")
        self.assertEqual(ithildin.clip_words("a b", 2), "a b")
        self.assertEqual(ithildin.clip_words("", 5), "")

    def test_norm_collapses_whitespace(self):
        self.assertEqual(ithildin.norm("  a \n b\t c  "), "a b c")
        self.assertEqual(ithildin.norm(""), "")

    def test_doc_starts_empty_and_add_records_the_page(self):
        doc = ithildin.Doc("/x/y.pdf", "PDF")
        self.assertEqual((doc.lines, doc.pages, doc.headings, doc.tables, doc.outline_source, doc.notes),
                         ([], None, [], [], "none", []))
        doc.add("first")
        doc.add("second", 3)
        self.assertEqual(doc.lines, [[None, "first"], [3, "second"]])


class Markdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ithildin.extract_markdown(path_of("guide-raw.md", MD))

    def test_lines_keep_text_and_drop_blank_lines(self):
        texts = [t for _, t in self.doc.lines]
        self.assertEqual(texts[:4], ["Guide", "Intro paragraph. Second sentence here.", "1 Setup",
                                     "Install the tool first. Then configure it."])
        self.assertNotIn("", texts)
        self.assertTrue(all(page is None for page, _ in self.doc.lines))

    def test_headings_have_level_number_and_title(self):
        self.assertEqual(self.doc.headings, [
            {"line": 0, "level": 1, "num": "", "title": "Guide"},
            {"line": 2, "level": 2, "num": "1", "title": "1 Setup"},
            {"line": 8, "level": 3, "num": "1.1", "title": "1.1 Options"},
            {"line": 13, "level": 2, "num": "2", "title": "2 Usage"}])
        self.assertEqual(self.doc.outline_source, "Markdown headings")

    def test_code_fences_keep_indentation_and_hide_headings(self):
        texts = [t for _, t in self.doc.lines]
        self.assertEqual(texts[4:8], ["```", "# not a heading", "  indented code", "```"])

    def test_tables_are_stored_as_rows_with_their_caption(self):
        self.assertEqual(len(self.doc.tables), 1)
        table = self.doc.tables[0]
        self.assertEqual(table["caption"], "Table 1. Flags")
        self.assertEqual(table["rows"], [["Flag", "Meaning"], ["-v", "verbose"], ["-q", "quiet"]])
        self.assertEqual([t for _, t in self.doc.lines[table["line"]:table["line"] + 3]],
                         ["| Flag | Meaning |", "| -v | verbose |", "| -q | quiet |"])

    def test_text_argument_is_used_instead_of_the_file(self):
        doc = ithildin.extract_markdown("/nonexistent.md", "# Only\n\nBody.\n", "Custom kind")
        self.assertEqual((doc.kind, [t for _, t in doc.lines]), ("Custom kind", ["Only", "Body."]))

    def test_table_at_the_very_end_and_table_inside_a_fence(self):
        doc = ithildin.extract_markdown("x", "| a | b |\n| 1 | 2 |")
        self.assertEqual(doc.tables[0]["rows"], [["a", "b"], ["1", "2"]])
        doc = ithildin.extract_markdown("x", "```\n| a | b |\n```\n")
        self.assertEqual(doc.tables, [])

    def test_no_headings_means_no_outline(self):
        doc = ithildin.extract_markdown("x", "just text\nmore text\n")
        self.assertEqual((doc.headings, doc.outline_source), ([], "none"))

    def test_bytes_that_are_not_utf8_do_not_crash(self):
        path = support.tmp("ithildin-units", "latin1.md")
        with open(path, "wb") as fh:
            fh.write(b"# Caf\xe9\n\nText.\n")
        doc = ithildin.extract_markdown(path)
        self.assertEqual(len(doc.headings), 1)

    def test_plain_text_has_no_outline_even_with_hash_lines(self):
        doc = ithildin.extract_text(path_of("hashes.txt", "# looks like a heading\nbody\n"))
        self.assertEqual((doc.kind, doc.headings, doc.outline_source), ("Text", [], "none"))


class Html(unittest.TestCase):
    PAGE = ("<html><body><nav>Menu item</nav><h1>Guide &amp; Notes</h1><p>Intro <b>bold</b> text.</p>"
            "<script>var hidden = 1;</script><style>.x{color:red}</style><noscript>Enable JS</noscript>"
            "<h2>Setup</h2><ul><li>First step</li><li>Second step</li></ul>"
            "<table><tr><th>Key</th><th>Value</th></tr><tr><td>a</td><td>1</td></tr></table>"
            "<div>Trailing text</div></body></html>")

    @classmethod
    def setUpClass(cls):
        cls.doc = ithildin.extract_html(path_of("page-raw.html", cls.PAGE))
        cls.texts = [t for _, t in cls.doc.lines]

    def test_headings_and_kind(self):
        self.assertEqual(self.doc.kind, "HTML page")
        self.assertEqual([(h["level"], h["title"]) for h in self.doc.headings], [(1, "Guide & Notes"), (2, "Setup")])

    def test_scripts_styles_and_navigation_are_dropped(self):
        joined = " ".join(self.texts)
        for hidden in ("Menu item", "var hidden", "color:red", "Enable JS"):
            self.assertNotIn(hidden, joined)

    def test_block_elements_become_lines_and_inline_markup_is_flattened(self):
        self.assertIn("Intro bold text.", self.texts)
        self.assertIn("First step", self.texts)
        self.assertIn("Second step", self.texts)
        self.assertEqual(self.texts[-1], "Trailing text")

    def test_table_cells_are_separated(self):
        self.assertIn("| Key | Value", self.texts)
        self.assertIn("| a | 1", self.texts)

    def test_empty_document(self):
        doc = ithildin.extract_html(path_of("empty.html", ""))
        self.assertEqual(doc.lines, [])


class Word(unittest.TestCase):
    def make(self, name, body, styles=None):
        return support.make_docx(support.tmp("ithildin-units", name), body, styles)

    def test_heading_styles_outline_levels_and_title(self):
        body = (support.w_p("Annual Report", style="Title") + support.w_p("1 Overview", style="Heading1")
                + support.w_p("Body text.") + support.w_p("1.1 Detail", style="Heading2")
                + support.w_p("By outline level", outline=2) + support.w_p(""))
        doc = ithildin.extract_docx(self.make("styles.docx", body))
        self.assertEqual(doc.kind, "Word document")
        self.assertEqual([(h["level"], h["num"], h["title"]) for h in doc.headings],
                         [(1, "", "Annual Report"), (1, "1", "1 Overview"), (2, "1.1", "1.1 Detail"),
                          (3, "", "By outline level")])
        self.assertEqual(doc.outline_source, "Word heading styles")
        self.assertEqual(len(doc.lines), 5, "the empty paragraph is dropped")

    def test_style_names_and_outline_levels_come_from_the_styles_part(self):
        styles = ('<w:style w:styleId="Kop2"><w:name w:val="heading 2"/></w:style>'
                  '<w:style w:styleId="Custom"><w:name w:val="Section Title"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>'
                  '<w:style w:styleId="Plain"><w:name w:val="Body"/></w:style>')
        body = (support.w_p("Localised heading", style="Kop2") + support.w_p("Custom heading", style="Custom")
                + support.w_p("Not a heading", style="Plain"))
        doc = ithildin.extract_docx(self.make("named-styles.docx", body, styles))
        self.assertEqual([(h["level"], h["title"]) for h in doc.headings],
                         [(2, "Localised heading"), (1, "Custom heading")])

    def test_a_very_long_heading_styled_paragraph_is_body_text(self):
        doc = ithildin.extract_docx(self.make("long.docx", support.w_p("word " * 60, style="Heading1")))
        self.assertEqual(doc.headings, [])
        self.assertEqual(doc.outline_source, "none")

    def test_tables_are_read_as_rows_and_find_their_caption(self):
        body = (support.w_p("Table 3. Limits") + support.w_tbl([["Item", "Max"], ["Pressure", "10 bar"]])
                + support.w_p("After."))
        doc = ithildin.extract_docx(self.make("table.docx", body))
        self.assertEqual(doc.tables[0]["caption"], "Table 3. Limits")
        self.assertEqual(doc.tables[0]["rows"], [["Item", "Max"], ["Pressure", "10 bar"]])
        self.assertEqual([t for _, t in doc.lines], ["Table 3. Limits", "| Item | Max |", "| Pressure | 10 bar |", "After."])

    def test_tabs_and_line_breaks_inside_a_paragraph_become_spaces(self):
        para = '<w:p><w:r><w:t>a</w:t><w:tab/><w:t>b</w:t><w:br/><w:t>c</w:t></w:r></w:p>'
        doc = ithildin.extract_docx(self.make("breaks.docx", para))
        self.assertEqual(doc.lines, [[None, "a b c"]])

    def test_through_load_and_the_commands(self):
        body = (support.w_p("1 Limits", style="Heading1") + support.w_p("The vessel is rated to 10 bar.")
                + support.w_p("2 Parts", style="Heading1") + support.w_p("Table 1. Spares")
                + support.w_tbl([["Part", "No."], ["Seal", "S-1"]]))
        path = self.make("flow.docx", body)
        self.assertRegex(out("map", path), r"(?m)^1 Limits \| L1-2 \| 9w \| The vessel is rated to 10 bar\.$")
        self.assertIn("§1 ", out("find", path, "10 bar"))
        self.assertIn("| Seal | S-1 |", out("table", path, "T1"))


class PowerPoint(unittest.TestCase):
    def make(self, name, slides, **kw):
        return support.make_pptx(support.tmp("ithildin-units", name), slides, **kw)

    def test_slides_are_pages_and_titles_are_sections(self):
        path = self.make("deck.pptx", [("Results", ["Revenue grew 3%."], None),
                                       ("Outlook", ["Flat next year.", "Costs fall."], None),
                                       (None, ["A slide without a title."], None)])
        doc = ithildin.extract_pptx(path)
        self.assertEqual((doc.kind, doc.pages, doc.outline_source), ("PowerPoint deck", 3, "slide titles"))
        self.assertEqual(doc.lines, [[1, "Results"], [1, "Revenue grew 3%."], [2, "Outlook"], [2, "Flat next year."],
                                     [2, "Costs fall."], [3, "A slide without a title."]])
        self.assertEqual([(h["line"], h["title"]) for h in doc.headings], [(0, "Results"), (2, "Outlook")])

    def test_slide_tables_are_stored_with_their_slide(self):
        path = self.make("deck-table.pptx", [("Numbers", ["Table 2. Units sold"], [["Region", "Units"], ["North", "40"]])])
        doc = ithildin.extract_pptx(path)
        self.assertEqual(doc.tables[0]["rows"], [["Region", "Units"], ["North", "40"]])
        self.assertEqual((doc.tables[0]["page"], doc.tables[0]["caption"]), (1, "Table 2. Units sold"))

    def test_slide_ten_comes_after_slide_nine(self):
        path = self.make("deck-11.pptx", [(f"Slide {i}", [f"Body {i}."], None) for i in range(1, 12)])
        doc = ithildin.extract_pptx(path)
        self.assertEqual([h["title"] for h in doc.headings], [f"Slide {i}" for i in range(1, 12)])

    def test_map_says_slides_and_find_cites_the_slide(self):
        path = self.make("deck-cmd.pptx", [(f"Quarter {i}", [f"Region {i} grew."], None) for i in range(1, 5)])
        m = out("map", path)
        self.assertIn("4 slides", m)
        self.assertIn("Quarter 3 | p3", m)
        self.assertIn(">p4 ", out("find", path, "Region 4"))
        self.assertTrue(out("read", path, "p2").startswith("[ithildin read: page 2, p2]\n[p2]\nQuarter 2"))


class AddTable(unittest.TestCase):
    def test_empty_table_is_ignored(self):
        doc = ithildin.Doc("x", "t")
        ithildin._add_table(doc, [])
        self.assertEqual((doc.tables, doc.lines), ([], []))

    def test_short_rows_are_padded_and_pipes_in_cells_are_replaced(self):
        doc = ithildin.Doc("x", "t")
        ithildin._add_table(doc, [["a", "b", "c"], ["only"], ["x|y", "", ""]], page=4)
        self.assertEqual(doc.lines, [[4, "| a | b | c |"], [4, "| only |  |  |"], [4, "| x/y |  |  |"]])
        self.assertEqual(doc.tables[0]["page"], 4)

    def test_caption_is_looked_for_in_the_two_lines_before(self):
        doc = ithildin.Doc("x", "t")
        doc.add("Table A-1: Limits")
        doc.add("(continued)")
        ithildin._add_table(doc, [["a"]])
        self.assertEqual(doc.tables[0]["caption"], "Table A-1: Limits")
        doc = ithildin.Doc("x", "t")
        doc.add("Table 9. Too far back")
        doc.add("one")
        doc.add("two")
        ithildin._add_table(doc, [["a"]])
        self.assertEqual(doc.tables[0]["caption"], "")


class DetectHeadings(unittest.TestCase):
    def test_numbered_named_and_capital_headings(self):
        doc = doc_of("widget.txt", TXT)
        self.assertEqual(doc.outline_source, "numbering and layout (no bookmarks in the file)")
        self.assertEqual([(h["id"], h["level"], h["title"]) for h in doc.headings], [
            ("S1", 1, "ACME WIDGET MANUAL"), ("1", 1, "1 Introduction"), ("1.1", 2, "1.1 Scope"),
            ("2", 1, "2 Installation"), ("2.1", 2, "2.1 Tools Required"), ("S6", 1, "Appendix A Spare Parts")])

    def test_numbered_list_items_are_not_headings(self):
        doc = doc_of("widget2.txt", TXT)
        titles = [h["title"] for h in doc.headings]
        self.assertNotIn("1. Remove the cover.", titles)
        self.assertNotIn("2. Lift the tray.", titles)

    def test_section_numbers_must_move_forward(self):
        text = "1 Intro\nbody text here\n7 Stray Number\nmore body\n2 Method\nbody\n1 Repeat\nbody\n3 Results\nbody\n"
        doc = doc_of("forward.txt", text)
        self.assertEqual([h["num"] for h in doc.headings], ["1", "2", "3"])

    def test_capital_lines_are_dropped_when_the_document_is_numbered(self):
        text = "".join(f"{i} Section Number {i}\nbody text\n" for i in range(1, 7)) + "IMPORTANT NOTICE\nbody\n"
        doc = doc_of("caps.txt", text)
        self.assertEqual(len(doc.headings), 6)

    def test_contents_lines_table_rows_and_long_lines_are_skipped(self):
        text = ("1 Introduction ........ 3\n| 2 Fake Heading |\n" + "3 " + "Very long heading " * 8 + "\n"
                + "1 Introduction\nReal body.\n2 Details\nMore body.\n3 Summary\nEnd.\n")
        doc = doc_of("skips.txt", text)
        self.assertEqual([h["title"] for h in doc.headings], ["1 Introduction", "2 Details", "3 Summary"])

    def test_contents_pages_are_skipped_in_paged_documents(self):
        doc = ithildin.Doc("x.pdf", "PDF")
        doc.pages = 3
        for line in ["1 Introduction 3", "2 Method 5", "3 Results 9", "4 Discussion 12", "5 Summary 15"]:
            doc.add(line, 1)
        for page, lines in [(2, ["1 Introduction", "Body of the introduction."]), (3, ["2 Method", "Body of the method."])]:
            for line in lines:
                doc.add(line, page)
        ithildin.detect_headings(doc)
        self.assertEqual([(h["num"], doc.lines[h["line"]][0]) for h in doc.headings], [("1", 2), ("2", 3)])

    def test_no_structure_at_all(self):
        doc = doc_of("flat.txt", "some words here\nand some more words\n")
        self.assertEqual((doc.headings, doc.outline_source), ([], "none"))


class Finish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = doc_of("guide.md", MD)
        cls.by_id = {h["id"]: h for h in cls.doc.headings}

    def test_ids_use_the_documents_own_numbers_when_it_has_them(self):
        self.assertEqual([h["id"] for h in self.doc.headings], ["S1", "1", "1.1", "2"])

    def test_repeated_numbers_fall_back_to_positional_ids(self):
        doc = doc_of("dup.md", "# 1 First\n\na\n\n# 1 Again\n\nb\n\n# 2 Other\n\nc\n")
        self.assertEqual([h["id"] for h in doc.headings], ["S1", "S2", "2"])

    def test_a_section_ends_at_the_next_heading_of_its_level_or_above(self):
        ends = {k: (h["line"], h["body_end"], h["end"]) for k, h in self.by_id.items()}
        self.assertEqual(ends, {"S1": (0, 2, 15), "1": (2, 8, 13), "1.1": (8, 13, 13), "2": (13, 15, 15)})

    def test_gist_is_the_first_sentence_of_the_sections_own_text(self):
        self.assertEqual(self.by_id["S1"]["gist"], "Intro paragraph.")
        self.assertEqual(self.by_id["1"]["gist"], "Install the tool first.")
        self.assertEqual(self.by_id["2"]["gist"], "Run it.")

    def test_word_counts_include_subsections(self):
        self.assertEqual(self.by_id["2"]["words"], 10)
        self.assertGreater(self.by_id["1"]["words"], self.by_id["1.1"]["words"])
        self.assertEqual(self.by_id["S1"]["words"], sum(ithildin.words(t) for _, t in self.doc.lines))

    def test_tables_get_ids_and_defined_terms_are_collected(self):
        self.assertEqual([t["id"] for t in self.doc.tables], ["T1"])
        self.assertEqual(self.doc.terms, [{"term": "Dry Run", "line": 14}])

    def test_defined_term_phrasings(self):
        text = ('# Definitions\n\n"Service Interval" means 500 hours. “Authorized Dealer” shall mean a listed dealer.\n\n'
                'Acme Corporation (the "Company") and its staff (each, a "Member").\n\n'
                '"Service Interval" means the same thing twice. "lowercase term" means nothing.\n')
        doc = doc_of("terms.md", text)
        self.assertEqual([t["term"] for t in doc.terms], ["Service Interval", "Authorized Dealer", "Company", "Member"])

    def test_pdf_tables_and_figures_are_found_by_caption(self):
        doc = ithildin.Doc("x.pdf", "PDF")
        doc.pages = 2
        for page, line in [(1, "1 Intro"), (1, "Table 3. Operating limits"), (1, "Figure 2: Cooling loop"),
                           (2, "Fig. 4 Wiring diagram"), (2, "Table 9 ........ 12"), (2, "Table"), (2, "See Table 3 for limits.")]:
            doc.add(line, page)
        ithildin.finish(doc)
        self.assertEqual([(t["id"], t["caption"], t["page"]) for t in doc.tables],
                         [("T1", "Table 3. Operating limits", 1), ("F1", "Figure 2: Cooling loop", 1),
                          ("F2", "Fig. 4 Wiring diagram", 2)])

    def test_gist(self):
        self.assertEqual(ithildin._gist(""), "")
        self.assertEqual(ithildin._gist("  One sentence only.  "), "One sentence only.")
        self.assertEqual(ithildin._gist("No full stop at the end"), "No full stop at the end")
        self.assertEqual(ithildin._gist("Is it? Yes."), "Is it?")
        self.assertEqual(ithildin._gist("Version 2.5 is out. Next."), "Version 2.5 is out.")
        long = " ".join(f"w{i}" for i in range(40)) + ". Next."
        self.assertEqual(ithildin._gist(long), " ".join(f"w{i}" for i in range(28)) + " …")


class Cache(unittest.TestCase):
    def setUp(self):
        self.cache = support.tmp("ithildin-units", "cache-" + self.id().rsplit(".", 1)[-1], "c")
        patcher = mock.patch.dict(os.environ, {"ITHILDIN_CACHE": self.cache})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_folder_is_created_private(self):
        self.assertEqual(ithildin.cache_dir(), self.cache)
        self.assertEqual(stat.S_IMODE(os.stat(self.cache).st_mode), 0o700)

    def test_default_folder_is_under_the_system_temp_folder(self):
        import tempfile
        with mock.patch.dict(os.environ):
            del os.environ["ITHILDIN_CACHE"]
            with mock.patch("os.makedirs"), mock.patch("os.chmod"):
                self.assertEqual(ithildin.cache_dir(), os.path.join(tempfile.gettempdir(), "ithildin"))

    def test_second_load_comes_from_the_cache(self):
        path = path_of("cached.md", MD)
        first = ithildin.load(path)
        self.assertEqual(len(os.listdir(self.cache)), 1)
        with mock.patch.object(ithildin, "extract_markdown", side_effect=AssertionError("should not re-parse")):
            second = ithildin.load(path)
        self.assertEqual((second.lines, second.headings, second.tables, second.terms, second.kind),
                         (first.lines, first.headings, first.tables, first.terms, first.kind))
        self.assertEqual(second.path, path)

    def test_a_cache_entry_does_not_store_the_path(self):
        ithildin.load(path_of("nopath.md", MD))
        entry = json.loads(support.read(os.path.join(self.cache, os.listdir(self.cache)[0])))
        self.assertNotIn("path", entry)
        self.assertEqual(entry["kind"], "Markdown")

    def test_changed_content_gets_a_new_entry(self):
        path = path_of("changing.md", "# A\n\nOne.\n")
        self.assertEqual(ithildin.load(path).headings[0]["title"], "A")
        support.write(path, "# B\n\nTwo.\n")
        self.assertEqual(ithildin.load(path).headings[0]["title"], "B")
        self.assertEqual(len(os.listdir(self.cache)), 2)

    def test_the_same_content_at_another_path_shares_the_entry(self):
        a = ithildin.load(path_of("copy-a.md", MD))
        b = ithildin.load(path_of("copy-b.md", MD))
        self.assertEqual(len(os.listdir(self.cache)), 1)
        self.assertNotEqual(a.path, b.path)

    def test_a_damaged_cache_entry_is_ignored_and_rebuilt(self):
        path = path_of("damaged.md", MD)
        ithildin.load(path)
        entry = os.path.join(self.cache, os.listdir(self.cache)[0])
        support.write(entry, "{ not json")
        self.assertEqual(len(ithildin.load(path).headings), 4)
        self.assertEqual(json.loads(support.read(entry))["kind"], "Markdown")

    def test_an_unwritable_cache_does_not_stop_the_load(self):
        path = path_of("nowrite.md", MD)
        real_open = open

        def fail_on_cache_write(file, mode="r", *a, **k):
            if str(file).startswith(self.cache) and "w" in mode:
                raise OSError("read-only")
            return real_open(file, mode, *a, **k)

        with mock.patch("builtins.open", fail_on_cache_write):
            self.assertEqual(len(ithildin.load(path).headings), 4)


class Load(unittest.TestCase):
    def test_missing_file_and_folder_exit_with_a_message(self):
        for target in ("/nonexistent/file.pdf", support.TMP):
            with self.assertRaises(SystemExit) as cm:
                ithildin.load(target)
            self.assertEqual(str(cm.exception), f"ithildin: no such file: {target}")

    def test_extension_decides_the_reader(self):
        cases = {"a.md": "Markdown", "a.markdown": "Markdown", "a.mdx": "Markdown", "a.html": "HTML page",
                 "a.htm": "HTML page", "a.xhtml": "HTML page", "a.txt": "Text", "a.text": "Text", "a.log": "Text",
                 "noextension": "Text", "A.MD": "Markdown"}
        for name, kind in cases.items():
            # Each file gets its own content: the cache is keyed on content (see the regression tests).
            self.assertEqual(doc_of(os.path.join("ext", name), f"# Title\n\nBody text for {name}.\n").kind, kind, name)

    def test_pandoc_formats_use_pandoc_when_it_is_installed(self):
        path = path_of("notes.rst", "Title\n=====\n\nBody.\n")
        result = types.SimpleNamespace(returncode=0, stdout="# Title\n\nBody from pandoc.\n", stderr="")
        with mock.patch.object(ithildin.shutil, "which", lambda name: "/usr/bin/pandoc" if name == "pandoc" else None), \
                mock.patch.object(ithildin, "_run", return_value=result) as run:
            doc = ithildin.load(path)
        self.assertEqual(run.call_args[0][0], ["pandoc", path, "-t", "gfm", "--wrap=none"])
        self.assertEqual((doc.kind, doc.headings[0]["title"]), ("RST document", "Title"))
        self.assertIn("Body from pandoc.", [t for _, t in doc.lines])

    def test_pandoc_failure_exits_with_its_message(self):
        path = path_of("broken.rst", "x")
        result = types.SimpleNamespace(returncode=1, stdout="", stderr="pandoc: cannot parse\n")
        with mock.patch.object(ithildin.shutil, "which", return_value="/usr/bin/pandoc"), \
                mock.patch.object(ithildin, "_run", return_value=result):
            with self.assertRaises(SystemExit) as cm:
                ithildin.load(path)
        self.assertEqual(str(cm.exception), f"ithildin: pandoc could not read {path}: pandoc: cannot parse")

    def test_old_office_formats_ask_for_a_conversion_when_libreoffice_is_installed(self):
        for name, target in (("old.doc", "docx"), ("old.ppt", "pptx")):
            path = path_of(name, "binary-ish")
            with mock.patch.object(ithildin.shutil, "which", lambda n: "/usr/bin/soffice" if n == "soffice" else None):
                with self.assertRaises(SystemExit) as cm:
                    ithildin.load(path)
            self.assertEqual(str(cm.exception), f"ithildin: convert first: soffice --headless --convert-to {target} {path}")

    def test_run_passes_the_command_and_captures_text(self):
        result = ithildin._run([sys.executable, "-c", "print('hello')"])
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "hello"))


class Locations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lined = doc_of("loc.md", MD)
        cls.paged = ithildin.load(support.make_pptx(support.tmp("ithildin-units", "loc.pptx"), [
            (f"Slide {i}", [f"Body {i}."], None) for i in range(1, 6)]))

    def test_loc(self):
        self.assertEqual(ithildin.loc(self.lined, 0), "L1")
        self.assertEqual(ithildin.loc(self.lined, 14), "L15")
        self.assertEqual(ithildin.loc(self.lined, 999), "L15", "past the end clamps to the last line")
        self.assertEqual(ithildin.loc(self.paged, 0), "p1")
        self.assertEqual(ithildin.loc(self.paged, 9), "p5")

    def test_span(self):
        self.assertEqual(ithildin.span(self.lined, 2, 13), "L3-13")
        self.assertEqual(ithildin.span(self.lined, 4, 5), "L5")
        self.assertEqual(ithildin.span(self.paged, 0, 10), "p1-5")
        self.assertEqual(ithildin.span(self.paged, 2, 4), "p2")

    def test_section_of(self):
        doc = doc_of("pre.md", "preamble line\n\n# First\n\nbody\n\n# Second\n\nbody\n")
        self.assertIsNone(ithildin.section_of(doc, 0))
        self.assertEqual(ithildin.section_of(doc, 1)["title"], "First")
        self.assertEqual(ithildin.section_of(doc, 2)["title"], "First")
        self.assertEqual(ithildin.section_of(doc, 3)["title"], "Second")
        self.assertEqual(ithildin.section_of(doc, 99)["title"], "Second")
        self.assertIsNone(ithildin.section_of(doc_of("none.txt", "plain\ntext\n"), 1))


def big_markdown(chapters=12, sections=5, paras=4, tables=False):
    parts = ["# Handbook\n\nIntroductory text.\n"]
    n = 0
    for c in range(1, chapters + 1):
        parts.append(f"## {c} Chapter {c}\n\nChapter {c} opens here. More words follow.\n")
        for s in range(1, sections + 1):
            parts.append(f"### {c}.{s} Topic {c}.{s}\n")
            parts.extend(f"Paragraph {p} of topic {c}.{s} mentions item {c * 100 + s * 10 + p}.\n" for p in range(paras))
            if tables:
                n += 1
                parts.append(f"Table {n}. Values for topic {c}.{s}\n\n| k | v |\n|---|---|\n| a | {n} |\n")
    return "\n".join(parts)


class RenderMap(unittest.TestCase):
    def test_header_line(self):
        doc = doc_of("map.md", MD)
        header = ithildin.render_map(doc, 2500).split("\n")[0]
        self.assertRegex(header, r'^\[ithildin map: map\.md \(Markdown, 53 words, ~\d+ tokens\)\. 4 sections, 1 tables, '
                                 r'0 figures\. Outline from Markdown headings\. Read parts: ithildin\.py read FILE '
                                 r'<id\|p12-14\|L40-90>\. Search: ithildin\.py find FILE "term" "other term"\.\]$')

    def test_outline_rows_tables_and_terms(self):
        lines = ithildin.render_map(doc_of("map2.md", MD), 2500).split("\n")
        self.assertEqual(lines[1], "S1 Guide | L1-15 | 53w | Intro paragraph.")
        self.assertEqual(lines[2], "  1 Setup | L3-13 | 37w | Install the tool first.")
        self.assertTrue(lines[3].startswith("    1.1 Options | L9-13 | "))
        self.assertEqual(lines[4], "  2 Usage | L14-15 | 10w | Run it.")
        self.assertEqual(lines[5:], ["Tables and figures:", "  T1 L11: Table 1. Flags (3 rows)", "Defined terms: Dry Run (L15)"])

    def test_document_without_structure_gets_samples(self):
        text = "\n".join(f"note {i}: something was said about item {i}." for i in range(200))
        lines = ithildin.render_map(doc_of("flatmap.txt", text), 2500).split("\n")
        self.assertEqual(lines[1], "No section structure found. Use find to locate topics, then read page or line ranges.")
        self.assertEqual(lines[2], "Text samples by location:")
        self.assertEqual(lines[3], "  L1: note 0: something was said about item 0.")
        self.assertEqual(len(lines), 23)

    def test_notes_are_shown(self):
        doc = doc_of("notes.md", MD)
        doc.notes.append("Something the reader should know.")
        self.assertIn("NOTE: Something the reader should know.", ithildin.render_map(doc, 2500))

    def test_small_budget_collapses_subsections_and_drops_gists(self):
        doc = doc_of("bigmap.md", big_markdown())
        full = ithildin.render_map(doc, 100000)
        small = ithildin.render_map(doc, 600)
        self.assertIn("1.3 Topic 1.3 | ", full)
        self.assertNotIn("1.3 Topic 1.3 | ", small)
        self.assertRegex(small, r"(?m)^  7 Chapter 7 \| L[\d-]+ \| \d+w \| 5 subsections")
        self.assertLess(ithildin.est_tokens(small), 600)
        self.assertLess(len(small), len(full) / 3)

    def test_very_small_budget_cuts_the_outline_and_says_so(self):
        # 300 top-level sections cannot be collapsed into a parent, so the outline has to be cut.
        doc = doc_of("hugemap.md", "\n".join(f"# Section {i}\n\nText {i}.\n" for i in range(300)))
        tiny = ithildin.render_map(doc, 200).split("\n")
        self.assertEqual(tiny[-1], "… outline cut to fit the budget; use --depth or find for the rest.")
        self.assertEqual(tiny[1], "S1 Section 0 | L1-2 | 4w")
        self.assertLess(len(tiny), 40)

    def test_depth_limits_the_levels_shown(self):
        doc = doc_of("depthmap.md", big_markdown())
        two = ithildin.render_map(doc, 100000, 2)
        self.assertIn("3 Chapter 3 | ", two)
        self.assertNotIn("3.1 Topic 3.1 | ", two)
        self.assertIn("| 5 subsections", two)

    def test_long_table_lists_are_cut_with_a_pointer(self):
        doc = doc_of("tablemap.md", big_markdown(tables=True))
        m = ithildin.render_map(doc, 800)
        self.assertIn("Tables and figures:", m)
        self.assertRegex(m, r'… \d+ more; find "Table" lists them\.')

    def test_more_than_thirty_terms_are_counted(self):
        text = "# Terms\n\n" + "\n\n".join(f'"Term {chr(65 + i // 26)}{chr(65 + i % 26)}" means thing {i}.' for i in range(35))
        self.assertIn(", … 5 more", ithildin.render_map(doc_of("terms35.md", text), 2500))

    def test_label(self):
        self.assertEqual(ithildin._label({"id": "7.3", "title": "7.3 Limits"}), "7.3 Limits")
        self.assertEqual(ithildin._label({"id": "S4", "title": "Limits"}), "S4 Limits")


class Resolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = doc_of("resolve.md", MD)
        cls.deck = ithildin.load(support.make_pptx(support.tmp("ithildin-units", "resolve.pptx"), [
            ("One", ["Body one."], None), (None, [], None), ("Three", ["Body three."], None)]))

    def exits(self, doc, target):
        with self.assertRaises(SystemExit) as cm:
            ithildin.resolve(doc, target)
        return str(cm.exception)

    def test_section_ids_numbers_and_titles(self):
        self.assertEqual(ithildin.resolve(self.doc, "1.1"), (8, 13, "1.1 Options"))
        self.assertEqual(ithildin.resolve(self.doc, " §1 "), (2, 13, "1 Setup"))
        self.assertEqual(ithildin.resolve(self.doc, "s1"), (0, 15, "S1 Guide"))
        self.assertEqual(ithildin.resolve(self.doc, "usage"), (13, 15, "2 Usage"))

    def test_line_ranges(self):
        self.assertEqual(ithildin.resolve(self.doc, "L3-4"), (2, 4, "lines 3-4"))
        self.assertEqual(ithildin.resolve(self.doc, "l7"), (6, 7, "lines 7-7"))
        self.assertEqual(ithildin.resolve(self.doc, "L10 - L12"), (9, 12, "lines 10-12"))
        self.assertEqual(ithildin.resolve(self.doc, "L14-999"), (13, 15, "lines 14-999"))

    def test_page_ranges(self):
        self.assertEqual(ithildin.resolve(self.deck, "p1"), (0, 2, "page 1"))
        self.assertEqual(ithildin.resolve(self.deck, "P1-3"), (0, 4, "pages 1-3"))
        self.assertEqual(ithildin.resolve(self.deck, "p3-p3"), (2, 4, "page 3"))

    def test_pages_on_a_document_without_pages(self):
        self.assertEqual(self.exits(self.doc, "p3"),
                         "ithildin: this document has no pages; use a section id or a line range like L40-90.")

    def test_pages_with_no_text(self):
        self.assertEqual(self.exits(self.deck, "p2"), "ithildin: no text on pages 2-2 (document has 3 pages).")
        self.assertEqual(self.exits(self.deck, "p9-12"), "ithildin: no text on pages 9-12 (document has 3 pages).")

    def test_ambiguous_title_lists_the_candidates(self):
        doc = doc_of("ambiguous.md", "# 1 Fuel System\n\na\n\n# 2 Fuel Filter\n\nb\n")
        self.assertEqual(self.exits(doc, "fuel"),
                         "ithildin: several sections match; pick one id: 1 1 Fuel System; 2 2 Fuel Filter")

    def test_unknown_target(self):
        self.assertEqual(self.exits(self.doc, "99.9"),
                         "ithildin: no section, page or line range matches '99.9'. Run map to see ids.")

    def test_a_repeated_number_resolves_to_its_first_section(self):
        doc = doc_of("dupnum.md", "# 1 First\n\na\n\n# 1 Again\n\nb\n")
        self.assertEqual(ithildin.resolve(doc, "1"), (0, 2, "S1 1 First"))


class RenderRead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = doc_of("read.md", MD)

    def test_section_text_is_exact(self):
        self.assertEqual(ithildin.render_read(self.doc, ["2"], 8000),
                         '[ithildin read: 2 Usage, L14-15]\n2 Usage\nRun it. "Dry Run" means nothing is written.')

    def test_a_section_includes_its_subsections(self):
        text = ithildin.render_read(self.doc, ["1"], 8000)
        self.assertIn("1.1 Options", text)
        self.assertIn("| -q | quiet |", text)
        self.assertNotIn("2 Usage", text)

    def test_several_targets_in_one_call(self):
        text = ithildin.render_read(self.doc, ["L1-2", "2"], 8000)
        self.assertEqual(text.count("[ithildin read: "), 2)
        self.assertTrue(text.startswith("[ithildin read: lines 1-2, L1-2]\nGuide\nIntro paragraph."))

    def test_page_markers_appear_where_the_page_changes(self):
        deck = ithildin.load(support.make_pptx(support.tmp("ithildin-units", "read.pptx"), [
            ("One", ["Body one."], None), ("Two", ["Body two."], None)]))
        self.assertEqual(ithildin.render_read(deck, ["p1-2"], 8000),
                         "[ithildin read: pages 1-2, p1-2]\n[p1]\nOne\nBody one.\n[p2]\nTwo\nBody two.")

    def test_truncation_says_where_to_continue_and_which_subsections_remain(self):
        doc = doc_of("readbig.md", big_markdown())
        text = ithildin.render_read(doc, ["3"], 150)
        last = text.split("\n")[-1]
        m = re.match(r"^\[truncated at L(\d+) to stay under 150 tokens\. Continue with: read FILE L(\d+)-(\d+) "
                     r"or by subsection: ([\d., ]+)\]$", last)
        self.assertTrue(m, last)
        self.assertEqual(m.group(1), m.group(2))
        self.assertTrue(set(m.group(4).split(", ")) <= {"3.1", "3.2", "3.3", "3.4", "3.5"})
        shown = text.split("\n")[1:-1]
        self.assertLessEqual(sum(ithildin.est_tokens(t) + 1 for t in shown), 150)
        rest = ithildin.render_read(doc, [f"L{m.group(2)}-{m.group(3)}"], 100000).split("\n")[1:]
        whole = ithildin.render_read(doc, ["3"], 100000).split("\n")[1:]
        self.assertEqual(shown + rest, whole, "the continuation picks up exactly where the first read stopped")

    def test_the_token_budget_is_shared_between_targets(self):
        doc = doc_of("readshared.md", big_markdown())
        text = ithildin.render_read(doc, ["1.1", "1.2"], 70)
        self.assertEqual(text.count("[ithildin read: "), 2)
        self.assertIn("[truncated at ", text)


class RenderFind(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = doc_of("find.md", MD)

    def find(self, *patterns, regex=False, limit=20, context=0, doc=None):
        return ithildin.render_find(doc or self.doc, list(patterns), regex, limit, context)

    def test_one_hit_with_its_section_and_location(self):
        self.assertEqual(self.find("verbose"),
                         "[ithildin find: 'verbose': 1 hits in 1 sections (1.1)]\n== 'verbose' (1 hits)\n"
                         ">L12 §1.1 | | -v | verbose |")

    def test_search_ignores_case(self):
        self.assertIn("1 hits", self.find("INSTALL THE TOOL"))

    def test_several_patterns_each_get_a_count(self):
        first = self.find("verbose", "nothing here", "it").split("\n")[0]
        self.assertRegex(first, r"^\[ithildin find: 'verbose': 1 hits in 1 sections \(1\.1\); "
                                r"'nothing here': 0 hits in 0 sections; 'it': \d+ hits in \d+ sections \(.+\)\]$")

    def test_plain_patterns_are_literal_and_regex_is_opt_in(self):
        self.assertIn("0 hits", self.find("verbos."))
        self.assertIn("1 hits", self.find("verbos.", regex=True))
        self.assertIn("2 hits", self.find(r"^\| -[vq] ", regex=True))

    def test_a_phrase_that_wraps_onto_the_next_line_is_found_once(self):
        doc = doc_of("wrap.txt", "the maximum coolant\noutlet temperature is high\nunrelated line\n")
        text = self.find("coolant outlet", doc=doc)
        self.assertIn("'coolant outlet': 1 hits", text)
        self.assertIn(">L1  | the maximum coolant", text)

    def test_limit_shows_the_first_hits_and_counts_the_rest(self):
        doc = doc_of("many.md", big_markdown())
        text = self.find("Paragraph", limit=3, doc=doc)
        self.assertEqual(len([l for l in text.split("\n") if l.startswith(">")]), 3)
        self.assertIn("  … 237 more; narrow the pattern or raise -n.", text)

    def test_context_lines_surround_the_hit(self):
        lines = self.find("verbose", context=1).split("\n")[2:]
        self.assertEqual(lines, [" L11 §1.1 | | Flag | Meaning |", ">L12 §1.1 | | -v | verbose |",
                                 " L13 §1.1 | | -q | quiet |"])

    def test_hits_before_the_first_heading_have_no_section(self):
        doc = doc_of("preamble.md", "needle in the preamble\n\n# First\n\nbody\n")
        self.assertEqual(self.find("needle", doc=doc),
                         "[ithildin find: 'needle': 1 hits in 1 sections]\n== 'needle' (1 hits)\n>L1  | needle in the preamble")

    def test_long_lines_are_cut_in_the_listing(self):
        doc = doc_of("longline.txt", "needle " + "x" * 600 + "\n")
        self.assertLess(len(self.find("needle", doc=doc).split("\n")[-1]), 260)

    def test_many_sections_are_abbreviated_in_the_summary(self):
        doc = doc_of("sections.md", big_markdown(chapters=20, sections=1, paras=1))
        self.assertIn(", …)", self.find("mentions item", doc=doc).split("\n")[0])


class RenderTable(unittest.TestCase):
    def test_table_by_id_in_any_case(self):
        doc = doc_of("table.md", MD)
        want = ("[ithildin table T1 at L11: Table 1. Flags, 3 rows]\n| Flag | Meaning |\n| -v | verbose |\n| -q | quiet |")
        self.assertEqual(ithildin.render_table(doc, "T1"), want)
        self.assertEqual(ithildin.render_table(doc, "t1"), want)

    def test_a_table_without_a_caption_says_so(self):
        doc = doc_of("nocap.md", "# A\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        self.assertTrue(ithildin.render_table(doc, "T1").startswith("[ithildin table T1 at L2: no caption, 2 rows]"))

    def test_unknown_table_lists_the_ones_that_exist(self):
        with self.assertRaises(SystemExit) as cm:
            ithildin.render_table(doc_of("table2.md", MD), "T9")
        self.assertEqual(str(cm.exception), "ithildin: no table 'T9'. Tables: T1")

    def test_a_table_with_no_stored_rows_outside_a_pdf(self):
        doc = doc_of("table3.md", MD)
        doc.tables[0].pop("rows")
        with self.assertRaises(SystemExit) as cm:
            ithildin.render_table(doc, "T1")
        self.assertEqual(str(cm.exception), "ithildin: no rows stored for this table.")


class Main(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = path_of("main.md", MD)

    def test_version(self):
        self.assertEqual(out("version"), ithildin.VERSION + "\n")

    def test_each_command_prints_its_view(self):
        self.assertTrue(out("map", self.path).startswith("[ithildin map: main.md "))
        self.assertTrue(out("find", self.path, "verbose").startswith("[ithildin find: 'verbose': 1 hits"))
        self.assertTrue(out("read", self.path, "2").startswith("[ithildin read: 2 Usage, L14-15]"))
        self.assertTrue(out("table", self.path, "T1").startswith("[ithildin table T1 at L11"))

    def test_options_reach_the_views(self):
        self.assertNotIn("1.1 Options", out("map", self.path, "--depth", "2"))
        self.assertIn(" L11 ", out("find", self.path, "verbose", "-C", "1"))
        self.assertIn("1 hits", out("find", self.path, "--regex", "verb.se"))
        self.assertIn("more; narrow", out("find", self.path, "e", "-n", "1"))
        self.assertIn("[truncated at ", out("read", self.path, "S1", "--max-tokens", "5"))

    def test_map_budget_default_can_come_from_the_environment(self):
        doc_path = path_of("envbudget.md", big_markdown())
        with mock.patch.dict(os.environ, {"ITHILDIN_MAP_BUDGET": "500"}):
            small = out("map", doc_path)
        self.assertLess(len(small), len(out("map", doc_path)))

    def test_usage_errors_exit_with_status_two(self):
        for argv in ([], ["map"], ["find", self.path], ["nonsense", self.path], ["map", self.path, "--budget", "x"]):
            with self.assertRaises(SystemExit) as cm, mock.patch.object(sys, "stderr"):
                ithildin.main(argv)
            self.assertEqual(cm.exception.code, 2, argv)

    def test_command_line_end_to_end(self):
        r = support.run_py(support.ITHILDIN_PY, "read", self.path, "2")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.decode("utf-8"),
                         '[ithildin read: 2 Usage, L14-15]\n2 Usage\nRun it. "Dry Run" means nothing is written.\n')
        r = support.run_py(support.ITHILDIN_PY, "read", self.path, "99")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Run map to see ids", r.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
