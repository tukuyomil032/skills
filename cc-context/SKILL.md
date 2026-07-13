---
name: cctrace
description: >
  Generates a Context Snapshot (Why/rationale + file changes) before /compact to preserve
  important decision history across Claude Code sessions. Use when running /compact or when
  you need to save session context. Hooks auto-intercept both manual and auto-compact.
aliases:
  - cct
license: MIT
---

# cctrace — Context Snapshot Skill

Saves the "Why" behind technical decisions before `/compact` wipes the conversation history.

## Commands

| Command | Description |
|---------|-------------|
| `cctrace:init` | Set up cctrace for the current project (hooks + .cctrace/ dir) |
| `cctrace:run` | Manually generate a Context Snapshot now |
| `cctrace:config` | View/change cctrace configuration |
| `cctrace:status` | Show freshness and snapshot history |
| `cctrace:list` | List all saved snapshots |
| `cctrace:load` | Inject a saved snapshot into the current session |
| `cctrace:reset` | Force re-generation before next /compact |

---

## cctrace:init

**Purpose**: Set up cctrace for the current project.

### Steps

1. Check that `~/.claude/skills/cctrace/` exists. If not, tell the user to install cctrace first:
   ```
   cp -r <dev-path>/cc-context ~/.claude/skills/cctrace
   chmod +x ~/.claude/skills/cctrace/hooks/*.sh
   ```

2. Create `.cctrace/` directory in the current working directory.

3. Create `.cctrace/config.json` with defaults:
   ```json
   {
     "model": "claude-sonnet-4-6",
     "detail_level": "full",
     "proactive_threshold": null
   }
   ```

