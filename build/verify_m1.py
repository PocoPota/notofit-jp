"""M1 検証: 合成結果が方針2（Noto 基準・欧文を合わせる）を満たすか確認する。

  .venv/bin/python build/verify_m1.py
"""
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.recordingPen import RecordingPen
import uharfbuzz as hb

OUT = 'build/NotofitJP-Regular.ttf'
WGHT = 400
results = []


def check(label, cond, detail=''):
    results.append(cond)
    mark = '\033[32mPASS\033[0m' if cond else '\033[31mFAIL\033[0m'
    print(f'  {label:52} {detail:24} {mark}')


def contour(font, cp):
    cm = font.getBestCmap()
    if cp not in cm:
        return None
    pen = RecordingPen()
    font.getGlyphSet()[cm[cp]].draw(pen)
    return pen.value


def same_shape(a, b, tol=1):
    """輪郭が同一か。マージエンジンと instancer で丸め順序が異なり ±1 ユニットずれるため、
    1000upem で 1 ユニットの許容差を持たせる（視覚的に同一）。"""
    if a is None or b is None or len(a) != len(b):
        return False
    for (op_a, pts_a), (op_b, pts_b) in zip(a, b):
        if op_a != op_b or len(pts_a) != len(pts_b):
            return False
        for pa, pb in zip(pts_a, pts_b):
            if any(abs(x - y) > tol for x, y in zip(pa, pb)):
                return False
    return True


out = TTFont(OUT)
noto = instancer.instantiateVariableFont(TTFont('sources/NotoSansJP.ttf'), {'wght': WGHT})
outfit = instancer.instantiateVariableFont(TTFont('sources/Outfit.ttf'), {'wght': WGHT})

print('\n=== 1. 基本 ===')
print(f'  グリフ数: Noto {noto["maxp"].numGlyphs} + Outfit {outfit["maxp"].numGlyphs}'
      f' -> 合成 {out["maxp"].numGlyphs}')
check('静的フォントとして出力されている', 'fvar' not in out, 'fvar なし')
check('upem が 1000 で維持されている', out['head'].unitsPerEm == 1000, str(out['head'].unitsPerEm))
check('アウトラインが glyf', 'glyf' in out)

print('\n=== 2. 縦メトリクス（既定の行の高さが Noto と一致すること） ===')
o_out, o_noto, h_out, h_noto = out['OS/2'], noto['OS/2'], out['hhea'], noto['hhea']
check('hhea が Noto と一致',
      (h_out.ascender, h_out.descender, h_out.lineGap) == (h_noto.ascender, h_noto.descender, h_noto.lineGap),
      f'{h_out.ascender}/{h_out.descender}')
check('usWin が Noto と一致',
      (o_out.usWinAscent, o_out.usWinDescent) == (o_noto.usWinAscent, o_noto.usWinDescent),
      f'{o_out.usWinAscent}/{o_out.usWinDescent}')
use_typo = bool(o_out.fsSelection & (1 << 7))
check('USE_TYPO_METRICS が Noto と同じ', use_typo == bool(o_noto.fsSelection & (1 << 7)), str(use_typo))
lh_out = (h_out.ascender - h_out.descender + h_out.lineGap) / 1000
lh_noto = (h_noto.ascender - h_noto.descender + h_noto.lineGap) / 1000
check('既定 line-height 相当が一致', lh_out == lh_noto, f'{lh_out:.3f}em')
print(f'  ※ sTypo は Outfit 由来 {o_out.sTypoAscender}/{o_out.sTypoDescender}'
      f'（Noto {o_noto.sTypoAscender}/{o_noto.sTypoDescender}）。'
      f'USE_TYPO_METRICS={use_typo} のため行の高さには影響しない')

