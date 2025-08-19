"""
Text parsing utilities for medicine scraper functionality.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


class MedicineNameMatcher:
    """Utility for fuzzy matching medicine names with case-insensitive and similarity-based matching."""

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize medicine name for comparison.
        Args:
            name: Medicine name to normalize
        Returns:
            Normalized name (lowercase, no diacritics, normalized spaces)
        """
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower()

        # Remove diacritics (Polish characters)
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        # Replace common variations
        replacements = {
            "ą": "a",
            "ć": "c",
            "ę": "e",
            "ł": "l",
            "ń": "n",
            "ó": "o",
            "ś": "s",
            "ź": "z",
            "ż": "z",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        # Handle Polish-English medicine name variations
        language_replacements = {
            "witamina": "vitamin",
            "magnez": "magnesium",
            "wapń": "calcium",
            "żelazo": "iron",
        }
        for polish, english in language_replacements.items():
            if polish in normalized:
                normalized = normalized.replace(polish, english)

        # Remove/normalize special characters and hyphens
        normalized = re.sub(r"[-_.,;:]", " ", normalized)

        # Normalize whitespace and remove extra spaces
        normalized = " ".join(normalized.split())

        return normalized

    @staticmethod
    def calculate_similarity(name1: str, name2: str) -> float:
        """
        Calculate similarity between two medicine names using multiple metrics.

        Args:
            name1: First medicine name
            name2: Second medicine name

        Returns:
            Similarity score between 0.0 and 1.0 (1.0 = identical)
        """
        norm1 = MedicineNameMatcher.normalize_name(name1)
        norm2 = MedicineNameMatcher.normalize_name(name2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match after normalization
        if norm1 == norm2:
            return 1.0

        # Check if one is contained in the other (but not too short)
        if norm1 in norm2 or norm2 in norm1:
            shorter_len = min(len(norm1), len(norm2))
            if shorter_len >= 3:  # Minimum 3 characters for substring matching
                return 0.9

        # Split into words and check word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if words1 and words2:
            intersection = words1 & words2
            union = words1 | words2

            if not intersection:
                return 0.0  # No common words = no match

            word_similarity = len(intersection) / len(union)

            # Boost if main medicine name words match (first 1-2 words)
            main_words1 = set(norm1.split()[:2])
            main_words2 = set(norm2.split()[:2])
            main_intersection = main_words1 & main_words2

            if main_intersection:
                # Check if the main words are significant (not just numbers/dosages)
                significant_words = [w for w in main_intersection if len(w) >= 3 and not w.isdigit()]
                if significant_words:
                    word_similarity += 0.2

            # Penalize if there are conflicting numbers (different dosages)
            numbers1 = set(re.findall(r"\d+", norm1))
            numbers2 = set(re.findall(r"\d+", norm2))
            if numbers1 and numbers2 and not (numbers1 & numbers2):
                # Different numbers present - likely different dosages
                word_similarity *= 0.5

            return min(word_similarity, 1.0)

        # Levenshtein-like character similarity
        return MedicineNameMatcher._character_similarity(norm1, norm2)

    @staticmethod
    def _character_similarity(s1: str, s2: str) -> float:
        """
        Calculate character-based similarity (simplified Levenshtein).
        Args:
            s1: First string
            s2: Second string
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if len(s1) == 0 or len(s2) == 0:
            return 0.0

        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0

        # Count matching characters in similar positions
        matches = 0
        for i in range(min(len(s1), len(s2))):
            if s1[i] == s2[i]:
                matches += 1

        return matches / max_len

    @staticmethod
    def find_best_match(
        search_name: str, available_names: List[str], min_similarity: float = 0.6
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching medicine name from available options.

        Args:
            search_name: Name to search for
            available_names: List of available medicine names
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            Tuple of (best_match, similarity_score) or None if no good match found
        """
        if not search_name or not available_names:
            return None

        best_match = None
        best_score = 0.0

        for name in available_names:
            similarity = MedicineNameMatcher.calculate_similarity(search_name, name)
            if similarity > best_score and similarity >= min_similarity:
                best_score = similarity
                best_match = name

        return (best_match, best_score) if best_match else None

    @staticmethod
    def is_name_match(search_name: str, found_name: str, min_similarity: float = 0.7) -> bool:
        """
        Check if two medicine names match with given similarity threshold.

        Args:
            search_name: Name being searched for
            found_name: Name found on website
            min_similarity: Minimum similarity to consider a match

        Returns:
            True if names match above threshold
        """
        similarity = MedicineNameMatcher.calculate_similarity(search_name, found_name)
        return similarity >= min_similarity


class PharmacyTextParser:
    """Parser for pharmacy-related text content."""

    # Common Polish city names for address detection
    POLISH_CITIES = [
        "gdańsk",
        "warszawa",
        "kraków",
        "wrocław",
        "poznań",
        "łódź",
        "katowice",
        "bydgoszcz",
        "lublin",
        "białystok",
        "szczecin",
        "gdynia",
        "częstochowa",
        "radom",
        "sosnowiec",
        "toruń",
        "kielce",
        "olsztyn",
        "gliwice",
        "zabrze",
        "bytom",
    ]

    # Street indicators in Polish
    STREET_INDICATORS = ["ul.", "al.", "pl.", "os."]

    # Text patterns to skip when looking for pharmacy name
    SKIP_PATTERNS = ["znajdź", "leki", "okolicy", "zarezerwuj"]

    # Action text patterns to skip
    ACTION_PATTERNS = ["wyświetl", "zamknięta", "zapraszamy", "otwarta"]

    @classmethod
    def extract_pharmacy_name(cls, element_text: str) -> Optional[str]:
        """
        Extract pharmacy name from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Pharmacy name or None if not found
        """
        lines = [line.strip() for line in element_text.split("\n") if line.strip()]
        if not lines:
            return None

        # Look for pharmacy name in the lines - typically after distance info
        for i, line in enumerate(lines):
            # Skip first line if it contains search-related text
            if i == 0 and any(skip_word in line.lower() for skip_word in cls.SKIP_PATTERNS):
                continue

            # Skip lines that look like distance only (e.g., "252 m", "1.5 km")
            if cls._is_distance_line(line):
                continue

            # If line contains distance and name together (e.g., "34 m APTEKA"), extract just the name
            clean_line = cls._remove_distance_prefix(line)
            if clean_line != line and clean_line:
                # Skip lines that look like addresses after distance removal
                if cls._is_address_line(clean_line):
                    continue
                # Skip action lines after distance removal
                if any(action in clean_line.lower() for action in cls.ACTION_PATTERNS):
                    continue
                return clean_line

            # Skip lines that look like addresses
            if cls._is_address_line(line):
                continue

            # Skip action lines
            if any(action in line.lower() for action in cls.ACTION_PATTERNS):
                continue

            # This should be the pharmacy name
            if line:
                return line

        # Fallback to first line if no name found using smart logic
        return lines[0] if lines else None

    @classmethod
    def extract_address(cls, element_text: str) -> Optional[str]:
        """
        Extract address from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Address string or None if not found
        """
        lines = [line.strip() for line in element_text.split("\n") if line.strip()]

        for line in lines:
            if cls._is_address_line(line):
                return line

        return None

    @classmethod
    def extract_distance(cls, element_text: str) -> Optional[float]:
        """
        Extract distance in kilometers from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Distance in kilometers or None if not found
        """
        distance_match = re.search(r"(\d+[.,]?\d*)\s*(m|km)", element_text)
        if distance_match:
            distance_val = float(distance_match.group(1).replace(",", "."))
            unit = distance_match.group(2)
            if unit == "m":
                distance_val = distance_val / 1000
            return distance_val
        return None

    @classmethod
    def extract_phone(cls, element_text: str) -> Optional[str]:
        """
        Extract phone number from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Phone number or None if not found
        """
        phone_match = re.search(r"(\d{3}[\s-]?\d{3}[\s-]?\d{3})", element_text)
        return phone_match.group(1) if phone_match else None

    @classmethod
    def extract_price(cls, element_text: str) -> Optional[float]:
        """
        Extract price from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Price in PLN or None if not found
        """
        price_match = re.search(r"(\d+[.,]?\d*)\s*(?:zł|PLN)", element_text)
        if price_match:
            price_str = price_match.group(1).replace(",", ".")
            return float(price_str)
        return None

    @classmethod
    def extract_availability(cls, element_text: str) -> str:
        """
        Extract availability status from text content.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Availability status: 'high', 'low', 'none'
        """
        avail_text = element_text.lower()

        # Check for specific Polish availability terms from la-lek-ilosc div
        if "wiele sztuk" in avail_text:
            return "high"
        elif "ostatnie sztuki" in avail_text:
            return "low"
        elif "niedostępny" in avail_text or "brak" in avail_text:
            return "none"
        # If pharmacy has opening hours mentioned, assume low availability (pharmacy exists)
        elif any(term in avail_text for term in ["zapraszamy", "jutro", "otwarta", "zamknięta"]):
            return "low"
        else:
            # If no information at all, return none (unknown)
            return "none"

    @classmethod
    def parse_pharmacy_data(cls, element_text: str) -> Dict[str, Any]:
        """
        Parse all pharmacy data from text content.

        Note: Price extraction (full and refunded prices) is handled by the superior
        dynamic extraction method in PharmacyExtractor._extract_dynamic_prices()

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Dictionary with parsed pharmacy data
        """
        return {
            "name": cls.extract_pharmacy_name(element_text) or "Unknown Pharmacy",
            "address": cls.extract_address(element_text) or "",
            "phone": cls.extract_phone(element_text),
            "distance_km": cls.extract_distance(element_text),
            "availability": cls.extract_availability(element_text),
        }

    @classmethod
    def _is_distance_line(cls, line: str) -> bool:
        """
        Check if line contains only distance information.
        Args:
            line: Text line to check
        Returns:
            True if line looks like a distance (e.g., "34 m", "1.5 km"), False otherwise
        """
        return bool(re.match(r"^\d+[.,]?\d*\s*(m|km)$", line))

    @classmethod
    def _is_address_line(cls, line: str) -> bool:
        """
        Check if line looks like an address.
        Args:
            line: Text line to check
        Returns:
            True if line contains address-like patterns, False otherwise
        """
        line_lower = line.lower()

        # Check for address patterns - lines with commas and city names or street indicators
        has_comma_and_city = "," in line and any(city in line_lower for city in cls.POLISH_CITIES)
        has_street_indicator = any(indicator in line_lower for indicator in cls.STREET_INDICATORS)

        return has_comma_and_city or has_street_indicator

    @classmethod
    def _remove_distance_prefix(cls, line: str) -> str:
        """
        Remove distance prefix from a line if present.
        Args:
            line: Text line to process
        Returns:
            Line with distance prefix removed (e.g., "34 m APTEKA" -> "APTEKA")
        """
        # Pattern to match distance at the beginning of line (e.g., "34 m APTEKA" -> "APTEKA")
        distance_pattern = r"^\d+[.,]?\d*\s*(m|km)\s+"
        return re.sub(distance_pattern, "", line).strip()

    @classmethod
    def extract_dosage_and_amount(cls, element_text: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract dosage and amount from combined text like "50 mcg | 50 tabl.".

        Args:
            element_text: Raw text content from medicine element

        Returns:
            Tuple of (dosage, amount) where either can be None if not found
        """
        # Look for combined pattern like "50 mcg | 50 tabl."
        combined_pattern = r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|g|μg|%|ml|l)\s*\|\s*(\d+)\s*(tabl\.|szt\.|kaps\.|amp\.|ml|g)"
        combined_match = re.search(combined_pattern, element_text, re.IGNORECASE)

        if combined_match:
            dosage_value = combined_match.group(1).replace(",", ".")
            dosage_unit = combined_match.group(2)
            amount_value = combined_match.group(3)
            amount_unit = combined_match.group(4)

            dosage = f"{dosage_value} {dosage_unit}"
            amount = f"{amount_value} {amount_unit}"

            return dosage, amount

        # If no combined pattern, try to extract separately
        dosage = cls.extract_dosage_only(element_text)
        amount = cls.extract_amount_only(element_text)

        return dosage, amount

    @classmethod
    def extract_dosage_only(cls, element_text: str) -> Optional[str]:
        """
        Extract dosage from text content.

        Args:
            element_text: Raw text content from medicine element

        Returns:
            Dosage string or None if not found
        """
        dosage_patterns = [
            r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|g|μg)",  # 500 mg, 250 mcg, etc.
            r"(\d+(?:[.,]\d+)?)\s*%",  # 5%, etc.
            r"(\d+(?:[.,]\d+)?)\s*(ml|l)",  # 200 ml, etc. (for liquid dosages)
        ]

        for pattern in dosage_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                value = match.group(1).replace(",", ".")
                unit = match.group(2) if len(match.groups()) > 1 else "%"
                return f"{value} {unit}"

        return None

    @classmethod
    def extract_amount_only(cls, element_text: str) -> Optional[str]:
        """
        Extract amount (package size) from text content.

        Args:
            element_text: Raw text content from medicine element

        Returns:
            Amount string or None if not found
        """
        amount_patterns = [
            r"(\d+)\s*(tabl\.)",  # 50 tabl.
            r"(\d+)\s*(szt\.)",  # 30 szt.
            r"(\d+)\s*(kaps\.)",  # 60 kaps.
            r"(\d+)\s*(amp\.)",  # 5 amp.
            r"(\d+)\s*(ml)",  # 200 ml (for liquid packages)
            r"(\d+)\s*(g)",  # 100 g (for creams/ointments)
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2)
                return f"{value} {unit}"

        return None

    @classmethod
    def matches_dosage_and_amount(
        cls,
        search_dosage: Optional[str],
        search_amount: Optional[str],
        found_dosage: Optional[str],
        found_amount: Optional[str],
    ) -> bool:
        """
        Check if found dosage and amount match the search criteria.

        Args:
            search_dosage: Required dosage (e.g., "50 mcg")
            search_amount: Required amount (e.g., "50 tabl.")
            found_dosage: Dosage found in medicine listing
            found_amount: Amount found in medicine listing

        Returns:
            True if matches search criteria, False otherwise
        """
        # If no search criteria specified, any found values match
        if not search_dosage and not search_amount:
            return True

        # Check dosage match
        dosage_matches = True
        if search_dosage:
            if not found_dosage:
                dosage_matches = False
            else:
                # Normalize and compare dosages
                search_norm = cls._normalize_dosage(search_dosage)
                found_norm = cls._normalize_dosage(found_dosage)
                dosage_matches = search_norm == found_norm

        # Check amount match
        amount_matches = True
        if search_amount:
            if not found_amount:
                amount_matches = False
            else:
                # Normalize and compare amounts
                search_norm = cls._normalize_amount(search_amount)
                found_norm = cls._normalize_amount(found_amount)
                amount_matches = search_norm == found_norm

        return dosage_matches and amount_matches

    @classmethod
    def _normalize_dosage(cls, dosage: str) -> str:
        """
        Normalize dosage string for comparison with fuzzy matching for user input.
        Args:
            dosage: Dosage string to normalize (e.g., "50 mg", "20 mcg")
        Returns:
            Normalized dosage string (e.g., "50 mg", "20 mcg")
        """
        if not dosage:
            return ""

        # Convert to lowercase and standardize units
        dosage = dosage.lower().strip()

        # Extract number and unit with more flexible patterns
        # Handle patterns like "50mg", "50 mg", "50mg.", "50 mcg", etc.
        match = re.match(r"(\d+(?:[.,]\d+)?)\s*([a-zA-ZμµγΓ%]+\.?)", dosage)
        if match:
            value = match.group(1).replace(",", ".")
            unit = match.group(2).rstrip(".")  # Remove trailing dots

            # Comprehensive unit mapping with fuzzy matching for user input
            unit_map = {
                # Weight units
                "mg": "mg",
                "milligram": "mg",
                "miligram": "mg",  # Common typo
                "mcg": "mcg",
                "microgram": "mcg",
                "mikrogram": "mcg",
                "μg": "mcg",  # Greek mu
                "µg": "mcg",  # Micro sign
                "ug": "mcg",  # User might type without special chars
                "mikrog": "mcg",  # Short form
                "g": "g",
                "gram": "g",
                "gr": "g",  # Short form
                # Volume units
                "ml": "ml",
                "milliliter": "ml",
                "mililitr": "ml",  # Polish spelling
                "l": "l",
                "liter": "l",
                "litr": "l",  # Polish spelling
                # Percentage
                "%": "%",
                "percent": "%",
                "procent": "%",  # Polish
                # International units
                "iu": "iu",
                "ui": "iu",  # Alternative
                "j.m.": "iu",  # Polish abbreviation
                "jm": "iu",  # Without dots
                # Other common units
                "mmol": "mmol",
                "mol": "mol",
                "eq": "eq",
                "meq": "meq",
            }

            # Find best match for unit (handle typos and variations)
            normalized_unit = unit_map.get(unit, unit)

            # If exact match not found, try fuzzy matching for common typos
            if normalized_unit == unit and unit not in unit_map:
                for standard_unit, canonical in unit_map.items():
                    # Simple similarity check for typos (allow 1-2 character differences)
                    if abs(len(unit) - len(standard_unit)) <= 2:
                        # Check character overlap
                        common_chars = sum(1 for c1, c2 in zip(unit, standard_unit) if c1 == c2)
                        if common_chars >= len(unit) - 2:  # Allow up to 2 different chars
                            normalized_unit = canonical
                            break

            return f"{value} {normalized_unit}"

        return dosage

    @classmethod
    def _normalize_amount(cls, amount: str) -> str:
        """
        Normalize amount string for comparison with fuzzy matching for user input.
        Args:
            amount: Amount string to normalize (e.g., "50 tabl.", "20 kaps.")
        Returns:
            Normalized amount string (e.g., "50 tabl", "20 kaps")
        """
        if not amount:
            return ""

        # Convert to lowercase and standardize units
        amount = amount.lower().strip()

        # Extract number and unit with flexible patterns
        # Handle patterns like "20tabl", "20 tabl.", "20 tab", "20t", etc.
        match = re.match(r"(\d+)\s*([a-zA-Z]+\.?)", amount)
        if match:
            value = match.group(1)
            unit = match.group(2).rstrip(".")  # Remove trailing dots

            # Comprehensive unit mapping with fuzzy matching for user input
            unit_map = {
                # Tablets - most common variations
                "tabl": "tabl",
                "tablet": "tabl",
                "tabletek": "tabl",  # Polish plural
                "tabletki": "tabl",  # Polish
                "tab": "tabl",  # Common abbreviation
                "t": "tabl",  # Very short form
                "tabs": "tabl",  # English plural
                "tbl": "tabl",  # Another abbreviation
                # Capsules
                "kaps": "kaps",
                "kapsułek": "kaps",  # Polish plural
                "kapsułki": "kaps",  # Polish
                "kap": "kaps",  # User abbreviation
                "capsule": "kaps",
                "caps": "kaps",
                "cap": "kaps",
                "k": "kaps",  # Very short form
                # Pieces
                "szt": "szt",
                "sztuk": "szt",  # Polish plural
                "pieces": "szt",
                "pcs": "szt",
                "pc": "szt",
                "s": "szt",  # Very short form
                # Ampoules
                "amp": "amp",
                "ampułek": "amp",  # Polish plural
                "ampułki": "amp",  # Polish
                "ampoule": "amp",
                "ampoules": "amp",
                "a": "amp",  # Very short form
                # Volume units
                "ml": "ml",
                "milliliter": "ml",
                "mililitr": "ml",  # Polish
                "g": "g",
                "gram": "g",
                "gr": "g",
                # Drops
                "krople": "krople",
                "kropli": "krople",  # Polish genitive
                "drops": "krople",
                "drop": "krople",
                # Patches
                "plaster": "plaster",
                "plastry": "plaster",  # Polish plural
                "patch": "plaster",
                "patches": "plaster",
                # Sachets
                "saszetka": "saszetka",
                "saszetki": "saszetka",  # Polish plural
                "sachet": "saszetka",
                "sachets": "saszetka",
                # Vials
                "fiolka": "fiolka",
                "fiolki": "fiolka",  # Polish plural
                "vial": "fiolka",
                "vials": "fiolka",
            }

            # Find best match for unit (handle typos and variations)
            normalized_unit = unit_map.get(unit, unit)

            # If exact match not found, try fuzzy matching for common typos
            if normalized_unit == unit and unit not in unit_map:
                for standard_unit, canonical in unit_map.items():
                    # Simple similarity check for typos (allow 1-2 character differences)
                    if abs(len(unit) - len(standard_unit)) <= 2:
                        # Check character overlap
                        common_chars = sum(1 for c1, c2 in zip(unit, standard_unit) if c1 == c2)
                        if common_chars >= max(1, len(unit) - 2):  # Allow up to 2 different chars
                            normalized_unit = canonical
                            break

            return f"{value} {normalized_unit}"

        return amount

    @classmethod
    def extract_additional_info(cls, element_text: str) -> Optional[str]:
        """
        Extract additional pharmacy information like prescription requirements, refund status, and stock details.

        This sophisticated feature was lost during refactoring and is now restored.

        Args:
            element_text: Raw text content from pharmacy element

        Returns:
            Formatted additional info string, or None if no additional info found
        """
        try:
            additional_info_parts = []

            # Look for prescription information
            if "recepta" in element_text.lower():
                additional_info_parts.append("Wymaga recepty")
            elif "bez recepty" in element_text.lower():
                additional_info_parts.append("Bez recepty")

            # Look for refund information
            if "refundacja" in element_text.lower() or "refundowane" in element_text.lower():
                additional_info_parts.append("Refundowane")
            elif "100% dopłata" in element_text.lower() or "pełna płatność" in element_text.lower():
                additional_info_parts.append("Pełna płatność")

            # Look for availability details beyond just the level
            if "tylko" in element_text.lower() and "sztuk" in element_text.lower():
                stock_match = re.search(r"tylko\s+(\d+)\s+sztuk", element_text.lower())
                if stock_match:
                    additional_info_parts.append(f"Tylko {stock_match.group(1)} szt.")

            # Return combined info or None
            return " | ".join(additional_info_parts) if additional_info_parts else None

        except Exception as e:
            return None


class LocationTextParser:
    """Handles location text parsing and matching for Polish cities and addresses."""

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Normalize text by removing Polish diacritics.

        Args:
            text: Text with Polish characters

        Returns:
            Text with diacritics replaced by base characters
        """
        if not text:
            return ""

        # Normalize unicode characters (decompose diacritics)
        normalized = unicodedata.normalize("NFD", text)
        # Filter out diacritical marks
        without_diacritics = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        return without_diacritics

    @classmethod
    def parse_location_parts(cls, location: str) -> Tuple[str, str]:
        """
        Parse location string into city and street components.

        Args:
            location: Location string like "Poznań" or "Poznań, Słowackiego"

        Returns:
            Tuple of (city, street) both lowercased
        """
        if not location:
            return "", ""

        # Split by comma and clean up
        parts = [part.strip() for part in location.split(",")]

        city = parts[0].lower() if parts else ""
        street = parts[1].lower() if len(parts) > 1 else ""

        return city, street

    @classmethod
    def calculate_location_match_score(cls, search_location: str, option_city: str, option_street: str) -> int:
        """
        Calculate a match score between search location and option location.

        Args:
            search_location: The location being searched for
            option_city: City from the option
            option_street: Street from the option

        Returns:
            Match score (higher is better, 0 means no match)
        """
        if not search_location:
            return 0

        search_city, search_street = cls.parse_location_parts(search_location)
        option_city_lower = option_city.lower() if option_city else ""
        option_street_lower = option_street.lower() if option_street else ""

        score = 0

        # City matching
        if search_city and option_city_lower:
            if search_city == option_city_lower:
                score += 15  # Exact city match
            elif search_city in option_city_lower or option_city_lower in search_city:
                score += 10  # Partial city match

        # Street matching
        if search_street and option_street_lower:
            if search_street in option_street_lower or option_street_lower in search_street:
                score += 5  # Street match

        return score
