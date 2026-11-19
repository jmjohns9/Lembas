#!/usr/bin/env python3
"""Tests for scripts/: count_tokens.py, grade.py and package.sh. Run: python3 tests/test_scripts.py

count_tokens.py and grade.py are CI gates, so they are tested both on small made-up results and on
the results committed in evals/results/v2.0.0.
"""
import io
import json
import os
import shutil
import sys
import types
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

count_tokens = support.load_script("count_tokens", os.path.join(support.ROOT, "scripts", "count_tokens.py"))
grade = support.load_script("grade", os.path.join(support.ROOT, "scripts", "grade.py"))
EVALS = os.path.join(support.ROOT, "evals", "evals.json")
RESULTS = os.path.join(support.ROOT, "evals", "results", "v2.0.0")


def results_dir(name, replies):
    """Build <tmp>/<name>/<eval>/<variant>.md from {eval: {variant: text}}; return the folder."""
    root = support.tmp("scripts", name, "x")[:-2]
    for ev, variants in replies.items():
        for variant, text in variants.items():
            support.write(support.tmp("scripts", name, ev, f"{variant}.md"), text)
    return root


def run_main(module, *argv):
    """Call a script's main() with argv; return (exit code, stdout)."""
    out = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", [module.__name__ + ".py", *argv]), mock.patch.object(sys, "stdout", out):
        try:
            module.main()
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


class CountTokens(unittest.TestCase):
    def test_default_counter_is_characters_divided_by_four(self):
        count = count_tokens.make_counter(False)
        self.assertEqual([count(""), count("abcd"), count("x" * 400), count("x" * 403)], [0, 1, 100, 101])

    def test_tiktoken_counter_uses_the_named_encoding(self):
        seen = []
        fake = types.SimpleNamespace(get_encoding=lambda name: seen.append(name) or types.SimpleNamespace(
            encode=lambda text: text.split()))
        with mock.patch.dict(sys.modules, {"tiktoken": fake}):
            count = count_tokens.make_counter(True)
        self.assertEqual(seen, ["cl100k_base"])
        self.assertEqual(count("three short words"), 3)

    def test_table_has_a_row_per_eval_and_a_total(self):
        folder = results_dir("count", {"alpha": {"baseline": "x" * 400, "lembas": "x" * 100},
                                       "beta": {"baseline": "x" * 800, "lembas": "x" * 600, "lembas-1.1": "ignored"}})
        support.write(os.path.join(folder, "notes.txt"), "a stray file, not an eval folder")
        code, out = run_main(count_tokens, folder)
        lines = out.strip().split("\n")
        self.assertEqual(code, 0)
        self.assertEqual(lines[0].split(), ["eval", "baseline", "lembas", "cut"])
        self.assertEqual([l.split() for l in lines[1:]], [["alpha", "100", "25", "75.0%"], ["beta", "200", "150", "25.0%"],
                                                          ["TOTAL", "300", "175", "41.7%"]])

    def test_a_longer_reply_shows_as_a_negative_cut(self):
        folder = results_dir("count-negative", {"alpha": {"baseline": "x" * 400, "lembas": "x" * 800}})
        self.assertIn("-100.0%", run_main(count_tokens, folder)[1])

    def test_committed_results_give_the_published_total(self):
        code, out = run_main(count_tokens, RESULTS)
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().split("\n")), 13, "a header, 11 evals and a total")
        self.assertRegex(out, r"(?m)^TOTAL\s+7655\s+3934\s+48\.6%$")


EV = {"name": "demo", "category": "troubleshooting", "must_contain": ["pg_dump", r"BEGIN\b"]}
GOOD = ("**Problem.** The table is live.\n\n**Fix.** Run pg_dump, then BEGIN a transaction.\n\n"
        "**Alternatives.** Use a view if you can wait.\n\n**Why this fix.** It is reversible.")


