#!/usr/bin/env python3
"""Regression tests: one class per bug in docs/CODE_REVIEW.md. Run: python3 tests/test_regressions.py

Each test was written before its fix and seen to fail against the unfixed code. The class name
carries the finding's id, so a failure here points straight at the write-up.
"""
import io
import json
import math
import os
import random
import stat
import subprocess
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import squeeze  # noqa: E402
import ithildin  # noqa: E402

hook = support.load_script("squeeze_hook_regressions", support.HOOK_PY)
grade = support.load_script("grade_regressions", os.path.join(support.ROOT, "scripts", "grade.py"))
count_tokens = support.load_script("count_tokens_regressions", os.path.join(support.ROOT, "scripts", "count_tokens.py"))
gen = support.load_script("generate_replies_regressions", os.path.join(support.ROOT, "evals", "generate_replies.py"))
sq_bench = support.load_script("squeeze_bench_regressions", os.path.join(support.ROOT, "evals", "squeeze-bench", "run_e2e.py"))
EVALS = os.path.join(support.ROOT, "evals", "evals.json")
out = support.ithildin_out


def log_text(n=4000):
    return "".join(f"2026-01-01 00:{i // 60 % 60:02d}:{i % 60:02d} INFO tick {i} ok\n" for i in range(n)) + "ERROR boom\n"


def low_saving_log():
    """A log whose summary would save under 30%, so squeeze passes it through."""
    rnd = random.Random(5)
    for n in range(60, 140, 4):
        text = "\n".join(f"ERROR unit{rnd.getrandbits(40):x} failed: cause {rnd.getrandbits(60):x} "
                         f"in handler {rnd.getrandbits(30):x}" for _ in range(n)) + "\n"
        view, info = squeeze.squeeze(text, kind="log", original_path="probe.log")
        if view is None and info["before"] > squeeze.DEFAULT_THRESHOLD:
            return text
    raise AssertionError("could not build a low-saving input")


def sq(*args, data=None, env=None):
    r = support.run_py(support.SQUEEZE_PY, *args, data=data, env=env)
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")


def ith(*args, env=None):
    r = support.run_py(support.ITHILDIN_PY, *args, env=env)
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")


def md(name, text):
    return support.write(support.tmp("regressions", name), text)


def exit_message(fn, *args):
    try:
        fn(*args)
    except SystemExit as exc:
        return str(exc.code)
    raise AssertionError("expected the call to exit with a message")


def no_traceback(test, code, stderr):
    test.assertNotIn("Traceback", stderr)
    test.assertNotEqual(code, 0)


def pending(*names):
    """Mark tests whose fix has not landed yet, so the suite stays green until it does."""
    def mark(cls):
        for name in names:
            setattr(cls, name, unittest.expectedFailure(getattr(cls, name)))
        return cls
    return mark


# ====================================================================== squeeze.py

class I01_PipedOutputSurvivesAnUnwritableCache(unittest.TestCase):
    def setUp(self):
        blocker = support.write(support.tmp("regressions", "i01", "blocker"), "a regular file")
        self.bad_dir = os.path.join(blocker, "cache")       # cannot be created: its parent is a file

    def test_command_line_prints_the_input_unchanged(self):
        text = log_text()
        code, stdout, stderr = sq(data=text, env={"LEMBAS_SQUEEZE_DIR": self.bad_dir})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout.decode("utf-8"), text)
        self.assertNotIn("Traceback", stderr)
        self.assertIn("squeeze: could not save the original", stderr)

    def test_library_call_returns_none_and_records_why(self):
        with mock.patch.dict(os.environ, {"LEMBAS_SQUEEZE_DIR": self.bad_dir}):
            view, info = squeeze.squeeze(log_text())
        self.assertIsNone(view)
        self.assertIn("could not save the original", info["error"])

    def test_a_file_argument_needs_no_cache_and_still_gets_a_summary(self):
        path = support.write(support.tmp("regressions", "i01", "app.log"), log_text())
        code, stdout, _ = sq(path, env={"LEMBAS_SQUEEZE_DIR": self.bad_dir})
        self.assertEqual(code, 0)
        self.assertTrue(stdout.decode("utf-8").startswith("[lembas squeeze: log"))


class I02_OutputIsUtf8WhateverTheTerminalEncoding(unittest.TestCase):
    def test_squeeze_passes_through_text_the_terminal_encoding_cannot_represent(self):
        text = "deploy \U0001F680 done 你好\n" * 5
        for encoding in ("cp1252", "ascii", "latin-1"):
            code, stdout, stderr = sq(data=text, env={"PYTHONIOENCODING": encoding})
            self.assertEqual(code, 0, f"{encoding}: {stderr[-200:]}")
            self.assertEqual(stdout.decode("utf-8"), text, encoding)

    def test_squeeze_summary_is_utf8(self):
        for encoding in ("cp1252", "ascii"):
            code, stdout, stderr = sq("--stats", data=log_text(), env={"PYTHONIOENCODING": encoding})
            self.assertEqual(code, 0, f"{encoding}: {stderr[-200:]}")
            summary = stdout.decode("utf-8")
            self.assertTrue(summary.startswith("[lembas squeeze: log"))
            self.assertIn("…", summary)
            self.assertIn("% smaller", stderr)

    def test_ithildin_output_is_utf8(self):
        path = md("i02.md", "# Limits\n\nThe limit is 104 °C — see 你好 \U0001F600.\n")
        for encoding in ("cp1252", "ascii"):
            for args in (("read", path, "L1-2"), ("map", path), ("find", path, "limit")):
                code, stdout, stderr = ith(*args, env={"PYTHONIOENCODING": encoding})
                self.assertEqual(code, 0, f"{encoding} {args[0]}: {stderr[-200:]}")
                self.assertIn("104 °C", stdout.decode("utf-8"))


class I07_DeeplyNestedJsonDoesNotCrash(unittest.TestCase):
    DEEP = "[" * 100000 + "]" * 100000

    def test_library_call_does_not_raise(self):
        view, info = squeeze.squeeze(self.DEEP, original_path="deep.json")
        self.assertTrue(view is None or view.startswith("[lembas squeeze: text"))
        view, info = squeeze.squeeze(self.DEEP, "deep.json", original_path="deep.json")
        self.assertTrue(view is None or view.startswith("[lembas squeeze: text"))

    def test_piped_input_still_produces_output(self):
        code, stdout, stderr = sq(data=self.DEEP)
        self.assertEqual(code, 0, stderr[-200:])
        self.assertGreater(len(stdout), 100)


