#!/usr/bin/env python3
"""
Android Mobile Agent Example

Prerequisites:
1. Android device connected via USB with USB debugging enabled
2. Appium server running: appium server --address 127.0.0.1 --port 4723
3. GEMINI_API_KEY environment variable set
4. ADB recognizes device: adb devices

Run:
    python examples/mobile/android_example.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from stagehand.agent import MobileAgent, create_mobile_agent


async def example_chrome_search():
    """Example: Open Chrome and search for something."""
    print("=" * 60)
    print("Android Example: Chrome Search")
    print("=" * 60)

    # Create agent for Pixel 8 (or change to match your device)
    agent = MobileAgent(
        device_profile="pixel_8",  # Options: pixel_8, pixel_8_pro, samsung_galaxy_s24, etc.
        appium_url="http://localhost:4723",
        model="gemini-2.5-flash-preview-05-20",  # Or use gemini-2.0-flash
        max_steps=15,
    )

    try:
        # Connect to device
        # Get device name from: adb devices -l
        await agent.connect(
            device_name="Pixel 8",  # Or your device name
            browser_name="Chrome",  # Use Chrome browser
            # For native apps, use app_package instead:
            # app_package="com.android.chrome",
            # app_activity="com.google.android.apps.chrome.Main",
        )
        print(f"Connected to {agent.device_profile.name}")
        print(f"Viewport: {agent.appium_client.viewport_width}x{agent.appium_client.viewport_height}")

        # Take initial screenshot
        screenshot = await agent.screenshot()
        print(f"Screenshot captured: {len(screenshot)} bytes")

        # Execute a task using AI
        result = await agent.execute(
            instruction="Open google.com and search for 'Python automation'",
            max_steps=10,
        )

        print(f"\nTask completed: {result.completed}")
        print(f"Message: {result.message}")
        print(f"Actions taken: {len(result.actions)}")
        if result.usage:
            print(f"Tokens used: {result.usage.input_tokens} in, {result.usage.output_tokens} out")

    finally:
        await agent.disconnect()
        print("\nDisconnected from device")


async def example_native_app():
    """Example: Interact with a native Android app."""
    print("=" * 60)
    print("Android Example: Native App Interaction")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="pixel_8",
        appium_url="http://localhost:4723",
        max_steps=20,
    )

    try:
        # Connect to Settings app
        await agent.connect(
            device_name="Pixel 8",
            app_package="com.android.settings",
            app_activity=".Settings",
        )
        print("Connected to Settings app")

        # Navigate using AI
        result = await agent.execute(
            instruction="Find and tap on 'Display' settings, then look for brightness control",
        )

        print(f"\nResult: {result.message}")

    finally:
        await agent.disconnect()


async def example_manual_gestures():
    """Example: Manual gesture control without AI."""
    print("=" * 60)
    print("Android Example: Manual Gestures")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="pixel_8",
        appium_url="http://localhost:4723",
    )

    try:
        await agent.connect(
            device_name="Pixel 8",
            browser_name="Chrome",
        )

        # Open a URL directly
        await agent.open_url("https://news.ycombinator.com")
        print("Opened Hacker News")

        # Wait for page load
        await asyncio.sleep(2)

        # Take screenshot
        screenshot = await agent.screenshot()
        print(f"Screenshot: {len(screenshot)} bytes")

        # Use the navigation handler directly for gestures
        handler = agent.navigation_handler

        # Import action types
        from stagehand.types.agent import (
            AgentAction, TapAction, SwipeAction, LongPressAction
        )

        # Perform a swipe down (scroll)
        swipe_action = AgentAction(
            action_type="swipe",
            action=SwipeAction(
                type="swipe",
                start_x=500,  # Center X (0-1000 grid)
                start_y=700,  # Lower area
                end_x=500,
                end_y=300,    # Swipe up to scroll down
                duration_ms=300,
            )
        )
        result = await handler.perform_action(swipe_action)
        print(f"Swipe performed: {result.success}")

        await asyncio.sleep(1)

        # Tap on first link (approximate position)
        tap_action = AgentAction(
            action_type="tap",
            action=TapAction(
                type="tap",
                x=500,  # Center X
                y=250,  # Upper area where first link might be
            )
        )
        result = await handler.perform_action(tap_action)
        print(f"Tap performed: {result.success}")

        await asyncio.sleep(2)

        # Go back
        await agent.go_back()
        print("Navigated back")

    finally:
        await agent.disconnect()


async def main():
    """Run all examples."""
    print("\nSelect an example to run:")
    print("1. Chrome Search (AI-powered)")
    print("2. Native App Interaction (AI-powered)")
    print("3. Manual Gestures (no AI)")
    print()

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        await example_chrome_search()
    elif choice == "2":
        await example_native_app()
    elif choice == "3":
        await example_manual_gestures()
    else:
        print("Running Chrome Search example by default...")
        await example_chrome_search()


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY not set. AI-powered examples will fail.")
        print("Set it with: export GEMINI_API_KEY=your_key_here")
        print()

    asyncio.run(main())
