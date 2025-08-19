"""
Selenium-based web scraper for ktomalek.pl to search for medicine availability in pharmacies.

This scraper uses Selenium WebDriver to handle dynamic content and JavaScript
on the ktomalek.pl website, providing reliable scraping of pharmacy data.
"""

import html
import logging
import time
from typing import List

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pharmaradar.location_selector import LocationSelector
from pharmaradar.medicine import Medicine
from pharmaradar.pharmacy_info import PharmacyInfo
from pharmaradar.scraping_utils import PageNavigator, PharmacyDuplicateDetector, PharmacyExtractor, PharmacyFilter
from pharmaradar.text_parsers import MedicineNameMatcher, PharmacyTextParser
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

    def _search_medicine_on_homepage(self, driver, medicine_name: str) -> bool:
        """Backward compatibility wrapper for PageNavigator.search_medicine."""
        return PageNavigator.search_medicine(driver, medicine_name, self.timeout)

    def _select_location_from_options(self, driver, location: str) -> bool:
        """Backward compatibility wrapper for LocationSelector."""
        location_selector = LocationSelector(driver, self.timeout)
        return location_selector.select_location(location)

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

        medicine_details = f"{medicine.dosage or ''} {medicine.amount or ''}"
        if medicine_details.strip():
            medicine_details = f"{medicine.name} ({medicine_details.strip()})"
        else:
            medicine_details = medicine.name

        try:
            driver = self.driver_manager.get_driver()

            # Navigate to the search page
            driver.get(self.BASE_URL)
            time.sleep(2)

            # Dismiss cookie popup if present
            if not PageNavigator.dismiss_cookie_popup(driver):
                self.log.warning("Failed to dismiss cookie popup - continuing with search")

            # Perform the search
            pharmacies = self._perform_search(driver, medicine)

            return pharmacies

        except Exception as e:
            self.log.error(f"Error in search for medicine {medicine.name}: {str(e)}")
            return []

    def _perform_search(self, driver, medicine: Medicine) -> List[PharmacyInfo]:
        """Perform the correct medicine search workflow on ktomalek.pl website."""
        try:
            # Build search query including dosage and amount if specified
            search_parts = [medicine.name]
            if medicine.dosage:
                search_parts.append(medicine.dosage)
            if medicine.amount:
                search_parts.append(medicine.amount)

            search_query = " ".join(search_parts)

            # Step 1: Set location first (required by website workflow)
            location_selector = LocationSelector(driver, self.timeout)
            if not location_selector.select_location(medicine.location):
                self.log.error("Failed to select location")
                return []

            # Step 2: Search for medicine after location is set
            if not PageNavigator.search_medicine(driver, search_query, self.timeout):
                self.log.error("Failed to search for medicine")
                return []

            # Step 3: Extract pharmacy results
            pharmacies = self._extract_pharmacy_results(driver, medicine)

            return pharmacies

        except Exception as e:
            self.log.error(f"Error performing search: {e}")
            return []

    def _extract_pharmacy_results(self, driver, medicine: Medicine) -> List[PharmacyInfo]:
        """Extract pharmacy results after medicine search and location selection."""
        try:
            pharmacies = []

            # Wait for results to load
            time.sleep(3)

            # Look for medicine result containers first
            medicine_selectors = ["div.results-item", "div[class*='result']", "div[data-group]"]

            # Find medicine elements
            medicine_elements = []
            selected_selector = None
            for selector in medicine_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    visible_elements = [e for e in elements if e.is_displayed() and e.text.strip()]
                    if visible_elements:
                        medicine_elements = visible_elements
                        selected_selector = selector
                        break
                except Exception as e:
                    self.log.warning(f"Error finding medicine elements with selector {selector}: {e}")

            if not medicine_elements:
                self.log.warning("No medicine elements found on the page")
                return []

            # Process each medicine element to find pharmacy buttons and click them
            # Use index-based iteration to handle stale element references
            max_medicines = min(10, len(medicine_elements))  # Process first 10 medicines
            for i in range(max_medicines):
                try:
                    # Always re-find medicine elements to avoid stale references
                    current_medicine_elements = driver.find_elements(By.CSS_SELECTOR, selected_selector)

                    if i >= len(current_medicine_elements):
                        break

                    medicine_element = current_medicine_elements[i]

                    # Extract medicine name for context
                    medicine_name = "Unknown"
                    medicine_element_text = ""
                    try:
                        name_link = medicine_element.find_element(By.CSS_SELECTOR, "a.nazwaLeku")
                        medicine_name = name_link.text.strip()
                        medicine_element_text = medicine_element.text.strip()
                    except Exception:
                        medicine_element_text = medicine_element.text.strip()

                    # Check if medicine name matches using fuzzy matching
                    if not MedicineNameMatcher.is_name_match(medicine.name, medicine_name, min_similarity=0.7):
                        similarity = MedicineNameMatcher.calculate_similarity(medicine.name, medicine_name)
                        self.log.debug(
                            f"Medicine name mismatch: '{medicine.name}' vs '{medicine_name}' (similarity: {similarity:.2f})"
                        )
                        continue

                    # Extract dosage and amount from medicine element
                    found_dosage, found_amount = PharmacyTextParser.extract_dosage_and_amount(medicine_element_text)

                    # Check if this medicine matches the search criteria for dosage/amount
                    if not PharmacyTextParser.matches_dosage_and_amount(
                        medicine.dosage, medicine.amount, found_dosage, found_amount
                    ):
                        self.log.debug(
                            f"Dosage/amount mismatch - skipping: {medicine.dosage} {medicine.amount} vs {found_dosage} {found_amount}"
                        )
                        continue

                    # Look for pharmacy availability button in this medicine element
                    pharmacy_button = self._find_pharmacy_button(medicine_element)

                    if not pharmacy_button:
                        continue

                    # Click the pharmacy button to navigate to pharmacy list
                    try:
                        # Scroll into view and click
                        driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", pharmacy_button
                        )
                        time.sleep(1)

                        # Click the button
                        if pharmacy_button.get_attribute("onclick"):
                            driver.execute_script("arguments[0].click();", pharmacy_button)
                        else:
                            pharmacy_button.click()

                        time.sleep(5)  # Wait for page to load

                        # Extract pharmacy data from the new page
                        page_pharmacies = self._extract_pharmacies_from_pharmacy_page(driver, medicine)

                        if page_pharmacies:
                            pharmacies.extend(page_pharmacies)

                        # Go back to the medicine search results
                        driver.back()

                        # Wait for the page to reload and medicine elements to be available again
                        try:
                            WebDriverWait(driver, 10).until(
                                lambda d: len(d.find_elements(By.CSS_SELECTOR, selected_selector)) > 0
                            )
                        except Exception:
                            self.log.warning("Timeout waiting for medicine search results to reload")

                        time.sleep(2)

                    except Exception as e:
                        self.log.error(f"Error clicking pharmacy button for {medicine_name}: {e}")
                        continue

                except StaleElementReferenceException:
                    self.log.warning(f"Stale element reference for medicine element {i + 1} - skipping")
                    continue
                except Exception as e:
                    self.log.warning(f"Error processing medicine element {i + 1}: {e}")
                    continue

            # Apply smart filtering and sorting
            return PharmacyFilter.filter_and_sort_pharmacies(pharmacies, medicine)

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
