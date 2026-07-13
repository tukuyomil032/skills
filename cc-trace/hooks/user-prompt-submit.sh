#!/usr/bin/env bash
# cctrace: UserPromptSubmit hook
# Injects the transcript_path into every prompt's additionalContext.
# This allows cctrace:run (invoked as a Claude skill) to know where the transcript is.

set -euo pipefail

INPUT=$(cat)

# Extract transcript_path from hook input
TRANSCRIPT=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$TRANSCRIPT" ]; then
    exit 0
fi

# Output additionalContext with transcript path
python3 -c "
import json, sys

transcript = sys.argv[1]

output = {
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': f'[cctrace] transcript_path: {transcript}'
    }
}

print(json.dumps(output))
" "$TRANSCRIPT" 2>/dev/null

exit 0
