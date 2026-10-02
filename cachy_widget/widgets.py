"""Painted sections of the card: header, hero (today), 48h chart, tomorrow, headlines."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient, QTextLayout,
)
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget

from . import news as newsmod
from . import theme as T
from . import weather as W
from .icons import draw_icon

FAMILIES = ["Inter", "Noto Sans", "Cantarell", "DejaVu Sans", "sans-serif"]


def font(px: float, weight: QFont.Weight = QFont.Weight.Normal, caps: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(round(px))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    if caps:
        f.setCapitalization(QFont.Capitalization.AllUppercase)
    return f


def text(p: QPainter, x: float, y: float, s: str, f: QFont, color, align: str = "left") -> float:
    """Draw `s` with its baseline at y; returns the text width."""
    p.setFont(f)
    p.setPen(QColor(color) if isinstance(color, str) else color)
    w = QFontMetrics(f).horizontalAdvance(s)
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    p.drawText(QPointF(x, y), s)
    return w


def wrap(s: str, f: QFont, width: float, max_lines: int) -> list[str]:
    """Word-wrap into at most `max_lines`, eliding the end of the last line."""
    layout = QTextLayout(s, f)
    layout.beginLayout()
    spans = []
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        spans.append((line.textStart(), line.textLength()))
    layout.endLayout()
    if len(spans) <= max_lines:
        return [s[a:a + n].strip() for a, n in spans]
    out = [s[a:a + n].strip() for a, n in spans[: max_lines - 1]]
    rest = s[spans[max_lines - 1][0]:].strip()
    out.append(QFontMetrics(f).elidedText(rest, Qt.TextElideMode.ElideRight, int(width)))
    return out


class Section(QWidget):
    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)

    def begin(self) -> QPainter:
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        return p


# --------------------------------------------------------------------------- header


class Header(Section):
    refresh_clicked = pyqtSignal()
    place_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(46, parent)
        self.place = ""
        self.status = ""
        self.busy = False
        self._hover = None
        self.setMouseTracking(True)

    def set_state(self, place: str | None = None, status: str | None = None, busy: bool | None = None) -> None:
        if place is not None:
            self.place = place
        if status is not None:
            self.status = status
        if busy is not None:
            self.busy = busy
        self.update()

    def _refresh_rect(self) -> QRectF:
        return QRectF(self.width() - 30, 8, 26, 26)

    def _place_rect(self) -> QRectF:
        w = QFontMetrics(font(16, QFont.Weight.DemiBold)).horizontalAdvance(self.place) + 26
        return QRectF(0, 0, min(w, self.width() - 160), 28)

    def mouseMoveEvent(self, e):
        over = "refresh" if self._refresh_rect().contains(e.position()) else "place" if self._place_rect().contains(e.position()) else None
        if over != self._hover:
            self._hover = over
            self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _):
        self._hover = None
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._refresh_rect().contains(e.position()):
                self.refresh_clicked.emit()
                return
            if self._place_rect().contains(e.position()):
                self.place_clicked.emit()
                return
        e.ignore()

    def mousePressEvent(self, e):
        over = self._refresh_rect().contains(e.position()) or self._place_rect().contains(e.position())
        if not over:
            e.ignore()  # lets the window start a drag

    def paintEvent(self, _):
        p = self.begin()
        # location pin + name
        pin = QPainterPath()
        pin.addEllipse(QPointF(7, 14), 5.5, 5.5)
        hole = QPainterPath()
        hole.addEllipse(QPointF(7, 14), 2, 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.ACCENT))
        p.drawPath(pin.subtracted(hole))
        name_color = T.TEXT if self._hover == "place" else "#dfe5f0"
        text(p, 20, 20, self.place or "Locating…", font(16, QFont.Weight.DemiBold), name_color)
        text(p, 2, 40, self.status, font(11), T.TEXT_FAINT)

        # refresh glyph: arc with arrow head
        r = self._refresh_rect()
        c = r.center()
        col = QColor(T.ACCENT if (self._hover == "refresh" or self.busy) else T.TEXT_MUTED)
        pen = QPen(col, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc = QRectF(c.x() - 6, c.y() - 6, 12, 12)
        p.drawArc(arc, 40 * 16, 280 * 16)
        p.setBrush(col)
        p.drawPolygon(QPointF(c.x() + 6.5, c.y() - 6.5), QPointF(c.x() + 7, c.y() - 0.5), QPointF(c.x() + 1.5, c.y() - 3))


# --------------------------------------------------------------------------- hero (today)


class Hero(Section):
    def __init__(self, parent=None):
        super().__init__(212, parent)
        self.f: W.Forecast | None = None
        self.summary = ""

    def set_forecast(self, f: W.Forecast | None) -> None:
        self.f = f
        self.summary = W.today_summary(f) if f else ""
        self.update()

    def paintEvent(self, _):
        p = self.begin()
        f = self.f
        w = self.width()
        if not f:
            text(p, 2, 70, "No forecast yet", font(26, QFont.Weight.Light), T.TEXT_MUTED)
            text(p, 2, 98, "It will appear as soon as the network is back.", font(13), T.TEXT_FAINT)
            return
        c = f.current
        kind = c.kind
        glow_key = "night" if (not c.is_day and kind in ("clear", "partly")) else kind

        # soft glow behind the icon
        gc = QColor(T.GLOW.get(glow_key, "#8aa4c8"))
        g = QRadialGradient(QPointF(w - 80, 68), 72)
        gc.setAlpha(90)
        g.setColorAt(0, gc)
        gc.setAlpha(0)
        g.setColorAt(1, gc)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(w - 80, 68), 72, 72)

        draw_icon(p, QRectF(w - 150, -6, 144, 144), kind, c.is_day)

        # big temperature + degree sign set smaller for a lighter look
        num = f"{round(c.temp)}"
        big = font(76, QFont.Weight.Light)
        tw = text(p, 0, 80, num, big, T.TEXT)
        text(p, tw + 2, 52, "°", font(46, QFont.Weight.Light), T.ACCENT)

        text(p, 2, 108, c.label, font(18, QFont.Weight.Medium), T.TEXT)
        d = f.today
        sub = f"Feels {W.fmt_temp(c.feels)}   ·   H {W.fmt_temp(d.tmax)}   L {W.fmt_temp(d.tmin)}"
        text(p, 2, 130, sub, font(13), T.TEXT_MUTED)

        # one human sentence
        for i, line in enumerate(wrap(self.summary, font(13, QFont.Weight.Medium), w - 4, 2)):
            text(p, 2, 156 + i * 18, line, font(13, QFont.Weight.Medium), T.ACCENT)

        # stat row
        stats = [
            ("Rain", f"{d.precip}%"),
            ("Wind", f"{round(c.wind)} {f.wind_unit}"),
            ("Humidity", f"{c.humidity}%"),
            ("Sunset" if c.is_day else "Sunrise", W.fmt_clock(d.sunset if c.is_day else f.tomorrow.sunrise)),
        ]
        col_w = w / len(stats)
        y = 196
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(QPointF(0, y - 26), QPointF(w, y - 26))
        for i, (label, value) in enumerate(stats):
            x = i * col_w + 2
            text(p, x, y - 8, label, font(10, QFont.Weight.Medium, caps=True, spacing=0.8), T.TEXT_FAINT)
            text(p, x, y + 8, value, font(13, QFont.Weight.DemiBold), T.TEXT)


# --------------------------------------------------------------------------- 48h chart


class Chart(Section):
    """Temperature curve for today + tomorrow, rain bars, and a 'now' marker."""

    def __init__(self, parent=None):
        super().__init__(122, parent)
        self.f: W.Forecast | None = None

    def set_forecast(self, f: W.Forecast | None) -> None:
        self.f = f
        self.update()

    def paintEvent(self, _):
        f = self.f
        if not f or len(f.hours) < 2:
            return
        p = self.begin()
        w, hs = self.width(), f.hours
        n = len(hs)
        x_of = lambda i: 4 + (w - 8) * i / (n - 1)  # noqa: E731
        lo, hi = min(h.temp for h in hs), max(h.temp for h in hs)
        span = max(hi - lo, 1)
        top, bottom = 26, 74
        y_of = lambda t: bottom - (t - lo) / span * (bottom - top)  # noqa: E731
        pts = [QPointF(x_of(i), y_of(h.temp)) for i, h in enumerate(hs)]

        # smooth path (Catmull-Rom -> cubic Béziers)
        path = QPainterPath(pts[0])
        for i in range(n - 1):
            p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
            path.cubicTo(
                QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6),
                QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6),
                p2,
            )

        # index of "now"
        now = f.current.time
        now_i = max(0, min(n - 1, next((i for i, h in enumerate(hs) if h.time >= now.replace(minute=0, second=0, microsecond=0)), 0)))
        now_x = x_of(now_i)

        # day divider at midnight
        mid_i = next((i for i, h in enumerate(hs) if h.time.date() != hs[0].time.date()), n // 2)
        mid_x = x_of(mid_i)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(mid_x, 8), QPointF(mid_x, 112))
        text(p, 6, 12, "TODAY", font(9, QFont.Weight.DemiBold, spacing=1.0), T.TEXT_FAINT)
        text(p, mid_x + 6, 12, "TOMORROW", font(9, QFont.Weight.DemiBold, spacing=1.0), T.TEXT_FAINT)

        # rain probability bars
        for i, h in enumerate(hs):
            if h.precip >= 10:
                bh = h.precip / 100 * 22
                col = QColor(T.ACCENT_2)
                col.setAlpha(150 if i >= now_i else 70)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(QRectF(x_of(i) - 1.6, 98 - bh, 3.2, bh), 1.2, 1.2)

        # area fill, then curve (dim for the past, bright for the future)
        area = QPainterPath(path)
        area.lineTo(pts[-1].x(), bottom + 6)
        area.lineTo(pts[0].x(), bottom + 6)
        area.closeSubpath()
        fill = QLinearGradient(0, top, 0, bottom + 6)
        a = QColor(T.ACCENT)
        a.setAlpha(60)
        fill.setColorAt(0, a)
        a.setAlpha(0)
        fill.setColorAt(1, a)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.save()
        p.setClipRect(QRectF(now_x, 0, w, 120))
        p.drawPath(area)
        p.restore()

        pen = QPen(QColor(T.ACCENT), 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.setClipRect(QRectF(0, 0, now_x, 120))
        dim = QColor(T.TEXT_MUTED)
        dim.setAlpha(110)
        p.setPen(QPen(dim, 2.0))
        p.drawPath(path)
        p.restore()
        p.save()
        p.setClipRect(QRectF(now_x, 0, w, 120))
        p.setPen(pen)
        p.drawPath(path)
        p.restore()

        # now marker
        p.setPen(Qt.PenStyle.NoPen)
        ring = QColor(T.ACCENT)
        ring.setAlpha(60)
        p.setBrush(ring)
        p.drawEllipse(pts[now_i], 7, 7)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(pts[now_i], 3.6, 3.6)

        # peak labels for each day (max) and the day's low
        for day_slice in (range(0, mid_i), range(mid_i, n)):
            if not len(day_slice):
                continue
            imax = max(day_slice, key=lambda i: hs[i].temp)
            imin = min(day_slice, key=lambda i: hs[i].temp)
            for idx, dy in ((imax, -9), (imin, 16)):
                if idx == now_i and idx == imax:
                    dy = -14
                x = min(max(pts[idx].x(), 14), w - 14)
                text(p, x, pts[idx].y() + dy, W.fmt_temp(hs[idx].temp), font(11, QFont.Weight.DemiBold), T.TEXT, "center")

        # hour ticks
        for i, h in enumerate(hs):
            if h.time.hour in (6, 12, 18):
                label = {6: "6a", 12: "12p", 18: "6p"}[h.time.hour]
                text(p, x_of(i), 116, label, font(10), T.TEXT_FAINT, "center")


# --------------------------------------------------------------------------- tomorrow


class Tomorrow(Section):
    def __init__(self, parent=None):
        super().__init__(88, parent)
        self.f: W.Forecast | None = None

    def set_forecast(self, f: W.Forecast | None) -> None:
        self.f = f
        self.update()

    def paintEvent(self, _):
        f = self.f
        if not f:
            return
        p = self.begin()
        w = self.width()
        d = f.tomorrow
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, self.height() - 1), 18, 18)

        draw_icon(p, QRectF(12, 14, 60, 60), d.kind, True)
        x = 82
        text(p, x, 28, f"Tomorrow · {d.date.strftime('%a')}", font(10, QFont.Weight.DemiBold, caps=True, spacing=0.9), T.ACCENT)
        text(p, x, 50, d.label, font(16, QFont.Weight.DemiBold), T.TEXT)
        text(p, x, 70, W.tomorrow_summary(f), font(12), T.TEXT_MUTED)

        right = w - 18
        wt = text(p, right, 52, W.fmt_temp(d.tmax), font(30, QFont.Weight.Light), T.TEXT, "right")
        text(p, right - wt - 8, 52, W.fmt_temp(d.tmin), font(16), T.TEXT_FAINT, "right")
        text(p, right, 72, f"{d.precip}% rain", font(11), T.ACCENT_2 if d.precip >= 30 else T.TEXT_FAINT, "right")


# --------------------------------------------------------------------------- headlines

ROW_H = 60


class NewsList(Section):
    def __init__(self, parent=None):
        super().__init__(40, parent)
        self.items: list[newsmod.Headline] = []
        self.error = ""
        self._hover = -1
        self._pressed = -1
        self.setMouseTracking(True)

    def set_items(self, items: list[newsmod.Headline], error: str = "") -> None:
        self.items, self.error = items, error
        self.setFixedHeight(34 + max(len(items), 1) * ROW_H)
        self.update()

    def _row_at(self, pos) -> int:
        i = int((pos.y() - 34) // ROW_H)
        return i if pos.y() >= 34 and 0 <= i < len(self.items) else -1

    def mouseMoveEvent(self, e):
        i = self._row_at(e.position())
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.CursorShape.PointingHandCursor if i >= 0 else Qt.CursorShape.ArrowCursor)
            self.setToolTip(self.items[i].title if i >= 0 else "")
            self.update()

    def leaveEvent(self, _):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        self._pressed = self._row_at(e.position()) if e.button() == Qt.MouseButton.LeftButton else -1
        if self._pressed < 0:
            e.ignore()  # empty area: let the window drag

    def mouseReleaseEvent(self, e):
        i = self._row_at(e.position())
        if e.button() == Qt.MouseButton.LeftButton and i >= 0 and i == self._pressed:
            QDesktopServices.openUrl(QUrl(self.items[i].link))
        self._pressed = -1

    def paintEvent(self, _):
        p = self.begin()
        w = self.width()
        text(p, 2, 16, "Headlines", font(11, QFont.Weight.DemiBold, caps=True, spacing=1.2), T.ACCENT)
        text(p, w - 2, 16, datetime.now().strftime("%A, %B %-d"), font(11), T.TEXT_FAINT, "right")
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(QPointF(0, 27), QPointF(w, 27))

        if not self.items:
            msg = self.error or "Loading headlines…"
            text(p, 2, 62, msg[:60], font(13), T.TEXT_MUTED)
            return

        for i, h in enumerate(self.items):
            y = 34 + i * ROW_H
            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 14))
                p.drawRoundedRect(QRectF(-6, y + 1, w + 12, ROW_H - 2), 12, 12)
            meta_x = 2
            sw = text(p, meta_x, y + 17, h.source, font(10, QFont.Weight.DemiBold, caps=True, spacing=0.9), T.ACCENT)
            ago = newsmod.time_ago(h.published)
            if ago:
                text(p, meta_x + sw + 8, y + 17, ago, font(11), T.TEXT_FAINT)
            tf = font(13.5, QFont.Weight.Medium)
            for j, line in enumerate(wrap(h.title, tf, w - 6, 2)):
                text(p, 2, y + 35 + j * 17, line, tf, T.TEXT if i == self._hover else "#d5dbe8")
            if i < len(self.items) - 1:
                p.setPen(QPen(QColor(255, 255, 255, 10), 1))
                p.drawLine(QPointF(0, y + ROW_H), QPointF(w, y + ROW_H))
