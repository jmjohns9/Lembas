#!/usr/bin/env python3
"""Tests for the benchmark tooling in evals/. Run: python3 tests/test_evals.py

The runners start Claude Code with `claude -p`, which needs the CLI and a paid account. Here that
one call (subprocess.run) is replaced with a stand-in that returns a canned JSON result, so the
tests are fast, repeatable and need no API key. Everything around the call is real: argument
building, the work folder and its settings file, usage accounting, grading and the output files.

The task checks are also tested against the fixture generators, so a change to a fixture that
would silently break a benchmark grader fails here instead.
"""
import io
import json
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import ithildin_fixtures  # noqa: E402

EVALS_DIR = os.path.join(support.ROOT, "evals")
gen = support.load_script("generate_replies", os.path.join(EVALS_DIR, "generate_replies.py"))
sq_bench = support.load_script("squeeze_bench", os.path.join(EVALS_DIR, "squeeze-bench", "run_e2e.py"))
ith_bench = support.load_script("ithildin_bench", os.path.join(EVALS_DIR, "ithildin-bench", "run_e2e.py"))

USAGE = {"input_tokens": 10, "cache_creation_input_tokens": 200, "cache_read_input_tokens": 3000, "output_tokens": 55}


def claude_result(result="An answer.", **extra):
    payload = {"result": result, "usage": USAGE, "total_cost_usd": 0.0123, "num_turns": 3}
    payload.update(extra)
    return types.SimpleNamespace(stdout=json.dumps(payload), stderr="", returncode=0)


def run_main(module, *argv):
    out = io.StringIO()
    with mock.patch.object(sys, "argv", ["prog", *argv]), mock.patch.object(sys, "stdout", out):
        module.main()
    return out.getvalue()


PROBLEM_EV = {"id": 7, "name": "demo", "category": "safety", "prompt": "How do I do it safely?",
              "must_contain": ["pg_dump", "RENAME"]}
GOOD = ("**Problem.** The table is live.\n\n**Fix.** Run pg_dump, then RENAME inside a transaction.\n\n"
        "**Alternatives.** Use a view if downtime is not allowed.\n\n**Why this fix.** It is reversible.")


class GenerateRepliesGrade(unittest.TestCase):
    def expectations(self, text, ev=PROBLEM_EV):
        return {e["text"]: e for e in gen.grade(ev, text)["expectations"]}

    def test_a_good_reply_passes_every_expectation(self):
        g = gen.grade(PROBLEM_EV, GOOD)
        self.assertEqual(g["summary"], {"passed": 7, "failed": 0, "total": 7, "pass_rate": 1.0})

    def test_each_expectation_carries_evidence(self):
        exp = self.expectations(GOOD)
        self.assertEqual(exp["Keeps key fact: pg_dump"]["evidence"], "pg_dump")
        self.assertEqual(exp["No em or en dashes"]["evidence"], "dash count 0")
        self.assertEqual(exp["Has Problem, Fix, Alternatives and Why parts"]["evidence"],
                         "Problem: yes, Fix: yes, Alternatives: yes, Why: yes")

    def test_openers_closers_and_dashes(self):
        for opener in ["Great question! ", "Sure, ", "Certainly: ", "Of course. ", "I'd be happy to help. ", "Let me explain. "]:
            self.assertFalse(self.expectations(opener + GOOD)["Opens with the answer, no greeting or praise"]["passed"], opener)
        for closer in ["Let me know if that works.", "Hope this helps!", "Feel free to ask.", "Any other questions?"]:
            self.assertFalse(self.expectations(GOOD + "\n\n" + closer)["No closing offer of further help"]["passed"], closer)
        dashes = self.expectations(GOOD + " One — two – three.")["No em or en dashes"]
        self.assertEqual((dashes["passed"], dashes["evidence"]), (False, "dash count 2"))

    def test_missing_fact_and_missing_part_lower_the_pass_rate(self):
        g = gen.grade(PROBLEM_EV, GOOD.replace("pg_dump", "a backup").replace("**Fix.**", "Fix:"))
        self.assertEqual((g["summary"]["passed"], g["summary"]["failed"]), (5, 2))
        self.assertEqual(g["summary"]["pass_rate"], round(5 / 7, 3))

    def test_alternatives_must_say_when_they_win(self):
        text = GOOD.replace("Use a view if downtime is not allowed.", "You could also use a view.")
        alt = self.expectations(text)["Each alternative says when it wins"]
        self.assertEqual((alt["passed"], alt["evidence"]), (False, "You could also use a view."))
        missing = self.expectations("Just run pg_dump and RENAME it.")["Each alternative says when it wins"]
        self.assertEqual((missing["passed"], missing["evidence"]), (False, "no Alternatives section"))

    def test_concept_prompts_are_not_asked_for_the_four_parts(self):
        g = gen.grade(dict(PROBLEM_EV, category="concept"), "pg_dump copies it; RENAME swaps it.")
        self.assertEqual(g["summary"]["total"], 5)
        self.assertEqual(gen.grade({"category": "code"}, "x = 1")["summary"]["total"], 3)

    def test_body_drops_the_frontmatter(self):
        with_front = support.write(support.tmp("evals", "skill.md"), "---\nname: x\ndescription: y\n---\n\n# Title\n\nRules.\n")
        without = support.write(support.tmp("evals", "plain.md"), "# Title\n\nRules.\n")
        self.assertEqual(gen.body(with_front), "# Title\n\nRules.")
        self.assertEqual(gen.body(without), "# Title\n\nRules.\n")


