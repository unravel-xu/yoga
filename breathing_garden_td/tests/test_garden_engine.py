import math
import tracemalloc
import unittest
from dataclasses import replace

from breathing_garden_td.garden_engine import Garden, Config, GrowthTip, test_tracking


def input_at(u=.4, v=.5, **kwargs):
    return dict(tip_u=u,tip_v=v,tracked=1,draw=1,pinch=0,**kwargs)


def run(garden, seconds, data=None, fps=60):
    for i in range(round(seconds*fps)):
        garden.advance(1/fps,data(i/fps) if callable(data) else data)


class GardenTests(unittest.TestCase):
    def test_empty_input(self):
        g = Garden()
        run(g,10)
        self.assertEqual(len(g.plants),0)
        self.assertEqual(len(g.dust),190)

    def test_motion_draws_and_stops_then_keeps_growing(self):
        g = Garden()
        run(g,2,lambda t:input_at(.3+t*.12,.5))
        self.assertGreater(sum(len(p.stroke_points) for p in g.plants),10)
        n = g.segment_count
        run(g,1,{"tracked":0})
        self.assertGreater(g.segment_count,n)

    def test_dwell_once_and_attached(self):
        g = Garden()
        run(g,.7,input_at())
        self.assertEqual(g.events["flowers"],0)
        run(g,.2,input_at())
        self.assertEqual(g.events["flowers"],1)
        run(g,1,input_at())
        self.assertEqual(g.events["flowers"],1)
        p = g.plants[0]
        f = p.flowers[0]
        self.assertIn((f.x,f.y),list(g._anchors(p)))
        self.assertEqual(len(list(g.paths()))-g.segment_count-len(g.dust),7)

    def test_pinch_release_dissolves_not_disappears(self):
        g = Garden()
        run(g,.5,input_at())
        hold = input_at()
        hold.update(draw=0,pinch=1)
        run(g,.2,hold)
        self.assertEqual(g.events["dissolves"],0)
        hold["pinch"] = 0
        run(g,.15,hold)
        self.assertEqual(g.events["dissolves"],1)
        self.assertTrue(30 <= len(g.particles) <= 70)
        self.assertEqual(g.plants[0].fade_state,"dissolving")
        self.assertGreater(g.opacity(g.plants[0]),0)
        run(g,7,{})
        self.assertFalse(g.plants)
        self.assertFalse(g.particles)

    def test_tracking_loss_and_jump_never_bridge(self):
        g = Garden()
        run(g,.5,input_at(.15))
        run(g,.1,{"tracked":0})
        run(g,.5,input_at(.85))
        run(g,.2,input_at(.2))
        strokes = [s for p in g.plants for s in p.segments if s.stroke]
        self.assertTrue(all(math.hypot(s.nx-s.x,s.ny-s.y) <= .009001 for s in strokes))
        self.assertGreaterEqual(g.events["jumps"],1)
        self.assertGreaterEqual(len(g.plants),3)

    def test_loss_does_not_release_pinch(self):
        g = Garden()
        run(g,.4,input_at())
        hold = input_at()
        hold.update(pinch=1,draw=0)
        run(g,.2,hold)
        run(g,.2,{"tracked":0})
        run(g,.2,input_at())
        self.assertEqual(g.events["dissolves"],0)

    def test_bounded_and_young_lives_get_budget(self):
        cfg = replace(Config(),MAX_PLANTS=3,MAX_TOTAL_SEGMENTS=100,
                      MAX_SEGMENTS_PER_PLANT=80,RETIRE_SECONDS=.4)
        g = Garden(config=cfg)
        maximum = 0
        for i in range(60*80):
            g.advance(1/60,test_tracking(i/60))
            maximum = max(maximum,g.segment_count)
            self.assertLessEqual(len(g.plants),3)
            self.assertLessEqual(g.segment_count,100)
            self.assertLessEqual(len(g.particles),cfg.MAX_PARTICLES)
            self.assertTrue(all(len(p.segments)<=80 and len(p.growth_tips)<=cfg.MAX_TIPS_PER_PLANT for p in g.plants))
        self.assertGreater(maximum,50)
        self.assertGreater(g.next_id,8)

    def test_lifecycle_cleans_everything(self):
        g = Garden(config=replace(Config(),LIFE_FULL_SECONDS=2,LIFE_FADE_SECONDS=1))
        run(g,.4,input_at())
        run(g,11,{})
        self.assertFalse(g.plants)
        self.assertFalse(g.particles)

    def test_invalid_and_missing_face_input(self):
        g = Garden()
        for u,v in [(-2,3),(float("nan"),1),(float("inf"),.3),(None,.3),("x",.1)]:
            run(g,.2,input_at(u,v,mouth=float("nan"),smile=None))
        run(g,2,input_at())
        self.assertTrue(math.isfinite(g.breath()))
        self.assertAlmostEqual(g.mouth,0)
        self.assertTrue(all(-1<=s.nx<=1 and -.5625<=s.ny<=.5625 for p in g.plants for s in p.segments))

    def test_y_flip_and_debounce(self):
        g = Garden()
        run(g,.5,input_at(.5,.1))
        self.assertGreater(g.position[1],0)
        self.assertAlmostEqual(g.position[1],.45)
        g2 = Garden()
        for i in range(60):
            data = input_at()
            data["draw"] = i%2
            g2.advance(1/30,data)
        self.assertFalse(g2.plants)

    def test_fixed_step_reproducible_across_fps(self):
        states = []
        for fps in (30,60,120):
            g = Garden(seed=41)
            run(g,1,input_at(),fps)
            run(g,4,{},fps)
            states.append([(s.nx,s.ny) for p in g.plants for s in p.segments])
        self.assertEqual(states[0],states[1])
        self.assertEqual(states[1],states[2])

    def test_long_simulation_memory_is_bounded(self):
        g = Garden()
        tracemalloc.start()
        run(g,100,lambda t:test_tracking(t))
        first = tracemalloc.get_traced_memory()[0]
        run(g,260,lambda t:test_tracking(t+100))
        current,peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(current-first,2_500_000)
        self.assertLess(peak,8_000_000)
        self.assertLessEqual(g.segment_count,2300)
        self.assertLessEqual(len(g.plants),9)

    def test_render_is_read_only_and_finite(self):
        g = Garden()
        run(g,8,test_tracking)
        before = g.diagnostics()
        for points,color in g.paths():
            self.assertTrue(all(math.isfinite(v) for p in points for v in p))
            self.assertTrue(all(math.isfinite(c) for c in color))
        self.assertEqual(before,g.diagnostics())

    def test_stall_is_bounded(self):
        g = Garden()
        self.assertLessEqual(g.advance(600,{}),8)
        self.assertGreater(g.dropped_seconds,599)

    def test_branch_cap_does_not_drop_existing_tips(self):
        g = Garden(config=replace(Config(),MAX_TIPS_PER_PLANT=2,BRANCH_PROBABILITY=1))
        plant = g._make_plant(0,0,0)
        plant.growth_tips = [GrowthTip(0,0,0,0,40,0),GrowthTip(0,0,math.pi,0,40,0)]
        g.advance(1/30,{})
        self.assertEqual(len(plant.growth_tips),2)
        self.assertTrue(all(t.remaining_steps==39 for t in plant.growth_tips))

    def test_particle_speed_and_fade(self):
        g = Garden()
        run(g,.4,input_at())
        self.assertTrue(g.dissolve_near(*g.position))
        p = g.particles[0]
        speed = math.hypot(p.vx,p.vy)
        alpha = g.opacity(g.plants[0])
        run(g,1,{})
        self.assertLess(math.hypot(p.vx,p.vy),speed)
        self.assertLess(g.opacity(g.plants[0]),alpha)


if __name__ == "__main__":
    unittest.main()
