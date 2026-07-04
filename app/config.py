import os


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# SwitchBot API credentials (required)
SWITCHBOT_TOKEN = os.environ.get("SWITCHBOT_TOKEN", "")
SWITCHBOT_SECRET = os.environ.get("SWITCHBOT_SECRET", "")

# Polling interval in seconds. SwitchBot API allows 10,000 requests/day,
# so keep interval * device count within that budget.
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))

# Database connection URL (SQLAlchemy format).
# Default: SQLite file under /data (mounted as a Docker volume).
# PostgreSQL example: postgresql+psycopg2://user:pass@db:5432/switchbot
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/switchbot.db")

# Device types to log. Empty = use the default sensor types below.
_default_types = [
    "Meter",
    "MeterPlus",
    "MeterPro",
    "MeterPro(CO2)",
    "WoIOSensor",
    "Hub 2",
]
TARGET_DEVICE_TYPES = _split_csv(os.environ.get("TARGET_DEVICE_TYPES", "")) or _default_types

# Optional: restrict to specific device IDs (comma separated). Empty = all.
TARGET_DEVICE_IDS = _split_csv(os.environ.get("TARGET_DEVICE_IDS", ""))

# Port for the visualization web server (web.py)
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
