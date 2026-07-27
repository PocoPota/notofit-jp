"""ビルドコア（計画書 工程①②③）。

設定値からフォントを生成する。プレビューと本番ビルドで同じ経路を通すことで、
調整画面で見たものと配布物が食い違わないようにする。

プレビューは sample text に出てくる文字だけへサブセットしてから処理するため、
生成が桁で速くなる（工程⑤のサブセット化を前倒しで使う）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
from dataclasses import dataclass, asdict, field
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.subset import Subsetter, Options

from .palt import bake

ROOT = Path(__file__).resolve().parent.parent
NOTO = ROOT / 'sources' / 'NotoSansJP.ttf'
OUTFIT = ROOT / 'sources' / 'Outfit.ttf'
CACHE = ROOT / 'build' / 'cache'


@dataclass
class WeightConfig:
    """出力ウェイト1つ分の設計値。"""
    weight: int             # 出力の font-weight（CSS 上の値）
    jaWght: int             # 和文のインスタンス化値。置き換え互換性のためラウンドな値
    latinWght: float        # 欧文のインスタンス化値。見かけの太さを揃える
    scale: float = 1.0      # 欧文の拡縮
    baselineOffset: int = 0  # 欧文の上下位置（フォントユニット）


@dataclass
class TuningConfig:
    """調整ツールが決める設計値の全体。"""
    weights: list[WeightConfig] = field(default_factory=list)
    paltFraction: float = 0.0
    excludeCodepoints: list[str] = field(default_factory=list)
    familyName: str = 'Notofit JP'

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        data['weights'] = [WeightConfig(**w) for w in data.get('weights', [])]
        return cls(**data)

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + '\n')

    def weight(self, w):
        for wc in self.weights:
            if wc.weight == w:
                return wc
        raise KeyError(f'ウェイト {w} が設定にない')


def _key(*parts):
    return hashlib.sha1('|'.join(map(str, parts)).encode()).hexdigest()[:16]


def _subset(src: Path, text: str, dest: Path):
    """text に出てくる文字だけへサブセットする。可変軸と layout feature は維持する。"""
    font = TTFont(src)
    opts = Options()
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    opts.recalc_bounds = True
    sub = Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    font.save(dest)
    font.close()


def prepare_base(wght: int, palt_fraction: float, text: str | None = None) -> Path:
    """和文（Noto）を静的化し palt を焼き込んだ TTF を作る。結果はキャッシュする。

    text を渡すと先にサブセットしてから処理する（プレビュー用）。
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f'noto-{wght}-p{palt_fraction}-{_key(text or "full")}.ttf'
    if dest.exists():
        return dest

    src = NOTO
    if text:
        # サブセットしてから静的化する。フル版の静的化は約4秒かかるため。
        sub_path = CACHE / f'noto-sub-{_key(text)}.ttf'
        if not sub_path.exists():
            _subset(NOTO, text, sub_path)
        src = sub_path

    font = instancer.instantiateVariableFont(TTFont(src), {'wght': wght}, updateFontNames=False)
    if palt_fraction > 0:
        bake(font, palt_fraction)
    font.save(dest)
    font.close()
    return dest


def prepare_sub(text: str | None = None) -> Path:
    """欧文（Outfit）を用意する。可変のまま渡し、インスタンス化は合成ツールに任せる。"""
    if not text:
        return OUTFIT
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f'outfit-sub-{_key(text)}.ttf'
    if not dest.exists():
        _subset(OUTFIT, text, dest)
    return dest


def merge(base: Path, sub: Path, wc: WeightConfig, cfg: TuningConfig,
          out_ttf: Path, out_woff2: Path | None = None) -> dict:
    """合成する。base は静的化済み、sub は可変のまま渡してツール側で固定する。"""
    import merge_fonts

    config = {
        'baseFont': {'path': str(base), 'scale': 1.0, 'baselineOffset': 0, 'axes': []},
        'subFont': {
            'path': str(sub),
            'scale': wc.scale,
            'baselineOffset': wc.baselineOffset,
            'axes': [{'tag': 'wght', 'currentValue': wc.latinWght}],
            'excludeCodepoints': cfg.excludeCodepoints,
        },
        'output': {
            'familyName': cfg.familyName,
            'weight': wc.weight,
            'metricsSource': 'base',   # 縦メトリクスは和文側に固定（置き換え互換性）
        },
        'export': {'path': {'font': str(out_ttf)}},
    }
    if out_woff2:
        config['export']['path']['woff2'] = str(out_woff2)

    out_ttf.parent.mkdir(parents=True, exist_ok=True)
    saved = sys.argv, sys.stdin, sys.stdout, sys.stderr
    try:
        sys.argv = ['merge_fonts.py']
        sys.stdin = io.StringIO(json.dumps(config))
        sys.stdout = io.StringIO()          # 出力パスの表示を抑える
        sys.stderr = io.StringIO()          # 進捗 JSON と Coverage 警告を抑える
        merge_fonts.main()
    finally:
        sys.argv, sys.stdin, sys.stdout, sys.stderr = saved
    return config


def build_weight(cfg: TuningConfig, weight: int, out_dir: Path,
                 text: str | None = None, woff2: bool = False) -> Path:
    """1ウェイト分を生成する。text を渡すとその文字だけのプレビュー用フォントになる。"""
    wc = cfg.weight(weight)
    base = prepare_base(wc.jaWght, cfg.paltFraction, text)
    sub = prepare_sub(text)
    stem = f'NotofitJP-{weight}'
    out_ttf = Path(out_dir) / f'{stem}.ttf'
    out_woff2 = Path(out_dir) / f'{stem}.woff2' if woff2 else None
    merge(base, sub, wc, cfg, out_ttf, out_woff2)
    return out_woff2 or out_ttf
