"""palt の部分焼き込み（計画書 工程②）。

palt が持つ約物の字幅調整のうち、比率 f の分を hmtx とアウトラインに恒久的に書き込み、
残り (1 - f) を palt に書き戻す。既定状態が全角ベタと palt 全開の中間になり、CSS の
指定なしにどのブラウザでも同じ結果が得られる。

静的インスタンス化した後のフォントに適用すること。Noto Sans JP の palt は
FeatureVariations によりウェイトで内容が変わるため、可変のまま適用すると
どのウェイトの値を焼いたのか曖昧になる。
"""
from __future__ import annotations

SINGLE_POS = 1
EXTENSION_POS = 9


def _iter_subtables(lookup):
    """Extension を剥がして SinglePos サブテーブルを返す。"""
    for st in lookup.SubTable:
        if lookup.LookupType == EXTENSION_POS:
            st = st.ExtSubTable
        if getattr(st, 'Format', None) in (1, 2) and hasattr(st, 'Coverage'):
            yield st


def _lookup_indices(font, tag='palt'):
    gpos = font['GPOS'].table
    idxs = set()
    for rec in gpos.FeatureList.FeatureRecord:
        if rec.FeatureTag == tag:
            idxs.update(rec.Feature.LookupListIndex)
    return sorted(idxs)


def collect_adjustments(font, tag='palt'):
    """グリフ名 -> (XAdvance 合計, XPlacement 合計)。

    同じ feature に複数の lookup がぶら下がる場合（Noto の重いウェイト）、
    シェイピング時は累積して適用されるため合計をとる。
    """
    gpos = font['GPOS'].table
    acc: dict[str, tuple[int, int]] = {}
    for i in _lookup_indices(font, tag):
        for st in _iter_subtables(gpos.LookupList.Lookup[i]):
            glyphs = st.Coverage.glyphs
            values = st.Value if isinstance(st.Value, list) else [st.Value] * len(glyphs)
            for name, value in zip(glyphs, values):
                xa = getattr(value, 'XAdvance', 0) or 0
                xp = getattr(value, 'XPlacement', 0) or 0
                prev = acc.get(name, (0, 0))
                acc[name] = (prev[0] + xa, prev[1] + xp)
    return acc


def _shift_x(glyf, name, dx):
    """アウトラインを水平に平行移動する。"""
    if dx == 0:
        return
    glyph = glyf[name]
    if glyph.isComposite():
        for component in glyph.components:
            component.x += dx
    elif glyph.numberOfContours > 0:
        coords = glyph.coordinates
        for i in range(len(coords)):
            x, y = coords[i]
            coords[i] = (x + dx, y)
        glyph.recalcBounds(glyf)


def _scale_values_in_place(font, fraction, tag='palt'):
    """palt の値を残り (1 - fraction) に書き換える。

    Format 1 では 1つの Value オブジェクトが複数グリフに共有され、さらに複数の lookup
    から参照されうるため、同一オブジェクトを二重に縮めないよう id で管理する。
    """
    gpos = font['GPOS'].table
    remain = 1.0 - fraction
    seen: set[int] = set()
    for i in _lookup_indices(font, tag):
        for st in _iter_subtables(gpos.LookupList.Lookup[i]):
            values = st.Value if isinstance(st.Value, list) else [st.Value]
            for value in values:
                if value is None or id(value) in seen:
                    continue
                seen.add(id(value))
                if getattr(value, 'XAdvance', None):
                    value.XAdvance = round(remain * value.XAdvance)
                if getattr(value, 'XPlacement', None):
                    value.XPlacement = round(remain * value.XPlacement)


def bake(font, fraction, tag='palt'):
    """palt の fraction 分を hmtx / アウトラインに焼き込む。font を破壊的に変更する。

    Returns: 焼き込んだグリフ数
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f'fraction は 0.0〜1.0 の範囲: {fraction}')
    if fraction == 0.0:
        return 0
    if 'GPOS' not in font:
        raise ValueError('GPOS がない')

    adjustments = collect_adjustments(font, tag)
    if not adjustments:
        raise ValueError(f'{tag} が見つからない')

    hmtx, glyf = font['hmtx'], font['glyf']
    baked = 0
    for name, (xa, xp) in adjustments.items():
        if name not in hmtx.metrics:
            continue
        d_adv, dx = round(fraction * xa), round(fraction * xp)
        if d_adv == 0 and dx == 0:
            continue
        advance, lsb = hmtx.metrics[name]
        _shift_x(glyf, name, dx)
        hmtx.metrics[name] = (advance + d_adv, lsb + dx)
        baked += 1

    _scale_values_in_place(font, fraction, tag)
    return baked
