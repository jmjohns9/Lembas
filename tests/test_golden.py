#!/usr/bin/env python3
"""Golden-output tests: the exact text squeeze.py and ithildin.py print for known inputs.

Run: python3 tests/test_golden.py

Each case compares today's output with a file in tests/golden/. They exist to prove that a
refactor or an optimization changes nothing a reader can see. When a change to the output is
intended (a bug fix), regenerate the files and review the diff before committing it:

    UPDATE_GOLDEN=1 python3 tests/test_golden.py && git diff tests/golden

Inputs come from the deterministic fixture generators. PDF output is not recorded here, because
PDF layout depends on the fonts installed; the Markdown and Word versions of the manual are.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import squeeze  # noqa: E402

GOLDEN = os.path.join(support.TESTS, "golden")
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
PASS_THROUGH = "<passed through unchanged>\n"


class GoldenCase(unittest.TestCase):
    maxDiff = None

    def check(self, name, text):
        path = os.path.join(GOLDEN, name + ".txt")
        if UPDATE:
            os.makedirs(GOLDEN, exist_ok=True)
            support.write(path, text)
            return
        self.assertTrue(os.path.exists(path), f"no golden file for {name}; see this module's docstring")
        self.assertEqual(text, support.read(path), f"output differs from tests/golden/{name}.txt")


class SqueezeGolden(GoldenCase):
    FILES = ["app.log", "orders.json", "events.jsonl", "sales.csv", "mid-app.log", "mid-orders.json",
             "mid-sales.csv"]

    def view(self, text, name, **kw):
        # original_path is the bare file name, so the header is the same on every machine.
        view, _ = squeeze.squeeze(text, name, original_path=name or "piped-output", **kw)
        return PASS_THROUGH if view is None else view + "\n"

    def test_default_budget(self):
        for name in self.FILES:
            with self.subTest(file=name):
                text = support.read(os.path.join(support.squeeze_fixtures(), name))
                self.check(f"squeeze-{name}", self.view(text, name))

    def test_tight_budget_uses_the_smaller_detail_levels(self):
        for name in ["app.log", "orders.json", "sales.csv"]:
            with self.subTest(file=name):
                text = support.read(os.path.join(support.squeeze_fixtures(), name))
                self.check(f"squeeze-{name}-budget300", self.view(text, name, budget=300))

    def test_piped_command_output_is_detected_without_a_name(self):
        for script in ["run_tests.py", "fetch_orders.py"]:
            with self.subTest(script=script):
                out = support.run_py(os.path.join(support.squeeze_fixtures(), script)).stdout.decode("utf-8")
                self.check(f"squeeze-piped-{script}", self.view(out, None))

    def test_forced_text_view(self):
        text = support.read(os.path.join(support.squeeze_fixtures(), "app.log"))
        self.check("squeeze-app.log-as-text", self.view(text, "app.log", kind="text"))


class IthildinGolden(GoldenCase):
    def run_cases(self, fmt):
        docs = support.manual_docs()
        if fmt not in docs:
            self.skipTest(f"{fmt} cannot be built here (python-docx is not installed)")
        path, tag = docs[fmt], fmt.replace("manual.", "ithildin-")
        full_map = support.ithildin_out("map", path, "--budget", "20000")
        self.check(f"{tag}-map", support.ithildin_out("map", path))
        self.check(f"{tag}-map-budget800", support.ithildin_out("map", path, "--budget", "800"))
        self.check(f"{tag}-map-depth1", support.ithildin_out("map", path, "--depth", "1"))
        self.check(f"{tag}-find", support.ithildin_out("find", path, "coolant outlet", "altitude", "OF-7731", "-C", "1"))
        self.check(f"{tag}-find-regex", support.ithildin_out("find", path, "--regex", r"torque\s+values?", "-n", "5"))
        self.check(f"{tag}-read-section", support.ithildin_out("read", path, "7.3"))
        self.check(f"{tag}-read-truncated", support.ithildin_out("read", path, "7", "--max-tokens", "500"))
        self.check(f"{tag}-read-lines", support.ithildin_out("read", path, "L40-48"))
        table = re.search(r"(?m)^\s*(T\d+) [^:]+: Table \d+\. Torque values for engine", full_map).group(1)
        self.check(f"{tag}-table", support.ithildin_out("table", path, table))

    def test_markdown(self):
        self.run_cases("manual.md")

    def test_word(self):
        self.run_cases("manual.docx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
