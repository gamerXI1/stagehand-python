import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from browserbase import Browserbase
from browserbase.types import SessionCreateParams as BrowserbaseSessionCreateParams
from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
)

from .context import StagehandContext
from .logging import StagehandLogger
from .page import StagehandPage

# AWS AgentCore Browser support - import conditionally
try:
    from bedrock_agentcore.tools.browser_client import BrowserClient
    AWS_AGENTCORE_AVAILABLE = True
except ImportError:
    AWS_AGENTCORE_AVAILABLE = False
    BrowserClient = None


async def connect_browserbase_browser(
    playwright: Playwright,
    session_id: str,
    browserbase_api_key: str,
    stagehand_instance: Any,
    logger: StagehandLogger,
) -> tuple[Browser, BrowserContext, StagehandContext, StagehandPage]:
    """
    Connect to a Browserbase remote browser session.

    Args:
        playwright: The Playwright instance
        session_id: The Browserbase session ID
        browserbase_api_key: The Browserbase API key
        stagehand_instance: The Stagehand instance (for context initialization)
        logger: The logger instance

    Returns:
        tuple of (browser, context, stagehand_context, page)
    """
    # Connect to remote browser via Browserbase SDK and CDP
    bb = Browserbase(api_key=browserbase_api_key)
    try:
        if session_id:
            session = bb.sessions.retrieve(session_id)
            if session.status != "RUNNING":
                raise RuntimeError(
                    f"Browserbase session {session_id} is not running (status: {session.status})"
                )
        else:
            browserbase_session_create_params = (
                BrowserbaseSessionCreateParams(
                    project_id=stagehand_instance.browserbase_project_id,
                    browser_settings={
                        "viewport": {
                            "width": 1288,
                            "height": 711,
                        },
                    },
                )
                if not stagehand_instance.browserbase_session_create_params
                else stagehand_instance.browserbase_session_create_params
            )
            session = bb.sessions.create(**browserbase_session_create_params)
            if not session.id:
                raise Exception("Could not create Browserbase session")
            stagehand_instance.session_id = session.id
        connect_url = session.connectUrl
    except Exception as e:
        logger.error(f"Error retrieving or validating Browserbase session: {str(e)}")
        raise

    logger.debug(f"Connecting to remote browser at: {connect_url}")
    try:
        browser = await playwright.chromium.connect_over_cdp(connect_url)
    except Exception as e:
        logger.error(f"Failed to connect Playwright via CDP: {str(e)}")
        raise

    existing_contexts = browser.contexts
    logger.debug(f"Existing contexts in remote browser: {len(existing_contexts)}")
    if existing_contexts:
        context = existing_contexts[0]
    else:
        # This case might be less common with Browserbase but handle it
        logger.warning(
            "No existing context found in remote browser, creating a new one."
        )
        context = await browser.new_context()

    stagehand_context = await StagehandContext.init(context, stagehand_instance)

    # Access or create a page via StagehandContext
    existing_pages = context.pages
    logger.debug(f"Existing pages in context: {len(existing_pages)}")
    if existing_pages:
        logger.debug("Using existing page via StagehandContext")
        page = await stagehand_context.get_stagehand_page(existing_pages[0])
    else:
        logger.debug("Creating a new page via StagehandContext")
        page = await stagehand_context.new_page()

    return browser, context, stagehand_context, page


