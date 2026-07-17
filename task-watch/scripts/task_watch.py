#!/usr/bin/env python3
"""Run and watch a local command while streaming, logging, and distilling output."""

from __future__ import annotations

import argparse
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path


EVIDENCE = re.compile(r"(?:error|fail|warn)", re.IGNORECASE)


def distill_lines(lines: list[str], limit: int) -> list[dict[str, int | str]]:
    """Select evidence lines and recent tail lines, deduplicated by text."""
    if limit <= 0:
        return []

    selected: list[tuple[int, str]] = []
    seen_text: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if EVIDENCE.search(line) and line not in seen_text:
            selected.append((line_number, line))
            seen_text.add(line)
            if len(selected) == limit:
                break

    if len(selected) < limit:
        for line_number in range(len(lines), 0, -1):
            line = lines[line_number - 1]
            if line in seen_text:
                continue
            selected.append((line_number, line))
            seen_text.add(line)
            if len(selected) == limit:
                break

    selected.sort(key=lambda entry: entry[0])
    return [{"line_number": line_number, "text": line} for line_number, line in selected]


def _read_output(stream: object, output_queue: queue.Queue[str | None]) -> None:
    try:
        for line in stream:  # type: ignore[union-attr]
            output_queue.put(line)
    finally:
        output_queue.put(None)


def run_command(
    command: list[str],
    log_path: Path,
    idle_seconds: float,
    heartbeat_seconds: float,
    summary_lines: int,
) -> tuple[int, dict[str, object]]:
    start = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=False,
    )
    assert process.stdout is not None
    output_queue: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(target=_read_output, args=(process.stdout, output_queue), daemon=True)
    reader.start()

    lines: list[str] = []
    idle_observed = False
    idle_reported = False
    last_output = start
    next_heartbeat = start + heartbeat_seconds if heartbeat_seconds > 0 else float("inf")
    reader_done = False

    with log_path.open("w", encoding="utf-8") as log_file:
        while not reader_done:
            now = time.monotonic()
            deadlines = [now + 0.1, next_heartbeat]
            if idle_seconds > 0 and not idle_reported:
                deadlines.append(last_output + idle_seconds)
            timeout = max(0.0, min(deadlines) - now)
            try:
                item = output_queue.get(timeout=timeout)
            except queue.Empty:
                item = ""

            if item is None:
                reader_done = True
            elif item:
                sys.stdout.write(item)
                sys.stdout.flush()
                log_file.write(item)
                log_file.flush()
                lines.append(item.rstrip("\r\n"))
                last_output = time.monotonic()
                idle_reported = False

            now = time.monotonic()
            if idle_seconds > 0 and not idle_reported and now - last_output >= idle_seconds:
                idle_observed = True
                idle_reported = True
                print(f"[task-watch] idle for {now - last_output:.2f}s; child continues", file=sys.stderr, flush=True)
            if heartbeat_seconds > 0 and now >= next_heartbeat:
                state = "idle" if idle_reported else "running"
                print(f"[task-watch] heartbeat: {state}", file=sys.stderr, flush=True)
                while next_heartbeat <= now:
                    next_heartbeat += heartbeat_seconds

    exit_code = process.wait()
    reader.join(timeout=1)
    duration = time.monotonic() - start
    summary: dict[str, object] = {
        "command": command,
        "duration_seconds": round(duration, 6),
        "evidence": distill_lines(lines, summary_lines),
        "exit_code": exit_code,
        "idle_observed": idle_observed,
        "log_path": str(log_path.resolve()),
    }
    return exit_code, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("task-watch.log"))
    parser.add_argument("--idle-seconds", type=float, default=60.0)
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0)
    parser.add_argument("--summary-lines", type=int, default=20)
    parser.add_argument("--json-summary", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    if args.idle_seconds < 0 or args.heartbeat_seconds < 0 or args.summary_lines < 0:
        parser.error("timing and summary values must be non-negative")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    exit_code, summary = run_command(
        args.command,
        args.log,
        args.idle_seconds,
        args.heartbeat_seconds,
        args.summary_lines,
    )
    if args.json_summary is not None:
        args.json_summary.parent.mkdir(parents=True, exist_ok=True)
        args.json_summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
