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
from .build import ROOT, SHIFT_CONFIG, TuningConfig, build_weight
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

    manifest = {'family': family, 'slices': len(ranges), 'weights': {}}
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
    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

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
