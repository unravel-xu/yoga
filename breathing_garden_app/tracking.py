"""Convert existing MediaPipe Tracking results to the seven garden channels."""
import math


class TrackingBridge:
    def __init__(self):
        self.selected = None
        self.pinching = False

    def reset(self):
        self.selected = None
        self.pinching = False

    def convert(self, state, aspect=16/9):
        values = dict(tip_u=.5,tip_v=.5,tracked=0,draw=0,pinch=0,mouth=0,smile=0)
        if state.face is not None:
            values.update(mouth=state.mouth,smile=state.smile)
        hands = {hand.label:hand for hand in state.hands if len(hand.points)>=21}
        if self.selected and self.selected not in hands:
            # One explicit lost frame prevents drawing across hand identities.
            self.reset()
            return values
        if not hands:
            self.reset()
            return values
        if self.selected is None:
            self.selected = "Right" if "Right" in hands else sorted(hands)[0]
        hand = hands[self.selected]
        points = hand.points
        if not all(math.isfinite(c) for i in (0,4,6,8,9) for c in points[i]):
            self.reset()
            return values
        def distance(i,j):
            return math.hypot((points[i][0]-points[j][0])*aspect,points[i][1]-points[j][1])
        if distance(0,9)<.012 or distance(0,8)<.02:
            self.reset()
            return values
        # Hysteresis plus the engine's temporal debounce rejects pinch chatter.
        if hand.pinch >= .78:
            self.pinching = True
        elif hand.pinch <= .55:
            self.pinching = False
        extended = distance(0,8)>distance(0,6)*1.10
        # Inference already runs on the optionally mirrored RGB image. Both
        # coordinates remain normalized, with top-down Y (no extra flip here).
        values.update(tip_u=points[8][0],tip_v=points[8][1],tracked=1,
                      draw=int(extended and not self.pinching),pinch=int(self.pinching))
        return values
