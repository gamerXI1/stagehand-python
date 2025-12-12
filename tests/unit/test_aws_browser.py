"""Unit tests for AWS AgentCore Browser support."""
import unittest.mock as mock
from typing import Optional
from unittest.mock import MagicMock, AsyncMock

import pytest

from stagehand.browser import (
    _validate_aws_region,
    _validate_websocket_url,
    _create_aws_browser_client,
    _connect_aws_cdp,
    _cleanup_aws_on_failure,
    AWSBrowserClientProtocol,
    AWS_AGENTCORE_AVAILABLE,
)


class TestValidateAWSRegion:
    """Tests for _validate_aws_region function."""

    def test_valid_region_us_west_2(self):
        """Test valid US West 2 region."""
        result = _validate_aws_region("us-west-2")
        assert result == "us-west-2"

    def test_valid_region_us_east_1(self):
        """Test valid US East 1 region."""
        result = _validate_aws_region("us-east-1")
        assert result == "us-east-1"

    def test_valid_region_eu_central_1(self):
        """Test valid EU Central 1 region."""
        result = _validate_aws_region("eu-central-1")
        assert result == "eu-central-1"

    def test_valid_region_ap_southeast_2(self):
        """Test valid AP Southeast 2 region."""
        result = _validate_aws_region("ap-southeast-2")
        assert result == "ap-southeast-2"

    def test_valid_region_with_whitespace(self):
        """Test region with leading/trailing whitespace."""
        result = _validate_aws_region("  us-west-2  ")
        assert result == "us-west-2"

    def test_empty_region_raises_error(self):
        """Test empty region raises ValueError."""
        with pytest.raises(ValueError, match="aws_region is required"):
            _validate_aws_region("")

    def test_none_region_raises_error(self):
        """Test None region raises ValueError."""
        with pytest.raises(ValueError, match="aws_region is required"):
            _validate_aws_region(None)

    def test_whitespace_only_raises_error(self):
        """Test whitespace-only region raises ValueError."""
        with pytest.raises(ValueError, match="aws_region is required"):
            _validate_aws_region("   ")

    def test_invalid_format_no_number(self):
        """Test invalid region format without number."""
        with pytest.raises(ValueError, match="Invalid AWS region format"):
            _validate_aws_region("us-west")

    def test_invalid_format_uppercase(self):
        """Test invalid region format with uppercase."""
        with pytest.raises(ValueError, match="Invalid AWS region format"):
            _validate_aws_region("US-WEST-2")

    def test_invalid_format_random_string(self):
        """Test invalid region format with random string."""
        with pytest.raises(ValueError, match="Invalid AWS region format"):
            _validate_aws_region("invalid-region")

    def test_invalid_format_missing_parts(self):
        """Test invalid region format missing parts."""
        with pytest.raises(ValueError, match="Invalid AWS region format"):
            _validate_aws_region("us2")


