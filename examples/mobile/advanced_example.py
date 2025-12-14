#!/usr/bin/env python3
"""
Advanced Mobile Agent Examples

Demonstrates:
- Context manager usage
- Custom instructions
- Error handling
- Multi-step workflows
- Combining AI and manual control
- Cross-platform patterns
"""

import asyncio
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from stagehand.agent import MobileAgent
from stagehand.types.mobile import MobileDeviceProfile, MobilePlatform


# =============================================================================
# Example 1: Context Manager Usage
# =============================================================================

async def example_context_manager():
    """Use MobileAgent as async context manager for automatic cleanup."""
    print("=" * 60)
    print("Example: Context Manager")
    print("=" * 60)

    async with MobileAgent(
        device_profile="pixel_8",
        appium_url="http://localhost:4723",
    ) as agent:
        await agent.connect(
            device_name="Pixel 8",
            browser_name="Chrome",
        )

        result = await agent.execute("Go to google.com")
        print(f"Result: {result.message}")

    # Agent is automatically disconnected here
    print("Agent disconnected automatically")


# =============================================================================
# Example 2: Custom Device Profile
# =============================================================================

async def example_custom_profile():
    """Use a custom device profile for non-standard devices."""
    print("=" * 60)
    print("Example: Custom Device Profile")
    print("=" * 60)

    # Define custom profile for a specific device
    custom_profile = MobileDeviceProfile(
        name="OnePlus 12",
        platform=MobilePlatform.ANDROID,
        viewport_width=412,
        viewport_height=915,
        device_scale_factor=3.0,
        platform_version="14",
    )

    agent = MobileAgent(
        custom_profile=custom_profile,
        appium_url="http://localhost:4723",
    )

    try:
        await agent.connect(
            device_name="OnePlus 12",
            browser_name="Chrome",
        )
        print(f"Connected with custom profile: {agent.device_profile.name}")

        result = await agent.execute("Search for weather")
        print(f"Result: {result.message}")

    finally:
        await agent.disconnect()


# =============================================================================
# Example 3: Custom System Instructions
# =============================================================================

async def example_custom_instructions():
    """Provide custom instructions to guide AI behavior."""
    print("=" * 60)
    print("Example: Custom Instructions")
    print("=" * 60)

    custom_instructions = """
    You are an expert mobile QA tester. When performing tasks:

    1. Always wait for elements to fully load before interacting
    2. If an action fails, try an alternative approach
    3. Take note of any UI anomalies or errors you observe
    4. Prefer tapping on clearly labeled buttons over icons
    5. If you see a cookie consent popup, dismiss it first

    Report any issues you encounter in your final message.
    """

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
        instructions=custom_instructions,
        max_steps=25,
    )

    try:
        await agent.connect(
            device_name="iPhone 15 Pro",
            browser_name="Safari",
        )

        result = await agent.execute(
            instruction="Navigate to amazon.com and search for 'wireless headphones'. Report any UI issues.",
        )

        print(f"\nTask completed: {result.completed}")
        print(f"AI Report: {result.message}")

    finally:
        await agent.disconnect()


# =============================================================================
# Example 4: Error Handling and Retry
# =============================================================================

