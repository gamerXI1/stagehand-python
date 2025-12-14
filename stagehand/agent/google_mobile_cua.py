"""Google CUA client configured for mobile device automation."""

import asyncio
import functools
import os
import time
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import (
    Content,
    FunctionDeclaration,
    FunctionResponse,
    FunctionResponseBlob,
    FunctionResponsePart,
    GenerateContentConfig,
    Part,
    Schema,
    Tool,
)
from pydantic import TypeAdapter

from ..handlers.mobile_navigation_handler import MobileNavigationHandler
from ..types.agent import (
    ActionExecutionResult,
    AgentAction,
    AgentActionType,
    AgentConfig,
    AgentExecuteOptions,
    AgentResult,
)
from ..types.mobile import (
    COORDINATE_GRID_SIZE,
    DEFAULT_LONG_PRESS_DURATION_MS,
    DEFAULT_SWIPE_DURATION_MS,
    DEFAULT_PINCH_DURATION_MS,
    MAX_HISTORY_LENGTH,
)

# Retry configuration
MAX_API_RETRIES = 3
RETRY_BASE_DELAY_S = 1.0


class GoogleMobileCUAClient:
    """Google CUA client for mobile device automation.

    Uses Gemini's computer-use model with mobile-optimized configuration.
    Translates Google CUA actions to mobile touch gestures via MobileNavigationHandler.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-computer-use-preview-10-2025",
        instructions: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        logger: Optional[Any] = None,
        handler: Optional[MobileNavigationHandler] = None,
        viewport_width: int = 393,
        viewport_height: int = 852,
    ):
        """Initialize GoogleMobileCUAClient.

        Args:
            model: Gemini model name
            instructions: System prompt/instructions
            config: Agent configuration
            logger: Logger instance
            handler: MobileNavigationHandler for action execution
            viewport_width: Device viewport width in pixels
            viewport_height: Device viewport height in pixels
        """
        # Load environment variables
        load_dotenv()

        self.model = model
        self.instructions = instructions or self._default_mobile_instructions()
        self.config = config or AgentConfig()
        self.logger = logger
        self.handler = handler
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

        # Initialize Google GenAI client
        api_key = None
        if config and hasattr(config, "options") and config.options:
            api_key = config.options.get("apiKey")
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Provide via config or environment variable."
            )

        self.genai_client = genai.Client(api_key=api_key)
        self._generate_content_config = self._build_config()
        self.history: list[Content] = []

        # Action mapping dispatch table - maps function names to mapping functions
        self._action_mappers: dict[str, Callable[[dict[str, Any]], tuple[str, dict[str, Any]]]] = {
            "tap_at": self._map_tap,
            "double_tap_at": self._map_double_tap,
            "long_press_at": self._map_long_press,
            "swipe": self._map_swipe,
            "type_text_at": self._map_type,
            "go_back": self._map_go_back,
            "go_home": self._map_go_home,
            "open_app": self._map_open_app,
            "open_url": self._map_open_url,
            "wait": self._map_wait,
            "pinch": self._map_pinch,
            "scroll": self._map_scroll,
        }

    def _log(self, level: str, message: str, category: str = "mobile_agent") -> None:
        """Log a message if logger is available."""
        if self.logger:
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(message, category=category)

    def _clamp_coordinate(self, value: int) -> int:
        """Clamp coordinate to valid 0-1000 range.

        Args:
            value: Coordinate value from model

        Returns:
            Clamped coordinate within valid range
        """
        return max(0, min(COORDINATE_GRID_SIZE, value))

    def _default_mobile_instructions(self) -> str:
        """Default system instructions for mobile automation."""
        return """You are a mobile device automation agent. You interact with iOS and Android devices through touch gestures.

Key behaviors:
- Use tap_at for clicking/tapping on elements
- Use swipe for scrolling and navigation gestures
- Use long_press_at for context menus and drag operations
- Use type_text_at to enter text after tapping on input fields
- Use go_home to return to home screen
- Use go_back to navigate back
- Use open_app to launch applications

