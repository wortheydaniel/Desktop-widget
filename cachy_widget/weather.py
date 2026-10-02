"""Weather: Open-Meteo client (no API key), parsing, and plain-English summaries."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime

from . import net

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather interpretation codes -> (label, icon kind)
_WMO: dict[int, tuple[str, str]] = {
    0: ("Clear", "clear"),
    1: ("Mostly clear", "clear"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"),
    67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Heavy showers", "rain"),
    85: ("Snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm, hail", "storm"),
    99: ("Severe thunderstorm", "storm"),
}


def describe(code: int) -> tuple[str, str]:
    return _WMO.get(int(code), ("Unknown", "cloudy"))


@dataclass
class Hour:
    time: datetime
    temp: float
    precip: int  # probability, %
    code: int


@dataclass
class Day:
    date: date
    code: int
    tmax: float
    tmin: float
    precip: int  # max probability, %
    wind: float
    sunrise: datetime
    sunset: datetime
    uv: float

    @property
    def label(self) -> str:
        return describe(self.code)[0]

    @property
    def kind(self) -> str:
        return describe(self.code)[1]


@dataclass
class Current:
    time: datetime
    temp: float
    feels: float
    code: int
    is_day: bool
    wind: float
    humidity: int

    @property
    def label(self) -> str:
        return describe(self.code)[0]

    @property
    def kind(self) -> str:
        return describe(self.code)[1]


@dataclass
class Forecast:
    place: str
    units: str  # "imperial" | "metric"
    current: Current
    today: Day
    tomorrow: Day
    hours: list[Hour]  # today 00:00 .. tomorrow 23:00 (local to the place)

    @property
    def temp_unit(self) -> str:
        return "°F" if self.units == "imperial" else "°C"

    @property
    def wind_unit(self) -> str:
        return "mph" if self.units == "imperial" else "km/h"


# --------------------------------------------------------------------------- fetch


def forecast_url(lat: float, lon: float, units: str) -> str:
    imperial = units == "imperial"
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
            "wind_speed_10m_max,sunrise,sunset,uv_index_max"
        ),
        "forecast_days": "2",
        "timezone": "auto",
        "temperature_unit": "fahrenheit" if imperial else "celsius",
        "wind_speed_unit": "mph" if imperial else "kmh",
    }
    return f"{FORECAST_URL}?{urllib.parse.urlencode(params)}"


def fetch_raw(lat: float, lon: float, units: str) -> dict:
    return net.get_json(forecast_url(lat, lon, units))


def geocode(query: str, count: int = 6) -> list[dict]:
    """City name -> [{'name': 'Austin, Texas, United States', 'lat':…, 'lon':…}]."""
    url = f"{GEOCODE_URL}?{urllib.parse.urlencode({'name': query, 'count': count, 'language': 'en'})}"
    out = []
    for r in net.get_json(url).get("results", []):
        parts = [r.get("name"), r.get("admin1"), r.get("country")]
        label = ", ".join(dict.fromkeys(p for p in parts if p))  # dedupe e.g. "Singapore, Singapore"
        out.append({"name": label, "short": r.get("name", label), "lat": r["latitude"], "lon": r["longitude"]})
    return out


def locate_by_ip() -> dict:
    """Rough location from the public IP (city-level); used when none is configured."""
    last: Exception | None = None
    for url, parse in (
        ("https://ipwho.is/", lambda j: (j["city"], j["region"], j["latitude"], j["longitude"]) if j.get("success", True) else None),
        ("https://ipapi.co/json/", lambda j: (j["city"], j["region"], j["latitude"], j["longitude"])),
    ):
        try:
            got = parse(net.get_json(url, timeout=8))
            if got:
                city, region, lat, lon = got
                return {"name": ", ".join(p for p in (city, region) if p), "short": city, "lat": lat, "lon": lon}
        except Exception as exc:  # noqa: BLE001 - try next provider
            last = exc
    raise RuntimeError(f"could not detect location ({last}); set one from the right-click menu")


# --------------------------------------------------------------------------- parse


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s)


def parse(raw: dict, place: str, units: str) -> Forecast:
    c, h, d = raw["current"], raw["hourly"], raw["daily"]
    current = Current(
        time=_t(c["time"]),
        temp=c["temperature_2m"],
        feels=c["apparent_temperature"],
        code=c["weather_code"],
        is_day=bool(c["is_day"]),
        wind=c["wind_speed_10m"],
        humidity=c["relative_humidity_2m"],
    )
    days = [
        Day(
            date=date.fromisoformat(d["time"][i]),
            code=d["weather_code"][i],
            tmax=d["temperature_2m_max"][i],
            tmin=d["temperature_2m_min"][i],
            precip=int(d["precipitation_probability_max"][i] or 0),
            wind=d["wind_speed_10m_max"][i],
            sunrise=_t(d["sunrise"][i]),
            sunset=_t(d["sunset"][i]),
            uv=d["uv_index_max"][i] or 0,
        )
        for i in range(2)
    ]
    hours = [
        Hour(_t(h["time"][i]), h["temperature_2m"][i], int(h["precipitation_probability"][i] or 0), h["weather_code"][i])
        for i in range(len(h["time"]))
    ]
    return Forecast(place, units, current, days[0], days[1], hours)


# --------------------------------------------------------------------------- words


def _celsius(f: Forecast, v: float) -> float:
    return (v - 32) * 5 / 9 if f.units == "imperial" else v


def _hour_label(dt: datetime) -> str:
    return dt.strftime("%-I %p").replace("AM", "AM").strip()


def today_summary(f: Forecast) -> str:
    """One or two short sentences: what to expect for the rest of today."""
    now = f.current.time
    upcoming = [x for x in f.hours if x.time.date() == now.date() and x.time.hour >= now.hour]
    wet = [x for x in upcoming if x.precip >= 50]
    bits: list[str] = []
    if wet:
        kind = describe(wet[0].code)[1]
        noun = {"snow": "Snow", "storm": "Storms"}.get(kind, "Rain")
        if wet[0].time.hour <= now.hour:
            bits.append(f"{noun} now, easing later." if len(wet) < len(upcoming) else f"{noun} on and off all day.")
        else:
            bits.append(f"{noun} likely around {_hour_label(wet[0].time)}.")
    elif f.today.precip < 20:
        bits.append("Dry for the rest of today.")
    else:
        bits.append(f"Small chance of rain ({f.today.precip}%).")

    hi = _celsius(f, f.today.tmax)
    if hi >= 32:
        bits.append("Hot out — stay hydrated.")
    elif hi <= 0:
        bits.append("Freezing — bundle up.")
    elif f.today.wind >= (25 if f.units == "imperial" else 40):
        bits.append("Gusty.")
    elif f.today.uv >= 8 and f.current.is_day:
        bits.append("High UV, wear sunscreen.")
    return " ".join(bits)


def tomorrow_summary(f: Forecast) -> str:
    """Compare tomorrow with today, e.g. '6° cooler than today · rain likely'."""
    delta = round(f.tomorrow.tmax - f.today.tmax)
    threshold = 5 if f.units == "imperial" else 3
    if abs(delta) >= threshold:
        text = f"{abs(delta)}° {'warmer' if delta > 0 else 'cooler'} than today"
    else:
        text = "About the same as today"
    if f.tomorrow.precip >= 50:
        noun = {"snow": "snow", "storm": "storms"}.get(f.tomorrow.kind, "rain")
        text += f" · {noun} likely"
    return text


def fmt_temp(v: float) -> str:
    return f"{round(v):d}°"


def fmt_clock(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p")
