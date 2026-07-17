---
name: cmd-guard
description: Check shell commands for prohibited utilities in executable positions and suggest approved replacements. Trigger automatically before running or proposing commands that may use grep, find, cat, ls, or du.
---

# Command Guard

Run the checker before executing a shell command. It parses text only and never executes it.

Start in advisory mode so findings can be reviewed. Use `--enforce` only when the workflow explicitly requires blocking; violations then exit with status 2.

```bash
python3 scripts/check_command.py "find . -name '*.py' | grep test"
python3 scripts/check_command.py --enforce < command.txt
```

Read the deterministic JSON and replace each reported token with its suggested utility.

Supported grammar includes simple commands, assignments, redirections and heredocs, pipelines and list separators, `if`/`while`/`until` command positions, groups, function definitions, the `sudo`/`env`/`command`/`time` wrappers, and command, backtick, or process substitutions. Arithmetic expansion is treated as data.

The JSON always includes `status`, `mode`, `requested_mode`, `indeterminate`, and `violations`. For unsupported grammar such as `case`, `for`, `select`, `coproc`, `[[...]]`, here-strings, or parameter expansion, `status` is `indeterminate`, `mode` falls back to `advisory`, and the checker never blocks even when `--enforce` was requested. Treat that result as requiring manual review; this checker is not a complete Bash parser.
