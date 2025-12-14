"""Unit tests for MobileNavigationHandler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from stagehand.handlers.mobile_navigation_handler import MobileNavigationHandler
from stagehand.types.agent import (
    AgentAction,
    DoubleTapAction,
    LongPressAction,
    PinchAction,
    SwipeAction,
    TapAction,
    TypeAction,
    WaitAction,
    FunctionAction,
    FunctionArguments,
)


@pytest.fixture
def mock_appium_client():
    """Create a mock AppiumClient."""
    client = MagicMock()
    client.viewport_width = 393
    client.viewport_height = 852
    client.get_screenshot_base64 = AsyncMock(return_value="base64screenshot")
    client.create_touch_action = MagicMock(return_value=(MagicMock(), MagicMock()))
    client.execute_touch_action = AsyncMock()
    client.send_keys = AsyncMock()
    client.press_back = AsyncMock()
    client.press_home = AsyncMock()
    client.open_url = AsyncMock()
    client.launch_app = AsyncMock()
    client.hide_keyboard = AsyncMock()
    client._ensure_connected = MagicMock(return_value=MagicMock())
    return client


@pytest.fixture
def handler(mock_appium_client):
    """Create MobileNavigationHandler with mock client."""
    return MobileNavigationHandler(
        appium_client=mock_appium_client,
        logger=None,
    )


class TestCoordinateNormalization:
    """Tests for coordinate normalization.

    Uses formula: pixel = grid * (viewport - 1) / 1000
    This maps 0-1000 grid to 0-(viewport-1) pixels, ensuring max grid
    coordinate maps to max valid pixel (not off-screen).
    """

    def test_normalize_x(self, handler):
        # 500 on 1000-grid should be close to half of viewport width
        result = handler.normalize_x(500)
        assert result == 196  # 500 * 392 / 1000 = 196

    def test_normalize_y(self, handler):
        # 500 on 1000-grid should be close to half of viewport height
        result = handler.normalize_y(500)
        assert result == 425  # 500 * 851 / 1000 = 425.5 -> 425

    def test_normalize_coordinates(self, handler):
        x, y = handler.normalize_coordinates(250, 750)
        assert x == 98  # 250 * 392 / 1000 = 98
        assert y == 638  # 750 * 851 / 1000 = 638.25 -> 638

    def test_normalize_zero(self, handler):
        x, y = handler.normalize_coordinates(0, 0)
        assert x == 0
        assert y == 0

    def test_normalize_max(self, handler):
        # Max grid (1000) should map to max valid pixel (viewport - 1)
        x, y = handler.normalize_coordinates(1000, 1000)
        assert x == 392  # 1000 * 392 / 1000 = 392 (max valid pixel)
        assert y == 851  # 1000 * 851 / 1000 = 851 (max valid pixel)

    def test_normalize_clamps_negative(self, handler):
        # Negative coordinates should clamp to 0
        x, y = handler.normalize_coordinates(-100, -50)
        assert x == 0
        assert y == 0

    def test_normalize_clamps_overflow(self, handler):
        # Coordinates > 1000 should clamp to max valid pixel
        x, y = handler.normalize_coordinates(1500, 2000)
        assert x == 392
        assert y == 851


class TestTapAction:
    """Tests for tap action execution."""

    @pytest.mark.asyncio
    async def test_perform_tap(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="tap",
            action=TapAction(type="tap", x=500, y=500),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.execute_touch_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_tap_with_duration(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="tap",
            action=TapAction(type="tap", x=500, y=500, duration_ms=100),
        )
        result = await handler.perform_action(action)
        assert result.success is True


class TestDoubleTapAction:
    """Tests for double tap action execution."""

    @pytest.mark.asyncio
    async def test_perform_double_tap(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="double_tap",
            action=DoubleTapAction(type="double_tap", x=500, y=500),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.execute_touch_action.assert_called_once()


class TestLongPressAction:
    """Tests for long press action execution."""

    @pytest.mark.asyncio
    async def test_perform_long_press(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="long_press",
            action=LongPressAction(type="long_press", x=500, y=500, duration_ms=1000),
        )
        result = await handler.perform_action(action)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_perform_long_press_default_duration(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="long_press",
            action=LongPressAction(type="long_press", x=500, y=500),
        )
        result = await handler.perform_action(action)
        assert result.success is True


class TestSwipeAction:
    """Tests for swipe action execution."""

    @pytest.mark.asyncio
    async def test_perform_swipe(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="swipe",
            action=SwipeAction(
                type="swipe",
                start_x=500,
                start_y=800,
                end_x=500,
                end_y=200,
                duration_ms=300,
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.execute_touch_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_horizontal_swipe(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="swipe",
            action=SwipeAction(
                type="swipe",
                start_x=800,
                start_y=500,
                end_x=200,
                end_y=500,
                duration_ms=200,
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True


class TestTypeAction:
    """Tests for type action execution."""

    @pytest.mark.asyncio
    async def test_perform_type(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="type",
            action=TypeAction(type="type", text="Hello World"),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.send_keys.assert_called_with("Hello World")

    @pytest.mark.asyncio
    async def test_perform_type_with_coordinates(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="type",
            action=TypeAction(type="type", text="Test", x=500, y=500),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.execute_touch_action.assert_called()
        mock_appium_client.send_keys.assert_called_with("Test")

    @pytest.mark.asyncio
    async def test_perform_type_with_enter(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="type",
            action=TypeAction(type="type", text="Search", press_enter_after=True),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        assert mock_appium_client.send_keys.call_count == 2


class TestWaitAction:
    """Tests for wait action execution."""

    @pytest.mark.asyncio
    async def test_perform_wait(self, handler):
        action = AgentAction(
            action_type="wait",
            action=WaitAction(type="wait", milliseconds=100),
        )
        result = await handler.perform_action(action)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_perform_wait_default(self, handler):
        action = AgentAction(
            action_type="wait",
            action=WaitAction(type="wait"),
        )
        result = await handler.perform_action(action)
        assert result.success is True


class TestFunctionActions:
    """Tests for function action execution."""

    @pytest.mark.asyncio
    async def test_perform_goto(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="function",
            action=FunctionAction(
                type="function",
                name="goto",
                arguments=FunctionArguments(url="https://example.com"),
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.open_url.assert_called_with("https://example.com")

    @pytest.mark.asyncio
    async def test_perform_navigate_back(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="function",
            action=FunctionAction(
                type="function",
                name="navigate_back",
                arguments=None,
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.press_back.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_go_home(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="function",
            action=FunctionAction(
                type="function",
                name="go_home",
                arguments=None,
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.press_home.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_hide_keyboard(self, handler, mock_appium_client):
        action = AgentAction(
            action_type="function",
            action=FunctionAction(
                type="function",
                name="hide_keyboard",
                arguments=None,
            ),
        )
        result = await handler.perform_action(action)
        assert result.success is True
        mock_appium_client.hide_keyboard.assert_called_once()


class TestUnsupportedActions:
    """Tests for unsupported action handling."""

    @pytest.mark.asyncio
    async def test_unsupported_action_type(self, handler):
        action = AgentAction(
            action_type="unknown_action",
            action=TapAction(type="tap", x=0, y=0),
        )
        result = await handler.perform_action(action)
        assert result.success is False
        assert "Unsupported action type" in result.error


class TestScreenshot:
    """Tests for screenshot capture."""

    @pytest.mark.asyncio
    async def test_get_screenshot(self, handler, mock_appium_client):
        screenshot = await handler.get_screenshot_base64()
        assert screenshot == "base64screenshot"
        mock_appium_client.get_screenshot_base64.assert_called_once()
