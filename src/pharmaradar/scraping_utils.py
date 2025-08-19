"""
Scraping utilities for medicine data extraction.

Contains functions for extracting and processing pharmacy data from web pages.
"""

import re
import time
from typing import TYPE_CHECKING, Dict, List, Optional
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pharmaradar.availability_level import AvailabilityLevel
from pharmaradar.medicine import Medicine
from pharmaradar.pharmacy_info import PharmacyInfo
from pharmaradar.text_parsers import PharmacyTextParser

if TYPE_CHECKING:
    from selenium import webdriver


class PharmacyExtractor:
    """Handles extraction of pharmacy data from web elements."""

    @staticmethod
    def extract_pharmacy_from_element(
        element: WebElement, medicine: Medicine, driver: Optional["webdriver.Remote"] = None
    ) -> Optional[PharmacyInfo]:
        """Extract pharmacy information from a single pharmacy container."""
        try:
            element_text = element.text.strip()

            # Parse using the text parser for basic data
            pharmacy_data = PharmacyTextParser.parse_pharmacy_data(element_text)

            # Enhanced price extraction with dynamic refund selection (if driver is available)
            if driver:
                PharmacyExtractor._extract_dynamic_prices(element, pharmacy_data, driver)

            # Enhanced phone extraction from JavaScript buttons and tel: links
            enhanced_phone = PharmacyExtractor._extract_phone_from_html(element)
            if enhanced_phone:
                pharmacy_data["phone"] = enhanced_phone

            # Enhanced additional info extraction (prescription, refund status, stock details)
            additional_info = PharmacyTextParser.extract_additional_info(element.text.strip())
            if additional_info:
                pharmacy_data["additional_info"] = additional_info

            # Add missing required field
            if "opening_hours" not in pharmacy_data:
                pharmacy_data["opening_hours"] = None

            # Extract reservation URL from form with medicine search context
            reservation_url = PharmacyExtractor._extract_reservation_url(element, medicine)
            if reservation_url:
                pharmacy_data["reservation_url"] = reservation_url

            # Create PharmacyInfo object
            if pharmacy_data.get("name") and pharmacy_data.get("address"):
                return PharmacyInfo(**pharmacy_data)

            return None

        except Exception as e:
            return None

    @staticmethod
    def _extract_reservation_url(element: WebElement, medicine: Medicine) -> Optional[str]:
        """
        Extract reservation URL and construct a session-independent link.

        Creates a simple search URL that doesn't rely on session state and works reliably.
        """
        try:
            # Look for existing reservation link first
            reservation_link = element.find_element(
                By.CSS_SELECTOR, "a[href*='rezerwacj'], button[onclick*='rezerwacj']"
            )
            if reservation_link:
                href = reservation_link.get_attribute("href") or reservation_link.get_attribute("onclick")
                if href and "http" in href:
                    return href
        except Exception:
            pass

        # Create a simple, generic search URL that recreates the search context
        try:
            search_parts = [medicine.name]
            if medicine.dosage:
                search_parts.append(medicine.dosage)
            if medicine.amount:
                search_parts.append(medicine.amount)
            search_query = " ".join(search_parts)

            encoded_medicine = quote_plus(search_query)
            encoded_location = quote_plus(medicine.location)

            # Simple URL that recreates the search - works reliably
            return f"https://ktomalek.pl/?miejscowosc={encoded_location}&szukanyLek={encoded_medicine}"

        except Exception as e:
            return "https://ktomalek.pl/"

    @staticmethod
    def _extract_dynamic_prices(element: WebElement, pharmacy_data: Dict, driver: "webdriver.Remote") -> None:
        """
        Extract full and refunded prices using dynamic dropdown interaction.

        This method interacts with refund selection dropdowns to get both full and refunded prices.
        It handles "R - Ryczałt" (refunded) and "Pełnopłatny" (full price) options.
        """
        try:
            # First get the full price if not already extracted
            if not pharmacy_data.get("price_full"):
                price_full = PharmacyTextParser.extract_price(element.text.strip())
                if price_full:
                    pharmacy_data["price_full"] = price_full

            # Try to extract refunded price by interacting with refund selection dropdown
            refund_selects = element.find_elements(By.CSS_SELECTOR, "select[id*='refundacja_lek_']")
            if refund_selects:
                for select in refund_selects:
                    try:
                        if select.is_displayed():
                            # Get current options
                            options = select.find_elements(By.TAG_NAME, "option")
                            refund_option = None
                            full_price_option = None

                            # Look for refund option (R - Ryczałt) and full price option
                            for option in options:
                                option_text = option.text.strip()
                                if "R - Ryczałt" in option_text or "ryczałt" in option_text.lower():
                                    refund_option = option
                                elif "100%" in option_text or "Pełnopłatny" in option_text:
                                    full_price_option = option

                            if refund_option:
                                # Select the refund option using JavaScript
                                driver.execute_script(
                                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                                    select,
                                    refund_option.get_attribute("value"),
                                )
                                time.sleep(1)  # Wait for price update

                                # Re-extract the element text to get updated price
                                updated_text = element.text.strip()

                                # Look for the new price in the updated text
                                updated_price_matches = re.findall(r"(\d+[,.]?\d*)\s*zł", updated_text)
                                if updated_price_matches:
                                    for price_str in updated_price_matches:
                                        try:
                                            potential_refunded = float(price_str.replace(",", "."))
                                            # Refunded price should be different and lower than full price
                                            price_full = pharmacy_data.get("price_full")
                                            if (
                                                price_full is not None
                                                and potential_refunded != price_full
                                                and potential_refunded < price_full
                                                and potential_refunded > 0
                                            ):
                                                pharmacy_data["price_refunded"] = potential_refunded
                                                break
                                        except Exception:
                                            continue

                                # Reset to 100% option to not affect other elements
                                if full_price_option:
                                    driver.execute_script(
                                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                                        select,
                                        full_price_option.get_attribute("value"),
                                    )
                                    time.sleep(0.5)
                            break
                    except Exception as e:
                        continue

        except Exception as e:
            return

    @staticmethod
    def _extract_phone_from_html(element: WebElement) -> Optional[str]:
        """
        Extract phone number from HTML elements with sophisticated techniques.

        This method prioritizes JavaScript button extraction over simple text parsing
        and formats the phone number as a clickable link with country code.

        Args:
            element: WebElement containing pharmacy information

        Returns:
            Phone number formatted as +48XXXXXXXXX for clickable links, or None if not found
        """

        # Look for phone in onclick attribute of "Wyświetl numer" button
        # Pattern: ofertyAptek.otworzDialogTelefon('856154', 'APTEKA PIERWSZA', '737 455 567', ...)
        try:
            display_buttons = element.find_elements(
                By.CSS_SELECTOR, "button[onclick*='ofertyAptek.otworzDialogTelefon']"
            )
            for button in display_buttons:
                onclick = button.get_attribute("onclick") or ""
                onclick_match = re.search(r"ofertyAptek\.otworzDialogTelefon\([^,]+,\s*[^,]+,\s*'([^']+)'", onclick)
                if onclick_match:
                    phone_raw = onclick_match.group(1).strip()
                    # Clean up the phone number
                    phone_clean = re.sub(r"[^\d]", "", phone_raw)
                    if len(phone_clean) == 9:  # Valid Polish phone number
                        return f"+48{phone_clean}"  # Add country code for clickable links
        except Exception as e:
            pass
        # Fallback: look for "tel:" links in the element
        try:
            tel_links = element.find_elements(By.CSS_SELECTOR, "a[href^='tel:']")
            for tel_link in tel_links:
                href = tel_link.get_attribute("href") or ""
                if href.startswith("tel:"):
                    phone_raw = href.replace("tel:", "").strip()
                    # Clean up the phone number
                    phone_clean = re.sub(r"[^\d]", "", phone_raw)
                    if phone_clean.startswith("48"):
                        phone_clean = phone_clean[2:]  # Remove country code
                    if len(phone_clean) == 9:  # Valid Polish phone number
                        return f"+48{phone_clean}"  # Add country code for clickable links
        except Exception as e:
            pass
        # No phone number found
        return None


