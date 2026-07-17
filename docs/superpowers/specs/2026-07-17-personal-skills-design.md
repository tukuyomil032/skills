# Personal Skills Portfolio Design

## Goal

Add nine original, personal workflow skills without copying or vendoring skills installed under `~/.claude` or `~/.codex`.

## Final names

| Earlier candidate | Final skill |
|---|---|
| `command-policy-guard` | `cmd-guard` |
| `atomic-commit-guard` | `commit-guard` |
| `long-task-sentinel` + `large-output-distiller` | `task-watch` |
| `failure-pattern-ledger` | `fail-ledger` |
| `multimodal-bug-bundle` | `bug-bundle` |
| `context-integrity-guard` + `decision-drift-guard` | `context-guard` |
| `feasibility-evidence-matrix` | `proof-matrix` |
| `mac-permission-doctor` | `mac-doctor` |
| `skill-effectiveness-observer` | `skill-meter` |

Every name is at most 14 characters, is easy to type, and remains understandable from its skill description.

## Architecture

Each skill is independently installable and contains its own `SKILL.md`, Japanese `SKILL.ja.md`, deterministic standard-library Python scripts where enforcement or data transformation is needed, and focused `unittest` coverage. Skills exchange files or invoke installed commands through documented contracts; they do not import code from another skill directory.

All guards start conservatively. Deterministic policy violations may block only in explicit enforcement mode. Semantic judgments remain advisory and must show evidence. Diagnostic skills are read-only by default. Observers never edit other skills automatically.

## Skill boundaries

### `cmd-guard`

Inspect an actual shell command and identify disallowed command-position tokens such as `grep`, `find`, `cat`, `ls`, and `du`. Suggest `rg`, `fd`, `bat`, `eza`, and `dust`. Ignore prose and arguments. Default to advisory output; return a blocking exit status only with `--enforce`.

### `commit-guard`

Validate staged Git delivery before commit. Enforce the configured English prefix, a multi-paragraph message, and a `Co-Authored-By: Codex` trailer. Treat multi-task staging as an evidence-backed warning because semantic atomicity cannot be proved reliably.

### `task-watch`

Run a long command without `shell=True`, stream and persist combined output, emit heartbeat state, detect idle periods without killing the process by default, and produce a compact evidence-linked summary. This absorbs the earlier `large-output-distiller` concept.

### `fail-ledger`

Store structured failure records as JSONL with symptom, cause, fix, evidence, and a general fix rule. Normalize a fingerprint for recurrence counting. Promotion to a reusable pattern requires at least two matching observations.

### `bug-bundle`

Create a redacted ZIP containing selected logs, images, video-derived keyframes, Git state, and a manifest. Invoke `vfr-extract` when a video is supplied, but report an actionable missing-tool state rather than copying `video-frame-reader`.

### `context-guard`

Read `cc-trace` snapshots and current task material, check freshness deterministically, and generate a bounded semantic comparison prompt. It supports post-compact integrity review and pre-change drift review without modifying `cc-trace`.

### `proof-matrix`

Validate structured feasibility claims and render a Markdown matrix with status, supporting evidence, counterevidence, constraints, retrieval date, and confidence. Unknown or stale evidence must remain explicit.

### `mac-doctor`

Collect read-only macOS diagnostics for an application or executable: OS and architecture, file existence, quarantine, code signature, entitlements, sandbox metadata, and permission guidance. Unobservable TCC state is reported as unknown.

### `skill-meter`

Record privacy-minimal skill outcomes and produce aggregate reports for completion, retries, duration, and manual corrections. It stores no transcript text by default and never edits skills automatically.

## Existing-skill integration

- `task-watch` can wrap local CI/build/test commands and can distill logs later consumed by `ci-monitoring`.
- `bug-bundle` invokes the installed `vfr-extract` interface supplied by `video-frame-reader`.
- `context-guard` reads `.cctrace/latest-summary.md` and related metadata produced by `cc-trace`.
- `commit-guard` hands off naturally to `ci-monitoring` after a successful push, but neither skill depends on the other's files.
- `fail-ledger` and `skill-meter` use compatible event fields but remain independent because their privacy and decision boundaries differ.

## Safety and validation

- No destructive Git or macOS permission mutation.
- No secret values in logs or bundles; likely secret assignments and sensitive filenames are redacted or skipped.
- Scripts use Python's standard library and run on Python 3.11+ unless the feature is explicitly macOS-only.
- Each script has focused unit tests for its parser, validation, redaction, or aggregation behavior.
- Existing uncommitted work in `ci-monitoring/packages/src/index.ts` remains untouched and unstaged.

