import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_commit.py"
VALID_MESSAGE = """feat: add guard

Validate commit messages before creating a commit.

Technical notes: use only deterministic message rules.

Co-Authored-By: Codex <codex@openai.com>
"""


class CommitGuardTests(unittest.TestCase):
    def run_guard(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def payload(self, result: subprocess.CompletedProcess[str]) -> dict:
        return json.loads(result.stdout)

    def test_accepts_valid_message_string(self) -> None:
        result = self.run_guard("--message", VALID_MESSAGE, "--enforce")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.payload(result)["errors"], [])

    def test_accepts_valid_message_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "message.txt"
            path.write_text(VALID_MESSAGE, encoding="utf-8")
            result = self.run_guard(str(path), "--enforce")
        self.assertEqual(result.returncode, 0)

    def test_rejects_prefix_subject_and_body_errors(self) -> None:
        result = self.run_guard("--message", "feature: \n\nOnly one detail.\n", "--enforce")
        payload = self.payload(result)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(any("prefix" in error for error in payload["errors"]))
        self.assertTrue(any("subject" in error for error in payload["errors"]))
        self.assertTrue(any("two" in error for error in payload["errors"]))

    def test_requires_exact_trailer(self) -> None:
        wrong = VALID_MESSAGE.replace(
            "Co-Authored-By: Codex <codex@openai.com>",
            "Co-authored-by: Codex <codex@openai.com>",
        )
        result = self.run_guard("--message", wrong, "--enforce")
        self.assertTrue(any("Co-Authored-By" in error for error in self.payload(result)["errors"]))
        self.assertEqual(result.returncode, 2)

    def test_multi_component_staging_is_warning_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for component in ("alpha", "beta"):
                path = repo / component / "file.txt"
                path.parent.mkdir()
                path.write_text(component, encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "alpha", "beta"], check=True)
            result = self.run_guard("--message", VALID_MESSAGE, "--repo", str(repo), "--enforce")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(any("top-level" in warning for warning in self.payload(result)["warnings"]))

    def test_advisory_and_enforce_exit_behavior(self) -> None:
        invalid = "fix: short\n"
        advisory = self.run_guard("--message", invalid)
        enforce = self.run_guard("--message", invalid, "--enforce")
        self.assertEqual(advisory.returncode, 0)
        self.assertEqual(enforce.returncode, 2)


if __name__ == "__main__":
    unittest.main()
