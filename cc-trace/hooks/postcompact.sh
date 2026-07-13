#!/usr/bin/env bash
# cctrace: PostCompact hook
# Records the timestamp of the last successful compact.
# This is used by precompact-manual.sh to detect stale snapshots.

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

# Only record if cctrace is initialized for this project
if [ -d "$CCTRACE_DIR" ]; then
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$CCTRACE_DIR/.last-compact-at"
fi

exit 0
