# Notofit JP 開発計画書

| 項目           | 内容                                                     |
| -------------- | -------------------------------------------------------- |
| プロジェクト名 | Notofit JP                                               |
| 概要           | Outfit と Noto Sans JP を合成した和欧混植用フォントの制作 |
| ライセンス     | SIL Open Font License 1.1                                |

本書は目的・方針・全体アーキテクチャを定める。個々の設計値、検証データ、実装手順は
別ドキュメントに置く。

---

## 1. 目的と背景

### 1.1 目的

欧文 Outfit と和文 Noto Sans JP を単一のフォントファイルに合成し、和欧混植の品質を
フォント側で確定させる。CSS の記述子や feature 設定への依存を最小化し、閲覧環境に
かかわらず同一の組版結果を得ることを目的とする。

### 1.2 用途と適用範囲

**Web での配信を主目的とする。** 横書きのみを対象とし、印刷・縦組みは想定しない。

**Noto Sans JP をメインで使っている既存の日本語サイトを、そのまま置き換えられること**を
要件とする。したがって和文が基準であり、`font-family` の差し替えだけで既存のレイアウトが
崩れないことを目標とする。字面のサイズ・行の高さ・和文の字送りは可能な限り Noto Sans JP
と一致させ、**欧文側（Outfit）を和文に合わせて調整する**。

### 1.3 背景

和欧混植の調整項目のうち、CSS で解決できるものとできないものがある。

| 課題                     | CSS での可否            | 備考                                                         |
| ------------------------ | ----------------------- | ------------------------------------------------------------ |
| 約物のアキ               | 不可                    | 隣接時だけ詰める、という文脈処理を CSS で書けない             |
| 和欧のジャンプ率         | `size-adjust` で可能    | 単体なら CSS で足りる                                        |
| 和欧間のアキ             | `text-autospace` で可能 | 本計画では CSS 側で担保する                                  |
| **和欧のベースライン**   | **不可**                | `ascent-override` は行ボックスを変えるだけでグリフは動かない |
| **グリフ単位の上下位置** | **不可**                | Outfit のコロン類が下寄り。CSS には手段がない                |

ベースラインが CSS で調整できない点が、合成を選択する主たる根拠である。和文側のみを
加工する方式では和欧の関係の半分が CSS 依存となり、2つの `@font-face` の値が独立して
変動するため、一貫した設計を維持できない。

### 1.4 合成が成立する前提

Noto Sans JP と Outfit は upem・アウトライン形式（glyf）・軸構成（wght）が一致して
おり、合成の技術的前提を満たす。一方で cap-height と x-height には差があり、欧文を
和文に合わせるためのスケールとベースラインの設計値は、この組み合わせで算出する必要が
ある。

ソース:

```
https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf
https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit%5Bwght%5D.ttf
```

---

## 2. 方針

| # | 方針                                         | 理由                                                                    |
| - | -------------------------------------------- | ----------------------------------------------------------------------- |
| 1 | **Web 配信を主目的とし、横書きのみ対応する** | 用途を絞ることで縦組み用の feature・メトリクスの検証を対象外にできる     |
| 2 | **Noto Sans JP 基準とし、欧文を和文に合わせる** | 既存の Noto Sans JP 採用サイトを差し替えだけで置き換え可能にする         |
| 3 | 和欧を1ファイルに合成する                    | ベースラインとグリフ位置は CSS で扱えず、分離すると設計が2箇所に分散する |
| 4 | 調整はフォント側に焼き込み、CSS に依存しない | feature 指定やブラウザ実装差の影響を受けない                            |
| 5 | 静的フォントとして出力する                   | 可変フォント同士の合成は `gvar` のデルタ統合を要し、現実的でない        |
| 6 | 約物は全角のまま、隣接時のアキだけ取り除く   | 単独の約物は全角ベタが正しい。詰めるべきは重複したアキだけ（→ [yakumono.md](yakumono.md)） |
| 7 | 配信は `unicode-range` によるスライス方式    | Google Fonts の区切りを用い、文字頻度の分析は行わない（約物のみ1つに集約） |
| 8 | 和欧間のアキのみ CSS に委ねる                | CSS が十分に機能している唯一の領域（→ 6）                               |

