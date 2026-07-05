import logging
import time

import config
import weather
from db import (
    Measurement,
    WeatherMeasurement,
    build_measurement,
    build_weather_measurement,
    make_session_factory,
)
from switchbot import SwitchBotClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("switchbot-logger")


def select_target_devices(devices: list[dict]) -> list[dict]:
    targets = []
    for d in devices:
        if config.TARGET_DEVICE_IDS and d.get("deviceId") not in config.TARGET_DEVICE_IDS:
            continue
        if d.get("deviceType") not in config.TARGET_DEVICE_TYPES:
            continue
        targets.append(d)
    return targets


def poll_weather(session) -> int:
    """Log outdoor weather from Open-Meteo into weather_measurements. Returns rows added."""
    if not config.WEATHER_ENABLED:
        return 0
    try:
        current = weather.fetch_current(config.WEATHER_LATITUDE, config.WEATHER_LONGITUDE)
    except Exception as e:
        logger.error("Failed to fetch weather: %s", e)
        return 0
    m = build_weather_measurement(current)
    session.add(m)
    logger.info(
        "%s (OpenMeteo): temp=%s hum=%s precip=%s wind=%s pressure=%s",
        config.WEATHER_DEVICE_NAME,
        m.temperature, m.humidity, m.precipitation, m.wind_speed, m.pressure_msl,
    )
    return 1


def migrate_legacy_weather(session_factory) -> None:
    """measurementsに擬似デバイスとして保存していた旧外気データをweather_measurementsへ移す。"""
    with session_factory() as session:
        legacy = (
            session.query(Measurement)
            .filter(Measurement.device_id == "open-meteo")
            .all()
        )
        if not legacy:
            return
        for r in legacy:
            session.add(
                WeatherMeasurement(
                    recorded_at=r.recorded_at,
                    temperature=r.temperature,
                    humidity=r.humidity,
                    raw_status=r.raw_status,
                )
            )
            session.delete(r)
        session.commit()
        logger.info("Migrated %d legacy weather row(s) to weather_measurements", len(legacy))


def poll_once(client: SwitchBotClient, session_factory) -> None:
    devices = select_target_devices(client.list_devices())
    if not devices:
        logger.warning(
            "No target devices found (types=%s, ids=%s)",
            config.TARGET_DEVICE_TYPES,
            config.TARGET_DEVICE_IDS or "all",
        )

    with session_factory() as session:
        saved = poll_weather(session)
        for device in devices:
            try:
                status = client.get_device_status(device["deviceId"])
            except Exception as e:
                logger.error("Failed to get status for %s (%s): %s",
                             device.get("deviceName"), device.get("deviceId"), e)
                continue
            m = build_measurement(device, status)
            session.add(m)
            saved += 1
            logger.info(
                "%s (%s): temp=%s hum=%s battery=%s co2=%s light=%s",
                m.device_name, m.device_type,
                m.temperature, m.humidity, m.battery, m.co2, m.light_level,
            )
        session.commit()
        logger.info("Saved %d measurement(s)", saved)


def main() -> None:
    client = SwitchBotClient(config.SWITCHBOT_TOKEN, config.SWITCHBOT_SECRET)
    session_factory = make_session_factory(config.DATABASE_URL)
    migrate_legacy_weather(session_factory)
    logger.info(
        "Starting polling loop: interval=%ss, db=%s",
        config.POLL_INTERVAL_SECONDS,
        config.DATABASE_URL.split("@")[-1],  # avoid logging credentials
    )
    while True:
        started = time.monotonic()
        try:
            poll_once(client, session_factory)
        except Exception:
            logger.exception("Polling cycle failed")
        elapsed = time.monotonic() - started
        time.sleep(max(1.0, config.POLL_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    main()