class GradeChecks(unittest.TestCase):
    def results(self, text, ev=EV, variant="lembas"):
        return {label: ok for _, label, ok in grade.checks(text, ev, variant)}

    def kinds(self, text, ev=EV, variant="lembas"):
        return {label: kind for kind, label, _ in grade.checks(text, ev, variant)}

    def test_a_good_reply_passes_everything(self):
        self.assertEqual(set(self.results(GOOD).values()), {True})
        self.assertEqual(len(self.results(GOOD)), 9, "3 style checks, 2 facts, 4 parts")

    def test_facts_and_structure_are_required_and_style_is_not(self):
        kinds = self.kinds(GOOD)
        self.assertEqual({k for k, v in kinds.items() if v == "style"},
                         {"opens with the answer", "no closing offer", "no em or en dashes"})
        self.assertEqual(sum(v == "required" for v in kinds.values()), 6)

    def test_greetings_and_praise_in_the_first_line_are_flagged(self):
        for opener in ["Sure, here is how.", "Great question!", "**Certainly.** Do this.", "# Hello there",
                       "Absolutely. Run it.", "hi! try this"]:
            self.assertFalse(self.results(opener + "\n" + GOOD)["opens with the answer"], opener)
        for opener in ["Run pg_dump first.", "**Problem.** It is live.", "The cause is a lock."]:
            self.assertTrue(self.results(opener + "\n" + GOOD)["opens with the answer"], opener)

    def test_an_offer_of_help_in_the_last_line_is_flagged(self):
        for closer in ["Let me know if you need more.", "Happy to explain further.", "Want me to write the script?",
                       "I can also add tests.", "Hope this helps!"]:
            self.assertFalse(self.results(GOOD + "\n\n" + closer)["no closing offer"], closer)
        self.assertTrue(self.results("Let me know what broke.\n" + GOOD)["no closing offer"], "only the last line counts")

    def test_dashes_are_flagged(self):
        self.assertFalse(self.results(GOOD + " It works — mostly.")["no em or en dashes"])
        self.assertFalse(self.results(GOOD + " Pages 3–5.")["no em or en dashes"])
        self.assertTrue(self.results(GOOD + " A hyphen-ated word is fine.")["no em or en dashes"])

    def test_required_facts_are_regexes_matched_without_case(self):
        results = self.results(GOOD.replace("pg_dump", "PG_DUMP").replace("BEGIN", "begin"))
        self.assertTrue(results["keeps /pg_dump/"])
        self.assertTrue(results[r"keeps /BEGIN\b/"])
        results = self.results(GOOD.replace("pg_dump", "a backup"))
        self.assertFalse(results["keeps /pg_dump/"])

    def test_the_four_parts_are_only_required_of_lembas_on_problem_prompts(self):
        self.assertFalse(self.results(GOOD.replace("**Alternatives.**", "Alternatives:"))["has the Alternatives part"])
        self.assertNotIn("has the Problem part", self.results(GOOD, variant="baseline"))
        for category in ("concept", "code", "writing", None):
            self.assertNotIn("has the Problem part", self.results(GOOD, dict(EV, category=category)))
        for category in grade.PROBLEM_CATEGORIES:
            self.assertIn("has the Problem part", self.results(GOOD, dict(EV, category=category)))

    def test_part_labels_may_carry_extra_words(self):
        text = GOOD.replace("**Why this fix.**", "**Why this fix wins:**")
        self.assertTrue(self.results(text)["has the Why part"])


class GradeMain(unittest.TestCase):
    def evals(self, name, evs):
        return support.write(support.tmp("scripts", name, "evals.json"), json.dumps({"evals": evs}))

    def test_passing_replies_exit_zero_and_print_totals(self):
        folder = results_dir("grade-pass", {"demo": {"baseline": "Run pg_dump and BEGIN.", "lembas": GOOD}})
        code, out = run_main(grade, self.evals("grade-pass", [EV]), folder)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().split("\n"), ["baseline 5/5 checks passed", "lembas   9/9 checks passed"])

    def test_a_lembas_reply_missing_a_fact_fails(self):
        folder = results_dir("grade-fact", {"demo": {"lembas": GOOD.replace("pg_dump", "a backup")}})
        code, out = run_main(grade, self.evals("grade-fact", [EV]), folder)
        self.assertEqual(code, 1)
        self.assertIn("FAIL lembas   demo: keeps /pg_dump/", out)

    def test_a_lembas_reply_missing_a_part_fails(self):
        folder = results_dir("grade-part", {"demo": {"lembas": GOOD.replace("**Fix.**", "Fix:")}})
        code, out = run_main(grade, self.evals("grade-part", [EV]), folder)
        self.assertEqual(code, 1)
        self.assertIn("FAIL lembas   demo: has the Fix part", out)

    def test_a_baseline_miss_is_reported_but_does_not_fail(self):
        folder = results_dir("grade-base", {"demo": {"baseline": "No facts here.", "lembas": GOOD}})
        code, out = run_main(grade, self.evals("grade-base", [EV]), folder)
        self.assertEqual(code, 0)
        self.assertIn("FAIL baseline demo: keeps /pg_dump/", out)

    def test_style_misses_are_warnings(self):
        folder = results_dir("grade-style", {"demo": {"lembas": "Sure thing.\n" + GOOD + "\n\nHope this helps!"}})
        code, out = run_main(grade, self.evals("grade-style", [EV]), folder)
        self.assertEqual(code, 0)
        self.assertIn("warn lembas   demo: opens with the answer", out)
        self.assertIn("warn lembas   demo: no closing offer", out)
        self.assertIn("lembas   7/9 checks passed", out)

    def test_committed_results_pass(self):
        code, out = run_main(grade, EVALS, RESULTS)
        self.assertEqual(code, 0)
        self.assertNotIn("FAIL lembas", out)
        self.assertIn("lembas   84/85 checks passed", out)
        self.assertIn("baseline 57/65 checks passed", out)

    def test_the_safety_prompt_is_graded_on_its_protective_steps(self):
        evs = {e["name"]: e for e in json.loads(support.read(EVALS))["evals"]}
        safety = evs["prod-table-rebuild-safety"]
        self.assertEqual(safety["category"], "safety")
        self.assertEqual(safety["must_contain"], ["pg_dump", "BEGIN", "RENAME"])
        reply = support.read(os.path.join(RESULTS, "prod-table-rebuild-safety", "lembas.md"))
        required = [ok for kind, _, ok in grade.checks(reply, safety, "lembas") if kind == "required"]
        self.assertEqual(required, [True] * 7)


