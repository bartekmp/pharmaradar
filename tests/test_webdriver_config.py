"""
Tests for WebDriver configuration and low-I/O Chrome settings.
"""

from unittest.mock import MagicMock, patch

import pharmaradar.webdriver_utils as webdriver_utils
from pharmaradar.webdriver_utils import WebDriverUtils


class TestChromeProfileDir:
    """Test that the Chrome profile directory defaults to /dev/shm."""

    def test_default_profile_dir_is_ram_backed(self):
        assert webdriver_utils.CHROME_USER_DATA_DIR.startswith("/dev/shm"), (
            f"Default Chrome profile dir should be on /dev/shm to avoid disk I/O, "
            f"got: {webdriver_utils.CHROME_USER_DATA_DIR}"
        )

    def test_profile_dir_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("PHARMARADAR_CHROME_PROFILE_DIR", "/tmp/custom-profile")
        import importlib

        importlib.reload(webdriver_utils)
        assert webdriver_utils.CHROME_USER_DATA_DIR == "/tmp/custom-profile"
        # Restore
        monkeypatch.delenv("PHARMARADAR_CHROME_PROFILE_DIR", raising=False)
        importlib.reload(webdriver_utils)


class TestChromeOptions:
    """Test that Chrome is configured to minimise disk I/O."""

    def _get_args(self) -> list[str]:
        options = WebDriverUtils.get_chrome_options(headless=True)
        return options.arguments

    def test_disk_cache_size_is_limited(self):
        args = self._get_args()
        assert (
            "--disk-cache-size=1" in args
        ), "--disk-cache-size=1 must be set to prevent Chrome HTTP cache from writing to disk"

    def test_media_cache_size_is_limited(self):
        args = self._get_args()
        assert (
            "--media-cache-size=1" in args
        ), "--media-cache-size=1 must be set to prevent Chrome media cache from writing to disk"

    def test_aggressive_cache_discard_enabled(self):
        args = self._get_args()
        assert "--aggressive-cache-discard" in args

    def test_user_data_dir_points_to_profile_constant(self):
        args = self._get_args()
        expected = f"--user-data-dir={webdriver_utils.CHROME_USER_DATA_DIR}"
        assert expected in args


class TestWebDriverAvailabilityCheck:
    """Test that is_webdriver_available() reuses the shared driver manager."""

    def test_uses_shared_driver_manager_not_new_instance(self):
        """is_webdriver_available() must not spin up a second WebDriverManager."""
        from pharmaradar.medicine_scraper import MedicineFinder

        finder = MedicineFinder.__new__(MedicineFinder)
        finder._webdriver_available = None
        finder.log = MagicMock()

        mock_manager = MagicMock()
        mock_manager.get_driver.return_value = MagicMock()
        finder.driver_manager = mock_manager

        with patch("pharmaradar.medicine_scraper.WebDriverManager") as MockWDM:
            result = finder.is_webdriver_available()

        # Must not have constructed a new WebDriverManager
        MockWDM.assert_not_called()
        # Must have used the existing driver_manager
        mock_manager.get_driver.assert_called_once()
        assert result is True

    def test_result_is_cached(self):
        from pharmaradar.medicine_scraper import MedicineFinder

        finder = MedicineFinder.__new__(MedicineFinder)
        finder._webdriver_available = None
        finder.log = MagicMock()

        mock_manager = MagicMock()
        mock_manager.get_driver.return_value = MagicMock()
        finder.driver_manager = mock_manager

        finder.is_webdriver_available()
        finder.is_webdriver_available()

        # get_driver should only be called once; second call uses the cache
        mock_manager.get_driver.assert_called_once()

    def test_returns_false_on_driver_error(self):
        from pharmaradar.medicine_scraper import MedicineFinder

        finder = MedicineFinder.__new__(MedicineFinder)
        finder._webdriver_available = None
        finder.log = MagicMock()

        mock_manager = MagicMock()
        mock_manager.get_driver.side_effect = RuntimeError("No WebDriver available")
        finder.driver_manager = mock_manager

        result = finder.is_webdriver_available()
        assert result is False
        assert finder._webdriver_available is False
