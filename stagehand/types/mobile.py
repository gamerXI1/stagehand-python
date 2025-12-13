"""Mobile device types, profiles, and Appium configuration models."""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MobilePlatform(str, Enum):
    """Supported mobile platforms."""

    IOS = "iOS"
    ANDROID = "Android"


class MobileDeviceProfile(BaseModel):
    """Device profile for mobile emulation and Appium configuration."""

    name: str
    platform: MobilePlatform
    viewport_width: int
    viewport_height: int
    device_scale_factor: float = 1.0
    user_agent: Optional[str] = None
    platform_version: Optional[str] = None


# Pre-configured device profiles for common devices
DEVICE_PROFILES: dict[str, MobileDeviceProfile] = {
    # iOS Devices
    "iphone_15_pro": MobileDeviceProfile(
        name="iPhone 15 Pro",
        platform=MobilePlatform.IOS,
        viewport_width=393,
        viewport_height=852,
        device_scale_factor=3.0,
        platform_version="17.0",
    ),
    "iphone_15": MobileDeviceProfile(
        name="iPhone 15",
        platform=MobilePlatform.IOS,
        viewport_width=393,
        viewport_height=852,
        device_scale_factor=3.0,
        platform_version="17.0",
    ),
    "iphone_se": MobileDeviceProfile(
        name="iPhone SE",
        platform=MobilePlatform.IOS,
        viewport_width=375,
        viewport_height=667,
        device_scale_factor=2.0,
        platform_version="17.0",
    ),
    "iphone_14_pro_max": MobileDeviceProfile(
        name="iPhone 14 Pro Max",
        platform=MobilePlatform.IOS,
        viewport_width=430,
        viewport_height=932,
        device_scale_factor=3.0,
        platform_version="16.0",
    ),
    "ipad_pro_12_9": MobileDeviceProfile(
        name="iPad Pro 12.9",
        platform=MobilePlatform.IOS,
        viewport_width=1024,
        viewport_height=1366,
        device_scale_factor=2.0,
        platform_version="17.0",
    ),
    "ipad_air": MobileDeviceProfile(
        name="iPad Air",
        platform=MobilePlatform.IOS,
        viewport_width=820,
        viewport_height=1180,
        device_scale_factor=2.0,
        platform_version="17.0",
    ),
    # Android Devices
    "pixel_8": MobileDeviceProfile(
        name="Pixel 8",
        platform=MobilePlatform.ANDROID,
        viewport_width=412,
        viewport_height=915,
        device_scale_factor=2.625,
        platform_version="14",
    ),
    "pixel_8_pro": MobileDeviceProfile(
        name="Pixel 8 Pro",
        platform=MobilePlatform.ANDROID,
        viewport_width=448,
        viewport_height=998,
        device_scale_factor=2.625,
        platform_version="14",
    ),
    "pixel_7": MobileDeviceProfile(
        name="Pixel 7",
        platform=MobilePlatform.ANDROID,
        viewport_width=412,
        viewport_height=915,
        device_scale_factor=2.625,
        platform_version="13",
    ),
    "samsung_galaxy_s24": MobileDeviceProfile(
        name="Samsung Galaxy S24",
        platform=MobilePlatform.ANDROID,
        viewport_width=360,
        viewport_height=780,
        device_scale_factor=3.0,
        platform_version="14",
    ),
    "samsung_galaxy_s24_ultra": MobileDeviceProfile(
        name="Samsung Galaxy S24 Ultra",
        platform=MobilePlatform.ANDROID,
        viewport_width=384,
        viewport_height=824,
        device_scale_factor=3.0,
        platform_version="14",
    ),
    "galaxy_tab_s9": MobileDeviceProfile(
        name="Galaxy Tab S9",
        platform=MobilePlatform.ANDROID,
        viewport_width=800,
        viewport_height=1280,
        device_scale_factor=2.0,
        platform_version="14",
    ),
}


class AppiumCapabilities(BaseModel):
    """Appium desired capabilities for device connection."""

    platform_name: MobilePlatform = Field(alias="platformName")
    platform_version: Optional[str] = Field(default=None, alias="platformVersion")
    device_name: str = Field(alias="deviceName")
    automation_name: str = Field(alias="automationName")
    udid: Optional[str] = None
    no_reset: bool = Field(default=False, alias="noReset")
    full_reset: bool = Field(default=False, alias="fullReset")
    new_command_timeout: int = Field(default=300, alias="newCommandTimeout")

    # iOS-specific
    bundle_id: Optional[str] = Field(default=None, alias="bundleId")
    xcode_org_id: Optional[str] = Field(default=None, alias="xcodeOrgId")
    xcode_signing_id: Optional[str] = Field(default=None, alias="xcodeSigningId")

    # Android-specific
    app_package: Optional[str] = Field(default=None, alias="appPackage")
    app_activity: Optional[str] = Field(default=None, alias="appActivity")

    # Browser automation
    browser_name: Optional[str] = Field(default=None, alias="browserName")

    # App path (for installing apps)
    app: Optional[str] = None

    class Config:
        populate_by_name = True


