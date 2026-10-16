#!/usr/bin/env python3
"""Tests for squeeze.py and the Claude Code hook. Run: python3 tests/test_squeeze.py"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "lembas") if os.path.isdir(os.path.join(ROOT, "skills")) else os.path.join(ROOT, "lembas")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import squeeze  # noqa: E402

HOOK = os.path.join(SKILL, "hooks", "squeeze_hook.py")
FIXTURES = tempfile.mkdtemp(prefix="lembas-fixtures-")
subprocess.run([sys.executable, os.path.join(ROOT, "tests", "make_fixtures.py"), FIXTURES],
               check=True, stdout=subprocess.DEVNULL)
ANSWERS = json.load(open(os.path.join(FIXTURES, "answers.json")))
os.environ["LEMBAS_SQUEEZE_DIR"] = tempfile.mkdtemp(prefix="lembas-cache-")


def view_of(name, **kw):
    path = os.path.join(FIXTURES, name)
    text = open(path).read()
    view, info = squeeze.squeeze(text, path, original_path=path, **kw)
    return view, info


def run_hook(payload, env=None):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, env=e)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


class PassThrough(unittest.TestCase):
    def test_small_input_unchanged(self):
        view, _ = squeeze.squeeze("ERROR one line\n" * 10)
        self.assertIsNone(view)

    def test_source_code_unchanged(self):
        code = "\n".join(f"def f{i}(x):\n    return x * {i}\n" for i in range(800))
        view, info = squeeze.squeeze(code)
        self.assertIsNone(view)
        self.assertEqual(info["kind"], "code")

    def test_diff_unchanged(self):
        diff = "diff --git a/x.py b/x.py\n@@ -1,3 +1,3 @@\n" + "\n".join(f"-old {i}\n+new {i}" for i in range(3000))
        view, _ = squeeze.squeeze(diff)
        self.assertIsNone(view)

    def test_prose_unchanged(self):
        rnd = random.Random(1)
        words = "the a system user request value result change table query".split()
        prose = "\n".join(" ".join(rnd.choice(words) for _ in range(12)).capitalize() + "." for _ in range(900))
        view, info = squeeze.squeeze(prose)
        self.assertIsNone(view, info)

    def test_broken_json_falls_back_safely(self):
        text = '{"a": [' + ",".join(str(i) for i in range(20000))  # truncated
        view, info = squeeze.squeeze(text, "x.json")
        self.assertTrue(view is None or view.startswith("[lembas squeeze"))

    def test_deterministic(self):
        a, _ = view_of("app.log")
        b, _ = view_of("app.log")
        self.assertEqual(a, b)


class Logs(unittest.TestCase):
    def setUp(self):
        self.view, self.info = view_of("app.log")
        self.facts = ANSWERS["app.log"]

    def test_much_smaller(self):
        self.assertLess(self.info["after"], self.info["before"] * 0.01)

    def test_root_cause_and_trace_kept(self):
        self.assertIn("KeyError: 'customer_id'", self.view)
        self.assertIn("payments/settle.py\", line 142", self.view)
        self.assertIn(f"L{self.facts['traceback_line']} ", self.view)

    def test_repeated_error_counted(self):
        self.assertIn(self.facts["redis_host"], self.view)
        self.assertIn(f"repeats {self.facts['redis_connection_errors']}×", self.view)

    def test_line_numbers_match_original(self):
        lines = open(os.path.join(FIXTURES, "app.log")).read().split("\n")
        for row in self.view.split("\n"):
            if row.startswith("L") and " " in row:
                num, text = row.split(" ", 1)
                if num[1:].isdigit() and "…[+" not in text:
                    self.assertEqual(lines[int(num[1:]) - 1], text)

    def test_no_error_ever_silently_dropped(self):
        rnd = random.Random(7)
        lines = [f"2026-01-01 00:00:{i % 60:02d} INFO tick {i}" for i in range(30000)]
        kinds = [f"ERROR module{chr(65 + k)} failed: disk {chr(97 + k)} unavailable" for k in range(60)]
        for k in kinds:
            lines.insert(rnd.randrange(len(lines)), k)
        view, _ = squeeze.squeeze("\n".join(lines))
        shown = sum(k in view for k in kinds)
        self.assertGreater(shown, 0)
        if shown < len(kinds):
            self.assertIn(f"{len(kinds) - shown} more distinct error messages not shown", view)

    def test_names_containing_error_are_not_errors(self):
        for line in ["npm http fetch GET 200 https://registry.npmjs.org/http-errors 49ms",
                     "install liberror-perl:all <none> 0.17029-2", "GET /api/error 200", "0 errors, 0 failed"]:
            self.assertEqual(squeeze._severity(line), 0, line)
        for line in ["Build failed.", "KeyError: 'x'", "ERROR boom", "request timed out", '"GET /x HTTP/1.1" 502 0']:
            self.assertEqual(squeeze._severity(line), 2, line)

    def test_ansi_and_progress_bars_removed(self):
        text = "\n".join(f"\x1b[32mINFO\x1b[0m step {i} 10%\r50%\r100%" for i in range(4000))
        view, _ = squeeze.squeeze(text)
        self.assertNotIn("\x1b", view)
        self.assertNotIn("\r", view)


class Json(unittest.TestCase):
    def test_orders(self):
        view, info = view_of("orders.json")
        self.assertLess(info["after"], info["before"] * 0.03)
        self.assertIn("array[640]", view)
        for order_id, code in ANSWERS["orders.json"]["failed_orders"].items():
            self.assertIn(order_id, view)
            self.assertIn(code, view)
        self.assertIn("refund", view)
        self.assertIn("at .data", view)

    def test_jsonl(self):
        view, _ = view_of("events.jsonl")
        self.assertIn("array[5000]", view)
        self.assertIn(ANSWERS["events.jsonl"]["error_message"], view)
        for i in ANSWERS["events.jsonl"]["error_events"]:
            self.assertIn(f"[{i}]", view)


class Csv(unittest.TestCase):
    def test_sales(self):
        view, info = view_of("sales.csv")
        facts = ANSWERS["sales.csv"]
        self.assertLess(info["after"], info["before"] * 0.01)
        self.assertIn("9,000 rows", view)
        self.assertIn(f"sum {facts['revenue_total']:,.2f}", view)
        self.assertIn(f"{facts['null_reps']} null", view)
        self.assertIn("987,654.32 at L6063", view)
        self.assertEqual(view.count("! max"), 1, "only the shifted-decimal row should be flagged")
        for region in facts["regions"]:
            self.assertIn(region, view)


class Hook(unittest.TestCase):
    def test_bash_large_output_replaced(self):
        text = open(os.path.join(FIXTURES, "app.log")).read()[:200000]
        out = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "cat app.log"},
                        "tool_response": {"stdout": text, "stderr": "", "interrupted": False, "isImage": False}})
        new = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertTrue(new["stdout"].startswith("[lembas squeeze: log"))
        self.assertEqual(set(new), {"stdout", "stderr", "interrupted", "isImage"})

    def test_bash_persisted_output_used(self):
        path = os.path.join(FIXTURES, "app.log")
        out = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "cat app.log"},
                        "tool_response": {"stdout": "2026 INFO truncated preview\n" * 1200, "stderr": "",
                                          "persistedOutputPath": path, "persistedOutputSize": os.path.getsize(path)}})
        stdout = out["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        self.assertIn("KeyError: 'customer_id'", stdout)
        self.assertIn(path, stdout)

    def test_bash_small_and_raw_untouched(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
                   "tool_response": {"stdout": "a\nb\n", "stderr": ""}}
        self.assertIsNone(run_hook(payload))
        big = open(os.path.join(FIXTURES, "app.log")).read()[:100000]
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "LEMBAS_RAW=1 cat app.log"},
                   "tool_response": {"stdout": big, "stderr": ""}}
        self.assertIsNone(run_hook(payload))
        payload["tool_input"]["command"] = "cat app.log"
        self.assertIsNone(run_hook(payload, {"LEMBAS_SQUEEZE": "0"}))

    def test_read_post_and_slices(self):
        path = os.path.join(FIXTURES, "sales.csv")
        content = "".join(open(path).readlines()[:3000])
        resp = {"type": "text", "file": {"filePath": path, "content": content, "numLines": 3000, "startLine": 1, "totalLines": 3000}}
        out = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": path}, "tool_response": resp})
        f = out["hookSpecificOutput"]["updatedToolOutput"]["file"]
        self.assertTrue(f["content"].startswith("[lembas squeeze: csv"))
        self.assertIsNone(run_hook({"hook_event_name": "PostToolUse", "tool_name": "Read",
                                    "tool_input": {"file_path": path, "offset": 10, "limit": 50}, "tool_response": resp}))
        code = dict(resp, file=dict(resp["file"], filePath="/x/app.py"))
        self.assertIsNone(run_hook({"hook_event_name": "PostToolUse", "tool_name": "Read",
                                    "tool_input": {"file_path": "/x/app.py"}, "tool_response": code}))

    def test_read_pre_oversized(self):
        path = os.path.join(FIXTURES, "app.log")
        out = run_hook({"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path}})
        h = out["hookSpecificOutput"]
        self.assertEqual(h["permissionDecision"], "deny")
        self.assertIn("KeyError: 'customer_id'", h["permissionDecisionReason"])
        self.assertLess(len(h["permissionDecisionReason"]), 10000)

    def test_bad_input_never_crashes(self):
        r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")


class Cli(unittest.TestCase):
    def test_pipe_saves_original(self):
        text = open(os.path.join(FIXTURES, "app.log")).read()
        r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "squeeze.py")], input=text,
                           capture_output=True, text=True)
        header = r.stdout.split("\n", 1)[0]
        path = header.split("Full original: ", 1)[1].split(" ;", 1)[0]
        self.assertEqual(open(path).read(), text)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600, "saved output must be private")
        self.assertEqual(os.stat(os.path.dirname(path)).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main(verbosity=2)
