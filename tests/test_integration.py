#!/usr/bin/env python3
"""End-to-end tests of the workflows the skills describe. Run: python3 tests/test_integration.py

Each test follows a workflow the way Claude is told to: get the summary, then go back to the
original for exact values. They run the real command-line tools in subprocesses.
"""
import csv
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import ithildin_fixtures  # noqa: E402


def squeeze_cli(*args, data=None, env=None):
    r = support.run_py(support.SQUEEZE_PY, *args, data=data, env=env)
    assert r.returncode == 0, r.stderr.decode()
    return r.stdout.decode("utf-8")


def original_path(summary):
    return summary.split("\n", 1)[0].split("Full original: ", 1)[1].split(" ;", 1)[0]


def cited_lines(summary):
    """(line number, text) for every unclipped 'L123 text' row in a summary."""
    for row in summary.split("\n"):
        m = re.match(r"^L(\d+) (.*)$", row)
        if m and "…[+" not in m.group(2):
            yield int(m.group(1)), m.group(2)


class SqueezeWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = support.squeeze_fixtures()
        cls.answers = json.loads(support.read(os.path.join(cls.fx, "answers.json")))

    def test_piped_test_run_then_look_up_a_cited_line_in_the_saved_original(self):
        raw = support.run_py(os.path.join(self.fx, "run_tests.py")).stdout.decode("utf-8")
        summary = squeeze_cli(data=raw)
        self.assertLess(len(summary), len(raw) / 20)
        for name in self.answers["run_tests.py"]["failed"]:
            self.assertIn(name, summary)
        self.assertIn("3 failed, 3997 passed", summary)
        saved = original_path(summary)
        self.assertEqual(support.read(saved), raw, "the saved original is the complete piped output")
        original = raw.split("\n")
        cited = list(cited_lines(summary))
        self.assertGreater(len(cited), 20)
        for number, text in cited:
            self.assertEqual(original[number - 1], text, f"L{number}")

    def test_log_summary_points_at_the_incident_and_the_original_confirms_it(self):
        path = os.path.join(self.fx, "app.log")
        summary = squeeze_cli(path)
        self.assertEqual(original_path(summary), path, "a file argument is its own original; nothing is copied")
        original = support.read(path).split("\n")
        trace = self.answers["app.log"]["traceback_line"]
        self.assertIn(f"L{trace} ", summary)
        self.assertIn("Unhandled exception", original[trace - 1])
        self.assertEqual(original[trace + 5], "KeyError: 'customer_id'")
        note = re.search(r"\[this error repeats (\d+)× in total, last at L(\d+)\]", summary)
        count, last = int(note.group(1)), int(note.group(2))
        self.assertIn(self.answers["app.log"]["redis_host"], original[last - 1])
        self.assertEqual(count, self.answers["app.log"]["redis_connection_errors"])
        self.assertEqual(count, sum("redis.exceptions.ConnectionError" in l for l in original),
                         "the count in the summary is the count in the file")

    def test_csv_profile_matches_figures_computed_on_the_original(self):
        path = os.path.join(self.fx, "sales.csv")
        summary = squeeze_cli(path)
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        total = sum(float(r["revenue"]) for r in rows)
        self.assertIn(f"{len(rows):,} rows × 7 columns", summary)
        self.assertIn(f"sum {total:,.2f}", summary)
        self.assertIn(f"{sum(r['rep'] == '' for r in rows)} null", summary)
        flagged = int(re.search(r"! max [\d,.]+ at L(\d+) is", summary).group(1))
        self.assertIn("987654.32", support.read(path).split("\n")[flagged - 1])

    def test_json_failure_indexes_point_at_the_failing_records(self):
        path = os.path.join(self.fx, "orders.json")
        summary = squeeze_cli(path)
        data = json.loads(support.read(path))["data"]
        listed = re.search(r"items that look like errors or failures: (\d+) \(indexes ([\d, ]+)\)", summary)
        indexes = [int(i) for i in listed.group(2).split(", ")]
        self.assertEqual(int(listed.group(1)), len(indexes))
        self.assertEqual({data[i]["id"]: data[i]["error"]["code"] for i in indexes},
                         self.answers["orders.json"]["failed_orders"])
        self.assertIn("at .data", summary, "the summary gives the jq path to the array")

    def test_output_is_identical_on_every_run(self):
        path = os.path.join(self.fx, "events.jsonl")
        self.assertEqual(squeeze_cli(path), squeeze_cli(path))
        raw = support.read(path)
        self.assertEqual(squeeze_cli(data=raw), squeeze_cli(data=raw), "piped input hashes to the same saved file")

    def test_the_hook_and_the_command_line_give_the_same_summary(self):
        path = os.path.join(self.fx, "app.log")
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "./run.sh"},
                   "tool_response": {"stdout": "preview only\n", "stderr": "", "persistedOutputPath": path}}
        r = support.run_py(support.HOOK_PY, data=json.dumps(payload))
        hooked = json.loads(r.stdout)["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        self.assertEqual(hooked + "\n", squeeze_cli(path))

    def test_small_code_and_diff_inputs_come_back_untouched(self):
        for text in ("print('hello')\n", "diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b\n",
                     "def f(x):\n    return x\n\n" * 2000):
            self.assertEqual(squeeze_cli(data=text), text)


def flat(text):
    """Collapse whitespace and drop page markers, so a phrase split by a line or page break matches."""
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\[p\d+\]$", "", text))


class IthildinWorkflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = support.manual_docs()

    def ith(self, *args):
        r = support.run_py(support.ITHILDIN_PY, *args)
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        return r.stdout.decode("utf-8")

    def test_map_then_find_then_read_answers_each_planted_question(self):
        for name, path in self.docs.items():
            full_map = self.ith("map", path, "--budget", "20000")
            for key, fact in ithildin_fixtures.PLANTED.items():
                if key in ("head_bolt_torque", "oil_filter_pn"):
                    continue                      # these two live in tables; see the next test
                with self.subTest(doc=name, fact=key):
                    section = fact["section"]
                    self.assertRegex(full_map, rf"(?m)^\s*{re.escape(section)} ", "the map lists the section")
                    found = self.ith("find", path, fact["needle"][:40])
                    self.assertIn(f"§{section} ", found, "find points at that section")
                    text = flat(self.ith("read", path, section))
                    self.assertIn(fact["needle"], text, "read returns the sentence that answers")
                    self.assertIn(fact["answer"], text)

    def test_table_questions_are_answered_from_table_rows(self):
        for name, path in self.docs.items():
            with self.subTest(doc=name):
                full_map = self.ith("map", path, "--budget", "20000")
                torque = re.search(r"(?m)^\s*(T\d+) [^:]+: Table \d+\. Torque values for engine", full_map).group(1)
                self.assertIn("| Cylinder head bolt | M12 | 85 | Spiral, 3 passes |", self.ith("table", path, torque))
                parts = re.search(r"(?m)^\s*(T\d+) [^:]+: Table \d+\. Common replacement parts", full_map).group(1)
                self.assertIn("| Oil filter | OF-7731-B | 1 |", self.ith("table", path, parts))

    def test_a_section_can_be_read_by_title_when_it_has_no_number(self):
        for name, path in self.docs.items():
            with self.subTest(doc=name):
                text = self.ith("read", path, "Appendix B")
                self.assertRegex(text.split("\n")[0], r"^\[ithildin read: S\d+ Appendix B Parts List, ")
                self.assertIn("OF-7731-B", text)

    def test_a_long_read_can_be_continued_until_the_section_is_complete(self):
        path = self.docs["manual.md"]
        whole = self.ith("read", path, "7", "--max-tokens", "1000000").split("\n")[1:-1]
        pieces, target = [], "7"
        for _ in range(60):
            out = self.ith("read", path, target, "--max-tokens", "1500").rstrip("\n").split("\n")
            more = re.match(r"^\[truncated at .* Continue with: read FILE (L\d+-\d+)", out[-1])
            pieces += out[1:-1] if more else out[1:]
            if not more:
                break
            target = more.group(1)
        else:
            self.fail("the read never finished")
        self.assertEqual(pieces, whole)

    def test_the_map_is_a_small_fraction_of_the_document(self):
        for name, path in self.docs.items():
            with self.subTest(doc=name):
                header = self.ith("map", path).split("\n")[0]
                whole = int(re.search(r"~([\d,]+) tokens", header).group(1).replace(",", ""))
                import ithildin
                self.assertLess(ithildin.est_tokens(self.ith("map", path)), whole / 25)

    def test_the_cache_is_shared_between_separate_runs(self):
        cache = support.tmp("integration", "ith-cache", "x")[:-2]
        path = self.docs["manual.md"]
        first = support.run_py(support.ITHILDIN_PY, "map", path, env={"ITHILDIN_CACHE": cache}).stdout
        entries = os.listdir(cache)
        second = support.run_py(support.ITHILDIN_PY, "find", path, "coolant", env={"ITHILDIN_CACHE": cache})
        self.assertEqual(second.returncode, 0)
        self.assertEqual(os.listdir(cache), entries, "the second command reuses the first one's parse")
        self.assertEqual(support.run_py(support.ITHILDIN_PY, "map", path, env={"ITHILDIN_CACHE": cache}).stdout, first)


if __name__ == "__main__":
    unittest.main(verbosity=1)
