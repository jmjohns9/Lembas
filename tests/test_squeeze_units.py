#!/usr/bin/env python3
"""Unit tests for every public function in squeeze.py. Run: python3 tests/test_squeeze_units.py

tests/test_squeeze.py checks whole summaries of large generated files. These tests check each
function directly, on small inputs, including edge cases and error paths.
"""
import json
import os
import random
import stat
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import squeeze  # noqa: E402


def ts(i):
    return f"2026-01-01 00:{i // 60 % 60:02d}:{i % 60:02d}"


class EstTokens(unittest.TestCase):
    def test_boundaries(self):
        for text, want in [("", 0), ("a", 1), ("ab", 1), ("abc", 1), ("abcd", 2), ("x" * 3000, 1000)]:
            self.assertEqual(squeeze.est_tokens(text), want, repr(text[:8]))

    def test_never_decreases_as_text_grows(self):
        sizes = [squeeze.est_tokens("x" * n) for n in range(40)]
        self.assertEqual(sizes, sorted(sizes))


class Clean(unittest.TestCase):
    def test_plain_text_is_returned_as_is(self):
        text = "line one\nline two\n"
        self.assertEqual(squeeze.clean(text), text)

    def test_colour_codes_are_removed(self):
        self.assertEqual(squeeze.clean("\x1b[1;31mERROR\x1b[0m boom"), "ERROR boom")

    def test_terminal_title_sequences_are_removed(self):
        self.assertEqual(squeeze.clean("\x1b]0;my title\x07text"), "text")
        self.assertEqual(squeeze.clean("\x1b]8;;http://x\x1b\\link"), "link")

    def test_progress_bar_redraws_keep_only_the_final_state(self):
        self.assertEqual(squeeze.clean("10%\r50%\r100%\nnext"), "100%\nnext")

    def test_windows_line_endings_become_unix_ones(self):
        self.assertEqual(squeeze.clean("a\r\nb\r\n"), "a\nb\n")

    def test_unicode_survives(self):
        text = "café 你好 \U0001F600\n"
        self.assertEqual(squeeze.clean(text), text)

    def test_empty(self):
        self.assertEqual(squeeze.clean(""), "")


class Clip(unittest.TestCase):
    def test_short_and_exact_length_lines_are_unchanged(self):
        self.assertEqual(squeeze.clip("abc"), "abc")
        self.assertEqual(squeeze.clip("x" * squeeze.MAX_LINE), "x" * squeeze.MAX_LINE)

    def test_long_line_is_cut_and_says_how_much_was_removed(self):
        self.assertEqual(squeeze.clip("x" * 301), "x" * 300 + "…[+1 chars]")
        self.assertEqual(squeeze.clip("abcdef", 2), "ab…[+4 chars]")