class GenerateRepliesRun(unittest.TestCase):
    def test_call_builds_the_command_and_reads_the_result(self):
        with mock.patch.object(gen.subprocess, "run", return_value=claude_result("Hello.")) as run:
            text, tokens, seconds = gen.call("What is X?", "Be brief.")
        args, kwargs = run.call_args
        cmd = args[0]
        self.assertEqual(cmd[:2], ["claude", "-p"])
        self.assertEqual(cmd[cmd.index("--model") + 1], gen.MODEL)
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "Be brief.")
        self.assertEqual(cmd[-1], "What is X?")
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual((text, tokens), ("Hello.", 55))
        self.assertGreaterEqual(seconds, 0)

    def test_call_without_a_system_prompt_leaves_the_flag_out(self):
        with mock.patch.object(gen.subprocess, "run", return_value=claude_result()) as run:
            gen.call("What is X?", None)
        self.assertNotIn("--system-prompt", run.call_args[0][0])

    def test_call_runs_in_a_fresh_empty_folder(self):
        seen = []
        with mock.patch.object(gen.subprocess, "run", side_effect=lambda cmd, **kw: seen.append(
                (kw["cwd"], os.listdir(kw["cwd"]))) or claude_result()):
            gen.call("p", None)
            gen.call("p", None)
        self.assertEqual([files for _, files in seen], [[], []])
        self.assertNotEqual(seen[0][0], seen[1][0])
        self.assertFalse(os.path.exists(seen[0][0]), "the folder is removed afterwards")

    def test_main_writes_a_reply_timing_and_grade_for_every_arm(self):
        evals = support.write(support.tmp("evals", "gen", "evals.json"), json.dumps({"evals": [
            PROBLEM_EV, {"id": 8, "name": "second", "category": "code", "prompt": "Write it.", "must_contain": ["def "]}]}))
        skill = support.write(support.tmp("evals", "gen", "SKILL.md"), "---\nname: s\n---\nNew rules.")
        old = support.write(support.tmp("evals", "gen", "OLD.md"), "Old rules.")
        out_dir = support.tmp("evals", "gen", "out", "x")[:-2]
        systems = []

        def fake_call(prompt, system):
            systems.append(system)
            return (GOOD if system == "New rules." else "def f(): pass"), 42, 1.5

        with mock.patch.object(gen, "call", side_effect=fake_call):
            printed = run_main(gen, out_dir, "--skill", skill, "--old-skill", old, "--evals", evals, "--workers", "2")
        self.assertEqual(sorted(set(map(str, systems))), ["New rules.", "None", "Old rules."])
        self.assertEqual(len(printed.strip().split("\n")), 6, "2 evals x 3 arms")
        for name in ("demo", "second"):
            meta = json.loads(support.read(os.path.join(out_dir, name, "eval_metadata.json")))
            self.assertEqual(meta["eval_name"], name)
            for arm in ("with_skill", "old_skill", "without_skill"):
                base = os.path.join(out_dir, name, arm)
                self.assertTrue(os.path.isfile(os.path.join(base, "outputs", "response.md")))
                self.assertEqual(json.loads(support.read(os.path.join(base, "timing.json"))),
                                 {"total_tokens": 42, "duration_ms": 1500, "total_duration_seconds": 1.5})
        graded = json.loads(support.read(os.path.join(out_dir, "demo", "with_skill", "grading.json")))
        self.assertEqual(graded["summary"]["pass_rate"], 1.0)
        self.assertEqual(support.read(os.path.join(out_dir, "demo", "with_skill", "outputs", "response.md")), GOOD)

    def test_the_repo_eval_file_is_well_formed(self):
        data = json.loads(support.read(os.path.join(EVALS_DIR, "evals.json")))
        evs = data["evals"]
        self.assertEqual(len(evs), 11)
        self.assertEqual(len({e["id"] for e in evs}), 11)
        self.assertEqual(len({e["name"] for e in evs}), 11)
        for e in evs:
            self.assertTrue({"id", "name", "category", "prompt", "expected_output", "must_contain"} <= set(e), e["name"])
            self.assertTrue(e["must_contain"], e["name"])
            for pattern in e["must_contain"]:
                gen.re.compile(pattern)
            self.assertTrue(os.path.isfile(os.path.join(EVALS_DIR, "results", "v2.0.0", e["name"], "lembas.md")), e["name"])