4. Use AskUserQuestion to confirm `.gitignore` update:
   - Options: [追記する, スキップする]
   - If confirmed: append `.cctrace/` to `.gitignore` (create if it doesn't exist)

5. Use AskUserQuestion to choose where to register hooks:
   - Option A: `~/.claude/settings.json` (全プロジェクト共通・推奨)
   - Option B: `.claude/settings.json` (このプロジェクトのみ)

6. Read the chosen settings.json. Parse it carefully, then append the 5 hooks under `"hooks"` key.
   **Important**: Do NOT replace existing hooks — only add the cctrace entries.
   Use `python3` or `jq` to safely merge JSON rather than overwriting.

   Hooks to add:
   ```json
   {
     "PreCompact": [
       {
         "matcher": "manual",
         "hooks": [{ "type": "command", "command": "~/.claude/skills/cctrace/hooks/precompact-manual.sh", "timeout": 10 }]
       },
       {
         "matcher": "auto",
         "hooks": [{ "type": "command", "command": "~/.claude/skills/cctrace/hooks/precompact-auto.sh", "timeout": 120 }]
       }
     ],
     "PostCompact": [
       { "hooks": [{ "type": "command", "command": "~/.claude/skills/cctrace/hooks/postcompact.sh", "timeout": 10 }] }
     ],
     "SessionStart": [
       { "hooks": [{ "type": "command", "command": "~/.claude/skills/cctrace/hooks/session-start.sh", "timeout": 15 }] }
     ],
     "UserPromptSubmit": [
       { "hooks": [{ "type": "command", "command": "~/.claude/skills/cctrace/hooks/user-prompt-submit.sh", "timeout": 5 }] }
     ]
   }
   ```

7. Show completion summary: what was created, where hooks were registered.

---

## cctrace:run

**Purpose**: Generate a Context Snapshot from the current session's conversation.

**The transcript path is injected into your context by the UserPromptSubmit hook as:**
```
[cctrace] transcript_path: /path/to/transcript.jsonl
```

### Steps

1. Check if `.cctrace/latest-summary.md` already exists.
   - If exists: use AskUserQuestion — [上書き生成する, キャンセル]
   - If not exists: use AskUserQuestion — [生成する, キャンセル]
   - If cancelled: stop.

2. Get the transcript path from the injected context (`[cctrace] transcript_path: ...`).
   - If not found, look for the most recent `.jsonl` in `~/.claude/projects/` matching the current CWD.

3. Get the model from `.cctrace/config.json` (default: `claude-sonnet-4-6`).

4. Run the transcript processor to build a structured prompt:
   ```bash
   python3 ~/.claude/skills/cctrace/scripts/process_transcript.py \
     "<transcript_path>" \
     "<cwd>" \
     "<detail_level>"
   ```
   The script outputs a prompt string to stdout.

5. Pipe the prompt to claude CLI:
   ```bash
   python3 ~/.claude/skills/cctrace/scripts/process_transcript.py \
     "<transcript_path>" "<cwd>" "<detail_level>" \
   | claude -p --model <model>
   ```
   Capture the output as the summary content.

6. Write the summary:
   - Archive: `.cctrace/YYYY-MM-DD-HHmmss.md`
   - Latest: `.cctrace/latest-summary.md`

7. Confirm: "✓ cctrace スナップショットを保存しました: `.cctrace/latest-summary.md`"

---

## cctrace:config

**Purpose**: View and edit cctrace settings.

### Steps

1. Read `.cctrace/config.json`. If not found, suggest running `cctrace:init` first.

2. Display current settings in a formatted block.

3. Use AskUserQuestion (multi-select): どの設定を変更しますか？
   - model（AI モデル）
   - detail_level（minimal / full）
   - proactive_threshold（コンテキスト使用率 %, null で無効）
   - 変更しない

4. For each selected item, prompt for new value via AskUserQuestion.

5. Write updated config to `.cctrace/config.json`.

---

## cctrace:status

**Purpose**: Show the current state of cctrace in this project.

### Steps

1. Check if `.cctrace/` exists. If not, suggest `cctrace:init`.

2. Collect and display:
   ```
   ── cctrace status ──────────────────────────
   📄 latest-summary.md: 2026-07-13 10:30 (3.2 KB)
   🕐 last compact:      2026-07-13 09:55
   ✅ freshness:         FRESH (summary is newer than last compact)

   📦 archives: 5 snapshots in .cctrace/
   ⚙️  model: claude-sonnet-4-6 | detail: full
   ────────────────────────────────────────────
   ```

3. Freshness logic:
   - FRESH ✅ if `latest-summary.md` mtime > `.last-compact-at` mtime (or `.last-compact-at` doesn't exist)
   - STALE ⚠️ otherwise
   - MISSING ❌ if `latest-summary.md` doesn't exist

---

## cctrace:list

**Purpose**: List all saved Context Snapshots.

### Steps

1. List all `.md` files in `.cctrace/` excluding `latest-summary.md`.
   Sort by filename (newest first).

2. For each file, show:
   - Filename (timestamp)
   - File size
   - First non-frontmatter line (title or first heading)

3. If no archives: "アーカイブがありません。`cctrace:run` で最初のスナップショットを作成してください。"

---

## cctrace:load

**Purpose**: Inject a saved snapshot into the current session context.

### Steps

1. If no argument: load `latest-summary.md`.
   If argument provided (number or date string): find the matching archive in `.cctrace/`.

2. Read the snapshot file.

3. Output the full content as a visible block with header:
   ```
   ── cctrace: Loaded Context Snapshot ─────────
   [snapshot content]
   ─────────────────────────────────────────────
   ```

4. Confirm: "✓ スナップショットを現セッションに読み込みました。"

---

## cctrace:reset

**Purpose**: Force re-generation of a snapshot before the next /compact.

### Steps

1. Use AskUserQuestion:
   "`.last-compact-at` を削除して次の /compact で cctrace:run を強制しますか？"
   Options: [リセットする, キャンセル]

2. If confirmed: delete `.cctrace/.last-compact-at`.

3. Confirm: "✓ リセット完了。次の /compact 時に cctrace:run が必要になります。"

---

## Notes for All Commands

- **CWD**: Always use the project's working directory (where `.cctrace/` lives).
- **Config fallback**: If `.cctrace/config.json` is missing, use defaults silently.
- **Error handling**: If any Bash command fails, explain what happened and suggest `cctrace:init`.
- **Transcript path**: Injected by UserPromptSubmit hook as `[cctrace] transcript_path: <path>`
