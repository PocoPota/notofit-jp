# Notofit JP 利用ガイド

Notofit JP を使う人のための資料。設計の経緯や実装の記録は
[plan.md](plan.md) 以下の設計資料にある。

---

## 1. これは何か

欧文の **Outfit** と和文の **Noto Sans JP** を、ひとつのフォントに合成した Web 向けの
和欧混植フォント。**Noto Sans JP の置き換え**として使えることを目標に作っている。

フォントの側で以下を確定させている。CSS の記述子や feature 指定に依存しない。

| | 内容 |
| --- | --- |
| 和欧の関係 | 欧文の大きさ・ベースライン・見かけの太さを和文に合わせてある |
| グリフ単位の位置 | コロン類・括弧・引用符の高さを個別に補正してある |
| 約物 | 単独では全角のまま。隣り合ったときだけアキを取り除く |
| かな・全角英数 | 字面に応じた幅（プロポーショナル）にしてある |
| 縦メトリクス | Noto Sans JP と同じ。行の高さが変わらない |

## 2. 仕様

| 項目 | 値 |
| ---- | -- |
| ウェイト | 400（Regular）/ 700（Bold） |
| スタイル | ローマン体のみ。イタリックはない |
| 書字方向 | **横書き専用**。縦組みは対象外 |
| 形式 | woff2 のみ。TTF / OTF は配布しない |
| units per em | 1000 |
| スライス | 125（`unicode-range` による分割）× ウェイト = 250 ファイル |
| パッケージ | 約 6.0 MB。1ページが読むのは使用文字ぶんの十数ファイル |
| ライセンス | SIL Open Font License 1.1 |

### 含まれる OpenType feature

`kern`（約物の隣接処理を含む）、`ccmp`、`liga`、`locl`、`mark`、`mkmk`、
`vert` / `vrt2`（字形の切り替えのみ）、`jp78` / `jp83` / `jp90` / `nlck`、
`fwid` / `hwid` / `pwid`、`ruby` ほか。

### 削除した feature

`palt` / `halt` / `vhal` / `vpal` / `vkrn`。いずれも **CSS で指定されると意図しない
字送りになる**ため取り除いてある。字幅はフォント側で確定している。

## 3. 導入

```bash
npm install notofit-jp
```

```css
/* npm */
@import "notofit-jp/notofit-jp.css";

/* CDN */
@import url("https://cdn.jsdelivr.net/npm/notofit-jp@0.1/notofit-jp.css");
```

ウェイト単位で読み込むこともできる。

```css
@import "notofit-jp/400.css";
@import "notofit-jp/700.css";
```

## 4. 指定する CSS

```css
body {
  font-family: "Notofit JP", sans-serif;
  text-autospace: normal;   /* 和欧間のアキ */
  font-kerning: normal;     /* 約物の隣接処理 */
}
```

### `text-autospace: normal`

**書かないと和欧間のアキが付かない。**

| 指定 | `あA` |
| ---- | ----- |
| なし | 1.667em |
| `text-autospace: normal` | **1.792em**（+0.125em） |

仕様上の初期値は `normal` だが、Chromium の実装は `no-autospace` を初期値としている。

和欧間のアキをフォントに焼き込んでいないのは、`pre` や `code` の中で自動的に無効になる
といった文脈処理が CSS 側の仕様にあり、フォントでは再現できないため。

### `font-kerning: normal`

**Firefox は既定（`auto`）では約物のカーニングを適用しない。** 明示すると効く。

| 指定 | `」「`（Firefox） |
| ---- | ----------------- |
| なし（`auto`） | 2.000em |
| `font-kerning: normal` | **1.500em** |

Chromium は既定で効くため差はない。

> **注意**: Firefox の `font-kerning: normal` は、CJK フォントに対して `palt` も
> 有効にする。Notofit JP は `palt` を削除しているため影響を受けないが、**同じページで
> 他の和文フォントを使っている場合はその字送りが変わる**。