def by_id(tasks):
    return {t["id"]: t for t in tasks}


class SqueezeBenchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = support.squeeze_fixtures()
        cls.answers = json.loads(support.read(os.path.join(cls.fixtures, "answers.json")))
        cls.tasks = by_id(sq_bench.TASKS + sq_bench.TASKS_MID)

    def test_all_of_needs_every_pattern(self):
        check = sq_bench.all_of(r"alpha", r"be+ta")
        self.assertTrue(check("ALPHA and\nbeeeta"))
        self.assertFalse(check("alpha only"))
        self.assertFalse(check(""))

    def test_task_ids_are_unique_and_every_task_has_what_the_runner_needs(self):
        self.assertEqual(len(self.tasks), len(sq_bench.TASKS) + len(sq_bench.TASKS_MID))
        for task in self.tasks.values():
            self.assertEqual(set(task), {"id", "file", "prompt", "check"})
            self.assertFalse(task["check"](""), task["id"])

    def test_generated_fixtures_exist_for_every_task_except_the_two_real_logs(self):
        missing = {t["file"] for t in self.tasks.values() if not os.path.exists(os.path.join(self.fixtures, t["file"]))}
        self.assertEqual(missing, {"real-npm-install.log", "real-dpkg.log"})

    def test_incident_check_agrees_with_the_generated_log(self):
        log = self.answers["app.log"]
        answer = (f"The first error is at line {log['traceback_line']:,}: KeyError 'customer_id' in payments/settle.py, "
                  f"line 142. After it, {log['redis_connection_errors']} redis connection errors to {log['redis_host']}.")
        self.assertTrue(self.tasks["incident-log"]["check"](answer), answer)
        self.assertFalse(self.tasks["incident-log"]["check"](answer.replace("customer_id", "order_id")))
        mid = f"KeyError customer_id at settle.py line 142, then {log['redis_connection_errors']} redis errors."
        self.assertTrue(self.tasks["mid-incident-log"]["check"](mid))

    def test_failed_orders_check_agrees_with_the_generated_orders(self):
        failed = self.answers["orders.json"]["failed_orders"]
        answer = "; ".join(f"{order} failed with {code.replace('_', ' ')}" for order, code in failed.items())
        for task in ("failed-orders", "api-failures"):
            self.assertTrue(self.tasks[task]["check"](answer), answer)
            self.assertFalse(self.tasks[task]["check"](answer.replace("ord_100402", "ord_999999")))
        first_two = "; ".join(f"{order}: {code}" for order, code in list(failed.items())[:2])
        self.assertEqual(self.answers["mid"]["orders_failed"], list(failed)[:2])
        self.assertTrue(self.tasks["mid-failed-orders"]["check"](first_two))

    def test_sales_checks_agree_with_the_generated_csv(self):
        sales = self.answers["sales.csv"]
        answer = (f"Total revenue is {sales['revenue_total']:,.2f}. One row has revenue 987,654.32, a shifted decimal, "
                  f"and {sales['null_reps']} rows have no rep.")
        self.assertTrue(self.tasks["sales-total"]["check"](answer), answer)
        self.assertFalse(self.tasks["sales-total"]["check"](answer.replace(f"{sales['revenue_total']:,.2f}", "1.00")))
        mid = self.answers["mid"]
        answer = f"Total revenue is {mid['sales_total']:,.2f}; {mid['sales_null_reps']} rows have a blank rep."
        self.assertTrue(self.tasks["mid-sales-total"]["check"](answer), answer)

    def test_event_and_test_failure_checks_agree_with_their_fixtures(self):
        events = self.answers["events.jsonl"]
        answer = f"Two server errors, events {events['error_events'][0]} and {events['error_events'][1]}: {events['error_message']}."
        self.assertTrue(self.tasks["event-errors"]["check"](answer), answer)
        failed = self.answers["run_tests.py"]["failed"]
        answer = (f"{failed[0]}: expected 23.79 but got 23.78. {failed[1]}: max delay 640 > 300. "
                  f"{failed[2]}: got 500, KeyError 'kid'.")
        self.assertTrue(self.tasks["test-failures"]["check"](answer), answer)

    def test_real_log_checks_on_sample_answers(self):
        self.assertTrue(self.tasks["dpkg-failures"]["check"]("No packages failed to install. The last install was 2026-10-07."))
        self.assertFalse(self.tasks["dpkg-failures"]["check"]("Several packages were installed on 2026-10-07."))
        npm = "Deprecated: acorn-import-assertions, har-validator, uuid, left-pad and request@2.88. The install succeeded."
        self.assertTrue(self.tasks["npm-deprecations"]["check"](npm))


