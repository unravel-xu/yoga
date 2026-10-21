"""QPainter frontend using exactly the TD prototype's pure Python Garden."""
import time

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from breathing_garden_td.garden_engine import Garden, Config, test_tracking
from breathing_garden_app.tracking import TrackingBridge
from interactive_app.engine import Tracking, HAND_EDGES


def visible_color(rgba):
    """Display mapping only; zero alpha always stays exactly transparent."""
    rgb = [1-(1-max(0,min(1,c)))**1.55 for c in rgba[:3]]
    return QColor.fromRgbF(*rgb,min(.96,max(0,rgba[3])*1.45))


class GardenCanvas(QWidget):
    doubleClicked = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(580,360)
        self.quality = "NORMAL"
        self.world = Garden()
        self.bridge = TrackingBridge()
        self.state = Tracking()
        self.image = QImage()
        self.input = {}
        self.paths = []
        self.show_camera = False
        self.debug = False
        self.intensity = 1.0
        self.active = False
        self.demo = False
        self.frame_time = 0.0
        self.last_tick = time.monotonic()
        self.render_fps = 60.0
        self.paint_ms = 0.0
        self.path_ms = 0.0
        self.slow_seconds = 0.0
        self.degraded = False
        self.last_debug_refresh = 0.0

    def reset_world(self, quality=None):
        if quality:
            self.quality = quality
        self.world = Garden(config=Config.for_quality(self.quality))
        self.bridge.reset()
        self.input = {}
        self.state = Tracking()
        self.frame_time = 0
        self.paths = []
        self.degraded = False
        self.slow_seconds = 0
        self.last_tick = time.monotonic()

    def clear(self):
        """Stop input, NOT the world. Existing lives must continue to grow."""
        self.bridge.reset()
        self.world._disconnect()
        self.input = {}
        self.state = Tracking()
        self.image = QImage()
        self.frame_time = 0
        self.active = False
        self.update()

    def set_frame(self,image,state):
        self.state = state
        self.image = image
        self.frame_time = time.monotonic()
        self.input = self.bridge.convert(state,image.width()/image.height() if image.height() else 16/9)

    def animate(self):
        now = time.monotonic()
        elapsed = max(0,now-self.last_tick)
        self.last_tick = now
        if elapsed > .001:
            self.render_fps += (min(240,1/elapsed)-self.render_fps)*.035
        fresh = self.tracking_fresh(now)
        if self.demo:
            data = test_tracking(self.world.time+self.world.accumulator)
        elif self.active and fresh:
            data = self.input
        else:
            data = {}
        self.world.config.BRIGHTNESS = .86*self.intensity
        steps = self.world.advance(elapsed,data)
        if self.quality == "NORMAL" and not self.degraded:
            self.slow_seconds = self.slow_seconds+min(elapsed,.25) if self.render_fps<40 else max(0,self.slow_seconds-elapsed)
            if self.slow_seconds>8:
                self.degraded = True
                cfg = self.world.config
                cfg.MAX_TOTAL_SEGMENTS = 1400
                cfg.MAX_SEGMENTS_PER_PLANT = 440
                cfg.MAX_TIPS_PER_PLANT = 20
                cfg.MAX_PARTICLES = 290
                for plant in self.world.plants:
                    if len(plant.segments)>cfg.MAX_SEGMENTS_PER_PLANT:
                        self.world._retire(plant)
        if steps or not self.paths:
            started = time.perf_counter()
            self.paths = []
            for points,rgba in self.world.paths():
                path = QPainterPath(QPointF(*points[0]))
                for point in points[1:]:
                    path.lineTo(QPointF(*point))
                color = visible_color(rgba)
                self.paths.append((path,color))
            self.path_ms = (time.perf_counter()-started)*1000
        self.update()

    def tracking_fresh(self,now=None):
        now = time.monotonic() if now is None else now
        captured = self.state.captured_at or self.frame_time
        return now-self.frame_time<.30 and now-captured<.35

    def viewport(self):
        width = min(self.width(),self.height()*16/9)
        height = width*9/16
        return QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)

    def paintEvent(self,event):
        started = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor("#02060B"))
        view = self.viewport()
        painter.setClipRect(view)
        if self.show_camera and not self.image.isNull() and time.monotonic()-self.frame_time<.30:
            painter.setOpacity(.28)
            painter.drawImage(view,self.image)
            painter.setOpacity(1)
        painter.save()
        painter.translate(view.center())
        scale = view.width()/2
        painter.scale(scale,-scale)
        # Cosmetic widths are device pixels: include Retina scaling so the
        # core stays readable on Mac displays. No full-frame blur/readback.
        pixel_ratio = self.devicePixelRatioF()
        for glow in (True,False):
            if glow and (self.quality=="LOW" or self.degraded):
                continue
            for path,color in self.paths:
                c = QColor(color)
                if glow:
                    c.setAlphaF(c.alphaF()*.16)
                pen = QPen(c,(6.8 if glow else 1.35)*pixel_ratio,Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
        painter.restore()
        if self.debug and not self.demo and time.monotonic()-self.frame_time<.3:
            def position(point):
                return QPointF(view.left()+point[0]*view.width(),view.top()+point[1]*view.height())
            painter.setPen(QPen(QColor(160,230,215,135),1))
            for hand in self.state.hands:
                if len(hand.points)<21:
                    continue
                for a,b in HAND_EDGES:
                    painter.drawLine(position(hand.points[a]),position(hand.points[b]))
                painter.setBrush(QColor("#D9FFF1"))
                painter.drawEllipse(position(hand.points[8]),3,3)
        painter.end()
        self.paint_ms = (time.perf_counter()-started)*1000

    def mouseDoubleClickEvent(self,event):
        self.doubleClicked.emit()