class Detect(unittest.TestCase):
    def test_file_extension_decides_first(self):
        cases = {"a.json": "json", "a.JSON": "json", "a.jsonl": "jsonl", "a.ndjson": "jsonl", "a.csv": "csv",
                 "a.tsv": "csv", "a.py": "code", "a.md": "code", "dir/b.yaml": "code"}
        for name, want in cases.items():
            self.assertEqual(squeeze.detect("anything at all", name), want, name)

    def test_json_found_by_parsing_is_handed_back(self):
        parsed = {}
        self.assertEqual(squeeze.detect('  [{"a": 1}]', None, parsed), "json")
        self.assertEqual(parsed["json"], [{"a": 1}])
        parsed = {}
        squeeze.detect('{"a": 1}', "x.json", parsed)        # known by name: nothing is parsed
        self.assertEqual(parsed, {})

    def test_json_documents(self):
        self.assertEqual(squeeze.detect('{"a": 1}'), "json")
        self.assertEqual(squeeze.detect("  \n[1, 2, 3]"), "json")

    def test_json_lines(self):
        text = "\n".join(json.dumps({"i": i}) for i in range(10))
        self.assertEqual(squeeze.detect(text), "jsonl")

    def test_diff(self):
        self.assertEqual(squeeze.detect("diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b\n"), "diff")

    def test_delimited_tables(self):
        self.assertEqual(squeeze.detect("a,b,c\n" + "1,2,3\n" * 10), "csv")
        self.assertEqual(squeeze.detect("a\tb\n" + "1\t2\n" * 10), "csv")

    def test_timestamped_lines_are_a_log_even_when_they_contain_commas(self):
        text = "\n".join(f"{ts(i)},123 INFO a=1, b=2, c=3" for i in range(30))
        self.assertEqual(squeeze.detect(text), "log")

    def test_source_code(self):
        self.assertEqual(squeeze.detect("def f(x):\n    return x\n\n" * 40), "code")

    def test_prose(self):
        rnd = random.Random(4)
        words = "river stone bridge lantern harbour valley meadow orchard".split()
        text = "\n".join(" ".join(rnd.choice(words) for _ in range(9)) + "." for _ in range(30))
        self.assertEqual(squeeze.detect(text), "text")

    def test_empty_and_whitespace_only(self):
        self.assertEqual(squeeze.detect(""), "text")
        self.assertEqual(squeeze.detect(" \n\t\n  "), "text")

    def test_lines_sharing_a_first_word_are_a_log(self):
        text = "\n".join(f"worker handled job number{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(60))
        self.assertEqual(squeeze.detect(text), "log")

    def test_many_lines_in_few_patterns_are_a_log(self):
        kinds = ["connected to host {}", "sent {} bytes", "closed after {} ms", "opened channel {}"]
        text = "\n".join(kinds[i % 4].format(i) for i in range(120))
        self.assertEqual(squeeze.detect(text), "log")


class Template(unittest.TestCase):
    def test_variable_tokens_become_placeholders(self):
        self.assertEqual(squeeze.template("GET /api/cart 200 35ms rid=abc123"), "GET /api/cart <*> rid=<*>")

    def test_known_shapes_get_named_placeholders(self):
        self.assertEqual(squeeze.template("2026-10-14 08:00:00,123 INFO started"), "<ts> INFO started")
        self.assertEqual(squeeze.template("job 3f2b8c1e-1111-2222-3333-444455556666 done"), "job <id> done")
        self.assertEqual(squeeze.template("fetch https://example.com/a?b=1 ok"), "fetch <url> ok")
        self.assertEqual(squeeze.template("peer 10.0.4.17:6379 up"), "peer <ip> up")

    def test_same_pattern_for_lines_that_differ_only_in_values(self):
        a = squeeze.template(f"{ts(1)} DEBUG cache hit key=user:17 ttl=60s")
        b = squeeze.template(f"{ts(999)} DEBUG cache hit key=user:99812 ttl=412s")
        self.assertEqual(a, b)

    def test_long_lines_are_capped(self):
        self.assertLessEqual(len(squeeze.template("word " * 100)), 160)

    def test_empty(self):
        self.assertEqual(squeeze.template(""), "")


class Severity(unittest.TestCase):
    def test_errors(self):
        for line in ["ERROR boom", "fatal: not a git repository", "TypeError: x is not a function",
                     "java.lang.IllegalStateException", "connection refused", "Segmentation fault",
                     "E   assert 1 == 2", "process killed", "Out of memory", "permission denied",
                     '"POST /pay HTTP/1.1" 503 12', "panic: runtime error"]:
            self.assertEqual(squeeze._severity(line), 2, line)

    def test_warnings(self):
        for line in ["WARN slow query", "warning: unused variable", "retrying in 5s",
                     "this API is deprecated", '"GET /missing HTTP/1.1" 404 12']:
            self.assertEqual(squeeze._severity(line), 1, line)

    def test_ordinary_lines(self):
        for line in ["INFO all good", "", "GET /health 200", "0 errors", "errors=0", "failed: 0",
                     "completed without errors", "no failures", "/var/log/error.log rotated",
                     "loaded module error_handler.py", "user@errors.example.com signed in"]:
            self.assertEqual(squeeze._severity(line), 0, line)

    def test_error_key_ignores_numbers_and_timestamps(self):
        a = squeeze._error_key(f"{ts(5)} ERROR job 123 failed after 4 retries")
        b = squeeze._error_key(f"{ts(77)} ERROR job 98765 failed after 1 retries")
        self.assertEqual(a, b)
        self.assertEqual(a, "<ts> ERROR job <n> failed after <n> retries")


class SqueezeLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lines = [f"{ts(i)} INFO request {i} ok" for i in range(3000)]
        lines[1000:1000] = [f"{ts(1000)} INFO loading plugin zeta",
                            f"{ts(1000)} INFO plugin zeta ready",
                            f"{ts(1000)} ERROR handler crashed",
                            "Traceback (most recent call last):",
                            '  File "/app/x.py", line 7, in run',
                            "    do()",
                            "ValueError: bad value 42"]
        for k, at in enumerate((1500, 1600, 1700)):
            lines.insert(at, f"{ts(at)} ERROR cache refused connection to 10.0.0.5:{6379 + k}")
        for at in (2000, 2100):
            lines.insert(at, f"{ts(at)} WARN slow query {at}ms")
        cls.lines = lines
        cls.body, cls.facts = squeeze.squeeze_log("\n".join(lines) + "\n", 1500)

    def number_of(self, needle):
        return next(i for i, l in enumerate(self.lines) if needle in l) + 1

    def test_facts_count_lines_errors_and_warnings(self):
        self.assertEqual(self.facts, "3,012 lines, 4 error lines (2 distinct), 2 warnings")

    def test_error_and_whole_stack_trace_are_kept_with_original_line_numbers(self):
        first = self.number_of("handler crashed")
        for offset, text in enumerate(["ERROR handler crashed", "Traceback (most recent call last):",
                                       'File "/app/x.py", line 7, in run', "do()", "ValueError: bad value 42"]):
            self.assertRegex(self.body, rf"(?m)^L{first + offset} .*{text.replace('(', '.').replace(')', '.')}")

    def test_unusual_lines_just_before_the_first_error_are_kept_as_context(self):
        self.assertIn(f"L{self.number_of('loading plugin zeta')} ", self.body)
        self.assertIn("plugin zeta ready", self.body)

    def test_repeated_error_is_shown_once_with_a_count(self):
        self.assertEqual(self.body.count("cache refused connection"), 1)
        last = len(self.lines) - self.lines[::-1].index(next(l for l in reversed(self.lines) if "cache refused" in l))
        self.assertIn(f"[this error repeats 3× in total, last at L{last}]", self.body)

    def test_repeated_warning_is_counted(self):
        self.assertIn("[this warning repeats 2× in total", self.body)

    def test_first_and_last_lines_are_shown(self):
        self.assertIn(f"L1 {self.lines[0]}", self.body)
        self.assertIn(f"L{len(self.lines)} {self.lines[-1]}", self.body)

    def test_routine_lines_are_collapsed_into_patterns_with_counts(self):
        self.assertIn("lines collapsed", self.body)
        self.assertRegex(self.body, r"Collapsed lines: [\d,]+ lines in \d+ patterns")
        self.assertRegex(self.body, r"(?m)^  \d[\d,]*× L\d+ .*INFO request \d+ ok")

    def test_a_trailing_newline_does_not_add_a_line(self):
        _, facts = squeeze.squeeze_log("a\nb\nc\n", 100)
        self.assertTrue(facts.startswith("3 lines"), facts)
        _, facts = squeeze.squeeze_log("a\nb\nc", 100)
        self.assertTrue(facts.startswith("3 lines"), facts)

    def test_very_long_stack_trace_is_cut_in_the_middle_and_says_so(self):
        lines = [f"{ts(i)} INFO tick {i}" for i in range(500)]
        lines[250:250] = ["ERROR deep recursion"] + [f"    at frame{i} (file.js:{i})" for i in range(50)]
        body, _ = squeeze.squeeze_log("\n".join(lines), 1500)
        self.assertRegex(body, r"…\[\d+ trace lines omitted\]")
        self.assertIn("at frame0 ", body)
        self.assertIn("at frame49 ", body)

    def test_too_many_distinct_warnings_are_counted_not_dropped(self):
        names = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet",
                 "kilo", "lima", "mike", "november", "oscar", "papa", "quebec", "romeo", "sierra", "tango"]
        lines = [f"{ts(i)} INFO tick {i}" for i in range(400)]
        for i, name in enumerate(names):
            lines.insert(10 + i * 15, f"WARN disk {name} nearly full")
        body, facts = squeeze.squeeze_log("\n".join(lines), 1500)
        shown = sum(f"disk {n} nearly" in body for n in names)
        self.assertIn("20 warnings", facts)
        self.assertLess(shown, len(names))
        self.assertIn(f"[{len(names) - shown} more distinct warnings not shown]", body)

    def test_very_long_lines_are_clipped(self):
        body, _ = squeeze.squeeze_log("ERROR " + "x" * 1000 + "\nok\n", 1500)
        self.assertIn("…[+", body)

    def test_empty_and_blank_input(self):
        body, facts = squeeze.squeeze_log("", 100)
        self.assertEqual(facts, "0 lines, 0 error lines (0 distinct), 0 warnings")
        self.assertEqual(body, "")
        _, facts = squeeze.squeeze_log("\n\n\n", 100)
        self.assertTrue(facts.startswith("3 lines, 0 error lines"), facts)


