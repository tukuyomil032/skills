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
