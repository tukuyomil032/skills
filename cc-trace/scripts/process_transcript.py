#!/usr/bin/env python3
"""
cctrace: transcript processor + prompt builder
Usage: process_transcript.py <transcript_path> <cwd> [detail_level]

Reads a Claude Code transcript.jsonl, extracts key information,
and outputs a structured prompt for `claude -p` to generate a cctrace summary.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def read_transcript(path: str) -> list[dict]:
    """Read and parse transcript.jsonl (JSON Lines format)."""
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
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
    """Extract human/assistant messages from transcript entries.

    Handles two formats:
    - Nested: entry["type"] in ("user", "assistant"), message in entry["message"]
    - Flat: entry["role"] in ("user", "assistant"), content in entry["content"]
    """
    messages = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        entry_type = entry.get("type", "")

        # --- Nested format (Claude Code transcript.jsonl) ---
        # entry["type"] = "user" | "assistant", actual message is in entry["message"]
        if entry_type in ("user", "assistant") and "message" in entry:
            msg = entry["message"]
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", entry_type)
            content = msg.get("content", "")
            content = _extract_content(content, messages)
            if content:
                messages.append({"role": role, "content": content})

        # --- Flat format (legacy / SDK format) ---
        elif entry.get("role") in ("user", "human", "assistant"):
            role = entry["role"]
            content = entry.get("content", "")
            content = _extract_content(content, messages)
            if content:
                messages.append({"role": role, "content": content})

    return messages


def _extract_content(content, messages: list) -> str:
    """Flatten content blocks to text, side-loading tool_use entries."""
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                messages.append(
                    {
                        "role": "tool_use",
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    }
                )
            # skip: thinking, tool_result, image, etc.
        return "\n".join(t for t in text_parts if t)
    elif isinstance(content, str):
        return content
    return ""


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
            for pat in [
                r">\s*([^\s|&;]+\.(py|ts|tsx|js|jsx|rs|swift|go|java|kt|md|json|yml|yaml|sh|css|html))",
                r"touch\s+([^\s]+)",
                r"tee\s+([^\s]+)",
            ]:
                for m in re.finditer(pat, cmd):
                    path = m.group(1)
                    if path not in seen:
                        changed_files.append(path)
                        seen.add(path)

    return changed_files


# Keywords indicating decision-making in Japanese and English
# Based on real transcript analysis across 5+ projects (tukuyomil032-skills, perch, docky, etc.)
DECISION_PATTERNS = [
    # === 意思決定・採用 ===
    r"を採用(?:した|しました|する)|採用しました",
    r"方針(?:転換|を(?:立て|変更|変え)|が(?:決まり|固まり))",
    r"方式(?:確定|推奨|を採用|で行く|にした)",
    r"設計(?:方針|として(?:は)?|にします)",
    r"アプローチ(?:を取|を採用|として)",
    r"案[A-Ca-c①②③](?:を採用|推奨|確定|で行く)?|推奨案",
    r"使うことにした|に決めた|にすることにした|で行くことにした",
    r"選択しました|決定しました|確定しました|確定した",
    # === 却下・比較 ===
    r"却下(?:した|しました|の候補)?|見送り|見送った",
    r"不採用(?:の|だ|にした)|後押し材料",
    r"やめました|やめた|辞めてください",
    r"ダサい|ダサくて",  # ユーザー固有の審美的却下
    r"合わない|向いていない|合いません|向いてない",
    r"使わない|使いません|使用しない",
    r"〜より.*方が|より.*方式.*が堅牢|より.*の方が",
    # === 理由・根拠 ===
    r"なぜこれを言うかというと|→なぜ",  # ユーザー特徴パターン（特異性高）
    r"なぜなら[、。\s]|なぜかというと",
    r"根拠(?:が|を|として|は|になる)",
    r"懸念(?:が|を|した|点|として)",
    r"(?:が|は)ポイント|重要なポイント|ポイントとして",
    r"これを防ぐため|を防ぐために|防ぐため",
    r"というのも[、。\s]",
    r"のため[、。\s]|ためです[。\s]|ためになっています",
    r"理由(?:は|として|が)|という理由",
    r"の観点から|観点として",
    r"おかげで|ことで(?:実現|解決|対応)",
    # === 制約・要件発見 ===
    r"非対応|使用不可",
    r"権限がない|権限がないため",
    r"制限されて|制限があ(?:り|る)|の制限(?:が|として)",
    r"着手できない|着手できないため",
    r"hook.*使えない|から使用不可|hook.*使用不可",
    r"entitlement.*必要|entitlement.*が必要",
    r"が必要です|が必要(?:な|になっ|とな)",
    r"しなければ(?:なら|いけ)|できません|不可能",
    r"という制約|制約として|制約上",
    # === 技術検討 ===
    r"アーキテクチャ(?:案|判断|を)?|アーキ(?:判断|決定)",
    r"を検討|と比較(?:して|した)|比較検討",
    r"悩んだ|迷った|検討した|調べた結果",
    r"選択肢(?:として|が|は)|候補(?:として|が|は)",
    r"トレードオフ|trade.?off",
    # === English (high-specificity only) ===
    r"went with|opted for|decided to use|chose to use",
    r"instead of|rather than",
    r"rejected|avoid(?:ing)?|not using|skip(?:ped|ping)?",
    r"because of|due to|in order to|so that",
    r"trade.?offs?|alternative|candidate",
    r"constraint|requirement|limitation|cannot|impossible",
    r"the reason(?:\s+is|\s+was|:)|reason for",
    # === ユーザー固有の口語パターン (tukuyomil032) ===
    r"感じで(?:行き|いき|進め)",  # 「感じで行きたい」
    r"一旦(?:次|これ|ここ|先に)",  # 作業区切り指示
    r"そもそも[、。\s]",  # 前提への立ち返り
    r"なんで.*んです(?:か|よ)?|なんで.*のか",  # 不満・確認
    r"ちゃんと.*(?:読め|調べ|確認)",  # 要求の強調
    r"普通に.*(?:したい|して|できる)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DECISION_PATTERNS]

TODO_PATTERNS = [
    re.compile(r"TODO|FIXME|HACK|XXX", re.IGNORECASE),
    re.compile(
        r"次(?:のフェーズ|回|のステップ|の実装|のタスク|で)|後で|後回し|将来", re.IGNORECASE
    ),
    re.compile(r"未解決|未実装|要対応|要確認|要検討|要修正", re.IGNORECASE),
    re.compile(r"next step|later|follow.?up|pending|to.?do", re.IGNORECASE),
    re.compile(r"Phase \d+|フェーズ\d+|第\d+フェーズ", re.IGNORECASE),
    re.compile(r"一旦(?:次|ここまで|保留)|一旦.*後で", re.IGNORECASE),
    re.compile(r"既知の(?:制限|問題|課題)|known issue", re.IGNORECASE),
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
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if log.returncode == 0 and log.stdout.strip():
            result_parts.append("Recent commits:\n" + log.stdout.strip())
    except Exception:
        pass

    try:
        diff = subprocess.run(
            ["git", "diff", "--name-status", "HEAD~1", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
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

    file_list = (
        "\n".join(f"  - {f}" for f in file_changes[:30]) if file_changes else "  (none detected)"
    )

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

Generate a cctrace Context Snapshot in this exact format. Output raw markdown — NO code fences, NO ```markdown wrapper, NO preamble:

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

Output ONLY the above markdown. Do not wrap in code fences."""

    return prompt


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: process_transcript.py <transcript_path> <cwd> [detail_level]", file=sys.stderr
        )
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