class JsonHelpers(unittest.TestCase):
    def test_scalar(self):
        for v in (None, "s", 1, 1.5, True):
            self.assertTrue(squeeze._scalar(v))
        for v in ([], {}, [1]):
            self.assertFalse(squeeze._scalar(v))

    def test_fmt(self):
        self.assertEqual(squeeze._fmt("abc", 10), '"abc"')
        self.assertEqual(squeeze._fmt("x" * 50, 10), '"xxxxxxxxxx"…(+40 chars)')
        self.assertEqual(squeeze._fmt(5, 10), "5")
        self.assertEqual(squeeze._fmt(None, 10), "null")
        self.assertEqual(squeeze._fmt(True, 10), "true")
        self.assertEqual(squeeze._fmt("café", 10), '"café"')

    def test_flatten_goes_two_levels_deep(self):
        flat = squeeze._flatten({"a": {"b": {"c": {"d": 1}}}, "x": 1})
        self.assertEqual(flat, {"a.b.c": {"d": 1}, "x": 1})
        self.assertEqual(squeeze._flatten({}), {})

    def test_is_bad_spots_failures(self):
        for item in [{"error": "boom"}, {"errors": ["x"]}, {"status": "failed"}, {"status": "FAILED"},
                     {"state": "timed out"}, {"code": 404}, {"status": 500}, {"resp": {"http_status": 503}},
                     {"level": "error"}, {"result": "cancelled"}, {"a": {"b": {"exception": "E"}}}]:
            self.assertTrue(squeeze._is_bad(item), item)

    def test_is_bad_ignores_healthy_and_empty_values(self):
        for item in [{"error": None}, {"error": ""}, {"errors": []}, {"error": {}}, {"error": False},
                     {"error": 0}, {"status": "ok"}, {"code": 200}, {"status_code": True}, {"status": "shipped"},
                     {}, 5, "failed", None, ["error"]]:
            self.assertFalse(squeeze._is_bad(item), item)

    def test_bad_repr_puts_identity_and_error_fields_first(self):
        item = {"total": 5, "error": {"code": "declined"}, "id": "o1"}
        self.assertEqual(squeeze._bad_repr(item, 400), 'id="o1"; error.code="declined"; total=5')
        self.assertEqual(squeeze._bad_repr("plain", 100), '"plain"')
        self.assertIn("…[+", squeeze._bad_repr({"id": 1, "note": "n" * 500}, 50))

    def test_type_names(self):
        cases = [(None, "null"), (True, "bool"), (1, "num"), (1.5, "num"), ("s", "str"), ([], "array"), ({}, "object")]
        for value, want in cases:
            self.assertEqual(squeeze._type(value), want)

    def test_num(self):
        self.assertEqual(squeeze._num(1234567), "1,234,567")
        self.assertEqual(squeeze._num(1234.5678), "1,235")
        self.assertEqual(squeeze._num(0.5), "0.5")

    def test_field_summary(self):
        fs = squeeze._field_summary
        self.assertEqual(fs(["a", "a", "b"], 3, 40), 'str, 3/3, "a"×2, "b"×1')
        self.assertEqual(fs(list(range(100)), 100, 40), "num, 100/100, 0…99 (unique)")
        self.assertEqual(fs([None, 1, 2], 5, 40), "num, 3/5, 1 null, 1×1, 2×1")
        self.assertEqual(fs([f"user{i}" for i in range(20)], 20, 40), 'str, 20/20, unique, e.g. "user0", "user1"')
        self.assertEqual(fs([[1, 2], [3]], 2, 40), "array, 2/2, len 1–2 of num")
        self.assertEqual(fs([None, None], 2, 40), "null, 2/2, 2 null")
        self.assertEqual(fs([i % 10 for i in range(100)] + [0.5], 101, 40), "num, 101/101, 0…9")
        self.assertIn("12 distinct", fs([f"k{i % 12}" for i in range(48)], 48, 40))


