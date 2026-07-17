---
name: commit-guard
description: コミットメッセージの構造、Codex の共同作者表記、ステージ済みパスの広がりを検証する。Git コミット作成前やコミット準備状況の確認時に使う。
---

# コミットガード

コミット前にメッセージファイルまたは文字列を検証する。

```bash
python3 scripts/check_commit.py --enforce .git/COMMIT_EDITMSG
python3 scripts/check_commit.py --message "$(printf 'fix: example\\n...')" --repo .
```

最初は advisory モードを使う。`--enforce` が終了コード 2 を返すのは決定的なメッセージエラーだけである。複数コンポーネントのステージングは意味的な原子性を判断するための警告であり、それだけではブロックしない。

push 成功後は自然に `ci-monitoring` へ引き渡す。両スキル間に実行時依存はない。
