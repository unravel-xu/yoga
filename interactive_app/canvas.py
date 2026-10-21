"""Qt painter for face halos, two hand trails, and bounded particle bursts."""
from __future__ import annotations

import math
import random
import time
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget

from interactive_app.engine import PALETTES, HAND_EDGES, Tracking


class InteractionCanvas(QWidget):
    doubleClicked = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 390)
        self.state = Tracking()
        self.image = QImage()
        self.show_camera = True
        self.debug = False
        self.intensity = 1.0
        self.active = False
        self.demo = False
        self.trails = {"Left": deque(maxlen=32), "Right": deque(maxlen=32)}
        self.particles = []
        self.previous_burst = {}
        self.current_color = list(PALETTES["calm"])
        self.last_tick = time.monotonic()

    def clear(self):
        self.state = Tracking()
        self.image = QImage()
        self.particles.clear()
        self.previous_burst.clear()
        for trail in self.trails.values():
            trail.clear()
        self.active = False
        self.update()

    def set_frame(self, image, state):
        self.image = image
        self.state = state
        for hand in state.hands:
            self.trails[hand.label].append((hand.x, hand.y, time.monotonic()))
            if hand.burst > .8 and self.previous_burst.get(hand.label, 0) <= .8:
                self.emit_particles(hand.x, hand.y, 42, .18)
            self.previous_burst[hand.label] = hand.burst

    def emit_particles(self, x, y, count, speed):
        for _ in range(count):
            angle = random.random() * math.tau
            v = speed * random.uniform(.4, 1.2)
            self.particles.append([x, y, math.cos(angle)*v, math.sin(angle)*v, random.uniform(.4, 1.2), 1.2])
        del self.particles[:-500]

    def animate(self):
        now = time.monotonic()
        dt = min(.05, now - self.last_tick)
        self.last_tick = now
        target = PALETTES[self.state.emotion]
        a = 1 - math.exp(-dt / .3)
        self.current_color = [c + a*(t-c) for c, t in zip(self.current_color, target)]
        for particle in self.particles:
            particle[0] += particle[2]*dt
            particle[1] += particle[3]*dt
            particle[2] *= math.exp(-dt*1.4)
            particle[3] *= math.exp(-dt*1.4)
            particle[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for hand in self.state.hands:
            if self.active and random.random() < .2 + hand.speed*.6:
                self.emit_particles(hand.x, hand.y, 1, .05 + hand.speed*.10)
        self.update()

    def viewport(self):
        aspect = self.image.width()/self.image.height() if not self.image.isNull() else 16/9
        width = min(self.width(), self.height()*aspect)
        height = width/aspect
        return QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#070b14"))
        view = self.viewport()
        p.setClipRect(view)
        if self.show_camera and not self.image.isNull():
            p.setOpacity(.52)
            p.drawImage(view, self.image)
            p.setOpacity(1)
        else:
            bg = QLinearGradient(view.topLeft(), view.bottomRight())
            bg.setColorAt(0, QColor("#101b30"))
            bg.setColorAt(1, QColor("#080b15"))
            p.fillRect(view, bg)
            p.setPen(QPen(QColor(139, 180, 218, 12), 1))
            for i in range(1, 16):
                x = view.left() + view.width()*i/16
                p.drawLine(QPointF(x, view.top()), QPointF(x, view.bottom()))
            for i in range(1, 9):
                y = view.top() + view.height()*i/9
                p.drawLine(QPointF(view.left(), y), QPointF(view.right(), y))

        def position(x, y):
            return QPointF(view.left()+x*view.width(), view.top()+y*view.height())
        color = QColor(*[round(c) for c in self.current_color])
        now = time.monotonic()
        if self.active:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            if self.state.face:
                x,y,scale = self.state.face
                center = position(x,y)
                radius = view.width()*max(.075, scale*.66) * (1+self.state.strength*.23)
                pulse = .5+.5*math.sin(now*(2+self.state.strength*2))
                self.glow(p, center, radius*1.7, color, (.10+self.state.strength*.13)*self.intensity)
                p.setBrush(Qt.BrushStyle.NoBrush)
                ring_color = QColor(color)
                ring_color.setAlphaF(min(1, (.18+self.state.strength*.35)*self.intensity))
                p.setPen(QPen(ring_color, 1.4))
                p.drawEllipse(center, radius*(1+pulse*.08), radius*(1+pulse*.08))
                p.drawEllipse(center, radius*1.2, radius*1.2)
            for trail in self.trails.values():
                points = [(x,y,t) for x,y,t in trail if now-t < .85]
                for i in range(1,len(points)):
                    age = max(0, 1-(now-points[i][2])/.85)
                    c = QColor(color)
                    c.setAlphaF(min(1, age*.52*self.intensity))
                    p.setPen(QPen(c, (2+age*4), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.drawLine(position(*points[i-1][:2]), position(*points[i][:2]))
            for hand in self.state.hands:
                center = position(hand.x,hand.y)
                radius = view.height()*(.02 + (1-hand.pinch)*.018 + hand.speed*.025)
                self.glow(p, center, radius*3, color, .72*self.intensity)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(234,249,255,230))
                p.drawEllipse(center, radius*.26, radius*.26)
                p.setBrush(Qt.BrushStyle.NoBrush)
                c = QColor(color)
                c.setAlphaF(min(1, (.25+hand.openness*.5)*self.intensity))
                p.setPen(QPen(c, 1.6))
                ring = radius*(1.8+hand.openness*1.2+hand.burst*3)
                p.drawEllipse(center,ring,ring)
                if self.debug and len(hand.points) >= 21:
                    p.setPen(QPen(QColor(185,239,255,180),1.2))
                    for start,end in HAND_EDGES:
                        p.drawLine(position(*hand.points[start]), position(*hand.points[end]))
            for x,y,vx,vy,life,total in self.particles:
                c = QColor(color)
                c.setAlphaF(min(1, life/total*self.intensity))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawEllipse(position(x,y), 1.2+life*1.8, 1.2+life*1.8)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if not self.active:
            p.setPen(QColor("#c7d4e9"))
            p.setFont(QFont("Helvetica Neue", 27, QFont.Weight.Light))
            p.drawText(view.adjusted(0,-20,0,-20), Qt.AlignmentFlag.AlignCenter, "让表情与手势，成为光")
            p.setPen(QColor("#71859e"))
            p.setFont(QFont("Helvetica Neue", 12))
            p.drawText(view.adjusted(0,62,0,62), Qt.AlignmentFlag.AlignCenter, "选择摄像头并开始互动，或先体验演示")
        elif self.demo:
            p.setPen(QColor("#94a7c3"))
            p.setFont(QFont("Helvetica Neue", 11))
            p.drawText(view.adjusted(24,20,-24,-20), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, "演示模式 · 模拟数据")
        p.end()

    @staticmethod
    def glow(painter, center, radius, color, opacity):
        gradient = QRadialGradient(center, radius)
        bright = QColor(color)
        bright.setAlphaF(min(1, opacity))
        middle = QColor(color)
        middle.setAlphaF(min(1, opacity*.22))
        transparent = QColor(color)
        transparent.setAlpha(0)
        gradient.setColorAt(0,bright)
        gradient.setColorAt(.3,middle)
        gradient.setColorAt(1,transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center,radius,radius)

    def mouseDoubleClickEvent(self,event):
        self.doubleClicked.emit()