class PageNavigator:
    """Handles page navigation and interaction."""

    @staticmethod
    def dismiss_cookie_popup(driver: "webdriver.Remote") -> bool:
        """
        Dismiss the cookie popup if present.
        Args:
            driver: The Selenium WebDriver instance
        Returns:
            bool: True if successfully dismissed, False otherwise.
        """
        try:
            # Try primary cookie button
            try:
                cookie_button = driver.find_element(By.ID, "btnCookiesAll")
                if cookie_button.is_displayed():
                    cookie_button.click()
                    return True
            except Exception:
                pass

            # Try alternative selectors
            cookie_selectors = [
                "button[id*='cookie']",
                "button[class*='cookie']",
                "button[class*='accept']",
                ".accept-cookies",
            ]

            for selector in cookie_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            elem.click()
                            return True
                except Exception:
                    continue
            return False
        except Exception as e:
            return False

    @staticmethod
    def search_medicine(driver: "webdriver.Remote", search_query: str, timeout: int = 15) -> bool:
        """
        Search for medicine using the main search form.
        Args:
            driver: The Selenium WebDriver instance
            search_query: The medicine name to search for
            timeout: Maximum wait time for elements (default 15 seconds)
        Returns:
            bool: True if search was successful, False otherwise.
        """
        try:
            # Find medicine input
            try:
                medicine_input = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.ID, "szukanyLek")))
            except Exception:
                # Fallback selectors
                selectors = ["input[placeholder*='lek']", "input[placeholder*='szukasz']", "input[type='text']"]
                medicine_input = None
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed():
                                medicine_input = elem
                                break
                        if medicine_input:
                            break
                    except Exception:
                        continue

                if not medicine_input:
                    return False

            # Enter search query
            medicine_input.clear()
            medicine_input.send_keys(search_query)

            # Find and click submit button
            try:
                submit_button = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))
                )
                submit_button.click()
            except Exception:
                # Fallback: press Enter
                medicine_input.send_keys(Keys.ENTER)

            return True

        except Exception as e:
            return False


