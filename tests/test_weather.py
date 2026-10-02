from datetime import datetime

from cachy_widget import demo, weather as W


def fc(units="imperial", hour=14):
    now = datetime(2026, 10, 2, hour, 20)
    return W.parse(demo.raw_forecast(units, now), "Testville", units)


def test_parse_shapes():
    f = fc()
    assert len(f.hours) == 48
    assert f.today.date.isoformat() == "2026-10-02"
    assert f.tomorrow.date.isoformat() == "2026-10-03"
    assert f.current.kind == "partly"
    assert f.temp_unit == "°F" and f.wind_unit == "mph"


def test_metric_units():
    f = fc("metric")
    assert f.temp_unit == "°C" and f.wind_unit == "km/h"
    assert f.today.tmax == 24


def test_describe_unknown_code_is_safe():
    assert W.describe(12345) == ("Unknown", "cloudy")


def test_today_summary_mentions_upcoming_rain():
    # demo data has rain 15:00-19:00; at 14:20 it is "coming"
    assert "Rain likely around 3 PM" in W.today_summary(fc(hour=14))


def test_tomorrow_summary_compares_with_today():
    s = W.tomorrow_summary(fc())
    assert "cooler than today" in s and "rain likely" in s


def test_forecast_url_units():
    assert "temperature_unit=fahrenheit" in W.forecast_url(30.27, -97.74, "imperial")
    assert "wind_speed_unit=kmh" in W.forecast_url(30.27, -97.74, "metric")
