"""Alert notification provider services (Phase 8)."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, UTC
import logging
import httpx

logger = logging.getLogger("airex.notifications")


class NotificationProvider:
    async def send_notification(self, payload: dict, secret: str | None = None) -> None:
        raise NotImplementedError("NotificationProvider subclass must implement send_notification.")


class WebhookNotificationProvider(NotificationProvider):
    """HMAC-signed Webhook Notification Provider."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send_notification(self, payload: dict, secret: str | None = None) -> None:
        if not self.webhook_url:
            return

        json_data = json.dumps(payload, default=str)
        headers = {"Content-Type": "application/json"}
        timestamp = str(int(datetime.now(UTC).timestamp()))
        headers["X-Airex-Timestamp"] = timestamp

        # Compute HMAC signature if secret is provided (no leak of secret in body)
        if secret:
            # We signature-hash: secret + timestamp + body
            message = f"{timestamp}.{json_data}".encode()
            sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
            headers["X-Airex-Signature"] = sig

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(self.webhook_url, content=json_data, headers=headers)
            resp.raise_for_status()
            logger.info(f"Successfully dispatched alert webhook to {self.webhook_url}")
