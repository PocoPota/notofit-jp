"""本番ビルド（計画書 工程⑤⑥と配布物の組み立て）。

    .venv/bin/python -m notofit.release            dist/ を作る
    .venv/bin/python -m notofit.release --slices   区切りを取り直す

設定（config/tuning.json と config/glyph-shifts.json）を読み、合成 → サブセット分割 →
CSS 生成まで通して dist/ を作る。調整ツールのプレビューと同じ notofit.build を経由する
ため、調整画面で見たものと配布物が食い違わない。
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import time
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

from . import slices
from . import __version__
from .build import (ROOT, SHIFT_CONFIG, PROJECT, PROJECT_URL,
                    TuningConfig, build_weight)
from .glyphshift import ShiftConfig
from .yakumono import CLASSES

CONFIG = ROOT / 'config' / 'tuning.json'
SLICES = ROOT / 'config' / 'slices.json'
OFL = ROOT / 'OFL.txt'
DIST = ROOT / 'dist'

#: サブセットに残す name レコード。0（著作権）と 14（ライセンス URL）を明示的に残す。
#: pyftsubset の既定は 0〜6 のみで 14 が落ちる。→ docs/notes/name-table.md
NAME_IDS = [0, 1, 2, 3, 4, 5, 6, 14]

#: `kern` のペア調整の対象。1つのスライスにまとめる（→ slices.isolate）
YAKUMONO = {ord(c) for chars in CLASSES.values() for c in chars}


def _codepoints(unicode_range: str) -> list[int]:
    """CSS の unicode-range を符号位置の一覧に展開する。"""
    out = []
    for part in slices.to_unicodes(unicode_range).split(','):
        if not part:
            continue
        if '-' in part:
            low, high = part.split('-')
            out.extend(range(int(low, 16), int(high, 16) + 1))
        else:
            out.append(int(part, 16))
    return out


def subset_slice(data: bytes, unicode_range: str, dest: Path) -> dict:
    """1スライス分を切り出して woff2 で書き出す。"""
    font = TTFont(io.BytesIO(data))
    options = Options()
    options.layout_features = ['*']      # kern を含む feature を維持する
    options.name_IDs = NAME_IDS
    options.notdef_outline = True
    options.recalc_bounds = True
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=_codepoints(unicode_range))
    subsetter.subset(font)

    glyphs = font['maxp'].numGlyphs
    font.flavor = 'woff2'
    dest.parent.mkdir(parents=True, exist_ok=True)
    font.save(dest)
    font.close()
    return {'glyphs': glyphs, 'bytes': dest.stat().st_size}


def font_face(family: str, weight: int, url: str, unicode_range: str) -> str:
    return (
        '@font-face{'
        f'font-family:"{family}";'
        'font-style:normal;'
        f'font-weight:{weight};'
        'font-display:swap;'
        f'src:url("{url}") format("woff2");'
        f'unicode-range:{unicode_range}'
        '}\n'
    )


def package_json(family: str, stem: str, weights) -> str:
    """npm パッケージのメタデータ。バージョンはフォントの nameID 5 と同じ値を使う。"""
    return json.dumps({
        'name': stem,
        'version': __version__,
        'description': f'{family} — Outfit と Noto Sans JP を合成した和欧混植用フォント',
        'style': f'{stem}.css',
        'files': ['*.css', 'w', 'manifest.json', 'OFL.txt', 'README.md'],
        'keywords': ['font', 'webfont', 'japanese', 'cjk', 'woff2'],
        'license': 'OFL-1.1',
        'repository': {'type': 'git', 'url': f'git+{PROJECT_URL}.git'},
        'homepage': PROJECT_URL,
        'sideEffects': ['*.css'],
    }, ensure_ascii=False, indent=2) + '\n'


def readme(family: str, stem: str, weights) -> str:
    """配布パッケージの README。利用側が最初に読むもの。"""
    faces = ' / '.join(str(w) for w in weights)
    return f"""# {family}

Outfit と Noto Sans JP を合成した、Web 向けの和欧混植フォント。

Noto Sans JP を使っているページを `font-family` の差し替えだけで置き換えられることを
目標にしている。行の高さと、単独で現れる約物の字送りは Noto Sans JP と一致する。

ウェイトは {faces}。横書き専用。

## 使い方

```
npm install {stem}
```

```css
@import "{stem}/{stem}.css";          /* 全ウェイト */
/* または @import "{stem}/400.css"; のようにウェイト単位で */

body {{
  font-family: "{family}", sans-serif;
  text-autospace: normal;   /* 和欧間のアキ。書かないと付かない */
  font-kerning: normal;     /* 約物の隣接処理。Firefox 向けに必要 */
}}
```

`unicode-range` でスライスしてあるため、ページが実際に読み込むのは使用文字に対応する
十数個のファイルだけになる。

## 書いてはいけない CSS