class TestValidateWebsocketUrl:
    """Tests for _validate_websocket_url function."""

    def test_valid_wss_url(self):
        """Test valid wss:// URL."""
        result = _validate_websocket_url("wss://example.com/socket")
        assert result == "wss://example.com/socket"

    def test_valid_ws_url(self):
        """Test valid ws:// URL."""
        result = _validate_websocket_url("ws://localhost:8080/socket")
        assert result == "ws://localhost:8080/socket"

    def test_none_url_raises_error(self):
        """Test None URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="invalid WebSocket URL"):
            _validate_websocket_url(None)

    def test_empty_url_raises_error(self):
        """Test empty URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="invalid WebSocket URL"):
            _validate_websocket_url("")

    def test_non_string_url_raises_error(self):
        """Test non-string URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="invalid WebSocket URL"):
            _validate_websocket_url(12345)

    def test_http_url_raises_error(self):
        """Test HTTP URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Invalid WebSocket URL format"):
            _validate_websocket_url("http://example.com/socket")

    def test_https_url_raises_error(self):
        """Test HTTPS URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Invalid WebSocket URL format"):
            _validate_websocket_url("https://example.com/socket")


class TestCreateAWSBrowserClient:
    """Tests for _create_aws_browser_client function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = MagicMock()
        logger.debug = MagicMock()
        logger.info = MagicMock()
        return logger

    @pytest.fixture
    def mock_stagehand(self):
        """Create a mock stagehand instance."""
        stagehand = MagicMock()
        stagehand.aws_session_id = None
        return stagehand

    @mock.patch("stagehand.browser.AWS_AGENTCORE_AVAILABLE", False)
    def test_raises_when_package_not_available(self, mock_logger, mock_stagehand):
        """Test raises RuntimeError when bedrock-agentcore not installed."""
        with pytest.raises(RuntimeError, match="bedrock-agentcore"):
            _create_aws_browser_client(
                "us-west-2", None, None, mock_stagehand, mock_logger
            )

    @pytest.mark.skipif(not AWS_AGENTCORE_AVAILABLE, reason="AWS package not available")
    @mock.patch("stagehand.browser.BrowserClient")
    @mock.patch("stagehand.browser.boto3")
    def test_creates_client_with_profile(
        self, mock_boto3, mock_browser_client, mock_logger, mock_stagehand
    ):
        """Test creates client with boto3 session when profile specified."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_client = MagicMock()
        mock_client.session_id = "test-session-id"
        mock_browser_client.return_value = mock_client

        result = _create_aws_browser_client(
            "us-west-2", "my-profile", None, mock_stagehand, mock_logger
        )

        mock_boto3.Session.assert_called_once_with(profile_name="my-profile")
        mock_browser_client.assert_called_once_with(
            region="us-west-2", boto3_session=mock_session
        )
        mock_client.start.assert_called_once()

    @pytest.mark.skipif(not AWS_AGENTCORE_AVAILABLE, reason="AWS package not available")
    @mock.patch("stagehand.browser.BrowserClient")
    @mock.patch("stagehand.browser.boto3")
    def test_creates_client_without_profile(
        self, mock_boto3, mock_browser_client, mock_logger, mock_stagehand
    ):
        """Test creates client without boto3 session when no profile."""
        mock_client = MagicMock()
        mock_client.session_id = "test-session-id"
        mock_browser_client.return_value = mock_client

        result = _create_aws_browser_client(
            "us-west-2", None, None, mock_stagehand, mock_logger
        )

        mock_boto3.Session.assert_not_called()
        mock_browser_client.assert_called_once_with(region="us-west-2")
        mock_client.start.assert_called_once()

    @pytest.mark.skipif(not AWS_AGENTCORE_AVAILABLE, reason="AWS package not available")
    @mock.patch("stagehand.browser.BrowserClient")
    @mock.patch("stagehand.browser.boto3")
    def test_resumes_existing_session(
        self, mock_boto3, mock_browser_client, mock_logger, mock_stagehand
    ):
        """Test resumes existing session when session_id provided."""
        mock_client = MagicMock()
        mock_browser_client.return_value = mock_client

        result = _create_aws_browser_client(
            "us-west-2", None, "existing-session-id", mock_stagehand, mock_logger
        )

        mock_client.start.assert_not_called()
        assert mock_client.session_id == "existing-session-id"
        # Verify that generate_ws_headers was called to validate the session
        mock_client.generate_ws_headers.assert_called_once()

    @pytest.mark.skipif(not AWS_AGENTCORE_AVAILABLE, reason="AWS package not available")
    @mock.patch("stagehand.browser.BrowserClient")
    @mock.patch("stagehand.browser.boto3")
    def test_session_resume_failure(
        self, mock_boto3, mock_browser_client, mock_logger, mock_stagehand
    ):
        """Test raises error when session resume fails."""
        mock_client = MagicMock()
        mock_client.generate_ws_headers.side_effect = Exception("Session expired")
        mock_browser_client.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to resume AWS session"):
            _create_aws_browser_client(
                "us-west-2", None, "expired-session-id", mock_stagehand, mock_logger
            )

    @pytest.mark.skipif(not AWS_AGENTCORE_AVAILABLE, reason="AWS package not available")
    @mock.patch("stagehand.browser.BrowserClient")
    @mock.patch("stagehand.browser.boto3")
    def test_stores_session_id_on_stagehand(
        self, mock_boto3, mock_browser_client, mock_logger, mock_stagehand
    ):
        """Test stores new session_id on stagehand instance."""
        mock_client = MagicMock()
        mock_client.session_id = "new-session-id"
        mock_browser_client.return_value = mock_client

        _create_aws_browser_client(
            "us-west-2", None, None, mock_stagehand, mock_logger
        )

        assert mock_stagehand.aws_session_id == "new-session-id"


class TestConnectAWSCDP:
    """Tests for _connect_aws_cdp function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = MagicMock()
        logger.debug = MagicMock()
        return logger

    @pytest.fixture
    def mock_browser_client(self):
        """Create a mock browser client."""
        client = MagicMock()
        client.generate_ws_headers.return_value = (
            "wss://example.com/socket",
            {"Authorization": "Bearer token"},
        )
        return client

    @pytest.mark.asyncio
    async def test_connects_via_cdp(self, mock_logger, mock_browser_client):
        """Test connects to browser via CDP."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

        result = await _connect_aws_cdp(
            mock_playwright, mock_browser_client, mock_logger
        )

        assert result == mock_browser
        mock_playwright.chromium.connect_over_cdp.assert_called_once_with(
            "wss://example.com/socket",
            headers={"Authorization": "Bearer token"},
        )

    @pytest.mark.asyncio
    async def test_raises_on_invalid_websocket_url(self, mock_logger):
        """Test raises error on invalid WebSocket URL."""
        mock_client = MagicMock()
        mock_client.generate_ws_headers.return_value = (None, {})
        mock_playwright = MagicMock()

        with pytest.raises(RuntimeError, match="invalid WebSocket URL"):
            await _connect_aws_cdp(mock_playwright, mock_client, mock_logger)

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self, mock_logger, mock_browser_client):
        """Test raises error on connection timeout."""
        import asyncio

        mock_playwright = MagicMock()

        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(100)

        mock_playwright.chromium.connect_over_cdp = slow_connect

        with pytest.raises(RuntimeError, match="timeout"):
            await _connect_aws_cdp(
                mock_playwright, mock_browser_client, mock_logger
            )


class TestCleanupAWSOnFailure:
    """Tests for _cleanup_aws_on_failure function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.mark.asyncio
    async def test_closes_context(self, mock_logger):
        """Test closes browser context."""
        mock_context = MagicMock()
        mock_context.close = AsyncMock()

        await _cleanup_aws_on_failure(mock_context, None, None, mock_logger)

        mock_context.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_browser(self, mock_logger):
        """Test closes browser."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()

        await _cleanup_aws_on_failure(None, mock_browser, None, mock_logger)

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stops_browser_client(self, mock_logger):
        """Test stops browser client."""
        mock_client = MagicMock()
        mock_client.session_id = "test-session"

        await _cleanup_aws_on_failure(None, None, mock_client, mock_logger)

        mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_context_close_error(self, mock_logger):
        """Test handles error when closing context."""
        mock_context = MagicMock()
        mock_context.close = AsyncMock(side_effect=Exception("Close failed"))

        await _cleanup_aws_on_failure(mock_context, None, None, mock_logger)

        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_browser_close_error(self, mock_logger):
        """Test handles error when closing browser."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock(side_effect=Exception("Close failed"))

        await _cleanup_aws_on_failure(None, mock_browser, None, mock_logger)

        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_client_stop_error(self, mock_logger):
        """Test handles error when stopping client."""
        mock_client = MagicMock()
        mock_client.session_id = "test-session"
        mock_client.stop.side_effect = Exception("Stop failed")

        await _cleanup_aws_on_failure(None, None, mock_client, mock_logger)

        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleans_all_resources(self, mock_logger):
        """Test cleans up all resources in order."""
        mock_context = MagicMock()
        mock_context.close = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        mock_client = MagicMock()
        mock_client.session_id = "test-session"

        await _cleanup_aws_on_failure(
            mock_context, mock_browser, mock_client, mock_logger
        )

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_none_resources(self, mock_logger):
        """Test handles None resources gracefully."""
        # Should not raise any errors
        await _cleanup_aws_on_failure(None, None, None, mock_logger)


class TestAWSBrowserClientProtocol:
    """Tests for AWSBrowserClientProtocol."""

    def test_protocol_attributes(self):
        """Test protocol defines expected attributes."""
        # Create a class that implements the protocol
        class MockBrowserClient:
            session_id: Optional[str] = None

            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

            def generate_ws_headers(self) -> tuple[str, dict[str, str]]:
                return ("ws://example.com", {})

        client = MockBrowserClient()
        assert isinstance(client, AWSBrowserClientProtocol)

    def test_protocol_missing_method(self):
        """Test protocol check fails for incomplete implementation."""

        class IncompleteBrowserClient:
            session_id: Optional[str] = None

            def start(self) -> None:
                pass
            # Missing stop() and generate_ws_headers()

        client = IncompleteBrowserClient()
        assert not isinstance(client, AWSBrowserClientProtocol)
