"""グリフ単位の垂直調整（計画書 工程④）。

Outfit のコロン類は自身の x-height 中心より低く配置されており、和文の全角コロンと
並ぶとさらに差が開く。対象のグリフだけをアウトラインごと垂直移動する。

水平方向の調整と違い hmtx は触らない。垂直方向の移動は字送りに影響しないため。

合成の後（＝静的化の後）に適用する。ウェイトごとに最適値が異なりうるため、設定も
ウェイトごとに持つ。
"""
from __future__ import annotations

import json
from pathlib import Path


class ShiftConfig:
    """ウェイトごとの、文字 -> 垂直移動量（1000 upem 単位、正で上）。"""

    def __init__(self, weights=None):
        self.weights: dict[str, dict[str, int]] = weights or {}

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls({str(k): {c: int(v) for c, v in shifts.items()}
                    for k, shifts in data.get('weights', {}).items()})

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps({'weights': self.weights}, ensure_ascii=False, indent=2) + '\n')

    def for_weight(self, weight) -> dict[str, int]:
        return self.weights.get(str(weight), {})

    def set_for_weight(self, weight, shifts):
        self.weights[str(weight)] = {c: int(v) for c, v in shifts.items() if int(v) != 0}


def _shift_y(glyf, name, dy):
    glyph = glyf[name]
    if glyph.isComposite():
        for component in glyph.components:
            component.y += dy
    elif glyph.numberOfContours > 0:
        coords = glyph.coordinates
        for i in range(len(coords)):
            x, y = coords[i]
            coords[i] = (x, y + dy)
        glyph.recalcBounds(glyf)


def apply(font, shifts):
    """文字 -> 移動量 を適用する。font を破壊的に変更する。

    Returns: 実際に動かしたグリフ数
    """
    if not shifts:
        return 0
    cmap, glyf = font.getBestCmap(), font['glyf']
    moved = 0
    for char, dy in shifts.items():
        dy = int(dy)
        if dy == 0 or not char:
            continue
        codepoint = ord(char[0])
        name = cmap.get(codepoint)
        if name is None:
            continue
        _shift_y(glyf, name, dy)
        moved += 1
    return moved


def measure(font, chars):
    """文字ごとの字面の上下と中心を返す。基準線を引くために使う。"""
    cmap, glyf = font.getBestCmap(), font['glyf']
    out = {}
    for char in chars:
        name = cmap.get(ord(char))
        if name is None:
            continue
        glyph = glyf[name]
        if glyph.numberOfContours == 0:
            continue
        out[char] = {
            'yMin': glyph.yMin,
            'yMax': glyph.yMax,
            'center': (glyph.yMin + glyph.yMax) / 2,
            'advance': font['hmtx'].metrics[name][0],
        }
    return out