class SqueezeJson(unittest.TestCase):
    def render(self, obj, budget=100000):
        body, facts = squeeze.squeeze_json(obj, budget)
        return body.split("\n"), facts

    def test_small_object(self):
        lines, facts = self.render({"a": 1, "b": "x", "c": [], "d": {}, "e": None})
        self.assertEqual(lines, ["a: 1", 'b: "x"', "c: []", "d: {}", "e: null"])
        self.assertEqual(facts, "top level: object with 5 keys")

    def test_nested_object_is_indented(self):
        lines, _ = self.render({"meta": {"page": 1}})
        self.assertEqual(lines, ["meta:", "  page: 1"])

    def test_object_with_many_keys_shows_first_and_last_and_says_what_is_hidden(self):
        lines, _ = self.render({f"k{i}": i for i in range(50)})
        self.assertEqual(lines[0], "k0: 0")
        self.assertIn("… 10 keys not shown (first: k37, last: k46); last 3 keys:", lines)
        self.assertEqual(lines[-3:], ["k47: 47", "k48: 48", "k49: 49"])
        self.assertNotIn("k40: 40", lines)

    def test_deep_nesting_stops_with_a_key_summary(self):
        obj = cur = {}
        for i in range(9):
            cur["level%d" % i] = {}
            cur = cur["level%d" % i]
        cur["leaf"] = 1
        lines, _ = self.render(obj)
        self.assertTrue(any(l.strip().startswith("{1 keys: level") for l in lines), lines)
        self.assertFalse(any("leaf" in l for l in lines))

    def test_short_scalar_array_is_inline_and_long_one_is_summarised(self):
        self.assertEqual(self.render({"xs": [1, 2, 3]})[0], ["xs: [1, 2, 3]"])
        self.assertEqual(self.render({"xs": list(range(20))})[0], ["xs: array[20] at .xs: num, 20/20, 0…19 (unique)"])
        lines, facts = self.render(list(range(20)))
        self.assertEqual(lines, ["array[20] at .: num, 20/20, 0…19 (unique)"])
        self.assertEqual(facts, "top level: array of 20")

    def test_array_of_objects_lists_fields_first_and_last_item(self):
        lines, _ = self.render([{"id": i, "v": i % 3} for i in range(30)])
        self.assertEqual(lines[0], "array[30] of objects at .")
        self.assertIn("  fields (2):", lines)
        self.assertIn("    id: num, 30/30, 0…29 (unique)", lines)
        self.assertIn("    v: num, 30/30, 0×10, 1×10, 2×10", lines)
        self.assertIn("  [0]:", lines)
        self.assertEqual(lines[-1], '  [29] {"id": 29, "v": 2}')

    def test_rare_fields_are_listed_with_where_they_occur(self):
        items = [{"id": i} for i in range(30)]
        items[7]["refund"] = 1
        lines, _ = self.render(items)
        self.assertIn("  rare fields: refund (in 1 items, e.g. [7])", lines)

    def test_failing_items_are_listed_with_their_indexes(self):
        items = [{"id": i, "status": "ok"} for i in range(30)]
        items[4].update(status="failed", error="card_declined")
        items[19]["code"] = 500
        lines, _ = self.render(items)
        self.assertIn("  items that look like errors or failures: 2 (indexes 4, 19)", lines)
        self.assertTrue(any(l.startswith("    [4] id=4; ") and "card_declined" in l for l in lines), lines)

    def test_mixed_array(self):
        lines, _ = self.render([1, {"a": 1}, "x"])
        self.assertEqual(lines[0], "array[3] of mixed at .")

    def test_jq_paths_quote_unusual_keys(self):
        lines, _ = self.render({"my key": list(range(20))})
        self.assertIn('at ["my key"]', lines[0])

    def test_scalar_document(self):
        self.assertEqual(self.render("just a string"), (['"just a string"'], "scalar"))
        self.assertEqual(self.render(42), (["42"], "scalar"))

    def test_empty_containers(self):
        self.assertEqual(self.render([]), (["[]"], "top level: array of 0"))
        self.assertEqual(self.render({}), ([""], "top level: object with 0 keys"))

    def test_tight_budget_drops_the_sample_item(self):
        items = [{"id": i, "name": f"item {i}", "tags": ["a", "b"], "price": i * 1.5} for i in range(200)]
        roomy, _ = self.render(items)
        tight, _ = self.render(items, budget=40)
        self.assertIn("  [0]:", roomy)
        self.assertNotIn("  [0]:", tight)
        self.assertLess(len("\n".join(tight)), len("\n".join(roomy)))