class IOSCapabilities(AppiumCapabilities):
    """iOS-specific Appium capabilities."""

    platform_name: Literal[MobilePlatform.IOS] = Field(
        default=MobilePlatform.IOS, alias="platformName"
    )
    automation_name: str = Field(default="XCUITest", alias="automationName")
    wda_local_port: Optional[int] = Field(default=None, alias="wdaLocalPort")
    webkit_debug_proxy_port: Optional[int] = Field(
        default=None, alias="webkitDebugProxyPort"
    )
    use_new_wda: bool = Field(default=False, alias="useNewWDA")
    show_xcode_log: bool = Field(default=False, alias="showXcodeLog")


class AndroidCapabilities(AppiumCapabilities):
    """Android-specific Appium capabilities."""

    platform_name: Literal[MobilePlatform.ANDROID] = Field(
        default=MobilePlatform.ANDROID, alias="platformName"
    )
    automation_name: str = Field(default="UiAutomator2", alias="automationName")
    auto_grant_permissions: bool = Field(default=True, alias="autoGrantPermissions")
    chrome_driver_executable: Optional[str] = Field(
        default=None, alias="chromedriverExecutable"
    )
    native_web_screenshot: bool = Field(default=True, alias="nativeWebScreenshot")
    android_install_timeout: int = Field(default=90000, alias="androidInstallTimeout")


class MobileSessionConfig(BaseModel):
    """Configuration for establishing a mobile Appium session."""

    appium_server_url: str = "http://localhost:4723"
    capabilities: AppiumCapabilities
    implicit_wait_ms: int = 10000
    command_timeout_ms: int = 60000


class MobileAgentConfig(BaseModel):
    """Configuration for the MobileAgent."""

    device_profile: Optional[str] = None  # Key from DEVICE_PROFILES
    custom_profile: Optional[MobileDeviceProfile] = None
    session_config: Optional[MobileSessionConfig] = None
    model: str = "gemini-2.5-computer-use-preview-10-2025"
    instructions: Optional[str] = None
    max_steps: int = 20
    wait_between_actions_ms: int = 500
    options: Optional[dict[str, Any]] = None


def get_device_profile(device_key: str) -> MobileDeviceProfile:
    """Get a device profile by key.

    Args:
        device_key: Key from DEVICE_PROFILES (e.g., 'iphone_15_pro', 'pixel_8')

    Returns:
        MobileDeviceProfile for the specified device

    Raises:
        ValueError: If device_key is not found
    """
    if device_key not in DEVICE_PROFILES:
        available = ", ".join(DEVICE_PROFILES.keys())
        raise ValueError(
            f"Unknown device profile: {device_key}. Available profiles: {available}"
        )
    return DEVICE_PROFILES[device_key]


def create_ios_capabilities(
    device_name: str,
    bundle_id: Optional[str] = None,
    browser_name: Optional[str] = None,
    platform_version: Optional[str] = None,
    udid: Optional[str] = None,
) -> IOSCapabilities:
    """Create iOS Appium capabilities.

    Args:
        device_name: Name of the iOS device or simulator
        bundle_id: Bundle ID for native app (e.g., 'com.apple.mobilesafari')
        browser_name: Browser name for web testing ('Safari')
        platform_version: iOS version (e.g., '17.0')
        udid: Device UDID for real devices

    Returns:
        IOSCapabilities configured for the device
    """
    return IOSCapabilities(
        deviceName=device_name,
        bundleId=bundle_id,
        browserName=browser_name,
        platformVersion=platform_version,
        udid=udid,
    )


def create_android_capabilities(
    device_name: str,
    app_package: Optional[str] = None,
    app_activity: Optional[str] = None,
    browser_name: Optional[str] = None,
    platform_version: Optional[str] = None,
    udid: Optional[str] = None,
) -> AndroidCapabilities:
    """Create Android Appium capabilities.

    Args:
        device_name: Name of the Android device or emulator
        app_package: Package name for native app (e.g., 'com.android.chrome')
        app_activity: Activity to launch (e.g., 'com.google.android.apps.chrome.Main')
        browser_name: Browser name for web testing ('Chrome')
        platform_version: Android version (e.g., '14')
        udid: Device serial for real devices

    Returns:
        AndroidCapabilities configured for the device
    """
    return AndroidCapabilities(
        deviceName=device_name,
        appPackage=app_package,
        appActivity=app_activity,
        browserName=browser_name,
        platformVersion=platform_version,
        udid=udid,
    )
