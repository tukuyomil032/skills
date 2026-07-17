import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "task_watch.py"
SPEC = importlib.util.spec_from_file_location("task_watch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DistillTests(unittest.TestCase):
    def test_selects_evidence_and_tail_with_line_numbers_and_deduplication(self) -> None:
        lines = ["start", "WARNING: slow", "middle", "ERROR: broke", "done", "done"]
        self.assertEqual(
            MODULE.distill_lines(lines, 4),
            [
                {"line_number": 2, "text": "WARNING: slow"},
                {"line_number": 3, "text": "middle"},
                {"line_number": 4, "text": "ERROR: broke"},
                {"line_number": 6, "text": "done"},
            ],
        )

    def test_zero_limit_returns_no_evidence(self) -> None:
        self.assertEqual(MODULE.distill_lines(["ERROR"], 0), [])


class TaskWatchCliTests(unittest.TestCase):
    def run_watch(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_success_creates_log_and_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "run.log"
            summary = root / "summary.json"
            result = self.run_watch(
                "--log", str(log),
                "--json-summary", str(summary),
                "--summary-lines", "5",
                "--",
                sys.executable, "-u", "-c", "print('ok'); print('WARN: sample')",
            )
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(log.read_text(encoding="utf-8"), "ok\nWARN: sample\n")
            self.assertEqual(payload["exit_code"], 0)
            self.assertEqual(payload["command"][0], sys.executable)
            self.assertEqual(payload["log_path"], str(log.resolve()))
            self.assertTrue(any(entry["line_number"] == 2 for entry in payload["evidence"]))

    def test_propagates_failing_child_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_watch(
                "--log", str(Path(directory) / "fail.log"),
                "--",
                sys.executable, "-c", "raise SystemExit(7)",
            )
        self.assertEqual(result.returncode, 7)

    def test_short_idle_period_is_observed_without_killing_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "idle.json"
            result = self.run_watch(
                "--log", str(root / "idle.log"),
                "--json-summary", str(summary),
                "--idle-seconds", "0.05",
                "--heartbeat-seconds", "0",
                "--",
                sys.executable, "-u", "-c", "import time; time.sleep(0.15); print('awake')",
            )
            payload = json.loads(summary.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(payload["idle_observed"])
        self.assertIn("idle", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
