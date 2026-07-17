---
name: task-watch
description: Run long local commands with live combined output, persistent logs, idle reporting, exit-code propagation, and distilled JSON evidence. Use for builds, tests, or other verbose tasks that need monitoring.
---

# Task Watch

Run the command after `--` without a shell:

```bash
python3 scripts/task_watch.py --log build.log --json-summary build.json -- make test
```

Tune `--idle-seconds`, `--heartbeat-seconds`, and `--summary-lines` as needed. Idle detection reports state and does not kill the child. The JSON summary preserves the command, outcome, timing, log location, and numbered error/fail/warn-plus-tail evidence.

Use this skill to absorb large local output and hand back concise evidence. It complements `ci-monitoring`, which follows remote CI rather than local long-running tasks.
