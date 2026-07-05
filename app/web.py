"""Visualization web server for logged SwitchBot measurements."""

import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

import config
from db import Measurement, WeatherMeasurement, make_session_factory

# 外気(weather_measurements)はダッシュボード上では擬似デバイスとして扱う
WEATHER_DEVICE_ID = "open-meteo"
WEATHER_DEVICE_TYPE = "OpenMeteo"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("switchbot-web")

app = Flask(__name__, static_folder="static")
session_factory = make_session_factory(config.DATABASE_URL)

# Cap points per device per response; older ranges are thinned by striding.
MAX_POINTS_PER_DEVICE = 500

METRICS = ["temperature", "humidity", "co2", "battery", "light_level"]


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/devices")
def api_devices():
    with session_factory() as session:
        rows = (
            session.query(
                Measurement.device_id,
                Measurement.device_name,
                Measurement.device_type,
            )
            .distinct()
            .order_by(Measurement.device_name)
            .all()
        )
    return jsonify(
        [
            {"deviceId": r.device_id, "deviceName": r.device_name, "deviceType": r.device_type}
            for r in rows
        ]
    )


def _to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


@app.route("/api/measurements")
def api_measurements():
    try:
        hours = float(request.args.get("hours", "24"))
    except ValueError:
        return jsonify({"error": "invalid hours"}), 400
    hours = min(max(hours, 1), 24 * 365)
    device_id = request.args.get("device_id")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with session_factory() as session:
        q = (
            session.query(Measurement)
            .filter(Measurement.recorded_at >= cutoff.replace(tzinfo=None))
            .order_by(Measurement.recorded_at)
        )
        if device_id:
            q = q.filter(Measurement.device_id == device_id)
        rows = q.all()

        wrows = []
        if device_id in (None, WEATHER_DEVICE_ID):
            wrows = (
                session.query(WeatherMeasurement)
                .filter(WeatherMeasurement.recorded_at >= cutoff.replace(tzinfo=None))
                .order_by(WeatherMeasurement.recorded_at)
                .all()
            )

    # Group rows into one series per device
    by_device: dict[str, dict] = {}
    for r in rows:
        series = by_device.setdefault(
            r.device_id,
            {
                "deviceId": r.device_id,
                "deviceName": r.device_name,
                "deviceType": r.device_type,
                "points": [],
            },
        )
        series["points"].append(
            {
                "t": _to_iso_utc(r.recorded_at),
                "temperature": r.temperature,
                "humidity": r.humidity,
                "co2": r.co2,
                "battery": r.battery,
                "light_level": r.light_level,
            }
        )

    # Merge outdoor weather in as a pseudo device series
    if wrows:
        by_device[WEATHER_DEVICE_ID] = {
            "deviceId": WEATHER_DEVICE_ID,
            "deviceName": config.WEATHER_DEVICE_NAME,
            "deviceType": WEATHER_DEVICE_TYPE,
            "points": [
                {
                    "t": _to_iso_utc(w.recorded_at),
                    "temperature": w.temperature,
                    "humidity": w.humidity,
                    "co2": None,
                    "battery": None,
                    "light_level": None,
                }
                for w in wrows
            ],
        }

    # Thin long series so the chart stays responsive (always keep the last point)
    for series in by_device.values():
        pts = series["points"]
        if len(pts) > MAX_POINTS_PER_DEVICE:
            stride = -(-len(pts) // MAX_POINTS_PER_DEVICE)  # ceil division
            thinned = pts[::stride]
            if thinned[-1] is not pts[-1]:
                thinned.append(pts[-1])
            series["points"] = thinned

    # Report which metrics actually have data so the UI can hide empty charts
    available = {
        m: any(p[m] is not None for s in by_device.values() for p in s["points"])
        for m in METRICS
    }

    return jsonify({"hours": hours, "series": list(by_device.values()), "available": available})


@app.route("/api/latest")
def api_latest():
    """Latest measurement per device, for the summary cards."""
    with session_factory() as session:
        device_ids = [r.device_id for r in session.query(Measurement.device_id).distinct()]
        result = []
        for did in device_ids:
            r = (
                session.query(Measurement)
                .filter(Measurement.device_id == did)
                .order_by(Measurement.recorded_at.desc())
                .first()
            )
            if r is None:
                continue
            result.append(
                {
                    "deviceId": r.device_id,
                    "deviceName": r.device_name,
                    "deviceType": r.device_type,
                    "recordedAt": _to_iso_utc(r.recorded_at),
                    "temperature": r.temperature,
                    "humidity": r.humidity,
                    "co2": r.co2,
                    "battery": r.battery,
                    "light_level": r.light_level,
                }
            )

        w = (
            session.query(WeatherMeasurement)
            .order_by(WeatherMeasurement.recorded_at.desc())
            .first()
        )
        if w is not None:
            result.append(
                {
                    "deviceId": WEATHER_DEVICE_ID,
                    "deviceName": config.WEATHER_DEVICE_NAME,
                    "deviceType": WEATHER_DEVICE_TYPE,
                    "recordedAt": _to_iso_utc(w.recorded_at),
                    "temperature": w.temperature,
                    "humidity": w.humidity,
                    "co2": None,
                    "battery": None,
                    "light_level": None,
                }
            )
    result.sort(key=lambda x: x["deviceName"])
    return jsonify(result)


if __name__ == "__main__":
    logger.info("Starting web server on port %d", config.WEB_PORT)
    serve(app, host="0.0.0.0", port=config.WEB_PORT)
