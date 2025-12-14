# Mobile Agent Examples

Examples for using Stagehand's MobileAgent with real iOS and Android devices.

## Prerequisites

### 1. Install Dependencies

```bash
pip install stagehand[mobile]
# or
pip install "Appium-Python-Client>=4.0.0"
```

### 2. Set Up Appium Server

```bash
# Install Appium
npm install -g appium

# Install drivers
appium driver install uiautomator2  # Android
appium driver install xcuitest      # iOS

# Start server
appium server --address 127.0.0.1 --port 4723
```

### 3. Set Gemini API Key

```bash
export GEMINI_API_KEY=your_api_key_here
```

### 4. Platform-Specific Setup

#### Android
```bash
# Install Android SDK and set environment
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools

# Connect device via USB with USB debugging enabled
adb devices  # Verify device appears
```

#### iOS
```bash
# Install Xcode from App Store
xcode-select --install

# For real devices: configure signing in Xcode
# Get device UDID:
xcrun xctrace list devices
```

## Examples

### Basic Examples

| File | Description |
|------|-------------|
| `android_example.py` | Android-specific examples (Chrome, native apps, gestures) |
| `ios_example.py` | iOS-specific examples (Safari, Settings, App Store, pinch zoom) |
| `advanced_example.py` | Advanced patterns (error handling, workflows, hybrid control) |

### Quick Start

```bash
# Android
python examples/mobile/android_example.py

# iOS
python examples/mobile/ios_example.py

# Advanced examples
python examples/mobile/advanced_example.py
```

## Common Tasks

### Open Browser and Search

```python
from stagehand.agent import MobileAgent
import asyncio

async def main():
    agent = MobileAgent(
        device_profile="pixel_8",  # or "iphone_15_pro"
        appium_url="http://localhost:4723",
    )

    await agent.connect(
        device_name="Pixel 8",
        browser_name="Chrome",  # or "Safari" for iOS
    )

    result = await agent.execute("Search for 'Python tutorials' on Google")
    print(result.message)

    await agent.disconnect()

asyncio.run(main())
```

### Launch Native App

```python
# Android
await agent.connect(
    device_name="Pixel 8",
    app_package="com.whatsapp",
    app_activity=".Main",
)

# iOS
await agent.connect(
    device_name="iPhone 15 Pro",
    bundle_id="net.whatsapp.WhatsApp",
)
```

### Manual Gestures

```python
from stagehand.types.agent import AgentAction, TapAction, SwipeAction

handler = agent.navigation_handler

# Tap at center of screen
tap = AgentAction(
    action_type="tap",
    action=TapAction(type="tap", x=500, y=500)  # 0-1000 grid
)
await handler.perform_action(tap)

# Swipe up to scroll down
swipe = AgentAction(
    action_type="swipe",
    action=SwipeAction(
        type="swipe",
        start_x=500, start_y=700,
        end_x=500, end_y=300,
        duration_ms=300,
    )
)
await handler.perform_action(swipe)
```

### Use Context Manager

```python
async with MobileAgent(device_profile="pixel_8") as agent:
    await agent.connect(device_name="Pixel 8", browser_name="Chrome")
    result = await agent.execute("Go to google.com")
# Auto-disconnects
```

## Coordinate System

All coordinates use a **0-1000 grid** regardless of actual screen resolution:

```
(0, 0) ─────────────────────── (1000, 0)
  │                                 │
  │                                 │
  │          (500, 500)             │
  │           center                │
  │                                 │
  │                                 │
(0, 1000) ─────────────────── (1000, 1000)
```

## Available Device Profiles

### Android
- `pixel_8`, `pixel_8_pro`, `pixel_7`
- `samsung_galaxy_s24`, `samsung_galaxy_s24_ultra`
- `galaxy_tab_s9`

### iOS
- `iphone_15_pro`, `iphone_15`, `iphone_se`
- `iphone_14_pro_max`
- `ipad_pro_12_9`, `ipad_air`

## Troubleshooting

### "Could not find a connected Android device"
```bash
adb devices  # Check device is listed
adb kill-server && adb start-server  # Restart ADB
```

### "WebDriverAgent installation failed" (iOS)
1. Open Xcode project at `~/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj`
2. Set your development team in Signing & Capabilities
3. Build once manually

### Connection timeout
- Ensure Appium server is running: `curl http://localhost:4723/status`
- Check device screen is unlocked
- Disable any battery optimization for Appium/ADB
