#!/usr/bin/env python3
"""Unit tests for the Claude Code hook. Run: python3 tests/test_squeeze_hook.py

tests/test_squeeze.py drives the hook as Claude Code does, through a subprocess. These tests call
its functions in-process, so each branch can be reached and measured. No Claude Code is needed:
the hook's input is a JSON event and its output is JSON, and both are built and read here.
"""
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

hook = support.load_script("squeeze_hook", support.HOOK_PY)


def log_text(n=4000):
    return "".join(f"2026-01-01 00:{i // 60 % 60:02d}:{i % 60:02d} INFO tick {i} ok\n" for i in range(n)) + "ERROR boom\n"


def call(fn, data):
    """Run one hook handler; return the JSON it emitted, or None if it stayed silent."""
    out = support.capture(fn, data)
    return json.loads(out) if out else None


def bash(command, stdout="", stderr="", **extra):
    response = {"stdout": stdout, "stderr": stderr, "interrupted": False, "isImage": False}
    response.update(extra)
    return {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": response}


def updated(result):
    return result["hookSpecificOutput"]["updatedToolOutput"]


class Bash(unittest.TestCase):
    def test_large_log_output_is_replaced_and_other_fields_are_kept(self):
        result = call(hook.on_bash, bash("cat app.log", log_text(), exitCode=0))
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        new = updated(result)
        self.assertTrue(new["stdout"].startswith("[lembas squeeze: log"))
        self.assertEqual({k: new[k] for k in ("stderr", "interrupted", "isImage", "exitCode")},
                         {"stderr": "", "interrupted": False, "isImage": False, "exitCode": 0})

    def test_small_output_is_left_alone(self):
        self.assertIsNone(call(hook.on_bash, bash("ls", "a\nb\n")))
        self.assertIsNone(call(hook.on_bash, bash("true", "")))

    def test_large_standard_error_is_squeezed_on_its_own(self):
        new = updated(call(hook.on_bash, bash("make", "done\n", log_text())))
        self.assertEqual(new["stdout"], "done\n")
        self.assertTrue(new["stderr"].startswith("[lembas squeeze: log"))

    def test_raw_prefix_and_squeeze_itself_are_never_touched(self):
        self.assertIsNone(call(hook.on_bash, bash("LEMBAS_RAW=1 cat app.log", log_text())))
        self.assertIsNone(call(hook.on_bash, bash("cat app.log | python3 scripts/squeeze.py", log_text())))

    def test_a_narrowing_command_is_left_alone_while_its_output_fits_inline(self):
        mid = log_text(600)                       # over the normal threshold, under 30,000 characters
        self.assertLess(len(mid), hook.INLINE_LIMIT)
        self.assertIsNone(call(hook.on_bash, bash("grep -n tick app.log", mid)))
        self.assertIsNotNone(call(hook.on_bash, bash("cat app.log", mid)))

    def test_a_narrowing_command_is_squeezed_once_its_output_is_too_big_to_show(self):
        self.assertGreater(len(log_text()), hook.INLINE_LIMIT)
        self.assertIsNotNone(call(hook.on_bash, bash("grep -n tick app.log", log_text())))

    def test_saved_output_file_is_summarised_instead_of_the_preview(self):
        saved = support.write(support.tmp("hook", "saved-output.txt"), log_text())
        result = call(hook.on_bash, bash("cat app.log", "truncated preview\n", persistedOutputPath=saved))
        stdout = updated(result)["stdout"]
        self.assertIn("4,001 lines", stdout)
        self.assertIn(f"Full original: {saved} ;", stdout)

    def test_missing_saved_output_file_falls_back_to_the_inline_text(self):
        result = call(hook.on_bash, bash("cat app.log", log_text(), persistedOutputPath="/nonexistent/output.txt"))
        self.assertIn("4,001 lines", updated(result)["stdout"])

    def test_images_and_unexpected_shapes_are_ignored(self):
        self.assertIsNone(call(hook.on_bash, bash("screenshot", log_text(), isImage=True)))
        for response in (None, "a string", ["a", "list"]):
            self.assertIsNone(call(hook.on_bash, {"tool_input": {"command": "x"}, "tool_response": response}))

    def test_missing_fields_are_tolerated(self):
        self.assertIsNotNone(call(hook.on_bash, {"tool_response": {"stdout": log_text()}}))
        self.assertIsNone(call(hook.on_bash, {"tool_input": None, "tool_response": {"stdout": None, "stderr": None}}))
        self.assertIsNone(call(hook.on_bash, {}))


class Narrowing(unittest.TestCase):
    def test_commands_that_narrow_their_output(self):
        for cmd in ["grep -n error app.log", "cat app.log | head -50", "sed -n '10,20p' f", "jq '.items[]' f.json",
                    "cat f | awk '{print $1}'", "rg TODO src", "(tail -5 f)", "ls; wc -l f", "cmd && cut -f1 f"]:
            self.assertTrue(hook.NARROWING.search(cmd), cmd)

    def test_commands_that_do_not(self):
        for cmd in ["cat app.log", "npm test", "pytest -q", "python3 build.py", "make all", "curl -s http://x/y"]:
            self.assertFalse(hook.NARROWING.search(cmd), cmd)


class ReadText(unittest.TestCase):
    def test_reads_at_most_the_limit_and_tolerates_bad_bytes(self):
        path = support.tmp("hook", "bytes.bin")
        with open(path, "wb") as fh:
            fh.write(b"abcdef\xff\xfe")
        self.assertEqual(hook.read_text(path, 3), "abc")
        self.assertEqual(hook.read_text(path), "abcdef��")


def read_event(event, path, content=None, **tool_input):
    data = {"hook_event_name": event, "tool_name": "Read", "tool_input": dict(file_path=path, **tool_input)}
    if content is not None:
        lines = content.count("\n")
        data["tool_response"] = {"type": "text", "file": {"filePath": path, "content": content, "numLines": lines,
                                                           "startLine": 1, "totalLines": lines}}
    return data


class ReadPost(unittest.TestCase):
    CSV = "id,region,units\n" + "".join(f"{i},{'north' if i % 2 else 'south'},{i % 9}\n" for i in range(4000))

    def test_slice_detection(self):
        self.assertFalse(hook._is_slice({}))
        self.assertFalse(hook._is_slice({"file_path": "x", "offset": 0}))
        for key in ("offset", "limit", "pages"):
            self.assertTrue(hook._is_slice({key: 5 if key != "pages" else "1-2"}), key)

    def test_large_data_file_content_is_replaced(self):
        event = read_event("PostToolUse", "/data/sales.csv", self.CSV)
        f = updated(call(hook.on_read_post, event))["file"]
        self.assertTrue(f["content"].startswith("[lembas squeeze: csv, 4,000 rows"))
        self.assertIn("Full original: /data/sales.csv ;", f["content"])
        lines = f["content"].count("\n") + 1
        self.assertEqual((f["numLines"], f["totalLines"], f["startLine"]), (lines, lines, 1))
        self.assertEqual(f["filePath"], "/data/sales.csv")

    def test_the_event_passed_in_is_not_modified(self):
        event = read_event("PostToolUse", "/data/sales.csv", self.CSV)
        call(hook.on_read_post, event)
        self.assertEqual(event["tool_response"]["file"]["content"], self.CSV)

    def test_reads_that_ask_for_exact_lines_are_left_alone(self):
        for extra in ({"offset": 10}, {"limit": 50}, {"pages": "1-3"}):
            self.assertIsNone(call(hook.on_read_post, read_event("PostToolUse", "/d/s.csv", self.CSV, **extra)))

    def test_only_data_file_types_are_squeezed(self):
        for path in ("/src/app.py", "/docs/readme.md", "/data/noext", "/data/archive.txt"):
            self.assertIsNone(call(hook.on_read_post, read_event("PostToolUse", path, self.CSV)), path)
        for path in ("/d/a.CSV", "/d/a.tsv", "/d/a.log", "/d/a.out"):
            self.assertIsNotNone(call(hook.on_read_post, read_event("PostToolUse", path, self.CSV)), path)

    def test_small_files_and_other_result_shapes_are_left_alone(self):
        self.assertIsNone(call(hook.on_read_post, read_event("PostToolUse", "/d/s.csv", "a,b\n1,2\n")))
        image = {"tool_input": {"file_path": "/d/s.csv"}, "tool_response": {"type": "image", "file": {}}}
        self.assertIsNone(call(hook.on_read_post, image))
        self.assertIsNone(call(hook.on_read_post, {"tool_input": {"file_path": "/d/s.csv"}, "tool_response": None}))
        self.assertIsNone(call(hook.on_read_post, {"tool_input": {"file_path": "/d/s.csv"},
                                                    "tool_response": {"type": "text"}}))

    def test_path_can_come_from_the_request_when_the_result_has_none(self):
        event = read_event("PostToolUse", "/data/sales.csv", self.CSV)
        del event["tool_response"]["file"]["filePath"]
        self.assertIsNotNone(call(hook.on_read_post, event))


class ReadPre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.big = support.write(support.tmp("hook", "big.log"), log_text(9000))
        cls.small = support.write(support.tmp("hook", "small.log"), log_text(50))
        assert os.path.getsize(cls.big) > hook.READ_LIMIT

    def test_oversized_data_file_is_declined_with_a_summary(self):
        result = call(hook.on_read_pre, read_event("PreToolUse", self.big))
        out = result["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        reason = out["permissionDecisionReason"]
        self.assertRegex(reason, r"^This file is 0\.\d MB, over the Read tool's 256 KB limit")
        self.assertIn(self.big, reason)
        self.assertIn("[lembas squeeze: log, 9,001 lines", reason)

    def test_files_within_the_limit_are_allowed(self):
        self.assertIsNone(call(hook.on_read_pre, read_event("PreToolUse", self.small)))

    def test_missing_files_slices_and_other_types_are_allowed(self):
        self.assertIsNone(call(hook.on_read_pre, read_event("PreToolUse", "/nonexistent/x.log")))
        self.assertIsNone(call(hook.on_read_pre, read_event("PreToolUse", self.big, offset=100, limit=50)))
        big_py = support.write(support.tmp("hook", "big.py"), log_text(9000))
        self.assertIsNone(call(hook.on_read_pre, read_event("PreToolUse", big_py)))
        self.assertIsNone(call(hook.on_read_pre, {"tool_input": {}}))


class Main(unittest.TestCase):
    def run_main(self, stdin="", argv=(), env=None):
        """Call main() with the given stdin; return (exit code, parsed stdout or None, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["squeeze_hook.py", *argv]), mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err), \
                mock.patch.dict(os.environ, env or {}):
            code = hook.main()
        text = out.getvalue()
        return code, (json.loads(text) if text else None), err.getvalue()

    def test_routes_each_event_to_its_handler(self):
        code, result, _ = self.run_main(json.dumps(bash("cat app.log", log_text())))
        self.assertEqual(code, 0)
        self.assertIn("updatedToolOutput", result["hookSpecificOutput"])
        content = "a,b\n" + "1,2\n" * 5000
        _, result, _ = self.run_main(json.dumps(read_event("PostToolUse", "/d/x.csv", content)))
        self.assertTrue(updated(result)["file"]["content"].startswith("[lembas squeeze: csv"))
        big = support.write(support.tmp("hook", "main-big.log"), log_text(9000))
        _, result, _ = self.run_main(json.dumps(read_event("PreToolUse", big)))
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_other_tools_and_events_are_ignored(self):
        for event, tool in [("PostToolUse", "Write"), ("PreToolUse", "Bash"), ("Stop", None), (None, None)]:
            data = dict(bash("cat app.log", log_text()), hook_event_name=event, tool_name=tool)
            self.assertEqual(self.run_main(json.dumps(data)), (0, None, ""), (event, tool))

    def test_switched_off_by_environment_variable(self):
        payload = json.dumps(bash("cat app.log", log_text()))
        self.assertEqual(self.run_main(payload, env={"LEMBAS_SQUEEZE": "0"}), (0, None, ""))
        self.assertIsNotNone(self.run_main(payload, env={"LEMBAS_SQUEEZE": "1"})[1])

    def test_bad_input_is_reported_and_never_fails_the_tool_call(self):
        for stdin in ("not json", "", "[1, 2, 3]", '"a string"', "null"):
            code, result, err = self.run_main(stdin)
            self.assertEqual((code, result), (0, None), stdin)
            self.assertIn("lembas squeeze hook skipped", err, stdin)

    def test_print_settings_gives_json_that_registers_both_events(self):
        code, settings, _ = self.run_main(argv=["--print-settings"])
        self.assertEqual(code, 0)
        hooks = settings["hooks"]
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Read")
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Bash|Read")
        for event in ("PreToolUse", "PostToolUse"):
            entry = hooks[event][0]["hooks"][0]
            self.assertEqual(entry, {"type": "command", "command": f'python3 "{support.HOOK_PY}"'})


class Environment(unittest.TestCase):
    """Settings read from the environment, checked through a real subprocess."""

    def run_hook(self, payload, **env):
        r = support.run_py(support.HOOK_PY, data=json.dumps(payload), env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_threshold_and_budget_can_be_changed(self):
        modest = log_text(150)                    # about 1,700 tokens: under the default threshold
        self.assertIsNone(self.run_hook(bash("cat app.log", modest)))
        result = self.run_hook(bash("cat app.log", modest), LEMBAS_SQUEEZE_THRESHOLD="100")
        self.assertTrue(updated(result)["stdout"].startswith("[lembas squeeze: log"))
        roomy = updated(self.run_hook(bash("cat app.log", log_text())))["stdout"]
        tight = updated(self.run_hook(bash("cat app.log", log_text()), LEMBAS_SQUEEZE_BUDGET="150"))["stdout"]
        self.assertLess(len(tight), len(roomy))

    def test_the_command_printed_by_print_settings_runs_the_hook(self):
        r = support.run_py(support.HOOK_PY, "--print-settings")
        command = json.loads(r.stdout)["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        self.assertTrue(command.startswith('python3 "') and command.endswith('"'))
        script = command[len('python3 "'):-1]
        self.assertTrue(os.path.samefile(script, support.HOOK_PY))
        r = support.run_py(script, data=json.dumps(bash("cat app.log", log_text())))
        self.assertIn("updatedToolOutput", r.stdout.decode())


if __name__ == "__main__":
    unittest.main(verbosity=1)
