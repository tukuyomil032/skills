import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_command.py"


class CommandGuardTests(unittest.TestCase):
    def run_guard(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def payload(self, result: subprocess.CompletedProcess[str]) -> dict:
        return json.loads(result.stdout)

    def test_detects_direct_command(self) -> None:
        result = self.run_guard("grep -n needle file.txt")
        self.assertEqual(
            self.payload(result)["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )

    def test_detects_commands_in_pipeline_and_after_separator(self) -> None:
        result = self.run_guard("printf text | grep text; find . -name '*.py'")
        self.assertEqual(
            self.payload(result)["violations"],
            [
                {"replacement": "rg", "token": "grep"},
                {"replacement": "fd", "token": "find"},
            ],
        )

    def test_does_not_match_quoted_or_prose_arguments(self) -> None:
        result = self.run_guard("printf '%s' 'grep this text'; echo cat find ls du")
        self.assertEqual(self.payload(result)["violations"], [])

    def test_handles_assignments_and_wrappers(self) -> None:
        result = self.run_guard("MODE=quiet sudo -u root env FLAG=1 command grep value file")
        self.assertEqual(
            self.payload(result)["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )

    def test_handles_control_words_groups_and_leading_redirections(self) -> None:
        result = self.run_guard("! grep x f; if find .; then <input cat; fi; { ls; }; 2>errors du -s .")
        self.assertEqual(
            self.payload(result)["violations"],
            [
                {"replacement": "rg", "token": "grep"},
                {"replacement": "fd", "token": "find"},
                {"replacement": "bat", "token": "cat"},
                {"replacement": "eza", "token": "ls"},
                {"replacement": "dust", "token": "du"},
            ],
        )

    def test_allows_replacement_commands(self) -> None:
        result = self.run_guard("rg value file | fd '*.py'; bat file; eza; dust")
        self.assertEqual(self.payload(result)["violations"], [])

    def test_advisory_and_enforce_exit_behavior(self) -> None:
        advisory = self.run_guard(stdin="cat file")
        enforce = self.run_guard("--enforce", stdin="cat file")
        clean = self.run_guard("--enforce", "bat file")
        self.assertEqual(advisory.returncode, 0)
        self.assertEqual(enforce.returncode, 2)
        self.assertEqual(clean.returncode, 0)


if __name__ == "__main__":
    unittest.main()
