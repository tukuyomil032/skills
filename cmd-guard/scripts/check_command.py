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
    "time": {"-f", "--format", "-o", "--output"},
}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PUNCTUATION = "<>|&;(){}!\n"
OPERATORS = ("<<<", "<<-", "&&", "||", ";;", "<<", ">>", "<&", ">&", "<>", ">|", "()")
UNSUPPORTED_WORDS = {"case", "coproc", "esac", "for", "select"}


@dataclass(frozen=True)
class ShellToken:
    value: str
    quoted: bool = False
    substitutions: tuple[str, ...] = ()
    comment: bool = False


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


def extract_parenthesized(command: str, open_index: int) -> tuple[str, int]:
    index = open_index + 1
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


def extract_arithmetic(command: str, start: int) -> tuple[str, int]:
    index = start + 3
    depth = 0
    content: list[str] = []
    while index < len(command):
        if command[index] == "\\" and index + 1 < len(command):
            content.extend(command[index:index + 2])
            index += 2
            continue
        if command[index] == "(":
            depth += 1
            content.append(command[index])
            index += 1
            continue
        if command[index] == ")":
            if depth > 0:
                depth -= 1
                content.append(")")
                index += 1
                continue
            if command.startswith("))", index):
                return "".join(content), index + 2
        content.append(command[index])
        index += 1
    raise ValueError("unterminated arithmetic expansion")


def remove_heredoc_bodies(tokens: list[ShellToken]) -> list[ShellToken]:
    output: list[ShellToken] = []
    pending: list[tuple[str, bool]] = []
    expect_delimiter = False
    in_body = False
    body_line: list[ShellToken] = []

    for token in tokens:
        if in_body:
            if token.value == "\n":
                delimiter, expand = pending[0]
                if len(body_line) == 1 and body_line[0].value == delimiter:
                    pending.pop(0)
                    if not pending:
                        in_body = False
                elif expand:
                    nested = tuple(item for body_token in body_line for item in body_token.substitutions)
                    token = ShellToken("\n", substitutions=nested)
                body_line.clear()
                output.append(token)
            else:
                body_line.append(token)
            continue

        output.append(token)
        if expect_delimiter:
            pending.append((token.value, not token.quoted))
            output[-1] = ShellToken(token.value, token.quoted)
            expect_delimiter = False
        elif token.value in {"<<", "<<-"} and not token.quoted:
            expect_delimiter = True
        elif token.value == "\n" and pending:
            in_body = True

    if in_body and pending and body_line:
        delimiter, _ = pending[0]
        if len(body_line) == 1 and body_line[0].value == delimiter:
            pending.pop(0)
    if expect_delimiter or pending:
        raise ValueError("unterminated heredoc")
    return output


def tokenize(command: str) -> list[ShellToken]:
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
            line_end = command.find("\n", index)
            if line_end < 0:
                line_end = len(command)
            fragment = command[index + 1:line_end]
            nested = tuple(
                substitution
                for nested_token in tokenize(fragment)
                for substitution in nested_token.substitutions
            )
            tokens.append(ShellToken(command[index:line_end], True, nested, True))
            index = line_end
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
                    escaped = command[index + 1]
                    if escaped == "\n":
                        pass
                    elif escaped in '$`"\\':
                        characters.append(escaped)
                    else:
                        characters.extend(("\\", escaped))
                    index += 2
                elif command[index] == "`":
                    substitution, index = extract_backtick(command, index)
                    substitutions.append(substitution)
                    characters.append("__cmdsub__")
                elif command.startswith("$((", index):
                    arithmetic, index = extract_arithmetic(command, index)
                    characters.append(f"__arithmetic_{len(arithmetic)}__")
                elif command.startswith("$(", index):
                    substitution, index = extract_parenthesized(command, index + 1)
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
            if command[index + 1] != "\n":
                quoted = True
                characters.append(command[index + 1])
            index += 2
            continue
        if character == "`":
            substitution, index = extract_backtick(command, index)
            substitutions.append(substitution)
            characters.append("__cmdsub__")
            continue
        if command.startswith("$((", index):
            arithmetic, index = extract_arithmetic(command, index)
            characters.append(f"__arithmetic_{len(arithmetic)}__")
            continue
        if command.startswith("$(", index):
            substitution, index = extract_parenthesized(command, index + 1)
            substitutions.append(substitution)
            characters.append("__cmdsub__")
            continue
        if character in "<>" and index + 1 < len(command) and command[index + 1] == "(":
            substitution, index = extract_parenthesized(command, index + 1)
            substitutions.append(substitution)
            characters.append("__process_sub__")
            continue
        if character in PUNCTUATION:
            flush()
            operator = next((item for item in OPERATORS if command.startswith(item, index)), character)
            tokens.append(ShellToken(operator))
            index += len(operator)
            continue
        characters.append(character)
        index += 1
    flush()
    return remove_heredoc_bodies(tokens)


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


def wrapper_tokens(tokens: list[ShellToken], index: int) -> list[ShellToken]:
    result: list[ShellToken] = []
    for token in tokens[index:]:
        if is_separator(token.value):
            break
        result.append(token)
    return result


