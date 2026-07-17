---
name: cmd-guard
description: 実行位置にある禁止ユーティリティを検出し、承認済みの代替を提案する。grep、find、cat、ls、du を使う可能性があるコマンドを実行・提示する前に自動で使う。
---

# コマンドガード

シェルコマンドの実行前にチェッカーを使う。文字列を解析するだけで、コマンド自体は実行しない。

まず advisory モードで確認する。ワークフローが明示的にブロックを要求するときだけ `--enforce` を使う。違反時は終了コード 2 になる。

```bash
python3 scripts/check_command.py "find . -name '*.py' | grep test"
python3 scripts/check_command.py --enforce < command.txt
```

決定的な JSON にある各 token を、提示された replacement へ置き換える。
