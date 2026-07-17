#!/usr/bin/env python3
"""Check shell command positions for discouraged utilities without executing them."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys


FORBIDDEN = {"grep": "rg", "find": "fd", "cat": "bat", "ls": "eza", "du": "dust"}
WRAPPERS = {"command", "env", "sudo"}
COMMAND_CONTROL_WORDS = {"if", "then", "elif", "else", "while", "until", "do", "time"}
NON_COMMAND_CONTROL_WORDS = {"case", "esac", "fi", "for", "in", "done", "select"}
OPTION_ARGUMENTS = {
    "env": {"-C", "--chdir", "-S", "--split-string", "-u", "--unset"},
    "sudo": {
        "-C", "--close-from", "-D", "--chdir", "-g", "--group", "-h", "--host",
        "-p", "--prompt", "-R", "--chroot", "-r", "--role", "-t", "--type",
        "-T", "--command-timeout", "-u", "--user",
    },
}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="<>|&;(){}!\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def is_separator(token: str) -> bool:
    return bool(token) and all(character in "|&;(){}!\n" for character in token)


def is_redirection(token: str) -> bool:
    return "<" in token or ">" in token


def skip_wrapper_options(tokens: list[str], index: int, wrapper: str) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index + 1
        if wrapper == "env" and ASSIGNMENT.match(token):
            index += 1
            continue
        if not token.startswith("-") or token == "-":
            return index
        option = token.split("=", 1)[0]
        index += 1
        if option in OPTION_ARGUMENTS.get(wrapper, set()) and "=" not in token:
            index += 1
    return index


def check_command(command: str) -> list[dict[str, str]]:
    tokens = tokenize(command)
    violations: list[dict[str, str]] = []
    index = 0
    command_position = True

    while index < len(tokens):
        token = tokens[index]
        if is_separator(token):
            command_position = True
            index += 1
            continue
        if not command_position:
            index += 1
            continue
        if ASSIGNMENT.match(token):
            index += 1
            continue
        if token.isdigit() and index + 1 < len(tokens) and is_redirection(tokens[index + 1]):
            index += 1
            token = tokens[index]
        if is_redirection(token):
            index += 2
            continue
        if token in COMMAND_CONTROL_WORDS:
            index += 1
            continue
        if token in NON_COMMAND_CONTROL_WORDS:
            command_position = False
            index += 1
            continue

        executable = os.path.basename(token)
        if executable in WRAPPERS:
            index = skip_wrapper_options(tokens, index + 1, executable)
            continue
        if executable in FORBIDDEN:
            violations.append({"replacement": FORBIDDEN[executable], "token": executable})
        command_position = False
        index += 1

    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("command", nargs="?", help="shell command string; read stdin when omitted")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command = args.command if args.command is not None else sys.stdin.read()
    try:
        violations = check_command(command)
        payload = {"command": command, "mode": "enforce" if args.enforce else "advisory", "violations": violations}
    except ValueError as error:
        violations = []
        payload = {"command": command, "error": str(error), "mode": "enforce" if args.enforce else "advisory", "violations": violations}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2 if args.enforce and (payload.get("error") or violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
