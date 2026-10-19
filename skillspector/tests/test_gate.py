"""Tests for gate.py.

The unit tests need only PyYAML. The fixture tests run the real scanner and
are skipped unless `skillspector` is on PATH; CI runs them inside the image.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import gate  # noqa: E402

FIXTURES = HERE / "fixtures"


def make_tree(root: Path, files: list[str]) -> None:
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")


class DiscoverSkills(unittest.TestCase):
    def test_finds_skill_dirs_and_honours_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(
                root,
                [
                    "skills/a/SKILL.md",
                    "skills/b/SKILL.md",
                    "pkg/evals/files/.trees/vendor/c/SKILL.md",
                    "node_modules/x/SKILL.md",
                    "skills/README.md",
                ],
            )
            self.assertEqual(
                gate.discover_skills(root, []),
                ["pkg/evals/files/.trees/vendor/c", "skills/a", "skills/b"],
            )
            self.assertEqual(gate.discover_skills(root, ["*/evals/files/*"]), ["skills/a", "skills/b"])


class SelectChanged(unittest.TestCase):
    skills = ["skills/a", "skills/ab", "skills/c"]

    def test_picks_skills_containing_a_changed_file(self):
        changed = ["skills/a/SKILL.md", "./skills/c/references/x.md", "README.md"]
        self.assertEqual(gate.select_changed(self.skills, changed, None), ["skills/a", "skills/c"])

    def test_prefix_is_a_whole_directory(self):
        self.assertEqual(gate.select_changed(self.skills, ["skills/ab/SKILL.md"], None), ["skills/ab"])

    def test_baseline_change_scans_everything(self):
        changed = [".skillspector-baseline.yaml"]
        self.assertEqual(gate.select_changed(self.skills, changed, ".skillspector-baseline.yaml"), self.skills)

    def test_nothing_changed(self):
        self.assertEqual(gate.select_changed(self.skills, ["docs/x.md", ""], None), [])


class RulesForSkill(unittest.TestCase):
    files = ["SKILL.md", "references/a.md", "evals/evals.json"]

    def translate(self, rules, skill="skills/x"):
        return gate.rules_for_skill(rules, skill, self.files)

    def test_rule_without_path_applies_everywhere(self):
        rule = {"id": "P1", "reason": "r"}
        self.assertEqual(self.translate([rule]), [(0, rule)])

    def test_repository_path_becomes_skill_relative(self):
        out = self.translate([{"id": "P1", "path": "skills/x/SKILL.md", "reason": "r"}])
        self.assertEqual(out, [(0, {"id": "P1", "reason": "r", "path": "SKILL.md"})])

    def test_glob_expands_to_each_matching_file(self):
        out = self.translate([{"id": "P1", "path": "*/x/references/*", "reason": "r"}])
        self.assertEqual([r["path"] for _, r in out], ["references/a.md"])

    def test_file_alias_is_accepted(self):
        out = self.translate([{"id": "P1", "file": "skills/x/evals/*", "reason": "r"}])
        self.assertEqual(out, [(0, {"id": "P1", "reason": "r", "path": "evals/evals.json"})])

    def test_rule_for_another_skill_is_dropped(self):
        self.assertEqual(self.translate([{"id": "P1", "path": "skills/y/SKILL.md", "reason": "r"}]), [])

    def test_glob_characters_in_file_names_are_escaped(self):
        out = gate.rules_for_skill([{"id": "P1", "path": "s/*", "reason": "r"}], "s", ["a[1]?.md"])
        self.assertEqual(out[0][1]["path"], "a[[]1][?].md")


class LoadBaseline(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.yaml"
            path.write_text(text, encoding="utf-8")
            return gate.load_baseline(path)

    def test_rules(self):
        self.assertEqual(self.load('version: 2\nrules:\n  - id: P1\n    reason: "ok"\n'), [{"id": "P1", "reason": "ok"}])

    def test_fingerprints_are_refused(self):
        with self.assertRaisesRegex(gate.GateError, "fingerprints"):
            self.load("version: 2\nfingerprints:\n  - hash: sha256:00\n    reason: x\n")

    def test_reason_is_required(self):
        with self.assertRaisesRegex(gate.GateError, "reason"):
            self.load("version: 2\nrules:\n  - id: P1\n")

    def test_id_is_required(self):
        with self.assertRaisesRegex(gate.GateError, "needs an id"):
            self.load("version: 2\nrules:\n  - path: x\n    reason: r\n")


@unittest.skipUnless(shutil.which("skillspector"), "skillspector is not installed")
class Fixtures(unittest.TestCase):
    def gate(self, fixture, *extra):
        return subprocess.run(
            [sys.executable, str(HERE.parent / "gate.py"), str(FIXTURES / fixture), *extra],
            capture_output=True,
            text=True,
        )

    def test_clean_skill_passes(self):
        proc = self.gate("clean")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_risky_skill_fails(self):
        proc = self.gate("risky")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("P1", proc.stdout)

    def test_baselined_skill_passes_and_reports_the_stale_rule(self):
        proc = self.gate("baselined")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("4 suppressed", proc.stdout)
        self.assertIn("no-such-skill", proc.stderr)

    def test_unchanged_skills_are_not_scanned(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as changed:
            changed.write("README.md\n")
            changed.flush()
            proc = self.gate("risky", "--changed-files", changed.name)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("scanned 0 skill(s)", proc.stdout)


if __name__ == "__main__":
    unittest.main()
