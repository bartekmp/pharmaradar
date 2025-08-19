"""
Location selection utilities for medicine scraping.

Handles location search and selection on the ktomalek.pl website.
"""

import logging
import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pharmaradar.text_parsers import LocationTextParser


class LocationSelector:
    """Handles location selection on the ktomalek.pl website."""

    def __init__(self, driver: webdriver.Remote, timeout: int = 15, log: logging.Logger = logging.getLogger()):
        self.driver = driver
        self.timeout = timeout
        self.log = log

    def select_location(self, location: str) -> bool:
        """
        Select location using the searchAdresu input and kontenerAdresow results.
        Args:
            location: The location string to search for (e.g., "Warszawa, ul. Marszałkowska 1").
        Returns:
            bool: True if location was successfully selected, False otherwise.
        """
        try:
            self.log.info(f"Selecting location: {location}")

            # Activate step 1 to make location input visible
            if not self._activate_location_step():
                self.log.warning("Could not activate location step")

            # Fill location search input
            if not self._fill_location_input(location):
                self.log.error("Failed to fill location input")
                return False

            # Trigger location search
            if not self._trigger_location_search():
                self.log.error("Failed to trigger location search")
                return False

            # Select best matching location
            if not self._select_best_location(location):
                self.log.error("Failed to select location")
                return False

            return True

        except Exception as e:
            self.log.error(f"Error in location selection: {e}")
            return False

    def _activate_location_step(self) -> bool:
        """
        Activate step 1 (krok_1) to make the location input field visible.
        Args:
            None
        Returns:
            bool: True if activation was successful, False otherwise.
        """
        try:
            time.sleep(2)  # Wait for page to stabilize

            step1_selectors = ["a[onclick*='krok_1.aktywuj']", "#krok_1_linked a"]

            for selector in step1_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(1)
                            return True
                except Exception:
                    continue

            # Fallback: execute JavaScript directly
            js_code = """
            if (typeof aktualnyKrok !== 'undefined' && typeof krok_1 !== 'undefined') {
                aktualnyKrok.dezaktywuj(false, false);
                krok_1.aktywuj();
                $('#searchAdresu').focus();
            }
            """
            self.driver.execute_script(js_code)
            time.sleep(1)
            return True

        except Exception as e:
            self.log.warning(f"Error activating location step: {e}")
            return False

    def _fill_location_input(self, location: str) -> bool:
        """
        Fill the location search input.
        Args:
            location: The location string to search for (e.g., "Warszawa, ul. Marszałkowska 1").
        Returns:
            bool: True if input was successfully filled, False otherwise.
        """
        try:
            location_input = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, "searchAdresu"))
            )

            location_input.clear()
            time.sleep(0.5)

            # Use specific location format that works better
            specific_location = f"{location}, centrum" if "," not in location else location
            location_input.send_keys(specific_location)

            return True

        except Exception as e:
            self.log.error(f"Could not fill location input: {e}")
            return False

    def _trigger_location_search(self) -> bool:
        """
        Trigger the location search.
        Args:
            None
        Returns:
            bool: True if search was successfully triggered, False otherwise.
        """
        try:
            show_addresses_button = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, "showAdresy"))
            )

            # Try both button click and JavaScript execution
            try:
                show_addresses_button.click()
            except Exception:
                js_code = "if (typeof lokalizacja !== 'undefined') { lokalizacja.znajdzLokalizacje(); }"
                self.driver.execute_script(js_code)

            # Wait for search to complete
            time.sleep(5)

            # Wait for loading to complete if present
            try:
                loading_element = self.driver.find_element(By.ID, "loadingPolozenie")
                if loading_element.is_displayed():
                    WebDriverWait(self.driver, 15).until(lambda d: not loading_element.is_displayed())
                    time.sleep(1)
            except Exception:
                pass  # No loading indicator

            return True

        except Exception as e:
            self.log.error(f"Could not trigger location search: {e}")
            return False

    def _select_best_location(self, location: str) -> bool:
        """
        Select the best matching location from search results.
        Args:
            location: The location string to search for (e.g., "Warszawa, ul. Marszałkowska 1").
        Returns:
            bool: True if a suitable location was selected, False otherwise.
        """
        try:
            container = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, "kontenerAdresow"))
            )

            time.sleep(1)  # Wait for results to populate

            # Find location links
            location_links = container.find_elements(By.CLASS_NAME, "block-link")

            if not location_links:
                # Try alternative selectors
                alternative_selectors = [
                    "a[onclick*='lokalizacja.zapiszLokalizacje']",
                    "a[onclick*='zapiszLokalizacje']",
                    "a[href='#0']",
                ]

                for selector in alternative_selectors:
                    try:
                        elements = container.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            location_links = elements
                            break
                    except Exception:
                        continue

            # Try fallback with city only if no results
            if not location_links and "," in location:
                city_only = location.split(",")[0].strip()
                return self._retry_with_city_only(city_only)

            if not location_links:
                self.log.error("No location links found")
                return False

            # Find best match using the location parser
            best_match = self._find_best_location_match(location_links, location)

            if best_match:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", best_match
                    )
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].click();", best_match)
                    time.sleep(2)
                    return True
                except Exception as e:
                    self.log.error(f"Error clicking location: {e}")
                    return False
            else:
                self.log.warning("No suitable location match found")
                return False

        except Exception as e:
            self.log.error(f"Error selecting location: {e}")
            return False

    def _find_best_location_match(self, location_links: list[WebElement], location: str):
        """
        Find the best matching location from the available options.
        Args:
            location_links: List of WebElement links containing location options.
            location: The original location string to match against (e.g., "Warszawa, ul. Marszałkowska 1").
        Returns:
            WebElement: The best matching location link, or None if no match found.
        """

        best_match = None
        best_score = 0

        for link in location_links:
            try:
                onclick_attr = link.get_attribute("onclick")
                if not onclick_attr or "lokalizacja.zapiszLokalizacje" not in onclick_attr:
                    continue

                # Extract city and street from onclick JS code
                match = re.search(
                    r"lokalizacja\.zapiszLokalizacje\([^,]+,\s*[^,]+,\s*'([^']*)',\s*'([^']*)'\)", onclick_attr
                )
                if not match:
                    continue

                option_city = match.group(1)
                option_street = match.group(2)

                # Calculate match score
                score = LocationTextParser.calculate_location_match_score(location, option_city, option_street)

                if score > best_score:
                    best_score = score
                    best_match = link

            except Exception:
                continue

        return best_match

    def _retry_with_city_only(self, city: str) -> bool:
        """
        Retry location selection with city name only.
        Args:
            city: The city name to search for (e.g., "Warszawa").
        Returns:
            bool: True if a suitable location was selected, False otherwise.
        """
        try:
            self.log.info(f"Retrying with city only: {city}")

            # Clear and enter city only
            location_input = self.driver.find_element(By.ID, "searchAdresu")
            location_input.clear()
            time.sleep(0.5)
            location_input.send_keys(city)

            # Trigger search again
            show_addresses_button = self.driver.find_element(By.ID, "showAdresy")
            show_addresses_button.click()
            time.sleep(3)

            # Try to find location links again
            container = self.driver.find_element(By.ID, "kontenerAdresow")
            location_links = container.find_elements(By.CLASS_NAME, "block-link")

            if location_links:
                best_match = self._find_best_location_match(location_links, city)
                if best_match:
                    self.driver.execute_script("arguments[0].click();", best_match)
                    time.sleep(2)
                    return True

            return False

        except Exception as e:
            self.log.warning(f"City-only retry failed: {e}")
            return False