class CsvHelpers(unittest.TestCase):
    def test_num_value(self):
        cases = [("12", 12.0), ("1.5e3", 1500.0), (" 7 ", 7.0), ("-3.2", -3.2), (".5", 0.5), ("5.", 5.0),
                 ("1,234", 1234.0), ("1,234,567.5", 1234567.5), ("$5", 5.0), ("abc", None), ("", None),
                 ("1,23", None), ("12abc", None), ("nan", None), ("inf", None), ("1_000", None)]
        for text, want in cases:
            self.assertEqual(squeeze._num_value(text), want, text)

    def test_numfmt(self):
        cases = [(5.0, "5"), (1234567.0, "1,234,567"), (1234.5, "1,234.50"), (12.5, "12.5"), (0.123456789, "0.123457"),
                 (-2.0, "-2")]
        for value, want in cases:
            self.assertEqual(squeeze._numfmt(value), want)

    def profile(self, values):
        return squeeze._profile_column(values, list(range(2, len(values) + 2)), 40)

    def test_integer_column(self):
        self.assertEqual(self.profile(["1", "2", "3"]),
                         ("int", 0, "1×1, 2×1, 3×1; min 1, max 3, mean 2, median 2, sum 6", []))

    def test_float_date_bool_and_text_columns(self):
        self.assertEqual(self.profile(["1.5", "2.5"])[0], "float")
        self.assertEqual(self.profile(["2026-01-01", "2026-01-03"])[:3], ("date", 0, "2026-01-01 … 2026-01-03, 2 distinct"))
        self.assertEqual(self.profile(["yes", "no", "yes"])[:3], ("bool", 0, '"yes"×2, "no"×1'))
        kind, nulls, summary, _ = self.profile([f"name{i}" for i in range(20)])
        self.assertEqual((kind, nulls), ("text", 0))
        self.assertEqual(summary, 'unique, length 5–6; e.g. "name0"')

    def test_null_spellings_are_counted(self):
        self.assertEqual(self.profile(["", "NA", "null", "N/A", "-", "NaN"]), ("empty", 6, "all null", []))
        self.assertEqual(self.profile(["1", "", "n/a", "2"])[:2], ("int", 2))

    def test_unique_integers_are_called_an_id(self):
        self.assertEqual(self.profile([str(i) for i in range(1, 31)])[2], "1…30, unique (likely an ID)")

    def test_a_value_far_above_the_rest_is_flagged_with_its_line(self):
        flags = self.profile([str(i) for i in range(1, 13)] + ["1000"] + ["5"])[3]
        self.assertEqual(flags, ["max 1,000 at L14 is 83.3× the next largest (12)"])

    def test_a_single_negative_value_is_flagged(self):
        flags = self.profile(["-5"] + [str(i) for i in range(1, 13)] + ["3"])[3]
        self.assertEqual(flags, ["min -5 at L2 is the only negative value"])

    def test_no_flags_for_an_ordinary_spread(self):
        self.assertEqual(self.profile([str(i) for i in range(1, 40)] + ["7"])[3], [])

    def test_repeated_text_values_show_the_most_common(self):
        values = ["north"] * 9 + ["south"] * 5 + [f"other{i}" for i in range(20)]
        self.assertIn('top "north"×9, "south"×5', self.profile(values)[2])

    def test_csv_shape(self):
        self.assertEqual(squeeze._csv_shape(["a,b,c"] * 6), ",")
        self.assertEqual(squeeze._csv_shape(["a;b;c"] * 6), ";")
        self.assertEqual(squeeze._csv_shape(["a|b"] * 6), "|")
        self.assertEqual(squeeze._csv_shape(["a\tb"] * 6), "\t")
        self.assertIsNone(squeeze._csv_shape(["a,b,c"] * 4), "fewer than five lines is not enough to judge")
        self.assertIsNone(squeeze._csv_shape(["just words", "more words here", "and, a comma", "no", "x", "y z"]))
        self.assertIsNone(squeeze._csv_shape([]))


