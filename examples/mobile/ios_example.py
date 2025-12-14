#!/usr/bin/env python3
"""
iOS Mobile Agent Example

Prerequisites:
1. iPhone/iPad connected via USB (or Simulator running)
2. Appium server running: appium server --address 127.0.0.1 --port 4723
3. GEMINI_API_KEY environment variable set
4. Xcode and WebDriverAgent configured
5. For real devices: valid Apple Developer certificate

Run:
    python examples/mobile/ios_example.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from stagehand.agent import MobileAgent


async def example_safari_search():
    """Example: Open Safari and search for something."""
    print("=" * 60)
    print("iOS Example: Safari Search")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="iphone_15_pro",  # Options: iphone_15, iphone_se, ipad_pro_12_9, etc.
        appium_url="http://localhost:4723",
        model="gemini-2.5-flash-preview-05-20",
        max_steps=15,
    )

    try:
        # Connect to device
        # For simulator: device_name should match Simulator name
        # For real device: provide udid from `xcrun xctrace list devices`
        await agent.connect(
            device_name="iPhone 15 Pro",  # Or "iPhone 15 Pro Simulator"
            browser_name="Safari",
            # For real device, uncomment and provide UDID:
            # udid="00008030-001A34E22E38802E",
        )
        print(f"Connected to {agent.device_profile.name}")

        # Execute AI-powered task
        result = await agent.execute(
            instruction="Go to apple.com and find information about the latest iPhone",
            max_steps=12,
        )

        print(f"\nTask completed: {result.completed}")
        print(f"Message: {result.message}")
        print(f"Actions taken: {len(result.actions)}")

    finally:
        await agent.disconnect()
        print("\nDisconnected")


async def example_native_app():
    """Example: Interact with iOS Settings app."""
    print("=" * 60)
    print("iOS Example: Settings App")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
        max_steps=20,
    )

    try:
        # Connect to Settings app
        await agent.connect(
            device_name="iPhone 15 Pro",
            bundle_id="com.apple.Preferences",  # iOS Settings app
        )
        print("Connected to Settings app")

        # Use AI to navigate
        result = await agent.execute(
            instruction="Find the Wi-Fi settings and check the current network name",
        )

        print(f"\nResult: {result.message}")

    finally:
        await agent.disconnect()


async def example_app_store():
    """Example: Search the App Store."""
    print("=" * 60)
    print("iOS Example: App Store Search")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
        max_steps=15,
    )

    try:
        await agent.connect(
            device_name="iPhone 15 Pro",
            bundle_id="com.apple.AppStore",
        )
        print("Connected to App Store")

        result = await agent.execute(
            instruction="Tap on Search tab, then search for 'Spotify' and find its rating",
        )

        print(f"\nResult: {result.message}")

    finally:
        await agent.disconnect()


async def example_pinch_zoom():
    """Example: Use pinch zoom gesture on Maps."""
    print("=" * 60)
    print("iOS Example: Pinch Zoom on Maps")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
    )

    try:
        await agent.connect(
            device_name="iPhone 15 Pro",
            bundle_id="com.apple.Maps",
        )
        print("Connected to Maps")

        # Wait for app to load
        await asyncio.sleep(2)

        handler = agent.navigation_handler

        from stagehand.types.agent import AgentAction, PinchAction, TapAction

        # Tap center to dismiss any popups
        tap = AgentAction(
            action_type="tap",
            action=TapAction(type="tap", x=500, y=500)
        )
        await handler.perform_action(tap)
        await asyncio.sleep(1)

        # Pinch out to zoom in
        pinch_out = AgentAction(
            action_type="pinch",
            action=PinchAction(
                type="pinch",
                center_x=500,
                center_y=500,
                scale=2.0,  # Zoom in 2x
                duration_ms=500,
            )
        )
        result = await handler.perform_action(pinch_out)
        print(f"Pinch zoom in: {result.success}")

        await asyncio.sleep(1)

        # Pinch in to zoom out
        pinch_in = AgentAction(
            action_type="pinch",
            action=PinchAction(
                type="pinch",
                center_x=500,
                center_y=500,
                scale=0.5,  # Zoom out
                duration_ms=500,
            )
        )
        result = await handler.perform_action(pinch_in)
        print(f"Pinch zoom out: {result.success}")

    finally:
        await agent.disconnect()


async def main():
    print("\nSelect an example to run:")
    print("1. Safari Search (AI-powered)")
    print("2. Settings App (AI-powered)")
    print("3. App Store Search (AI-powered)")
    print("4. Maps Pinch Zoom (manual gestures)")
    print()

    choice = input("Enter choice (1-4): ").strip()

    examples = {
        "1": example_safari_search,
        "2": example_native_app,
        "3": example_app_store,
        "4": example_pinch_zoom,
    }

    if choice in examples:
        await examples[choice]()
    else:
        print("Running Safari Search example by default...")
        await example_safari_search()


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY not set. AI-powered examples will fail.")
        print("Set it with: export GEMINI_API_KEY=your_key_here")
        print()

    asyncio.run(main())