方針2は、Gen Interface JP をはじめとする和欧合成フォントの一般的な設計（和文を欧文の
cap-height に合わせて縮小する）とは基準が逆になる。本プロジェクトは新規の組版体験では
なく既存サイトの置き換えを目的とするため、和文の字面と字送りを動かさないことを優先する。

---

## 3. スコープ

### 3.1 対象範囲

- 静的インスタンスの生成（複数ウェイト）
- 約物の隣接処理（`kern`）と、かな・全角英数のプロポーショナル化（`palt` 焼き込み）
- 和欧の合成（欧文のスケール・ベースライン調整、縦メトリクスの統一）
- グリフ単位の垂直位置調整
- `unicode-range` によるサブセット分割と woff2 出力
- Web 配信用 CSS の生成
- Noto Sans JP との置き換え互換性の確認

### 3.2 対象外

| 項目               | 判断                                                                  |
| ------------------ | --------------------------------------------------------------------- |
| 縦組み             | 横書きのみ対応。縦組み用の feature は調整せず、`vhal` / `vpal` / `vkrn` は削除する（→ 4.2 ②） |
| 印刷・アプリ用途   | Web 配信（woff2）に絞る。ヒンティングや OTF/TTF での配布は扱わない      |
| 和欧間のアキ       | CSS の `text-autospace` に委ねる（→ 6）                                |
| `chws` の実装      | 実装済みブラウザが限られ、実効性がないため不採用（→ [yakumono.md](yakumono.md)） |
| 可変フォント出力   | 合成方式の帰結として静的のみとする                                     |

削除する feature の一覧と理由は 4.2 の工程②。字形を切り替える `vert` / `vrt2` は字送りに
影響しないため残す。

### 3.3 成果物

| 成果物           | 内容                                     |
| ---------------- | ---------------------------------------- |
| `dist/*.woff2`   | サブセット済みフォント（スライス × ウェイト数） |
| `dist/*.css`     | `@font-face` 宣言                         |
| `OFL.txt`        | ライセンス全文                            |
| `README.md`      | 出自・派生関係の明記、CSS の推奨・非推奨（→ [usage.md](usage.md)） |
| ビルドスクリプト | 各工程を再実行可能な形で                  |

### 3.4 配布

**npm パッケージとして公開する。**

| 項目 | 内容 |
| ---- | ---- |
| 形式 | npm パッケージ。`dist/` の woff2 と CSS を同梱する |
| CDN | npm に公開すれば jsDelivr / unpkg から配信されるため、別途用意しない |
| GitHub Release | 併用するかは後で判断する |
| ライセンス | `OFL.txt` を同梱する |

**サンプルと使い方を載せた Web ページ**を `site/index.html` に置く。実物を見せられる場と、
CSS の書き方（→ [usage.md](usage.md)）の案内を兼ねる。比較用に素の Noto Sans JP を
Google Fonts から読み、約物・字幅・和欧の関係の違いをその場で見せる。

フォント自体は jsDelivr（npm 経由）から読むため、**npm に公開されるまでページ上の
フォントは反映されない**。公開は `.github/workflows/pages.yml` が `site/` を GitHub Pages
へ送る。

利用側は CSS を読み込む形を想定する。パスの解決はバンドラに任せるため、工程⑥ が出力する
`@font-face` の `src` はパッケージ内の相対パスとする。

```
notofit-jp/
├── notofit-jp.css     @font-face（全ウェイト）
├── 400.css / 700.css  ウェイト単位で読み込みたい場合
├── w/<weight>/*.woff2 サブセット済みフォント（125スライス × ウェイト）
├── package.json
├── manifest.json      生成結果の内訳
├── OFL.txt
└── README.md          使い方、CSS の推奨と非推奨、出自とクレジット
```

`dist/` 一式がそのままパッケージの中身になる。`npm pack` で 6.0MB / 257ファイル。

### バージョン

`notofit/__init__.py` の `__version__` を唯一の出処とし、**フォントの nameID 5 と npm の
`version` が同じ値**になるようにする。フォントを更新すれば字送りが変わりうるため、
利用側から見れば破壊的変更になりうる点に注意する。

---

## 4. アーキテクチャ

### 4.1 ビルドパイプライン

