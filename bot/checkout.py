from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError, sync_playwright

from config import AppConfig


LOGGER = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_VIEWPORT = {"width": 1280, "height": 800}
_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]

# Fields Cookie-Editor exports that Playwright does not accept
_COOKIE_STRIP_FIELDS = {"hostOnly", "storeId", "session"}

# Map Cookie-Editor sameSite values to Playwright-accepted values
_SAMESITE_MAP = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
    None: "None",
}


def _load_cookies(context: BrowserContext, cookies_path: str) -> None:
    raw = json.loads(Path(cookies_path).read_text())
    cleaned = []
    for cookie in raw:
        c = {k: v for k, v in cookie.items() if k not in _COOKIE_STRIP_FIELDS}
        c["sameSite"] = _SAMESITE_MAP.get(c.get("sameSite"), "None")
        if "expirationDate" in c:
            c["expires"] = int(c.pop("expirationDate"))
        cleaned.append(c)
    context.add_cookies(cleaned)
    LOGGER.info("Loaded %d cookies from %s", len(cleaned), cookies_path)


def save_session(config: AppConfig) -> None:
    """Legacy flow — opens browser for manual login."""
    state_path = Path(config.browser_state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            args=_LAUNCH_ARGS,
        )
        context = browser.new_context(
            user_agent=_USER_AGENT,
            viewport=_VIEWPORT,
        )
        page = context.new_page()
        page.goto(config.product_url, wait_until="domcontentloaded", timeout=30_000)
        LOGGER.info("Log in manually if needed, then press Enter in the terminal to save the session")
        input("Press Enter after the browser session is ready to save...")
        context.storage_state(path=str(state_path))
        browser.close()
        LOGGER.info("Saved browser state to %s", state_path)


def open_saved_session(config: AppConfig) -> None:
    state_path = Path(config.browser_state_path)
    cookies_path = getattr(config, "cookies_path", None)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config.headless,
            args=_LAUNCH_ARGS,
        )

        # Prefer cookies JSON if available, fall back to storage state
        if cookies_path and Path(cookies_path).exists():
            context = browser.new_context(
                user_agent=_USER_AGENT,
                viewport=_VIEWPORT,
            )
            _load_cookies(context, cookies_path)
            LOGGER.info("Using cookies from %s", cookies_path)
        elif state_path.exists():
            context = browser.new_context(
                storage_state=str(state_path),
                user_agent=_USER_AGENT,
                viewport=_VIEWPORT,
            )
            LOGGER.info("Using saved session from %s", state_path)
        else:
            LOGGER.warning("No cookies file or saved session found — loading without auth")
            context = browser.new_context(
                user_agent=_USER_AGENT,
                viewport=_VIEWPORT,
            )

        page = context.new_page()
        _load_product_page(page, config)
        _retailer_browser_handoff(page, context, config)
        browser.close()


def _load_product_page(page: Page, config: AppConfig) -> None:
    page.goto(config.product_url, wait_until="domcontentloaded", timeout=30_000)
    LOGGER.info("Loaded product page for %s", config.retailer)


def _retailer_browser_handoff(page: Page, context: BrowserContext, config: AppConfig) -> None:
    if config.retailer == "walmart":
        _handle_walmart_handoff(page, config)
    elif config.retailer == "target":
        _handle_target_handoff(page)
    elif config.retailer == "pokemon_center":
        _handle_pokemon_center_handoff(page)

    context.storage_state(path=config.browser_state_path)


def _handle_target_handoff(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except TimeoutError:
        LOGGER.info("Target page remained active; continuing with visible session")


def _handle_walmart_handoff(page: Page, config: AppConfig) -> None:
    start = time.time()
    while time.time() - start < config.max_queue_wait:
        content = page.content().lower()
        if "queue" in content or "line" in content:
            LOGGER.info("Walmart queue page detected, waiting...")
            time.sleep(5)
            page.reload(wait_until="domcontentloaded")
            continue
        return
    raise TimeoutError("Timed out while waiting on Walmart queue page")


def _handle_pokemon_center_handoff(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except TimeoutError:
        LOGGER.info("Pokemon Center page stayed busy; leaving browser open for manual completion")