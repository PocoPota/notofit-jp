"""サブセットの区切りを Google Fonts から取得する（計画書 工程⑤）。

文字頻度の分析は行わず、Google Fonts が Noto Sans JP に用いている unicode-range の
区切りをそのまま採用する（方針7）。数百万の日本語ページから集めた頻度データの結果が、
すでにその区切りに反映されているため。

取得結果は config/slices.json に保存し、ビルドはそれを読む。ビルドのたびに取りに行くと
再現性がなく、Google 側の変更でいつのまにか区切りが変わることになるため。
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

CSS_URL = ('https://fonts.googleapis.com/css2'
           '?family=Noto+Sans+JP:wght@100..900&display=swap')

# woff2 のスライスを返させるため、対応ブラウザの UA を送る
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')

_RANGE = re.compile(r'unicode-range:\s*([^;}]+)')


def fetch(url: str = CSS_URL) -> list[str]:
    """Google Fonts の CSS から unicode-range を順に取り出す。

    同じ区切りが各ウェイトぶん繰り返されるため、重複は順序を保って除く。
    """
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request) as response:
        css = response.read().decode('utf-8')

    seen, ranges = set(), []
    for match in _RANGE.finditer(css):
        value = ' '.join(match.group(1).split())
        if value not in seen:
            seen.add(value)
            ranges.append(value)
    if not ranges:
        raise ValueError('unicode-range が取得できなかった')
    return ranges


def to_unicodes(unicode_range: str) -> str:
    """CSS の unicode-range を pyftsubset の --unicodes 形式に変換する。

    U+3000-303F, U+FF01 -> 3000-303F,FF01
    """
    parts = [p.strip().removeprefix('U+').removeprefix('u+')
             for p in unicode_range.split(',')]
    return ','.join(p for p in parts if p)


def save(path, ranges: list[str], source: str = CSS_URL):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(
        {'source': source, 'count': len(ranges), 'ranges': ranges},
        ensure_ascii=False, indent=2) + '\n')


def load(path) -> list[str]:
    data = json.loads(Path(path).read_text())
    return data['ranges']


def to_range(codepoints) -> str:
    """符号位置の集合を CSS の unicode-range 表記にまとめる。"""
    out, ordered = [], sorted(codepoints)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        out.append(f'U+{ordered[i]:04X}' if i == j
                   else f'U+{ordered[i]:04X}-{ordered[j]:04X}')
        i = j + 1
    return ', '.join(out)


def expand(unicode_range: str) -> set[int]:
    """CSS の unicode-range を符号位置の集合に展開する。"""
    out = set()
    for part in to_unicodes(unicode_range).split(','):
        if not part:
            continue
        if '-' in part:
            low, high = part.split('-')
            out.update(range(int(low, 16), int(high, 16) + 1))
        else:
            out.add(int(part, 16))
    return out


def isolate(ranges: list[str], codepoints) -> list[str]:
    """指定した符号位置だけを1つのスライスに集め、他のスライスからは取り除く。

    ブラウザはフォントをまたいでカーニングを適用しないため、`kern` のペア調整で
    処理する約物が別々のスライスに入ると調整が効かない。`。」` のような頻出の
    組み合わせが対象になるため、まとめて1つのスライスに置く。
    → docs/yakumono.md
    """
    wanted = set(codepoints)
    out = []
    for unicode_range in ranges:
        rest = expand(unicode_range) - wanted
        if rest:
            out.append(to_range(rest))
    present = {cp for r in ranges for cp in expand(r)} & wanted
    if present:
        out.append(to_range(present))
    return out