async def connect_aws_agentcore_browser(
    playwright: Playwright,
    aws_region: str,
    aws_profile: Optional[str],
    aws_session_id: Optional[str],
    stagehand_instance: Any,
    logger: StagehandLogger,
) -> tuple[Browser, BrowserContext, StagehandContext, StagehandPage, Any]:
    """
    Connect to an AWS AgentCore Browser session.

    Args:
        playwright: The Playwright instance
        aws_region: AWS region for AgentCore Browser (e.g., 'us-west-2')
        aws_profile: Optional AWS profile name for credentials (uses boto3 default credential chain)
        aws_session_id: Optional session ID for resuming existing sessions (EXPERIMENTAL - not yet tested)
        stagehand_instance: The Stagehand instance (for context initialization)
        logger: The logger instance

    Returns:
        tuple of (browser, context, stagehand_context, page, browser_client)

    Raises:
        RuntimeError: If bedrock-agentcore package is not installed
        ValueError: If aws_region is invalid or missing
        asyncio.TimeoutError: If CDP connection times out
    """
    import asyncio
    import re

    if not AWS_AGENTCORE_AVAILABLE:
        raise RuntimeError(
            "AWS AgentCore Browser support requires the 'bedrock-agentcore' package. "
            "Install it with: pip install stagehand[aws]"
        )

    # Validate region format and presence
    if not aws_region or not aws_region.strip():
        raise ValueError(
            "aws_region is required for AWS environment. "
            "Set it via config.aws_region or AWS_REGION environment variable."
        )

    # Validate AWS region format (e.g., us-west-2, eu-central-1)
    if not re.match(r'^[a-z]{2}-[a-z]+-\d+$', aws_region.strip()):
        raise ValueError(
            f"Invalid AWS region format: '{aws_region}'. "
            "Expected format: 'us-west-2', 'eu-central-1', etc."
        )

    logger.info(f"Connecting to AWS AgentCore Browser in region: {aws_region}")

    # Initialize cleanup tracking
    browser_client = None
    browser = None
    context = None

    try:
        # Note: AWS credentials are handled by boto3's default credential chain
        # which checks (in order): environment variables, AWS config files, IAM roles, etc.
        # If aws_profile is provided, boto3 will use it automatically via AWS_PROFILE env var
        # or ~/.aws/credentials. We don't set os.environ to avoid global state mutation.
        if aws_profile:
            logger.debug(f"Using AWS profile: {aws_profile} (via boto3 credential chain)")
            logger.warning(
                "AWS profile support depends on your boto3 configuration. "
                "Ensure ~/.aws/credentials or environment variables are properly set."
            )

        # Create browser session client
        browser_client = BrowserClient(region=aws_region)

        # Handle session creation or resumption
        if aws_session_id:
            logger.warning(
                "AWS session resume is EXPERIMENTAL and not fully tested. "
                "If connection fails, remove aws_session_id to create a new session."
            )
            logger.info(f"Attempting to resume AWS AgentCore Browser session: {aws_session_id}")
            browser_client.session_id = aws_session_id
            # TODO: Add session validation when BrowserClient API supports it
            # Currently we assume session_id assignment works, but this may fail during CDP connection
        else:
            logger.info("Starting new AWS AgentCore Browser session...")
            browser_client.start()
            logger.info(f"AWS session created with ID: {browser_client.session_id}")
            stagehand_instance.aws_session_id = browser_client.session_id

        # Generate WebSocket URL and authentication headers
        # Note: Despite the method name, this returns (websocket_url, auth_headers) tuple
        ws_url, headers = browser_client.generate_ws_headers()
        logger.debug("Generated WebSocket URL and authentication headers for CDP connection")

        # Validate WebSocket URL
        if not ws_url or not isinstance(ws_url, str):
            raise RuntimeError(
                f"BrowserClient.generate_ws_headers() returned invalid WebSocket URL: {ws_url}"
            )
        if not ws_url.startswith(('ws://', 'wss://')):
            raise RuntimeError(
                f"Invalid WebSocket URL format (expected ws:// or wss://): {ws_url}"
            )

        # Connect to remote browser via CDP with timeout
        logger.debug("Connecting to AWS AgentCore Browser via CDP...")
        try:
            browser = await asyncio.wait_for(
                playwright.chromium.connect_over_cdp(ws_url, headers=headers),
                timeout=30.0  # 30 second timeout to match Playwright init timeout
            )
        except asyncio.TimeoutError:
            logger.error("Timeout connecting to AWS AgentCore Browser (30s)")
            raise RuntimeError(
                "AWS AgentCore Browser connection timeout after 30 seconds. "
                "Check your network connection and AWS region availability."
            )

        # Get existing context (AWS AgentCore Browser creates a default context)
        existing_contexts = browser.contexts
        logger.debug(f"Existing contexts in AWS browser: {len(existing_contexts)}")
        if existing_contexts:
            context = existing_contexts[0]
        else:
            logger.warning(
                "No existing context found in AWS browser, creating a new one."
            )
            context = await browser.new_context()

        # Initialize Stagehand context wrapper
        stagehand_context = await StagehandContext.init(context, stagehand_instance)

        # Access or create a page via StagehandContext
        existing_pages = context.pages
        logger.debug(f"Existing pages in AWS context: {len(existing_pages)}")
        if existing_pages:
            logger.debug("Using existing page via StagehandContext")
            page = await stagehand_context.get_stagehand_page(existing_pages[0])
        else:
            logger.debug("Creating a new page via StagehandContext")
            page = await stagehand_context.new_page()

        return browser, context, stagehand_context, page, browser_client

    except Exception as e:
        # Comprehensive cleanup on any failure
        logger.error(f"Failed to connect to AWS AgentCore Browser: {str(e)}")

        # Clean up in reverse order of creation
        if context:
            try:
                logger.debug("Cleaning up browser context after failure...")
                await context.close()
            except Exception as cleanup_error:
                logger.warning(f"Failed to close context during cleanup: {cleanup_error}")

        if browser:
            try:
                logger.debug("Cleaning up browser connection after failure...")
                await browser.close()
            except Exception as cleanup_error:
                logger.warning(f"Failed to close browser during cleanup: {cleanup_error}")

        if browser_client:
            try:
                logger.debug("Stopping AWS browser session after failure...")
                browser_client.stop()
                logger.debug("AWS browser session stopped")
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to stop AWS browser client during cleanup: {cleanup_error}. "
                    f"AWS session may still be running. Check AWS console for session: {browser_client.session_id if hasattr(browser_client, 'session_id') else 'unknown'}"
                )

        # Re-raise the original exception
        raise