class SqueezeCsv(unittest.TestCase):
    def test_header_rows_and_columns(self):
        text = "name,qty,price\n" + "".join(f"item{i},{i},{i * 1.5}\n" for i in range(1, 21))
        body, facts = squeeze.squeeze_csv(text, 1500)
        lines = body.split("\n")
        self.assertEqual(facts, "20 rows × 3 columns")
        self.assertEqual(lines[0], "columns (3), 20 data rows:")
        self.assertTrue(lines[1].startswith("  name (text): unique"))
        self.assertIn("first rows:", lines)
        self.assertIn("L1 name,qty,price", lines)
        self.assertIn("L2 item1,1,1.5", lines)
        self.assertIn("  … 13 rows not shown", lines)
        self.assertEqual(lines[-1], "L21 item20,20,30.0")

    def test_numeric_first_row_means_no_header(self):
        text = "".join(f"{i},{i * 2},{i * 3}\n" for i in range(1, 31))
        body, facts = squeeze.squeeze_csv(text, 1500)
        self.assertEqual(facts, "30 rows × 3 columns")
        self.assertIn("  col1 (int)", body)
        self.assertIn("L1 1,2,3", body)

    def test_rows_with_the_wrong_number_of_fields_are_reported(self):
        text = "a,b,c\n" + "1,2,3\n" * 8 + "4,5\n" + "1,2,3\n" * 3
        body, _ = squeeze.squeeze_csv(text, 1500)
        self.assertIn("! 1 rows have the wrong number of fields (expected 3): L10 has 2 fields", body)

    def test_other_delimiters_are_named(self):
        text = "a\tb\n" + "".join(f"{i}\t{i}\n" for i in range(20))
        body, _ = squeeze.squeeze_csv(text, 1500)
        self.assertTrue(body.startswith("columns (2), 20 data rows, delimiter '\\t':"), body[:60])

    def test_wide_tables_list_the_columns_that_are_not_profiled(self):
        header = ",".join(f"c{i}" for i in range(70))
        text = header + "\n" + (",".join("1" for _ in range(70)) + "\n") * 10
        body, facts = squeeze.squeeze_csv(text, 100000)
        self.assertEqual(facts, "10 rows × 70 columns")
        self.assertIn("  … +10 more columns: c60, c61", body)

    def test_quoted_field_with_a_line_break_keeps_original_line_numbers(self):
        text = 'id,note\n1,"two\nlines"\n' + "".join(f"{i},ok\n" for i in range(2, 12))
        body, facts = squeeze.squeeze_csv(text, 1500)
        self.assertEqual(facts, "11 rows × 2 columns")
        self.assertIn("L13 11,ok", body)

    def test_too_few_rows_is_an_error_for_the_caller_to_handle(self):
        with self.assertRaises(ValueError):
            squeeze.squeeze_csv("only,a,header\n", 100)
        with self.assertRaises(ValueError):
            squeeze.squeeze_csv("", 100)


class SqueezeText(unittest.TestCase):
    def test_long_text_shows_head_and_tail(self):
        lines = [f"line {i}" for i in range(1, 1001)]
        body, facts = squeeze.squeeze_text("\n".join(lines), 1500)
        out = body.split("\n")
        self.assertEqual(facts, "1,000 lines, head and tail only")
        self.assertEqual(out[0], "L1 line 1")
        self.assertEqual(out[-1], "L1000 line 1000")
        self.assertIn("  … L76–L925: 850 lines not shown", out)

    def test_short_text_shows_every_line_once(self):
        lines = [f"line {i}" for i in range(1, 101)]
        body, _ = squeeze.squeeze_text("\n".join(lines), 1500)
        self.assertEqual(body.split("\n"), [f"L{i} line {i}" for i in range(1, 101)])

    def test_tight_budget_shows_fewer_lines(self):
        lines = ["some reasonably long line of text number %d" % i for i in range(1000)]
        roomy, _ = squeeze.squeeze_text("\n".join(lines), 1500)
        tight, _ = squeeze.squeeze_text("\n".join(lines), 100)
        self.assertLess(tight.count("\n"), roomy.count("\n"))

    def test_single_enormous_line_is_clipped(self):
        body, facts = squeeze.squeeze_text("x" * 100000, 1500)
        self.assertEqual(facts, "1 lines, head and tail only")
        self.assertLess(len(body), 400)


