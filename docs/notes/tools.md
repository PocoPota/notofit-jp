# ツール調査メモ

調査日: 2026-07-27

Notofit JP のビルドに使用しうるツールの調査結果。採用の最終判断は M1 の検証結果による。
計画書は [../plan.md](../plan.md)。

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

**注意点**

- 入力フォントの name テーブルに OFL のライセンス文字列がないと読み込みが失敗する
  （両ソースとも OFL のため問題ないと見込まれるが、未確認）
- API の関数・クラス名、対応 Python バージョンは未確認。PyPI ページが取得できなかった
  ため、実際に導入して確認する
- ② `palt` の焼き込みと ④ グリフ単位の垂直調整は守備範囲外。自前で fontTools を使う

### 代替案: fontTools の merge を自前で使う

`fontTools.merge` でマージ処理を自作する選択肢。全面的に制御できるが、グリフ名衝突と
GSUB/GPOS の統合を自力で解く必要があり、M1 が重くなる。

**方針: まず ofl-font-baker を試す。** 設計が方針2と一致しており、合わなければ自前実装に
落とせばよい。逆順より手戻りが小さい。

---

## 2. 基盤

### fontTools

全工程の土台。

| 用途                   | モジュール                               |
| ---------------------- | ---------------------------------------- |
| ① 静的インスタンス化   | `varLib.instancer`                       |
| ② `palt` 焼き込み      | `ttLib`（GPOS / hmtx / glyf の直接編集） |
| ④ グリフ単位の垂直調整 | `ttLib`（glyf の直接編集）               |
| ⑤ サブセット化         | `subset` / `pyftsubset`                  |
| woff2 出力             | `ttLib.woff2`（brotli 経由）             |

### brotli

woff2 圧縮。`fonttools[woff2]` で同時に入る。

---

## 3. 検証

### uharfbuzz

シェイピング結果をプログラムから検証する。焼き込み後の advance が意図どおりか、feature が
生きているかを、ブラウザを開かずに確認できる。② と ⑤ の検証工程の実体になる。

### pytest

設計値と出力の回帰テスト。M4 の置き換え互換性（行送り・字送りが Noto Sans JP と一致
するか）は目視ではなく数値の assert にできる部分が多いため、早い段階から入れる価値がある。

### Playwright（任意）

M3 / M4 の3エンジン確認を自動化する場合に使う。Chromium / WebKit / Firefox を1つの API で
回せる。手動確認でも足りるが、ウェイトを増やすと効いてくる。

---

## 4. 構成案

```
Python 3.11+ / uv または venv
├── fonttools[woff2]     ①⑤ + ②④ の自前処理
├── ofl-font-baker       ③ 合成
├── uharfbuzz            検証
└── pytest               回帰テスト
```

Node 側は現時点で不要。成果物は woff2 と CSS であり、デモサイトを作る段階になったら
検討する。

---

## 5. 参照

- [ofl-font-baker · PyPI](https://pypi.org/project/ofl-font-baker/)
- [yamatoiizuka/ofl-font-baker](https://github.com/yamatoiizuka/ofl-font-baker)
- [fontTools varLib.instancer](https://fonttools.readthedocs.io/en/latest/varLib/instancer.html)
- [fontTools subset](https://fonttools.readthedocs.io/en/latest/subset/)