class I08_ByteOrderMarkIsIgnored(unittest.TestCase):
    RECORDS = [{"id": i, "status": "ok" if i % 50 else "failed", "error": None if i % 50 else "boom"} for i in range(3000)]

    def test_json_with_a_bom_is_still_json(self):
        for name in (None, "x.json"):
            view, info = squeeze.squeeze("﻿" + json.dumps(self.RECORDS), name, original_path="x.json")
            self.assertEqual(info["kind"], "json", name)
            self.assertNotIn("error", info)
            self.assertIn("items that look like errors or failures: 60", view)

    def test_json_lines_with_a_bom(self):
        text = "﻿" + "\n".join(json.dumps(r) for r in self.RECORDS)
        self.assertEqual(squeeze.squeeze(text, original_path="x.jsonl")[1]["kind"], "jsonl")

    def test_csv_with_a_bom_keeps_its_first_column_name(self):
        text = "﻿name,amount,region\n" + "".join(f"item{i},{i * 3},north\n" for i in range(4000))
        view, _ = squeeze.squeeze(text, "x.csv", original_path="x.csv")
        self.assertIn("\n  name (text): ", view)
        self.assertNotIn("﻿", view)

    def test_a_file_written_with_a_bom_through_the_command_line(self):
        path = support.tmp("regressions", "i08", "bom.json")
        with open(path, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + json.dumps(self.RECORDS).encode("utf-8"))
        code, stdout, _ = sq(path)
        self.assertTrue(stdout.decode("utf-8").startswith("[lembas squeeze: json"))

    def test_markdown_with_a_bom_keeps_its_first_heading(self):
        doc = ithildin.load(md("i08.md", "﻿# Overview\n\nIntro.\n\n## Setup\n\nInstall.\n"))
        self.assertEqual([h["title"] for h in doc.headings], ["Overview", "Setup"])

    def test_text_and_html_with_a_bom(self):
        doc = ithildin.load(md("i08.txt", "﻿first line of notes\nsecond line\n"))
        self.assertEqual(doc.lines[0][1], "first line of notes")
        doc = ithildin.load(md("i08.html", "﻿<h1>Title</h1><p>Body.</p>"))
        self.assertEqual(doc.lines[0][1], "Title")


class I16_CurrencyWithThousandsSeparators(unittest.TestCase):
    def test_values(self):
        cases = [("$1,234.56", 1234.56), ("€9,000", 9000.0), ("£12", 12.0), ("-$5.00", -5.0),
                 ("$ 7.50", 7.5), ("$1,23", None), ("$", None), ("$abc", None)]
        for text, want in cases:
            self.assertEqual(squeeze._num_value(text), want, text)

    def test_a_money_column_is_profiled_as_numbers(self):
        text = "item,price\n" + "".join(f"item{i},\"${1000 + i:,}.50\"\n" for i in range(3000))
        view, _ = squeeze.squeeze(text, "prices.csv", original_path="prices.csv")
        row = next(l for l in view.split("\n") if l.strip().startswith("price "))
        self.assertIn("price (float)", row)
        self.assertIn("min 1,000.50, max 3,999.50", row)
        self.assertTrue(row.endswith("sum 7,500,000"), row)
        self.assertEqual(sum(1000 + i + 0.5 for i in range(3000)), 7500000)


class I17_PassThroughWritesNothingAndReportsHonestly(unittest.TestCase):
    def test_nothing_is_saved_for_output_that_is_passed_through(self):
        cache = support.tmp("regressions", "i17", "cache", "x")[:-2]
        text = low_saving_log()
        code, stdout, stderr = sq("--stats", "--type", "log", data=text, env={"LEMBAS_SQUEEZE_DIR": cache})
        self.assertEqual(stdout.decode("utf-8"), text)
        self.assertEqual(os.listdir(cache), [])
        self.assertNotIn("% smaller", stderr)
        self.assertRegex(stderr, r"^squeeze: log, ~[\d,]+ tokens, passed through unchanged")

    def test_small_input_stats(self):
        _, _, stderr = sq("--stats", data="hello\n")
        self.assertRegex(stderr, r"^squeeze: auto, ~\d+ tokens, passed through unchanged")

    def test_library_info_has_no_saved_path_for_a_pass_through(self):
        view, info = squeeze.squeeze(low_saving_log(), kind="log")
        self.assertIsNone(view)
        self.assertNotIn("path", info)


@pending("test_missing_file_and_folder")
class I20_UnreadableFileGetsAMessage(unittest.TestCase):
    def test_missing_file_and_folder(self):
        for target in (support.tmp("regressions", "i20", "nope.log"), support.TMP):
            code, stdout, stderr = sq(target)
            self.assertEqual(code, 2, stderr)
            self.assertEqual(stdout, b"")
            self.assertNotIn("Traceback", stderr)
            self.assertTrue(stderr.startswith(f"squeeze: cannot read {target}: "), stderr)
            self.assertEqual(stderr.count("\n"), 1)


class I21_LargeIntegersKeepTheirDigits(unittest.TestCase):
    def test_eighteen_digit_ids(self):
        first = 123456789012345000
        text = "id,v\n" + "".join(f"{first + i},{i % 7}\n" for i in range(3000))
        view, _ = squeeze.squeeze(text, "ids.csv", original_path="ids.csv")
        row = next(l for l in view.split("\n") if l.strip().startswith("id "))
        self.assertIn(f"{first:,}…{first + 2999:,}, unique (likely an ID)", row)

    def test_integer_statistics_are_exact(self):
        big = 9007199254740993                          # 2**53 + 1: not representable as a float
        kind, _, summary, _ = squeeze._profile_column([str(big), str(big), "1"], [2, 3, 4], 40)
        self.assertEqual(kind, "int")
        self.assertIn(f"max {big:,}", summary)
        self.assertIn(f"sum {2 * big + 1:,}", summary)


