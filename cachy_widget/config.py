"""Config + cache locations (XDG) and a tiny JSON-backed settings store."""

from __future__ import annotations

import copy
import json
import locale
import os
from pathlib import Path

from . import APP_ID


def _xdg(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / fallback) / APP_ID


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache")
CONFIG_FILE = CONFIG_DIR / "config.json"
WEATHER_CACHE = CACHE_DIR / "weather.json"
LOCATION_CACHE = CACHE_DIR / "location.json"
NEWS_CACHE = CACHE_DIR / "news.json"


def default_units() -> str:
    """Imperial for en_US, metric everywhere else."""
    lang = locale.getlocale()[0] or os.environ.get("LANG", "")
    return "imperial" if lang.startswith("en_US") else "metric"


DEFAULTS: dict = {
    # {"name": "Austin, Texas", "lat": 30.27, "lon": -97.74}; null = detect from IP
    "location": None,
    "units": None,  # "imperial" | "metric" | null (auto from locale)
    "news_count": 5,
    "weather_refresh_minutes": 20,
    "news_refresh_minutes": 30,
    "always_on_bottom": True,
    "opacity": 0.94,
    "feeds": [
        {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml"},
        {"name": "Guardian", "url": "https://www.theguardian.com/world/rss"},
    ],
}


def load() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        print(f"[cachy-widget] ignoring bad config {CONFIG_FILE}: {exc}")
    if cfg["units"] not in ("imperial", "metric"):
        cfg["units"] = default_units()
    return cfg


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    tmp.replace(CONFIG_FILE)


def read_cache(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_cache(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        pass
