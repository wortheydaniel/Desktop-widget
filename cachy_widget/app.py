"""Main window: frameless translucent card, background refresh jobs, context menu."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, QRectF, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu, QVBoxLayout, QWidget

from . import APP_ID, config, demo
from . import news as newsmod
from . import theme as T
from . import weather as W
from .widgets import Chart, Header, Hero, NewsList, Tomorrow

CARD_WIDTH = 408
RADIUS = 28


class _Signals(QObject):
    ok = pyqtSignal(object)
    err = pyqtSignal(str)


class Job(QRunnable):
    """Run `fn` on the thread pool; deliver the result (or error text) back on the GUI thread."""

    def __init__(self, fn, on_ok, on_err):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.signals.ok.connect(on_ok)
        self.signals.err.connect(on_err)

    def run(self):
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[cachy-widget] background job failed: {exc}", file=sys.stderr)
            self.signals.err.emit(str(exc) or exc.__class__.__name__)
        else:
            self.signals.ok.emit(result)


class WidgetWindow(QWidget):
    def __init__(self, cfg: dict, demo_mode: bool = False):
        super().__init__()
        self.cfg = cfg
        self.demo_mode = demo_mode
        self.forecast: W.Forecast | None = None
        self.pool = QThreadPool.globalInstance()
        self._jobs: set[Job] = set()
        self._drag_ok = True

        self.setWindowTitle("CachyOS Weather")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.apply_window_flags()
        self.setWindowOpacity(float(cfg.get("opacity", 0.94)))

        self.header = Header()
        self.hero = Hero()
        self.chart = Chart()
        self.tomorrow = Tomorrow()
        self.news = NewsList()
        self.header.refresh_clicked.connect(self.refresh_all)
        self.header.place_clicked.connect(self.choose_location)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 22)
        lay.setSpacing(0)
        for w, gap in ((self.header, 4), (self.hero, 2), (self.chart, 12), (self.tomorrow, 18), (self.news, 0)):
            lay.addWidget(w)
            lay.addSpacing(gap)
        lay.addStretch(1)
        self.setFixedWidth(CARD_WIDTH)
        self.news.set_items([])

        self._load_cached()

        self.weather_timer = QTimer(self, interval=int(cfg["weather_refresh_minutes"]) * 60_000, timeout=self.refresh_weather)
        self.news_timer = QTimer(self, interval=int(cfg["news_refresh_minutes"]) * 60_000, timeout=self.refresh_news)
        self.tick = QTimer(self, interval=30_000, timeout=self._update_status)
        for t in (self.weather_timer, self.news_timer, self.tick):
            t.start()
        QTimer.singleShot(0, self.refresh_all)

    # ------------------------------------------------------------------ window behaviour

    def apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("always_on_bottom", True):
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(T.BG_TOP))
        g.setColorAt(1, QColor(T.BG_BOTTOM))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, RADIUS, RADIUS)
        # faint accent wash in the top-left, like the CachyOS wallpapers' green glow
        wash = QLinearGradient(0, 0, self.width(), 220)
        c = QColor(T.ACCENT)
        c.setAlpha(26)
        wash.setColorAt(0, c)
        c.setAlpha(0)
        wash.setColorAt(0.7, c)
        p.setBrush(wash)
        p.drawRoundedRect(r, RADIUS, RADIUS)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawRoundedRect(r, RADIUS, RADIUS)

    def mousePressEvent(self, e):
        # Children ignore presses that aren't on a control, so those bubble up here: drag the card.
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.addAction("Refresh now", self.refresh_all)
        menu.addAction("Change location…", self.choose_location)
        menu.addSeparator()
        units = QAction("Use °C / km/h" if self.cfg["units"] == "imperial" else "Use °F / mph", self)
        units.triggered.connect(self.toggle_units)
        menu.addAction(units)
        bottom = QAction("Stay on desktop (below windows)", self, checkable=True)
        bottom.setChecked(bool(self.cfg.get("always_on_bottom", True)))
        bottom.toggled.connect(self.set_always_on_bottom)
        menu.addAction(bottom)
        menu.addAction("Edit settings & news feeds…", self.open_config)
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        menu.exec(e.globalPos())

    # ------------------------------------------------------------------ actions

    def toggle_units(self) -> None:
        self.cfg["units"] = "metric" if self.cfg["units"] == "imperial" else "imperial"
        config.save(self.cfg)
        self.refresh_weather()

    def set_always_on_bottom(self, on: bool) -> None:
        self.cfg["always_on_bottom"] = on
        config.save(self.cfg)
        self.apply_window_flags()

    def open_config(self) -> None:
        if not config.CONFIG_FILE.exists():
            config.save(self.cfg)
        subprocess.Popen(["xdg-open", str(config.CONFIG_FILE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def choose_location(self) -> None:
        if self.demo_mode:
            return
        query, ok = QInputDialog.getText(self, "Change location", "City (e.g. Berlin, or Portland Oregon):")
        if not ok or not query.strip():
            return
        self.header.set_state(status="Searching…")
        self._run(lambda: W.geocode(query.strip()), self._pick_place, self._weather_failed)

    def _pick_place(self, results: list[dict]) -> None:
        self._update_status()
        if not results:
            self.header.set_state(status="No matching place found")
            return
        choice = results[0]
        if len(results) > 1:
            names = [r["name"] for r in results]
            name, ok = QInputDialog.getItem(self, "Pick a place", "Which one?", names, 0, False)
            if not ok:
                return
            choice = results[names.index(name)]
        self.cfg["location"] = {"name": choice["name"], "short": choice["short"], "lat": choice["lat"], "lon": choice["lon"]}
        config.save(self.cfg)
        self.refresh_weather()

    # ------------------------------------------------------------------ data

    def _run(self, fn, ok, err) -> None:
        job = Job(fn, ok, err)

        def done(*_):
            self._jobs.discard(job)

        job.signals.ok.connect(done)
        job.signals.err.connect(done)
        self._jobs.add(job)
        self.pool.start(job)

    def refresh_all(self) -> None:
        self.refresh_weather()
        self.refresh_news()

    def _load_cached(self) -> None:
        if self.demo_mode:
            return
        cached = config.read_cache(config.WEATHER_CACHE)
        if cached:
            try:
                self._show_forecast(W.parse(cached["raw"], cached["place"], cached["units"]), stale_at=cached["fetched"])
            except (KeyError, ValueError, TypeError):
                pass
        items = config.read_cache(config.NEWS_CACHE)
        if items:
            try:
                self.news.set_items([
                    newsmod.Headline(i["source"], i["title"], i["link"],
                                     datetime.fromisoformat(i["published"]) if i["published"] else None)
                    for i in items
                ])
            except (KeyError, ValueError, TypeError):
                pass

    def refresh_weather(self) -> None:
        self.header.set_state(busy=True)
        units = self.cfg["units"]

        def work():
            if self.demo_mode:
                return {"place": "Demo City", "units": units, "raw": demo.raw_forecast(units)}
            loc = self.cfg.get("location") or config.read_cache(config.LOCATION_CACHE)
            if not loc:
                loc = W.locate_by_ip()
                config.write_cache(config.LOCATION_CACHE, loc)
            raw = W.fetch_raw(loc["lat"], loc["lon"], units)
            return {"place": loc.get("short") or loc["name"], "units": units, "raw": raw,
                    "fetched": datetime.now(timezone.utc).isoformat()}

        self._run(work, self._weather_ok, self._weather_failed)

    def _weather_ok(self, res: dict) -> None:
        forecast = W.parse(res["raw"], res["place"], res["units"])
        if not self.demo_mode:
            config.write_cache(config.WEATHER_CACHE, res)
        self._show_forecast(forecast, stale_at=None)

    def _weather_failed(self, msg: str) -> None:
        print(f"[cachy-widget] weather: {msg}", file=sys.stderr)
        shown = "Offline · showing last forecast" if self.forecast else "Can't reach the weather service · retrying"
        self.header.set_state(status=shown, busy=False)
        QTimer.singleShot(90_000, self.refresh_weather)  # retry soon; the regular timer is 20 min

    def _show_forecast(self, f: W.Forecast, stale_at: str | None) -> None:
        self.forecast = f
        self.updated_at = datetime.fromisoformat(stale_at) if stale_at else datetime.now(timezone.utc)
        self.hero.set_forecast(f)
        self.chart.set_forecast(f)
        self.tomorrow.set_forecast(f)
        self.header.set_state(place=f.place, busy=False)
        self._update_status(stale=bool(stale_at))

    def _update_status(self, stale: bool = False) -> None:
        if not isinstance(stale, bool):  # called from the QTimer
            stale = False
        if self.forecast is None:
            return
        local = self.updated_at.astimezone()
        label = "Cached" if stale else "Updated"
        self.header.set_state(status=f"{datetime.now().strftime('%A, %B %-d')}  ·  {label} {local.strftime('%-I:%M %p')}")

    def refresh_news(self) -> None:
        count = int(self.cfg["news_count"])

        def work():
            if self.demo_mode:
                return demo.headlines()[:count], []
            return newsmod.gather(self.cfg["feeds"], count)

        self._run(work, self._news_ok, self._news_failed)

    def _news_ok(self, res) -> None:
        items, errors = res
        if errors:
            print("[cachy-widget] feed errors:", *errors, sep="\n  ")
        self.news.set_items(items)
        if not self.demo_mode:
            config.write_cache(config.NEWS_CACHE, [
                {"source": h.source, "title": h.title, "link": h.link,
                 "published": h.published.isoformat() if h.published else None} for h in items
            ])

    def _news_failed(self, msg: str) -> None:
        if not self.news.items:  # keep cached headlines on screen if we have them
            self.news.set_items([], error="Headlines unavailable · retrying")
        QTimer.singleShot(90_000, self.refresh_news)


def run(argv: list[str], demo_mode: bool = False, screenshot: str | None = None) -> int:
    app = QApplication(argv[:1])
    app.setApplicationName(APP_ID)
    app.setDesktopFileName(APP_ID)  # Wayland app_id -> lets KWin/Hyprland rules match the widget
    app.setQuitOnLastWindowClosed(True)
    cfg = config.load()
    win = WidgetWindow(cfg, demo_mode=demo_mode)
    win.show()

    if screenshot:
        def shot():
            # Composite over a wallpaper-ish backdrop so the translucent card previews realistically.
            from PyQt6.QtGui import QImage, QRadialGradient
            pad = 40
            img = QImage(win.width() + 2 * pad, win.height() + 2 * pad, QImage.Format.Format_ARGB32)
            p = QPainter(img)
            bg = QRadialGradient(img.width() * 0.2, img.height() * 0.1, img.height())
            bg.setColorAt(0, QColor("#0b4f4a"))
            bg.setColorAt(1, QColor("#050a14"))
            p.fillRect(img.rect(), bg)
            p.drawPixmap(pad, pad, win.grab())
            p.end()
            img.save(screenshot)
            app.quit()

        QTimer.singleShot(1200, shot)
    return app.exec()