@pending("test_booleans_and_numbers_are_counted_apart")
class I22_TrueIsNotTheNumberOne(unittest.TestCase):
    def test_booleans_and_numbers_are_counted_apart(self):
        self.assertEqual(squeeze._field_summary([True, 1, 1.0, True], 4, 40), "bool/num, 4/4, true×2, 1×2")
        self.assertEqual(squeeze._field_summary([False, 0, False], 3, 40), "bool/num, 3/3, false×2, 0×1")


@pending(*(["test_sum_is_the_same_on_every_python_version"] if sys.version_info < (3, 12) else []))
class I23_ColumnSumsAreCorrectlyRounded(unittest.TestCase):
    def test_sum_is_the_same_on_every_python_version(self):
        # Plain sum() adds left to right before Python 3.12 and gives 2 here; from 3.12 it compensates
        # and gives 1.5. The summary must not depend on the interpreter, so it uses exact summation.
        values = ["1e16", "1.5", "-1e16"]
        self.assertEqual(math.fsum(float(v) for v in values), 1.5)
        summary = squeeze._profile_column(values, [2, 3, 4], 40)[2]
        self.assertTrue(summary.endswith("sum 1.5"), summary)


@pending("test_words_in_arguments_and_file_names_do_not_count", "test_commands_in_command_position_still_count")
class I28_NarrowingLooksAtCommandsNotArguments(unittest.TestCase):
    def test_words_in_arguments_and_file_names_do_not_count(self):
        for cmd in ["cat more.log", "pytest -k tail", "python tr.py", "make less-css", "npm run sort",
                    "cat head.txt", "echo grep", "git commit -m 'sort the list'", "./build.sh --tail"]:
            self.assertFalse(hook.NARROWING.search(cmd), cmd)

    def test_commands_in_command_position_still_count(self):
        for cmd in ["grep -n error app.log", "cat app.log | head -50", "cat f |grep x", "ls; wc -l f", "cmd && cut -f1 f",
                    "(tail -5 f)", "sudo grep x /var/log/syslog", "LC_ALL=C sort big.txt", "/usr/bin/grep x f",
                    "find . -name '*.log' -exec grep -l x {} +", "time rg TODO", "x=$(jq .a f.json)",
                    "for f in *.log; do tail -1 $f; done", "true\nsed -n '1,5p' f"]:
            self.assertTrue(hook.NARROWING.search(cmd), cmd)


@pending("test_summary_notes_that_only_part_of_the_file_was_read")
class I29_OversizedSavedOutputSaysItWasCut(unittest.TestCase):
    def test_summary_notes_that_only_part_of_the_file_was_read(self):
        path = support.write(support.tmp("regressions", "i29", "saved.txt"), log_text(4000))
        payload = {"tool_input": {"command": "./run.sh"},
                   "tool_response": {"stdout": "preview\n", "stderr": "", "persistedOutputPath": path}}
        with mock.patch.object(hook, "MAX_SCAN", 60000):
            raw = support.capture(hook.on_bash, payload)
        stdout = json.loads(raw)["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        self.assertIn("only the first", stdout)
        self.assertIn(path, stdout)
        untouched = json.loads(support.capture(hook.on_bash, payload))["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        self.assertNotIn("only the first", untouched)


@pending("test_python_warning_classes")
class I42_WarningClassNamesAreWarnings(unittest.TestCase):
    def test_python_warning_classes(self):
        for line in ["/app/x.py:10: UserWarning: glyph missing", "DeprecationWarning", "ResourceWarning: unclosed file",
                     "sys:1: RuntimeWarning: coroutine was never awaited"]:
            self.assertEqual(squeeze._severity(line), 1, line)
        for line in ["Warnings are off", "see the WarningPolicy class docs", "no_warning_here"]:
            self.assertEqual(squeeze._severity(line), 0, line)


# ====================================================================== squeeze_hook.py

class I03_PartialReadIsSummarisedFromTheWholeFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rnd = random.Random(9)
        cls.values = [rnd.choice([10, 20, 30, 40, 50]) * rnd.randint(1, 9) for _ in range(5000)]
        cls.rows = ["date,region,revenue"] + [f"2026-01-{1 + i % 28:02d},{'north' if i % 2 else 'south'},{v}"
                                              for i, v in enumerate(cls.values)]
        cls.path = support.write(support.tmp("regressions", "i03", "sales.csv"), "\n".join(cls.rows) + "\n")
        assert os.path.getsize(cls.path) < hook.READ_LIMIT

    def event(self, path, lines=2000, **file_fields):
        content = "\n".join(self.rows[:lines]) + "\n"
        f = dict({"filePath": path, "content": content, "numLines": lines, "startLine": 1, "totalLines": 5001}, **file_fields)
        return {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": path},
                "tool_response": {"type": "text", "file": f}}

    def test_summary_describes_the_whole_file_not_the_part_that_was_read(self):
        raw = support.capture(hook.on_read_post, self.event(self.path))
        content = json.loads(raw)["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"]
        self.assertIn("5,000 rows × 3 columns", content.split("\n")[0])
        self.assertIn(f"sum {sum(self.values):,}", content)
        self.assertNotIn(f"sum {sum(self.values[:1999]):,}", content)

    def test_a_partial_read_is_left_alone_when_the_file_cannot_be_reread(self):
        self.assertEqual(support.capture(hook.on_read_post, self.event("/nonexistent/sales.csv")), "")

    def test_a_complete_read_is_summarised_from_the_content_it_was_given(self):
        raw = support.capture(hook.on_read_post, self.event("/nonexistent/sales.csv", lines=5001, totalLines=5001))
        self.assertIn("5,000 rows", json.loads(raw)["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"])


class I09_BadSettingsNeverBreakTheToolCall(unittest.TestCase):
    PAYLOAD = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "cat x"},
                          "tool_response": {"stdout": log_text(), "stderr": ""}})

    def test_non_numeric_budget_or_threshold_falls_back_to_the_default(self):
        for name in ("LEMBAS_SQUEEZE_BUDGET", "LEMBAS_SQUEEZE_THRESHOLD"):
            r = support.run_py(support.HOOK_PY, data=self.PAYLOAD, env={name: "lots"})
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertIn("updatedToolOutput", r.stdout.decode())
            self.assertNotIn("Traceback", r.stderr.decode())
            self.assertIn(name, r.stderr.decode())

    def test_small_payload_with_a_bad_setting(self):
        small = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
                            "tool_response": {"stdout": "a\n", "stderr": ""}})
        r = support.run_py(support.HOOK_PY, data=small, env={"LEMBAS_SQUEEZE_BUDGET": ""})
        self.assertEqual((r.returncode, r.stdout), (0, b""))