```
NotoSansJP[wght].ttf (可変)        Outfit[wght].ttf (可変)
        │                                  │
        │ ① 各ウェイトで静的化              │ ① 各ウェイトで静的化
        ▼                                  ▼
   NotoSansJP-<w>.ttf                 Outfit-<w>.ttf
        │                                  │
        │ ② 約物の kern / palt 焼き込み      │
        ▼                                  │
        └────────────┬─────────────────────┘
                     │ ③ 合成（和文が基準）
                     │   - 欧文を SCALE 倍に拡縮
                     │   - 欧文のベースラインを BASELINE_OFFSET だけ移動
                     │   - 縦メトリクス・和文の字送りは Noto 側に固定
                     ▼
              NotofitJP-<w>.ttf
                     │ ④ グリフ単位の垂直調整
                     │ ⑤ unicode-range で分割
                     ▼
              dist/*.woff2
                     │ ⑥ CSS 生成
                     ▼
              dist/*.css
```

### 4.2 各工程の役割

#### ① 静的インスタンス化

`fontTools.varLib.instancer` で `wght` を固定する。

和文は Noto Sans JP のラウンドなウェイト位置をそのまま用いる（置き換え互換性のため、
既存サイトが指定している `font-weight` に対して同じ太さを返す必要がある）。欧文側は
ラウンドな値に限定せず、和文と見かけの太さが揃う位置を選ぶ。`usWeightClass` および
CSS 上の `font-weight` は、いずれもラウンドな値で宣言する。

#### ② 約物と字幅の処理

2つの異なる処理を行う。詳細と決定経緯は [yakumono.md](yakumono.md) と
[proportional.md](proportional.md)。

**約物** — 字幅は全角のまま変更せず、隣接したときに重複するアキだけを `kern` のペア調整で
取り除く。単独の約物は全角ベタが JLREQ どおり正しいため、詰める必要があるのは隣接時だけで
ある。`kern` は既定で有効な feature だが、**エンジンによって効き方に差がある**
（Firefox は `font-kerning: normal` が要る。WebKit は行分割が許される位置では効かない）。
差は受け入れる。→ [notes/browser-kerning.md](notes/browser-kerning.md)

**かな・全角英数** — `palt` を焼き込んでプロポーショナル化しうる。調整量を `hmtx` と
アウトラインに恒久的に書き込む。字面は締まるが字送りが変わるため、**採否は M2 で決める**
（既定は焼き込む側。→ [proportional.md](proportional.md)）。

**feature の削除** — 処理を終えたあと、次の feature を削除する。いずれも
**CSS で指定されると意図しない字送りになる**もので、方針4（フォント側で確定し、CSS に
依存しない）を守るには残せない。

| feature | 削除する理由 |
| ------- | ------------ |
| `palt` | 焼き込み済み。約物には値が残っており、指定されると `kern` の調整と二重にかかって約物が潰れる |
| `halt` | Chromium の `text-spacing-trim` が使う。同じく `kern` と二重適用になる |
| `vhal` / `vpal` / `vkrn` | 縦組み用。横書き限定の方針により不要 |

削除は焼き込み（`palt` の値を読む）と `kern` の追加より後に行う。字形を切り替える
`vert` / `vrt2` は字送りに影響しないため残す。

約物の処理という同じ目的を持つ `chws` は、そもそも実装しない。仕様上は JLREQ 相当を
実装していないエンジンが既定で有効にすべき feature だが、実際に適用されるのは Chromium 系に
限られ、WebKit / Gecko では効かないため。

#### ③ 合成

和欧を1つのフォントに統合する。**和文を基準とし、動かすのは欧文側**とする（→ 方針2）。

| 調整         | 内容                                                                     |
| ------------ | ------------------------------------------------------------------------ |
| ジャンプ率   | 欧文を `SCALE` 倍に拡縮し、Noto Sans JP の欧文と同等の字面サイズに揃える |
| ベースライン | 欧文を `BASELINE_OFFSET` だけ移動し、和文と光学的に揃える                |
| 縦メトリクス | hhea / OS/2 を Noto Sans JP 側に固定し、既定の行の高さを一致させる       |
| 字送り       | 和文の advance には手を入れない（②の処理を除く）                         |
| 欧文の重複   | Noto Sans JP 自身が持つ欧文は Outfit で上書きする。**記号もすべて Outfit を採用する** |

