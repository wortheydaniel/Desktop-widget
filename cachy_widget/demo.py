"""Offline sample data (``--demo``): same shape as the real API/feeds, so the full parse path is exercised."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from . import news


def raw_forecast(units: str = "imperial", now: datetime | None = None) -> dict:
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    day0 = now.replace(hour=0, minute=0)
    imperial = units == "imperial"
    conv = (lambda c: c * 9 / 5 + 32) if imperial else (lambda c: c)
    times, temps, precip, codes = [], [], [], []
    for i in range(48):
        t = day0 + timedelta(hours=i)
        base = 17 + 7 * math.sin((t.hour - 9) / 24 * 2 * math.pi) - (3 if i >= 24 else 0)
        wet = 15 <= i <= 19 or 38 <= i <= 41
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        temps.append(round(conv(base), 1))
        precip.append(70 if wet else 5 if i % 5 else 15)
        codes.append(61 if wet else 2)
    d = lambda i, s: (day0 + timedelta(days=i, hours=s)).strftime("%Y-%m-%dT%H:%M")  # noqa: E731
    return {
        "current": {
            "time": now.strftime("%Y-%m-%dT%H:%M"),
            "temperature_2m": round(conv(21.4), 1),
            "apparent_temperature": round(conv(20.1), 1),
            "relative_humidity_2m": 54,
            "weather_code": 2,
            "is_day": 1 if 6 <= now.hour < 19 else 0,
            "wind_speed_10m": 9.0 if imperial else 14.0,
        },
        "hourly": {"time": times, "temperature_2m": temps, "precipitation_probability": precip, "weather_code": codes},
        "daily": {
            "time": [day0.strftime("%Y-%m-%d"), (day0 + timedelta(days=1)).strftime("%Y-%m-%d")],
            "weather_code": [2, 63],
            "temperature_2m_max": [round(conv(24), 1), round(conv(18), 1)],
            "temperature_2m_min": [round(conv(14), 1), round(conv(12), 1)],
            "precipitation_probability_max": [70, 80],
            "wind_speed_10m_max": [14.0, 18.0] if imperial else [22.0, 29.0],
            "sunrise": [d(0, 6.7 // 1), d(1, 6.7 // 1)],
            "sunset": [d(0, 19), d(1, 18)],
            "uv_index_max": [6.2, 2.1],
        },
    }


def headlines() -> list[news.Headline]:
    now = datetime.now(timezone.utc)
    rows = [
        ("BBC", "Global leaders agree landmark deal on shared grid investment after marathon overnight talks", 25),
        ("NPR", "Scientists report record-breaking solar output as new panels go online across the Southwest", 70),
        ("Guardian", "City councils weigh free public transit pilot as ridership climbs for ninth month", 130),
        ("BBC", "Open-source projects see surge of new contributors following major distro releases", 190),
        ("NPR", "Local bakery wins national award for sourdough made with heritage grain", 300),
    ]
    return [news.Headline(s, t, "https://example.com/", now - timedelta(minutes=m)) for s, t, m in rows]
