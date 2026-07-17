#!/usr/bin/env python3
"""Check shell command positions for discouraged utilities without executing them."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import re
import sys


FORBIDDEN = {"grep": "rg", "find": "fd", "cat": "bat", "ls": "eza", "du": "dust"}
WRAPPERS = {"command", "env", "sudo", "time"}
COMMAND_CONTROL_WORDS = {"if", "then", "elif", "else", "while", "until", "do"}
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
HEREDOC = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))")
PUNCTUATION = "<>|&;(){}!\n"


@dataclass(frozen=True)
class ShellToken:
    value: str
    quoted: bool = False
    substitutions: tuple[str, ...] = ()


def strip_heredoc_bodies(command: str) -> str:
    output: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in command.splitlines(keepends=True):
        if pending:
            delimiter, strip_tabs = pending[0]
            candidate = line.rstrip("\r\n")
            if strip_tabs:
                candidate = candidate.lstrip("\t")
            if candidate == delimiter:
                pending.pop(0)
            output.append("\n" if line.endswith(("\n", "\r")) else "")
            continue
        output.append(line)
        for match in HEREDOC.finditer(line):
            delimiter = next(group for group in match.groups() if group is not None)
            operator = match.group(0).split(delimiter, 1)[0]
            pending.append((delimiter, "<<-" in operator))
    return "".join(output)


def extract_backtick(command: str, start: int) -> tuple[str, int]:
    index = start + 1
    content: list[str] = []
    while index < len(command):
        if command[index] == "\\" and index + 1 < len(command):
            content.extend(command[index:index + 2])
            index += 2
            continue
        if command[index] == "`":
            return "".join(content), index + 1
        content.append(command[index])
        index += 1
    raise ValueError("unterminated backtick command substitution")


def extract_dollar_parens(command: str, start: int) -> tuple[str, int]:
    index = start + 2
    depth = 1
    quote = ""
    content: list[str] = []
    while index < len(command):
        character = command[index]
        if character == "\\" and index + 1 < len(command):
            content.extend(command[index:index + 2])
            index += 2
            continue
        if quote:
            content.append(character)
            if character == quote:
                quote = ""
            index += 1
            continue
        if character in "'\"":
            quote = character
            content.append(character)
        elif character == "(":
            depth += 1
            content.append(character)
        elif character == ")":
            depth -= 1
            if depth == 0:
                return "".join(content), index + 1
            content.append(character)
        else:
            content.append(character)
        index += 1
    raise ValueError("unterminated $(...) command substitution")


def tokenize(command: str) -> list[ShellToken]:
    command = strip_heredoc_bodies(command)
    tokens: list[ShellToken] = []
    characters: list[str] = []
    substitutions: list[str] = []
    quoted = False
    index = 0

    def flush() -> None:
        nonlocal quoted
        if characters:
            tokens.append(ShellToken("".join(characters), quoted, tuple(substitutions)))
            characters.clear()
            substitutions.clear()
            quoted = False

    while index < len(command):
        character = command[index]
        if character in " \t\r":
            flush()
            index += 1
            continue
        if character == "#" and not characters:
            while index < len(command) and command[index] != "\n":
                index += 1
            continue
        if character == "'":
            quoted = True
            end = command.find("'", index + 1)
            if end < 0:
                raise ValueError("unterminated single quote")
            characters.append(command[index + 1:end])
            index = end + 1
            continue
        if character == '"':
            quoted = True
            index += 1
            while index < len(command) and command[index] != '"':
                if command[index] == "\\" and index + 1 < len(command):
                    characters.append(command[index + 1])
                    index += 2
                elif command[index] == "`":
                    substitution, index = extract_backtick(command, index)
                    substitutions.append(substitution)
                    characters.append("__cmdsub__")
                elif command.startswith("$(", index):
                    substitution, index = extract_dollar_parens(command, index)
                    substitutions.append(substitution)
                    characters.append("__cmdsub__")
                else:
                    characters.append(command[index])
                    index += 1
            if index >= len(command):
                raise ValueError("unterminated double quote")
            index += 1
            continue
        if character == "\\" and index + 1 < len(command):
            quoted = True
            characters.append(command[index + 1])
            index += 2
            continue
        if character == "`":
            substitution, index = extract_backtick(command, index)
            substitutions.append(substitution)
            characters.append("__cmdsub__")
            continue
        if command.startswith("$(", index):
            substitution, index = extract_dollar_parens(command, index)
            substitutions.append(substitution)
            characters.append("__cmdsub__")
            continue
        if character in PUNCTUATION:
            flush()
            end = index + 1
            while end < len(command) and command[end] in PUNCTUATION:
                end += 1
            tokens.append(ShellToken(command[index:end]))
            index = end
            continue
        characters.append(character)
        index += 1
    flush()
    return tokens


def is_separator(token: str) -> bool:
    return bool(token) and all(character in "|&;(){}!\n" for character in token)


def is_redirection(token: str) -> bool:
    return "<" in token or ">" in token


def skip_wrapper_options(tokens: list[ShellToken], index: int, wrapper: str) -> int:
    while index < len(tokens):
        token = tokens[index].value
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
        shell_token = tokens[index]
        for substitution in shell_token.substitutions:
            violations.extend(check_command(substitution))
        token = shell_token.value
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
        if token.isdigit() and index + 1 < len(tokens) and is_redirection(tokens[index + 1].value):
            index += 1
            token = tokens[index].value
        if is_redirection(token):
            index += 2
            continue
        if not shell_token.quoted and token in COMMAND_CONTROL_WORDS:
            index += 1
            continue
        if not shell_token.quoted and token in NON_COMMAND_CONTROL_WORDS:
            command_position = False
            index += 1
            continue

        executable = os.path.basename(token)
        if index + 1 < len(tokens) and tokens[index + 1].value == "()":
            command_position = False
            index += 2
            continue
        if index + 2 < len(tokens) and tokens[index + 1].value == "(" and tokens[index + 2].value == ")":
            command_position = False
            index += 3
            continue
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
