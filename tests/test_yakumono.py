"""約物処理の検証: kern ペアが隣接時だけ効き、halt 系が削除されていること。"""
import sys, io
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
import uharfbuzz as hb
sys.path.insert(0, '.')
from notofit.palt import bake, DEFAULT_FRACTIONS
from notofit.yakumono import add_kern_pairs, remove_features

ok = lambda c: '\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
res = []
def check(label, cond, detail=''):
    res.append(cond); print(f'  {label:42} {detail:22} {ok(cond)}')

def shaper(font):
    b = io.BytesIO(); font.save(b); f = hb.Font(hb.Face(hb.Blob(b.getvalue())))
    def w(t, feat=None):
        buf = hb.Buffer(); buf.add_str(t); buf.guess_segment_properties(); hb.shape(f, buf, feat)
        return sum(p.x_advance for p in buf.glyph_positions) / 1000
    return w

for wght in range(100, 1000, 100):
    print(f'\n=== wght={wght} ===')
    font = instancer.instantiateVariableFont(TTFont('sources/NotoSansJP.ttf'), {'wght': wght})
    before = shaper(font)
    b = bake(font, DEFAULT_FRACTIONS)
    n = add_kern_pairs(font)
    r = remove_features(font, ('halt', 'vhal', 'vpal', 'vkrn'))
    # palt は本番では削除するが、このテストは焼き込みの効きを見るため残す
    w = shaper(font)
    print(f'  焼込={b}グリフ kernペア={n}組 削除feature={r}件')

    print('  -- 隣接する約物は詰まる（JLREQ: 二分アキが1つ残り 1.5em）--')
    for t in ('」「', '。」', '）（', '『「'):
        check(f'{t}', abs(w(t) - 1.5) < 0.01, f'{before(t):.3f} -> {w(t):.3f}em')

    # かなは焼き込みで縮むため、文字列全体の幅ではなく約物自身の advance で判定する
    print('  -- 単独の約物は全角のまま（advance 1000）--')
    cmap, hmtx = font.getBestCmap(), font['hmtx'].metrics
    for ch in '「」（）。、・：':
        adv = hmtx[cmap[ord(ch)]][0]
        check(f'{ch} の advance', adv == 1000, str(adv))
    print('  -- かなに挟まれた約物は詰まらない --')
    for t in ('あ「い', 'あ」い', 'あ。い', 'あ・い'):
        expect = w('あ') + 1.0 + w('い')
        check(f'{t}', abs(w(t) - expect) < 0.01, f'{w(t):.3f} (期待{expect:.3f})em')

    print('  -- 中点がらみ（字面が四分アキ = 合計 1.5em）--')
    for t in ('」・', '・「', '。・'):
        check(f'{t}', abs(w(t) - 1.5) < 0.01, f'{w(t):.3f}em')

    print('  -- かなはプロポーショナル化される --')
    check('あいう が縮む', w('あいう') < before('あいう') - 0.05, f'{before("あいう"):.3f} -> {w("あいう"):.3f}em')
    check('漢字は不変', abs(w('漢字') - before('漢字')) < 0.001, f'{w("漢字"):.3f}em')

    print('  -- halt 系が削除されている --')
    feats = {fr.FeatureTag for tag in ('GPOS', 'GSUB') if tag in font
             for fr in font[tag].table.FeatureList.FeatureRecord}
    for tag in ('halt', 'vhal', 'vpal', 'vkrn'):
        check(f'{tag} が無い', tag not in feats)
    check('kern は残る', 'kern' in feats)
    check('vert は残る（字形切替）', 'vert' in feats)
    check('halt 指定は無効', abs(w('」「', {'halt': True}) - w('」「')) < 0.001,
          f'{w("」「", {"halt": True}):.3f}em')

print(f'\n{sum(res)}/{len(res)} PASS')
raise SystemExit(0 if all(res) else 1)
