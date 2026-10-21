"""The Breathing Garden. Standard-library simulation; no TD/camera imports.

Positions and distances use a world of width 2 and height 1.125. Input v is
top-down. advance() accepts elapsed seconds, not frame numbers. A seeded RNG
and a 30 Hz fixed step keep simulation reproducible at different render rates.
"""
import math
import random
from dataclasses import dataclass, field

CHANNELS = ("tip_u", "tip_v", "tracked", "draw", "pinch", "mouth", "smile")
BACKGROUND = (2/255, 6/255, 11/255)
MINT = (105/255, 205/255, 187/255)
OLD = (23/255, 60/255, 71/255)
WARM = (230/255, 201/255, 153/255)
HIGHLIGHT = (217/255, 1.0, 241/255)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def number(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def ease(t):
    t = clamp(t)
    return t*t*(3-2*t)


@dataclass
class Config:
    GROW_HZ: int = 30
    GROW_STEP: float = .0056
    BRANCH_PROBABILITY: float = .018
    MAX_DEPTH: int = 3
    MAX_PLANTS: int = 9
    MAX_SEGMENTS_PER_PLANT: int = 660
    MAX_TOTAL_SEGMENTS: int = 2300
    STROKE_SEED_SPACING: float = .125
    STROKE_SAMPLE_SPACING: float = .009
    DWELL_SECONDS: float = .72
    DWELL_RADIUS: float = .024
    LIFE_FULL_SECONDS: float = 48
    LIFE_FADE_SECONDS: float = 13
    RETIRE_SECONDS: float = 4.5
    DISSOLVE_SECONDS: float = 3.8
    DUST_COUNT: int = 190
    MAX_PARTICLES: int = 460
    MAX_TIPS_PER_PLANT: int = 32
    MAX_FLOWERS_PER_PLANT: int = 4
    GESTURE_HOLD: float = .065
    SMOOTH_SECONDS: float = .065
    MAX_INPUT_JUMP: float = .26
    BREATH_PERIOD: float = 5.2
    BRIGHTNESS: float = .86
    CURVATURE: float = .019
    AUTO_LOW_FPS: float = 42

    @classmethod
    def for_quality(cls, quality="NORMAL"):
        if quality == "LOW":
            return cls(MAX_TOTAL_SEGMENTS=1400, MAX_SEGMENTS_PER_PLANT=440,
                       DUST_COUNT=150, MAX_PARTICLES=290, MAX_TIPS_PER_PLANT=20,
                       MAX_FLOWERS_PER_PLANT=3)
        return cls()


@dataclass
class GrowthTip:
    x: float
    y: float
    angle: float
    depth: int
    remaining_steps: int
    spawn_time: float
    phase: float = 0.0


@dataclass
class Segment:
    x: float
    y: float
    nx: float
    ny: float
    birth_time: float
    depth: int = 0
    stroke: bool = False


@dataclass
class Flower:
    x: float
    y: float
    birth_time: float
    phase: float
    radius: float = .024


@dataclass
class Plant:
    id: int
    birth_time: float
    last_interaction_time: float
    stroke_points: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    growth_tips: list = field(default_factory=list)
    flowers: list = field(default_factory=list)
    fade_state: str = "alive"
    fade_started: float = 0.0
    fade_duration: float = 13.0
    seed_distance: float = 0.0


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    birth_time: float
    lifetime: float
    phase: float


class Debounce:
    def __init__(self):
        self.value = False
        self.candidate = False
        self.elapsed = 0.0

    def update(self, target, dt, hold):
        target = bool(target)
        if target != self.candidate:
            self.candidate, self.elapsed = target, 0.0
        self.elapsed += dt
        previous = self.value
        if self.elapsed + 1e-9 >= hold:
            self.value = target
        return previous, self.value


class Garden:
    def __init__(self, seed=17, config=None):
        self.config = config or Config()
        self.seed = seed
        self.rng = random.Random(seed)
        self.time = 0.0
        self.accumulator = 0.0
        self.dropped_seconds = 0.0
        self.plants = []
        self.particles = []
        self.dust = [[self.rng.uniform(-1, 1), self.rng.uniform(-.5625, .5625),
                      self.rng.uniform(0, math.tau)] for _ in range(self.config.DUST_COUNT)]
        self.next_id = 1
        self.active_id = None
        self.pending_seed = None
        self.raw_previous = None
        self.position = None
        self.sample_position = None
        self.dwell_anchor = None
        self.dwell_time = 0.0
        self.dwell_fired = False
        self.draw_gate = Debounce()
        self.pinch_gate = Debounce()
        self.tracked = False
        self.mouth = self.smile = 0.0
        self.revision = 0
        self.events = {"flowers": 0, "dissolves": 0, "seeds": 0, "jumps": 0}

    @property
    def segment_count(self):
        return sum(len(p.segments) for p in self.plants)

    def advance(self, elapsed, tracking=None):
        elapsed = max(0.0, number(elapsed))
        # Limit catch-up after stalls; never perform thousands of SOP updates.
        accepted = min(elapsed, .25)
        self.dropped_seconds += elapsed-accepted
        self.accumulator += accepted
        steps = 0
        dt = 1/self.config.GROW_HZ
        while self.accumulator + 1e-10 >= dt:
            self.accumulator = max(0.0, self.accumulator-dt)
            self.time += dt
            self._step(tracking or {}, dt)
            steps += 1
        return steps

    def _disconnect(self):
        self.active_id = None
        self.raw_previous = self.position = self.sample_position = None
        self.dwell_anchor = None
        self.dwell_time = 0.0
        self.dwell_fired = False
        self.draw_gate = Debounce()
        self.pinch_gate = Debounce()

    def _input(self, data, dt):
        cfg = self.config
        # Missing or invalid face values gently return to base breathing.
        face_alpha = 1-math.exp(-dt/1.4)
        self.mouth += (clamp(number(data.get("mouth")))-self.mouth)*face_alpha
        self.smile += (clamp(number(data.get("smile")))-self.smile)*face_alpha
        self.tracked = number(data.get("tracked")) >= .5
        if not self.tracked:
            self._disconnect()  # no grace-period bridges or synthetic releases
            return
        u, v = data.get("tip_u"), data.get("tip_v")
        if u is None or v is None or not all(math.isfinite(number(z, float("nan"))) for z in (u,v)):
            self.tracked = False
            self._disconnect()
            return
        raw = (clamp(number(u))*2-1, (.5-clamp(number(v)))*1.125)
        if self.raw_previous and math.dist(raw, self.raw_previous) > cfg.MAX_INPUT_JUMP:
            self.events["jumps"] += 1
            self._disconnect()
        self.raw_previous = raw
        alpha = 1-math.exp(-dt/cfg.SMOOTH_SECONDS)
        self.position = raw if self.position is None else tuple(a+(b-a)*alpha for a,b in zip(self.position, raw))
        _, draw = self.draw_gate.update(number(data.get("draw")) >= .6, dt, cfg.GESTURE_HOLD)
        old_pinch, pinch = self.pinch_gate.update(number(data.get("pinch")) >= .6, dt, cfg.GESTURE_HOLD)
        if old_pinch and not pinch:
            self.dissolve_near(*self.position)
        if draw and not pinch:
            self._draw(*self.position)
            if self.dwell_anchor is None or math.dist(self.position, self.dwell_anchor) > cfg.DWELL_RADIUS:
                self.dwell_anchor = self.position
                self.dwell_time = 0.0
                self.dwell_fired = False
            self.dwell_time += dt
            if not self.dwell_fired and self.dwell_time + 1e-9 >= cfg.DWELL_SECONDS:
                self._flower_at(*self.position)
                self.dwell_fired = True
        else:
            self.sample_position = None
            self.active_id = None
            self.dwell_anchor = None
            self.dwell_time = 0.0
            self.dwell_fired = False

    def _retire(self, plant, state="retiring", duration=None):
        if plant.fade_state != "alive":
            return
        plant.fade_state = state
        plant.fade_started = self.time
        plant.fade_duration = duration or self.config.RETIRE_SECONDS
        plant.growth_tips.clear()
        if self.active_id == plant.id:
            self.active_id = None
            self.sample_position = None

    def _make_plant(self, x, y, angle):
        if len(self.plants) >= self.config.MAX_PLANTS:
            oldest = next((p for p in self.plants if p.fade_state == "alive"), None)
            if oldest and not any(p.fade_state != "alive" for p in self.plants):
                self._retire(oldest)
            self.pending_seed = (x, y, angle)
            return None
        plant = Plant(self.next_id, self.time, self.time, stroke_points=[(x,y)])
        self.next_id += 1
        self.plants.append(plant)
        self._seed_tip(plant, x, y, angle)
        self.pending_seed = None
        return plant

    def _seed_tip(self, plant, x, y, angle):
        if len(plant.growth_tips) >= self.config.MAX_TIPS_PER_PLANT:
            return
        plant.growth_tips.append(GrowthTip(x, y, angle+self.rng.uniform(-.24,.24), 0,
                                self.rng.randint(35,70), self.time+.45,
                                self.rng.uniform(0, math.tau)))
        self.events["seeds"] += 1

    def _append(self, plant, x, y, nx, ny, depth=0, stroke=False):
        if len(plant.segments) >= self.config.MAX_SEGMENTS_PER_PLANT:
            self._retire(plant)
            return False
        if self.segment_count >= self.config.MAX_TOTAL_SEGMENTS:
            oldest = next((p for p in self.plants if p.fade_state == "alive"),None)
            if oldest and not any(p.fade_state != "alive" for p in self.plants):
                self._retire(oldest)
            return False
        plant.segments.append(Segment(x,y,nx,ny,self.time,depth,stroke))
        return True

    def _draw(self, x, y):
        plant = next((p for p in self.plants if p.id == self.active_id and p.fade_state == "alive"), None)
        if plant is None:
            # Prevent a tiny new stroke every simulation tick when at capacity.
            plant = self._make_plant(x,y,self.rng.uniform(.5,2.6))
            if plant is None:
                return
            self.active_id = plant.id
            self.sample_position = (x,y)
        plant.last_interaction_time = self.time
        if self.sample_position is None:
            self.sample_position = (x,y)
            return
        distance = math.dist(self.sample_position,(x,y))
        spacing = self.config.STROKE_SAMPLE_SPACING
        if distance < spacing:
            return
        # Distance resampling; bounded input jump means at most ~30 samples.
        sx, sy = self.sample_position
        dx, dy = (x-sx)/distance, (y-sy)/distance
        for _ in range(min(32, int(distance/spacing))):
            nx, ny = sx+dx*spacing, sy+dy*spacing
            if not self._append(plant,sx,sy,nx,ny,stroke=True):
                break
            plant.stroke_points.append((nx,ny))
            plant.seed_distance += spacing
            if plant.seed_distance >= self.config.STROKE_SEED_SPACING:
                angle = math.atan2(dy,dx)+self.rng.choice((-1,1))*self.rng.uniform(.65,1.3)
                self._seed_tip(plant,nx,ny,angle)
                plant.seed_distance %= self.config.STROKE_SEED_SPACING
            sx, sy = nx, ny
        # _append may retire the plant; don't restore a stale stroke endpoint.
        if plant.fade_state == "alive":
            self.sample_position = (sx,sy)

    def nearest(self, x, y, radius=.11):
        best = None
        distance = radius
        for plant in self.plants:
            if plant.fade_state != "alive":
                continue
            for px, py in self._anchors(plant):
                d = math.hypot(px-x,py-y)
                if d < distance:
                    distance, best = d, (plant,px,py)
        return best

    @staticmethod
    def _anchors(plant):
        if plant.stroke_points:
            yield plant.stroke_points[0]
        for segment in plant.segments:
            yield segment.nx, segment.ny

    def _flower_at(self, x, y):
        near = self.nearest(x,y,.085)
        if near is None:
            return  # never float an unconnected flower in empty space
        plant, px, py = near
        if len(plant.flowers) >= self.config.MAX_FLOWERS_PER_PLANT:
            return
        if any(math.hypot(f.x-px,f.y-py) < .055 for f in plant.flowers):
            return
        plant.flowers.append(Flower(px,py,self.time,self.rng.uniform(0,math.tau)))
        self.events["flowers"] += 1

    def dissolve_near(self, x, y):
        near = self.nearest(x,y,.13)
        if near is None:
            return False
        plant = near[0]
        self._retire(plant,"dissolving",self.config.DISSOLVE_SECONDS)
        self._release(plant,self.rng.randint(30,70))
        self.events["dissolves"] += 1
        return True

    def _release(self, plant, count):
        # Reservoir-sized random sampling, not a full geometry copy.
        room = self.config.MAX_PARTICLES-len(self.particles)
        for _ in range(min(count,room)):
            if plant.segments:
                s = self.rng.choice(plant.segments)
                f = self.rng.random()
                x,y = s.x+(s.nx-s.x)*f, s.y+(s.ny-s.y)*f
            elif plant.stroke_points:
                x,y = plant.stroke_points[0]
            else:
                continue
            angle = self.rng.uniform(0,math.tau)
            speed = self.rng.uniform(.008,.032)
            self.particles.append(Particle(x,y,math.cos(angle)*speed,math.sin(angle)*speed,
                                  self.time,self.rng.uniform(3.8,6.5),angle))

    def opacity(self, plant, now=None):
        now = self.time if now is None else now
        emergence_time = now if plant.fade_state == "alive" else min(now,plant.fade_started)
        emergence = ease((emergence_time-plant.birth_time)/.9)
        age = max(0,now-plant.birth_time)
        # Subtle continuous ageing, followed by a long smooth natural fade.
        maturity = 1-.16*clamp(age/self.config.LIFE_FULL_SECONDS)
        if plant.fade_state != "alive":
            return emergence*maturity*(1-ease((now-plant.fade_started)/plant.fade_duration))
        return emergence*maturity

    def _step(self, data, dt):
        self._input(data,dt)
        cfg = self.config
        for plant in self.plants:
            if plant.fade_state == "alive" and self.time-plant.birth_time >= cfg.LIFE_FULL_SECONDS:
                self._retire(plant,"natural",cfg.LIFE_FADE_SECONDS)
            if plant.fade_state != "alive":
                continue
            # Build a fresh bounded endpoint list. Each parent is advanced once;
            # newly spawned children are first updated on the next tick.
            next_tips = []
            child_slots = max(0,cfg.MAX_TIPS_PER_PLANT-len(plant.growth_tips))
            for tip_index, tip in enumerate(plant.growth_tips):
                if self.time < tip.spawn_time:
                    next_tips.append(tip)
                    continue
                if tip.remaining_steps <= 0:
                    if self.rng.random() < .12:
                        self._flower_at(tip.x,tip.y)
                    continue
                angle = tip.angle + cfg.CURVATURE*math.sin(self.time*1.1+tip.phase)+self.rng.uniform(-.045,.045)
                length = cfg.GROW_STEP*(.63**(tip.depth*.38))
                nx, ny = tip.x+math.cos(angle)*length, tip.y+math.sin(angle)*length
                if abs(nx) > .985 or abs(ny) > .548:
                    continue
                if not self._append(plant,tip.x,tip.y,nx,ny,tip.depth):
                    if plant.fade_state == "alive":
                        # Preserve ALL unprocessed tips while waiting for budget.
                        next_tips.extend(plant.growth_tips[tip_index:])
                    break
                tip.x,tip.y,tip.angle = nx,ny,angle
                tip.remaining_steps -= 1
                next_tips.append(tip)
                if tip.depth < cfg.MAX_DEPTH and child_slots > 0 and self.rng.random() < cfg.BRANCH_PROBABILITY:
                    next_tips.append(GrowthTip(nx,ny,angle+self.rng.choice((-1,1))*self.rng.uniform(.4,.9),
                                     tip.depth+1,self.rng.randint(18,44),self.time+.15,tip.phase+1.3))
                    child_slots -= 1
            plant.growth_tips = next_tips[:cfg.MAX_TIPS_PER_PLANT] if plant.fade_state == "alive" else []
        survivors = []
        for plant in self.plants:
            if plant.fade_state != "alive" and self.time >= plant.fade_started+plant.fade_duration:
                if plant.fade_state != "dissolving":
                    self._release(plant,7)
            else:
                survivors.append(plant)
        self.plants = survivors
        if self.pending_seed and len(self.plants) < cfg.MAX_PLANTS:
            self._make_plant(*self.pending_seed)
        self._particles(dt)
        self.revision += 1

    def _particles(self, dt):
        for point in self.dust:
            x,y,phase = point
            vx, vy = .003*math.sin(self.time*.19+phase), .002*math.cos(self.time*.16+phase)
            if self.tracked and self.position:
                dx,dy = self.position[0]-x,self.position[1]-y
                d = math.hypot(dx,dy)
                if .012 < d < .26:
                    force = .018*(1-d/.26)
                    vx += dx/d*force
                    vy += dy/d*force
            point[0] = (x+vx*dt+1)%2-1
            point[1] = (y+vy*dt+.5625)%1.125-.5625
        alive = []
        for p in self.particles:
            if self.time-p.birth_time >= p.lifetime:
                continue
            drag = math.exp(-dt*.65)
            p.vx = p.vx*drag + math.sin(self.time*1.3+p.phase)*.0015*dt
            p.vy = p.vy*drag + math.cos(self.time*1.1+p.phase)*.0015*dt
            p.x += p.vx*dt
            p.y += p.vy*dt
            alive.append(p)
        self.particles = alive

    def breath(self):
        return 1+(.035+.08*self.mouth)*math.sin(math.tau*self.time/self.config.BREATH_PERIOD)

    def paths(self):
        """Yield (points, RGBA). Render-only, bounded, no simulation mutations.

        Each two-point primitive is genuine persistent plant geometry, not a
        feedback trail. Flower outlines are attached to a plant anchor.
        """
        breath = self.breath()*self.config.BRIGHTNESS
        warm = self.smile*.34
        color = tuple(a+(b-a)*warm for a,b in zip(MINT,WARM))
        for plant in self.plants:
            alpha = self.opacity(plant)
            if alpha < .001:
                continue
            for s in plant.segments:
                age = self.time-s.birth_time
                old = .42*clamp(age/48)
                rgb = tuple((c+(o-c)*old)*breath for c,o in zip(color,OLD))
                a = alpha*(.72 if s.stroke else .62/(1+s.depth*.12))
                # Ease in the most recent growth increments (30 Hz geometry).
                a *= ease(age/.16)
                yield ((s.x,s.y),(s.nx,s.ny)), (*rgb,a)
            for flower in plant.flowers:
                unfold = ease((self.time-flower.birth_time)/1.7)
                r = flower.radius*unfold*(1+.018*math.sin(self.time+flower.phase))
                rotation = flower.phase+.045*math.sin(self.time*.35)
                for petal in range(6):
                    a = rotation+petal*math.tau/6
                    points = []
                    for j in range(13):
                        t = j*math.tau/12
                        along = r*(.46-.46*math.cos(t))
                        across = r*.20*math.sin(t)
                        points.append((flower.x+math.cos(a)*along-math.sin(a)*across,
                                       flower.y+math.sin(a)*along+math.cos(a)*across))
                    yield points, (*color,alpha*.34*unfold)
                core = .0025*unfold*(1+.12*math.sin(self.time*1.2+flower.phase))
                yield self._circle(flower.x,flower.y,core,9), (*HIGHLIGHT,alpha*.76*unfold)
        for x,y,phase in self.dust:
            a = .11+.055*math.sin(self.time*.6+phase)
            yield ((x-.0007,y),(x+.0007,y)), (.32,.60,.59,a)
        for p in self.particles:
            age = self.time-p.birth_time
            a = .45*ease(age/.45)*(1-ease(age/p.lifetime))
            yield ((p.x-.001,p.y),(p.x+.001,p.y)), (*MINT,a)

    @staticmethod
    def _circle(x,y,r,count):
        return [(x+math.cos(i*math.tau/count)*r,y+math.sin(i*math.tau/count)*r) for i in range(count+1)]

    def diagnostics(self):
        return {"seconds":round(self.time,3),"plants":len(self.plants),
                "segments":self.segment_count,"particles":len(self.dust)+len(self.particles),
                "growth_tips":sum(len(p.growth_tips) for p in self.plants),
                "flowers":sum(len(p.flowers) for p in self.plants),
                "events":dict(self.events),"dropped_seconds":self.dropped_seconds}


def test_tracking(t):
    """24 s choreography: draw, dwell, pinch/release, draw, tracking loss."""
    phase = t%24
    cycle = int(t//24)
    offset = .10*math.sin(cycle*2.1)
    if phase < 8:
        u = .23+.045*phase
        v = .53+.10*math.sin(phase*.7+cycle)
    elif phase < 11:
        u, v = .59, .53+.10*math.sin(8*.7+cycle)
    elif phase < 13:
        u, v = .59, .53+.10*math.sin(8*.7+cycle)
    else:
        u, v = .59-.032*(phase-13), .52+.11*math.sin((phase-13)*.5+cycle)
    return {"tip_u":u,"tip_v":v+offset,"tracked":int(phase < 21.5),
            "draw":int(phase < 10 or 13.3 < phase < 21),
            "pinch":int(11 < phase < 12.3),
            "mouth":.25+.18*math.sin(t*.3), "smile":.4+.35*math.sin(t*.11)}