class SaveOriginal(unittest.TestCase):
    def setUp(self):
        self.dir = support.tmp("save-original", self.id().rsplit(".", 1)[-1], "cache")

    def test_writes_the_text_with_an_extension_for_its_type(self):
        for kind, ext in [("log", ".log"), ("json", ".json"), ("jsonl", ".jsonl"), ("csv", ".csv"), ("text", ".txt")]:
            path = squeeze.save_original(f"content for {kind}", kind, self.dir)
            self.assertTrue(path.endswith(ext), path)
            self.assertEqual(support.read(path), f"content for {kind}")

    def test_file_and_folder_are_private(self):
        path = squeeze.save_original("secret\n", "log", self.dir)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.dir).st_mode), 0o700)

    def test_same_content_reuses_the_same_file(self):
        a = squeeze.save_original("same\n", "log", self.dir)
        b = squeeze.save_original("same\n", "log", self.dir)
        c = squeeze.save_original("different\n", "log", self.dir)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(os.listdir(self.dir)), 2)

    def test_folder_comes_from_the_environment_when_not_given(self):
        old = os.environ["LEMBAS_SQUEEZE_DIR"]
        os.environ["LEMBAS_SQUEEZE_DIR"] = self.dir
        try:
            self.assertEqual(os.path.dirname(squeeze.save_original("x\n", "log")), self.dir)
        finally:
            os.environ["LEMBAS_SQUEEZE_DIR"] = old

    def test_unicode_round_trips(self):
        text = "café 你好 \U0001F600\n"
        self.assertEqual(support.read(squeeze.save_original(text, "text", self.dir)), text)


def log_text(n=4000):
    return "".join(f"{ts(i)} INFO tick {i} ok\n" for i in range(n)) + "ERROR boom at the end\n"


class Squeeze(unittest.TestCase):
    def test_input_at_the_threshold_passes_through_and_one_token_over_does_not(self):
        self.assertEqual(squeeze.squeeze("a" * 30, threshold=10), (None, {"kind": "auto", "before": 10, "after": 10}))
        view, info = squeeze.squeeze("a" * 33, kind="text", threshold=10)
        self.assertEqual(info["before"], 11)
        self.assertEqual(info["kind"], "text")

    def test_empty_and_whitespace_only_input_pass_through(self):
        self.assertIsNone(squeeze.squeeze("")[0])
        self.assertIsNone(squeeze.squeeze(" \n" * 20000)[0])
        self.assertIsNone(squeeze.squeeze("", threshold=0)[0])

    def test_summary_header_names_the_type_size_and_original(self):
        view, info = squeeze.squeeze(log_text(), original_path="/var/log/app.log")
        header = view.split("\n")[0]
        self.assertRegex(header, r"^\[lembas squeeze: log, 4,001 lines, 1 error lines \(1 distinct\), 0 warnings\. "
                                 r"~[\d,]+ tokens shown as a summary\. Full original: /var/log/app\.log ; "
                                 r"grep -n or sed -n 'A,Bp' the original for any line range\. "
                                 r"Lines marked L123 are original line numbers\.\]$")
        self.assertEqual(info["kind"], "log")
        self.assertEqual(info["path"], "/var/log/app.log")
        self.assertLess(info["after"], info["before"])
        self.assertEqual(info["after"], squeeze.est_tokens(view))

    def test_without_an_original_path_the_text_is_saved_and_the_header_points_to_it(self):
        text = log_text()
        view, info = squeeze.squeeze(text)
        self.assertIn(f"Full original: {info['path']} ;", view)
        self.assertEqual(support.read(info["path"]), text)

    def test_each_data_type_gets_its_own_hint(self):
        hints = {"json": "jq", "jsonl": "jq", "csv": "pandas", "log": "grep -n", "text": "offset"}
        inputs = {
            "json": json.dumps([{"id": i, "v": "x" * 20} for i in range(2000)]),
            "jsonl": "\n".join(json.dumps({"id": i, "v": "x" * 20}) for i in range(2000)),
            "csv": "a,b,c\n" + "".join(f"{i},{i},{i}\n" for i in range(4000)),
            "log": log_text(),
            "text": "\n".join(f"plain line {i}" for i in range(5000)),
        }
        for kind, text in inputs.items():
            view, info = squeeze.squeeze(text, kind=kind, original_path="orig")
            self.assertEqual(info["kind"], kind)
            self.assertIn(hints[kind], view.split("\n")[0], kind)

    def test_code_passes_through_until_it_is_enormous(self):
        code = "def f(x):\n    return x\n\n" * 3000
        view, info = squeeze.squeeze(code)
        self.assertIsNone(view)
        self.assertEqual((info["kind"], info["before"]), ("code", info["after"]))
        view, info = squeeze.squeeze(code, hard_cap=1000, original_path="big.py")
        self.assertTrue(view.startswith("[lembas squeeze: text"), view[:40])

    def test_forcing_a_type_overrides_detection(self):
        rnd = random.Random(1)
        words = "the a system user request value result change table query".split()
        prose = "\n".join(" ".join(rnd.choice(words) for _ in range(12)).capitalize() + "." for _ in range(900))
        self.assertIsNone(squeeze.squeeze(prose)[0])
        view, info = squeeze.squeeze(prose, kind="text", original_path="p.txt")
        self.assertTrue(view.startswith("[lembas squeeze: text"))

    def test_a_summary_that_saves_under_30_percent_is_dropped(self):
        rnd = random.Random(5)
        for n in range(60, 140, 4):
            text = "\n".join(f"ERROR unit{rnd.getrandbits(40):x} failed: cause {rnd.getrandbits(60):x} "
                             f"in handler {rnd.getrandbits(30):x}" for _ in range(n)) + "\n"
            view, info = squeeze.squeeze(text, kind="log", original_path="e.log")
            if view is None and info["before"] > squeeze.DEFAULT_THRESHOLD:
                self.assertGreater(info["after"], info["before"] * (1 - squeeze.MIN_SAVING))
                return
        self.fail("could not build an input whose summary saves under 30%")

    def test_a_parser_failure_falls_back_to_the_text_view_and_records_why(self):
        text = "just one line with no table in it " * 2000
        view, info = squeeze.squeeze(text, kind="csv", original_path="x.csv")
        self.assertEqual(info["kind"], "text")
        self.assertIn("ValueError", info["error"])
        self.assertTrue(view.startswith("[lembas squeeze: text"))

    def test_json_lines_that_do_not_parse_are_kept_as_marked_records(self):
        lines = [json.dumps({"id": i, "msg": "m" * 30}) for i in range(1500)]
        lines[700] = "{this is not json"
        view, _ = squeeze.squeeze("\n".join(lines), kind="jsonl", original_path="e.jsonl")
        self.assertIn("array[1500]", view)
        self.assertIn("_unparsed_line", view)

    def test_colour_codes_do_not_count_towards_the_size(self):
        plain = "x" * 300
        coloured = "\x1b[31m" + plain + "\x1b[0m"
        self.assertEqual(squeeze.squeeze(coloured)[1]["before"], squeeze.squeeze(plain)[1]["before"])

    def test_none_is_rejected(self):
        with self.assertRaises(TypeError):
            squeeze.squeeze(None)


