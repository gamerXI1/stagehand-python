"""Mobile navigation handler for executing touch gestures via Appium."""

import asyncio
import base64
import math
from typing import Any, Optional

from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

from ..mobile.appium_client import AppiumClient
from ..types.agent import (
    ActionExecutionResult,
    AgentAction,
    DoubleTapAction,
    LongPressAction,
    PinchAction,
    RotateAction,
    SwipeAction,
    TapAction,
    TypeAction,
    WaitAction,
    ScrollAction,
    FunctionAction,
    ScreenshotAction,
)


class MobileNavigationHandler:
    """Handles mobile navigation and touch gesture execution via Appium.

    This handler translates AgentAction objects into Appium touch gestures
    using the W3C Actions API. It supports:
    - Tap, double tap, long press
    - Swipe gestures
    - Pinch zoom (in/out)
    - Rotation gestures
    - Text input
    - Navigation (back, home, app launch)
    """

    # Google CUA uses a 1000x1000 normalized coordinate grid
    COORDINATE_GRID_SIZE = 1000

    def __init__(
        self,
        appium_client: AppiumClient,
        logger: Optional[Any] = None,
    ):
        """Initialize MobileNavigationHandler.

        Args:
            appium_client: Connected AppiumClient instance
            logger: Optional logger instance
        """
        self.appium_client = appium_client
        self.logger = logger

    def _log(self, level: str, message: str, category: str = "mobile") -> None:
        """Log a message if logger is available."""
        if self.logger:
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(message, category=category)

    def normalize_x(self, x: int) -> int:
        """Convert X coordinate from 1000-grid to device pixels.

        Args:
            x: X coordinate in 0-1000 range

        Returns:
            X coordinate in device pixels
        """
        return int(x / self.COORDINATE_GRID_SIZE * self.appium_client.viewport_width)

    def normalize_y(self, y: int) -> int:
        """Convert Y coordinate from 1000-grid to device pixels.

        Args:
            y: Y coordinate in 0-1000 range

        Returns:
            Y coordinate in device pixels
        """
        return int(y / self.COORDINATE_GRID_SIZE * self.appium_client.viewport_height)

    def normalize_coordinates(self, x: int, y: int) -> tuple[int, int]:
        """Convert coordinates from 1000-grid to device pixels.

        Args:
            x: X coordinate in 0-1000 range
            y: Y coordinate in 0-1000 range

        Returns:
            Tuple of (x, y) in device pixels
        """
        return self.normalize_x(x), self.normalize_y(y)

    async def get_screenshot_base64(self) -> str:
        """Capture device screenshot as base64 string.

        Returns:
            Base64 encoded PNG screenshot
        """
        return await self.appium_client.get_screenshot_base64()

    async def perform_action(self, action: AgentAction) -> ActionExecutionResult:
        """Execute an agent action on the mobile device.

        Args:
            action: AgentAction containing the action to perform

        Returns:
            ActionExecutionResult indicating success or failure
        """
        action_model = action.action
        action_type = action.action_type

        self._log("info", f"Performing mobile action: {action_type}")

        try:
            if action_type == "tap":
                return await self._perform_tap(action_model)

            elif action_type == "double_tap":
                return await self._perform_double_tap(action_model)

            elif action_type == "long_press":
                return await self._perform_long_press(action_model)

            elif action_type == "swipe":
                return await self._perform_swipe(action_model)

            elif action_type == "pinch":
                return await self._perform_pinch(action_model)

            elif action_type == "rotate":
                return await self._perform_rotate(action_model)

            elif action_type == "type":
                return await self._perform_type(action_model)

            elif action_type == "scroll":
                return await self._perform_scroll(action_model)

            elif action_type == "wait":
                return await self._perform_wait(action_model)

            elif action_type == "screenshot":
                return await self._perform_screenshot(action_model)

            elif action_type == "function":
                return await self._perform_function(action_model)

            # Map click actions to tap for mobile
            elif action_type == "click":
                return await self._perform_tap_from_click(action_model)

            elif action_type == "double_click":
                return await self._perform_double_tap_from_click(action_model)

            else:
                self._log("error", f"Unsupported action type: {action_type}")
                return ActionExecutionResult(
                    success=False,
                    error=f"Unsupported action type: {action_type}",
                )

        except Exception as e:
            self._log("error", f"Error executing action {action_type}: {e}")
            return ActionExecutionResult(success=False, error=str(e))

    async def _perform_tap(self, action: TapAction) -> ActionExecutionResult:
        """Execute a single tap gesture.

        Args:
            action: TapAction with coordinates

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)
        duration_ms = action.duration_ms or 50

        self._log("debug", f"Tap at ({x}, {y}) duration={duration_ms}ms")

        actions, touch = self.appium_client.create_touch_action()

        # Build tap sequence: move -> press -> pause -> release
        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(duration_ms / 1000)
        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_tap_from_click(self, action: Any) -> ActionExecutionResult:
        """Convert click action to tap for mobile.

        Args:
            action: ClickAction with coordinates

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)

        self._log("debug", f"Tap (from click) at ({x}, {y})")

        actions, touch = self.appium_client.create_touch_action()
        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(0.05)
        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_double_tap(self, action: DoubleTapAction) -> ActionExecutionResult:
        """Execute a double tap gesture.

        Args:
            action: DoubleTapAction with coordinates

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)

        self._log("debug", f"Double tap at ({x}, {y})")

        actions, touch = self.appium_client.create_touch_action()

        # First tap
        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(0.05)
        actions.pointer_action.pointer_up()

        # Brief pause between taps
        actions.pointer_action.pause(0.1)

        # Second tap
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(0.05)
        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_double_tap_from_click(self, action: Any) -> ActionExecutionResult:
        """Convert double click action to double tap for mobile.

        Args:
            action: DoubleClickAction with coordinates

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)

        self._log("debug", f"Double tap (from double_click) at ({x}, {y})")

        actions, touch = self.appium_client.create_touch_action()

        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(0.05)
        actions.pointer_action.pointer_up()
        actions.pointer_action.pause(0.1)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(0.05)
        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_long_press(self, action: LongPressAction) -> ActionExecutionResult:
        """Execute a long press gesture.

        Args:
            action: LongPressAction with coordinates and duration

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)
        duration_s = action.duration_ms / 1000

        self._log("debug", f"Long press at ({x}, {y}) for {action.duration_ms}ms")

        actions, touch = self.appium_client.create_touch_action()

        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()
        actions.pointer_action.pause(duration_s)
        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_swipe(self, action: SwipeAction) -> ActionExecutionResult:
        """Execute a swipe gesture.

        Args:
            action: SwipeAction with start/end coordinates and duration

        Returns:
            ActionExecutionResult
        """
        start_x, start_y = self.normalize_coordinates(action.start_x, action.start_y)
        end_x, end_y = self.normalize_coordinates(action.end_x, action.end_y)
        duration_s = action.duration_ms / 1000

        self._log(
            "debug",
            f"Swipe from ({start_x}, {start_y}) to ({end_x}, {end_y}) in {action.duration_ms}ms",
        )

        actions, touch = self.appium_client.create_touch_action()

        # Swipe: move to start -> press -> move to end over duration -> release
        actions.pointer_action.move_to_location(start_x, start_y)
        actions.pointer_action.pointer_down()

        # Calculate intermediate steps for smooth swipe
        steps = max(int(duration_s * 60), 10)  # ~60fps or minimum 10 steps
        step_duration = duration_s / steps

        for i in range(1, steps + 1):
            progress = i / steps
            current_x = int(start_x + (end_x - start_x) * progress)
            current_y = int(start_y + (end_y - start_y) * progress)
            actions.pointer_action.move_to_location(current_x, current_y)
            actions.pointer_action.pause(step_duration)

        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_pinch(self, action: PinchAction) -> ActionExecutionResult:
        """Execute a pinch zoom gesture using two fingers.

        Args:
            action: PinchAction with center, scale, and duration

        Returns:
            ActionExecutionResult
        """
        center_x, center_y = self.normalize_coordinates(action.center_x, action.center_y)
        scale = action.scale
        duration_ms = action.duration_ms

        # Calculate finger positions
        # For pinch in (scale < 1): fingers start apart, move together
        # For pinch out (scale > 1): fingers start together, move apart
        base_distance = 100  # Base distance in pixels

        if scale < 1.0:
            # Pinch in: start far, end close
            start_distance = base_distance
            end_distance = int(base_distance * scale)
        else:
            # Pinch out: start close, end far
            start_distance = int(base_distance / scale)
            end_distance = base_distance

        self._log(
            "debug",
            f"Pinch at ({center_x}, {center_y}) scale={scale} duration={duration_ms}ms",
        )

        driver = self.appium_client._ensure_connected()

        # Create two separate touch inputs for multi-touch
        finger1 = PointerInput(interaction.POINTER_TOUCH, "finger1")
        finger2 = PointerInput(interaction.POINTER_TOUCH, "finger2")

        # Calculate start and end positions for both fingers (horizontal pinch)
        f1_start_x = center_x - start_distance
        f1_end_x = center_x - end_distance
        f2_start_x = center_x + start_distance
        f2_end_x = center_x + end_distance

        # Build finger 1 action sequence
        finger1_actions = finger1.create_pointer_move(
            duration=0, x=f1_start_x, y=center_y, origin="viewport"
        )
        finger1.create_pointer_down(button=0)
        finger1.create_pointer_move(
            duration=duration_ms, x=f1_end_x, y=center_y, origin="viewport"
        )
        finger1.create_pointer_up(button=0)

        # Build finger 2 action sequence
        finger2.create_pointer_move(
            duration=0, x=f2_start_x, y=center_y, origin="viewport"
        )
        finger2.create_pointer_down(button=0)
        finger2.create_pointer_move(
            duration=duration_ms, x=f2_end_x, y=center_y, origin="viewport"
        )
        finger2.create_pointer_up(button=0)

        # Execute multi-touch action
        actions = ActionBuilder(driver)
        actions.add_action(finger1)
        actions.add_action(finger2)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, actions.perform)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_rotate(self, action: RotateAction) -> ActionExecutionResult:
        """Execute a rotation gesture using two fingers.

        Args:
            action: RotateAction with center, angle, and duration

        Returns:
            ActionExecutionResult
        """
        center_x, center_y = self.normalize_coordinates(action.center_x, action.center_y)
        angle_rad = math.radians(action.angle)
        duration_ms = action.duration_ms
        radius = 80  # Fixed radius for rotation

        self._log(
            "debug",
            f"Rotate at ({center_x}, {center_y}) angle={action.angle}° duration={duration_ms}ms",
        )

        driver = self.appium_client._ensure_connected()

        # Create two touch inputs for rotation
        finger1 = PointerInput(interaction.POINTER_TOUCH, "finger1")
        finger2 = PointerInput(interaction.POINTER_TOUCH, "finger2")

        # Starting positions: opposite sides of center
        f1_start_angle = 0
        f2_start_angle = math.pi  # 180 degrees opposite

        # Calculate start positions
        f1_start_x = int(center_x + radius * math.cos(f1_start_angle))
        f1_start_y = int(center_y + radius * math.sin(f1_start_angle))
        f2_start_x = int(center_x + radius * math.cos(f2_start_angle))
        f2_start_y = int(center_y + radius * math.sin(f2_start_angle))

        # Calculate end positions
        f1_end_x = int(center_x + radius * math.cos(f1_start_angle + angle_rad))
        f1_end_y = int(center_y + radius * math.sin(f1_start_angle + angle_rad))
        f2_end_x = int(center_x + radius * math.cos(f2_start_angle + angle_rad))
        f2_end_y = int(center_y + radius * math.sin(f2_start_angle + angle_rad))

        # Build finger 1 action sequence
        finger1.create_pointer_move(
            duration=0, x=f1_start_x, y=f1_start_y, origin="viewport"
        )
        finger1.create_pointer_down(button=0)
        finger1.create_pointer_move(
            duration=duration_ms, x=f1_end_x, y=f1_end_y, origin="viewport"
        )
        finger1.create_pointer_up(button=0)

        # Build finger 2 action sequence
        finger2.create_pointer_move(
            duration=0, x=f2_start_x, y=f2_start_y, origin="viewport"
        )
        finger2.create_pointer_down(button=0)
        finger2.create_pointer_move(
            duration=duration_ms, x=f2_end_x, y=f2_end_y, origin="viewport"
        )
        finger2.create_pointer_up(button=0)

        # Execute multi-touch action
        actions = ActionBuilder(driver)
        actions.add_action(finger1)
        actions.add_action(finger2)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, actions.perform)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_type(self, action: TypeAction) -> ActionExecutionResult:
        """Type text into the current focused element.

        Args:
            action: TypeAction with text to type

        Returns:
            ActionExecutionResult
        """
        text = action.text

        self._log("debug", f"Typing text: '{text[:50]}...' " if len(text) > 50 else f"Typing text: '{text}'")

        # If coordinates provided, tap first to focus
        if action.x is not None and action.y is not None:
            x, y = self.normalize_coordinates(action.x, action.y)
            actions, touch = self.appium_client.create_touch_action()
            actions.pointer_action.move_to_location(x, y)
            actions.pointer_action.pointer_down()
            actions.pointer_action.pause(0.05)
            actions.pointer_action.pointer_up()
            await self.appium_client.execute_touch_action(actions)
            await asyncio.sleep(0.2)  # Wait for keyboard

        await self.appium_client.send_keys(text)

        if action.press_enter_after:
            # Send enter key
            await self.appium_client.send_keys("\n")

        return ActionExecutionResult(success=True, error=None)

    async def _perform_scroll(self, action: ScrollAction) -> ActionExecutionResult:
        """Perform scroll at coordinates.

        Args:
            action: ScrollAction with coordinates and scroll amounts

        Returns:
            ActionExecutionResult
        """
        x, y = self.normalize_coordinates(action.x, action.y)
        scroll_x = action.scroll_x or 0
        scroll_y = action.scroll_y or 0

        # Convert scroll amounts to swipe distance (negative scroll = swipe down)
        end_x = x - scroll_x
        end_y = y - scroll_y

        self._log("debug", f"Scroll at ({x}, {y}) by ({scroll_x}, {scroll_y})")

        actions, touch = self.appium_client.create_touch_action()

        actions.pointer_action.move_to_location(x, y)
        actions.pointer_action.pointer_down()

        # Smooth scroll over 300ms
        steps = 10
        for i in range(1, steps + 1):
            progress = i / steps
            current_x = int(x + (end_x - x) * progress)
            current_y = int(y + (end_y - y) * progress)
            actions.pointer_action.move_to_location(current_x, current_y)
            actions.pointer_action.pause(0.03)

        actions.pointer_action.pointer_up()

        await self.appium_client.execute_touch_action(actions)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_wait(self, action: WaitAction) -> ActionExecutionResult:
        """Wait for specified duration.

        Args:
            action: WaitAction with duration

        Returns:
            ActionExecutionResult
        """
        duration_s = (action.miliseconds or 1000) / 1000
        self._log("debug", f"Waiting for {duration_s}s")
        await asyncio.sleep(duration_s)
        return ActionExecutionResult(success=True, error=None)

    async def _perform_screenshot(self, action: ScreenshotAction) -> ActionExecutionResult:
        """Capture screenshot (no-op, screenshot taken separately).

        Args:
            action: ScreenshotAction

        Returns:
            ActionExecutionResult
        """
        self._log("debug", "Screenshot action (handled by agent loop)")
        return ActionExecutionResult(success=True, error=None)

    async def _perform_function(self, action: FunctionAction) -> ActionExecutionResult:
        """Execute a function action (navigation, app control).

        Args:
            action: FunctionAction with function name and arguments

        Returns:
            ActionExecutionResult
        """
        name = action.name
        args = action.arguments

        self._log("debug", f"Function: {name}")

        if name == "goto" and args and args.url:
            await self.appium_client.open_url(args.url)
            return ActionExecutionResult(success=True, error=None)

        elif name == "navigate_back":
            await self.appium_client.press_back()
            return ActionExecutionResult(success=True, error=None)

        elif name == "go_home":
            await self.appium_client.press_home()
            return ActionExecutionResult(success=True, error=None)

        elif name == "open_app":
            if args:
                # Check for app_id first, then fallback to url (for backwards compatibility)
                app_id = getattr(args, "app_id", None) or getattr(args, "url", None)
                if app_id:
                    await self.appium_client.launch_app(app_id)
                    return ActionExecutionResult(success=True, error=None)
            return ActionExecutionResult(success=False, error="Missing app_id for open_app")

        elif name == "hide_keyboard":
            await self.appium_client.hide_keyboard()
            return ActionExecutionResult(success=True, error=None)

        else:
            self._log("error", f"Unsupported function: {name}")
            return ActionExecutionResult(success=False, error=f"Unsupported function: {name}")

    async def handle_navigation(
        self, action_description: str, initial_context: Optional[str] = None
    ) -> None:
        """Handle potential context changes after actions.

        Args:
            action_description: Description of the action performed
            initial_context: Context before the action
        """
        self._log("debug", f"{action_description} - checking for context changes")

        try:
            current_context = await self.appium_client.get_current_context()
            if initial_context and current_context != initial_context:
                self._log(
                    "info",
                    f"Context changed from {initial_context} to {current_context}",
                )
        except Exception as e:
            self._log("debug", f"Could not check context: {e}")

        # Brief wait for UI to settle
        await asyncio.sleep(0.3)
