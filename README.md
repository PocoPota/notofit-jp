# Notofit JP

Outfit と Noto Sans JP を合成した、Web 向けの和欧混植フォント。**開発中。**

Noto Sans JP を使っている既存の日本語サイトを、`font-family` の差し替えだけで置き換え
られることを目標としている。和文を基準に欧文側を合わせるため、行の高さと和文の字送りは
Noto Sans JP と一致する。

両ソースとも SIL Open Font License 1.1。派生物も OFL で配布する。

## ドキュメント

| | |
| --- | --- |
| [docs/plan.md](docs/plan.md) | 開発計画書。目的・方針・アーキテクチャ |
| [docs/yakumono.md](docs/yakumono.md) | 約物の処理と、不採用にした案 |
| [docs/tuner.md](docs/tuner.md) | 和欧調整ツールの仕様 |
| [docs/notes/](docs/notes/) | 調査メモ（ツール構成、M1 の検証、`palt` の境界） |

## 開発

```bash
python3 -m venv .venv
.venv/bin/python -m pip install fonttools brotli ofl-font-baker uharfbuzz playwright
.venv/bin/python -m playwright install chromium

# 元フォントを取得する（リポジトリには含めない）
mkdir -p sources
curl -sSL -o sources/NotoSansJP.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
curl -sSL -o sources/Outfit.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit%5Bwght%5D.ttf"
```

設計値を目視で決めるための調整ツール:

```bash
.venv/bin/python -m notofit.server   # http://127.0.0.1:8765/
```

検証（各スクリプトは単体で実行でき、失敗があれば終了コード 1 を返す）:

```bash
.venv/bin/python tests/test_palt.py       # palt の焼き込み
.venv/bin/python tests/test_yakumono.py   # 約物の kern と feature 削除
.venv/bin/python tests/test_params.py     # SCALE / BASELINE_OFFSET / wght
.venv/bin/python build/verify_m1.py       # 合成の回帰
```

## 構成

```
notofit/       ビルドコア（palt 焼き込み・約物の kern・合成）
tuner/         調整ツールの GUI
config/        調整結果（設計値）
tests/         検証スクリプト
docs/          計画と設計判断の記録
```