class Cli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = support.write(support.tmp("cli", "app.log"), log_text())

    def cli(self, *args, data=None, env=None):
        r = support.run_py(support.SQUEEZE_PY, *args, data=data, env=env)
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def test_file_argument(self):
        code, out, err = self.cli(self.log)
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("[lembas squeeze: log"))
        self.assertIn(f"Full original: {self.log} ;", out)
        self.assertTrue(out.endswith("\n"))

    def test_standard_input(self):
        code, out, _ = self.cli(data=log_text())
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("[lembas squeeze: log"))

    def test_small_input_is_printed_unchanged(self):
        code, out, _ = self.cli(data="hello\nworld\n")
        self.assertEqual((code, out), (0, "hello\nworld\n"))

    def test_output_always_ends_with_a_newline(self):
        self.assertEqual(self.cli(data="no newline at end")[1], "no newline at end\n")

    def test_pass_through_still_strips_colour_codes(self):
        self.assertEqual(self.cli(data="\x1b[32mok\x1b[0m\n")[1], "ok\n")

    def test_type_budget_and_threshold_options(self):
        code, out, _ = self.cli("--type", "text", self.log)
        self.assertTrue(out.startswith("[lembas squeeze: text"))
        roomy = self.cli(self.log)[1]
        tight = self.cli("--budget", "200", self.log)[1]
        self.assertLess(len(tight), len(roomy))
        code, out, _ = self.cli("--threshold", "1000000", self.log)
        self.assertEqual(out, log_text())

    def test_stats_go_to_standard_error(self):
        code, out, err = self.cli("--stats", self.log)
        self.assertRegex(err, r"^squeeze: log, ~[\d,]+ → ~[\d,]+ tokens \(\d+% smaller\)\n$")
        self.assertTrue(out.startswith("[lembas squeeze"))

    def test_version(self):
        code, out, _ = self.cli("--version")
        self.assertEqual((code, out.strip()), (0, squeeze.VERSION))

    def test_unknown_type_is_a_usage_error(self):
        code, out, err = self.cli("--type", "yaml", self.log)
        self.assertEqual(code, 2)
        self.assertIn("invalid choice", err)

    def test_bytes_that_are_not_utf8_do_not_crash(self):
        r = support.run_py(support.SQUEEZE_PY, data=b"caf\xe9 \xff\xfe\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("caf", r.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