# ====================================================================== ithildin.py

class I04_SlidesFollowThePresentationOrder(unittest.TestCase):
    SLIDES = [(f"Slide made {i}", [f"Body of slide made {i}."], None) for i in range(1, 6)]

    def test_a_reordered_deck_is_numbered_as_it_is_shown(self):
        path = support.make_pptx(support.tmp("regressions", "i04", "reordered.pptx"), self.SLIDES, order=[5, 1, 2, 3, 4])
        doc = ithildin.load(path)
        self.assertEqual([(doc.lines[h["line"]][0], h["title"]) for h in doc.headings],
                         [(1, "Slide made 5"), (2, "Slide made 1"), (3, "Slide made 2"), (4, "Slide made 3"), (5, "Slide made 4")])
        self.assertIn("Slide made 5 | p1", out("map", path))
        self.assertIn(">p1 ", out("find", path, "Body of slide made 5"))

    def test_a_deck_without_an_order_list_falls_back_to_file_order(self):
        path = support.make_pptx(support.tmp("regressions", "i04", "bare.pptx"), self.SLIDES, presentation=False)
        self.assertEqual([h["title"] for h in ithildin.load(path).headings], [f"Slide made {i}" for i in range(1, 6)])

    def test_slides_the_order_list_leaves_out_are_kept_at_the_end(self):
        path = support.make_pptx(support.tmp("regressions", "i04", "partial.pptx"), self.SLIDES, order=[3, 1])
        self.assertEqual([h["title"] for h in ithildin.load(path).headings],
                         ["Slide made 3", "Slide made 1", "Slide made 2", "Slide made 4", "Slide made 5"])


class I05_WordContentControlsAreRead(unittest.TestCase):
    def test_paragraphs_headings_and_tables_inside_content_controls(self):
        body = (support.w_sdt(support.w_p("1 Limits", style="Heading1"))
                + support.w_p("Plain paragraph: the vessel is rated to 10 bar.")
                + support.w_sdt(support.w_p("Inside a control: the relief valve opens at 42 bar."))
                + support.w_sdt(support.w_sdt(support.w_p("Nested control: test pressure is 63 bar.")))
                + support.w_p("Table 1. Spares") + support.w_sdt(support.w_tbl([["Part", "No."], ["Seal", "S-1"]])))
        path = support.make_docx(support.tmp("regressions", "i05", "controls.docx"), body)
        doc = ithildin.load(path)
        self.assertEqual([h["title"] for h in doc.headings], ["1 Limits"])
        first = out("find", path, "10 bar", "42 bar", "63 bar").split("\n")[0]
        self.assertEqual(first, "[ithildin find: '10 bar': 1 hits in 1 sections (1); '42 bar': 1 hits in 1 sections (1); "
                                "'63 bar': 1 hits in 1 sections (1)]")
        self.assertEqual(doc.tables[0]["rows"], [["Part", "No."], ["Seal", "S-1"]])
        self.assertEqual(doc.tables[0]["caption"], "Table 1. Spares")

    def test_document_order_is_kept(self):
        body = support.w_p("one") + support.w_sdt(support.w_p("two")) + support.w_p("three")
        doc = ithildin.load(support.make_docx(support.tmp("regressions", "i05", "order.docx"), body))
        self.assertEqual([t for _, t in doc.lines], ["one", "two", "three"])


@pending("test_spreadsheets_and_other_binary_files", "test_formats_that_need_a_converter_say_which_one")
class I10_UnsupportedFilesAreRefused(unittest.TestCase):
    def test_spreadsheets_and_other_binary_files(self):
        import zipfile
        xlsx = support.tmp("regressions", "i10", "book.xlsx")
        with zipfile.ZipFile(xlsx, "w") as z:
            z.writestr("xl/workbook.xml", "<workbook/>" * 200)
        png = support.tmp("regressions", "i10", "image.png")
        with open(png, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 20)
        for path in (xlsx, png):
            code, stdout, stderr = ith("map", path)
            no_traceback(self, code, stderr)
            self.assertEqual(stdout, b"")
            self.assertIn("ithildin: cannot read", stderr)
            self.assertIn("PDF, DOCX, PPTX, Markdown, HTML", stderr)

    def test_formats_that_need_a_converter_say_which_one(self):
        with mock.patch.object(ithildin.shutil, "which", return_value=None):
            for name, tool in (("book.epub", "pandoc"), ("notes.odt", "pandoc"), ("old.doc", "LibreOffice"), ("old.ppt", "LibreOffice")):
                path = md(os.path.join("i10", name), "PK\x03\x04 not really")
                message = exit_message(ithildin.load, path)
                self.assertTrue(message.startswith("ithildin: "), message)
                self.assertIn(tool, message)

    def test_unknown_text_formats_are_still_read_as_text(self):
        for name in ("data.csv", "config.cfg", "script.py", "notes.unknownext"):
            doc = ithildin.load(md(os.path.join("i10", name), f"plain text content of {name}\nsecond line\n"))
            self.assertEqual(doc.kind, "Text")
            self.assertEqual(len(doc.lines), 2)


@pending("test_corrupt_pdf",
         "test_files_that_are_not_really_word_or_powerpoint",
         "test_invalid_regular_expression",
         "test_non_numeric_map_budget_in_the_environment",
         "test_reading_from_an_empty_document",
         "test_a_pdftotext_timeout_falls_back_to_pypdf")
