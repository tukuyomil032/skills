#!/usr/bin/env python3
"""
cctrace: transcript processor + prompt builder
Usage: process_transcript.py <transcript_path> <cwd> [detail_level]

Reads a Claude Code transcript.jsonl, extracts key information,
and outputs a structured prompt for `claude -p` to generate a cctrace summary.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime


def read_transcript(path: str) -> list[dict]:
    """Read and parse transcript.jsonl (JSON Lines format)."""
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return entries


def extract_messages(entries: list[dict]) -> list[dict]:
    """Extract human/assistant messages from transcript entries."""
    messages = []
    for entry in entries:
        # Handle various transcript formats
        if isinstance(entry, dict):
            role = entry.get("role", "")
            content = entry.get("content", "")

            # Handle content as list of blocks
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            # Extract tool use info
                            messages.append({
                                "role": "tool_use",
                                "name": block.get("name", ""),
                                "input": block.get("input", {}),
                            })
                content = "\n".join(text_parts)

            if role in ("user", "human", "assistant") and content:
                messages.append({"role": role, "content": str(content)})

    return messages


def extract_file_changes(messages: list[dict]) -> list[str]:
    """Extract file paths that were created or modified."""
    changed_files = []
    seen = set()

    for msg in messages:
        if msg.get("role") != "tool_use":
            continue
        name = msg.get("name", "")
        inp = msg.get("input", {})

        if name in ("Write", "Edit", "NotebookEdit"):
            path = inp.get("file_path") or inp.get("path") or ""
            if path and path not in seen:
                changed_files.append(path)
                seen.add(path)
        elif name == "Bash":
            cmd = inp.get("command", "")
            # Look for file operations in bash commands
            for pat in [r'>\s*([^\s|&;]+\.(py|ts|tsx|js|jsx|rs|swift|go|java|kt|md|json|yml|yaml|sh|css|html))',
                        r'touch\s+([^\s]+)',
                        r'tee\s+([^\s]+)']:
                for m in re.finditer(pat, cmd):
                    path = m.group(1)
                    if path not in seen:
                        changed_files.append(path)
                        seen.add(path)

    return changed_files


# Keywords indicating decision-making in Japanese and English
DECISION_PATTERNS = [
    # Japanese
    r'採用|選択|選ぶ|決定|使用する|使うことにした|にした|にします',
    r'却下|見送り|やめる|やめた|使わない|不採用|合わない|向いていない',
    r'理由|なぜなら|なので|ため|から|ことで|おかげで',
    r'代わりに|別の|より|に比べて|と比較|よりも',
    r'検討|考えた|悩んだ|迷った|比較|調べた',
    r'制約|要件|条件|必要|しなければ|できない|不可能',
    # English
    r'adopt|chose|decided|using|went with|picked|selected',
    r'reject|avoid|not using|instead of|rather than|skip',
    r'because|since|therefore|reason|due to|in order to',
    r'trade.?off|alternative|option|candidate|comparison',
    r'constraint|requirement|limitation|must|cannot|impossible',
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DECISION_PATTERNS]

TODO_PATTERNS = [
    re.compile(r'TODO|FIXME|HACK|XXX', re.IGNORECASE),
    re.compile(r'次(のフェーズ|回|のステップ|の実装|で)|後で|後回し|将来', re.IGNORECASE),
    re.compile(r'未解決|未実装|要対応|要確認|要検討', re.IGNORECASE),
    re.compile(r'next step|later|follow.?up|pending|to do', re.IGNORECASE),
]


def is_decision_related(text: str) -> bool:
    return any(p.search(text) for p in COMPILED_PATTERNS)


def has_todo(text: str) -> bool:
    return any(p.search(text) for p in TODO_PATTERNS)


def extract_key_segments(messages: list[dict], max_chars: int = 6000) -> str:
    """Extract the most decision-relevant segments from messages."""
    segments = []
    total = 0

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content or role == "tool_use":
            continue

        # Prioritize decision-related content
        if is_decision_related(content) or has_todo(content):
            # Trim individual messages to avoid overflow
            trimmed = content[:800] if len(content) > 800 else content
            prefix = "User" if role in ("user", "human") else "Assistant"
            segment = f"[{prefix}]: {trimmed}"
            segments.append(segment)
            total += len(segment)

        if total > max_chars:
            break

    return "\n\n".join(segments)


def get_git_summary(cwd: str) -> str:
    """Get a brief git log/diff summary for context."""
    import subprocess
    result_parts = []

    try:
        log = subprocess.run(
            ["git", "log", "--oneline", "-10", "--no-merges"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        if log.returncode == 0 and log.stdout.strip():
            result_parts.append("Recent commits:\n" + log.stdout.strip())
    except Exception:
        pass

    try:
        diff = subprocess.run(
            ["git", "diff", "--name-status", "HEAD~1", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        if diff.returncode == 0 and diff.stdout.strip():
            result_parts.append("Latest diff (files):\n" + diff.stdout.strip()[:800])
    except Exception:
        pass

    return "\n\n".join(result_parts)


def build_prompt(
    key_segments: str,
    file_changes: list[str],
    git_summary: str,
    cwd: str,
    detail_level: str,
) -> str:
    project_name = Path(cwd).name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    file_list = "\n".join(f"  - {f}" for f in file_changes[:30]) if file_changes else "  (none detected)"

    git_section = f"\n\n## Git Changes\n{git_summary}" if git_summary else ""

    detail_instruction = (
        "Be thorough: include all rationale, rejected alternatives, constraints discovered."
        if detail_level == "full"
        else "Be concise: key decisions and next steps only."
    )

    prompt = f"""You are generating a cctrace Context Snapshot — a structured markdown document that preserves the important decision history from a Claude Code session before context compaction.

{detail_instruction}

## Session Context
- Project: {project_name}
- CWD: {cwd}
- Generated: {now}

## Files Changed
{file_list}{git_section}

## Key Conversation Segments (decision-related excerpts)
{key_segments if key_segments else "(transcript segments unavailable)"}

---

Generate a cctrace Context Snapshot in this exact markdown format:

```markdown
---
generated: {now}
project: {project_name}
---

# cctrace: Context Snapshot

## セッション概要
(1-2 sentences: what was built/worked on this session)

## 意思決定の経緯（Why）
### 採用した技術・設計
- **[name]**: [reason chosen]
  - 却下した候補: [A]（reason）, [B]（reason）  ← include only if alternatives were considered

### 重要な制約・要件
- (discovered constraints, requirements, non-obvious rules)

## 変更されたファイル
- `path/to/file` — [what changed and why]

## 未解決の課題・次のステップ
- [ ] (open items, deferred work, known issues)
```

Output ONLY the markdown content. No explanation, no preamble."""

    return prompt


def main():
    if len(sys.argv) < 3:
        print("Usage: process_transcript.py <transcript_path> <cwd> [detail_level]", file=sys.stderr)
        sys.exit(1)

    transcript_path = sys.argv[1]
    cwd = sys.argv[2]
    detail_level = sys.argv[3] if len(sys.argv) > 3 else "full"

    entries = read_transcript(transcript_path)
    if not entries:
        # Fallback: output a minimal prompt even without transcript
        print(build_prompt("", [], "", cwd, detail_level))
        return

    messages = extract_messages(entries)
    file_changes = extract_file_changes(messages)
    key_segments = extract_key_segments(messages)
    git_summary = get_git_summary(cwd)

    prompt = build_prompt(key_segments, file_changes, git_summary, cwd, detail_level)
    print(prompt)


if __name__ == "__main__":
    main()
