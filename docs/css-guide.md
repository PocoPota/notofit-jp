# CSS の推奨・非推奨（暫定）

Notofit JP を使うページ側で、書くべき CSS と書いてはいけない CSS。配布時の README に
載せることを想定した下書き。**M3 / M4 で3エンジンで検証してから確定する。**

数値はすべて wght=400 での実測（HarfBuzz またはブラウザ）。

---

## 書いたほうがよい

### `text-autospace: normal`

**和欧間のアキはこれを書かないと付かない。**

| 指定 | `あA` |
| ---- | ----- |
| なし（既定） | 1.667em |
| `text-autospace: normal` | **1.792em**（+0.125em） |

仕様上の初期値は `normal` だが、**Chromium の実装は `no-autospace`** を初期値としている
（computed value を確認。Chromium 149）。したがってページ側で明示する必要がある。

本フォントは和欧間のアキをフォントに焼き込んでいない（→ [plan.md](plan.md) の方針8）。
文脈処理を CSS 側の実装に任せる判断であり、その代わりに1行書いてもらう前提になる。

```css
body { text-autospace: normal; }
```

---

## 書いてはいけない

### `font-kerning: none`

**約物の隣接処理が無効になる。**

| 文字列 | 既定 | `font-kerning: none` |
| ------ | ---- | -------------------- |
| `」「` | 1.500em | 2.000em（全角ベタに戻る） |

隣接した約物のアキを取り除く処理を `kern` に載せているため。

---

## 書かなくてよい（効果がない、または不要）

| プロパティ | 理由 |
| ---------- | ---- |
| `size-adjust` | 和欧のジャンプ率は合成時に確定済み |
| `ascent-override` / `descent-override` | 縦メトリクスは Noto Sans JP に揃えてある |
| `text-spacing-trim` | `halt` / `chws` を持たないフォントでは Chromium が適用しないため効かない。約物の処理は `kern` が担う |
| `font-feature-settings: "palt"` | **削除済み。** 指定しても字送りは変わらない。字幅はフォント側で確定している |
| `font-feature-settings: "halt"` | 削除済み。指定しても `」「` は 1.500em のまま |
| `font-feature-settings: "chws"` | 実装していない（→ [yakumono.md](yakumono.md)） |

---

## 置き換え時の注意

| 項目 | Noto Sans JP からの変化 |
| ---- | ----------------------- |
| 行の高さ | **変わらない**（縦メトリクスを揃えてある） |
| 約物が単独で現れるとき | **変わらない**（全角のまま） |
| 約物が隣接するとき | 詰まる（`」「` 2.000em → 1.500em） |
| かな・全角英数の字送り | プロポーショナル化する場合は詰まる（本文で約 −4.5%）。採否は M2 で決定（→ [proportional.md](proportional.md)） |
| `font-weight` | 400 と 700 のみ。それ以外の値の扱いは未検証 |

---

## 確定させるために必要なこと

- 3エンジン（Chromium / WebKit / Gecko）での確認（M3）
- 実際のページに当てての確認（M4）
- `font-weight` を 400 / 700 以外にしたときの挙動
- `halt` 削除で Chromium の `text-spacing-trim` が実際に止まることのブラウザ確認