def command_is_query(tokens: list[ShellToken], index: int) -> bool:
    for token in wrapper_tokens(tokens, index):
        if token.value == "--":
            return False
        if token.value in {"-v", "-V"}:
            return True
        if not token.value.startswith("-") or token.value == "-":
            return False
    return False


def sudo_is_nonexecuting(tokens: list[ShellToken], index: int) -> bool:
    wrapper = wrapper_tokens(tokens, index)
    position = 0
    while position < len(wrapper):
        option = wrapper[position].value
        if option == "--":
            return False
        if option in {"-e", "--edit", "-l", "--list"}:
            return True
        if not option.startswith("-") or option == "-":
            return False
        option_name = option.split("=", 1)[0]
        position += 1
        if option_name in OPTION_ARGUMENTS["sudo"] and "=" not in option:
            position += 1
    return False


def check_command(command: str) -> list[dict[str, str]]:
    return _check_command(command, set())


def _check_command(command: str, indeterminate: set[str]) -> list[dict[str, str]]:
    tokens = tokenize(command)
    violations: list[dict[str, str]] = []
    index = 0
    command_position = True

    while index < len(tokens):
        shell_token = tokens[index]
        if shell_token.comment:
            index += 1
            continue
        for substitution in shell_token.substitutions:
            violations.extend(_check_command(substitution, indeterminate))
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
            if index + 1 < len(tokens):
                for substitution in tokens[index + 1].substitutions:
                    violations.extend(_check_command(substitution, indeterminate))
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
        if executable == "env":
            wrapper_index = index + 1
            while wrapper_index < len(tokens):
                option = tokens[wrapper_index].value
                if ASSIGNMENT.match(option):
                    wrapper_index += 1
                    continue
                if option in {"-S", "--split-string"} and wrapper_index + 1 < len(tokens):
                    nested_command = tokens[wrapper_index + 1].value
                    indeterminate.update(unsupported_reasons(nested_command))
                    violations.extend(_check_command(nested_command, indeterminate))
                    command_position = False
                    index = wrapper_index + 2
                    break
                if option.startswith("--split-string="):
                    nested_command = option.split("=", 1)[1]
                    indeterminate.update(unsupported_reasons(nested_command))
                    violations.extend(_check_command(nested_command, indeterminate))
                    command_position = False
                    index = wrapper_index + 1
                    break
                if option.startswith("-S") and option != "-S":
                    nested_command = option[2:]
                    indeterminate.update(unsupported_reasons(nested_command))
                    violations.extend(_check_command(nested_command, indeterminate))
                    command_position = False
                    index = wrapper_index + 1
                    break
                if not option.startswith("-") or option == "-":
                    index = wrapper_index
                    break
                option_name = option.split("=", 1)[0]
                wrapper_index += 1
                if option_name in OPTION_ARGUMENTS["env"] and "=" not in option:
                    wrapper_index += 1
            else:
                command_position = False
                index = wrapper_index
            continue
        if executable == "command" and command_is_query(tokens, index + 1):
            command_position = False
            index += 1
            continue
        if executable == "sudo" and sudo_is_nonexecuting(tokens, index + 1):
            command_position = False
            index += 1
            continue
        if executable in WRAPPERS:
            index = skip_wrapper_options(tokens, index + 1, executable)
            continue
        if "$" in token or shell_token.substitutions:
            indeterminate.add(f"dynamic command word: {token}")
        if executable in FORBIDDEN:
            violations.append({"replacement": FORBIDDEN[executable], "token": executable})
        command_position = False
        index += 1

    return violations


def unsupported_reasons(command: str) -> list[str]:
    tokens = tokenize(command)
    reasons: set[str] = set()
    for index, token in enumerate(tokens):
        if not token.quoted and token.value in UNSUPPORTED_WORDS:
            reasons.add(f"unsupported control grammar: {token.value}")
        if not token.quoted and token.value in {"[[", "]]", "<<<"}:
            reasons.add(f"unsupported shell operator: {token.value}")
        if token.value == "$" and index + 1 < len(tokens) and tokens[index + 1].value == "{":
            reasons.add("unsupported parameter expansion")
        for substitution in token.substitutions:
            reasons.update(unsupported_reasons(substitution))
    return sorted(reasons)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("command", nargs="?", help="shell command string; read stdin when omitted")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command = args.command if args.command is not None else sys.stdin.read()
    requested_mode = "enforce" if args.enforce else "advisory"
    try:
        indeterminate_set = set(unsupported_reasons(command))
        violations = _check_command(command, indeterminate_set)
        indeterminate = sorted(indeterminate_set)
        payload = {
            "command": command,
            "indeterminate": indeterminate,
            "mode": "advisory" if indeterminate else requested_mode,
            "requested_mode": requested_mode,
            "status": "indeterminate" if indeterminate else ("violations" if violations else "clear"),
            "violations": violations,
        }
    except ValueError as error:
        violations = []
        indeterminate = []
        payload = {
            "command": command,
            "error": str(error),
            "indeterminate": indeterminate,
            "mode": requested_mode,
            "requested_mode": requested_mode,
            "status": "error",
            "violations": violations,
        }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 2 if args.enforce and not indeterminate and (payload.get("error") or violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
