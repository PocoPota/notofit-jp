"""scale / baselineOffset / latinWght が期待どおり欧文にのみ効くか確認する。"""
import sys, shutil
from pathlib import Path
from fontTools.ttLib import TTFont
sys.path.insert(0,'.')
from notofit.build import TuningConfig, WeightConfig, build_weight

TEXT='あAアB亜Cx永E1'
out=Path('build/paramtest'); shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True)
ok=lambda c:'\033[32mPASS\033[0m' if c else '\033[31mFAIL\033[0m'
res=[]

def measure(scale=1.0, baseline=0, lw=400):
    cfg=TuningConfig(weights=[WeightConfig(400,400,lw,scale,baseline)],paltFraction=0.0)
    p=build_weight(cfg,400,out/f's{scale}b{baseline}w{lw}',text=TEXT)
    f=TTFont(p); cm=f.getBestCmap(); glyf=f['glyf']; hm=f['hmtx']
    def g(ch):
        gl=glyf[cm[ord(ch)]]
        return dict(ymin=gl.yMin, ymax=gl.yMax, h=gl.yMax-gl.yMin, adv=hm.metrics[cm[ord(ch)]][0])
    return {'A':g('A'),'x':g('x'),'あ':g('あ'),'亜':g('亜')}

base=measure()
print('基準 (scale=1.0, baseline=0)')
for k,v in base.items(): print(f'  {k}: 高さ={v["h"]} yMax={v["ymax"]} advance={v["adv"]}')

print('\n--- scale=0.9 ---')
s=measure(scale=0.9)
for k in ('A','x'):
    exp=round(base[k]['h']*0.9)
    c=abs(s[k]['h']-exp)<=2; res.append(c)
    print(f'  欧文 {k}: 高さ {base[k]["h"]} -> {s[k]["h"]} (期待{exp}) {ok(c)}')
    c2=abs(s[k]['adv']-round(base[k]['adv']*0.9))<=2; res.append(c2)
    print(f'         advance {base[k]["adv"]} -> {s[k]["adv"]} (期待{round(base[k]["adv"]*0.9)}) {ok(c2)}')
for k in ('あ','亜'):
    c=s[k]['h']==base[k]['h'] and s[k]['adv']==base[k]['adv']; res.append(c)
    print(f'  和文 {k}: 不変 高さ={s[k]["h"]} advance={s[k]["adv"]} {ok(c)}')

print('\n--- baselineOffset=+30 ---')
b=measure(baseline=30)
for k in ('A','x'):
    c=abs((b[k]['ymax']-base[k]['ymax'])-30)<=1; res.append(c)
    print(f'  欧文 {k}: yMax {base[k]["ymax"]} -> {b[k]["ymax"]} (+30期待) {ok(c)}')
for k in ('あ','亜'):
    c=b[k]['ymax']==base[k]['ymax']; res.append(c)
    print(f'  和文 {k}: 不変 yMax={b[k]["ymax"]} {ok(c)}')

print('\n--- latinWght=700 ---')
w=measure(lw=700)
c=w['A']['adv']!=base['A']['adv']; res.append(c)
print(f'  欧文 A: advance {base["A"]["adv"]} -> {w["A"]["adv"]} (変化する) {ok(c)}')
c=w['あ']['adv']==base['あ']['adv']==1000; res.append(c)
print(f'  和文 あ: advance {w["あ"]["adv"]} (1000のまま) {ok(c)}')

print(f'\n{sum(res)}/{len(res)} PASS')
raise SystemExit(0 if all(res) else 1)
