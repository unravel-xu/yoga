"""Execute DAT: no module state is serialized into the TOE."""
import traceback


def onStart():
    return


def onCreate():
    return


def onFrameStart(frame):
    garden = me.parent()
    try:
        garden.op("garden_runtime").module.tick(garden)
    except Exception:
        message = traceback.format_exc()
        if garden.fetch("last_runtime_error", "") != message:
            print("[Breathing Garden] " + message)
        garden.store("last_runtime_error",message)
        garden.op("diagnostics").text = message
    return
