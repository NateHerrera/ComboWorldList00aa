from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    return int(raw_value)


@dataclass
class AppConfig:
    retailer: str
    product_url: str
    product_id: str
    buy_limit: int
    poll_interval: int
    max_queue_wait: int
    discord_webhook_url: str
    browser_state_path: str
    headless: bool
    target_api_key: str | None
    walmart_item_api_url: str
    pokemon_center_in_stock_text: str
    request_timeout: int
    cookies_path: str | None


def load_config() -> AppConfig:
    retailer = _require_env("RETAILER").lower()
    if retailer not in {"target", "walmart", "pokemon_center"}:
        raise ValueError("RETAILER must be one of: target, walmart, pokemon_center")

    return AppConfig(
        retailer=retailer,
        product_url=_require_env("PRODUCT_URL"),
        product_id=_require_env("PRODUCT_ID"),
        buy_limit=_get_int("BUY_LIMIT", 1),
        poll_interval=_get_int(
            "POLL_INTERVAL",
            2 if retailer == "pokemon_center" else 5,
        ),
        max_queue_wait=_get_int("MAX_QUEUE_WAIT", 180),
        discord_webhook_url=_require_env("DISCORD_WEBHOOK_URL"),
        browser_state_path=os.getenv("BROWSER_STATE_PATH", str(BASE_DIR / "session.json")),
        headless=os.getenv("HEADLESS", "false").strip().lower() == "true",
        target_api_key=os.getenv("TARGET_API_KEY", "").strip() or None,
        walmart_item_api_url=os.getenv(
            "WALMART_ITEM_API_URL",
            "https://www.walmart.com/orchestra/home/graphql/item",
        ).strip(),
        pokemon_center_in_stock_text=os.getenv(
            "POKEMON_CENTER_IN_STOCK_TEXT",
            "add to cart",
        ).strip().lower(),
        request_timeout=_get_int("REQUEST_TIMEOUT", 10),
        cookies_path=os.getenv("COOKIES_PATH", "").strip() or None,
    )
