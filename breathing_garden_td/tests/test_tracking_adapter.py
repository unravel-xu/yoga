from types import SimpleNamespace
import unittest
from unittest.mock import patch

from breathing_garden_td import stage3_tracking_adapter as adapter


class FakeChop(dict):
    numSamples = 1

    def __getitem__(self,key):
        return self.get(key)

    def parent(self):
        controls = SimpleNamespace(par=SimpleNamespace(
            Handsource=SimpleNamespace(eval=lambda:"hands"),
            Facesource=SimpleNamespace(eval=lambda:"face"),Adapterflipy=True))
        return SimpleNamespace(op=lambda name:controls)

    def clear(self):
        super().clear()

    def appendChan(self,name):
        self[name] = [0]
        return self[name]


def hand_data(hand,points):
    names = ("index_finger_tip","wrist","thumb_tip","middle_finger_mcp","index_finger_pip")
    return {"h{}:{}:{}".format(hand,name,axis):[point[i]]
            for name,point in zip(names,points) for i,axis in enumerate(("x","y"))}


class TrackingAdapterTests(unittest.TestCase):
    def call(self,hands=None,face=None):
        output = FakeChop()
        with patch.object(adapter,"op",side_effect=lambda path:{"hands":hands,"face":face}.get(path),create=True):
            adapter.onCook(output)
        return {k:v[0] for k,v in output.items()}

    def test_no_tracking_sources_safe(self):
        result = self.call()
        self.assertEqual(len(result),7)
        self.assertEqual(result["tracked"],0)
        self.assertEqual(result["mouth"],0)

    def test_existing_landmarks_and_blendshapes(self):
        hands = FakeChop(hand_data(1,[(.5,.75),(.5,.35),(.35,.5),(.5,.55),(.5,.60)]))
        face = FakeChop(jawOpen=[.3],mouthSmileLeft=[.4],mouthSmileRight=[.6])
        result = self.call(hands,face)
        self.assertEqual(result["tracked"],1)
        self.assertEqual(result["draw"],1)
        self.assertAlmostEqual(result["tip_v"],.25)
        self.assertAlmostEqual(result["smile"],.5)

    def test_collapsed_hand_rejected_and_second_hand_selected(self):
        data = hand_data(1,[(0,1)]*5)
        self.assertEqual(self.call(FakeChop(data))["tracked"],0)
        data.update(hand_data(2,[(.6,.75),(.6,.35),(.45,.5),(.6,.55),(.6,.60)]))
        result = self.call(FakeChop(data))
        self.assertEqual(result["tracked"],1)
        self.assertAlmostEqual(result["tip_u"],.6)


if __name__ == "__main__":
    unittest.main()
