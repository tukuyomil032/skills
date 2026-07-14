#!/usr/bin/env bash
# cctrace: PreCompact hook (matcher: auto)
# Auto-generates a Context Snapshot when auto-compact fires.
# No user confirmation — runs silently in background.

set -euo pipefail

INPUT=$(cat)

# Extract cwd and transcript_path from hook input
CWD=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('cwd', ''))
except Exception:
    print('')
" 2>/dev/null)

TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$CWD" ]; then
    CWD="$(pwd)"
fi

CCTRACE_DIR="$CWD/.cctrace"

# If cctrace is not initialized for this project, skip silently
if [ ! -d "$CCTRACE_DIR" ]; then
    exit 0
fi

# Load model from config
MODEL="claude-sonnet-4-6"
CONFIG_FILE="$CCTRACE_DIR/config.json"
if [ -f "$CONFIG_FILE" ]; then
    MODEL=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('model', 'claude-sonnet-4-6'))
except Exception:
    print('claude-sonnet-4-6')
" 2>/dev/null || echo "claude-sonnet-4-6")
fi

# Load detail level
DETAIL="full"
if [ -f "$CONFIG_FILE" ]; then
    DETAIL=$(python3 -c "
import json
try:
    d = json.load(open('$CONFIG_FILE'))
    print(d.get('detail_level', 'full'))
except Exception:
    print('full')
" 2>/dev/null || echo "full")
fi

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROCESS_SCRIPT="$SKILL_DIR/scripts/process_transcript.py"

if [ ! -f "$PROCESS_SCRIPT" ]; then
    # Fallback: look in default install location
    PROCESS_SCRIPT="$HOME/.claude/skills/cctrace/scripts/process_transcript.py"
fi

if [ ! -f "$PROCESS_SCRIPT" ]; then
    exit 0
fi

TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
ARCHIVE_FILE="$CCTRACE_DIR/${TIMESTAMP}.md"
LATEST_FILE="$CCTRACE_DIR/latest-summary.md"

# Generate the summary prompt
PROMPT=$(python3 "$PROCESS_SCRIPT" "$TRANSCRIPT" "$CWD" "$DETAIL" 2>/dev/null)

if [ -z "$PROMPT" ]; then
    exit 0
fi

# Call claude CLI to generate summary
# Write to archive first, then copy to latest
if echo "$PROMPT" | claude -p --model "$MODEL" --max-tokens 2048 > "$ARCHIVE_FILE" 2>/dev/null; then
    if [ -s "$ARCHIVE_FILE" ]; then
        cp "$ARCHIVE_FILE" "$LATEST_FILE"
    fi
fi

exit 0
