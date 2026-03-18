"""
Test module for Selenium-based medicine scraper functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from pharmaradar import Medicine, MedicineFinder
from pharmaradar.availability_level import AvailabilityLevel
from pharmaradar.pharmacy_info import PharmacyInfo
from pharmaradar.scraping_utils import PageNavigator, PharmacyFilter


class TestMedicineScraper:
    """Test the Selenium-based medicine scraper functionality."""

    def test_initialization_basic(self):
        """Test basic initialization."""
        scraper = MedicineFinder()
        assert scraper.headless
        assert scraper.timeout == 15
        assert scraper.driver is None

    @patch("pharmaradar.webdriver_utils.webdriver.Chrome")
    def test_get_webdriver_chrome_success(self, mock_chrome):
        """Test successful Chrome WebDriver creation."""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        scraper = MedicineFinder()
        driver = scraper.driver_manager.get_driver()

        assert driver == mock_driver
        mock_chrome.assert_called_once()

    @patch("pharmaradar.webdriver_utils.webdriver.Chrome")
    def test_get_webdriver_chrome_fails(self, mock_chrome):
        """Test exception when Chrome fails (no Firefox fallback in containers)."""
        mock_chrome.side_effect = Exception("Chrome not available")

        scraper = MedicineFinder()

        with pytest.raises(Exception):
            scraper.driver_manager.get_driver()

        mock_chrome.assert_called()

    def test_close_driver(self):
        """Test closing the WebDriver."""
        mock_driver = MagicMock()

        scraper = MedicineFinder()
        scraper.driver_manager.driver = mock_driver
        scraper.close()

        mock_driver.quit.assert_called_once()
        assert scraper.driver_manager.driver is None

    def test_close_driver_with_exception(self):
        """Test closing WebDriver when quit() raises exception."""
        mock_driver = MagicMock()
        mock_driver.quit.side_effect = Exception("Quit failed")

        scraper = MedicineFinder()
        scraper.driver_manager.driver = mock_driver
        scraper.close()  # Should not raise exception

        mock_driver.quit.assert_called_once()
        assert scraper.driver_manager.driver is None

    def test_context_manager(self):
        """Test using scraper as context manager."""
        with patch.object(MedicineFinder, "close") as mock_close:
            with MedicineFinder() as scraper:
                assert isinstance(scraper, MedicineFinder)
            mock_close.assert_called_once()

    def test_dismiss_cookie_popup(self):
        """Test dismissing cookie popup."""
        mock_driver = MagicMock()
        mock_button = MagicMock()
        mock_button.is_displayed.return_value = True
        mock_driver.find_element.return_value = mock_button

        result = PageNavigator.dismiss_cookie_popup(mock_driver)

        # Should try to find and click cookie button
        mock_driver.find_element.assert_called()
        mock_button.click.assert_called()
        assert result

    def test_clean_text(self):
        """Test text cleaning utility."""
        scraper = MedicineFinder()

        # Test normal text
        assert scraper._clean_text("APTEKA TEST") == "APTEKA TEST"

        # Test with extra whitespace
        assert scraper._clean_text("  APTEKA TEST  ") == "APTEKA TEST"

        # Test with HTML entities
        assert scraper._clean_text("APTEKA&nbsp;TEST") == "APTEKA TEST"

        # Test empty text
        assert scraper._clean_text("") == ""

    @patch("pharmaradar.webdriver_utils.webdriver.Chrome")
    def test_test_connection_success(self, mock_chrome):
        """Test successful connection test."""
        mock_driver = MagicMock()
        mock_body = MagicMock()
        mock_body.text = "Page content"
        mock_driver.find_element.return_value = mock_body
        mock_chrome.return_value = mock_driver

        scraper = MedicineFinder()
        result = scraper.test_connection()

        assert result
        mock_driver.get.assert_called()
        mock_driver.quit.assert_called_once()

    @patch("pharmaradar.webdriver_utils.webdriver.Chrome")
    def test_test_connection_failure(self, mock_chrome):
        """Test connection test failure (Chrome-only in containers)."""
        mock_chrome.side_effect = Exception("WebDriver failed")

        scraper = MedicineFinder()
        result = scraper.test_connection()

        assert not result

    @patch.object(MedicineFinder, "_set_location_via_js")
    @patch.object(MedicineFinder, "_extract_pharmacy_results")
    @patch("pharmaradar.medicine_scraper.WebDriverManager")
    def test_search_medicine_success(self, mock_manager_class, mock_extract, mock_set_location):
        """Test successful medicine search."""
        expected_pharmacies = [
            PharmacyInfo(
                name="Test Pharmacy",
                address="Test Address",
                phone="123-456-789",
                availability=AvailabilityLevel.LOW,
                price_full=15.99,
                opening_hours="8:00-20:00",
                distance_km=2.5,
            )
        ]
        mock_extract.return_value = expected_pharmacies
        mock_set_location.return_value = True

        # Mock the driver manager
        mock_manager = MagicMock()
        mock_driver = MagicMock()
        mock_manager.get_driver.return_value = mock_driver
        mock_manager_class.return_value = mock_manager

        medicine = Medicine(name="Test Medicine", location="Test Location")

        scraper = MedicineFinder()
        result = scraper.search_medicine(medicine)

        assert result == expected_pharmacies
        mock_driver.get.assert_called_once()
        mock_set_location.assert_called_once_with(mock_driver, "Test Location")
        mock_extract.assert_called_once_with(mock_driver, medicine)

    @patch.object(MedicineFinder, "is_webdriver_available")
    def test_search_medicine_failure(self, mock_is_available):
        """Test medicine search with WebDriver failure."""
        mock_is_available.return_value = False

        medicine = Medicine(name="Test Medicine", location="Test Location")

        scraper = MedicineFinder()
        result = scraper.search_medicine(medicine)

        assert result == []

    def test_extract_pharmacy_results(self):
        """Test extracting pharmacy results from page."""
        mock_driver = MagicMock()
        mock_element = MagicMock()
        mock_element.text = """Znajdź leki w okolicy i zarezerwuj
