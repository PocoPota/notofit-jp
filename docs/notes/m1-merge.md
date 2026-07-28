# M1: 合成の実現性検証

実施日: 2026-07-27
結論: **ofl-font-baker を採用する。合成方式を確定。M1 完了。**

計画書は [../plan.md](../plan.md)、ツール調査は [tools.md](tools.md)。

---

## 1. 検証内容

1ウェイト（wght=400）で ③ 合成を通し、計画書 R1（グリフ名衝突・cmap マージ・
GSUB/GPOS 統合）が解決できるかを確認した。設計値（`SCALE` / `BASELINE_OFFSET`）は
仮値（等倍・オフセット 0）とし、マージが破綻しないことのみを対象とした。

- 環境: Python 3.13.3 / venv
- 依存: fonttools 4.63.0 / ofl-font-baker 0.4.8 / uharfbuzz 0.55.0 / brotli 1.2.0
- 設定: `build/m1-config.json`
- 検証: `build/verify_m1.py` → **21/21 PASS**
- 所要: 合成 約8秒

## 2. 確認できたこと

| 項目             | 結果                                                                 |
| ---------------- | -------------------------------------------------------------------- |
| マージの成否     | 成功。17,936 + 416 → 18,105 グリフ                                    |
| グリフ名衝突     | 4件を自動検出・解決（下記）                                            |
| cmap             | Noto / Outfit 双方の符号位置が欠落ゼロで残る                          |
| 和文の字送り     | 全角の advance が 1000 のまま不変（**方針2の要件を満たす**）           |
| ラテンの出所     | 検証した12字すべて Outfit 由来。advance も Outfit と一致              |
| 縦メトリクス     | hhea / usWin / USE_TYPO_METRICS が Noto と一致。既定 line-height 1.448em で同値 |
| GSUB / GPOS      | Noto の全 feature が残存（GSUB 23種 / GPOS 9種）。Outfit 側も欠落なし  |
| `palt`           | 合成後も動作（`」「` 2.000 → 1.000em）                                 |
| 和欧混植         | `.notdef` なしでシェイプできる                                        |
| 出力形式         | 静的（`fvar` なし）、upem 1000、glyf                                   |

### グリフ名衝突の解決

sub 側（Outfit）のグリフ名が base 側（Noto）と衝突した場合、**sub 側を `{name}.sub` に
リネームして base のグリフを温存する**という挙動。無条件に行われ、stderr に警告が出る。

```
space    → space.sub     （base は U+00A0 で使用）
hyphen   → hyphen.sub    （base は U+00AD, U+2011 で使用）
ellipsis → ellipsis.sub  （base は U+22EF で使用）
uni2215  → uni2215.sub   （base は U+FF0F で使用）
```

同名だが符号位置が重ならないグリフは無関係なグリフである、という判断による。U+0020 の
スペースは `space.sub`（Outfit 由来）が使われ、期待どおり。

## 3. 判明した ofl-font-baker の仕様

README に基づく。設定は JSON を stdin に渡す（CLI: `ofl-font-baker`、
ライブラリ: `import merge_fonts` — パッケージ名と import 名が異なる）。

| 設定                        | 本計画での使い方                                            |
| --------------------------- | ----------------------------------------------------------- |
| `baseFont` / `subFont`      | base = Noto Sans JP、sub = Outfit                            |
| `axes`                      | **可変フォントのインスタンス化を内蔵**（→ 5. 計画への反映）  |
| `scale` / `baselineOffset`  | base / sub 個別に指定できる。sub 側にのみ与える              |
| `output.metricsSource`      | 既定が `"base"`。本計画の要件と一致                          |
| `output.metadataMode`       | 既定 `"merge"`（新規の派生物として name を再構成）           |
| `subFont.excludeCodepoints` | 指定した符号位置を base 側から取る（→ 4.）                   |
| `export.path.woff2`         | woff2 を直接出力できる                                       |
| `output.hinting`            | 既定 `"strip"`。Web 配信では妥当                             |

### 注意点

- **`metricsSource: "base"` は「base を維持し、sub のほうが大きい場合のみ拡張する」**
  という挙動。実際に `OS/2.sTypoAscender/Descender` は Outfit の 1000 / −260 が採用され、
  Noto の 880 / −120 にはならなかった。ただし出力の `USE_TYPO_METRICS` は False
  （Noto を継承）であり、ブラウザは hhea / usWin を見るため**既定の行の高さには影響しない**。
  M4 で実挙動を確認する
- 入力フォントは name テーブルに OFL のライセンス文字列が必要。Noto Sans JP / Outfit とも
  nameID 13 に保持しており問題なし
- 出力時に `GSUB/GPOS Coverage is not sorted by glyph ids.` が多数出るが、fontTools の
  情報メッセージであり出力は正常に読める

## 4. ラテン部分の重複の扱い

Noto Sans JP 自身が持つ欧文グリフは、**cmap ベースの差し替えにより自動的に Outfit 側で
上書きされる**。追加の作業は不要だった。

逆に「Noto 側の字形を残したい符号位置」は `subFont.excludeCodepoints` で個別に指定する。
CJK の組版慣習に合わせたい記号（`①` `◯` `※` `Ⅰ` `℃` など）が対象になる。Outfit が
これらを持つかを含め、**対象の選定は M2 で行う**。

## 5. 計画への反映

- **① 静的インスタンス化を ③ に統合できる。** ofl-font-baker が `axes` でインスタンス化を
  行うため、事前に静的化した中間ファイルを作る必要がない。
  ④ グリフ単位の垂直調整は合成後（＝静的化後）に行うので計画どおり

  > **後の訂正（2026-07-28）**: このとき「和文側は可変のまま ② → ③ でインスタンス化」と
  > 書いたが、これは誤り。`palt` は `FeatureVariations` によりウェイトで内容が変わるため、
  > **和文側は ② の前に静的化する必要がある**。欧文側のみ ③ に統合する。
  > → [palt-weight-boundary.md](palt-weight-boundary.md)
- **R1 は解消。** グリフ名衝突・cmap・GSUB/GPOS の統合はいずれもツール側で処理される
- fontTools の `merge` による自前実装は不要

## 6. 未確定のまま M2 に送る事項

- `SCALE` / `BASELINE_OFFSET` の値（現状は無調整。合成後 H=694 / x=475 に対し
  Noto は H=733 / x=543）
- 欧文の `wght` インスタンス化値
- `excludeCodepoints` の対象
- `palt` の焼き込み比率（その後カテゴリ別に分割し、約物は `kern` に移した。
  → [../yakumono.md](../yakumono.md)）
- `output.metadataMode` を `"merge"` のままにするか

## 7. 再現手順

```bash
python3 -m venv .venv
.venv/bin/python -m pip install fonttools ofl-font-baker uharfbuzz brotli

curl -sSL -o sources/NotoSansJP.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
curl -sSL -o sources/Outfit.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit%5Bwght%5D.ttf"

.venv/bin/python -c "import sys,merge_fonts; sys.argv=['merge_fonts.py']; \
  sys.stdin=open('build/m1-config.json'); merge_fonts.main()"
.venv/bin/python build/verify_m1.py
```

### 検証スクリプトの注意

`build/verify_m1.py` のアウトライン比較は **±1 ユニットの許容差**を持たせている。
マージエンジンと fontTools の instancer で座標の丸め順序が異なり、同一形状でも 1 ユニット
ずれるため（bbox と点数は完全に一致する）。1000upem での 1 ユニットは視覚的に同一。
