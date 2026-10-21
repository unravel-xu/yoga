"""TD bridge. Sole input boundary is the seven-channel null_tracking CHOP."""
import time

_state = None


def world(garden):
    global _state
    if _state is None:
        reset(garden)
    return _state["world"]


def reset(garden):
    global _state
    engine = garden.op("garden_engine").module
    controls = garden.op("garden_controls")
    cfg = engine.Config.for_quality(controls.par.Quality.eval())
    cfg.GROW_STEP = float(controls.par.Growstep)
    cfg.BRANCH_PROBABILITY = float(controls.par.Branchprob)
    cfg.LIFE_FULL_SECONDS = float(controls.par.Lifefull)
    cfg.LIFE_FADE_SECONDS = float(controls.par.Lifefade)
    cfg.BRIGHTNESS = float(controls.par.Brightness)
    _state = {"world":engine.Garden(seed=int(controls.par.Seed),config=cfg),
              "clock":time.perf_counter(),"report_at":0,"fps":60.0,
              "slow_seconds":0.0,"mode":controls.par.Mode.eval(),
              "quality":controls.par.Quality.eval(),"reset":int(controls.par.Resetserial),
              "degraded":False}
    garden.store("last_runtime_error","")
    # reset() may be reached from inside the SOP's first cook on TOE reload.
    # Never recursively cook that SOP here; mark geometry dirty for tick().
    garden.store("sop_revision",-1)


def tick(garden):
    global _state
    controls = garden.op("garden_controls")
    if _state is None:
        reset(garden)
    if _state["reset"] != int(controls.par.Resetserial) or _state["quality"] != controls.par.Quality.eval():
        reset(garden)
    state = _state
    now = time.perf_counter()
    elapsed = max(0,now-state["clock"])
    state["clock"] = now
    if elapsed > .0001:
        state["fps"] += (min(240,1/elapsed)-state["fps"])*.035
    engine = garden.op("garden_engine").module
    w = state["world"]
    cfg = w.config
    cfg.GROW_STEP = float(controls.par.Growstep)
    cfg.BRANCH_PROBABILITY = float(controls.par.Branchprob)
    cfg.LIFE_FULL_SECONDS = float(controls.par.Lifefull)
    cfg.LIFE_FADE_SECONDS = float(controls.par.Lifefade)
    cfg.BRIGHTNESS = float(controls.par.Brightness)
    if state["mode"] != controls.par.Mode.eval():
        w._disconnect()  # never bridge two different input coordinate streams
        state["mode"] = controls.par.Mode.eval()
    if state["mode"] == "TEST_MODE":
        values = engine.test_tracking(w.time+w.accumulator)
        test = garden.op("input_test")
        for i,name in enumerate(engine.CHANNELS):
            getattr(test.par,"const{}value".format(i)).val = values[name]
    tracking = garden.op("null_tracking")
    tracking.cook(force=True)
    values = {}
    for name in engine.CHANNELS:
        channel = tracking[name]
        if channel is not None:
            values[name] = float(channel[0])
    # No tip coordinates => engine safely treats the hand as lost.
    steps = w.advance(elapsed,values)
    if steps or garden.fetch("sop_revision",-1) != w.revision:
        garden.op("geo_growth/branches_sop").cook(force=True)
    # Keep the real-time output alive even when its network viewer is hidden.
    # SOP is rebuilt only at 30 Hz; the inexpensive GPU chain runs at render FPS.
    garden.op("render1").cook(force=True)
    garden.op("bloom1").cook(force=True)
    garden.op("out1").cook(force=True)
    if bool(controls.par.Autolow) and state["quality"] == "NORMAL" and not state["degraded"]:
        state["slow_seconds"] = state["slow_seconds"]+min(elapsed,.25) if state["fps"] < cfg.AUTO_LOW_FPS else max(0,state["slow_seconds"]-elapsed)
        if state["slow_seconds"] > 8:
            # Soft degrade: no abrupt garden reset or geometry deletion.
            state["degraded"] = True
            cfg.MAX_TOTAL_SEGMENTS = 1400
            cfg.MAX_SEGMENTS_PER_PLANT = 440
            cfg.MAX_TIPS_PER_PLANT = 20
            cfg.MAX_PARTICLES = 290
            # Ambient particles fade via their existing dimness; reduce only
            # as plants retire, not by deleting visible branches here.
            for plant in w.plants:
                if len(plant.segments) > cfg.MAX_SEGMENTS_PER_PLANT:
                    w._retire(plant)
            garden.op("render1").par.antialias = "aa2"
    if w.time-state["report_at"] >= 1:
        state["report_at"] = w.time
        report = w.diagnostics()
        report.update(fps=round(state["fps"],1),
                      sop_python_ms=round(garden.fetch("sop_python_ms",0),3),
                      sop_cook_ms=round(garden.op("geo_growth/branches_sop").cookTime,3),
                      mode=state["mode"],quality=state["quality"],auto_low=state["degraded"])
        garden.store("metrics",report)
        if bool(controls.par.Debug):
            import json
            garden.op("diagnostics").text = json.dumps(report,ensure_ascii=False,indent=2)