async def example_error_handling():
    """Demonstrate proper error handling patterns."""
    print("=" * 60)
    print("Example: Error Handling")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="pixel_8",
        appium_url="http://localhost:4723",
        max_steps=10,
    )

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            await agent.connect(
                device_name="Pixel 8",
                browser_name="Chrome",
            )

            result = await agent.execute(
                instruction="Open gmail.com and check for new emails",
            )

            if result.completed:
                print(f"Task completed: {result.message}")
                break
            else:
                print(f"Task incomplete: {result.message}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)

        except ConnectionError as e:
            print(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
            break
        finally:
            if agent.is_connected:
                await agent.disconnect()


# =============================================================================
# Example 5: Multi-Step Workflow
# =============================================================================

async def example_multi_step_workflow():
    """Execute a complex multi-step workflow."""
    print("=" * 60)
    print("Example: Multi-Step Workflow")
    print("=" * 60)

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
        max_steps=30,
    )

    try:
        await agent.connect(
            device_name="iPhone 15 Pro",
            browser_name="Safari",
        )

        # Step 1: Navigate to a shopping site
        print("\nStep 1: Navigate to shopping site...")
        result = await agent.execute(
            instruction="Go to ebay.com",
            max_steps=5,
        )
        print(f"  Result: {result.completed}")

        if not result.completed:
            print("  Failed to navigate, stopping workflow")
            return

        await asyncio.sleep(1)

        # Step 2: Search for a product
        print("\nStep 2: Search for product...")
        result = await agent.execute(
            instruction="Search for 'vintage camera'",
            max_steps=8,
        )
        print(f"  Result: {result.completed}")

        await asyncio.sleep(1)

        # Step 3: Apply filters
        print("\nStep 3: Apply filters...")
        result = await agent.execute(
            instruction="Filter results by 'Buy It Now' if available",
            max_steps=6,
        )
        print(f"  Result: {result.completed}")

        await asyncio.sleep(1)

        # Step 4: Get first result info
        print("\nStep 4: Get product info...")
        result = await agent.execute(
            instruction="Tap on the first product and tell me its price",
            max_steps=6,
        )
        print(f"  Product info: {result.message}")

        print("\nWorkflow completed!")

    finally:
        await agent.disconnect()


# =============================================================================
# Example 6: Combining AI and Manual Control
# =============================================================================

async def example_hybrid_control():
    """Combine AI-powered and manual gesture control."""
    print("=" * 60)
    print("Example: Hybrid AI + Manual Control")
    print("=" * 60)

    from stagehand.types.agent import AgentAction, SwipeAction, TapAction, TypeAction

    agent = MobileAgent(
        device_profile="pixel_8",
        appium_url="http://localhost:4723",
    )

    try:
        await agent.connect(
            device_name="Pixel 8",
            browser_name="Chrome",
        )

        # Use AI to navigate to a page
        print("Using AI to navigate...")
        result = await agent.execute(
            instruction="Go to twitter.com (or x.com)",
            max_steps=5,
        )

        await asyncio.sleep(2)

        # Use manual gestures for precise control
        handler = agent.navigation_handler
        print("Using manual gestures to scroll...")

        # Scroll down several times
        for i in range(3):
            swipe = AgentAction(
                action_type="swipe",
                action=SwipeAction(
                    type="swipe",
                    start_x=500,
                    start_y=700,
                    end_x=500,
                    end_y=300,
                    duration_ms=400,
                )
            )
            await handler.perform_action(swipe)
            await asyncio.sleep(0.5)

        print("Scrolled through feed")

        # Use AI to analyze what's visible
        print("Using AI to analyze content...")
        result = await agent.execute(
            instruction="What topics are trending or visible on the current screen?",
            max_steps=3,
        )
        print(f"AI Analysis: {result.message}")

    finally:
        await agent.disconnect()


# =============================================================================
# Example 7: Screenshot Analysis
# =============================================================================

async def example_screenshot_analysis():
    """Take screenshots and use AI to analyze them."""
    print("=" * 60)
    print("Example: Screenshot Analysis")
    print("=" * 60)

    import base64
    from pathlib import Path

    agent = MobileAgent(
        device_profile="iphone_15_pro",
        appium_url="http://localhost:4723",
    )

    try:
        await agent.connect(
            device_name="iPhone 15 Pro",
            browser_name="Safari",
        )

        # Navigate somewhere
        await agent.execute("Go to reddit.com", max_steps=5)
        await asyncio.sleep(2)

        # Take screenshot
        screenshot_b64 = await agent.screenshot()
        print(f"Captured screenshot: {len(screenshot_b64)} characters (base64)")

        # Save to file (optional)
        screenshot_path = Path("/tmp/mobile_screenshot.png")
        screenshot_path.write_bytes(base64.b64decode(screenshot_b64))
        print(f"Saved to: {screenshot_path}")

        # Use AI to describe what's on screen
        result = await agent.execute(
            instruction="Describe what you see on the current screen. What subreddits or posts are visible?",
            max_steps=2,
        )
        print(f"\nScreen Analysis:\n{result.message}")

    finally:
        await agent.disconnect()


# =============================================================================
# Example 8: Cross-Platform Function
# =============================================================================

async def run_on_platform(platform: str, task: str):
    """Run same task on different platforms."""

    profiles = {
        "android": ("pixel_8", "Chrome", None, None),
        "ios": ("iphone_15_pro", "Safari", None, None),
    }

    if platform not in profiles:
        print(f"Unknown platform: {platform}")
        return

    profile, browser, app_pkg, bundle = profiles[platform]

    agent = MobileAgent(
        device_profile=profile,
        appium_url="http://localhost:4723",
    )

    try:
        connect_args = {"device_name": agent.device_profile.name}
        if browser:
            connect_args["browser_name"] = browser
        if app_pkg:
            connect_args["app_package"] = app_pkg
        if bundle:
            connect_args["bundle_id"] = bundle

        await agent.connect(**connect_args)

        result = await agent.execute(task)
        return result

    finally:
        await agent.disconnect()


async def example_cross_platform():
    """Run the same task on both platforms."""
    print("=" * 60)
    print("Example: Cross-Platform Execution")
    print("=" * 60)

    task = "Open google.com and search for 'mobile automation'"

    print("\nRunning on Android...")
    try:
        result = await run_on_platform("android", task)
        print(f"Android result: {result.message if result else 'Failed'}")
    except Exception as e:
        print(f"Android failed: {e}")

    print("\nRunning on iOS...")
    try:
        result = await run_on_platform("ios", task)
        print(f"iOS result: {result.message if result else 'Failed'}")
    except Exception as e:
        print(f"iOS failed: {e}")


# =============================================================================
# Main Menu
# =============================================================================

async def main():
    examples = {
        "1": ("Context Manager", example_context_manager),
        "2": ("Custom Device Profile", example_custom_profile),
        "3": ("Custom Instructions", example_custom_instructions),
        "4": ("Error Handling", example_error_handling),
        "5": ("Multi-Step Workflow", example_multi_step_workflow),
        "6": ("Hybrid AI + Manual Control", example_hybrid_control),
        "7": ("Screenshot Analysis", example_screenshot_analysis),
        "8": ("Cross-Platform Execution", example_cross_platform),
    }

    print("\nAdvanced Mobile Agent Examples")
    print("-" * 40)
    for key, (name, _) in examples.items():
        print(f"{key}. {name}")
    print()

    choice = input("Select example (1-8): ").strip()

    if choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}\n")
        await func()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY not set")
        print("Set with: export GEMINI_API_KEY=your_key_here\n")

    asyncio.run(main())
