import json
import logging
import time

import config
import weather
from db import Measurement, build_measurement, make_session_factory
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
    """Log outdoor weather from Open-Meteo as a pseudo device. Returns rows added."""
    if not config.WEATHER_ENABLED:
        return 0
    try:
        current = weather.fetch_current(config.WEATHER_LATITUDE, config.WEATHER_LONGITUDE)
    except Exception as e:
        logger.error("Failed to fetch weather: %s", e)
        return 0
    m = Measurement(
        device_id="open-meteo",
        device_name=config.WEATHER_DEVICE_NAME,
        device_type="OpenMeteo",
        temperature=current.get("temperature_2m"),
        humidity=current.get("relative_humidity_2m"),
        raw_status=json.dumps(current, ensure_ascii=False),
    )
    session.add(m)
    logger.info("%s (OpenMeteo): temp=%s hum=%s", m.device_name, m.temperature, m.humidity)
    return 1


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