## 5. 書いてはいけない CSS

| プロパティ | 何が起きるか |
| ---------- | ------------ |
| `font-kerning: none` | 約物の隣接処理が無効になり、`」「` が全角ベタ（2.000em）に戻る |

## 6. 書いても効果がない CSS

| プロパティ | 理由 |
| ---------- | ---- |
| `font-feature-settings: "palt"` | 削除済み。字幅はフォント側で確定している |
| `font-feature-settings: "halt"` / `"chws"` | 前者は削除済み、後者は実装していない |
| `size-adjust` | 和欧のジャンプ率は合成時に確定済み |
| `ascent-override` / `descent-override` | 縦メトリクスは Noto Sans JP に揃えてある |
| `text-spacing-trim` | `halt` / `chws` を持たないため Chromium が適用しない |

## 7. ブラウザごとの挙動

Chromium 149 / WebKit 26.5 / Firefox 151 での実測。`」「` の幅。

| | Chromium | WebKit | Firefox（`font-kerning: normal`） |
| --- | -------- | ------ | -------- |
| `」「` `』「` `）（`（2文字目が始め括弧） | 1.500em | **2.000em** | 1.500em |
| `。」` `、」` `」・` `」：` `。、` `「『` | 1.500em | 1.500em | 1.500em |
| かな・全角英数の字送り | 一致 | 一致 | 一致 |
| 和欧の大きさ・ベースライン | 一致 | 一致 | 一致 |

**WebKit は「2文字目が始め括弧」の組み合わせでだけ約物の詰めが効かない。** 始め括弧の
前では行分割が許されるため、その位置でシェイピングのランが切れ、カーニングが届かない。
CSS では回避できない。その場合は従来どおり全角ベタで表示される。

字幅そのものに焼き込めば WebKit でも詰まるが、単独で現れる始め括弧まで詰まってしまう。
そちらのほうが頻度が高いため、現状を採っている。

## 8. Noto Sans JP から置き換えたとき

| 項目 | 変化 |
| ---- | ---- |
| 行の高さ | **変わらない**（縦メトリクスを揃えてある） |
| 単独の約物の字送り | **変わらない**（全角のまま） |
| 漢字の字送り | **変わらない**（全角のまま） |
| 隣接した約物 | 詰まる（`」「` が 2.000em → 1.500em） |
| かな・全角英数 | プロポーショナルになるため詰まる（本文で約 4.5%） |
| 欧文 | Outfit に置き換わる |

行の高さが変わらないため縦方向のレイアウトは保たれるが、かなが詰まるぶん**行の折り返し
位置は変わる**。

## 9. ライセンス

SIL Open Font License 1.1。改変・再配布ができる（派生物も OFL で配布すること）。

| 元フォント | 著作権とデザイン |
| ---------- | ---------------- |
| Noto Sans JP | Copyright 2014-2021 Adobe, with Reserved Font Name 'Source'<br>西塚涼子（かな・注音・漢字）、Paul D. Hunt（ラテン・ギリシャ・キリル）ほか |
| Outfit | Copyright 2021 The Outfit Project Authors<br>Rodrigo Fuenzalida（fragTYPE） |
| Notofit JP | Copyright 2026 The Notofit JP Project Authors |

Notofit JP は Google の公式な派生ではない。

## 10. さらに詳しく

設計の経緯と実装の記録。利用にあたって読む必要はない。

| | |
| --- | --- |
| [plan.md](plan.md) | 開発計画書。方針・アーキテクチャ・工程 |
| [yakumono.md](yakumono.md) | 約物の処理と、不採用にした案 |
| [proportional.md](proportional.md) | かな・全角英数の字幅 |
| [glyph-vertical.md](glyph-vertical.md) | グリフ単位の垂直調整 |
| [notes/](notes/) | 調査メモ（3エンジンの実測、name テーブル、`palt` の境界ほか） |
