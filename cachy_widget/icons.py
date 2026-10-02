"""Vector weather icons painted with QPainter: crisp at any size, no asset files."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient


_BLOBS = [(0.32, 0.58, 0.17), (0.52, 0.46, 0.22), (0.72, 0.58, 0.16)]


def _cloud(p: QPainter, dark: bool = False, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> None:
    """Three circles on a rounded base, all filled with one shared gradient so they read as one shape."""
    p.save()
    p.translate(dx, dy)
    p.translate(0.5, 0.5)
    p.scale(scale, scale)
    p.translate(-0.5, -0.5)
    g = QLinearGradient(0, 0.25, 0, 0.78)
    if dark:
        g.setColorAt(0, QColor("#aab4c8"))
        g.setColorAt(1, QColor("#6f7a92"))
    else:
        g.setColorAt(0, QColor("#ffffff"))
        g.setColorAt(1, QColor("#c9d6ea"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    for cx, cy, r in _BLOBS:
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.drawRoundedRect(QRectF(0.15, 0.58, 0.73, 0.17), 0.085, 0.085)
    p.restore()


def _sun(p: QPainter, cx: float, cy: float, r: float, rays: bool = True) -> None:
    if rays:
        pen = QPen(QColor("#ffc857"), r * 0.28)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(
                QPointF(cx + math.cos(a) * r * 1.42, cy + math.sin(a) * r * 1.42),
                QPointF(cx + math.cos(a) * r * 1.82, cy + math.sin(a) * r * 1.82),
            )
    g = QRadialGradient(QPointF(cx - r * 0.3, cy - r * 0.3), r * 1.5)
    g.setColorAt(0, QColor("#fff1b8"))
    g.setColorAt(0.55, QColor("#ffc857"))
    g.setColorAt(1, QColor("#ff9f43"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r, r)


def _moon(p: QPainter, cx: float, cy: float, r: float) -> None:
    crescent = QPainterPath()
    crescent.addEllipse(QPointF(cx, cy), r, r)
    bite = QPainterPath()
    bite.addEllipse(QPointF(cx + r * 0.55, cy - r * 0.35), r * 0.85, r * 0.85)
    shape = crescent.subtracted(bite)
    g = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
    g.setColorAt(0, QColor("#fffbe8"))
    g.setColorAt(1, QColor("#c9cff5"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(shape)


def _drops(p: QPainter, xs: list[float], y0: float, length: float, width: float, color: str, slant: float = 0.05) -> None:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for i, x in enumerate(xs):
        off = (i % 2) * 0.05
        p.drawLine(QPointF(x + slant, y0 + off), QPointF(x - slant, y0 + off + length))


def _bolt(p: QPainter) -> None:
    pts = QPolygonF(
        [QPointF(0.54, 0.62), QPointF(0.42, 0.84), QPointF(0.50, 0.84), QPointF(0.44, 1.0),
         QPointF(0.62, 0.77), QPointF(0.53, 0.77), QPointF(0.60, 0.62)]
    )
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffd23f"))
    p.drawPolygon(pts)


def draw_icon(p: QPainter, rect: QRectF, kind: str, is_day: bool = True) -> None:
    """Draw weather `kind` ('clear', 'partly', 'cloudy', 'fog', 'drizzle', 'rain', 'snow', 'storm') in `rect`."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    side = min(rect.width(), rect.height())
    p.translate(rect.center().x() - side / 2, rect.center().y() - side / 2)
    p.scale(side, side)

    if kind == "clear":
        if is_day:
            _sun(p, 0.5, 0.5, 0.22)
        else:
            _moon(p, 0.5, 0.5, 0.3)
    elif kind == "partly":
        if is_day:
            _sun(p, 0.34, 0.36, 0.15)
        else:
            _moon(p, 0.36, 0.36, 0.2)
        _cloud(p, dx=0.07, dy=0.1, scale=0.9)
    elif kind == "cloudy":
        _cloud(p, dark=True, dx=-0.08, dy=-0.05, scale=0.75)
        _cloud(p, dx=0.04, dy=0.08, scale=0.95)
    elif kind == "fog":
        _cloud(p, scale=0.9, dy=-0.1)
        pen = QPen(QColor(255, 255, 255, 190), 0.045)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for i, (x0, x1) in enumerate([(0.2, 0.78), (0.28, 0.86), (0.2, 0.7)]):
            y = 0.72 + i * 0.1
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
    elif kind == "drizzle":
        _cloud(p, dark=True, dy=-0.12)
        _drops(p, [0.34, 0.5, 0.66], 0.68, 0.1, 0.035, "#8fc7ff", 0.02)
    elif kind == "rain":
        _cloud(p, dark=True, dy=-0.12)
        _drops(p, [0.32, 0.5, 0.68], 0.66, 0.2, 0.05, "#4da3ff")
    elif kind == "snow":
        _cloud(p, dy=-0.12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff"))
        for i, (x, y) in enumerate([(0.32, 0.72), (0.5, 0.8), (0.68, 0.72), (0.41, 0.9), (0.6, 0.92)]):
            p.drawEllipse(QPointF(x, y), 0.032, 0.032)
    elif kind == "storm":
        _cloud(p, dark=True, dy=-0.14)
        _bolt(p)
    else:
        _cloud(p)
    p.restore()