class PharmacyFilter:
    """Handles filtering and sorting of pharmacy results."""

    @staticmethod
    def filter_and_sort_pharmacies(pharmacies: List[PharmacyInfo], medicine: Medicine) -> List[PharmacyInfo]:
        """
        Filter and sort pharmacies based on criteria.

        Algorithm:
        1. Filter pharmacies that match the medicine criteria
        2. Sort by distance (closest first)
        3. Take top 10
        4. If top 10 don't have high availability, extend with high availability ones within 2x distance

        Args:
            pharmacies: List of PharmacyInfo objects to filter and sort
            medicine: Medicine object containing search criteria
        Returns:
            List of filtered and sorted PharmacyInfo objects
        """
        try:
            # Filter pharmacies that match the medicine criteria
            filtered = [p for p in pharmacies if medicine.matches_pharmacy(p)]

            # Sort by distance first
            def distance_sort_key(pharmacy: PharmacyInfo) -> float:
                return pharmacy.distance_km or float("inf")

            filtered.sort(key=distance_sort_key)

            # Take top 10
            top_10 = filtered[:10]

            # Check if any of top 10 have high availability
            has_high_availability = any(p.availability == AvailabilityLevel.HIGH for p in top_10)

            if not has_high_availability and len(filtered) > 10:
                # Find the maximum distance in top 10
                max_distance = max((p.distance_km or 0) for p in top_10) if top_10 else 0
                distance_threshold = max_distance * 2

                # Find high availability pharmacies beyond top 10 within distance threshold
                high_availability_extensions = [
                    p
                    for p in filtered[10:]
                    if p.availability == AvailabilityLevel.HIGH and (p.distance_km or 0) <= distance_threshold
                ]

                # Sort the extensions by distance too
                high_availability_extensions.sort(key=distance_sort_key)

                # Combine: first top 10 (sorted by distance), then high availability extensions (sorted by distance)
                return top_10 + high_availability_extensions

            return top_10

        except Exception as e:
            # In case of any error, return the original list
            return pharmacies


class PharmacyDuplicateDetector:
    """Handles sophisticated duplicate detection for pharmacy results."""

    @staticmethod
    def is_duplicate_pharmacy(pharmacy: PharmacyInfo, existing_pharmacies: List[PharmacyInfo]) -> bool:
        """
        Check if a pharmacy is a duplicate using intelligent name and address comparison.

        This sophisticated duplicate detection was restored from the original implementation
        that was lost during refactoring.

        Args:
            pharmacy: The pharmacy to check for duplicates
            existing_pharmacies: List of already processed pharmacies

        Returns:
            True if the pharmacy is a duplicate, False otherwise
        """
        for existing_pharmacy in existing_pharmacies:
            if existing_pharmacy.name == pharmacy.name:
                # If both have addresses, compare them too
                if pharmacy.address and existing_pharmacy.address and pharmacy.address == existing_pharmacy.address:
                    return True
                # If addresses are missing or one is missing, consider duplicate by name only
                elif not pharmacy.address or not existing_pharmacy.address:
                    return True

        return False

    @staticmethod
    def add_pharmacy_with_duplicate_check(pharmacy: PharmacyInfo, pharmacies: List[PharmacyInfo]) -> bool:
        """
        Add a pharmacy to the list only if it's not a duplicate.

        Args:
            pharmacy: The pharmacy to add
            pharmacies: The list to add the pharmacy to

        Returns:
            True if the pharmacy was added, False if it was a duplicate
        """
        if not PharmacyDuplicateDetector.is_duplicate_pharmacy(pharmacy, pharmacies):
            pharmacies.append(pharmacy)
            return True
        else:
            return False


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    Args:
        text: The raw text to clean
    Returns:
        Cleaned text with extra whitespace removed and HTML entities normalized
    """
    if not text:
        return ""

    # Remove extra whitespace and normalize
    text = re.sub(r"\s+", " ", text.strip())
    # Remove HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")

    return text