| プロパティ | 何が起きるか |
| ---------- | ------------ |
| `font-kerning: none` | 約物の隣接処理が無効になり、`」「` が全角ベタに戻る |

`font-feature-settings` の `palt` / `halt` / `chws`、`size-adjust`、`ascent-override`、
`text-spacing-trim` は指定しても効果がない。字幅と縦メトリクスはフォント側で確定して
いるため。

## Noto Sans JP から変わること

| 項目 | 変化 |
| ---- | ---- |
| 行の高さ | **変わらない** |
| 単独の約物の字送り | **変わらない**（全角のまま） |
| 隣接した約物 | 詰まる（`」「` が 2.0em → 1.5em） |
| かな・全角英数の字送り | プロポーショナルになるため詰まる（本文で約 4.5%） |
| 欧文 | Outfit に置き換わる |

WebKit では、2文字目が始め括弧になる組み合わせ（`」「` など）で約物の詰めが効かない。
その位置で行分割が許されるため、ブラウザ側の処理でカーニングが届かない。

## もっと詳しく

仕様、ブラウザごとの挙動、置き換えたときの変化は利用ガイドにまとめています。
{PROJECT_URL}/blob/main/docs/usage.md

## ライセンス

SIL Open Font License 1.1（`OFL.txt`）。

- Noto Sans JP — Copyright 2014-2021 Adobe, with Reserved Font Name 'Source'
  デザイン: 西塚涼子（かな・注音・漢字）、Paul D. Hunt（ラテン・ギリシャ・キリル）ほか
- Outfit — Copyright 2021 The Outfit Project Authors
  デザイン: Rodrigo Fuenzalida（fragTYPE）
- {family} — Copyright 2026 {PROJECT}

`{PROJECT_URL}`
"""

def build(out_dir: Path = DIST, verbose: bool = True,
          ranges: list[str] | None = None) -> dict:
    """dist/ を作る。既存の内容は入れ替える。

    ranges を渡すと区切りを差し替える（テストで一部だけ通すため）。
    """
    cfg = TuningConfig.load(CONFIG)
    shifts = ShiftConfig.load(SHIFT_CONFIG)
    ranges = ranges if ranges is not None else slices.load(SLICES)
    # 約物は1つのスライトにまとめる。フォントをまたぐとカーニングが効かないため
    ranges = slices.isolate(ranges, YAKUMONO)
    family = cfg.familyName
    stem = family.lower().replace(' ', '-')

    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    manifest = {'family': family, 'version': __version__,
                'slices': len(ranges), 'weights': {}}
    all_css: list[str] = []
    started = time.time()

    for wc in cfg.weights:
        weight = wc.weight
        step = time.time()
        merged = build_weight(cfg, weight, out_dir / '_tmp',
                              shifts=shifts.for_weight(weight))
        data = Path(merged).read_bytes()
        if verbose:
            print(f'  {weight}: 合成 {time.time() - step:.1f}s ({len(data):,} bytes)')

        step, total, css = time.time(), 0, []
        for index, unicode_range in enumerate(ranges):
            rel = f'w/{weight}/{index:03d}.woff2'
            info = subset_slice(data, unicode_range, out_dir / rel)
            total += info['bytes']
            css.append(font_face(family, weight, f'./{rel}', unicode_range))
            if verbose and (index + 1) % 25 == 0:
                print(f'      スライス {index + 1}/{len(ranges)}')

        (out_dir / f'{weight}.css').write_text(''.join(css))
        all_css.extend(css)
        manifest['weights'][str(weight)] = {'files': len(ranges), 'bytes': total}
        if verbose:
            print(f'  {weight}: 分割 {len(ranges)}件 {time.time() - step:.1f}s '
                  f'(合計 {total:,} bytes)')

    shutil.rmtree(out_dir / '_tmp', ignore_errors=True)
    (out_dir / f'{stem}.css').write_text(''.join(all_css))
    if OFL.exists():
        shutil.copy(OFL, out_dir / 'OFL.txt')
    weights = [wc.weight for wc in cfg.weights]
    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (out_dir / 'package.json').write_text(package_json(family, stem, weights))
    (out_dir / 'README.md').write_text(readme(family, stem, weights))

    manifest['seconds'] = round(time.time() - started, 1)
    if verbose:
        print(f'\n  完了 {manifest["seconds"]}s -> {out_dir}')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description='Notofit JP の配布物を作る')
    parser.add_argument('--slices', action='store_true',
                        help='Google Fonts から unicode-range を取り直して保存する')
    parser.add_argument('--out', default=str(DIST), help='出力先（既定 dist/）')
    args = parser.parse_args(argv)

    if args.slices:
        ranges = slices.fetch()
        slices.save(SLICES, ranges)
        print(f'  {len(ranges)} 件を {SLICES} に保存した')
        return 0

    if not SLICES.exists():
        print(f'{SLICES} がない。--slices で取得する', file=sys.stderr)
        return 1
    build(Path(args.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
