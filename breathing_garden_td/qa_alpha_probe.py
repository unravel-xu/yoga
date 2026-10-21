"""Development-only numerical Line MAT alpha probe, run explicitly in TD."""
import json
from pathlib import Path


def run(folder):
    g = op('/project1/garden')
    c = g.op('geo_growth/branches_sop_callbacks')
    m = g.op('line_growth')
    original = c.text
    result = {}
    try:
        c.text = '''def onCook(s):
    s.clear()
    s.pointAttribs.create('Cd')
    for y,a in ((.2,1),(-.2,.25)):
        p=s.appendPoly(2,closed=False,addPoints=True)
        for v,x in zip(p,(-.5,.5)):
            v.point.P=(x,y,0)
            v.point.Cd=(.2,.8,.6,a)
'''
        g.op('geo_growth/branches_sop').cook(force=True)
        for premult in ('alreadypremult','premultinshader'):
            for post in (False,True):
                m.par.pointcolorpremult = premult
                m.par.postmultalpha = post
                m.par.srcblend = 'sa'
                g.op('render1').cook(force=True)
                pixels = g.op('render1').numpyArray(delayed=False)
                signal = pixels[:,:,1]-float(pixels[0,0,1])
                top = float(signal[:360,300:980].sum())
                bottom = float(signal[360:,300:980].sum())
                result[premult+str(post)] = dict(ratio=min(top,bottom)/max(top,bottom),
                                               top=top,bottom=bottom)
    finally:
        c.text = original
        m.par.pointcolorpremult='alreadypremult'
        m.par.postmultalpha=False
        g.op('geo_growth/branches_sop').cook(force=True)
    (Path(folder)/'qa'/'alpha-probe.json').write_text(json.dumps(result,indent=2))