class SqueezeBenchRun(unittest.TestCase):
    TASK = {"id": "incident-log", "file": "app.log", "prompt": "What happened?", "check": lambda t: "customer_id" in t}

    def run_one(self, arm, result=None, side_effect=None):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(cmd=cmd, kw=kw, files=sorted(os.listdir(kw["cwd"])),
                        settings=json.loads(support.read(os.path.join(kw["cwd"], ".claude", "settings.json"))))
            if side_effect:
                raise side_effect
            return result or claude_result("KeyError: customer_id")

        with mock.patch.object(sq_bench.subprocess, "run", side_effect=fake_run):
            row = sq_bench.run_one(self.TASK, arm, 0, support.squeeze_fixtures())
        return row, seen

    def test_default_arm_runs_plain_claude_code_on_a_copy_of_the_file(self):
        row, seen = self.run_one("default")
        self.assertEqual(seen["files"], [".claude", "app.log"])
        self.assertEqual(seen["settings"], {})
        self.assertNotIn("--append-system-prompt", seen["cmd"])
        self.assertIn("--allowedTools=Bash,Read,Grep,Glob", seen["cmd"])
        self.assertEqual(seen["cmd"][-1], "What happened?")
        self.assertEqual(seen["kw"]["env"]["LEMBAS_SQUEEZE_DIR"], os.path.join(seen["kw"]["cwd"], ".squeeze-cache"))
        self.assertFalse(os.path.exists(seen["kw"]["cwd"]), "the work folder is removed after a successful run")
        self.assertEqual({k: row[k] for k in ("task", "arm", "rep", "input_tokens", "cache_write", "cache_read",
                                              "total_input", "output_tokens", "cost_usd", "turns", "correct", "answer")},
                         {"task": "incident-log", "arm": "default", "rep": 0, "input_tokens": 10, "cache_write": 200,
                          "cache_read": 3000, "total_input": 3210, "output_tokens": 55, "cost_usd": 0.0123, "turns": 3,
                          "correct": True, "answer": "KeyError: customer_id"})

    def test_hook_arm_installs_the_hook_for_both_events(self):
        _, seen = self.run_one("hook")
        command = f'python3 "{support.HOOK_PY}"'
        self.assertEqual(seen["settings"]["hooks"]["PreToolUse"], [{"matcher": "Read", "hooks": [{"type": "command", "command": command}]}])
        self.assertEqual(seen["settings"]["hooks"]["PostToolUse"][0]["matcher"], "Bash|Read")
        self.assertNotIn("--append-system-prompt", seen["cmd"])

    def test_skill_arms_append_the_skill_text_with_an_absolute_script_path(self):
        _, seen = self.run_one("skill+hook")
        prompt = seen["cmd"][seen["cmd"].index("--append-system-prompt") + 1]
        self.assertTrue(prompt.lstrip().startswith("# Lembas"))
        self.assertNotIn("\nname: lembas", prompt)
        self.assertIn(support.SQUEEZE_PY, prompt)
        self.assertIn("hooks", seen["settings"])

    def test_wrong_answer_is_marked_incorrect(self):
        row, _ = self.run_one("default", claude_result("I could not find anything."))
        self.assertFalse(row["correct"])
        row, _ = self.run_one("default", claude_result(None))
        self.assertEqual((row["correct"], row["answer"]), (False, ""))

    def test_a_failed_run_is_recorded_not_raised(self):
        row, _ = self.run_one("default", side_effect=subprocess.TimeoutExpired("claude", 900))
        self.assertEqual(set(row), {"task", "arm", "rep", "error"})
        self.assertIn("TimeoutExpired", row["error"])
        row, _ = self.run_one("default", types.SimpleNamespace(stdout="not json", stderr="", returncode=1))
        self.assertIn("JSONDecodeError", row["error"])

    def test_main_runs_every_combination_and_saves_the_results(self):
        out = support.tmp("evals", "sq-bench", "out.json")
        calls = []

        def fake_run_one(task, arm, rep, fixtures):
            calls.append((task["id"], arm, rep))
            return {"task": task["id"], "arm": arm, "rep": rep, "total_input": 1, "cost_usd": 0.1, "turns": 1, "correct": True}

        with mock.patch.object(sq_bench, "run_one", side_effect=fake_run_one):
            printed = run_main(sq_bench, "/fixtures", out, "--reps", "2", "--workers", "1", "--arms", "default,skill",
                               "--tasks", "incident-log,sales-total")
        self.assertEqual(len(calls), 8, "2 tasks x 2 arms x 2 reps")
        self.assertEqual(len(json.loads(support.read(out))), 8)
        self.assertTrue(printed.strip().endswith(f"wrote {out}"))
        calls.clear()
        with mock.patch.object(sq_bench, "run_one", side_effect=fake_run_one):
            run_main(sq_bench, "/fixtures", out, "--reps", "1", "--workers", "1", "--arms", "hook", "--suite", "mid")
        self.assertEqual([c[0] for c in calls], ["mid-incident-log", "mid-failed-orders", "mid-sales-total"])


