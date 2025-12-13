"""Unit tests for mobile types and device profiles."""

import pytest

from stagehand.types.mobile import (
    AndroidCapabilities,
    create_android_capabilities,
    create_ios_capabilities,
    DEVICE_PROFILES,
    get_device_profile,
    IOSCapabilities,
    MobileAgentConfig,
    MobileDeviceProfile,
    MobilePlatform,
    MobileSessionConfig,
)


class TestMobilePlatform:
    """Tests for MobilePlatform enum."""

    def test_ios_value(self):
        assert MobilePlatform.IOS.value == "iOS"

    def test_android_value(self):
        assert MobilePlatform.ANDROID.value == "Android"


class TestMobileDeviceProfile:
    """Tests for MobileDeviceProfile model."""

    def test_create_profile(self):
        profile = MobileDeviceProfile(
            name="Test Device",
            platform=MobilePlatform.IOS,
            viewport_width=375,
            viewport_height=667,
        )
        assert profile.name == "Test Device"
        assert profile.platform == MobilePlatform.IOS
        assert profile.viewport_width == 375
        assert profile.viewport_height == 667
        assert profile.device_scale_factor == 1.0

    def test_profile_with_scale_factor(self):
        profile = MobileDeviceProfile(
            name="Retina Device",
            platform=MobilePlatform.IOS,
            viewport_width=390,
            viewport_height=844,
            device_scale_factor=3.0,
        )
        assert profile.device_scale_factor == 3.0


class TestDeviceProfiles:
    """Tests for pre-configured device profiles."""

    def test_iphone_15_pro_exists(self):
        assert "iphone_15_pro" in DEVICE_PROFILES
        profile = DEVICE_PROFILES["iphone_15_pro"]
        assert profile.platform == MobilePlatform.IOS
        assert profile.viewport_width == 393
        assert profile.viewport_height == 852

    def test_pixel_8_exists(self):
        assert "pixel_8" in DEVICE_PROFILES
        profile = DEVICE_PROFILES["pixel_8"]
        assert profile.platform == MobilePlatform.ANDROID
        assert profile.viewport_width == 412
        assert profile.viewport_height == 915

    def test_ipad_pro_exists(self):
        assert "ipad_pro_12_9" in DEVICE_PROFILES
        profile = DEVICE_PROFILES["ipad_pro_12_9"]
        assert profile.platform == MobilePlatform.IOS

    def test_samsung_galaxy_exists(self):
        assert "samsung_galaxy_s24" in DEVICE_PROFILES
        profile = DEVICE_PROFILES["samsung_galaxy_s24"]
        assert profile.platform == MobilePlatform.ANDROID

    def test_get_device_profile_valid(self):
        profile = get_device_profile("iphone_15_pro")
        assert profile.name == "iPhone 15 Pro"

    def test_get_device_profile_invalid(self):
        with pytest.raises(ValueError) as exc_info:
            get_device_profile("nonexistent_device")
        assert "Unknown device profile" in str(exc_info.value)


class TestIOSCapabilities:
    """Tests for iOS Appium capabilities."""

    def test_default_automation_name(self):
        caps = IOSCapabilities(deviceName="iPhone")
        assert caps.automation_name == "XCUITest"
        assert caps.platform_name == MobilePlatform.IOS

    def test_with_bundle_id(self):
        caps = IOSCapabilities(
            deviceName="iPhone 15",
            bundleId="com.apple.mobilesafari",
        )
        assert caps.bundle_id == "com.apple.mobilesafari"

    def test_with_browser(self):
        caps = IOSCapabilities(
            deviceName="iPhone 15",
            browserName="Safari",
        )
        assert caps.browser_name == "Safari"

    def test_create_ios_capabilities_helper(self):
        caps = create_ios_capabilities(
            device_name="iPhone 15 Pro",
            bundle_id="com.example.app",
            platform_version="17.0",
        )
        assert caps.device_name == "iPhone 15 Pro"
        assert caps.bundle_id == "com.example.app"
        assert caps.platform_version == "17.0"


class TestAndroidCapabilities:
    """Tests for Android Appium capabilities."""

    def test_default_automation_name(self):
        caps = AndroidCapabilities(deviceName="Pixel")
        assert caps.automation_name == "UiAutomator2"
        assert caps.platform_name == MobilePlatform.ANDROID

    def test_with_app_package(self):
        caps = AndroidCapabilities(
            deviceName="Pixel 8",
            appPackage="com.android.chrome",
            appActivity="com.google.android.apps.chrome.Main",
        )
        assert caps.app_package == "com.android.chrome"
        assert caps.app_activity == "com.google.android.apps.chrome.Main"

    def test_auto_grant_permissions_default(self):
        caps = AndroidCapabilities(deviceName="Pixel")
        assert caps.auto_grant_permissions is True

    def test_create_android_capabilities_helper(self):
        caps = create_android_capabilities(
            device_name="Pixel 8",
            app_package="com.example.app",
            platform_version="14",
        )
        assert caps.device_name == "Pixel 8"
        assert caps.app_package == "com.example.app"
        assert caps.platform_version == "14"


class TestMobileSessionConfig:
    """Tests for MobileSessionConfig model."""

    def test_default_appium_url(self):
        caps = IOSCapabilities(deviceName="iPhone")
        config = MobileSessionConfig(capabilities=caps)
        assert config.appium_server_url == "http://localhost:4723"

    def test_custom_appium_url(self):
        caps = IOSCapabilities(deviceName="iPhone")
        config = MobileSessionConfig(
            appium_server_url="http://remote:4723",
            capabilities=caps,
        )
        assert config.appium_server_url == "http://remote:4723"

    def test_default_timeouts(self):
        caps = IOSCapabilities(deviceName="iPhone")
        config = MobileSessionConfig(capabilities=caps)
        assert config.implicit_wait_ms == 10000
        assert config.command_timeout_ms == 60000


class TestMobileAgentConfig:
    """Tests for MobileAgentConfig model."""

    def test_default_values(self):
        config = MobileAgentConfig()
        assert config.model == "gemini-2.5-computer-use-preview-10-2025"
        assert config.max_steps == 20
        assert config.wait_between_actions_ms == 500

    def test_with_device_profile(self):
        config = MobileAgentConfig(device_profile="iphone_15_pro")
        assert config.device_profile == "iphone_15_pro"

    def test_with_custom_profile(self):
        custom = MobileDeviceProfile(
            name="Custom",
            platform=MobilePlatform.IOS,
            viewport_width=400,
            viewport_height=800,
        )
        config = MobileAgentConfig(custom_profile=custom)
        assert config.custom_profile.name == "Custom"
