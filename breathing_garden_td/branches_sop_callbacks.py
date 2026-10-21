"""Script SOP callbacks. me is the callback DAT INSIDE geo_growth."""
import time


def onSetupParameters(scriptOp):
    return


def onPulse(par):
    return


def onCook(scriptOp):
    started = time.perf_counter()
    garden = scriptOp.parent().parent()
    runtime = garden.op("garden_runtime").module
    world = runtime.world(garden)
    scriptOp.clear()
    scriptOp.pointAttribs.create("Cd")
    for points, rgba in world.paths():
        poly = scriptOp.appendPoly(len(points), closed=False, addPoints=True)
        for vertex, (x,y) in zip(poly,points):
            point = vertex.point
            point.P = (x,y,0)
            point.Cd = rgba
    garden.store("sop_python_ms",(time.perf_counter()-started)*1000)
    garden.store("sop_revision",world.revision)
    return