class IthildinBench(unittest.TestCase):
    def test_manual_task_checks_agree_with_the_planted_facts(self):
        planted = ithildin_fixtures.PLANTED
        tasks = by_id(ith_bench.TASKS)
        limits = (f"The maximum coolant outlet temperature is {planted['coolant_max']['answer']}. The warranty is void above "
                  f"{planted['altitude_void']['answer']} without the high-altitude kit, or with non-approved coolant.")
        self.assertTrue(tasks["manual-limits-warranty"]["check"](limits), limits)
        self.assertFalse(tasks["manual-limits-warranty"]["check"](limits.replace("104", "140")))
        torque = f"Cylinder head bolts take {planted['head_bolt_torque']['answer']} in a spiral, 3 passes."
        self.assertTrue(tasks["manual-torque-table"]["check"](torque), torque)
        parts = (f"The oil filter is {planted['oil_filter_pn']['answer']}. A service interval is "
                 f"{planted['service_interval']['answer']} or twelve months.")
        self.assertTrue(tasks["manual-docx-parts"]["check"](parts), parts)
        for task in tasks.values():
            self.assertFalse(task["check"](""), task["id"])

    def test_the_planted_facts_are_really_in_the_generated_manual(self):
        text = " ".join(b[1] for b in ithildin_fixtures.build_model() if b[0] == "p")
        for key in ("coolant_max", "altitude_void", "service_interval"):
            self.assertIn(ithildin_fixtures.PLANTED[key]["needle"], text, key)

    def test_ithildin_arm_appends_the_skill_and_default_arm_does_not(self):
        docs = support.manual_docs()
        task = {"id": "t", "file": "manual.md", "prompt": "Q?", "check": lambda t: "104" in t}
        seen = []

        def fake_run(cmd, **kw):
            seen.append((cmd, kw, sorted(os.listdir(kw["cwd"]))))
            return claude_result("It is 104.")

        with mock.patch.object(ith_bench.subprocess, "run", side_effect=fake_run):
            rows = [ith_bench.run_one(task, arm, 1, os.path.dirname(docs["manual.md"])) for arm in ("default", "ithildin")]
        (plain, _, files), (skilled, kw, _) = seen
        self.assertEqual(files, [".claude", "manual.md"])
        self.assertNotIn("--append-system-prompt", plain)
        prompt = skilled[skilled.index("--append-system-prompt") + 1]
        self.assertTrue(prompt.lstrip().startswith("# Ithildin"))
        self.assertIn(support.ITHILDIN_PY, prompt)
        self.assertEqual(kw["env"]["ITHILDIN_CACHE"], os.path.join(kw["cwd"], ".ithildin-cache"))
        self.assertEqual([(r["arm"], r["correct"], r["total_input"], r["rep"]) for r in rows],
                         [("default", True, 3210, 1), ("ithildin", True, 3210, 1)])

    def test_the_work_folder_is_removed_even_when_the_run_fails(self):
        docs = support.manual_docs()
        task = {"id": "t", "file": "manual.md", "prompt": "Q?", "check": bool}
        folders = []

        def fake_run(cmd, **kw):
            folders.append(kw["cwd"])
            raise subprocess.TimeoutExpired("claude", 900)

        with mock.patch.object(ith_bench.subprocess, "run", side_effect=fake_run):
            row = ith_bench.run_one(task, "default", 0, os.path.dirname(docs["manual.md"]))
        self.assertIn("TimeoutExpired", row["error"])
        self.assertFalse(os.path.exists(folders[0]))

    def test_main_filters_tasks_and_saves_the_results(self):
        out = support.tmp("evals", "ith-bench", "out.json")
        with mock.patch.object(ith_bench, "run_one", side_effect=lambda t, arm, rep, docs: {"task": t["id"], "arm": arm, "rep": rep}):
            printed = run_main(ith_bench, "/docs", out, "--reps", "1", "--workers", "1", "--tasks", "rust-errors")
        self.assertEqual(json.loads(support.read(out)), [{"task": "rust-errors", "arm": "default", "rep": 0},
                                                         {"task": "rust-errors", "arm": "ithildin", "rep": 0}])
        self.assertIn(f"wrote {out}", printed)


if __name__ == "__main__":
    unittest.main(verbosity=1)
