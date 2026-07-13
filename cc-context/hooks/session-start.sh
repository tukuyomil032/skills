#!/usr/bin/env bash
# cctrace: SessionStart hook
# If a latest-summary.md exists in the current project,
# inject it into Claude's context so the new session "remembers" the previous one.

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
    exit 0
fi

SUMMARY_FILE="$CWD/.cctrace/latest-summary.md"

if [ ! -f "$SUMMARY_FILE" ]; then
    exit 0
fi

# Read summary content (cap at 8000 chars to stay within additionalContext limit)
SUMMARY=$(head -c 8000 "$SUMMARY_FILE")

if [ -z "$SUMMARY" ]; then
    exit 0
fi

# Get snapshot metadata for display
SNAPSHOT_DATE=$(head -5 "$SUMMARY_FILE" | grep -E '^generated:' | sed 's/generated: //' | tr -d '"' || echo "unknown")

# Output additionalContext JSON
python3 -c "
import json, sys

summary = sys.argv[1]
date = sys.argv[2]

context = f'''[cctrace] 前回セッションの Context Snapshot が見つかりました ({date})

{summary}

---
このスナップショットは compact 前に cctrace が保存しました。
前回の意思決定の経緯や未解決の課題を参照できます。'''

output = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': context
    }
}

print(json.dumps(output))
" "$SUMMARY" "$SNAPSHOT_DATE" 2>/dev/null

exit 0
