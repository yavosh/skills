import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "skills/formal-verify/check.sh"


class CheckRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copyfile(RUNNER, self.root / "check.sh")
        jar = self.root / "fixture.jar"
        jar.touch()
        java = self.root / "java"
        java.write_text(
            '#!/bin/sh\n'
            'for spec in "$@"; do :; done\n'
            'printf "%s\\n" "$spec" >> "$CALL_LOG"\n'
            'case "$spec" in\n'
            '  Violation) echo "Invariant Safe is violated."; exit 1 ;;\n'
            '  Broken) echo "Error: fixture setup failed"; exit 2 ;;\n'
            '  *) echo "No error has been found." ;;\n'
            'esac\n'
        )
        java.chmod(0o700)
        self.log = self.root / "calls"
        self.env = {
            "PATH": os.defpath,
            "HOME": str(self.root),
            "JAVA": str(java),
            "TLA2TOOLS": str(jar),
            "CALL_LOG": str(self.log),
        }

    def run_checks(self, manifests):
        for name, content in manifests.items():
            (self.root / name).write_text(content)
        return subprocess.run(
            ["bash", str(self.root / "check.sh")],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_runs_unterminated_final_record(self):
        result = self.run_checks({"A.checks": "Success Success.cfg pass"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls(), ["Success"])

    def test_preserves_manifest_boundaries(self):
        result = self.run_checks({
            "A.checks": "First First.cfg pass first note",
            "B.checks": "Second Second.cfg pass\n",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls(), ["First", "Second"])

    def test_rejects_error_expectation_without_running_tools(self):
        result = self.run_checks({"A.checks": "Broken Broken.cfg error\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_rejects_missing_expectation(self):
        result = self.run_checks({"A.checks": "Success Success.cfg\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_rejects_manifests_without_checks(self):
        result = self.run_checks({"A.checks": "# only comments\n\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_accepts_expected_success_and_property_violation(self):
        result = self.run_checks({
            "checks.txt": "Success Success.cfg pass\nViolation Violation.cfg fail\n",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls(), ["Success", "Violation"])

    def test_rejects_setup_error_as_expected_violation(self):
        result = self.run_checks({"A.checks": "Broken Broken.cfg fail\n"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), ["Broken"])

    def test_rejects_unexpected_success(self):
        result = self.run_checks({"A.checks": "Success Success.cfg fail\n"})
        self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_manifests(self):
        result = self.run_checks({})
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
