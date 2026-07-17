---
name: commit-guard
description: Validate commit message structure, required Codex co-author attribution, and staged-path breadth. Use before creating a Git commit or reviewing commit readiness.
---

# Commit Guard

Validate a message file or literal message before committing:

```bash
python3 scripts/check_commit.py --enforce .git/COMMIT_EDITMSG
python3 scripts/check_commit.py --message "$(printf 'fix: example\\n...')" --repo .
```

Use advisory mode first. `--enforce` exits 2 only for deterministic message errors. Treat multi-component staging as a semantic-atomicity warning that requires judgment, never as a blocker by itself.

After a successful push, hand off naturally to `ci-monitoring`. The two skills have no runtime dependency.