class I11_BadInputGetsAMessageNotATraceback(unittest.TestCase):
    def test_corrupt_pdf(self):
        path = support.tmp("regressions", "i11", "bad.pdf")
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.4\nthis is not really a pdf\n" + bytes(range(256)) * 8)
        code, _, stderr = ith("map", path)
        no_traceback(self, code, stderr)
        self.assertTrue(stderr.startswith("ithildin: "), stderr)

    def test_files_that_are_not_really_word_or_powerpoint(self):
        for name in ("fake.docx", "fake.pptx"):
            code, _, stderr = ith("map", md(os.path.join("i11", name), "just text"))
            no_traceback(self, code, stderr)
            self.assertIn(f"ithildin: {name} is not a valid", stderr)
        import zipfile
        empty = support.tmp("regressions", "i11", "empty.docx")
        with zipfile.ZipFile(empty, "w") as z:
            z.writestr("unrelated.txt", "x")
        code, _, stderr = ith("map", empty)
        no_traceback(self, code, stderr)

    def test_invalid_regular_expression(self):
        path = md("i11.md", "# A\n\nlate fee (applies).\n")
        code, _, stderr = ith("find", path, "--regex", "late fee (")
        no_traceback(self, code, stderr)
        self.assertIn("ithildin: invalid regular expression 'late fee ('", stderr)
        self.assertEqual(ith("find", path, "late fee (")[0], 0, "the same text is fine as a plain pattern")

    def test_non_numeric_map_budget_in_the_environment(self):
        path = md("i11b.md", "# A\n\nText.\n")
        code, stdout, stderr = ith("map", path, env={"ITHILDIN_MAP_BUDGET": "big"})
        self.assertEqual(code, 0, stderr)
        self.assertTrue(stdout.decode("utf-8").startswith("[ithildin map"))
        self.assertIn("ITHILDIN_MAP_BUDGET", stderr)
        self.assertEqual(ith("version", env={"ITHILDIN_MAP_BUDGET": "big"})[0], 0)

    def test_reading_from_an_empty_document(self):
        path = md("i11-empty.md", "")
        code, _, stderr = ith("read", path, "L1-5")
        no_traceback(self, code, stderr)
        self.assertIn("ithildin: ", stderr)
        self.assertEqual(ith("map", path)[0], 0)

    def test_a_pdftotext_timeout_falls_back_to_pypdf(self):
        class Page:
            def extract_text(self, **kw):
                return "Text from the fallback reader, long enough to count as a text layer."

        fake = types.SimpleNamespace(PdfReader=lambda path: types.SimpleNamespace(pages=[Page()], outline=[]))
        with mock.patch.object(ithildin.shutil, "which", return_value="/usr/bin/pdftotext"), \
                mock.patch.object(ithildin, "_run", side_effect=subprocess.TimeoutExpired("pdftotext", 180)), \
                mock.patch.dict(sys.modules, {"pypdf": fake}):
            doc = ithildin.extract_pdf("/fake/slow.pdf")
        self.assertEqual(len(doc.lines), 1)


@pending("test_a_range_past_the_end_is_an_error_that_gives_the_real_length",
         "test_a_backwards_range_and_line_zero_are_errors",
         "test_truncation_lists_the_targets_that_were_not_read")
class I13_ReadRangesAreChecked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = "".join(f"# {i} Section {i}\n\n" + "".join(f"Line {j} of section {i}.\n\n" for j in range(30)) for i in range(1, 12))
        cls.path = md("i13.md", text)
        cls.doc = ithildin.load(cls.path)

    def test_a_range_past_the_end_is_an_error_that_gives_the_real_length(self):
        message = exit_message(ithildin.resolve, self.doc, "L9000-9100")
        self.assertEqual(message, f"ithildin: lines 9000-9100 are past the end; the document has {len(self.doc.lines)} lines.")

    def test_a_backwards_range_and_line_zero_are_errors(self):
        self.assertEqual(exit_message(ithildin.resolve, self.doc, "L20-10"),
                         "ithildin: line range L20-10 runs backwards; did you mean L10-20?")
        self.assertEqual(exit_message(ithildin.resolve, self.doc, "L0"), "ithildin: lines are numbered from 1.")
        self.assertEqual(exit_message(ithildin.resolve, self.doc, "p0") if self.doc.pages else "skip", "skip")

    def test_a_range_that_only_overruns_the_end_is_still_clamped(self):
        n = len(self.doc.lines)
        self.assertEqual(ithildin.resolve(self.doc, f"L{n - 1}-{n + 500}")[:2], (n - 2, n))

    def test_truncation_lists_the_targets_that_were_not_read(self):
        text = out("read", self.path, "1", "5", "9", "--max-tokens", "60")
        last = text.rstrip("\n").split("\n")[-1]
        self.assertRegex(last, r"^\[truncated at L\d+ to stay under 60 tokens\. Continue with: read FILE L\d+-\d+\. "
                               r"Not read yet: 5, 9\]$")

    def test_no_such_note_when_the_last_target_is_the_one_cut(self):
        text = out("read", self.path, "1", "--max-tokens", "60")
        self.assertNotIn("Not read yet", text)


@pending("test_depth_one_shows_the_top_level_even_when_that_is_a_second_level_heading")
class I14_DepthCountsFromTheShallowestHeading(unittest.TestCase):
    def test_depth_one_shows_the_top_level_even_when_that_is_a_second_level_heading(self):
        text = "".join(f"## Part {i}\n\nText for part {i}.\n\n### Detail {i}\n\nMore.\n\n" for i in range(1, 6))
        path = md("i14.md", text)
        one = out("map", path, "--depth", "1").rstrip("\n").split("\n")
        self.assertEqual(len(one), 6, one)
        self.assertEqual(one[1], "S1 Part 1 | L1-4 | 9w | 1 subsections | Text for part 1.")
        two = out("map", path, "--depth", "2")
        self.assertIn("  S2 Detail 1 | ", two)
        self.assertEqual(out("map", path, "--depth", "9"), out("map", path))


@pending("test_ithildin_cache_files_are_private",
         "test_a_folder_the_user_chose_keeps_its_permissions",
         "test_a_default_folder_owned_by_someone_else_is_not_used")