①の静的インスタンス化のうち欧文側はこの工程に統合する（合成ツールがインスタンス化を
内蔵するため、中間ファイルを介さない）。和文側は②の前に静的化しておく必要がある。
`palt` が `FeatureVariations` によりウェイトで内容を変えるため、可変のまま焼き込むと
どのウェイトの値を焼いたのかが曖昧になる（[notes/palt-weight-boundary.md](notes/palt-weight-boundary.md)）。

同種の実装である Gen Interface JP は欧文（Inter）を基準に和文を縮小しているが、本
プロジェクトは基準が逆であるため、設計値は流用せず Outfit と Noto の cap-height /
x-height 比から算出し直す。

`excludeCodepoints`（CJK 側の字形を残す符号位置）は**空とする**。`①` `※` `℃` のような記号を
CJK の慣習に寄せる選択肢はあるが、まず Outfit を全面的に採用し、必要が生じた時点で
個別に対応する。

置き換え互換性の観点から、縦メトリクスと和文の字送りを変えないことを最優先とする。
`font-family` の差し替えのみで既存サイトの行送りや折り返し位置が変わらないことを、
M4 で確認する。

本工程はグリフ名の衝突、cmap のマージ、GSUB/GPOS の統合を伴い、本計画で最大の技術的
不確実性を含む（→ 7）。

#### ④ グリフ単位の垂直調整

詳細と決定経緯は [glyph-vertical.md](glyph-vertical.md)。

本プロジェクト固有の工程。Outfit はコロン類（`:` `;`）が自身の x-height 中心より低く
配置されており、和文の全角コロンと並置すると差が目立つ。`palt` や `SCALE` は水平方向と
全体スケールのみを扱うため、対象グリフのアウトラインを個別に垂直移動する。

CSS では実現できない。`vertical-align` や `translateY` は要素単位でしか作用せず、
文中の特定グリフのみを動かす手段がないためである。

適用は静的インスタンス化の後とする。可変フォントのまま適用すると全ウェイトが同量
移動するが、細いウェイトと太いウェイトではドットの見え方が異なり、最適値がウェイト
ごとに異なりうるためである。

#### ⑤ サブセット化

Google Fonts の CSS から `unicode-range` を取得し、同じ区切りで `pyftsubset` に渡す。
文字頻度の分析は行わない。数百万の日本語ページから収集した頻度データの結果が、すでに
`unicode-range` の区切りに反映されているためである。

Google のスライシング手法は、使用頻度上位の文字群を等分したスライスと、残りを符号位置
順に等分したスライスからなる。ページが実際に読み込むのは使用文字に対応する少数の
スライスのみであり、総ファイル数は転送量にほとんど影響しない。

サブセット化の指定次第で layout feature が脱落しうるため、生成後に保持を検証する工程を
設ける。

**約物は1つのスライスに集める。** ブラウザはフォントをまたいでカーニングを適用しないため、
`kern` の対象となる約物が別々のスライスに落ちると調整が効かない。Google の区切りでは11個の
スライスに分散するため、対象の31字を1つに集め、他のスライスからは取り除く（区切りは
124 → 125 になる）。方針7からの逸脱だが、頻度に基づく区切りの意図は保たれる。
→ [yakumono.md](yakumono.md)

**name テーブルは著作権（nameID 0）とライセンス URL（14）を残し、ライセンス全文（13）は
落とす。** Google Fonts が配信しているスライスと同じ構成にする。`pyftsubset` の既定は
0〜6 のみを残すため、14 は明示的に指定する必要がある。理由と各実装の比較は
[notes/name-table.md](notes/name-table.md)。

#### ⑥ CSS 生成

スライスとウェイトの組み合わせごとに `@font-face` を出力する。合成済みであるため
`size-adjust` / `ascent-override` は用いない。

Noto Sans JP の Google Fonts 版 CSS と同じ `unicode-range` の区切り・同じ
`font-weight` の値で出力し、既存サイトが読み込んでいる CSS をそのまま差し替えられる形を
とる。

---

## 5. 進め方