print('\n=== 3. 和文の字送り（Noto から変わっていないこと） ===')
cm_out, cm_noto = out.getBestCmap(), noto.getBestCmap()
same = all(out['hmtx'].metrics[cm_out[ord(c)]][0] == noto['hmtx'].metrics[cm_noto[ord(c)]][0]
           for c in 'あ漢、。「」ＡＢ１々ー')
check('全角の advance が Noto と一致', same, '1000 で不変')

print('\n=== 4. ラテンの出所 ===')
latin_src = {}
for ch in 'AaGgQ?:;10&@':
    cp = ord(ch)
    c = contour(out, cp)
    latin_src[ch] = ('Outfit' if same_shape(c, contour(outfit, cp))
                     else 'Noto' if same_shape(c, contour(noto, cp)) else '不明')
check('ラテンがすべて Outfit 由来', set(latin_src.values()) == {'Outfit'},
      ' '.join(sorted(set(latin_src.values()))))
adv_ok = all(out['hmtx'].metrics[cm_out[ord(c)]][0] == outfit['hmtx'].metrics[outfit.getBestCmap()[ord(c)]][0]
             for c in 'AaGgQ?:;10&@')
check('ラテンの advance が Outfit と一致', adv_ok)

print('\n=== 5. cmap の網羅 ===')
miss_n = set(cm_noto) - set(cm_out)
miss_f = set(outfit.getBestCmap()) - set(cm_out)
check('Noto の符号位置が全て残っている', not miss_n, f'欠落 {len(miss_n)}')
check('Outfit の符号位置が全て残っている', not miss_f, f'欠落 {len(miss_f)}')

print('\n=== 6. OpenType feature ===')
def feats(f, tag):
    return {fr.FeatureTag for fr in f[tag].table.FeatureList.FeatureRecord} if tag in f else set()
for tag in ('GSUB', 'GPOS'):
    lost = feats(noto, tag) - feats(out, tag)
    check(f'{tag}: Noto の feature が欠落していない', not lost, f'{len(feats(out, tag))}種')
lost_sub = feats(outfit, 'GSUB') - feats(out, 'GSUB') - {'rvrn'}  # rvrn は可変専用のため除外
check('GSUB: Outfit の feature が欠落していない', not lost_sub, str(sorted(lost_sub) or ''))
check('palt / kern が残っている', {'palt', 'kern'} <= feats(out, 'GPOS') | feats(out, 'GSUB'))

print('\n=== 7. シェイピング（和欧混植） ===')
font = hb.Font(hb.Face(hb.Blob.from_file_path(OUT)))
def shape(text, features=None):
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, features)
    return buf.glyph_infos, buf.glyph_positions
order = out.getGlyphOrder()
for text in ('日本語とEnglishの混植', 'Ag：: 12'):
    infos, _ = shape(text)
    names = [order[i.codepoint] for i in infos]
    check(f'"{text}" が .notdef なしで組める', names.count('.notdef') == 0, f'{len(names)}グリフ')
w = lambda t, f=None: sum(p.x_advance for p in shape(t, f)[1]) / 1000
for t in ('」「', '）（', 'あ、い。う'):
    d, p = w(t), w(t, {'palt': True})
    check(f'palt が効く: {t}', p < d, f'{d:.3f} -> {p:.3f}em')

print('\n=== 8. 参考: 和欧の相対サイズ（無調整の現状） ===')
bh = lambda f, ch: (lambda g: g.yMax - g.yMin if g.numberOfContours else 0)(f['glyf'][f.getBestCmap()[ord(ch)]])
print(f'  合成: H={bh(out, "H")} x={bh(out, "x")} あ={bh(out, "あ")}')
print(f'  Noto: H={bh(noto, "H")} x={bh(noto, "x")}  ← 欧文をここへ寄せる SCALE を M2 で決める')

print(f'\n{"=" * 60}\n  {sum(results)}/{len(results)} PASS'
      f'{"" if all(results) else "  ← 要調査"}\n{"=" * 60}')
raise SystemExit(0 if all(results) else 1)
