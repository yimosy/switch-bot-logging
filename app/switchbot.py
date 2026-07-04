"""SwitchBot API v1.1 client."""

import base64
import hashlib
import hmac
import logging
import time
import uuid

import requests

API_BASE = "https://api.switch-bot.com/v1.1"

logger = logging.getLogger(__name__)


class SwitchBotError(Exception):
    pass


class SwitchBotClient:
    def __init__(self, token: str, secret: str, timeout: int = 30):
        if not token or not secret:
            raise SwitchBotError("SWITCHBOT_TOKEN and SWITCHBOT_SECRET must be set")
        self.token = token
        self.secret = secret
        self.timeout = timeout

    def _headers(self) -> dict:
        t = str(int(round(time.time() * 1000)))
        nonce = str(uuid.uuid4())
        string_to_sign = f"{self.token}{t}{nonce}"
        sign = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                msg=string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return {
            "Authorization": self.token,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "Content-Type": "application/json; charset=utf8",
        }

    def _get(self, path: str) -> dict:
        resp = requests.get(f"{API_BASE}{path}", headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") != 100:
            raise SwitchBotError(
                f"API error on {path}: statusCode={data.get('statusCode')} message={data.get('message')}"
            )
        return data.get("body", {})

    def list_devices(self) -> list[dict]:
        """Return physical devices (infrared remotes are excluded)."""
        body = self._get("/devices")
        return body.get("deviceList", [])

    def get_device_status(self, device_id: str) -> dict:
        return self._get(f"/devices/{device_id}/status")
