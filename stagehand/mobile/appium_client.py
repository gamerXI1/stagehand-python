"""Appium WebDriver client for iOS and Android device automation."""

import asyncio
import base64
from typing import Any, Optional

from appium import webdriver as appium_webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

from ..types.mobile import (
    AndroidCapabilities,
    AppiumCapabilities,
    IOSCapabilities,
    MobilePlatform,
    MobileSessionConfig,
)


class AppiumClient:
    """Appium WebDriver wrapper for mobile device automation.

    Supports both iOS (XCUITest) and Android (UiAutomator2) automation.
    Handles session management, screenshots, and device control.
    """

    def __init__(
        self,
        session_config: MobileSessionConfig,
        logger: Optional[Any] = None,
    ):
        """Initialize AppiumClient.

        Args:
            session_config: Configuration including Appium server URL and capabilities
            logger: Optional logger instance
        """
        self.session_config = session_config
        self.logger = logger
        self.driver: Optional[appium_webdriver.Remote] = None
        self._viewport_width: Optional[int] = None
        self._viewport_height: Optional[int] = None

    def _log(self, level: str, message: str, category: str = "appium") -> None:
        """Log a message if logger is available."""
        if self.logger:
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(message, category=category)

    async def connect(self) -> None:
        """Establish connection to the Appium server and start a session.

        Raises:
            ConnectionError: If unable to connect to Appium server
            ValueError: If capabilities are invalid
        """
        self._log("info", f"Connecting to Appium server: {self.session_config.appium_server_url}")

        try:
            options = self._build_options(self.session_config.capabilities)

            # Run synchronous WebDriver creation in executor
            loop = asyncio.get_event_loop()
            self.driver = await loop.run_in_executor(
                None,
                lambda: appium_webdriver.Remote(
                    command_executor=self.session_config.appium_server_url,
                    options=options,
                ),
            )

            # Set implicit wait
            self.driver.implicitly_wait(self.session_config.implicit_wait_ms / 1000)

            # Cache viewport size
            window_size = await self.get_viewport_size()
            self._viewport_width = window_size["width"]
            self._viewport_height = window_size["height"]

            self._log(
                "info",
                f"Connected to device. Viewport: {self._viewport_width}x{self._viewport_height}",
            )

        except Exception as e:
            self._log("error", f"Failed to connect to Appium: {e}")
            raise ConnectionError(f"Failed to connect to Appium server: {e}") from e

    def _build_options(
        self, capabilities: AppiumCapabilities
    ) -> UiAutomator2Options | XCUITestOptions:
        """Build Appium options from capabilities.

        Args:
            capabilities: Appium capabilities model

        Returns:
            Platform-specific options object
        """
        caps_dict = capabilities.model_dump(by_alias=True, exclude_none=True)

        if isinstance(capabilities, IOSCapabilities) or capabilities.platform_name == MobilePlatform.IOS:
            options = XCUITestOptions()
        elif isinstance(capabilities, AndroidCapabilities) or capabilities.platform_name == MobilePlatform.ANDROID:
            options = UiAutomator2Options()
        else:
            raise ValueError(f"Unsupported platform: {capabilities.platform_name}")

        # Load capabilities into options
        for key, value in caps_dict.items():
            if hasattr(options, key):
                setattr(options, key, value)
            else:
                options.set_capability(key, value)

        return options

    async def disconnect(self) -> None:
        """Close the Appium session and clean up resources."""
        if self.driver:
            self._log("info", "Disconnecting from Appium session")
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.driver.quit)
            except Exception as e:
                self._log("error", f"Error disconnecting: {e}")
            finally:
                self.driver = None
                self._viewport_width = None
                self._viewport_height = None

    def _ensure_connected(self) -> appium_webdriver.Remote:
        """Ensure driver is connected.

        Returns:
            The active WebDriver instance

        Raises:
            RuntimeError: If not connected
        """
        if not self.driver:
            raise RuntimeError("Not connected to Appium. Call connect() first.")
        return self.driver

    async def get_screenshot_base64(self) -> str:
        """Capture device screenshot as base64 encoded PNG.

        Returns:
            Base64 encoded screenshot string
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        screenshot = await loop.run_in_executor(None, driver.get_screenshot_as_base64)
        return screenshot

    async def get_screenshot_bytes(self) -> bytes:
        """Capture device screenshot as bytes.

        Returns:
            Screenshot as PNG bytes
        """
        base64_screenshot = await self.get_screenshot_base64()
        return base64.b64decode(base64_screenshot)

    async def get_viewport_size(self) -> dict[str, int]:
        """Get the device screen dimensions.

        Returns:
            Dict with 'width' and 'height' keys
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        size = await loop.run_in_executor(None, driver.get_window_size)
        return {"width": size["width"], "height": size["height"]}

    @property
    def viewport_width(self) -> int:
        """Get cached viewport width."""
        if self._viewport_width is None:
            raise RuntimeError("Viewport not initialized. Call connect() first.")
        return self._viewport_width

    @property
    def viewport_height(self) -> int:
        """Get cached viewport height."""
        if self._viewport_height is None:
            raise RuntimeError("Viewport not initialized. Call connect() first.")
        return self._viewport_height

    async def get_page_source(self) -> str:
        """Get the current view hierarchy as XML.

        Returns:
            XML string of the view hierarchy
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.page_source)

    async def get_current_context(self) -> str:
        """Get the current context (NATIVE_APP or WEBVIEW_*).

        Returns:
            Current context string
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.current_context)

    async def get_contexts(self) -> list[str]:
        """Get all available contexts.

        Returns:
            List of context strings (e.g., ['NATIVE_APP', 'WEBVIEW_chrome'])
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.contexts)

    async def switch_context(self, context: str) -> None:
        """Switch to a different context.

        Args:
            context: Context name (e.g., 'NATIVE_APP', 'WEBVIEW_chrome')
        """
        driver = self._ensure_connected()
        self._log("info", f"Switching to context: {context}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: driver.switch_to.context(context))

    async def launch_app(self, app_id: str) -> None:
        """Launch an app by bundle ID (iOS) or package name (Android).

        Args:
            app_id: Bundle ID or package name
        """
        driver = self._ensure_connected()
        self._log("info", f"Launching app: {app_id}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: driver.activate_app(app_id))

    async def terminate_app(self, app_id: str) -> bool:
        """Terminate an app by bundle ID (iOS) or package name (Android).

        Args:
            app_id: Bundle ID or package name

        Returns:
            True if app was terminated successfully
        """
        driver = self._ensure_connected()
        self._log("info", f"Terminating app: {app_id}")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.terminate_app(app_id))

    async def open_url(self, url: str) -> None:
        """Open a URL in the mobile browser.

        Args:
            url: URL to open
        """
        driver = self._ensure_connected()
        self._log("info", f"Opening URL: {url}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: driver.get(url))

    async def get_current_url(self) -> str:
        """Get the current URL (for web contexts).

        Returns:
            Current URL string
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.current_url)

    async def press_home(self) -> None:
        """Press the home button."""
        driver = self._ensure_connected()
        self._log("debug", "Pressing home button")
        loop = asyncio.get_event_loop()

        platform = self.session_config.capabilities.platform_name
        if platform == MobilePlatform.IOS:
            # iOS: Use driver.execute_script with mobile: pressButton
            await loop.run_in_executor(
                None,
                lambda: driver.execute_script("mobile: pressButton", {"name": "home"}),
            )
        else:
            # Android: Use keyevent for home button (keycode 3)
            await loop.run_in_executor(
                None, lambda: driver.press_keycode(3)
            )

    async def press_back(self) -> None:
        """Press the back button (Android) or navigate back (iOS)."""
        driver = self._ensure_connected()
        self._log("debug", "Pressing back button")
        loop = asyncio.get_event_loop()

        platform = self.session_config.capabilities.platform_name
        if platform == MobilePlatform.ANDROID:
            # Android: Use keyevent for back button (keycode 4)
            await loop.run_in_executor(None, lambda: driver.press_keycode(4))
        else:
            # iOS: Navigate back in browser or use swipe gesture
            await loop.run_in_executor(None, lambda: driver.back())

    async def lock_device(self, seconds: Optional[int] = None) -> None:
        """Lock the device screen.

        Args:
            seconds: Optional duration to lock (Android only)
        """
        driver = self._ensure_connected()
        self._log("debug", "Locking device")
        loop = asyncio.get_event_loop()

        if seconds:
            await loop.run_in_executor(None, lambda: driver.lock(seconds))
        else:
            await loop.run_in_executor(None, lambda: driver.lock())

    async def unlock_device(self) -> None:
        """Unlock the device screen."""
        driver = self._ensure_connected()
        self._log("debug", "Unlocking device")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: driver.unlock())

    async def is_locked(self) -> bool:
        """Check if the device is locked.

        Returns:
            True if device is locked
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.is_locked())

    async def set_orientation(self, orientation: str) -> None:
        """Set device orientation.

        Args:
            orientation: 'PORTRAIT' or 'LANDSCAPE'
        """
        driver = self._ensure_connected()
        self._log("debug", f"Setting orientation: {orientation}")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: setattr(driver, "orientation", orientation))

    async def get_orientation(self) -> str:
        """Get current device orientation.

        Returns:
            'PORTRAIT' or 'LANDSCAPE'
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.orientation)

    async def hide_keyboard(self) -> None:
        """Hide the on-screen keyboard if visible."""
        driver = self._ensure_connected()
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: driver.hide_keyboard())
        except Exception:
            # Keyboard might not be visible
            pass

    async def is_keyboard_shown(self) -> bool:
        """Check if keyboard is visible.

        Returns:
            True if keyboard is shown
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.is_keyboard_shown())

    def create_touch_action(self) -> tuple[ActionBuilder, PointerInput]:
        """Create a new touch action builder.

        Returns:
            Tuple of (ActionBuilder, PointerInput) for building touch gestures
        """
        driver = self._ensure_connected()
        touch_input = PointerInput(interaction.POINTER_TOUCH, "touch")
        actions = ActionBuilder(driver, mouse=touch_input)
        return actions, touch_input

    async def execute_touch_action(self, actions: ActionBuilder) -> None:
        """Execute a touch action sequence.

        Args:
            actions: ActionBuilder with configured touch actions
        """
        self._ensure_connected()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, actions.perform)

    async def find_element(self, by: str, value: str) -> Any:
        """Find an element on screen.

        Args:
            by: Locator strategy (e.g., AppiumBy.ACCESSIBILITY_ID)
            value: Locator value

        Returns:
            WebElement if found
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.find_element(by, value))

    async def find_elements(self, by: str, value: str) -> list[Any]:
        """Find multiple elements on screen.

        Args:
            by: Locator strategy
            value: Locator value

        Returns:
            List of WebElements
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: driver.find_elements(by, value))

    async def send_keys(self, text: str) -> None:
        """Send keystrokes to the active element.

        Args:
            text: Text to type
        """
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()

        # Get active element and send keys
        active = await loop.run_in_executor(None, lambda: driver.switch_to.active_element)
        await loop.run_in_executor(None, lambda: active.send_keys(text))

    async def clear_text(self) -> None:
        """Clear text from the active element."""
        driver = self._ensure_connected()
        loop = asyncio.get_event_loop()

        active = await loop.run_in_executor(None, lambda: driver.switch_to.active_element)
        await loop.run_in_executor(None, lambda: active.clear())
