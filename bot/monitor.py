from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from config import AppConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class StockStatus:
    in_stock: bool
    retailer: str
    detail: str
    raw: dict[str, Any] | None = None


class BaseMonitor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def check_stock(self) -> StockStatus:
        # Load cookies into session if available
        cookies_path = getattr(self.config, "cookies_path", None)
        if cookies_path:
            import json
            from pathlib import Path
            raw = json.loads(Path(cookies_path).read_text())
            for c in raw:
                self.session.cookies.set(c["name"], c["value"], domain=c.get("domain", "").lstrip("."))

        self.session.headers.update({
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.walmart.com/",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-platform": '"macOS"',
        })

        params = {"sku": self.config.product_id}
        response = self.session.get(
            self.config.walmart_item_api_url,
            params=params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()

        item = data.get("data", {}).get("product", {}) or data.get("item", {})
        availability = str(item.get("availabilityStatusV2") or item.get("availabilityStatus") or "").upper()
        in_stock = any(token in availability for token in {"IN_STOCK", "AVAILABLE"})

        return StockStatus(
            in_stock=in_stock,
            retailer="walmart",
            detail=f"Walmart availability={availability or 'UNKNOWN'}",
            raw=data,
    )

    def monitor_until_stock(self) -> StockStatus:
        LOGGER.info(
            "Monitoring started for %s every %ss",
            self.config.retailer,
            self.config.poll_interval,
        )
        while True:
            try:
                status = self.check_stock()
                if status.in_stock:
                    return status
                LOGGER.info("Not in stock yet: %s", status.detail)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Polling failure: %s", exc)

            time.sleep(self.config.poll_interval)


class TargetMonitor(BaseMonitor):
    def check_stock(self) -> StockStatus:
        if not self.config.target_api_key:
            raise ValueError("TARGET_API_KEY is required for Target monitoring")

        url = (
            "https://api.target.com/fulfillment_aggregator/v1/fiats/"
            f"{self.config.product_id}"
        )
        response = self.session.get(
            url,
            params={"key": self.config.target_api_key},
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()

        shipping_options = data.get("product", {}).get("fulfillment", {}).get("shipping_options", [])
        in_stock = any(option.get("availability_status") == "IN_STOCK" for option in shipping_options)

        return StockStatus(
            in_stock=in_stock,
            retailer="target",
            detail="Target fulfillment API checked",
            raw=data,
        )


class WalmartMonitor(BaseMonitor):
    def check_stock(self) -> StockStatus:
        params = {"sku": self.config.product_id}
        response = self.session.get(
            self.config.walmart_item_api_url,
            params=params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()

        item = data.get("data", {}).get("product", {}) or data.get("item", {})
        availability = str(item.get("availabilityStatusV2") or item.get("availabilityStatus") or "").upper()
        in_stock = any(token in availability for token in {"IN_STOCK", "AVAILABLE"})

        return StockStatus(
            in_stock=in_stock,
            retailer="walmart",
            detail=f"Walmart availability={availability or 'UNKNOWN'}",
            raw=data,
        )


class PokemonCenterMonitor(BaseMonitor):
    def check_stock(self) -> StockStatus:
        response = self.session.get(
            self.config.product_url,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()

        body = response.text.lower()
        in_stock = self.config.pokemon_center_in_stock_text in body and "sold out" not in body

        return StockStatus(
            in_stock=in_stock,
            retailer="pokemon_center",
            detail="Pokemon Center page text checked",
            raw={"url": self.config.product_url},
        )


def build_monitor(config: AppConfig) -> BaseMonitor:
    if config.retailer == "target":
        return TargetMonitor(config)
    if config.retailer == "walmart":
        return WalmartMonitor(config)
    if config.retailer == "pokemon_center":
        return PokemonCenterMonitor(config)
    raise ValueError(f"Unsupported retailer: {config.retailer}")