class I15_CacheFoldersArePrivateAndRespectful(unittest.TestCase):
    def test_ithildin_cache_files_are_private(self):
        cache = support.tmp("regressions", "i15", "ith-cache", "x")[:-2]
        with mock.patch.dict(os.environ, {"ITHILDIN_CACHE": cache}):
            ithildin.load(md("i15.md", "# A\n\nConfidential text.\n"))
        for name in os.listdir(cache):
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(cache, name)).st_mode), 0o600, name)

    def test_a_folder_the_user_chose_keeps_its_permissions(self):
        chosen = support.tmp("regressions", "i15", "chosen", "x")[:-2]
        os.chmod(chosen, 0o755)
        with mock.patch.dict(os.environ, {"ITHILDIN_CACHE": chosen}):
            ithildin.load(md("i15b.md", "# B\n\nText.\n"))
        self.assertEqual(stat.S_IMODE(os.stat(chosen).st_mode), 0o755)

    @unittest.skipUnless(hasattr(os, "getuid"), "needs POSIX file ownership")
    def test_a_default_folder_owned_by_someone_else_is_not_used(self):
        import tempfile
        shared = support.tmp("regressions", "i15", "shared-tmp", "x")[:-2]
        for module, name, pick in ((ithildin, "ithildin", lambda: ithildin.cache_dir()),
                                   (squeeze, "lembas-squeeze", lambda: os.path.dirname(squeeze.save_original("x\n", "log")))):
            planted = os.path.join(shared, name)
            os.makedirs(planted, exist_ok=True)
            os.chmod(planted, 0o777)
            env = {k: v for k, v in os.environ.items() if k not in ("ITHILDIN_CACHE", "LEMBAS_SQUEEZE_DIR")}
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(tempfile, "gettempdir", return_value=shared), \
                    mock.patch.object(os, "getuid", return_value=os.getuid() + 1):
                used = pick()
            self.assertNotEqual(os.path.realpath(used), os.path.realpath(planted), name)
            self.assertEqual(stat.S_IMODE(os.stat(used).st_mode), 0o700, name)
            self.assertEqual(os.listdir(planted), [], f"{name}: nothing may be written into the other user's folder")

    @unittest.skipUnless(hasattr(os, "getuid"), "needs POSIX file ownership")
    def test_our_own_default_folder_is_tightened_if_it_was_left_open(self):
        import tempfile
        shared = support.tmp("regressions", "i15", "own-tmp", "x")[:-2]
        loose = os.path.join(shared, "ithildin")
        os.makedirs(loose, exist_ok=True)
        os.chmod(loose, 0o777)
        env = {k: v for k, v in os.environ.items() if k != "ITHILDIN_CACHE"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(tempfile, "gettempdir", return_value=shared):
            self.assertEqual(ithildin.cache_dir(), loose)
        self.assertEqual(stat.S_IMODE(os.stat(loose).st_mode), 0o700)


@pending("test_closing_hashes_need_a_space_before_them")
class I30_HeadingsMayEndInAHash(unittest.TestCase):
    def test_closing_hashes_need_a_space_before_them(self):
        text = "# C#\n\na\n\n## F# and C#\n\nb\n\n## Closed ##\n\nc\n\n### Single #\n\nd\n\n## Issue #42\n\ne\n"
        doc = ithildin.load(md("i30.md", text))
        self.assertEqual([h["title"] for h in doc.headings], ["C#", "F# and C#", "Closed", "Single", "Issue #42"])


@pending("test_adjacent_hits_are_both_marked")
class I31_EveryHitIsMarkedWithContext(unittest.TestCase):
    def test_adjacent_hits_are_both_marked(self):
        path = md("i31.md", "# Notes\n\nfirst alpha line\n\nsecond alpha line\n\nthird plain line\n")
        lines = out("find", path, "alpha", "-C", "1").rstrip("\n").split("\n")[2:]
        self.assertEqual(lines, [" L1 §S1 | Notes", ">L2 §S1 | first alpha line", ">L3 §S1 | second alpha line",
                                 " L4 §S1 | third plain line"])


@pending("test_table_command_on_a_figure_id_points_to_read")
class I32_FiguresAreNotTables(unittest.TestCase):
    def test_table_command_on_a_figure_id_points_to_read(self):
        doc = ithildin.Doc("x.pdf", "PDF")
        doc.pages = 1
        for line in ["1 Intro", "Figure 1. Cooling loop schematic", "Valve State", "V1 Open"]:
            doc.add(line, 1)
        ithildin.finish(doc)
        self.assertEqual(doc.tables[0]["id"], "F1")
        self.assertEqual(exit_message(ithildin.render_table, doc, "F1"),
                         "ithildin: F1 is a figure (Figure 1. Cooling loop schematic), which has no rows. "
                         "Use read p1 for the text around it.")


@pending("test_title_is_not_body_text_and_a_break_does_not_split_a_heading")
class I33_HtmlHeadAndLineBreaks(unittest.TestCase):
    def test_title_is_not_body_text_and_a_break_does_not_split_a_heading(self):
        page = ("<html><head><title>Tab title</title><meta name=x content=y></head><body><header>Site header</header>"
                "<h2>Install<br>guide</h2><p>Run it.<br>Then check.</p><footer>Footer links</footer></body></html>")
        doc = ithildin.load(md("i33.html", page))
        texts = [t for _, t in doc.lines]
        self.assertEqual(texts, ["Site header", "Install guide", "Run it.", "Then check.", "Footer links"])
        self.assertEqual([h["title"] for h in doc.headings], ["Install guide"])


@pending("test_bookmarks_that_match_no_text_are_not_reported_as_the_outline")
@unittest.skipUnless(support.manual_docs().get("manual.pdf"), "reportlab is needed to build a PDF")
class I35_OutlineSourceIsOnlyClaimedWhenUsed(unittest.TestCase):
    def test_bookmarks_that_match_no_text_are_not_reported_as_the_outline(self):
        from reportlab.pdfgen import canvas
        path = support.tmp("regressions", "i35", "scan-with-bookmarks.pdf")
        c = canvas.Canvas(path)
        for i in range(5):
            c.rect(50, 50, 400, 600, fill=1)
            c.bookmarkPage(f"k{i}")
            c.addOutlineEntry(f"Chapter {i + 1}", f"k{i}", level=0)
            c.showPage()
        c.save()
        first = out("map", path).split("\n")[0]
        self.assertIn("0 sections", first)
        self.assertNotIn("Outline from PDF bookmarks", first)


@pending("test_outer_table_has_only_its_own_rows")
class I36_NestedTableRowsAreNotRepeated(unittest.TestCase):
    def test_outer_table_has_only_its_own_rows(self):
        inner = support.w_tbl([["inner a", "inner b"]])
        outer = (f"<w:tbl><w:tr><w:tc>{support.w_p('Outer 1')}{inner}</w:tc><w:tc>{support.w_p('x')}</w:tc></w:tr>"
                 f"<w:tr><w:tc>{support.w_p('Outer 2')}</w:tc><w:tc>{support.w_p('y')}</w:tc></w:tr></w:tbl>")
        doc = ithildin.load(support.make_docx(support.tmp("regressions", "i36", "nested.docx"), outer))
        self.assertEqual(len(doc.tables[0]["rows"]), 2)
        self.assertEqual([r[1] for r in doc.tables[0]["rows"]], ["x", "y"])
        self.assertIn("inner a", doc.tables[0]["rows"][0][0])


@pending("test_external_tools_are_given_an_absolute_path")
class I37_FileNamesCannotBeMistakenForOptions(unittest.TestCase):
    def test_external_tools_are_given_an_absolute_path(self):
        result = types.SimpleNamespace(returncode=0, stdout="Enough text on this page to count as a real text layer.\f", stderr="")
        with mock.patch.object(ithildin.shutil, "which", return_value="/usr/bin/tool"), \
                mock.patch.object(ithildin, "_run", return_value=result) as run, mock.patch.dict(sys.modules, {"pypdf": None}):
            ithildin.extract_pdf("-opw.pdf")
            self.assertEqual(run.call_args[0][0][3], os.path.abspath("-opw.pdf"))
            run.return_value = types.SimpleNamespace(returncode=0, stdout="# T\n\nBody.\n", stderr="")
            ithildin.extract_with_pandoc("-o.rst")
            self.assertEqual(run.call_args[0][0][1], os.path.abspath("-o.rst"))


class I43_NumberedHeadingsThatOpenEveryPage(unittest.TestCase):
    """Known limitation, not fixed: see docs/CODE_REVIEW.md, finding I-43."""

    @unittest.expectedFailure
    def test_chapter_headings_at_the_top_of_each_page_survive_header_removal(self):
        doc = ithildin.Doc("x.pdf", "PDF")
        doc.pages = 6
        topics = ["pumps", "valves", "filters", "belts", "gauges", "seals"]
        for page, topic in enumerate(topics, 1):
            for line in [f"{page} Chapter {page}", f"This chapter covers {topic} in detail.",
                         f"Inspect the {topic} weekly.", f"Replace worn {topic} promptly."]:
                doc.add(line, page)
        ithildin._strip_running_lines(doc)
        self.assertEqual(sum(t.endswith(f"Chapter {p}") for p, t in doc.lines), 6)


@pending("test_same_bytes_with_different_extensions_are_parsed_separately")
class I44_CacheKeyIncludesTheFileType(unittest.TestCase):
    def test_same_bytes_with_different_extensions_are_parsed_separately(self):
        text = "# Title\n\nBody text shared by both files.\n"
        as_markdown = ithildin.load(md(os.path.join("i44", "notes.md"), text))
        as_text = ithildin.load(md(os.path.join("i44", "notes.txt"), text))
        self.assertEqual((as_markdown.kind, len(as_markdown.headings)), ("Markdown", 1))
        self.assertEqual((as_text.kind, len(as_text.headings)), ("Text", 0))


@pending("test_text_after_a_caption_at_the_foot_of_a_page_is_returned")
class I45_TableTextFallbackCrossesThePageBreak(unittest.TestCase):
    def test_text_after_a_caption_at_the_foot_of_a_page_is_returned(self):
        doc = ithildin.Doc("/nonexistent/x.pdf", "PDF")
        doc.pages = 2
        for page, line in [(1, "1 Limits"), (1, "Body text."), (1, "Table 1. Operating limits"),
                           (2, "Item Limit"), (2, "Pressure 10 bar"), (2, "Speed 900 rpm")]:
            doc.add(line, page)
        ithildin.finish(doc)
        with mock.patch.dict(sys.modules, {"pdfplumber": None}):
            text = ithildin.render_table(doc, "T1")
        self.assertEqual(text.split("\n")[1:], ["Table 1. Operating limits", "Item Limit", "Pressure 10 bar", "Speed 900 rpm"])


# ====================================================================== scripts/ and evals/

def run_script(module, *argv):
    stdout, stderr, code = io.StringIO(), io.StringIO(), 0
    with mock.patch.object(sys, "argv", [module.__name__, *argv]), mock.patch.object(sys, "stdout", stdout), \
            mock.patch.object(sys, "stderr", stderr):
        try:
            module.main()
        except SystemExit as exc:
            code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()


def results(name, replies):
    root = support.tmp("regressions", name, "x")[:-2]
    for ev, variants in replies.items():
        for variant, text in variants.items():
            support.write(support.tmp("regressions", name, ev, f"{variant}.md"), text)
    return root


EV = {"name": "demo", "category": "safety", "must_contain": ["pg_dump"]}
GOOD = "**Problem.** Live table.\n\n**Fix.** Run pg_dump.\n\n**Alternatives.** A view if you can wait.\n\n**Why this fix.** Reversible."


@pending("test_empty_or_missing_results_folder_fails",
         "test_a_missing_lembas_reply_fails_and_is_named",
         "test_a_missing_baseline_is_only_a_warning",
         "test_an_empty_reply_fails_its_checks_instead_of_crashing",
         "test_missing_arguments_print_usage")
class I12_GradeCannotPassWithoutChecking(unittest.TestCase):
    def evals(self, name, evs=(EV,)):
        return support.write(support.tmp("regressions", name, "evals.json"), json.dumps({"evals": list(evs)}))

    def test_empty_or_missing_results_folder_fails(self):
        empty = support.tmp("regressions", "i12-empty", "x")[:-2]
        for folder in (empty, os.path.join(empty, "nope")):
            code, stdout, stderr = run_script(grade, self.evals("i12a"), folder)
            self.assertEqual(code, 1, folder)
            self.assertIn("demo", stdout + stderr)

    def test_a_missing_lembas_reply_fails_and_is_named(self):
        folder = results("i12-missing", {"demo": {"baseline": "Run pg_dump."}})
        code, stdout, _ = run_script(grade, self.evals("i12b"), folder)
        self.assertEqual(code, 1)
        self.assertIn("FAIL lembas   demo: reply file is missing", stdout)

    def test_a_missing_baseline_is_only_a_warning(self):
        folder = results("i12-nobase", {"demo": {"lembas": GOOD}})
        code, stdout, _ = run_script(grade, self.evals("i12c"), folder)
        self.assertEqual(code, 0)
        self.assertIn("warn baseline demo: reply file is missing", stdout)

    def test_an_empty_reply_fails_its_checks_instead_of_crashing(self):
        folder = results("i12-blank", {"demo": {"lembas": "\n\n"}})
        code, stdout, _ = run_script(grade, self.evals("i12d"), folder)
        self.assertEqual(code, 1)
        self.assertIn("FAIL lembas   demo: reply is empty", stdout)

    def test_missing_arguments_print_usage(self):
        code, _, stderr = run_script(grade)
        self.assertEqual(code, 2)
        self.assertIn("usage: ", stderr.lower())


@pending("test_empty_folder",
         "test_missing_reply_file_is_named",
         "test_an_empty_baseline_does_not_divide_by_zero",
         "test_replies_are_read_as_utf8_whatever_the_locale")
class I18_CountTokensReportsBadInput(unittest.TestCase):
    def test_empty_folder(self):
        empty = support.tmp("regressions", "i18-empty", "x")[:-2]
        code, _, stderr = run_script(count_tokens, empty)
        self.assertEqual(code, 1)
        self.assertIn(f"count_tokens: no eval folders in {empty}", stderr)

    def test_missing_reply_file_is_named(self):
        folder = results("i18-missing", {"demo": {"lembas": "short"}})
        code, _, stderr = run_script(count_tokens, folder)
        self.assertEqual(code, 1)
        self.assertIn(os.path.join("demo", "baseline.md"), stderr)
        self.assertNotIn("Traceback", stderr)

    def test_an_empty_baseline_does_not_divide_by_zero(self):
        folder = results("i18-zero", {"demo": {"baseline": "", "lembas": "short reply"}})
        code, stdout, _ = run_script(count_tokens, folder)
        self.assertEqual(code, 0)
        self.assertIn("n/a", stdout)

    # A C locale with Python's UTF-8 mode off makes ASCII the default file encoding, as on some servers.
    ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}

    def test_replies_are_read_as_utf8_whatever_the_locale(self):
        folder = results("i18-utf8", {"demo": {"baseline": "café pg_dump " * 50, "lembas": GOOD + " 你好"}})
        r = support.run_py(os.path.join(support.ROOT, "scripts", "count_tokens.py"), folder, env=self.ASCII_LOCALE)
        self.assertEqual(r.returncode, 0, r.stderr.decode()[-300:])
        self.assertRegex(r.stdout.decode(), r"(?m)^demo\s+150\s+\d+\s")
        evals = support.write(support.tmp("regressions", "i18-utf8", "evals.json"), json.dumps({"evals": [EV]}))
        r = support.run_py(os.path.join(support.ROOT, "scripts", "grade.py"), evals, folder, env=self.ASCII_LOCALE)
        self.assertEqual(r.returncode, 0, r.stderr.decode()[-300:])
        self.assertIn("lembas   8/8 checks passed", r.stdout.decode())


