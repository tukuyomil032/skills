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

対応文法は、単純コマンド、代入、リダイレクトと heredoc、パイプラインとリスト区切り、`if` / `while` / `until` のコマンド位置、グループ、関数定義、`sudo` / `env` / `command` / `time` ラッパー、command / backtick / process substitution である。算術展開はデータとして扱う。

引用なし heredoc 本文の command / backtick substitution は検査し、引用付き本文とすべての heredoc delimiter 語はリテラルとして扱う。分離・連結どちらの `env -S` 文字列も再帰的に解析する。`command -v` / `-V` と `sudo -l` / `-e` はコマンド語より前にある場合だけ非実行モードとして扱う。コマンド語内の展開はすべて indeterminate にするが、既知コマンドの引数内にある同じ展開は clear のままにする。

JSON には常に `status`、`mode`、`requested_mode`、`indeterminate`、`violations` が入る。`case`、`for`、`select`、`coproc`、`[[...]]`、here-string、parameter expansion などの対応外文法では、`status` を `indeterminate`、`mode` を `advisory` に戻し、`--enforce` 指定時もブロックしない。手動確認へ切り替える。このチェッカーは完全な Bash パーサーではない。