252 m
APTEKA GEMINI
Gdańsk, Rakoczego 9,11 U13, U14
Wyświetl numer
Zamknięta, zapraszamy jutro (08:00 – 20:00)"""

        # Mock the complex DOM investigation part
        mock_driver.find_element.return_value = MagicMock()
        mock_driver.find_elements.return_value = []  # No medicine elements found

        medicine = Medicine(name="Test Medicine", location="Test Location")

        scraper = MedicineFinder()
        result = scraper._extract_pharmacy_results(mock_driver, medicine)

        # Should return empty list since no medicine elements are found
        assert len(result) == 0

    def test_extract_pharmacies_from_pharmacy_page(self):
        """Test extracting pharmacy data from pharmacy page text."""
        mock_driver = MagicMock()
        mock_element = MagicMock()
        mock_element.text = """Znajdź leki w okolicy i zarezerwuj
252 m
APTEKA GEMINI
Gdańsk, Rakoczego 9,11 U13, U14
Wyświetl numer
Zamknięta, zapraszamy jutro (08:00 – 20:00)"""
        mock_element.is_displayed.return_value = True

        # Mock finding elements for phone and reservation
        mock_element.find_elements.return_value = []

        # Mock the driver.find_elements to return our mock element when the right selector is used
        def mock_find_elements(by, selector):
            if "result" in selector:  # This matches "div[class*='result']"
                return [mock_element]
            return []

        mock_driver.find_elements.side_effect = mock_find_elements

        medicine = Medicine(name="Test Medicine", location="Test Location")

        scraper = MedicineFinder()
        result = scraper._extract_pharmacies_from_pharmacy_page(mock_driver, medicine)

        assert len(result) == 1
        assert result[0].name == "APTEKA GEMINI"
        assert result[0].address == "Gdańsk, Rakoczego 9,11 U13, U14"
        assert result[0].distance_km == 0.252

    def test_filter_and_sort_pharmacies_top_10_only(self):
        """Test filtering when we have 10 or fewer pharmacies."""
        pharmacies = [
            PharmacyInfo(
                name=f"Pharmacy {i}",
                address=f"Address {i}",
                distance_km=i * 0.5,
                availability=AvailabilityLevel.LOW,
                phone=None,
                price_full=None,
                opening_hours=None,
            )
            for i in range(1, 6)
        ]
        result = PharmacyFilter.filter_and_sort_pharmacies(pharmacies, Medicine(name="test", location="test"))

        assert len(result) == 5
        assert result[0].distance_km == 0.5  # Closest first
        assert result[-1].distance_km == 2.5  # Furthest last

    def test_filter_and_sort_pharmacies_with_extension(self):
        """Test filtering with extended high-availability pharmacies when top 10 don't have high availability."""
        # Create 12 pharmacies - 10 close ones WITHOUT high availability, 2 far ones with high availability
        pharmacies = []

        # First 10 - close but NO high availability
        for i in range(1, 11):
            pharmacies.append(
                PharmacyInfo(
                    name=f"Close Pharmacy {i}",
                    address=f"Address {i}",
                    distance_km=i * 0.3,
                    availability=AvailabilityLevel.LOW,  # NOT HIGH
                    phone=None,
                    price_full=None,
                    opening_hours=None,
                )
            )

        # 2 additional - farther but with HIGH availability (within 2x distance of 10th)
        pharmacies.append(
            PharmacyInfo(
                name="Far High Availability 1",
                address="Far Address 1",
                distance_km=4.0,  # Within 2x of 10th pharmacy (3.0km * 2 = 6.0km)
                availability=AvailabilityLevel.HIGH,
                phone=None,
                price_full=None,
                opening_hours=None,
            )
        )
        pharmacies.append(
            PharmacyInfo(
                name="Far High Availability 2",
                address="Far Address 2",
                distance_km=5.0,
                availability=AvailabilityLevel.HIGH,
                phone=None,
                price_full=None,
                opening_hours=None,
            )
        )

        result = PharmacyFilter.filter_and_sort_pharmacies(pharmacies, Medicine(name="test", location="test"))

        # Should return 12 pharmacies (10 + 2 high availability)
        assert len(result) == 12

        # Should be sorted by distance (filter out None values for comparison)
        distances = [p.distance_km for p in result if p.distance_km is not None]
        assert distances == sorted(distances)

        # Should include the high availability ones
        names = [p.name for p in result]
        assert "Far High Availability 1" in names
        assert "Far High Availability 2" in names

    def test_filter_and_sort_pharmacies_no_extension_high_availability_in_top_10(self):
        """Test no extension when top 10 already have high availability."""
        # Create 12 pharmacies - some of top 10 have high availability
        pharmacies = []

        # First 10 - some with high availability
        for i in range(1, 11):
            availability = AvailabilityLevel.HIGH if i <= 3 else AvailabilityLevel.LOW  # First 3 have high availability
            pharmacies.append(
                PharmacyInfo(
                    name=f"Close Pharmacy {i}",
                    address=f"Address {i}",
                    distance_km=i * 0.3,
                    availability=availability,
                    phone=None,
                    price_full=None,
                    opening_hours=None,
                )
            )

        # 2 additional - farther with high availability
        pharmacies.append(
            PharmacyInfo(
                name="Far High Availability 1",
                address="Far Address 1",
                distance_km=4.0,
                availability=AvailabilityLevel.HIGH,
                phone=None,
                price_full=None,
                opening_hours=None,
            )
        )
        pharmacies.append(
            PharmacyInfo(
                name="Far High Availability 2",
                address="Far Address 2",
                distance_km=5.0,
                availability=AvailabilityLevel.HIGH,
                phone=None,
                price_full=None,
                opening_hours=None,
            )
        )

        result = PharmacyFilter.filter_and_sort_pharmacies(pharmacies, Medicine(name="test", location="test"))

        # Should return only top 10 (no extension because top 10 already have high availability)
        assert len(result) == 10
        assert result[0].distance_km == 0.3
        assert result[-1].distance_km == 3.0  # 10th pharmacy

    def test_filter_and_sort_pharmacies_no_extension(self):
        """Test filtering without extension when no high-availability pharmacies exist beyond top 10."""
        # Create 12 pharmacies - all with same availability (no "many" availability)
        pharmacies = []
        for i in range(1, 13):
            pharmacies.append(
                PharmacyInfo(
                    name=f"Pharmacy {i}",
                    address=f"Address {i}",
                    distance_km=i * 0.5,
                    availability=AvailabilityLevel.LOW,  # None have HIGH
                    phone=None,
                    price_full=None,
                    opening_hours=None,
                )
            )

        result = PharmacyFilter.filter_and_sort_pharmacies(pharmacies, Medicine(name="test", location="test"))

        # Should return only top 10 (no extension because no high availability beyond top 10)
        assert len(result) == 10
        assert result[0].distance_km == 0.5
        assert result[-1].distance_km == 5.0  # 10th pharmacy


