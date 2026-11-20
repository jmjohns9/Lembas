"""Security hardening: how long saved copies are kept, pandoc's sandbox, zip size limits, and the skills'
rule on instructions found in data. See SECURITY.md."""
import contextlib
import io
import os
import sys
import time
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
import squeeze  # noqa: E402
import ithildin  # noqa: E402

DAY = 24 * 3600


def log_text(n=4000):
    return "".join(f"2026-01-01 INFO request {i} ok\n" if i % 500 else f"2026-01-01 ERROR request {i} failed\n"
                   for i in range(n))


def age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


class SqueezeKeepsSavedCopiesForALimitedTime(unittest.TestCase):
    def setUp(self):
        self.dir = support.tmp("security", self.id().rsplit(".", 1)[1], "x")[:-2]
        os.makedirs(self.dir, exist_ok=True)

    def test_saved_copies_older_than_the_limit_are_deleted_on_the_next_save(self):
        old = squeeze.save_original("old output\n", "log", self.dir)
        recent = squeeze.save_original("recent output\n", "log", self.dir)
        mine = support.write(os.path.join(self.dir, "notes.txt"), "not squeeze's")
        age(old, 25 * 3600)
        age(recent, 3600)
        age(mine, 30 * DAY)
        squeeze.save_original("new output\n", "log", self.dir)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(recent))
        self.assertTrue(os.path.exists(mine), "only files squeeze names itself are deleted")

    def test_the_limit_is_configurable(self):
        old = squeeze.save_original("old output\n", "log", self.dir)
        age(old, 3 * 3600)
        with mock.patch.dict(os.environ, {"LEMBAS_SQUEEZE_KEEP_HOURS": "2"}):
            squeeze.save_original("new output\n", "log", self.dir)
        self.assertFalse(os.path.exists(old))

    def test_saving_the_same_output_again_restarts_its_clock(self):
        path = squeeze.save_original("same\n", "log", self.dir)
        age(path, 23 * 3600)
        squeeze.save_original("same\n", "log", self.dir)
        self.assertLess(time.time() - os.path.getmtime(path), 60)

    def test_zero_hours_saves_nothing_and_says_so(self):
        with mock.patch.dict(os.environ, {"LEMBAS_SQUEEZE_KEEP_HOURS": "0", "LEMBAS_SQUEEZE_DIR": self.dir}):
            view, info = squeeze.squeeze(log_text(), kind="log")
        self.assertIsNotNone(view)
        self.assertIn("not kept", view.split("\n", 1)[0])
        self.assertNotIn("path", info)
        self.assertEqual(os.listdir(self.dir), [])

    def test_a_bad_value_falls_back_to_the_default(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"LEMBAS_SQUEEZE_KEEP_HOURS": "a day"}), contextlib.redirect_stderr(err):
            self.assertEqual(squeeze.keep_hours(), squeeze.DEFAULT_KEEP_HOURS)
        self.assertIn("LEMBAS_SQUEEZE_KEEP_HOURS", err.getvalue())


class IthildinKeepsItsCacheForALimitedTime(unittest.TestCase):
    def setUp(self):
        self.cache = support.tmp("security", "ith-" + self.id().rsplit(".", 1)[1], "x")[:-2]
        os.makedirs(self.cache, exist_ok=True)
        self.doc = support.write(support.tmp("security", "ith-doc-" + self.id().rsplit(".", 1)[1] + ".md"),
                                 "# Title\n\nBody.\n")

    def entries(self):
        return [n for n in os.listdir(self.cache) if n.endswith(".json")]

    def test_cache_entries_older_than_the_limit_are_deleted(self):
        stale = support.write(os.path.join(self.cache, "a" * 40 + ".json"), "{}")
        mine = support.write(os.path.join(self.cache, "keep.json"), "{}")
        age(stale, 25 * 3600)
        age(mine, 30 * DAY)
        with mock.patch.dict(os.environ, {"ITHILDIN_CACHE": self.cache}):
            ithildin.load(self.doc)
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(mine), "only files ithildin names itself are deleted")
        self.assertEqual(len(self.entries()), 2)

    def test_zero_hours_writes_no_cache(self):
        with mock.patch.dict(os.environ, {"ITHILDIN_CACHE": self.cache, "ITHILDIN_CACHE_HOURS": "0"}):
            doc = ithildin.load(self.doc)
        self.assertEqual(doc.kind, "Markdown")
        self.assertEqual(self.entries(), [])


class PandocRunsSandboxed(unittest.TestCase):
    def test_pandoc_is_called_with_its_sandbox(self):
        done = mock.Mock(returncode=0, stdout="# T\n\nBody.\n", stderr="")
        with mock.patch.object(ithildin, "_run", return_value=done) as run:
            ithildin.extract_with_pandoc("notes.rst")
        self.assertIn("--sandbox", run.call_args[0][0])

    def test_a_pandoc_without_the_sandbox_is_not_used_unprotected(self):
        old = mock.Mock(returncode=2, stdout="", stderr="Unknown option --sandbox.\nTry pandoc --help for more information.")
        with mock.patch.object(ithildin, "_run", return_value=old) as run:
            with self.assertRaises(SystemExit) as cm:
                ithildin.extract_with_pandoc("notes.rst")
        self.assertEqual(run.call_count, 1)
        self.assertIn("2.15", str(cm.exception))


class OfficeFilesHaveSizeLimits(unittest.TestCase):
    def docx(self, name):
        path = support.tmp("security", name)
        support.make_docx(path, support.w_p("Heading", "Heading1") + support.w_p("Body text " * 50))
        return path

    def test_a_member_that_unpacks_too_large_is_refused(self):
        path = self.docx("big-member.docx")
        with mock.patch.object(ithildin, "MAX_ZIP_MEMBER", 100):
            with self.assertRaises(SystemExit) as cm:
                ithildin._office(ithildin.extract_docx, path, "Word")
        self.assertIn("word/document.xml unpacks to", str(cm.exception))

    def test_a_file_that_unpacks_too_large_in_total_is_refused(self):
        path = self.docx("big-total.docx")
        with zipfile.ZipFile(path) as z:
            total = sum(i.file_size for i in z.infolist())
        with mock.patch.object(ithildin, "MAX_ZIP_TOTAL", total - 1):
            with self.assertRaises(SystemExit) as cm:
                ithildin._office(ithildin.extract_docx, path, "Word")
        self.assertIn("unpacks to", str(cm.exception))

    def test_normal_files_are_read(self):
        doc = ithildin._office(ithildin.extract_docx, self.docx("normal.docx"), "Word")
        self.assertTrue(any("Body text" in t for _, t in doc.lines))


class SkillsTreatDataAsData(unittest.TestCase):
    def test_both_skills_say_instructions_inside_data_are_not_followed(self):
        for skill in (support.LEMBAS, support.ITHILDIN):
            with self.subTest(skill):
                text = support.read(os.path.join(skill, "SKILL.md"))
                self.assertRegex(text, r"never (as )?instructions")


if __name__ == "__main__":
    unittest.main()
