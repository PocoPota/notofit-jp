"""palt の部分焼き込み（計画書 工程②）。

palt が持つ字幅調整のうち、比率 f の分を hmtx とアウトラインに恒久的に書き込み、
残り (1 - f) を palt に書き戻す。CSS の指定なしにどのブラウザでも同じ結果が得られる。

比率はカテゴリごとに指定する。palt の対象は約物だけでなく、かな・全角英字・全角数字を
含むため、一律に扱うと約物の詰め具合とかなのプロポーショナル化を別々に決められない。
約物は焼き込まず全角のまま残し、隣接時の処理は kern に任せる（notofit/yakumono.py）。

静的インスタンス化した後のフォントに適用すること。Noto Sans JP の palt は
FeatureVariations によりウェイトで内容が変わるため、可変のまま適用すると
どのウェイトの値を焼いたのか曖昧になる。
"""
from __future__ import annotations

SINGLE_POS = 1
EXTENSION_POS = 9

#: カテゴリごとの既定の焼き込み比率
DEFAULT_FRACTIONS = {
    'kana': 1.0,        # ひらがな・カタカナ — プロポーショナル化する
    'latin': 1.0,       # 全角英字・全角数字 — 同上
    'yakumono': 0.0,    # 約物 — 全角のまま。隣接処理は kern が担う
    'other': 0.0,       # 分類できないもの — 触らない
}


#: 約物として扱う符号位置。U+30FB「・」はカタカナのブロックにあるが約物であり、
#: kana に含めると焼き込まれて半角になってしまうため個別に指定する。
_YAKUMONO_RANGES = (
    (0x3000, 0x303F),   # CJK の約物（。、「」など）
    (0x30FB, 0x30FB),   # ・（カタカナ中点）
    (0xFF01, 0xFF0F), (0xFF1A, 0xFF20), (0xFF3B, 0xFF40), (0xFF5B, 0xFF65),
    (0x2018, 0x201F),   # 引用符
)

#: かなとして扱う符号位置。約物と結合記号（U+3099〜309C）は除く。
_KANA_RANGES = (
    (0x3041, 0x3096), (0x309D, 0x309F),      # ひらがな・繰り返し記号
    (0x30A1, 0x30FA), (0x30FC, 0x30FF),      # カタカナ・長音符（・を除く）
    (0x31F0, 0x31FF),                        # 小書きカタカナ拡張
)

#: 全角英数
_LATIN_RANGES = ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A))


def _in(codepoint, ranges):
    return any(low <= codepoint <= high for low, high in ranges)


def categorize(codepoint):
    """符号位置を焼き込みカテゴリに分類する。"""
    if codepoint is None:
        return 'other'
    if _in(codepoint, _YAKUMONO_RANGES):
        return 'yakumono'
    if _in(codepoint, _KANA_RANGES):
        return 'kana'
    if _in(codepoint, _LATIN_RANGES):
        return 'latin'
    return 'other'


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


def _glyph_fractions(font, fractions):
    """グリフ名 -> 焼き込み比率。カテゴリ分類を符号位置から引く。"""
    reverse = {}
    for codepoint, name in font.getBestCmap().items():
        reverse.setdefault(name, codepoint)
    return {name: fractions.get(categorize(reverse.get(name)), 0.0)
            for name in font.getGlyphOrder()}


def _scale_values_in_place(font, per_glyph, tag='palt'):
    """palt の値を、グリフごとの残り (1 - f) に書き換える。

    Format 2 は Value がグリフごとに並ぶためカテゴリ別に扱える。Format 1 は 1つの
    Value を Coverage 全体で共有するため、比率が割れる場合は分割できず例外とする。
    同一オブジェクトが複数の lookup から参照されうるため、二重に縮めないよう id で管理する。
    """
    gpos = font['GPOS'].table
    seen: set[int] = set()
    for i in _lookup_indices(font, tag):
        for st in _iter_subtables(gpos.LookupList.Lookup[i]):
            glyphs = st.Coverage.glyphs
            if isinstance(st.Value, list):
                pairs = zip(glyphs, st.Value)
            else:
                distinct = {per_glyph.get(g, 0.0) for g in glyphs}
                if len(distinct) > 1:
                    raise ValueError(
                        'SinglePos Format 1 の Coverage にカテゴリの異なるグリフが混在し、'
                        'カテゴリ別の比率を適用できない')
                pairs = [(glyphs[0], st.Value)] if glyphs else []
            for name, value in pairs:
                if value is None or id(value) in seen:
                    continue
                seen.add(id(value))
                remain = 1.0 - per_glyph.get(name, 0.0)
                if getattr(value, 'XAdvance', None):
                    value.XAdvance = round(remain * value.XAdvance)
                if getattr(value, 'XPlacement', None):
                    value.XPlacement = round(remain * value.XPlacement)


def bake(font, fractions=None, tag='palt'):
    """palt をカテゴリ別の比率で hmtx / アウトラインに焼き込む。font を破壊的に変更する。

    fractions: カテゴリ -> 比率（0.0〜1.0）。数値を渡すと全カテゴリに一律で適用する。
               省略時は DEFAULT_FRACTIONS。

    Returns: 焼き込んだグリフ数
    """
    if fractions is None:
        fractions = DEFAULT_FRACTIONS
    elif isinstance(fractions, (int, float)):
        fractions = {key: float(fractions) for key in DEFAULT_FRACTIONS}
    for key, value in fractions.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f'{key} の比率は 0.0〜1.0 の範囲: {value}')
    if 'GPOS' not in font:
        raise ValueError('GPOS がない')
    if not any(fractions.values()):
        return 0

    adjustments = collect_adjustments(font, tag)
    if not adjustments:
        raise ValueError(f'{tag} が見つからない')

    per_glyph = _glyph_fractions(font, fractions)
    hmtx, glyf = font['hmtx'], font['glyf']
    baked = 0
    for name, (xa, xp) in adjustments.items():
        if name not in hmtx.metrics:
            continue
        fraction = per_glyph.get(name, 0.0)
        d_adv, dx = round(fraction * xa), round(fraction * xp)
        if d_adv == 0 and dx == 0:
            continue
        advance, lsb = hmtx.metrics[name]
        _shift_x(glyf, name, dx)
        hmtx.metrics[name] = (advance + d_adv, lsb + dx)
        baked += 1

    _scale_values_in_place(font, per_glyph, tag)
    return baked
