"""本番ビルド（工程⑤⑥）の検証。区切りを3つに絞って通す。"""
import sys, json, re, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from fontTools.ttLib import TTFont
import uharfbuzz as hb
from notofit import release, slices

ok = lambda c: '\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
res = []
def check(label, cond, detail=''):
    res.append(cond); print(f'  {label:44} {detail:26} {ok(cond)}')

allr = slices.load(release.SLICES)
check('区切りを 124 件読み込める', len(allr) == 124, f'{len(allr)}件')

# ラテンと、約物を含む区切り（「」（） は 117、。、・ は 119）で通す。
# release.build は約物を1つのスライスに集約するため、実際の枚数はそれを通した数になる
picked = [allr[-1], allr[-5], allr[-7]]
expected = slices.isolate(picked, release.YAKUMONO)
check('約物の集約で区切りが1つ増える', len(expected) == len(picked) + 1,
      f'{len(picked)} -> {len(expected)}')
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / 'dist'
    m = release.build(out, verbose=False, ranges=picked)

    print('\n=== 出力 ===')
    weights = [w.weight for w in
               release.TuningConfig.load(release.CONFIG).weights]
    check('woff2 の数 = 集約後の区切り × ウェイト',
          len(list(out.rglob('*.woff2'))) == len(expected) * len(weights),
          f'{len(list(out.rglob("*.woff2")))}個')
    for w in weights:
        check(f'{w}.css がある', (out / f'{w}.css').exists())
    check('全ウェイトの CSS がある', (out / 'notofit-jp.css').exists())
    check('OFL.txt が同梱される', (out / 'OFL.txt').exists())
    check('manifest.json がある', (out / 'manifest.json').exists())
    check('中間ファイルが残らない', not (out / '_tmp').exists())

    print('\n=== CSS ===')
    css = (out / f'{weights[0]}.css').read_text()
    blocks = css.count('@font-face')
    check('@font-face の数 = 集約後の区切りの数', blocks == len(expected), f'{blocks}件')
    check('font-family が設定される', 'font-family:"Notofit JP"' in css)
    check('font-display: swap', 'font-display:swap' in css)
    check('src は相対パス', 'src:url("./w/' in css)
    check('unicode-range がある', 'unicode-range:U+' in css)
    check('全ウェイト CSS は合計数',
          (out / 'notofit-jp.css').read_text().count('@font-face')
          == len(expected) * len(weights))
    for url in re.findall(r'url\("\./([^"]+)"\)', (out / 'notofit-jp.css').read_text()):
        if not (out / url).exists():
            check(f'{url} が存在する', False)
            break
    else:
        check('CSS が指すファイルがすべて存在する', True)

    print('\n=== スライスの中身 ===')
    latin = out / f'w/{weights[0]}/000.woff2'      # picked[0] = ラテンのスライス
    font = TTFont(latin)
    n = font['name']
    check('著作権(0) が残る', bool(n.getDebugName(0)), (n.getDebugName(0) or '')[:22])
    check('ライセンスURL(14) が残る', bool(n.getDebugName(14)), n.getDebugName(14) or '')
    check('ライセンス全文(13) は落とす', not n.getDebugName(13))
    feats = {fr.FeatureTag for t in ('GPOS', 'GSUB') if t in font
             for fr in font[t].table.FeatureList.FeatureRecord}
    check('kern が残る', 'kern' in feats)
    check('palt / halt は無い', not ({'palt', 'halt'} & feats))

    print('\n=== 約物のスライス ===')
    # 約物は1つのスライスに集約される。ブラウザはフォントをまたいでカーニングを
    # 適用しないため（→ docs/yakumono.md）
    import io
    yakumono = None
    for path in sorted((out / f'w/{weights[0]}').glob('*.woff2')):
        font = TTFont(path)
        if {0x300C, 0x300D, 0x3002, 0x30FB} <= set(font.getBestCmap()):
            yakumono = font
            break
    check('約物が1つのスライスに揃っている', yakumono is not None)
    if yakumono:
        # uharfbuzz は woff2 を読めないため、素の TTF に戻してからシェイプする
        buf = io.BytesIO(); yakumono.flavor = None; yakumono.save(buf)
        hbf = hb.Font(hb.Face(hb.Blob(buf.getvalue())))
        def w(s):
            b = hb.Buffer(); b.add_str(s); b.guess_segment_properties(); hb.shape(hbf, b)
            return sum(x.x_advance for x in b.glyph_positions) / 1000
        # 選んだ区切りに含まれる約物だけを見る（『』は別の区切りにあるため対象外）
        for pair in ('」「', '。」', '、」', '」・', '）（'):
            check(f'{pair} が詰まる', abs(w(pair) - 1.5) < 0.001, f'{w(pair):.3f}em')
        check('（） は詰めない', abs(w('（）') - 2.0) < 0.001, f'{w("（）"):.3f}em')

print(f'\n{sum(res)}/{len(res)} PASS')
raise SystemExit(0 if all(res) else 1)
