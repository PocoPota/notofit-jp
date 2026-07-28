"""本番パイプラインで palt が削除され、CSS で指定しても効かないことの確認。"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from fontTools.ttLib import TTFont
import uharfbuzz as hb
from notofit.build import TuningConfig, build_weight, DROP_FEATURES

ok = lambda c: '\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
res = []
def check(label, cond, detail=''):
    res.append(cond); print(f'  {label:44} {detail:22} {ok(cond)}')

cfg = TuningConfig.load('config/tuning.json')
for weight in (400, 700):
    print(f'\n=== wght={weight} ===')
    with tempfile.TemporaryDirectory() as tmp:
        path = build_weight(cfg, weight, Path(tmp), text='」「。」（）あいうえおアイウＡ１x')
        font = TTFont(path)
        feats = {fr.FeatureTag for t in ('GPOS', 'GSUB') if t in font
                 for fr in font[t].table.FeatureList.FeatureRecord}
        for tag in DROP_FEATURES:
            check(f'{tag} が削除されている', tag not in feats)
        check('kern は残る', 'kern' in feats)

        hbf = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        def w(s, feat=None):
            b = hb.Buffer(); b.add_str(s); b.guess_segment_properties(); hb.shape(hbf, b, feat)
            return sum(x.x_advance for x in b.glyph_positions) / 1000
        for s in ('」「', '。」', '（）', 'あいうえお', 'アイウ'):
            for tag in ('palt', 'halt'):
                check(f'{s} は {tag} 指定で変わらない', abs(w(s) - w(s, {tag: True})) < 0.001,
                      f'{w(s):.3f}em')
        check('」「 は隣接処理が効いている', abs(w('」「') - 1.5) < 0.001, f'{w("」「"):.3f}em')

print(f'\n{sum(res)}/{len(res)} PASS')
raise SystemExit(0 if all(res) else 1)
