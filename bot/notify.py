from __future__ import annotations

import logging
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


def send_discord_notification(webhook_url: str, title: str, description: str, **fields: Any) -> None:
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0x1F8B4C,
                "fields": [
                    {"name": key.replace("_", " ").title(), "value": str(value), "inline": False}
                    for key, value in fields.items()
                    if value is not None
                ],
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("Failed to send Discord notification: %s", exc)
