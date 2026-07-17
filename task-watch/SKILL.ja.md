---
name: task-watch
description: 長時間のローカルコマンドを、結合出力のライブ表示、ログ保存、idle 報告、終了コード伝播、JSON 証拠要約付きで実行する。ビルド、テスト、その他の大量出力タスクの監視に使う。
---

# タスクウォッチ

必須のリテラル `--` 区切りの後に置いたコマンドをシェルなしで実行する。watcher のオプションと子コマンド引数を混同しないため、区切りを省略しない。

```bash
python3 scripts/task_watch.py --log build.log --json-summary build.json -- make test
```

必要に応じて `--idle-seconds`、`--heartbeat-seconds`、`--summary-lines` を調整する。idle 検出は状態を報告するだけで、子プロセスを停止しない。JSON 要約にはコマンド、結果、所要時間、ログ位置、行番号付きの error/fail/warn 証拠と末尾を残す。

大量のローカル出力の要約をこのスキルに任せる。リモート CI を追跡する `ci-monitoring` を補完する。
