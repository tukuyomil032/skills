---
name: cc-trace
description: >
  `/compact` 実行前に Context Snapshot（Why・根拠 + ファイル変更）を生成し、
  Claude Code セッションをまたいで重要な意思決定の経緯を保存します。
  `/compact` 実行時や、セッションコンテキストを保存したいときに使用します。
  hooks が手動・自動 compact の両方を自動でインターセプトします。
aliases:
  - cct
license: MIT
---

# cctrace — Context Snapshot スキル

`/compact` が会話履歴を消去する前に、技術的な意思決定の「Why（理由）」を保存します。

## コマンド一覧

| コマンド | 説明 |
|---------|------|
| `cctrace:init` | 現在のプロジェクトに cctrace をセットアップする（hooks + `.cctrace/` ディレクトリ） |
| `cctrace:run` | Context Snapshot を今すぐ手動生成する |
| `cctrace:config` | cctrace の設定を表示・変更する |
| `cctrace:status` | スナップショットの鮮度と履歴を表示する |
| `cctrace:list` | 保存済みスナップショットを一覧表示する |
| `cctrace:load` | 保存済みスナップショットを現在のセッションに注入する |
| `cctrace:reset` | 次の /compact 前に再生成を強制する |

---

## cctrace:init

**目的**: 現在のプロジェクトに cctrace をセットアップする。

### 手順

1. `~/.claude/skills/cctrace/` が存在するか確認する。存在しない場合はユーザーに先にインストールするよう伝える:
   ```
   cp -r <dev-path>/cc-trace ~/.claude/skills/cctrace
   chmod +x ~/.claude/skills/cctrace/hooks/*.sh
   ```

2. 現在の作業ディレクトリに `.cctrace/` ディレクトリを作成する。

3. `.cctrace/config.json` をデフォルト設定で作成する:
   ```json
   {
     "model": "claude-sonnet-4-6",
     "detail_level": "full",
     "proactive_threshold": null
   }
   ```

4. AskUserQuestion を使って `.gitignore` への追記を確認する:
   - 選択肢: [追記する, スキップする]
   - 確認された場合: `.cctrace/` を `.gitignore` に追記する（存在しなければ作成する）

5. AskUserQuestion を使って hooks の登録先を選択する:
   - 選択肢 A: `~/.claude/settings.json`（全プロジェクト共通・推奨）
   - 選択肢 B: `.claude/settings.json`（このプロジェクトのみ）

6. 選択した settings.json を読み込む。慎重にパースし、`"hooks"` キーの下に 5 つの hook を追記する。
   **重要**: 既存の hooks を置き換えてはならない — cctrace のエントリのみ追加する。
   上書きを避けるため `python3` または `jq` を使って JSON を安全にマージする。

   追加する hooks:
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

7. 完了サマリーを表示する: 作成されたもの、hooks が登録された場所。

---

## cctrace:run

**目的**: 現在のセッションの会話から Context Snapshot を生成する。

**transcript のパスは UserPromptSubmit hook によってコンテキストに注入されています:**
```
[cctrace] transcript_path: /path/to/transcript.jsonl
```

### 手順

1. `.cctrace/latest-summary.md` がすでに存在するか確認する。
   - 存在する場合: AskUserQuestion — [上書き生成する, キャンセル]
   - 存在しない場合: AskUserQuestion — [生成する, キャンセル]
   - キャンセルされた場合: 停止する。

2. 注入されたコンテキストから transcript のパスを取得する（`[cctrace] transcript_path: ...`）。
   - 見つからない場合は、現在の CWD に対応する `~/.claude/projects/` 内の最新 `.jsonl` を探す。

3. `.cctrace/config.json` からモデルを取得する（デフォルト: `claude-sonnet-4-6`）。

4. トランスクリプト処理スクリプトを実行して構造化プロンプトを構築する:
   ```bash
   python3 ~/.claude/skills/cctrace/scripts/process_transcript.py \
     "<transcript_path>" \
     "<cwd>" \
     "<detail_level>"
   ```
   スクリプトはプロンプト文字列を stdout に出力する。

5. プロンプトを claude CLI にパイプする:
   ```bash
   python3 ~/.claude/skills/cctrace/scripts/process_transcript.py \
     "<transcript_path>" "<cwd>" "<detail_level>" \
   | claude -p --model <model>
   ```
   出力をサマリー内容としてキャプチャする。