async def connect_local_browser(
    playwright: Playwright,
    local_browser_launch_options: dict[str, Any],
    stagehand_instance: Any,
    logger: StagehandLogger,
) -> tuple[
    Optional[Browser], BrowserContext, StagehandContext, StagehandPage, Optional[Path]
]:
    """
    Connect to a local browser via CDP or launch a new browser context.

    Args:
        playwright: The Playwright instance
        local_browser_launch_options: Options for launching the local browser
        stagehand_instance: The Stagehand instance (for context initialization)
        logger: The logger instance

    Returns:
        tuple of (browser, context, stagehand_context, page, temp_user_data_dir)
    """
    cdp_url = local_browser_launch_options.get("cdp_url")
    temp_user_data_dir = None

    if cdp_url:
        logger.info(f"Connecting to local browser via CDP URL: {cdp_url}")
        try:
            browser = await playwright.chromium.connect_over_cdp(
                cdp_url, headers=local_browser_launch_options.get("headers")
            )

            if not browser.contexts:
                raise RuntimeError(f"No browser contexts found at CDP URL: {cdp_url}")
            context = browser.contexts[0]
            stagehand_context = await StagehandContext.init(context, stagehand_instance)
            logger.debug(f"Connected via CDP. Using context: {context}")
        except Exception as e:
            logger.error(f"Failed to connect via CDP URL ({cdp_url}): {str(e)}")
            raise
    else:
        logger.info("Launching new local browser context...")
        browser = None

        user_data_dir_option = local_browser_launch_options.get("user_data_dir")
        if user_data_dir_option:
            user_data_dir = Path(user_data_dir_option).resolve()
        else:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="stagehand_ctx_")
            temp_user_data_dir = Path(temp_dir)
            user_data_dir = temp_user_data_dir
            # Create Default profile directory and Preferences file like in TS
            default_profile_path = user_data_dir / "Default"
            default_profile_path.mkdir(parents=True, exist_ok=True)
            prefs_path = default_profile_path / "Preferences"
            default_prefs = {"plugins": {"always_open_pdf_externally": True}}
            try:
                with open(prefs_path, "w") as f:
                    json.dump(default_prefs, f)
                logger.debug(
                    f"Created temporary user_data_dir with default preferences: {user_data_dir}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to write default preferences to {prefs_path}: {e}"
                )

        downloads_path_option = local_browser_launch_options.get("downloads_path")
        if downloads_path_option:
            downloads_path = str(Path(downloads_path_option).resolve())
        else:
            downloads_path = str(Path.cwd() / "downloads")
        try:
            os.makedirs(downloads_path, exist_ok=True)
            logger.debug(f"Using downloads_path: {downloads_path}")
        except Exception as e:
            logger.error(f"Failed to create downloads_path {downloads_path}: {e}")

        # Prepare Launch Options (translate keys if needed)
        launch_options = {
            "headless": local_browser_launch_options.get(
                "headless", stagehand_instance.config.headless
            ),
            "accept_downloads": local_browser_launch_options.get(
                "acceptDownloads", True
            ),
            "downloads_path": downloads_path,
            "args": local_browser_launch_options.get(
                "args",
                [
                    "--disable-blink-features=AutomationControlled",
                ],
            ),
            "viewport": local_browser_launch_options.get(
                "viewport", {"width": 1288, "height": 711}
            ),
            "locale": local_browser_launch_options.get("locale", "en-US"),
            "timezone_id": local_browser_launch_options.get(
                "timezoneId", "America/New_York"
            ),
            "bypass_csp": local_browser_launch_options.get("bypassCSP", True),
            "proxy": local_browser_launch_options.get("proxy"),
            "ignore_https_errors": local_browser_launch_options.get(
                "ignoreHTTPSErrors", True
            ),
        }
        launch_options = {k: v for k, v in launch_options.items() if v is not None}

        # Launch Context
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(user_data_dir),  # Needs to be string path
                **launch_options,
            )
            stagehand_context = await StagehandContext.init(context, stagehand_instance)
            logger.info("Local browser context launched successfully.")
            browser = context.browser

        except Exception as e:
            logger.error(f"Failed to launch local browser context: {str(e)}")
            if temp_user_data_dir:
                try:
                    shutil.rmtree(temp_user_data_dir)
                except Exception:
                    pass
            raise

        cookies = local_browser_launch_options.get("cookies")
        if cookies:
            try:
                await context.add_cookies(cookies)
                logger.debug(f"Added {len(cookies)} cookies to the context.")
            except Exception as e:
                logger.error(f"Failed to add cookies: {e}")

    # Apply stealth scripts
    await apply_stealth_scripts(context, logger)

    # Get the initial page (usually one is created by default)
    if context.pages:
        playwright_page = context.pages[0]
        logger.debug("Using initial page from local context.")
        page = await stagehand_context.get_stagehand_page(playwright_page)
    else:
        logger.debug("No initial page found, creating a new one.")
        page = await stagehand_context.new_page()

    return browser, context, stagehand_context, page, temp_user_data_dir


