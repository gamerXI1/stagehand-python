"""Mobile agent for automating iOS and Android devices."""

import functools
from typing import Any, Callable, Optional, TypeVar

# Type variable for decorator return type preservation
F = TypeVar("F", bound=Callable[..., Any])

from ..handlers.mobile_navigation_handler import MobileNavigationHandler
from ..mobile.appium_client import AppiumClient
from ..types.agent import AgentConfig, AgentExecuteOptions, AgentResult
from ..types.mobile import (
    AndroidCapabilities,
    AppiumCapabilities,
    DEVICE_PROFILES,
    get_device_profile,
    IOSCapabilities,
    MobileAgentConfig,
    MobileDeviceProfile,
    MobilePlatform,
    MobileSessionConfig,
)
from .google_mobile_cua import GoogleMobileCUAClient


def _require_connection(method: F) -> F:
    """Decorator to ensure connection before method execution."""

    @functools.wraps(method)
    async def wrapper(self: "MobileAgent", *args: Any, **kwargs: Any) -> Any:
        if not self._connected or not self.appium_client:
            raise RuntimeError("Not connected. Call connect() first.")
        return await method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class MobileAgent:
    """Agent for automating mobile devices via Appium and Google CUA.

    Supports both iOS and Android devices for native app and mobile web automation.

    Example usage:
        ```python
        agent = MobileAgent(
            device_profile="iphone_15_pro",
            appium_url="http://localhost:4723",
        )
        await agent.connect(
            device_name="iPhone 15 Pro",
            bundle_id="com.apple.mobilesafari",
        )
        result = await agent.execute("Search for 'weather' on Google")
        await agent.disconnect()
        ```
    """

    def __init__(
        self,
        device_profile: Optional[str] = None,
        custom_profile: Optional[MobileDeviceProfile] = None,
        appium_url: str = "http://localhost:4723",
        model: str = "gemini-2.5-computer-use-preview-10-2025",
        instructions: Optional[str] = None,
        api_key: Optional[str] = None,
        max_steps: int = 20,
        logger: Optional[Any] = None,
    ):
        """Initialize MobileAgent.

        Args:
            device_profile: Key from DEVICE_PROFILES (e.g., 'iphone_15_pro', 'pixel_8')
            custom_profile: Custom MobileDeviceProfile (overrides device_profile)
            appium_url: Appium server URL
            model: Gemini model name for CUA
            instructions: Custom system instructions
            api_key: Gemini API key (or set GEMINI_API_KEY env var)
            max_steps: Maximum steps per task execution
            logger: Logger instance
        """
        self.appium_url = appium_url
        self.model = model
        self.instructions = instructions
        self.api_key = api_key
        self.max_steps = max_steps
        self.logger = logger

        # Resolve device profile
        if custom_profile:
            self.device_profile = custom_profile
        elif device_profile:
            self.device_profile = get_device_profile(device_profile)
        else:
            # Default to iPhone 15 Pro
            self.device_profile = DEVICE_PROFILES["iphone_15_pro"]

        # Components (initialized on connect)
        self.appium_client: Optional[AppiumClient] = None
        self.navigation_handler: Optional[MobileNavigationHandler] = None
        self.cua_client: Optional[GoogleMobileCUAClient] = None
        self._connected = False

    def _log(self, level: str, message: str, category: str = "mobile_agent") -> None:
        """Log a message if logger is available."""
        if self.logger:
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(message, category=category)

    @property
    def is_connected(self) -> bool:
        """Check if agent is connected to a device."""
        return self._connected

    @property
    def platform(self) -> MobilePlatform:
        """Get the current device platform."""
        return self.device_profile.platform

    async def connect(
        self,
        device_name: str,
        # iOS options
        bundle_id: Optional[str] = None,
        udid: Optional[str] = None,
        # Android options
        app_package: Optional[str] = None,
        app_activity: Optional[str] = None,
        # Browser options
        browser_name: Optional[str] = None,
        # Advanced options
        capabilities: Optional[AppiumCapabilities] = None,
        no_reset: bool = True,
    ) -> None:
        """Connect to a mobile device via Appium.

        Args:
            device_name: Device name (e.g., 'iPhone 15 Pro', 'Pixel 8')
            bundle_id: iOS app bundle ID (e.g., 'com.apple.mobilesafari')
            udid: Device UDID for real iOS devices
            app_package: Android app package (e.g., 'com.android.chrome')
            app_activity: Android app activity to launch
            browser_name: Browser for web testing ('Safari' or 'Chrome')
            capabilities: Pre-built capabilities (overrides other options)
            no_reset: Don't reset app state between sessions
        """
        if self._connected:
            self._log("warning", "Already connected. Call disconnect() first.")
            return

        self._log("info", f"Connecting to {device_name} ({self.platform.value})")

        # Build capabilities if not provided
        if capabilities is None:
            if self.platform == MobilePlatform.IOS:
                capabilities = IOSCapabilities(
                    deviceName=device_name,
                    platformVersion=self.device_profile.platform_version,
                    bundleId=bundle_id,
                    browserName=browser_name,
                    udid=udid,
                    noReset=no_reset,
                )
            else:
                capabilities = AndroidCapabilities(
                    deviceName=device_name,
                    platformVersion=self.device_profile.platform_version,
                    appPackage=app_package,
                    appActivity=app_activity,
                    browserName=browser_name,
                    udid=udid,
                    noReset=no_reset,
                )

        # Create session config
        session_config = MobileSessionConfig(
            appium_server_url=self.appium_url,
            capabilities=capabilities,
        )

        # Initialize Appium client
        self.appium_client = AppiumClient(
            session_config=session_config,
            logger=self.logger,
        )

        # Connect to device
        await self.appium_client.connect()

        # Get actual viewport size from device
        viewport = await self.appium_client.get_viewport_size()

        # Initialize navigation handler
        self.navigation_handler = MobileNavigationHandler(
            appium_client=self.appium_client,
            logger=self.logger,
        )

        # Initialize CUA client
        agent_config = AgentConfig(
            model=self.model,
            instructions=self.instructions,
            max_steps=self.max_steps,
            options={"apiKey": self.api_key} if self.api_key else None,
        )

        self.cua_client = GoogleMobileCUAClient(
            model=self.model,
            instructions=self.instructions,
            config=agent_config,
            logger=self.logger,
            handler=self.navigation_handler,
            viewport_width=viewport["width"],
            viewport_height=viewport["height"],
        )

        self._connected = True
        self._log("info", f"Connected. Viewport: {viewport['width']}x{viewport['height']}")

    async def disconnect(self) -> None:
        """Disconnect from the mobile device and clean up resources."""
        if not self._connected:
            self._log("debug", "Not connected")
            return

        self._log("info", "Disconnecting from device")

        if self.appium_client:
            await self.appium_client.disconnect()

        self.appium_client = None
        self.navigation_handler = None
        self.cua_client = None
        self._connected = False

        self._log("info", "Disconnected")

    async def execute(
        self,
        instruction: str,
        max_steps: Optional[int] = None,
        context: Optional[str] = None,
    ) -> AgentResult:
        """Execute a task on the mobile device.

        Args:
            instruction: Natural language instruction for the task
            max_steps: Override default max_steps
            context: Additional context for the agent

        Returns:
            AgentResult with actions taken and completion status

        Raises:
            RuntimeError: If not connected to a device
        """
        if not self._connected or not self.cua_client:
            raise RuntimeError("Not connected. Call connect() first.")

        steps = max_steps or self.max_steps

        # Add context to instruction if provided
        full_instruction = instruction
        if context:
            full_instruction = f"{context}\n\nTask: {instruction}"

        self._log("info", f"Executing: {instruction}")

        options = AgentExecuteOptions(
            instruction=full_instruction,
            max_steps=steps,
        )

        result = await self.cua_client.run_task(
            instruction=full_instruction,
            max_steps=steps,
            options=options,
        )

        self._log(
            "info",
            f"Task {'completed' if result.completed else 'incomplete'}: {result.message}",
        )

        return result

    @_require_connection
    async def screenshot(self) -> str:
        """Capture a screenshot of the device.

        Returns:
            Base64 encoded PNG screenshot

        Raises:
            RuntimeError: If not connected
        """
        return await self.appium_client.get_screenshot_base64()  # type: ignore[union-attr]

    @_require_connection
    async def launch_app(self, app_id: str) -> None:
        """Launch an app by bundle ID (iOS) or package name (Android).

        Args:
            app_id: Bundle ID or package name

        Raises:
            RuntimeError: If not connected
        """
        await self.appium_client.launch_app(app_id)  # type: ignore[union-attr]

    @_require_connection
    async def open_url(self, url: str) -> None:
        """Open a URL in the mobile browser.

        Args:
            url: URL to open

        Raises:
            RuntimeError: If not connected
        """
        await self.appium_client.open_url(url)  # type: ignore[union-attr]

    @_require_connection
    async def go_home(self) -> None:
        """Press the home button.

        Raises:
            RuntimeError: If not connected
        """
        await self.appium_client.press_home()  # type: ignore[union-attr]

    @_require_connection
    async def go_back(self) -> None:
        """Press the back button.

        Raises:
            RuntimeError: If not connected
        """
        await self.appium_client.press_back()  # type: ignore[union-attr]

    @_require_connection
    async def get_orientation(self) -> str:
        """Get current device orientation.

        Returns:
            'PORTRAIT' or 'LANDSCAPE'

        Raises:
            RuntimeError: If not connected
        """
        return await self.appium_client.get_orientation()  # type: ignore[union-attr]

    @_require_connection
    async def set_orientation(self, orientation: str) -> None:
        """Set device orientation.

        Args:
            orientation: 'PORTRAIT' or 'LANDSCAPE'

        Raises:
            RuntimeError: If not connected
        """
        await self.appium_client.set_orientation(orientation)  # type: ignore[union-attr]

    @_require_connection
    async def get_page_source(self) -> str:
        """Get the current view hierarchy as XML.

        Returns:
            XML string of view hierarchy

        Raises:
            RuntimeError: If not connected
        """
        return await self.appium_client.get_page_source()  # type: ignore[union-attr]

    async def __aenter__(self) -> "MobileAgent":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures disconnect."""
        await self.disconnect()


def create_mobile_agent(
    device: str = "iphone_15_pro",
    appium_url: str = "http://localhost:4723",
    api_key: Optional[str] = None,
    **kwargs,
) -> MobileAgent:
    """Factory function to create a MobileAgent.

    Args:
        device: Device profile key (e.g., 'iphone_15_pro', 'pixel_8')
        appium_url: Appium server URL
        api_key: Gemini API key
        **kwargs: Additional MobileAgent arguments

    Returns:
        Configured MobileAgent instance
    """
    return MobileAgent(
        device_profile=device,
        appium_url=appium_url,
        api_key=api_key,
        **kwargs,
    )
