"""Optional Script CHOP callbacks: adapt existing Stage 3 landmarks, no models.

The existing helper in this repository has already flipped Y to bottom-up.
Convert it back to top-down at this boundary. Other trackers should bypass this
adapter and supply the documented seven channels directly to Livechop.
"""
import math


def onSetupParameters(scriptOp):
    return


def onPulse(par):
    return


def onCook(scriptOp):
    garden = scriptOp.parent()
    controls = garden.op("garden_controls")
    hands = op(controls.par.Handsource.eval())
    face = op(controls.par.Facesource.eval())
    def value(chop,name,default=0):
        if chop is None:
            return default
        channel = chop[name]
        if channel is None or not chop.numSamples:
            return default
        result = float(channel[0])
        return result if math.isfinite(result) else default
    def point(hand,landmark):
        x = value(hands,"h{}:{}:x".format(hand,landmark),float("nan"))
        y = value(hands,"h{}:{}:y".format(hand,landmark),float("nan"))
        return (x,y) if math.isfinite(x) and math.isfinite(y) and abs(x)+abs(y)>.02 else None
    tip = wrist = thumb = palm = pip = None
    def valid(points):
        tip,wrist,thumb,palm,pip = points
        return (all(p is not None for p in points) and
                math.dist(wrist,palm)>.012 and math.dist(wrist,tip)>.02)
    for hand in (1,2):
        tip = point(hand,"index_finger_tip")
        wrist = point(hand,"wrist")
        thumb = point(hand,"thumb_tip")
        palm = point(hand,"middle_finger_mcp")
        pip = point(hand,"index_finger_pip")
        if valid((tip,wrist,thumb,palm,pip)):
            break
    # Legacy helpers may output collapsed (0,1) landmarks without a hand.
    # Geometric validity rejects that sentinel, including after Y inversion.
    tracked = valid((tip,wrist,thumb,palm,pip))
    result = dict(tip_u=.5,tip_v=.5,tracked=int(tracked),draw=0,pinch=0,
                  mouth=value(face,"jawOpen"),
                  smile=(value(face,"mouthSmileLeft")+value(face,"mouthSmileRight"))*.5)
    if tracked:
        scale = max(.025,math.dist(wrist,palm))
        pinch = math.dist(tip,thumb)/scale < .4
        extended = math.dist(wrist,tip) > math.dist(wrist,pip)*1.12
        result.update(tip_u=tip[0],tip_v=1-tip[1] if bool(controls.par.Adapterflipy) else tip[1],
                      draw=int(extended and not pinch),pinch=int(pinch))
    scriptOp.clear()
    scriptOp.numSamples = 1
    for name in ("tip_u","tip_v","tracked","draw","pinch","mouth","smile"):
        scriptOp.appendChan(name)[0] = result[name]
    return