async def apply_stealth_scripts(context: BrowserContext, logger: StagehandLogger):
    """Applies JavaScript init scripts to make the browser less detectable."""
    logger.debug("Applying stealth scripts to the context...")
    stealth_script = """
    (() => {
        // Override navigator.webdriver
        if (navigator.webdriver) {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        }

        // Mock languages and plugins
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Avoid complex plugin mocking, just return a non-empty array like structure
        if (navigator.plugins instanceof PluginArray && navigator.plugins.length === 0) {
             Object.defineProperty(navigator, 'plugins', {
                get: () => Object.values({
                    'plugin1': { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    'plugin2': { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    'plugin3': { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                }),
            });
        }

        // Remove Playwright-specific properties from window
        try {
            delete window.__playwright_run; // Example property, check actual properties if needed
            delete window.navigator.__proto__.webdriver; // Another common place
        } catch (e) {}

        // Override permissions API (example for notifications)
        if (window.navigator && window.navigator.permissions) {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                if (parameters && parameters.name === 'notifications') {
                    return Promise.resolve({ state: Notification.permission });
                }
                // Call original for other permissions
                return originalQuery.apply(window.navigator.permissions, [parameters]);
            };
        }
    })();
    """
    try:
        await context.add_init_script(stealth_script)
    except Exception as e:
        logger.error(f"Failed to add stealth init script: {str(e)}")


async def cleanup_browser_resources(
    browser: Optional[Browser],
    context: Optional[BrowserContext],
    playwright: Optional[Playwright],
    temp_user_data_dir: Optional[Path],
    logger: StagehandLogger,
    aws_browser_client: Optional[Any] = None,
):
    """
    Clean up browser resources.

    Args:
        browser: The browser instance (if any)
        context: The browser context
        playwright: The Playwright instance
        temp_user_data_dir: Temporary user data directory to remove (if any)
        logger: The logger instance
        aws_browser_client: AWS AgentCore BrowserClient instance (if any)
    """
    # Clean up AWS browser client first if it exists
    if aws_browser_client:
        try:
            logger.debug("Stopping AWS AgentCore Browser session...")
            aws_browser_client.stop()
            logger.debug("AWS AgentCore Browser session stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping AWS browser client: {str(e)}")

    if context:
        try:
            logger.debug("Closing browser context...")
            await context.close()
        except Exception as e:
            logger.error(f"Error closing context: {str(e)}")
    if browser:
        try:
            logger.debug("Closing browser...")
            await browser.close()
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")

    # Clean up temporary user data directory if created
    if temp_user_data_dir:
        try:
            logger.debug(
                f"Removing temporary user data directory: {temp_user_data_dir}"
            )
            shutil.rmtree(temp_user_data_dir)
        except Exception as e:
            logger.error(
                f"Error removing temporary directory {temp_user_data_dir}: {str(e)}"
            )

    if playwright:
        try:
            logger.debug("Stopping Playwright...")
            await playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping Playwright: {str(e)}")
