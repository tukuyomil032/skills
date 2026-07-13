#!/usr/bin/env bash
# cctrace: PreCompact hook (matcher: manual)
# Blocks /compact if the context snapshot is missing or stale.
# Stale = snapshot is older than the last compact timestamp.

set -euo pipefail

INPUT=$(cat)

# Extract cwd from hook input
CWD=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('cwd', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$CWD" ]; then
    CWD="$(pwd)"
fi

CCTRACE_DIR="$CWD/.cctrace"
SUMMARY_FILE="$CCTRACE_DIR/latest-summary.md"
LAST_COMPACT="$CCTRACE_DIR/.last-compact-at"

# If cctrace is not initialized for this project, skip silently
if [ ! -d "$CCTRACE_DIR" ]; then
    exit 0
fi

# Case 1: No summary at all — block
if [ ! -f "$SUMMARY_FILE" ]; then
    cat >&2 <<'EOF'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  cctrace: Context Snapshot が未生成です

  /compact の前に以下を実行してください:
    /cctrace:run

  これにより意思決定の経緯が保存されます。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
    exit 2
fi

# Case 2: No previous compact record — snapshot is always fresh
if [ ! -f "$LAST_COMPACT" ]; then
    exit 0
fi

# Case 3: Check if snapshot is newer than last compact
SUMMARY_MTIME=$(stat -f %m "$SUMMARY_FILE" 2>/dev/null || stat -c %Y "$SUMMARY_FILE" 2>/dev/null || echo 0)
COMPACT_MTIME=$(stat -f %m "$LAST_COMPACT" 2>/dev/null || stat -c %Y "$LAST_COMPACT" 2>/dev/null || echo 0)

if [ "$SUMMARY_MTIME" -gt "$COMPACT_MTIME" ]; then
    # Fresh — allow compact
    exit 0
else
    # Stale — block and ask user to re-run cctrace:run
    cat >&2 <<'EOF'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  cctrace: Snapshot が古い状態 (stale) です

  前回の compact 以降の変更が記録されていません。
  /compact の前に以下を実行してください:
    /cctrace:run

  (/cctrace:reset で強制スキップも可能)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
    exit 2
fi
