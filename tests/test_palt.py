"""palt 焼き込みの検証: 焼き込み後の既定幅が中間になり、palt 有効時は全開に届くこと。"""
import sys, io
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
import uharfbuzz as hb
sys.path.insert(0, '.')
from notofit.palt import bake

def widths(font):
    buf = io.BytesIO(); font.save(buf)
    hbf = hb.Font(hb.Face(hb.Blob(buf.getvalue())))
    def w(text, feat=None):
        b = hb.Buffer(); b.add_str(text); b.guess_segment_properties()
        hb.shape(hbf, b, feat)
        return sum(p.x_advance for p in b.glyph_positions) / 1000
    return w

SAMPLES = ['」「', '）（', '。」', 'あ、い。う']
ok = lambda c: '\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
results = []

for wght in (400, 700):
    base = instancer.instantiateVariableFont(TTFont('sources/NotoSansJP.ttf'), {'wght': wght})
    w0 = widths(base)
    ref = {t: (w0(t), w0(t, {'palt': True})) for t in SAMPLES}
    print(f'\n=== wght={wght} ===')
    for f in (0.0, 0.34, 1.0):
        font = instancer.instantiateVariableFont(TTFont('sources/NotoSansJP.ttf'), {'wght': wght})
        n = bake(font, f) if f else 0
        w = widths(font)
        print(f'  f={f}  焼込グリフ={n}')
        for t in SAMPLES:
            d_ref, p_ref = ref[t]
            d, p = w(t), w(t, {'palt': True})
            expect = d_ref + f * (p_ref - d_ref)          # 既定は素とpalt全開の f 補間
            c1 = abs(d - expect) < 0.01
            c2 = abs(p - p_ref) < 0.01                    # palt 有効時は常に全開と一致
            results += [c1, c2]
            print(f'    {t:9} 既定={d:.3f}(期待{expect:.3f}) {ok(c1)}  palt={p:.3f}(素{p_ref:.3f}) {ok(c2)}')

print(f'\n{sum(results)}/{len(results)} PASS')
raise SystemExit(0 if all(results) else 1)
