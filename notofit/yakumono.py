"""約物の隣接処理と、不要な feature の削除（計画書 工程②）。

約物の字幅は全角のまま変更せず、隣接したときに重複するアキだけを kern のペア調整で
取り除く。単独の約物は全角ベタが JLREQ どおり正しいため、詰めるのは隣接時だけでよい。

詳細と決定経緯は docs/yakumono.md。
"""
from __future__ import annotations

from fontTools.otlLib.builder import buildPairPosClassesSubtable, buildValue
from fontTools.ttLib.tables import otTables as ot

# JLREQ の文字クラスに対応する分類。インクが字面のどちら側に寄っているかで挙動が決まる。
CLASSES = {
    'open':   '「『（〔［｛〈《【〖〘〚',      # 始め括弧類 — インクは右半分
    'close':  '」』）〕］｝〉》】〗〙〛',      # 終わり括弧類 — インクは左半分
    'period': '。、．，',                     # 句点類・読点類 — インクは左下
    'middle': '・：；',                        # 中点類 — インクは中央、左右に四分
}

# (前のクラス, 後のクラス) -> 引く量の種類。表にない組み合わせは 0（調整しない）。
# 「その他」（かな・漢字）との組み合わせがすべて 0 であることが要点で、約物が単独で
# 現れる限り字送りは変わらない。
#
# いずれも既定は -500（二分）である。全角ベタでは空いている側が向かい合って二分ぶん
# 余計にアキができるため、それを取り除くと JLREQ の目標値になる。
#   」「 → 字面の間隔が二分アキ（連続する括弧の規定値）
#   「『 → ベタ（連続する始め括弧の規定値）
#   」・ → 四分アキ（中点類の前後の規定値）
# 中点は前後に四分しか持たないため引く量が違うように見えるが、実際は同じ -500 で
# 目標に届く。値を分けているのは、中点まわりだけ緩めたい場合に触れるようにするため。
MATRIX = {
    ('open',   'open'):   'pair',
    ('close',  'open'):   'pair',
    ('close',  'close'):  'pair',
    ('close',  'period'): 'pair',
    ('period', 'open'):   'pair',
    ('period', 'close'):  'pair',
    ('period', 'period'): 'pair',
    ('close',  'middle'): 'middle',
    ('period', 'middle'): 'middle',
    ('middle', 'open'):   'middle',
}


def _glyphs_for(font, chars):
    cmap = font.getBestCmap()
    return {cmap[ord(c)] for c in chars if ord(c) in cmap}


def build_pairs(font, pair=-500, middle=-500):
    """クラス行列から PairPos 用のペア定義を作る。

    値は前のグリフの advance に加算する（負で詰まる）。後続グリフが左へ寄り、
    2文字の合計幅もその分だけ縮む。
    """
    amounts = {'pair': pair, 'middle': middle}
    # ClassDefBuilder.classes() はソート済みタプルを返すため、キーも同じ型で作る。
    # frozenset だと buildPairPosClassesSubtable 内の照合が空振りし、値がすべて 0 になる。
    classes = {name: tuple(sorted(_glyphs_for(font, chars))) for name, chars in CLASSES.items()}
    pairs = {}
    for (first, second), kind in MATRIX.items():
        value = amounts[kind]
        if value == 0 or not classes[first] or not classes[second]:
            continue
        pairs[(classes[first], classes[second])] = (buildValue({'XAdvance': value}), buildValue({}))
    return pairs


def _kern_lookup_indices(font):
    gpos = font['GPOS'].table
    return {i for rec in gpos.FeatureList.FeatureRecord if rec.FeatureTag == 'kern'
            for i in rec.Feature.LookupListIndex}


def add_kern_pairs(font, pair=-500, middle=-500):
    """約物の隣接ペア調整を kern feature に追加する。font を破壊的に変更する。

    Returns: 追加したペア（クラスの組）の数
    """
    if 'GPOS' not in font:
        raise ValueError('GPOS がない')
    pairs = build_pairs(font, pair, middle)
    if not pairs:
        return 0

    gpos = font['GPOS'].table
    subtable = buildPairPosClassesSubtable(pairs, font.getReverseGlyphMap())

    lookup = ot.Lookup()
    lookup.LookupType = 2               # PairPos
    lookup.LookupFlag = 0
    lookup.SubTable = [subtable]
    lookup.SubTableCount = 1

    index = len(gpos.LookupList.Lookup)
    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)

    # 既存の kern に追加する。lookup は FeatureRecord ごとに順序を持つため末尾に足す。
    added = False
    for rec in gpos.FeatureList.FeatureRecord:
        if rec.FeatureTag == 'kern':
            rec.Feature.LookupListIndex.append(index)
            rec.Feature.LookupCount = len(rec.Feature.LookupListIndex)
            added = True
    if not added:
        raise ValueError('kern feature が見つからない')
    return len(pairs)


def remove_features(font, tags, table_tags=('GPOS', 'GSUB')):
    """指定した feature を削除する。font を破壊的に変更する。

    halt を残すと Chromium が text-spacing-trim で上乗せし、kern と二重適用になる。
    縦組み用の vhal / vpal / vkrn は横書き限定の方針により不要。

    Returns: 削除した FeatureRecord の数
    """
    tags = set(tags)
    removed = 0
    for table_tag in table_tags:
        if table_tag not in font:
            continue
        table = font[table_tag].table
        if not table.FeatureList:
            continue
        records = table.FeatureList.FeatureRecord
        drop = {i for i, rec in enumerate(records) if rec.FeatureTag in tags}
        if not drop:
            continue

        # 残す FeatureRecord の新しい添字を作る
        remap, new_index = {}, 0
        for i in range(len(records)):
            if i not in drop:
                remap[i] = new_index
                new_index += 1

        table.FeatureList.FeatureRecord = [r for i, r in enumerate(records) if i not in drop]
        table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)

        # LangSys が持つ添字を張り替える
        for script_rec in table.ScriptList.ScriptRecord:
            script = script_rec.Script
            lang_systems = [script.DefaultLangSys] if script.DefaultLangSys else []
            lang_systems += [r.LangSys for r in script.LangSysRecord]
            for lang_sys in lang_systems:
                lang_sys.FeatureIndex = [remap[i] for i in lang_sys.FeatureIndex if i in remap]
                lang_sys.FeatureCount = len(lang_sys.FeatureIndex)
                if lang_sys.ReqFeatureIndex != 0xFFFF:
                    lang_sys.ReqFeatureIndex = remap.get(lang_sys.ReqFeatureIndex, 0xFFFF)
        removed += len(drop)
    return removed