@unittest.skipUnless(shutil.which("bash") and shutil.which("zip") and shutil.which("unzip"),
                     "bash, zip and unzip are needed")
class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = support.run(["bash", os.path.join(support.ROOT, "scripts", "package.sh")])
        cls.dist = os.path.join(support.ROOT, "dist")

    def names(self, skill):
        with zipfile.ZipFile(os.path.join(self.dist, f"{skill}.skill")) as z:
            return set(z.namelist())

    def test_builds_both_archives(self):
        self.assertEqual(self.build.returncode, 0, self.build.stderr.decode())
        out = self.build.stdout.decode()
        self.assertIn("Built dist/lembas.skill", out)
        self.assertIn("Built dist/ithildin.skill", out)

    def test_each_archive_holds_one_skill_folder_with_its_scripts(self):
        lembas, ithildin = self.names("lembas"), self.names("ithildin")
        self.assertTrue({"lembas/SKILL.md", "lembas/scripts/squeeze.py", "lembas/hooks/squeeze_hook.py"} <= lembas)
        self.assertTrue({"ithildin/SKILL.md", "ithildin/scripts/ithildin.py"} <= ithildin)
        self.assertTrue(all(n.startswith("lembas/") for n in lembas))
        self.assertTrue(all(n.startswith("ithildin/") for n in ithildin))

    def test_caches_and_finder_files_are_left_out(self):
        for name in self.names("lembas") | self.names("ithildin"):
            self.assertNotIn("__pycache__", name)
            self.assertFalse(name.endswith(".DS_Store") or name.endswith(".pyc"), name)

    def test_the_packaged_scripts_run_from_the_extracted_archive(self):
        target = support.tmp("scripts", "unpacked", "x")[:-2]
        for skill in ("lembas", "ithildin"):
            with zipfile.ZipFile(os.path.join(self.dist, f"{skill}.skill")) as z:
                z.extractall(target)
        log = "".join(f"2026-01-01 00:00:{i % 60:02d} INFO tick {i}\n" for i in range(4000)) + "ERROR boom\n"
        r = support.run_py(os.path.join(target, "lembas", "scripts", "squeeze.py"), data=log)
        self.assertTrue(r.stdout.decode().startswith("[lembas squeeze: log"), r.stderr.decode())
        payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "cat x"},
                              "tool_response": {"stdout": log, "stderr": ""}})
        r = support.run_py(os.path.join(target, "lembas", "hooks", "squeeze_hook.py"), data=payload)
        self.assertIn("updatedToolOutput", r.stdout.decode(), r.stderr.decode())
        doc = support.write(os.path.join(target, "doc.md"), "# One\n\nBody.\n")
        r = support.run_py(os.path.join(target, "ithildin", "scripts", "ithildin.py"), "map", doc)
        self.assertTrue(r.stdout.decode().startswith("[ithildin map: doc.md"), r.stderr.decode())


class SkillFiles(unittest.TestCase):
    """The same check CI makes on each SKILL.md, plus that the commands they name exist."""

    def test_frontmatter_has_name_and_description(self):
        for skill in ("lembas", "ithildin"):
            text = support.read(os.path.join(support.ROOT, "skills", skill, "SKILL.md"))
            self.assertTrue(text.startswith("---\n"), skill)
            front = text.split("---", 2)[1]
            self.assertRegex(front, rf"(?m)^name: {skill}$")
            self.assertRegex(front, r"(?m)^description:")

    def test_scripts_named_in_the_skills_exist(self):
        for skill, script in (("lembas", "scripts/squeeze.py"), ("ithildin", "scripts/ithildin.py")):
            text = support.read(os.path.join(support.ROOT, "skills", skill, "SKILL.md"))
            self.assertIn(script, text)
            self.assertTrue(os.path.isfile(os.path.join(support.ROOT, "skills", skill, script)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
