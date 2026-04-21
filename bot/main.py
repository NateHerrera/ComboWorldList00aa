from __future__ import annotations

import argparse
import logging

from playwright.sync_api import TimeoutError

from checkout import open_saved_session, save_session
from config import load_config
from monitor import build_monitor
from notify import send_discord_notification


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retail stock monitor with browser session handoff")
    parser.add_argument(
        "command",
        nargs="?",
        default="monitor",
        choices=("monitor", "save-session"),
        help="monitor for stock or save a browser session before a drop",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config()
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to load configuration: %s", exc)
        return 1

    if args.command == "save-session":
        save_session(config)
        send_discord_notification(
            config.discord_webhook_url,
            title="Session Saved",
            description="Browser session saved locally for future monitoring runs.",
            retailer=config.retailer,
            browser_state_path=config.browser_state_path,
        )
        return 0

    send_discord_notification(
        config.discord_webhook_url,
        title="Monitoring Started",
        description=f"Watching {config.retailer} product for stock",
        retailer=config.retailer,
        product_url=config.product_url,
        product_id=config.product_id,
        poll_interval=config.poll_interval,
        buy_limit=config.buy_limit,
        max_queue_wait=config.max_queue_wait,
    )

    monitor = build_monitor(config)
    stock_status = monitor.monitor_until_stock()

    send_discord_notification(
        config.discord_webhook_url,
        title="In Stock Detected",
        description=f"{config.retailer} stock signal detected",
        detail=stock_status.detail,
    )

    try:
        if config.retailer == "walmart":
            send_discord_notification(
                config.discord_webhook_url,
                title="Queue Watch Started",
                description="Walmart product page opened with saved session; waiting for queue to clear.",
                max_queue_wait=config.max_queue_wait,
            )

        open_saved_session(config)
    except TimeoutError:
        send_discord_notification(
            config.discord_webhook_url,
            title="Queue Timeout",
            description="Max queue wait reached. Monitoring run stopped without completing browser handoff.",
            retailer=config.retailer,
            max_queue_wait=config.max_queue_wait,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        logging.exception("Browser handoff failed: %s", exc)
        send_discord_notification(
            config.discord_webhook_url,
            title="Browser Handoff Failed",
            description="Stock was detected, but the browser session could not be prepared.",
            error=str(exc),
        )
        return 1

    send_discord_notification(
        config.discord_webhook_url,
        title="Browser Ready",
        description="Saved session loaded and browser handed off for manual checkout.",
        retailer=config.retailer,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