Coordinate system:
- All coordinates use a 0-1000 grid regardless of actual screen size
- (0, 0) is top-left, (1000, 1000) is bottom-right
- Center of screen is (500, 500)

Always analyze the screenshot carefully before taking actions.
For text input, tap the field first, then use type_text_at.
"""

    def _build_config(self) -> GenerateContentConfig:
        """Build the GenerateContentConfig with mobile tools."""
        return GenerateContentConfig(
            temperature=0.3,  # Low for deterministic UI actions
            top_p=0.9,
            top_k=20,  # Focused sampling
            max_output_tokens=2048,  # Actions don't need large output
            tools=[self._build_mobile_tools()],
        )

    def _build_mobile_tools(self) -> Tool:
        """Build mobile-specific tool definitions."""
        return Tool(
            function_declarations=[
                # Tap action
                FunctionDeclaration(
                    name="tap_at",
                    description="Tap at the specified coordinates on the screen",
                    parameters=Schema(
                        type="object",
                        properties={
                            "x": Schema(
                                type="integer",
                                description="X coordinate (0-1000 grid)",
                            ),
                            "y": Schema(
                                type="integer",
                                description="Y coordinate (0-1000 grid)",
                            ),
                        },
                        required=["x", "y"],
                    ),
                ),
                # Double tap
                FunctionDeclaration(
                    name="double_tap_at",
                    description="Double tap at the specified coordinates",
                    parameters=Schema(
                        type="object",
                        properties={
                            "x": Schema(type="integer", description="X coordinate (0-1000)"),
                            "y": Schema(type="integer", description="Y coordinate (0-1000)"),
                        },
                        required=["x", "y"],
                    ),
                ),
                # Long press
                FunctionDeclaration(
                    name="long_press_at",
                    description="Long press at coordinates for context menus or drag initiation",
                    parameters=Schema(
                        type="object",
                        properties={
                            "x": Schema(type="integer", description="X coordinate (0-1000)"),
                            "y": Schema(type="integer", description="Y coordinate (0-1000)"),
                            "duration_ms": Schema(
                                type="integer",
                                description="Press duration in milliseconds (default 500)",
                            ),
                        },
                        required=["x", "y"],
                    ),
                ),
                # Swipe
                FunctionDeclaration(
                    name="swipe",
                    description="Swipe from start to end coordinates. Use for scrolling, pull-to-refresh, or navigation gestures.",
                    parameters=Schema(
                        type="object",
                        properties={
                            "start_x": Schema(type="integer", description="Start X (0-1000)"),
                            "start_y": Schema(type="integer", description="Start Y (0-1000)"),
                            "end_x": Schema(type="integer", description="End X (0-1000)"),
                            "end_y": Schema(type="integer", description="End Y (0-1000)"),
                            "duration_ms": Schema(
                                type="integer",
                                description="Swipe duration in milliseconds (default 300)",
                            ),
                        },
                        required=["start_x", "start_y", "end_x", "end_y"],
                    ),
                ),
                # Type text
                FunctionDeclaration(
                    name="type_text_at",
                    description="Type text at the specified coordinates. Taps first to focus, then types.",
                    parameters=Schema(
                        type="object",
                        properties={
                            "x": Schema(type="integer", description="X coordinate to tap (0-1000)"),
                            "y": Schema(type="integer", description="Y coordinate to tap (0-1000)"),
                            "text": Schema(type="string", description="Text to type"),
                            "press_enter": Schema(
                                type="boolean",
                                description="Press enter/return after typing",
                            ),
                        },
                        required=["x", "y", "text"],
                    ),
                ),
                # Navigate back
                FunctionDeclaration(
                    name="go_back",
                    description="Navigate back (Android back button or iOS back gesture)",
                    parameters=Schema(type="object", properties={}),
                ),
                # Go home
                FunctionDeclaration(
                    name="go_home",
                    description="Go to device home screen",
                    parameters=Schema(type="object", properties={}),
                ),
                # Open app
                FunctionDeclaration(
                    name="open_app",
                    description="Launch an application by name or package/bundle ID",
                    parameters=Schema(
                        type="object",
                        properties={
                            "app_name": Schema(
                                type="string",
                                description="App name or bundle ID / package name",
                            ),
                        },
                        required=["app_name"],
                    ),
                ),
                # Open URL
                FunctionDeclaration(
                    name="open_url",
                    description="Open a URL in the mobile browser",
                    parameters=Schema(
                        type="object",
                        properties={
                            "url": Schema(type="string", description="URL to open"),
                        },
                        required=["url"],
                    ),
                ),
                # Wait
                FunctionDeclaration(
                    name="wait",
                    description="Wait for specified duration",
                    parameters=Schema(
                        type="object",
                        properties={
                            "seconds": Schema(
                                type="number",
                                description="Duration to wait in seconds",
                            ),
                        },
                        required=["seconds"],
                    ),
                ),
                # Pinch zoom
                FunctionDeclaration(
                    name="pinch",
                    description="Pinch gesture for zooming. Scale < 1 zooms out, scale > 1 zooms in.",
                    parameters=Schema(
                        type="object",
                        properties={
                            "center_x": Schema(type="integer", description="Center X (0-1000)"),
                            "center_y": Schema(type="integer", description="Center Y (0-1000)"),
                            "scale": Schema(
                                type="number",
                                description="Scale factor (0.5 = zoom out 50%, 2.0 = zoom in 100%)",
                            ),
                        },
                        required=["center_x", "center_y", "scale"],
                    ),
                ),
                # Scroll document
                FunctionDeclaration(
                    name="scroll",
                    description="Scroll the page/document in specified direction",
                    parameters=Schema(
                        type="object",
                        properties={
                            "direction": Schema(
                                type="string",
                                description="Scroll direction: up, down, left, right",
                            ),
                            "amount": Schema(
                                type="integer",
                                description="Scroll amount (1-10, default 5)",
                            ),
                        },
                        required=["direction"],
                    ),
                ),
            ]
        )

    def format_screenshot(self, screenshot_base64: str) -> Part:
        """Format screenshot for Gemini API.

        Args:
            screenshot_base64: Base64 encoded PNG screenshot

        Returns:
            Part with inline image data
        """
        return Part(
            inline_data=types.Blob(mime_type="image/png", data=screenshot_base64)
        )

    def _format_initial_messages(
        self, instruction: str, screenshot_base64: Optional[str]
    ) -> list[Content]:
        """Format initial messages for the conversation.

        Args:
            instruction: Task instruction
            screenshot_base64: Initial screenshot

        Returns:
            List of Content messages
        """
        parts: list[Part] = []

        if self.instructions:
            parts.append(Part(text=self.instructions))

        parts.append(Part(text=instruction))

        if screenshot_base64:
            parts.append(self.format_screenshot(screenshot_base64))

        initial_content = Content(role="user", parts=parts)
        self.history = [initial_content]
        return self.history

    def _process_provider_response(
        self, response: types.GenerateContentResponse
    ) -> tuple[
        list[AgentAction],
        Optional[str],
        bool,
        Optional[str],
        list[tuple[str, dict[str, Any]]],
    ]:
        """Process Gemini response and extract actions.

        Args:
            response: Gemini API response

        Returns:
            Tuple of (actions, reasoning, task_completed, final_message, function_info)
        """
        if not response.candidates:
            self._log("error", "No candidates in response")
            return [], "No response from model", True, "Error: No candidates", []

        candidate = response.candidates[0]
        self.history.append(candidate.content)

        reasoning_text: Optional[str] = None
        function_calls: list[types.FunctionCall] = []

        for part in candidate.content.parts:
            if part.text:
                reasoning_text = (
                    part.text if reasoning_text is None else f"{reasoning_text} {part.text}"
                )
            if part.function_call:
                function_calls.append(part.function_call)

        # Handle malformed function calls
        if (
            not function_calls
            and not reasoning_text
            and hasattr(candidate, "finish_reason")
            and candidate.finish_reason == types.FinishReason.MALFORMED_FUNCTION_CALL
        ):
            return [], reasoning_text, False, None, []

        # Handle non-standard finish reasons
        if hasattr(candidate, "finish_reason"):
            finish = candidate.finish_reason
            if finish not in (
                types.FinishReason.FINISH_REASON_UNSPECIFIED,
                types.FinishReason.STOP,
                types.FinishReason.TOOL_CODE,
            ):
                error = f"Stopped: {finish.name}"
                self._log("error", error)
                return [], reasoning_text, True, error, []

        if not function_calls:
            msg = reasoning_text or "No actions from model"
            self._log("info", f"Task complete: {msg}")
            return [], reasoning_text, True, msg, []

        # Process function calls
        agent_actions: list[AgentAction] = []
        function_info: list[tuple[str, dict[str, Any]]] = []

        for fc in function_calls:
            action_name = fc.name
            action_args = fc.args or {}
            function_info.append((action_name, action_args))

            agent_action = self._map_function_to_action(action_name, action_args)
            if agent_action:
                agent_action.reasoning = reasoning_text
                agent_actions.append(agent_action)

        return agent_actions, reasoning_text, False, None, function_info

    # -------------------------------------------------------------------------
    # Action Mapping Methods - Individual mappers for each function type
    # -------------------------------------------------------------------------

    def _map_tap(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map tap_at function to tap action."""
        return "tap", {
            "type": "tap",
            "x": self._clamp_coordinate(args["x"]),
            "y": self._clamp_coordinate(args["y"]),
        }

    def _map_double_tap(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map double_tap_at function to double_tap action."""
        return "double_tap", {
            "type": "double_tap",
            "x": self._clamp_coordinate(args["x"]),
            "y": self._clamp_coordinate(args["y"]),
        }

    def _map_long_press(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map long_press_at function to long_press action."""
        return "long_press", {
            "type": "long_press",
            "x": self._clamp_coordinate(args["x"]),
            "y": self._clamp_coordinate(args["y"]),
            "duration_ms": args.get("duration_ms", DEFAULT_LONG_PRESS_DURATION_MS),
        }

    def _map_swipe(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map swipe function to swipe action."""
        return "swipe", {
            "type": "swipe",
            "start_x": self._clamp_coordinate(args["start_x"]),
            "start_y": self._clamp_coordinate(args["start_y"]),
            "end_x": self._clamp_coordinate(args["end_x"]),
            "end_y": self._clamp_coordinate(args["end_y"]),
            "duration_ms": args.get("duration_ms", DEFAULT_SWIPE_DURATION_MS),
        }

    def _map_type(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map type_text_at function to type action."""
        return "type", {
            "type": "type",
            "x": self._clamp_coordinate(args["x"]),
            "y": self._clamp_coordinate(args["y"]),
            "text": args["text"],
            "press_enter_after": args.get("press_enter", False),
        }

    def _map_go_back(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map go_back function to navigate_back function action."""
        return "function", {"type": "function", "name": "navigate_back", "arguments": None}

    def _map_go_home(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map go_home function to go_home function action."""
        return "function", {"type": "function", "name": "go_home", "arguments": None}

    def _map_open_app(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map open_app function to open_app function action."""
        return "function", {
            "type": "function",
            "name": "open_app",
            "arguments": {"app_id": args["app_name"]},
        }

    def _map_open_url(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map open_url function to goto function action."""
        return "function", {
            "type": "function",
            "name": "goto",
            "arguments": {"url": args["url"]},
        }

    def _map_wait(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map wait function to wait action."""
        return "wait", {
            "type": "wait",
            "milliseconds": int(args.get("seconds", 1) * 1000),
        }

    def _map_pinch(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map pinch function to pinch action."""
        return "pinch", {
            "type": "pinch",
            "center_x": self._clamp_coordinate(args["center_x"]),
            "center_y": self._clamp_coordinate(args["center_y"]),
            "scale": args["scale"],
            "duration_ms": DEFAULT_PINCH_DURATION_MS,
        }

    def _map_scroll(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Map scroll function to swipe action.

        Converts scroll direction to appropriate swipe gesture.
        Uses normalized coordinates (0-1000 grid).
        """
        direction = args.get("direction", "down")
        amount = args.get("amount", 5) * 100  # Convert to grid units

        # Scroll direction positions in 1000-grid coordinates
        center = COORDINATE_GRID_SIZE // 2  # 500
        near_edge = int(COORDINATE_GRID_SIZE * 0.3)  # 300
        far_edge = int(COORDINATE_GRID_SIZE * 0.7)  # 700

        scroll_params = {
            "down": (center, far_edge, center, far_edge - amount),
            "up": (center, near_edge, center, near_edge + amount),
            "left": (far_edge, center, far_edge - amount, center),
            "right": (near_edge, center, near_edge + amount, center),
        }

        start_x, start_y, end_x, end_y = scroll_params.get(
            direction, scroll_params["down"]
        )

        return "swipe", {
            "type": "swipe",
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "duration_ms": DEFAULT_SWIPE_DURATION_MS,
        }

    def _map_function_to_action(
        self, name: str, args: dict[str, Any]
    ) -> Optional[AgentAction]:
        """Map a Google CUA function call to an AgentAction.

        Uses dispatch table for clean function-to-action mapping.

        Args:
            name: Function name
            args: Function arguments

        Returns:
            AgentAction or None if unsupported
        """
        mapper = self._action_mappers.get(name)
        if not mapper:
            self._log("error", f"Unsupported function: {name}")
            return None

        try:
            action_type, action_payload = mapper(args)
            action_model = TypeAdapter(AgentActionType).validate_python(action_payload)
            return AgentAction(action_type=action_type, action=action_model)
        except Exception as e:
            self._log("error", f"Failed to parse action {name}: {e}")
            return None

    def _format_action_feedback(
        self,
        function_name: str,
        action_result: ActionExecutionResult,
        screenshot_base64: str,
        function_args: Optional[dict[str, Any]] = None,
    ) -> Content:
        """Format feedback for the model after an action.

        Args:
            function_name: Name of function that was called
            action_result: Result of action execution
            screenshot_base64: New screenshot after action
            function_args: Original function arguments

        Returns:
            Content with function response
        """
        response_data: dict[str, Any] = {}

        if not action_result.success:
            response_data["error"] = action_result.error or "Unknown error"
            self._log("info", f"Action failed: {response_data['error']}")

        function_response_part = Part(
            function_response=FunctionResponse(
                name=function_name,
                response=response_data,
                parts=[
                    FunctionResponsePart(
                        inline_data=FunctionResponseBlob(
                            mime_type="image/png", data=screenshot_base64
                        )
                    )
                ],
            )
        )

        feedback_content = Content(role="user", parts=[function_response_part])
        self.history.append(feedback_content)
        return feedback_content

    def _has_error_response(self, content: Content) -> bool:
        """Check if content contains an error response.

        Args:
            content: Content message to check

        Returns:
            True if content contains error information
        """
        for part in content.parts:
            if hasattr(part, "function_response") and part.function_response:
                resp = part.function_response
                if hasattr(resp, "response") and isinstance(resp.response, dict):
                    if resp.response.get("error"):
                        return True
        return False

    def _trim_history(self) -> None:
        """Trim history to prevent unbounded memory growth.

        Keeps the first message (system prompt + initial instruction),
        messages with errors (for context), and recent messages.
        """
        if len(self.history) <= MAX_HISTORY_LENGTH:
            return

        keep_first = 1
        keep_recent = 20
        max_errors = 5

        # Find error messages in middle section
        middle_start = keep_first
        middle_end = len(self.history) - keep_recent
        middle = self.history[middle_start:middle_end]

        error_messages = [m for m in middle if self._has_error_response(m)][:max_errors]

        # Reconstruct history: first + errors + recent
        self.history = (
            self.history[:keep_first]
            + error_messages
            + self.history[-keep_recent:]
        )

        self._log(
            "debug",
            f"Trimmed history to {len(self.history)} messages "
            f"(kept {len(error_messages)} error messages)",
        )

    async def run_task(
        self,
        instruction: str,
        max_steps: int = 20,
        options: Optional[AgentExecuteOptions] = None,
    ) -> AgentResult:
        """Execute a task on the mobile device.

        Args:
            instruction: Task instruction
            max_steps: Maximum steps to take
            options: Execution options

        Returns:
            AgentResult with actions taken and completion status
        """
        self._log("info", f"Starting task: '{instruction}' (max_steps={max_steps})")

        if not self.handler:
            self._log("error", "MobileNavigationHandler not set")
            return AgentResult(
                completed=False,
                actions=[],
                message="Error: Handler not set",
                usage={"input_tokens": 0, "output_tokens": 0, "inference_time_ms": 0},
            )

        # Get initial screenshot
        screenshot_b64 = await self.handler.get_screenshot_base64()
        self._format_initial_messages(instruction, screenshot_b64)

        actions_taken: list[AgentActionType] = []
        total_inference_time_ms = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for step in range(max_steps):
            self._log("info", f"Step {step + 1}/{max_steps}")

            # Enforce history limit to prevent memory leak
            self._trim_history()

            start_time = time.monotonic()
            response = None
            last_error: Optional[Exception] = None

            # Retry loop with exponential backoff
            for attempt in range(MAX_API_RETRIES):
                try:
                    # Run blocking Gemini API call in executor
                    # Use functools.partial to avoid closure capture issues
                    # Snapshot history with list() to prevent mutation during execution
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.genai_client.models.generate_content,
                            model=self.model,
                            contents=list(self.history),
                            config=self._generate_content_config,
                        ),
                    )
                    break  # Success - exit retry loop

                except Exception as e:
                    last_error = e
                    if attempt < MAX_API_RETRIES - 1:
                        delay = RETRY_BASE_DELAY_S * (2 ** attempt)
                        self._log(
                            "warning",
                            f"API call failed (attempt {attempt + 1}/{MAX_API_RETRIES}), "
                            f"retrying in {delay}s: {e}",
                        )
                        await asyncio.sleep(delay)
                    else:
                        self._log("error", f"API call failed after {MAX_API_RETRIES} attempts: {e}")

            if response is None:
                return AgentResult(
                    actions=actions_taken,
                    message=f"API error after {MAX_API_RETRIES} retries: {last_error}",
                    completed=False,
                    usage={
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "inference_time_ms": total_inference_time_ms,
                    },
                )

            end_time = time.monotonic()
            total_inference_time_ms += int((end_time - start_time) * 1000)

            # Track token usage from response
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                metadata = response.usage_metadata
                total_input_tokens += getattr(metadata, "prompt_token_count", 0)
                total_output_tokens += getattr(metadata, "candidates_token_count", 0)

            (
                agent_actions,
                reasoning,
                task_completed,
                final_message,
                function_info_list,
            ) = self._process_provider_response(response)

            if reasoning:
                self._log("info", f"Reasoning: {reasoning}")

            if agent_actions:
                for idx, agent_action in enumerate(agent_actions):
                    if agent_action.action:
                        actions_taken.append(agent_action.action)

                    func_name, func_args = function_info_list[idx]

                    # Execute action
                    result = await self.handler.perform_action(agent_action)

                    # Get new screenshot
                    screenshot_b64 = await self.handler.get_screenshot_base64()

                    # Send feedback to model
                    self._format_action_feedback(
                        function_name=func_name,
                        action_result=result,
                        screenshot_base64=screenshot_b64,
                        function_args=func_args,
                    )

            if task_completed:
                self._log("info", f"Task complete: {final_message}")
                return AgentResult(
                    actions=actions_taken,
                    message=final_message or "Task completed",
                    completed=True,
                    usage={
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "inference_time_ms": total_inference_time_ms,
                    },
                )

            if not agent_actions and not task_completed:
                self._log("info", "No actions received, ending task")
                return AgentResult(
                    actions=actions_taken,
                    message=final_message or "No further actions",
                    completed=False,
                    usage={
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "inference_time_ms": total_inference_time_ms,
                    },
                )

        self._log("info", "Max steps reached")
        return AgentResult(
            actions=actions_taken,
            message="Max steps reached",
            completed=False,
            usage={
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "inference_time_ms": total_inference_time_ms,
            },
        )
