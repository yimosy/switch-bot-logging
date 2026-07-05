"""Outdoor weather via the Open-Meteo API (no API key required)."""

import requests

API_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_current(latitude: str, longitude: str, timeout: int = 30) -> dict:
    """Return Open-Meteo's `current` block, e.g. temperature_2m / relative_humidity_2m."""
    resp = requests.get(
        API_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "is_day",
                    "precipitation",
                    "rain",
                    "snowfall",
                    "weather_code",
                    "cloud_cover",
                    "pressure_msl",
                    "surface_pressure",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "wind_gusts_10m",
                ]
            ),
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("current", {})