class TestChromeUserDataDir:
    """Tests verifying Chrome is configured to use a fixed user-data-dir directory.

    Without --user-data-dir, Chrome creates a new randomly-named temp directory
    (~100-500 MB) on each invocation that never gets cleaned up, causing multi-GB
    disk writes in long-running daemon processes.
    """

    def test_chrome_options_has_user_data_dir(self):
        """Chrome options must include a fixed --user-data-dir argument."""
        from pharmaradar.webdriver_utils import CHROME_USER_DATA_DIR, WebDriverUtils

        options = WebDriverUtils.get_chrome_options(headless=True)
        user_data_args = [a for a in options.arguments if a.startswith("--user-data-dir=")]

        assert len(user_data_args) == 1, "Exactly one --user-data-dir argument must be present"
        assert user_data_args[0] == f"--user-data-dir={CHROME_USER_DATA_DIR}"

    def test_chrome_options_no_incognito(self):
        """--incognito must not be present as it conflicts with --user-data-dir."""
        from pharmaradar.webdriver_utils import WebDriverUtils

        options = WebDriverUtils.get_chrome_options(headless=True)
        assert "--incognito" not in options.arguments, "--incognito is incompatible with --user-data-dir"

    def test_cleanup_removes_crash_subdirs_not_profile_dir(self, tmp_path):
        """cleanup_hanging_processes must remove crash/lock subdirs but keep the profile dir.

        The profile dir must NOT be fully deleted between sessions — doing so causes Chrome
        to crash when a new session starts immediately after (back-to-back calls like
        test_connection() followed by search_medicine()).
        """
        import os

        from pharmaradar.webdriver_utils import WebDriverUtils

        fake_profile_dir = str(tmp_path / "pharmaradar-chrome-profile")
        crash_dir = os.path.join(fake_profile_dir, "Crashpad")
        lock_file = os.path.join(fake_profile_dir, "SingletonLock")
        os.makedirs(crash_dir)
        open(lock_file, "w").close()

        with (
            patch("pharmaradar.webdriver_utils.subprocess.run"),
            patch("pharmaradar.webdriver_utils.time.sleep"),
            patch("pharmaradar.webdriver_utils.CHROME_USER_DATA_DIR", fake_profile_dir),
        ):
            WebDriverUtils.cleanup_hanging_processes()

        assert os.path.exists(fake_profile_dir), "Profile dir itself must NOT be deleted"
        assert not os.path.exists(crash_dir), "Crashpad subdir must be deleted"
        assert not os.path.exists(lock_file), "SingletonLock must be deleted"
