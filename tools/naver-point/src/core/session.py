"""Playwright browser session and Naver authentication manager."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from core.config import (
    NAVER_LOGIN_URL,
    NAVER_PAY_BENEFIT_URL,
    ERROR_SCREENSHOT_PATH,
    LOG_FILE,
)
from core.sync import SessionSyncManager

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class NaverSessionManager:
    """Manages browser context, Naver authentication state, and session persistence."""

    def __init__(self, headless: bool = True, session_path: Path | None = None):
        self.headless = headless
        self.sync_manager = SessionSyncManager(session_path)
        self.session_path = self.sync_manager.session_path
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def _start_context(self):
        """Start Playwright context with storage_state if available."""
        self.playwright = await async_playwright().start()

        # Attempt to pull latest session if needed
        self.sync_manager.pull()

        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            "user_agent": USER_AGENT,
            "viewport": {"width": 1280, "height": 800},
        }

        # Inject storage_state if file exists
        if self.session_path.exists() and self.session_path.stat().st_size > 0:
            try:
                # Validate JSON format before passing
                json.loads(self.session_path.read_text("utf-8"))
                launch_kwargs["storage_state"] = str(self.session_path)
                logger.info(f"Loaded storage_state from {self.session_path}")
            except Exception as e:
                logger.warning(f"Failed to read existing session JSON: {e}")

        browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=launch_kwargs["args"],
        )
        self.browser = browser

        context_kwargs = {
            "user_agent": launch_kwargs["user_agent"],
            "viewport": launch_kwargs["viewport"],
        }
        if "storage_state" in launch_kwargs:
            context_kwargs["storage_state"] = launch_kwargs["storage_state"]

        self.context = await browser.new_context(**context_kwargs)
        self.page = await self.context.new_page()

    async def save_session(self):
        """Save current context cookies and localStorage to session JSON and push to cloud."""
        if self.context:
            try:
                self.session_path.parent.mkdir(parents=True, exist_ok=True)
                await self.context.storage_state(path=str(self.session_path))
                logger.info(f"Session saved locally: {self.session_path}")
                self.sync_manager.push()
            except Exception as e:
                logger.error(f"Failed to save session state: {e}")

    async def save_error_screenshot(self, target_path: Path = ERROR_SCREENSHOT_PATH):
        """Capture screenshot on unexpected failure for AI/human diagnosis."""
        if self.page:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                await self.page.screenshot(path=str(target_path), full_page=True)
                logger.info(f"Error screenshot captured at {target_path}")
            except Exception as e:
                logger.warning(f"Could not capture error screenshot: {e}")

    async def is_logged_in(self) -> bool:
        """Check whether the active session has a valid Naver login cookie."""
        if not self.context:
            return False
        cookies = await self.context.cookies()
        has_nid_ses = any(c["name"] == "NID_SES" and c.get("value") for c in cookies)
        if not has_nid_ses:
            return False

        # Verify against benefit page
        try:
            await self.page.goto(NAVER_PAY_BENEFIT_URL, wait_until="domcontentloaded", timeout=7000)
            if "nidlogin.login" in self.page.url:
                return False
            login_btn = await self.page.query_selector("a[href*='nidlogin.login']")
            return login_btn is None
        except Exception:
            return False

    async def login_interactive(self, status_callback=None) -> bool:
        """Launch headed browser for manual user login and extract session."""
        self.headless = False
        await self._start_context()

        if status_callback:
            status_callback("🔑 브라우저 창에서 네이버 로그인을 진행해 주세요...")

        await self.page.goto(NAVER_LOGIN_URL)

        # Wait until user finishes login
        while True:
            await asyncio.sleep(1)
            current_url = self.page.url
            cookies = await self.context.cookies()
            has_nid_ses = any(c["name"] == "NID_SES" and c.get("value") for c in cookies)

            if "nidlogin.login" not in current_url and has_nid_ses:
                if status_callback:
                    status_callback("✅ 네이버 로그인 감지 완료! 세션을 저장하고 동기화합니다...")
                await asyncio.sleep(2)
                await self.save_session()
                return True

    async def get_session_info(self) -> dict:
        """Inspect session details without full browser run."""
        sync_status = self.sync_manager.get_status()
        if not self.session_path.exists():
            return {
                "exists": False,
                "logged_in": False,
                "account": None,
                "sync": sync_status,
            }

        try:
            data = json.loads(self.session_path.read_text("utf-8"))
            cookies = data.get("cookies", [])
            has_ses = any(c.get("name") == "NID_SES" for c in cookies)
            nid_aut = next((c for c in cookies if c.get("name") == "NID_AUT"), None)
            
            # Masked account identifier hint if available
            account_hint = "Naver User"
            return {
                "exists": True,
                "has_session_cookie": has_ses,
                "sync": sync_status,
                "cookie_count": len(cookies),
            }
        except Exception as e:
            return {
                "exists": True,
                "error": str(e),
                "sync": sync_status,
            }

    async def __aenter__(self):
        await self._start_context()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.save_error_screenshot()
        elif self.context:
            await self.save_session()

        try:
            if self.context:
                await self.context.close()
        finally:
            self.context = None
            try:
                if hasattr(self, "browser") and self.browser:
                    await self.browser.close()
            finally:
                if self.playwright:
                    await self.playwright.stop()
                self.playwright = None
                self.page = None
