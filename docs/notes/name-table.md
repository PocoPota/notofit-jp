# 配布フォントの name テーブルに何を残すか

調査日: 2026-07-28
関連: 計画書 [../plan.md](../plan.md) の工程⑤ と 8章

---

## 結論

**配布するスライスには著作権（nameID 0）とライセンス URL（14）を残し、ライセンス全文（13）は
落とす。Google Fonts が配信しているものと同じ構成にする。**

商標（7）は合成後のフォントに残す。デザイナー（9）は空のままとし、クレジットは配布
パッケージの README に載せる。

---

## 実際に配布されているものの比較

`fonts.gstatic.com` が返す Noto Sans JP のスライスと、npm の `gen-interface-jp@0.8.0` に
含まれる woff2 を実際に開いて確認した。

| nameID | Google Fonts のスライス | Gen Interface JP |
| ------ | ----------------------- | ---------------- |
| 0 著作権 | **Adobe の表示を残す** | 空 |
| 1〜6 名前・バージョン | あり | あり |
| 7 商標 | 空 | 空 |
| 8 製造者 / 9 デザイナー / 11 製造者URL | 空 | 空 |
| 13 ライセンス全文 | 空 | 空 |
| 14 ライセンス URL | **残す** | 空 |

Google は**著作権とライセンス URL だけ**を残す最小構成。全文を落として URL で代替し、
バイト数を抑えている。Gen はすべて空にし、`OFL.txt` をパッケージに同梱することで担保して
いる（`package.json` の `license` も `OFL-1.1`）。

なお `pyftsubset` の既定は `name_IDs = [0, 1, 2, 3, 4, 5, 6]` であり、**指定しなければ
7 以降は自動的に落ちる**。上記2つで 0 と 14 の扱いが分かれているのは、明示的な指定の
有無によると見られる。

## OFL の規定

> **Any trademark notices must remain in any derivative fonts** to respect trademark laws,
> but you may add any additional trademarks you claim.
> — [OFL-FAQ 5.7](https://openfontlicense.org/ofl-faq/)

> Put your copyright and the OFL text with your chosen Reserved Font Name(s) into your font
> files (the copyright and license fields). **A link to the OFL text on the OFL website is an
> acceptable (but not recommended) alternative.**
> — 同 4.2.2

デザイナー（nameID 9）についての規定はない。「作者は言及されると喜ぶが必須ではない」
（1.1.2）とあるのみ。

## 本プロジェクトの方針と理由

| 項目 | 方針 | 理由 |
| ---- | ---- | ---- |
| 著作権（0） | **残す** | FAQ 4.2.2 が font files に入れることを推奨。フォント単体で出自が辿れる |
| ライセンス URL（14） | **残す** | 全文の代替として FAQ が許容。Google も同じ構成 |
| ライセンス全文（13） | 落とす | スライス124個 × ウェイト数に全文を載せる意味が薄い。`OFL.txt` を同梱する |
| 商標（7） | **合成後のフォントには残す** | FAQ 5.7 が派生物に残すことを求めている。配布スライスでは既定で落ちる |
| デザイナー（9） | 空のまま | 規定がなく、Google も Gen も空。代わりに README にクレジットを載せる |
| 製造者（8）/ URL（11） | 任意 | Gen は自分の名前を入れている。入れる場合は合成時に指定する |

### 商標について

Noto Sans JP から `Source is a trademark of Adobe in the United States and/or other
countries.` を引き継いでいる。本フォントは `Source` の名を使っていないため一見奇妙だが、
**Adobe の商標についての事実の陳述**であり、消す理由がない。FAQ も残すことを求めている。

### 著作権について

Noto Sans JP 自体の著作権表示は **Adobe のみ**（Source Han Sans 由来）で、**Google の
名前は元から入っていない**。合成後は Adobe と The Outfit Project Authors の2つになる。

## README に載せるクレジット

OFL の必須要件ではないが、元フォントのデザイナーは name テーブルから落ちるため、配布
パッケージの README に記載する。

- Noto Sans JP（Source Han Sans 由来）— 西塚涼子（かな・注音・漢字）、Paul D. Hunt
  （ラテン・ギリシャ・キリル）ほか
- Outfit — Rodrigo Fuenzalida（fragTYPE）
