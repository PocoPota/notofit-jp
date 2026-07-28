# ツール調査メモ

最終更新: 2026-07-28

Notofit JP のビルドに使うツールと、その役割。**構成は M1 で確定した**（検証の詳細は
[m1-merge.md](m1-merge.md)）。計画書は [../plan.md](../plan.md)。

---

## 1. 合成エンジン

### ofl-font-baker

| 項目       | 内容                                            |
| ---------- | ----------------------------------------------- |
| 配布       | PyPI: `pip install ofl-font-baker`               |
| ライセンス | MIT（macOS GUI 版は別リポジトリ・AGPL v3.0）     |
| リポジトリ | https://github.com/yamatoiizuka/ofl-font-baker   |
| 用途       | ③ 合成                                           |

**base フォント（CJK）に sub フォント（ラテン）を cmap ベースで差し替えてマージする**
設計。本計画の方針2（Noto Sans JP を基準に Outfit を合わせる）と一致するため、
`base = Noto Sans JP` / `sub = Outfit` の当てはめになる。

設定項目と計画書の対応:

| 設定                | 対応する項目                                          |
| ------------------- | ----------------------------------------------------- |
| `scale`             | `SCALE`（③ の欧文拡縮）                                |
| `baseline`          | `BASELINE_OFFSET`                                      |
| `metricsSource`     | 縦メトリクスの取得元。本計画では `base`（Noto 側）となるはず |
| `excludeCodepoints` | ラテン部分の重複解決に使えそう                         |
| `metadataMode`      | name テーブルの継承方式                                |

その他、グリフ名衝突の検出、UPM 変換時の layout テーブルのスケーリングを持つ。
**計画書の R1（グリフ名衝突・cmap マージ・GSUB/GPOS 統合）が正面から扱われている領域。**

出力は `.otf` / `.ttf` / `.woff2`。可変フォントの静的インスタンス出力にも対応する。

**使い方**

インストール名と import 名が異なる。パッケージは `ofl-font-baker`、モジュールは
`merge_fonts`。設定 JSON を stdin に渡す CLI（`ofl-font-baker`）としても、
`merge_fonts.main()` を呼ぶライブラリとしても使える。本プロジェクトは後者
（`notofit/build.py`）。

**注意点**

- 入力フォントの name テーブルに OFL のライセンス文字列が必要。Noto Sans JP / Outfit とも
  nameID 13 に保持しており問題ない（M1 で確認）
- ② 約物の `kern` 調整・`palt` の焼き込み・feature の削除と、④ グリフ単位の垂直調整は
  守備範囲外。自前で fontTools を使う

### 検討した代替案: fontTools の merge を自前で使う

`fontTools.merge` でマージ処理を自作する選択肢。全面的に制御できるが、グリフ名衝突と
GSUB/GPOS の統合を自力で解く必要がある。**M1 で ofl-font-baker が破綻なく通ったため不要
になった。**

---

## 2. 基盤

### fontTools

全工程の土台。

| 用途                   | モジュール                               |
| ---------------------- | ---------------------------------------- |
| ① 静的インスタンス化   | `varLib.instancer`                       |
| ② 約物の `kern`        | `otlLib.builder`（クラスベース PairPos の生成）  |
| ② `palt` 焼き込み      | `ttLib`（GPOS / hmtx / glyf の直接編集）         |
| ② feature の削除       | `ttLib`（FeatureList と LangSys の張り替え）     |
| ④ グリフ単位の垂直調整 | `ttLib`（glyf の直接編集）               |
| ⑤ サブセット化         | `subset` / `pyftsubset`                  |
| woff2 出力             | `ttLib.woff2`（brotli 経由）             |

### brotli

woff2 圧縮。**個別に導入する必要がある**（fontTools 4.63 に `woff2` extra は存在せず、
`fonttools[woff2]` を指定しても警告が出るだけで入らない）。

---

## 3. 検証

### uharfbuzz

シェイピング結果をプログラムから検証する。焼き込み後の advance が意図どおりか、feature が
生きているかを、ブラウザを開かずに確認できる。② と ⑤ の検証工程の実体になる。

### テストスクリプト

`tests/*.py` は**単体で実行できるスクリプト**として書いている。結果を表で表示し、失敗が
あれば終了コード 1 を返す。

```bash
.venv/bin/python tests/test_yakumono.py
```

pytest はまだ導入していない。数が増えて一括実行が要るようになった段階で検討する。M4 の
置き換え互換性（行送り・字送りが Noto Sans JP と一致するか）は数値の assert にできる部分が
多いため、そこが導入の目安になる。

### Playwright

**導入済み**（Chromium のみ）。調整ツールの描画確認と、ブラウザ上での字送りの実測に使う。
`text-spacing-trim` のようにブラウザでしか再現しない挙動は、HarfBuzz では確認できない。

M3 / M4 の3エンジン確認にも使える（WebKit / Firefox は必要になった時点で追加導入する）。

---

## 4. 構成

```
Python 3.13 / venv
├── fonttools 4.63       ①⑤ + ②④ の自前処理
├── brotli               woff2 圧縮（個別に入れる）
├── ofl-font-baker 0.4.8 ③ 合成
├── uharfbuzz            シェイピングの検証
└── playwright           ブラウザ上での描画・字送りの検証
```

```bash
python3 -m venv .venv
.venv/bin/python -m pip install fonttools brotli ofl-font-baker uharfbuzz playwright
.venv/bin/python -m playwright install chromium
```

Node 側は現時点で不要。成果物は woff2 と CSS であり、デモサイトを作る段階になったら
検討する。

---

## 5. 参照

- [ofl-font-baker · PyPI](https://pypi.org/project/ofl-font-baker/)
- [yamatoiizuka/ofl-font-baker](https://github.com/yamatoiizuka/ofl-font-baker)
- [fontTools varLib.instancer](https://fonttools.readthedocs.io/en/latest/varLib/instancer.html)
- [fontTools subset](https://fonttools.readthedocs.io/en/latest/subset/)
