#!/usr/bin/env bash
# 動画ファイルを検索して JSON 配列で出力する
# Usage: ./find_video.sh [search_dir]
# Output: {"files": ["./demo.mp4", "./docs/animation.gif"], "count": 2}

SEARCH_DIR="${1:-.}"

if command -v fd &>/dev/null; then
    FILES=$(fd -e mp4 -e gif -e mov "$SEARCH_DIR" 2>/dev/null | sort -u)
else
    FILES=$(find "$SEARCH_DIR" \( -name "*.mp4" -o -name "*.gif" -o -name "*.mov" \) 2>/dev/null | sort -u)
fi

if [ -z "$FILES" ]; then
    echo '{"files": [], "count": 0}'
    exit 0
fi

echo "$FILES" | python3 -c "
import sys, json
files = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps({'files': files, 'count': len(files)}))
"
