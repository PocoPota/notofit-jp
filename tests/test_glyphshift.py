"""グリフ単位の垂直調整（工程④）の検証。対象だけが動き、字送りは変わらないこと。"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '.')
from fontTools.ttLib import TTFont
from notofit.build import TuningConfig, build_weight
from notofit import glyphshift

ok = lambda c: '\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
res = []
def check(label, cond, detail=''):
    res.append(cond); print(f'  {label:38} {detail:26} {ok(cond)}')

cfg = TuningConfig.load('config/tuning.json')
TEXT = ':;：；xHAB0あ'
SHIFTS = {':': 40, ';': -25}

for weight in (400, 700):
    print(f'\n=== wght={weight} ===')
    with tempfile.TemporaryDirectory() as tmp:
        before = TTFont(build_weight(cfg, weight, Path(tmp) / 'a', text=TEXT))
        after = TTFont(build_weight(cfg, weight, Path(tmp) / 'b', text=TEXT, shifts=SHIFTS))
        mb = glyphshift.measure(before, TEXT)
        ma = glyphshift.measure(after, TEXT)

        for ch, dy in SHIFTS.items():
            moved = ma[ch]['center'] - mb[ch]['center']
            check(f'{ch} が {dy:+d} 動く', abs(moved - dy) < 1,
                  f'{mb[ch]["center"]:.0f} -> {ma[ch]["center"]:.0f}')
            check(f'{ch} の advance は不変', ma[ch]['advance'] == mb[ch]['advance'],
                  str(ma[ch]['advance']))
            check(f'{ch} の字面の高さは不変',
                  abs((ma[ch]['yMax'] - ma[ch]['yMin']) - (mb[ch]['yMax'] - mb[ch]['yMin'])) < 1)

        for ch in '：；xHAB0あ':
            if ch in mb:
                check(f'{ch} は動かない', abs(ma[ch]['center'] - mb[ch]['center']) < 0.01)

print('\n=== 設定の読み書き ===')
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'shifts.json'
    c = glyphshift.ShiftConfig()
    c.set_for_weight(400, {':': 26, ';': 0})     # 0 は保存しない
    c.save(path)
    r = glyphshift.ShiftConfig.load(path)
    check('保存と読み込みで一致', r.for_weight(400) == {':': 26}, str(r.for_weight(400)))
    check('未設定のウェイトは空', r.for_weight(700) == {})
    check('存在しないファイルは空', glyphshift.ShiftConfig.load(Path(tmp) / 'x.json').weights == {})

print(f'\n{sum(res)}/{len(res)} PASS')
raise SystemExit(0 if all(res) else 1)
