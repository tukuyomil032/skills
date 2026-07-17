# Personal Skills Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement nine short-named, independently installable personal workflow skills with deterministic helpers and focused tests.

**Architecture:** Each skill owns its instructions, scripts, and tests. Cross-skill integration happens through command/file contracts, not shared runtime imports. Deterministic checks may enforce explicitly; semantic checks remain advisory.

**Tech Stack:** Markdown skill instructions, Python 3.11 standard library, `unittest`, Git command-line interfaces.

---

## File map

- `cmd-guard/`: shell command-position policy parser and tests.
- `commit-guard/`: Git message/staging validator and tests.
- `task-watch/`: subprocess watcher, log distiller, and tests.
- `fail-ledger/`: JSONL failure store, recurrence promotion, and tests.
- `bug-bundle/`: redacted diagnostic bundle builder and tests.
- `context-guard/`: cc-trace freshness and review-prompt builder with tests.
- `proof-matrix/`: evidence validator/Markdown renderer and tests.
- `mac-doctor/`: read-only macOS probe and mocked tests.
- `skill-meter/`: privacy-minimal event recorder/reporter and tests.

## Task 1: Deterministic workflow guards

**Files:**
- Create: `cmd-guard/SKILL.md`, `cmd-guard/SKILL.ja.md`, `cmd-guard/scripts/check_command.py`, `cmd-guard/tests/test_check_command.py`
- Create: `commit-guard/SKILL.md`, `commit-guard/SKILL.ja.md`, `commit-guard/scripts/check_commit.py`, `commit-guard/tests/test_check_commit.py`
- Create: `task-watch/SKILL.md`, `task-watch/SKILL.ja.md`, `task-watch/scripts/task_watch.py`, `task-watch/tests/test_task_watch.py`

- [ ] Write failing tests for command-position detection, message validation, safe subprocess execution, idle state, and evidence-preserving output distillation.
- [ ] Run each test module and confirm the missing implementation fails.
- [ ] Implement the minimal standard-library scripts described in the design.
- [ ] Add concise English and Japanese skill instructions with explicit triggers, advisory/enforcement boundaries, and invocation examples.
- [ ] Run all three test modules and confirm they pass.
- [ ] Commit each skill separately using the repository commit format and a `Co-Authored-By: Codex` trailer.

## Task 2: Reusable debugging and context intelligence

**Files:**
- Create: `fail-ledger/SKILL.md`, `fail-ledger/SKILL.ja.md`, `fail-ledger/scripts/fail_ledger.py`, `fail-ledger/tests/test_fail_ledger.py`
- Create: `bug-bundle/SKILL.md`, `bug-bundle/SKILL.ja.md`, `bug-bundle/scripts/bug_bundle.py`, `bug-bundle/tests/test_bug_bundle.py`
- Create: `context-guard/SKILL.md`, `context-guard/SKILL.ja.md`, `context-guard/scripts/context_guard.py`, `context-guard/tests/test_context_guard.py`

- [ ] Write failing tests for recurrence thresholds, secret redaction, excluded files, bundle manifests, cc-trace freshness, and bounded semantic-review prompt generation.
- [ ] Run each test module and confirm the missing implementation fails.
- [ ] Implement JSONL storage, bundle construction, and context review helpers without runtime imports across skill directories.
- [ ] Add concise English and Japanese skill instructions that document integration with `video-frame-reader` and `cc-trace` without copying them.
- [ ] Run all three test modules and confirm they pass.
- [ ] Commit each skill separately using the repository commit format and a `Co-Authored-By: Codex` trailer.

## Task 3: Evidence, platform diagnosis, and skill observation

**Files:**
- Create: `proof-matrix/SKILL.md`, `proof-matrix/SKILL.ja.md`, `proof-matrix/scripts/proof_matrix.py`, `proof-matrix/tests/test_proof_matrix.py`
- Create: `mac-doctor/SKILL.md`, `mac-doctor/SKILL.ja.md`, `mac-doctor/scripts/mac_doctor.py`, `mac-doctor/tests/test_mac_doctor.py`
- Create: `skill-meter/SKILL.md`, `skill-meter/SKILL.ja.md`, `skill-meter/scripts/skill_meter.py`, `skill-meter/tests/test_skill_meter.py`

- [ ] Write failing tests for evidence schema validation, Markdown escaping, stale/unknown states, mocked macOS probes, privacy-minimal event recording, and aggregate reporting.
- [ ] Run each test module and confirm the missing implementation fails.
- [ ] Implement the three standard-library tools with read-only diagnostics and no automatic prompt/skill edits.
- [ ] Add concise English and Japanese skill instructions with trigger examples and explicit uncertainty/privacy boundaries.
- [ ] Run all three test modules and confirm they pass.
- [ ] Commit each skill separately using the repository commit format and a `Co-Authored-By: Codex` trailer.

## Task 4: Portfolio validation

**Files:**
- Modify only files created by Tasks 1-3 when validation finds defects.

- [ ] Run `python3 -m unittest discover -s <skill>/tests -v` for every new skill.
- [ ] Parse every `SKILL.md` and `SKILL.ja.md` frontmatter and verify the directory name equals `name`.
- [ ] Search for stale long candidate names and retain them only where the design history intentionally maps old names to new names.
- [ ] Run `git diff --check` and inspect `git status --short`.
- [ ] Verify `ci-monitoring/packages/src/index.ts` remains unstaged and unchanged by this work.
- [ ] Run spec-compliance review, code-quality review, and empirical prompt evaluation before final handoff.