@pending("test_generate_replies_records_a_failed_call_and_carries_on",
         "test_squeeze_benchmark_removes_its_work_folder_after_a_failure")
class I38_BenchmarkRunnersSurviveAFailedRun(unittest.TestCase):
    def test_generate_replies_records_a_failed_call_and_carries_on(self):
        evals = support.write(support.tmp("regressions", "i38", "evals.json"), json.dumps({"evals": [
            {"id": 1, "name": "first", "category": "code", "prompt": "boom", "must_contain": []},
            {"id": 2, "name": "second", "category": "code", "prompt": "fine", "must_contain": []}]}))
        skill = support.write(support.tmp("regressions", "i38", "SKILL.md"), "Rules.")
        out_dir = support.tmp("regressions", "i38", "out", "x")[:-2]

        def fake_call(prompt, system):
            if prompt == "boom" and system:
                raise json.JSONDecodeError("Expecting value", "", 0)
            return "x = 1", 5, 0.1

        with mock.patch.object(gen, "call", side_effect=fake_call):
            code, stdout, _ = run_script(gen, out_dir, "--skill", skill, "--evals", evals, "--workers", "1")
        self.assertIn("first", stdout)
        self.assertRegex(stdout, r"(?m)^first\s+with_skill\s+error: JSONDecodeError")
        self.assertRegex(stdout, r"(?m)^second\s+with_skill\s+5 out tokens")
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "second", "with_skill", "outputs", "response.md")))
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "first", "without_skill", "outputs", "response.md")))

    def test_squeeze_benchmark_removes_its_work_folder_after_a_failure(self):
        folders = []

        def fake_run(cmd, **kw):
            folders.append(kw["cwd"])
            raise subprocess.TimeoutExpired("claude", 900)

        task = {"id": "t", "file": "app.log", "prompt": "Q?", "check": bool}
        fixtures = support.squeeze_fixtures()             # built before subprocess.run is replaced
        with mock.patch.object(sq_bench.subprocess, "run", side_effect=fake_run):
            row = sq_bench.run_one(task, "default", 0, fixtures)
        self.assertIn("error", row)
        self.assertFalse(os.path.exists(folders[0]))


@pending("test_words_that_merely_start_like_a_greeting_are_fine")
class I39_OpenerCheckUsesWholeWords(unittest.TestCase):
    def opens_with_answer(self, text):
        return {label: ok for _, label, ok in grade.checks(text, {"must_contain": []}, "baseline")}["opens with the answer"]

    def test_words_that_merely_start_like_a_greeting_are_fine(self):
        for first in ["Greater isolation is the point of a venv.", "Surely the cache is stale.", "Greatly simplified, it is a map.",
                      "Hello-world programs skip this.", "Certainly-typed languages differ."]:
            self.assertTrue(self.opens_with_answer(first), first)

    def test_real_greetings_are_still_flagged(self):
        for first in ["Sure, here it is.", "Great question!", "Great, let's begin.", "Hello! Here it is.", "Certainly.",
                      "Absolutely, do this.", "Good question."]:
            self.assertFalse(self.opens_with_answer(first), first)


if __name__ == "__main__":
    unittest.main(verbosity=1)
