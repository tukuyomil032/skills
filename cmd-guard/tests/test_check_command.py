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

    def test_preserves_shell_context_for_special_forms(self) -> None:
        heredoc = "printf x <<'EOF'\ngrep needle file\nEOF\nbat file"
        self.assertEqual(self.payload(self.run_guard(heredoc))["violations"], [])
        self.assertEqual(
            self.payload(self.run_guard("echo `grep needle file`; echo $(find .)"))["violations"],
            [
                {"replacement": "rg", "token": "grep"},
                {"replacement": "fd", "token": "find"},
            ],
        )
        self.assertEqual(
            self.payload(self.run_guard("time -p grep needle file"))["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )
        self.assertEqual(self.payload(self.run_guard('"if" grep'))["violations"], [])
        self.assertEqual(
            self.payload(self.run_guard("grep() { cat file; }"))["violations"],
            [{"replacement": "bat", "token": "cat"}],
        )

    def test_handles_final_parser_boundary_cases(self) -> None:
        quoted_heredoc = 'echo "<<EOF"\ngrep actual file'
        self.assertEqual(
            self.payload(self.run_guard(quoted_heredoc))["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )
        self.assertEqual(
            self.payload(self.run_guard("grep(){ cat file; }"))["violations"],
            [{"replacement": "bat", "token": "cat"}],
        )
        self.assertEqual(
            self.payload(self.run_guard("echo <(grep actual file)"))["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )
        self.assertEqual(self.payload(self.run_guard("echo $((grep + 1))"))["violations"], [])

    def test_unsupported_grammar_is_indeterminate_and_never_enforced(self) -> None:
        result = self.run_guard("--enforce", "case $x in y) grep value;; esac")
        payload = self.payload(result)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["status"], "indeterminate")
        self.assertEqual(payload["mode"], "advisory")
        self.assertTrue(payload["indeterminate"])

    def test_heredoc_expansions_follow_delimiter_quoting(self) -> None:
        unquoted = "printf x <<EOF\nplain grep words\n$(grep nested file)\n`find .`\nEOF"
        self.assertEqual(
            self.payload(self.run_guard(unquoted))["violations"],
            [
                {"replacement": "rg", "token": "grep"},
                {"replacement": "fd", "token": "find"},
            ],
        )
        quoted = "printf x <<'EOF'\n$(grep literal file)\nEOF"
        result = self.run_guard("--enforce", quoted)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.payload(result)["violations"], [])

    def test_wrapper_modes_distinguish_execution_from_queries(self) -> None:
        self.assertEqual(
            self.payload(self.run_guard("env -S 'grep -n value file'"))["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )
        for command in ("command -v grep", "command -V find", "sudo -l cat", "sudo -e ls"):
            with self.subTest(command=command):
                self.assertEqual(self.payload(self.run_guard(command))["violations"], [])

    def test_dynamic_command_word_is_indeterminate_only_in_command_position(self) -> None:
        dynamic = self.run_guard("--enforce", "$tool file")
        payload = self.payload(dynamic)
        self.assertEqual(dynamic.returncode, 0)
        self.assertEqual(payload["status"], "indeterminate")
        self.assertEqual(payload["mode"], "advisory")
        ordinary_argument = self.payload(self.run_guard("echo $tool"))
        self.assertEqual(ordinary_argument["status"], "clear")
        self.assertEqual(ordinary_argument["indeterminate"], [])

    def test_backslash_newline_continuation_forms_one_command_word(self) -> None:
        result = self.run_guard("gr\\\nep needle file")
        self.assertEqual(
            self.payload(result)["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )

    def test_wrapper_option_scanning_stops_at_executed_command(self) -> None:
        for command in ("command grep -v value file", "sudo -- grep -e value file"):
            with self.subTest(command=command):
                self.assertEqual(
                    self.payload(self.run_guard(command))["violations"],
                    [{"replacement": "rg", "token": "grep"}],
                )
        self.assertEqual(
            self.payload(self.run_guard("env -S'grep x file'"))["violations"],
            [{"replacement": "rg", "token": "grep"}],
        )

    def test_expansion_in_command_word_is_indeterminate(self) -> None:
        commands = ("g$part file", "pre${tool} file", "$(printf grep) file", "`printf grep` file")
        for command in commands:
            with self.subTest(command=command):
                result = self.run_guard("--enforce", command)
                payload = self.payload(result)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(payload["status"], "indeterminate")
                self.assertEqual(payload["mode"], "advisory")

    def test_heredoc_delimiter_word_substitutions_are_not_scanned(self) -> None:
        command = "bat <<$(grep)\nliteral body\n$(grep)"
        self.assertEqual(self.payload(self.run_guard(command))["violations"], [])

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
