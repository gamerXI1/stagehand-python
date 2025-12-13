"""Unit tests for MobileAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from stagehand.agent.mobile_agent import MobileAgent, create_mobile_agent
from stagehand.types.mobile import (
    DEVICE_PROFILES,
    MobileDeviceProfile,
    MobilePlatform,
)


class TestMobileAgentInit:
    """Tests for MobileAgent initialization."""

    def test_default_device_profile(self):
        agent = MobileAgent()
        assert agent.device_profile.name == "iPhone 15 Pro"
        assert agent.platform == MobilePlatform.IOS

    def test_with_device_profile_key(self):
        agent = MobileAgent(device_profile="pixel_8")
        assert agent.device_profile.name == "Pixel 8"
        assert agent.platform == MobilePlatform.ANDROID

    def test_with_custom_profile(self):
        custom = MobileDeviceProfile(
            name="Custom Device",
            platform=MobilePlatform.ANDROID,
            viewport_width=400,
            viewport_height=800,
        )
        agent = MobileAgent(custom_profile=custom)
        assert agent.device_profile.name == "Custom Device"

    def test_custom_profile_overrides_key(self):
        custom = MobileDeviceProfile(
            name="Custom",
            platform=MobilePlatform.ANDROID,
            viewport_width=400,
            viewport_height=800,
        )
        agent = MobileAgent(device_profile="iphone_15_pro", custom_profile=custom)
        # Custom profile should take precedence
        assert agent.device_profile.name == "Custom"

    def test_default_appium_url(self):
        agent = MobileAgent()
        assert agent.appium_url == "http://localhost:4723"

    def test_custom_appium_url(self):
        agent = MobileAgent(appium_url="http://remote:4723")
        assert agent.appium_url == "http://remote:4723"

    def test_default_max_steps(self):
        agent = MobileAgent()
        assert agent.max_steps == 20

    def test_custom_max_steps(self):
        agent = MobileAgent(max_steps=50)
        assert agent.max_steps == 50

    def test_not_connected_initially(self):
        agent = MobileAgent()
        assert agent.is_connected is False


class TestMobileAgentConnect:
    """Tests for MobileAgent connect/disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        agent = MobileAgent()
        # Should not raise
        await agent.disconnect()
        assert agent.is_connected is False

    @pytest.mark.asyncio
    async def test_execute_raises_when_not_connected(self):
        agent = MobileAgent()
        with pytest.raises(RuntimeError) as exc_info:
            await agent.execute("Do something")
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_screenshot_raises_when_not_connected(self):
        agent = MobileAgent()
        with pytest.raises(RuntimeError) as exc_info:
            await agent.screenshot()
        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_launch_app_raises_when_not_connected(self):
        agent = MobileAgent()
        with pytest.raises(RuntimeError) as exc_info:
            await agent.launch_app("com.example.app")
        assert "Not connected" in str(exc_info.value)


class TestMobileAgentHelpers:
    """Tests for MobileAgent helper methods."""

    def test_platform_property_ios(self):
        agent = MobileAgent(device_profile="iphone_15_pro")
        assert agent.platform == MobilePlatform.IOS

    def test_platform_property_android(self):
        agent = MobileAgent(device_profile="pixel_8")
        assert agent.platform == MobilePlatform.ANDROID


class TestCreateMobileAgent:
    """Tests for create_mobile_agent factory function."""

    def test_creates_agent_with_device(self):
        agent = create_mobile_agent(device="pixel_8")
        assert agent.device_profile.name == "Pixel 8"

    def test_creates_agent_with_appium_url(self):
        agent = create_mobile_agent(appium_url="http://custom:4723")
        assert agent.appium_url == "http://custom:4723"

    def test_creates_agent_with_api_key(self):
        agent = create_mobile_agent(api_key="test-key")
        assert agent.api_key == "test-key"


class TestMobileAgentContextManager:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_entry(self):
        async with MobileAgent() as agent:
            assert agent is not None
            assert isinstance(agent, MobileAgent)

    @pytest.mark.asyncio
    async def test_context_manager_disconnect_on_exit(self):
        agent = MobileAgent()
        async with agent:
            pass
        # Agent should be disconnected after exiting context
        assert agent.is_connected is False
