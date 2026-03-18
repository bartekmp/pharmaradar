"""
Selenium-based web scraper for ktomalek.pl to search for medicine availability in pharmacies.

This scraper uses Selenium WebDriver to handle dynamic content and JavaScript
on the ktomalek.pl website, providing reliable scraping of pharmacy data.
"""

import html
import logging
import time
from typing import List
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By

from pharmaradar.medicine import Medicine
from pharmaradar.pharmacy_info import PharmacyInfo
from pharmaradar.scraping_utils import PageNavigator, PharmacyDuplicateDetector, PharmacyExtractor, PharmacyFilter
from pharmaradar.text_parsers import LocationTextParser, MedicineNameMatcher, PharmacyTextParser
from pharmaradar.webdriver_utils import WebDriverManager


class MedicineFinder:
    """Selenium-based scraper for ktomalek.pl medicine search."""

    BASE_URL = "https://ktomalek.pl"

    def __init__(self, headless: bool = True, timeout: int = 15, log: logging.Logger = logging.getLogger()):
        """
        Initialize the medicine scraper with Selenium WebDriver.

        Args:
            headless: Whether to run browser in headless mode
            timeout: Timeout for web operations in seconds
        """
        self.headless = headless
        self.timeout = timeout
        self.driver_manager = WebDriverManager(headless, timeout)
        self._webdriver_available = None  # Cache WebDriver availability check
        self.log = log
        self.log.info("Initialized PharmaRadar scraper")

    def is_webdriver_available(self) -> bool:
        """
        Check if WebDriver is available without creating a full driver instance.

        Returns:
            True if WebDriver can be initialized, False otherwise
        """
        if self._webdriver_available is not None:
            return self._webdriver_available

        try:
            # Quick test to see if we can create a driver
            with WebDriverManager(headless=True, timeout=5) as test_manager:
                driver = test_manager.get_driver()
                driver.get("data:,")  # Simple test
                self._webdriver_available = True
                self.log.info("WebDriver availability check: ✅ Available")
                return True
        except Exception as e:
            self._webdriver_available = False
            self.log.warning(f"WebDriver availability check: ❌ Not available - {e}")
            return False

    @property
    def driver(self):
        """Get the current WebDriver instance (for backward compatibility)."""
        return self.driver_manager.driver

    @driver.setter
    def driver(self, value):
        """Set the WebDriver instance (for backward compatibility)."""
        self.driver_manager.driver = value

    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing extra whitespace and HTML entities.
        Args:
            text: The raw text to clean
        Returns:
            Cleaned text with extra whitespace removed and HTML entities decoded
        """
        # Decode HTML entities
        text = html.unescape(text)
        # Replace &nbsp; specifically
        text = text.replace("&nbsp;", " ")
        # Clean up whitespace
        return " ".join(text.split())

    def _get_webdriver(self):
        """Backward compatibility wrapper for driver manager."""
        return self.driver_manager.get_driver()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        """Close the WebDriver if it's open with cleanup."""
        self.driver_manager.close()

    def search_medicine(self, medicine: Medicine) -> List[PharmacyInfo]:
        """
        Search for medicine availability in pharmacies using Selenium.

        Args:
            medicine: Medicine object with search criteria

        Returns:
            List of PharmacyInfo objects with found pharmacies
        """
        # Check WebDriver availability first
        if not self.is_webdriver_available():
            self.log.error("WebDriver not available - medicine search cannot proceed")
            return []

        try:
            driver = self.driver_manager.get_driver()

            # Build search query
            search_parts = [medicine.name]
            if medicine.dosage:
                search_parts.append(medicine.dosage)
            if medicine.amount:
                search_parts.append(medicine.amount)
            search_query = " ".join(search_parts)

            # Navigate with ?szukanyLek= so the site pre-selects the medicine
            url = f"{self.BASE_URL}/?szukanyLek={quote_plus(search_query)}"
            self.log.info(f"Loading search URL: {url}")
            driver.get(url)
            time.sleep(3)

            # Dismiss cookie popup if present
            PageNavigator.dismiss_cookie_popup(driver, timeout=2)

            # Set the session location via the site's JS API
            if not self._set_location_via_js(driver, medicine.location):
                self.log.warning("Could not set location via JS")
                return []

            # Extract pharmacy results
            pharmacies = self._extract_pharmacy_results(driver, medicine)

            return pharmacies

        except Exception as e:
            self.log.error(f"Error in search for medicine {medicine.name}: {str(e)}")
            return []

    def _set_location_via_js(self, driver, location: str) -> bool:
        """Set the session location by geocoding *location* and calling zapiszLokalizacje.

        The ktomalek.pl site requires the location to be set via an AJAX call
        that stores GPS coordinates in the server session.  The ``miejscowosc``
        URL parameter is cosmetic and does **not** set the session location.

        Args:
            location: Free-form location string, e.g.
                      ``"Warszawa, aleja Stanów Zjednoczonych"``

        Returns True if the location was set successfully.
        """
        coords = self._geocode_address(location)

        if not coords:
            self.log.warning(f"Geocoding failed for: {location}")
            return False

        lon, lat = coords
        # Split into city / street for the zapiszLokalizacje API
        city, street = LocationTextParser.parse_location_parts(location)
        city = city.title() if city else location
        try:
            # Use execute_async_script because the AJAX call is asynchronous.
            # Selenium's execute_script cannot await JS Promises.
            # The callback is arguments[arguments.length - 1].
            result = driver.execute_async_script(
                """
                var lon = arguments[0];
                var lat = arguments[1];
                var city = arguments[2];
                var street = arguments[3];
                var done = arguments[arguments.length - 1];
                try {
                    var url = lokalizacja.zapiszLokalizacjeUrl + '?timestamp=' + Date.now();
                    $.ajax({
                        type: 'POST',
                        dataType: 'json',
                        data: {
                            dlugoscGeo: lon,
                            szerokoscGeo: lat,
                            miejscowosc: city,
                            ulica: street
                        },
                        url: url,
                        success: function(msg) { done(msg && msg.wynik === 'OK'); },
                        error: function() { done(false); }
                    });
                } catch(e) { done(false); }
                """,
                lon,
                lat,
                city,
                street,
            )
            if result:
                self.log.info(f"Location set to {location} ({lat}, {lon})")
                time.sleep(3)  # wait for pharmacy results AJAX
                return True
            self.log.warning(f"zapiszLokalizacje returned non-OK for {location}")
            return False
        except Exception as e:
            self.log.warning(f"JS location setting failed: {e}")
            return False

    @staticmethod
    def _geocode_address(address: str):
        """Geocode an address using the Nominatim (OpenStreetMap) API.

        Accepts any free-form address, e.g. ``"Warszawa, aleja Stanów
        Zjednoczonych 51"`` or just ``"Kraków"``.

        If the exact address fails (common with house numbers), falls back to
        the address without trailing numbers, then to the city name alone.

        Returns (longitude, latitude) tuple or None.
        """
        import re
        import urllib.request
        import json

        def _query(q: str):
            try:
                url = (
                    f"https://nominatim.openstreetmap.org/search"
                    f"?q={quote_plus(q + ', Poland')}"
                    f"&format=json&limit=1"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "PharmaRadar/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                if data:
                    return (float(data[0]["lon"]), float(data[0]["lat"]))
            except Exception:
                pass
            return None

        # 1) Try the exact address
        result = _query(address)
        if result:
            return result

        # 2) Strip trailing house numbers from each part and retry
        #    before: "Warszawa, Aleja Stanów Zjednoczonych 51"
        #    after:  "Warszawa, Aleja Stanów Zjednoczonych"
        stripped = ", ".join(re.sub(r"\s+\d+[a-zA-Z]?$", "", part.strip()) for part in address.split(","))
        if stripped != address:
            result = _query(stripped)
            if result:
                return result

        # 3) Fall back to city name only (first part before comma)
        city = address.split(",")[0].strip()
        if city and city != address and city != stripped:
            return _query(city)

        return None

    def _extract_pharmacy_results(self, driver, medicine: Medicine) -> List[PharmacyInfo]:
        """Extract pharmacy results after medicine search and location selection."""
        try:
            time.sleep(3)

            pharmacies = []

            # Ktomalek.pl is a single-page app (SPA). When the location is set,
            # it auto-loads and expands pharmacies for the best-matching medicine variant.
            # Medicine variants and actual pharmacies both use the `div.results-item` class.
            elements = driver.find_elements(By.CSS_SELECTOR, "div.results-item, div.apteka-item")
            visible_elements = [e for e in elements if e.is_displayed() and e.text.strip()]

            for element in visible_elements:
                try:
                    # Attempt to extract a pharmacy.
                    # PharmacyExtractor will happily extract basic fields from a medicine variant too,
                    # but its availability will be AvailabilityLevel.NONE.
                    pharmacy = PharmacyExtractor.extract_pharmacy_from_element(element, medicine, driver)
                    if pharmacy:
                        PharmacyDuplicateDetector.add_pharmacy_with_duplicate_check(pharmacy, pharmacies)
                except Exception as e:
                    self.log.warning(f"Error extracting pharmacy: {e}")
                    continue

            # The filter will drop the false-positive medicine variants (availability NONE)
            # and keep the real pharmacies (availability LOW, MEDIUM, HIGH).
            if pharmacies:
                valid = PharmacyFilter.filter_and_sort_pharmacies(pharmacies, medicine)
                if valid:
                    return valid

            # Fallback: if no pharmacies were found (e.g. no auto-expansion), look for the first
            # matching medicine variant and click its check availability button.
            for element in visible_elements:
                try:
                    try:
                        name_link = element.find_element(By.CSS_SELECTOR, "a.nazwaLeku")
                        medicine_name = name_link.text.strip()
                        medicine_element_text = element.text.strip()
                    except Exception:
                        continue

                    if not MedicineNameMatcher.is_name_match(medicine.name, medicine_name, min_similarity=0.7):
                        continue

                    found_dosage, found_amount = PharmacyTextParser.extract_dosage_and_amount(medicine_element_text)
                    if not PharmacyTextParser.matches_dosage_and_amount(
                        medicine.dosage, medicine.amount, found_dosage, found_amount
                    ):
                        continue

                    # Found matching variant. Find button.
                    btn = self._find_pharmacy_button(element)
                    if btn:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn
                        )
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", btn)
                        self.log.info("Clicked 'Sprawdź dostępność' on medicine variant.")
                        time.sleep(5)

                        # Extract the newly loaded pharmacies
                        return self._extract_pharmacies_from_pharmacy_page(driver, medicine)
                except Exception:
                    continue

            return []

        except Exception as e:
            self.log.error(f"Error extracting pharmacy results: {e}")
            return []

    def _find_pharmacy_button(self, medicine_element):
        """Find pharmacy availability button in medicine element."""
        pharmacy_button_selectors = [
            ".//a[descendant::*[contains(text(), 'Sprawdź dostępność')]]",
            ".//button[descendant::*[contains(text(), 'Sprawdź dostępność')]]",
            ".//form[descendant::*[contains(text(), 'Sprawdź dostępność')]]",
        ]

        for btn_selector in pharmacy_button_selectors:
            try:
                buttons = medicine_element.find_elements(By.XPATH, btn_selector)
                if buttons:
                    return buttons[0]
            except Exception:
                continue

        # Fallback: find spans and work up to parent
        try:
            spans = medicine_element.find_elements(By.XPATH, ".//span[contains(text(), 'Sprawdź dostępność')]")
            if spans:
                span = spans[0]
                potential_parents = [
                    span.find_element(By.XPATH, "./ancestor::a[1]"),
                    span.find_element(By.XPATH, "./ancestor::button[1]"),
                    span.find_element(By.XPATH, "./ancestor::form[1]"),
                ]

                for parent in potential_parents:
                    try:
                        if parent and parent.is_displayed():
                            return parent
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    def _extract_pharmacies_from_pharmacy_page(self, driver, medicine: Medicine) -> List[PharmacyInfo]:
        """Extract pharmacy information from a pharmacy listing page."""
        try:
            pharmacies = []

            time.sleep(2)  # Wait for page to load

            # Look for pharmacy containers on the pharmacy page
            pharmacy_selectors = [
                "div[class*='tabs-'][class*='-']",
                "div.apteka-item",
                "div[class*='pharmacy']",
                "div[class*='result']",
            ]

            # Find pharmacy elements on this page
            pharmacy_elements = []
            for selector in pharmacy_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    visible_elements = [e for e in elements if e.is_displayed() and e.text.strip()]
                    if visible_elements:
                        pharmacy_elements = visible_elements
                        break
                except Exception:
                    continue

            if not pharmacy_elements:
                return []

            # Process each pharmacy element with duplicate detection
            for element in pharmacy_elements:
                try:
                    pharmacy = PharmacyExtractor.extract_pharmacy_from_element(element, medicine, driver)
                    if pharmacy:
                        PharmacyDuplicateDetector.add_pharmacy_with_duplicate_check(pharmacy, pharmacies)
                except Exception as e:
                    self.log.warning(f"Error extracting pharmacy: {e}")
                    continue

            return pharmacies

        except Exception:
            return []

    def test_connection(self) -> bool:
        """Test if the website is accessible using Selenium."""
        try:
            self.log.info("Starting connection test...")
            driver = self.driver_manager.get_driver()
            driver.get(self.BASE_URL)

            # Check if we can find any content
            body = driver.find_element(By.TAG_NAME, "body")
            success = body is not None and len(body.text) > 0

            self.log.info(f"Connection test {'successful' if success else 'failed'}")
            return success

        except Exception as e:
            self.log.error(f"Connection test failed: {str(e)}")
            return False
        finally:
            self.close()
