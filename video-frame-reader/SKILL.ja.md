# video-frame-reader

動画ファイル（MP4/GIF/MOV）からキーフレームのみを抽出してClaudeに渡すスキル。全フレームと比べてコストを大幅削減しながら、アニメーションの流れを把握できる。

## 使いどころ

- アニメーションの動きが想定と違うとき
- UIの画面遷移バグをスクショ1枚では伝えにくいとき
- 歌詞ハイライト・自動スクロールなど複雑な動きの確認

## 構文

```
/video-frame-reader [動画パス] [--format jpeg|png] [--threshold 10-90]
/vfr [動画パス] [--format jpeg|png] [--threshold 10-90]
```

| パラメータ | デフォルト | 説明 |
|-----------|----------|------|
| `動画パス` | 省略可 | MP4/GIF/MOV のパス。**省略するとプロジェクト内を自動検索** |
| `--format` | `jpeg` | `jpeg`（小さい）または `png`（高精度） |
| `--threshold` | `30` | キーフレームとみなすピクセル差分 %（小さいほど多く抽出） |

## Claudeへの指示

### Step 0 — ファイルパスが省略されていたら find_video.sh を実行

```bash
bash /Users/hosiyomi322/Documents/dev/tukuyomil032-skills/video-frame-reader/scripts/find_video.sh
```

JSON出力 `{"files": [...], "count": N}` を解析し、番号リストで提示:

```
以下の動画ファイルが見つかりました:
1. ./demo.mp4
2. ./docs/animation.gif

どれを分析しますか？（番号で回答）
```

`count` が 0 なら「動画ファイルが見つかりませんでした」と伝えて終了。ユーザーの返答を待ち、選択されたパスを使用する。

### Step 1 — スクリプトを実行

```bash
uv run --project /Users/hosiyomi322/Documents/dev/tukuyomil032-skills/video-frame-reader \
  python /Users/hosiyomi322/Documents/dev/tukuyomil032-skills/video-frame-reader/scripts/extract_frames.py \
  <動画パス> [--format jpeg] [--threshold 30]
```

stdoutの1行JSONをキャプチャする。

### Step 2 — JSONを解析

- `output_path`: 生成された画像のパス
- `frames_extracted`: 抽出フレーム数
- `timestamps`: 各フレームのタイムスタンプ（秒）
- `cost_comparison`: コスト比較データ

### Step 3 — 画像をReadツールで読み込む

`output_path` のファイルをReadツールで読み込み、会話に注入する。

### Step 4 — フレームを左から右へ分析

- 各フレーム間で何が変化したか
- 不自然な遷移・バグ・予期しない状態がないか

### Step 5 — コスト比較表を表示

```markdown
| 方法 | サイズ | トークン | 推定コスト |
|------|--------|----------|------------|
| 全フレーム PNG | XXX KB | X,XXX | XX円 |
| 全フレーム JPEG | XXX KB | X,XXX | XX円 |
| **キーフレームのみ（今回）** | XXX KB | X,XXX | **XX円** |
```
