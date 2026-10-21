"""Explicit QA Execute DAT, removed from final scene after capture."""
import json
import time
from pathlib import Path

_start = None
_last = None
_intervals = []
_sop_ms = []
_max_segments = 0


def onFrameStart(frame):
    global _start,_last,_max_segments
    now = time.perf_counter()
    if _start is None:
        _start = _last = now
        return
    if now-_start < 2:
        _last = now
        return
    _intervals.append(now-_last)
    _last = now
    garden = op("/project1/garden")
    sop = garden.op("geo_growth/branches_sop")
    if sop.cookedThisFrame:
        _sop_ms.append(sop.cookTime)
    _max_segments = max(_max_segments,garden.op("garden_runtime").module.world(garden).segment_count)
    if now-_start >= 42:
        times = sorted(_intervals)
        cooks = sorted(_sop_ms)
        result = {"td_build":str(app.build),"render_resolution":[1280,720],
                  "quality":garden.op("garden_controls").par.Quality.eval(),
                  "measured_seconds":sum(times),"frames":len(times),
                  "average_fps":len(times)/sum(times),
                  "p95_frame_ms":times[int(len(times)*.95)]*1000,
                  "max_frame_ms":max(times)*1000,
                  "sop_cook_samples":len(cooks),
                  "mean_sop_cook_ms":sum(cooks)/len(cooks) if cooks else None,
                  "p95_sop_cook_ms":cooks[int(len(cooks)*.95)] if cooks else None,
                  "max_segments_observed":_max_segments,
                  "metrics":garden.fetch("metrics",{}),
                  "scope":"One local demo run. Not a guarantee for other computers or external tracking."}
        destination = Path(me.fetch("report_path"))
        destination.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        me.destroy()