| #  | マイルストーン     | 完了条件                                                            |
| -- | ------------------ | ------------------------------------------------------------------- |
| M1 | 合成の実現性検証   | **完了**（2026-07-27）。[notes/m1-merge.md](notes/m1-merge.md)        |
| M2 | 設計値の確定       | **完了**（2026-07-28）。値は `config/tuning.json` と `config/glyph-shifts.json` |
| M3 | 単一ウェイトの完成 | **完了**（2026-07-28）。①〜⑥ を通して生成し、3エンジンで確認（[notes/browser-kerning.md](notes/browser-kerning.md)） |
| M4 | 置き換え互換性の確認 | Noto Sans JP 採用ページで差し替え、行送りの一致と、折り返し位置の変化量が想定内であることを確認 |
| M5 | 全ウェイト展開     | **完了**（2026-07-28）。`notofit.release` が 400 / 700 を一括で生成する |
| M6 | 配布準備           | **ビルド側は完了**（2026-07-28）。`package.json` / README / OFL.txt を生成し、name テーブルに身元情報を入れた。残るは公開の実行 |

M1 は他のすべての工程の前提となるため最初に着手する。

### 決定事項

**ウェイトは 400 / 700 の2つとする（確定）。** 他のウェイトは将来的に追加しうるため、
設定と生成処理はウェイトごとの繰り返しとして構成し、追加が差分で済むようにする。

**決め方は項目によって違う。** 和欧の関係（`SCALE` / `BASELINE_OFFSET` / 欧文の `wght`）と
約物の詰め量は、並べて見なければ正解が決まらないため**目視で判断する**。数値は出発点および
参考として用いる。この作業のために調整ツールを用意する（→ [tuner.md](tuner.md)）。

一方 `palt` の焼き込み比率は、**字幅の変化量という数値が判断を支配する**。焼き込むほど
字面は締まるが、既存サイトの折り返し位置が動く（R5）。代表的な本文で比率ごとの総送り量を
測り、それを見て決める。目視はその後の確認にあたる（→ [proportional.md](proportional.md)）。

以下は M2 で確定した。**値そのものは設定ファイルに置き、文書には方針だけを書く。**
値は調整ツールで目視により決めたものであり、文章で根拠を再現できる性質のものではない。

- 和欧の関係・約物・字幅 → `config/tuning.json`
- グリフ単位の垂直調整 → `config/glyph-shifts.json`

| # | 項目                        | 内容                                                    |
| - | --------------------------- | ------------------------------------------------------- |
| 1 | `SCALE` / `BASELINE_OFFSET` | 欧文を和文に合わせる値。ウェイトごとに持つ              |
| 2 | 欧文の `wght` インスタンス化値 | 和文と見かけの太さが揃う位置（和文は 400 / 700 で固定） |
| 3 | 約物の `kern` の値          | 隣接時に引く量。既定 −500 は JLREQ 由来                  |
| 4 | かな・全角英数をプロポーショナル化するか | する / しない の2択。字送りの変化量で判断     |
| 5 | ~~`excludeCodepoints` の対象~~ | **確定: 空**。記号はすべて Outfit を採用する（→ 4.2 ③） |
| 6 | グリフ単位の垂直調整の対象と値 | Outfit のコロン類ほか。何に合わせるかを含む（→ [glyph-vertical.md](glyph-vertical.md)） |
| 7 | ~~`metadataMode`~~          | **確定: `merge`**。独自の名前を持つ派生物であるため（→ 8章） |

---

## 6. 和欧間のアキ（スコープ外）

CSS の `text-autospace: normal` に委ね、フォントには含めない。3エンジンとも対応済みで
あり、`pre` / `code` での自動無効化や要素境界の除外といった文脈処理も仕様から得られる。
これらはフォントに焼き込むと再現できない。

再検討の余地があるのはアキの量を変えたい場合に限られる。`text-autospace` のアキは仕様で
`0.125ic` に固定されており CSS 側に調整手段がないため、日本語組版の伝統的な四分アキ
（0.25em）を採るならフォント側に持つ必要がある。その場合は `kern` にクラスベースの
ペア調整として焼き込む形になるが、CSS 側との二重適用を避ける明示的な無効化が必要となり、
上記の文脈処理も失われる。現時点では採らない。

---

## 7. リスクと対策

