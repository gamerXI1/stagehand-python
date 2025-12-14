#!/usr/bin/env python3
"""
Mobile Agent Quick Start

A simple script to verify your setup is working.
Run this first before trying the more complex examples.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def check_prerequisites():
    """Check that all prerequisites are met."""
    print("Checking prerequisites...")
    print()

    issues = []

    # Check Gemini API key
    if os.getenv("GEMINI_API_KEY"):
        print("  [OK] GEMINI_API_KEY is set")
    else:
        print("  [!!] GEMINI_API_KEY not set")
        issues.append("Set GEMINI_API_KEY: export GEMINI_API_KEY=your_key")

    # Check Appium server
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:4723/status", timeout=2) as resp:
            if resp.status == 200:
                print("  [OK] Appium server is running")
            else:
                print("  [!!] Appium server returned non-200")
                issues.append("Check Appium server")
    except Exception:
        print("  [!!] Appium server not running")
        issues.append("Start Appium: appium server --port 4723")

    # Check ADB (Android)
    import shutil
    if shutil.which("adb"):
        print("  [OK] ADB is installed")

        # Check for connected devices
        import subprocess
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = [l for l in result.stdout.strip().split("\n")[1:] if l.strip()]
        if lines:
            print(f"  [OK] Android device(s) connected: {len(lines)}")
            for line in lines:
                print(f"       - {line.split()[0]}")
        else:
            print("  [--] No Android devices connected")
    else:
        print("  [--] ADB not found (Android testing not available)")

    # Check imports
    try:
        from stagehand.agent import MobileAgent
        from stagehand.types.mobile import DEVICE_PROFILES
        print("  [OK] Stagehand mobile imports work")
    except ImportError as e:
        print(f"  [!!] Import error: {e}")
        issues.append("Install: pip install stagehand[mobile]")

    print()

    if issues:
        print("Issues to resolve:")
        for issue in issues:
            print(f"  - {issue}")
        print()
        return False

    return True


async def test_connection(platform: str):
    """Test basic connection to a device."""
    from stagehand.agent import MobileAgent

    print(f"\nTesting {platform} connection...")

    if platform == "android":
        agent = MobileAgent(
            device_profile="pixel_8",
            appium_url="http://localhost:4723",
        )
        connect_kwargs = {
            "device_name": "Pixel 8",  # Will be overridden by actual device
            "browser_name": "Chrome",
        }
    else:
        agent = MobileAgent(
            device_profile="iphone_15_pro",
            appium_url="http://localhost:4723",
        )
        connect_kwargs = {
            "device_name": "iPhone 15 Pro",
            "browser_name": "Safari",
        }

    try:
        await asyncio.wait_for(agent.connect(**connect_kwargs), timeout=30.0)
        print(f"  [OK] Connected to {agent.device_profile.name}")
        print(f"  [OK] Viewport: {agent.appium_client.viewport_width}x{agent.appium_client.viewport_height}")

        # Take a screenshot
        screenshot = await agent.screenshot()
        print(f"  [OK] Screenshot captured: {len(screenshot)} bytes")

        # Simple AI test
        print("  [..] Testing AI command (this may take a few seconds)...")
        result = await agent.execute(
            instruction="What do you see on the screen? Just describe briefly.",
            max_steps=2,
        )
        print(f"  [OK] AI response: {result.message[:100]}...")

        await agent.disconnect()
        print(f"  [OK] Disconnected")
        return True

    except asyncio.TimeoutError:
        print(f"  [!!] Connection timed out")
        print("       Make sure device is connected and unlocked")
        return False
    except Exception as e:
        print(f"  [!!] Error: {e}")
        return False
    finally:
        if agent.is_connected:
            await agent.disconnect()


async def main():
    print("=" * 60)
    print("Mobile Agent Quick Start")
    print("=" * 60)
    print()

    # Check prerequisites
    if not check_prerequisites():
        print("Please resolve the issues above and try again.")
        return

    print("Prerequisites OK!")
    print()

    # Ask which platform to test
    print("Which platform would you like to test?")
    print("1. Android")
    print("2. iOS")
    print("3. Both")
    print()

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        await test_connection("android")
    elif choice == "2":
        await test_connection("ios")
    elif choice == "3":
        await test_connection("android")
        await test_connection("ios")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