6. サマリーを書き込む:
   - アーカイブ: `.cctrace/YYYY-MM-DD-HHmmss.md`
   - 最新: `.cctrace/latest-summary.md`

7. 完了メッセージ: "✓ cctrace スナップショットを保存しました: `.cctrace/latest-summary.md`"

---

## cctrace:config

**目的**: cctrace の設定を表示・編集する。

### 手順

1. `.cctrace/config.json` を読み込む。見つからない場合は `cctrace:init` を実行するよう提案する。

2. 現在の設定をフォーマットされたブロックで表示する。

3. AskUserQuestion（複数選択）: どの設定を変更しますか？
   - model（AI モデル）
   - detail_level（minimal / full）
   - proactive_threshold（コンテキスト使用率 %、null で無効）
   - 変更しない

4. 選択された項目ごとに、AskUserQuestion で新しい値を入力させる。

5. 更新した設定を `.cctrace/config.json` に書き込む。

---

## cctrace:status

**目的**: このプロジェクトにおける cctrace の現在の状態を表示する。

### 手順

1. `.cctrace/` が存在するか確認する。存在しない場合は `cctrace:init` を提案する。

2. 以下を収集して表示する:
   ```
   ── cctrace status ──────────────────────────
   📄 latest-summary.md: 2026-07-13 10:30 (3.2 KB)
   🕐 最終 compact:      2026-07-13 09:55
   ✅ 鮮度:              FRESH（サマリーが最終 compact より新しい）

   📦 アーカイブ: .cctrace/ 内に 5 件のスナップショット
   ⚙️  モデル: claude-sonnet-4-6 | 詳細度: full
   ────────────────────────────────────────────
   ```

3. 鮮度判定ロジック:
   - FRESH ✅: `latest-summary.md` の mtime が `.last-compact-at` の mtime より新しい場合（または `.last-compact-at` が存在しない場合）
   - STALE ⚠️: それ以外の場合
   - MISSING ❌: `latest-summary.md` が存在しない場合

---

## cctrace:list

**目的**: 保存済みの Context Snapshot を一覧表示する。

### 手順

1. `.cctrace/` 内の `latest-summary.md` を除く全 `.md` ファイルを一覧表示する。
   ファイル名（最新順）でソートする。

2. 各ファイルについて以下を表示する:
   - ファイル名（タイムスタンプ）
   - ファイルサイズ
   - フロントマター以外の最初の行（タイトルまたは最初の見出し）

3. アーカイブがない場合: "アーカイブがありません。`cctrace:run` で最初のスナップショットを作成してください。"

---

## cctrace:load

**目的**: 保存済みスナップショットを現在のセッションコンテキストに注入する。

### 手順

1. 引数なしの場合: `latest-summary.md` を読み込む。
   引数がある場合（番号または日付文字列）: `.cctrace/` 内で一致するアーカイブを探す。

2. スナップショットファイルを読み込む。

3. ヘッダー付きで全内容を表示する:
   ```
   ── cctrace: Loaded Context Snapshot ─────────
   [スナップショット内容]
   ─────────────────────────────────────────────
   ```

4. 完了メッセージ: "✓ スナップショットを現セッションに読み込みました。"

---

## cctrace:reset

**目的**: 次の /compact 前にスナップショットの再生成を強制する。

### 手順

1. AskUserQuestion を使って確認する:
   "`.last-compact-at` を削除して次の /compact で cctrace:run を強制しますか？"
   選択肢: [リセットする, キャンセル]

2. 確認された場合: `.cctrace/.last-compact-at` を削除する。

3. 完了メッセージ: "✓ リセット完了。次の /compact 時に cctrace:run が必要になります。"

---

## 全コマンド共通の注意事項

- **CWD**: 常にプロジェクトの作業ディレクトリ（`.cctrace/` が存在する場所）を使用する。
- **config のフォールバック**: `.cctrace/config.json` が存在しない場合はデフォルト値を無音で使用する。
- **エラーハンドリング**: Bash コマンドが失敗した場合は何が起きたかを説明し、`cctrace:init` を提案する。
- **transcript パス**: UserPromptSubmit hook によって `[cctrace] transcript_path: <path>` としてコンテキストに注入される。

---

## 注意事項

- このスキルは `cctrace:init` を実行してからでないと動作しません
- hooks は `~/.claude/settings.json` に登録され、グローバルに機能します
- `.cctrace/` ディレクトリが存在するプロジェクトのみ capture されます
