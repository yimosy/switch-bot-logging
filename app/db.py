import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    device_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery: Mapped[int | None] = mapped_column(Integer, nullable=True)
    co2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_status: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (Index("ix_measurements_device_recorded", "device_id", "recorded_at"),)


class WeatherMeasurement(Base):
    """Open-Meteoの外気データ。センサーとは別テーブルで全項目を保持する。"""

    __tablename__ = "weather_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain: Mapped[float | None] = mapped_column(Float, nullable=True)
    snowfall: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cloud_cover: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pressure_msl: Mapped[float | None] = mapped_column(Float, nullable=True)
    surface_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wind_gusts: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_status: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (Index("ix_weather_recorded", "recorded_at"),)


def build_weather_measurement(current: dict) -> WeatherMeasurement:
    """Map an Open-Meteo `current` payload to a WeatherMeasurement row."""
    return WeatherMeasurement(
        temperature=current.get("temperature_2m"),
        humidity=current.get("relative_humidity_2m"),
        apparent_temperature=current.get("apparent_temperature"),
        precipitation=current.get("precipitation"),
        rain=current.get("rain"),
        snowfall=current.get("snowfall"),
        weather_code=current.get("weather_code"),
        cloud_cover=current.get("cloud_cover"),
        pressure_msl=current.get("pressure_msl"),
        surface_pressure=current.get("surface_pressure"),
        wind_speed=current.get("wind_speed_10m"),
        wind_direction=current.get("wind_direction_10m"),
        wind_gusts=current.get("wind_gusts_10m"),
        is_day=current.get("is_day"),
        raw_status=json.dumps(current, ensure_ascii=False),
    )


def make_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def build_measurement(device: dict, status: dict) -> Measurement:
    """Map a SwitchBot status payload to a Measurement row."""
    return Measurement(
        device_id=device["deviceId"],
        device_name=device.get("deviceName", ""),
        device_type=device.get("deviceType", ""),
        temperature=status.get("temperature"),
        humidity=status.get("humidity"),
        battery=status.get("battery"),
        co2=status.get("CO2"),
        light_level=status.get("lightLevel"),
        raw_status=json.dumps(status, ensure_ascii=False),
    )