| #  | リスク                                            | 影響 | 対策                                                                 |
| -- | ------------------------------------------------- | ---- | -------------------------------------------------------------------- |
| R1 | 合成時のグリフ名衝突・cmap マージ・GSUB/GPOS 統合 | 高   | **解消**（M1）。合成ツール側で処理されることを確認済み                 |
| R2 | サブセット化で layout feature が脱落する          | 中   | ⑤の後に feature 保持の検証工程を設ける                                |
| R3 | `palt` の値がウェイトの境界で切り替わり、字送りに段差が出る | 低   | **調査済み**。400 / 700 の2ウェイトでは問題にならない。将来 500 / 600 を足すと 600–700 間にのみ不連続が生じる（[notes/palt-weight-boundary.md](notes/palt-weight-boundary.md)） |
| R4 | ウェイトごとに垂直調整の最適値が異なる            | 低   | **対応済み**。合成後に適用し、設定をウェイト別に持つ構造とした        |
| R5 | ②の処理が既存サイトのレイアウトを動かす           | 中   | 約物は隣接時のみに影響を限定した。かなの縮みは体感サイズが変わらない範囲とし、M4 で影響を確認 |

---

## 8. ライセンスと命名

両フォントとも SIL Open Font License 1.1。改変・再配布は可能だが、派生物も OFL で配布
する必要がある。Reserved Font Name は Noto Sans JP 側に `Source`（Source Han Sans 由来）が
設定されており、Outfit にはない。

`Noto` は予約名に含まれないため、`Notofit JP` という名称は OFL 上問題ない。

> 3. No Modified Version of the Font Software may use the Reserved Font Name(s)
>    unless explicit written permission is granted by the corresponding Copyright Holder.

ただし `Noto` は Google の商標であるため、広く配布する段階では公式の派生と誤認されない
配慮を行う。

必須事項:

- `OFL.txt` を同梱し、OFL 1.1 で配布する
- 名称に `Source` を含めない
- **自前の Reserved Font Name は設定しない。** 設定すると改変版が `Notofit` を名乗れなく
  なるが、利用側の手間が増える。Gen Interface JP も設定しておらず、Google Fonts も
  推奨していない
- 元フォントの著作権表示を残す。**Noto Sans JP の著作権表示は Adobe のみ**
  （Source Han Sans 由来）で、Google の表示は元から存在しない。Outfit は
  The Outfit Project Authors

---

## 9. 参考

### 関連ドキュメント

- [yakumono.md](yakumono.md) — 約物の処理と、不採用とした案
- [proportional.md](proportional.md) — かな・全角英数の字幅のプロポーショナル化
- [glyph-vertical.md](glyph-vertical.md) — グリフ単位の垂直調整と、その調整ツール
- [usage.md](usage.md) — 利用ガイド（外部向け）
- [notes/name-table.md](notes/name-table.md) — 配布フォントの name テーブルに何を残すか
- [notes/browser-kerning.md](notes/browser-kerning.md) — 3エンジンでの約物カーニングの実測
- [tuner.md](tuner.md) — 和欧調整ツール（開発支援 GUI）の仕様
- [notes/tools.md](notes/tools.md) — 使用ツールの調査メモ
- [notes/m1-merge.md](notes/m1-merge.md) — M1 合成の実現性検証の結果

### 外部資料

- [Gen Interface JP](https://gen.typesetting.jp/) / [ARCHITECTURE.md](https://github.com/yamatoiizuka/gen-interface-jp/blob/main/docs/ARCHITECTURE.md) — 同一構成の実装例
- [fontTools varLib.instancer](https://fonttools.readthedocs.io/en/latest/varLib/instancer.html) / [subset](https://fonttools.readthedocs.io/en/latest/subset/)
- [Google Fonts launches Japanese support](https://developers.googleblog.com/en/google-fonts-launches-japanese-support/) — スライシング手法の一次情報
- [OpenType 1.9.1 registered features a–e](https://learn.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws) — `chws` の登録エントリ
- [csswg-drafts #8262](https://github.com/w3c/csswg-drafts/pull/8262) — `text-autospace` のアキ量の決定経緯
- [googlefonts/chws_tool](https://github.com/googlefonts/chws_tool) / [kojiishi/east_asian_spacing](https://github.com/kojiishi/east_asian_spacing)
- [SIL Open Font License 1.1](https://openfontlicense.org/)
- [W3C Incremental Font Transfer](https://w3c.github.io/IFT/) — サブセット分割方式は将来置き換わりうる
