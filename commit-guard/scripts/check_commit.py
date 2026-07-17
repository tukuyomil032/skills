#!/usr/bin/env python3
"""Validate a commit message and optionally inspect staged path breadth."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


PREFIX = re.compile(r"^(?:feat|fix|ref|docs|chore):\s+\S.*$")
TRAILER = "Co-Authored-By: Codex <codex@openai.com>"


def validate_message(message: str) -> list[str]:
    errors: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", message.strip()) if part.strip()]
    subject = paragraphs[0] if paragraphs else ""

    if not re.match(r"^(?:feat|fix|ref|docs|chore):", subject):
        errors.append("subject prefix must be one of feat:, fix:, ref:, docs:, chore:")
    if "\n" in subject or not PREFIX.fullmatch(subject):
        errors.append("subject must contain a brief non-empty summary")

    body_paragraphs = [paragraph for paragraph in paragraphs[1:] if paragraph != TRAILER]
    if len(body_paragraphs) < 2:
        errors.append("message must include at least two non-empty body/detail paragraphs")
    if paragraphs.count(TRAILER) != 1 or not paragraphs or paragraphs[-1] != TRAILER:
        errors.append(f"message must end with exact trailer: {TRAILER}")
    return errors


def staged_path_warnings(repo: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only", "-z"],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return [f"could not inspect staged paths: {error}"]
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        return [f"could not inspect staged paths: {detail or 'git exited nonzero'}"]

    paths = [path for path in result.stdout.decode("utf-8", errors="surrogateescape").split("\0") if path]
    components = sorted({path.split("/", 1)[0] for path in paths})
    if len(components) > 1:
        joined = ", ".join(components)
        return [f"staged paths span multiple top-level components: {joined}; review semantic atomicity"]
    return []


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("message_file", nargs="?", type=Path)
    source.add_argument("--message")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.message is not None:
        message = args.message
    else:
        message = args.message_file.read_text(encoding="utf-8")
    errors = validate_message(message)
    warnings = staged_path_warnings(args.repo)
    payload = {
        "errors": errors,
        "mode": "enforce" if args.enforce else "advisory",
        "valid": not errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2 if args.enforce and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
