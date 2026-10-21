"""Actual TD integration tests. Optional, explicit developer execution only.

run(folder) rebuilds the owned garden and resets its scene; never run during
a performance. The final TOE does NOT contain this development harness.
"""
import json
from pathlib import Path


def run(folder):
    root = Path(folder)
    garden = op("/project1/garden")
    results = []
    def check(name,condition,detail=""):
        results.append({"check":name,"ok":bool(condition),"detail":str(detail)})
    external_before = [(n.path,n.id) for n in op("/project1").children if n != garden]
    marker = garden.create(textDAT,"_qa_user_marker")
    marker.text = "preserve user content"
    runner = garden.create(textDAT,"_qa_paste_builder")
    runner.text = (root/"build_garden_td.py").read_text()
    first_engine = garden.op("garden_engine").id
    runner.run()  # exercises the exact Text DAT > Run Script path requested
    check("paste-and-run executes",garden.op("garden_engine").id != first_engine)
    first = sorted(n.name for n in garden.children)
    runner.run()
    second = sorted(n.name for n in garden.children)
    check("idempotent names",first==second,second)
    check("user node preserved",garden.op("_qa_user_marker").text=="preserve user content")
    external_after = [(n.path,n.id) for n in op("/project1").children if n != garden]
    check("outside garden untouched",external_before==external_after)
    runner.destroy()
    marker.destroy()
    controls = garden.op("garden_controls")
    fake = garden.create(constantCHOP,"_qa_live")
    engine = garden.op("garden_engine").module
    fake.par.const.sequence.numBlocks = 7
    values = dict(tip_u=.27,tip_v=.22,tracked=1,draw=1,pinch=0,mouth=.3,smile=.6)
    for i,name in enumerate(engine.CHANNELS):
        getattr(fake.par,"const{}name".format(i)).val = name
        getattr(fake.par,"const{}value".format(i)).val = values[name]
    controls.par.Livechop = fake.path
    controls.par.Mode = "LIVE_MODE"
    garden.op("null_tracking").cook(force=True)
    actual = {name:float(garden.op("null_tracking")[name][0]) for name in engine.CHANNELS}
    check("LIVE seven-channel routing",all(abs(values[k]-actual[k])<1e-5 for k in values),actual)
    runtime = garden.op("garden_runtime").module
    runtime.reset(garden)
    for _ in range(30):
        runtime._state["clock"] -= 1/30
        runtime.tick(garden)
    world = runtime.world(garden)
    check("LIVE seeds plants",len(world.plants)>0)
    check("Y normalized and flipped",world.position and abs(world.position[1]-.315)<.001)
    check("face values flow",world.mouth>0 and world.smile>0)
    controls.par.Livechop = ""
    controls.par.Mode = "TEST_MODE"
    fake.destroy()
    controls.par.Quality = "LOW"
    runtime.tick(garden)
    check("LOW quality",len(runtime.world(garden).dust)==150 and runtime.world(garden).config.MAX_TOTAL_SEGMENTS==1400)
    controls.par.Quality = "NORMAL"
    runtime.tick(garden)
    previous_world = runtime.world(garden)
    runtime._state["slow_seconds"] = 9
    runtime._state["fps"] = 20
    runtime._state["clock"] -= 1/30
    runtime.tick(garden)
    check("auto LOW preserves world",runtime._state["degraded"] and runtime.world(garden) is previous_world)
    garden.op("render1").par.antialias = "aa4"
    # The optional legacy adapter must safely output no hand without a tracker.
    adapter = garden.op("stage3_adapter")
    adapter.cook(force=True)
    check("optional Stage3 adapter no-model fallback",adapter.numChans==7 and float(adapter["tracked"][0])==0)
    check("adapter errors",not adapter.errors(),adapter.errors())
    runtime.reset(garden)
    # Exercise the entire demo deterministically inside TD (not a recorded clip).
    world = runtime.world(garden)
    for i in range(30*24):
        world.advance(1/30,engine.test_tracking(i/30))
    check("TD demo dwell flower",world.events["flowers"]>0,world.events)
    check("TD demo pinch release",world.events["dissolves"]>0,world.events)
    garden.op("geo_growth/branches_sop").cook(force=True)
    for name in ("render1","bloom1","out1"):
        garden.op(name).cook(force=True)
    # GPU readback is only in this explicit QA, NEVER in the realtime engine.
    pixels = garden.op("render1").numpyArray(delayed=False)
    if pixels is not None:
        red,green = pixels[:,:,0],pixels[:,:,1]
        check("GPU Cd color is not white",int(((green-red)>.025).sum())>30)
    else:
        check("GPU readback",False,"numpyArray returned None")
    # Two equal lines at alpha 1 and .25 must have a .25 luminance ratio,
    # rather than .0625 (accidental double premultiplication) or 1 (ignored Cd).
    callback = garden.op("geo_growth/branches_sop_callbacks")
    original = callback.text
    try:
        callback.text = '''def onCook(s):
    s.clear()
    s.pointAttribs.create('Cd')
    for y,a in ((.2,1),(-.2,.25),(0,0)):
        p=s.appendPoly(2,closed=False,addPoints=True)
        for v,x in zip(p,(-.5,.5)):
            v.point.P=(x,y,0)
            v.point.Cd=(.2,.8,.6,a)
'''
        garden.op("geo_growth/branches_sop").cook(force=True)
        garden.op("render1").cook(force=True)
        pixels = garden.op("render1").numpyArray(delayed=False)
        # numpyArray row orientation can differ; inspect both horizontal halves.
        signal = pixels[:,:,1]-float(pixels[0,0,1])
        top = float(signal[:360,300:980].sum())
        bottom = float(signal[360:,300:980].sum())
        ratio = min(top,bottom)/max(top,bottom)
        check("GPU alpha linearity",.18<ratio<.32,ratio)
        check("GPU alpha zero invisible",abs(float(signal[350:370,300:980].sum()))<.001)
    finally:
        callback.text = original
        garden.op("geo_growth/branches_sop").cook(force=True)
    report = garden.op("validate_garden").module.validate(emit=False)
    check("network validation",report["ok"],report)
    result = {"ok":all(item["ok"] for item in results),"checks":results,"build":str(app.build)}
    runtime.reset(garden)
    # Parameter Execute DAT dispatches pulses at the end of a TD frame. Test
    # the real event after three frames, not by invoking its callback directly.
    run_script = '''import json
from pathlib import Path
g=op('/project1/garden')
c=g.op('garden_controls')
r=g.op('garden_runtime').module
result=json.loads(args[2])
result['checks'].append({'check':'Reset pulse callback (3 frames)',
    'ok':int(c.par.Resetserial)==args[1]+1 and r.world(g).seed==31,
    'detail':{'serial':int(c.par.Resetserial),'seed':r.world(g).seed}})
result['ok']=all(item['ok'] for item in result['checks'])
(Path(args[0])/'qa'/'td-integration-tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
c.par.Seed=17
r.reset(g)
'''
    # Call td.run rather than this function's own name.
    import td
    # A freshly created Parameter Execute DAT begins observing on the next
    # frame. Wait for registration before pulsing, then wait for dispatch.
    arm_script = '''import td
g=op('/project1/garden')
c=g.op('garden_controls')
serial=int(c.par.Resetserial)
c.par.Seed=31
c.par.Reset.pulse()
td.run(args[2],args[0],serial,args[1],delayFrames=3)
'''
    td.run(arm_script,str(root),json.dumps(result),run_script,delayFrames=3)
    return result
