"""
Test module for text parsing utilities.
"""

from pharmaradar.medicine import Medicine
from pharmaradar.text_parsers import LocationTextParser, PharmacyTextParser


class TestPharmacyTextParser:
    """Test the pharmacy text parsing functionality."""

    def test_extract_pharmacy_name_simple(self):
        """Test extracting pharmacy name from simple text."""
        text = """APTEKA ZIELONA MIŁA
Olsztyn, Kwiatowa 15
Wyświetl numer"""

        name = PharmacyTextParser.extract_pharmacy_name(text)
        assert name == "APTEKA ZIELONA MIŁA"

    def test_extract_pharmacy_name_with_search_text(self):
        """Test extracting pharmacy name when search text is present."""
        text = """Znajdź leki w okolicy i zarezerwuj
252 m
APTEKA ZIELONA MIŁA
Olsztyn, Kwiatowa 15
Wyświetl numer
Zamknięta, zapraszamy jutro (08:00 – 20:00)"""

        name = PharmacyTextParser.extract_pharmacy_name(text)
        assert name == "APTEKA ZIELONA MIŁA"

    def test_extract_pharmacy_name_with_distance(self):
        """Test extracting pharmacy name when distance is in separate line."""
        text = """1,2 km
APTEKA POD SŁONIEM
Wrocław, Parkowa 89
Dostępne"""

        name = PharmacyTextParser.extract_pharmacy_name(text)
        assert name == "APTEKA POD SŁONIEM"

    def test_extract_address_simple(self):
        """Test extracting address from text."""
        text = """APTEKA ZIELONA MIŁA
Olsztyn, Kwiatowa 15
Wyświetl numer"""

        address = PharmacyTextParser.extract_address(text)
        assert address == "Olsztyn, Kwiatowa 15"

    def test_extract_address_with_street_indicator(self):
        """Test extracting address with street indicator."""
        text = """APTEKA TESTOWA
ul. Słowackiego 45
Lublin"""

        address = PharmacyTextParser.extract_address(text)
        assert address == "ul. Słowackiego 45"

    def test_extract_distance_meters(self):
        """Test extracting distance in meters."""
        text = """252 m
APTEKA ZIELONA MIŁA"""

        distance = PharmacyTextParser.extract_distance(text)
        assert distance == 0.252

    def test_extract_distance_kilometers(self):
        """Test extracting distance in kilometers."""
        text = """1,5 km
APTEKA TESTOWA"""

        distance = PharmacyTextParser.extract_distance(text)
        assert distance == 1.5

    def test_extract_phone(self):
        """Test extracting phone number."""
        text = """APTEKA ZIELONA MIŁA
Olsztyn, Kwiatowa 15
Tel: 123 456 789"""

        phone = PharmacyTextParser.extract_phone(text)
        assert phone == "123 456 789"

    def test_extract_price(self):
        """Test extracting price."""
        text = """APTEKA ZIELONA MIŁA
Placeholderium R 1000
Cena: 72,08 zł"""

        price = PharmacyTextParser.extract_price(text)
        assert price == 72.08

    def test_extract_availability_high(self):
        """Test extracting availability - high."""
        text = """APTEKA ZIELONA MIŁA
Placeholderium R 1000
wiele sztuk"""

        availability = PharmacyTextParser.extract_availability(text)
        assert availability == "high"

    def test_extract_availability_low(self):
        """Test extracting availability - low."""
        text = """APTEKA ZIELONA MIŁA
Placeholderium R 1000
ostatnie sztuki"""

        availability = PharmacyTextParser.extract_availability(text)
        assert availability == "low"

    def test_extract_availability_unknown(self):
        """Test extracting availability - unknown."""
        text = """APTEKA ZIELONA MIŁA
Placeholderium R 1000
jakiś inny tekst"""

        availability = PharmacyTextParser.extract_availability(text)
        assert availability == "none"

    def test_parse_pharmacy_data_complete(self):
        """Test parsing complete pharmacy data."""
        text = """252 m
APTEKA ZIELONA MIŁA
Olsztyn, Kwiatowa 15
Tel: 123 456 789
Cena: 72,08 zł
wiele sztuk"""

        data = PharmacyTextParser.parse_pharmacy_data(text)

        assert data["name"] == "APTEKA ZIELONA MIŁA"
        assert data["address"] == "Olsztyn, Kwiatowa 15"
        assert data["phone"] == "123 456 789"
        assert data["distance_km"] == 0.252
        assert data["availability"] == "high"


class TestLocationTextParser:
    """Test the location text parsing functionality."""

    def test_normalize_text_polish_chars(self):
        """Test normalizing Polish characters."""
        text = "Poznań, ul. Grójecka"
        normalized = LocationTextParser.normalize_text(text)
        assert normalized == "Poznan, ul. Grojecka"

    def test_parse_location_parts_city_only(self):
        """Test parsing location with city only."""
        location = "Poznań"
        city, street = LocationTextParser.parse_location_parts(location)
        assert city == "poznań"
        assert street == ""

    def test_parse_location_parts_city_and_street(self):
        """Test parsing location with city and street."""
        location = "Poznań, Słowackiego"
        city, street = LocationTextParser.parse_location_parts(location)
        assert city == "poznań"
        assert street == "słowackiego"

    def test_calculate_location_match_score_exact_city(self):
        """Test location matching with exact city match."""
        score = LocationTextParser.calculate_location_match_score("Poznań", "Poznań", "")
        assert score >= 15  # 10 for city match + 5 for exact match

    def test_calculate_location_match_score_city_and_street(self):
        """Test location matching with city and street."""
        score = LocationTextParser.calculate_location_match_score("Poznań, Słowackiego", "Poznań", "ul. Słowackiego 45")
        assert score >= 15  # Should get points for both city and street matching

    def test_calculate_location_match_score_no_match(self):
        """Test location matching with no match."""
        score = LocationTextParser.calculate_location_match_score("Lublin", "Poznań", "")
        assert score == 0


class TestPharmacyTextParserDosageAmount:
    """Test the dosage and amount extraction functionality."""

    def test_extract_combined_dosage_amount(self):
        """Test extracting combined dosage and amount like '50 mcg | 50 tabl.'"""
        text = "Placeholderium R 1000\n50 mcg | 50 tabl.\nCena: 25,50 zł"

        dosage, amount = PharmacyTextParser.extract_dosage_and_amount(text)

        assert dosage == "50 mcg"
        assert amount == "50 tabl."

    def test_extract_combined_different_units(self):
        """Test extracting different dosage and amount units"""
        test_cases = [
            ("250 mg | 30 szt.", "250 mg", "30 szt."),
            ("5.5 ml | 100 ml", "5.5 ml", "100 ml"),
            ("2,5 g | 60 kaps.", "2.5 g", "60 kaps."),
            ("10 % | 5 amp.", "10 %", "5 amp."),
        ]

        for text, expected_dosage, expected_amount in test_cases:
            dosage, amount = PharmacyTextParser.extract_dosage_and_amount(text)
            assert dosage == expected_dosage, f"Failed for: {text}"
            assert amount == expected_amount, f"Failed for: {text}"

    def test_extract_dosage_only(self):
        """Test extracting only dosage when amount not present"""
        text = "Placeholderium R 1000\n500 mg\nDostępny"

        dosage, amount = PharmacyTextParser.extract_dosage_and_amount(text)

        assert dosage == "500 mg"
        assert amount is None

    def test_extract_amount_only(self):
        """Test extracting only amount when dosage not present"""
        text = "Placeholderium R 1000\n30 tabl.\nDostępny"

        dosage, amount = PharmacyTextParser.extract_dosage_and_amount(text)

        assert dosage is None
        assert amount == "30 tabl."

    def test_extract_separate_dosage_amount(self):
        """Test extracting dosage and amount when not combined with |"""
        text = "Placeholderium R 1000\n250 mg\n60 tabl.\nCena: 15 zł"

        dosage, amount = PharmacyTextParser.extract_dosage_and_amount(text)

        assert dosage == "250 mg"
        assert amount == "60 tabl."

    def test_normalize_dosage(self):
        """Test dosage normalization"""
        test_cases = [
            ("50 mcg", "50 mcg"),
            ("50 μg", "50 mcg"),  # μg should be converted to mcg
            ("2,5 mg", "2.5 mg"),  # comma to dot conversion
            ("5 %", "5 %"),
            ("200 ml", "200 ml"),
        ]

        for input_dosage, expected in test_cases:
            result = PharmacyTextParser._normalize_dosage(input_dosage)
            assert result == expected, f"Failed for: {input_dosage}"

    def test_normalize_amount(self):
        """Test amount normalization"""
        test_cases = [
            ("50 tabl.", "50 tabl"),
            ("30 szt.", "30 szt"),
            ("60 kaps.", "60 kaps"),
            ("5 amp.", "5 amp"),
            ("100 ml", "100 ml"),
            ("50 g", "50 g"),
        ]

        for input_amount, expected in test_cases:
            result = PharmacyTextParser._normalize_amount(input_amount)
            assert result == expected, f"Failed for: {input_amount}"

    def test_matches_dosage_and_amount_exact(self):
        """Test exact dosage and amount matching"""
        # Exact match
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", "50 mcg", "50 tabl.") is True

        # Different dosage
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", "100 mcg", "50 tabl.") is False

        # Different amount
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", "50 mcg", "30 tabl.") is False

    def test_matches_dosage_and_amount_normalization(self):
        """Test dosage and amount matching with normalization"""
        # μg vs mcg conversion
        assert PharmacyTextParser.matches_dosage_and_amount("50 μg", "50 tabl.", "50 mcg", "50 tabl.") is True

        # Comma vs dot conversion
        assert PharmacyTextParser.matches_dosage_and_amount("2,5 mg", "30 szt.", "2.5 mg", "30 szt.") is True

        # Dot vs no dot in amount units
        assert PharmacyTextParser.matches_dosage_and_amount("100 mg", "50 tabl.", "100 mg", "50 tabl") is True

    def test_matches_dosage_and_amount_partial_criteria(self):
        """Test matching when only some criteria specified"""
        # Only dosage specified - should match any amount
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", None, "50 mcg", "30 tabl.") is True

        # Only amount specified - should match any dosage
        assert PharmacyTextParser.matches_dosage_and_amount(None, "50 tabl.", "100 mg", "50 tabl.") is True

        # No criteria specified - should match anything
        assert PharmacyTextParser.matches_dosage_and_amount(None, None, "100 mg", "30 tabl.") is True

    def test_matches_dosage_and_amount_missing_found_values(self):
        """Test matching when found values are missing"""
        # Search criteria specified but found values missing
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", None, None) is False

        # Only dosage found, amount required
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", "50 mcg", None) is False

        # Only amount found, dosage required
        assert PharmacyTextParser.matches_dosage_and_amount("50 mcg", "50 tabl.", None, "50 tabl.") is False

    def test_normalize_dosage_fuzzy_user_input(self):
        """Test enhanced dosage normalization with user input variants and typos."""
        test_cases = [
            # Standard cases
            ("50 mg", "50 mg", "exact match"),
            ("50mg", "50 mg", "no space"),
            ("50 mg.", "50 mg", "with trailing dot"),
            # Unit variations for mcg
            ("50 mcg", "50 mcg", "mcg standard"),
            ("50 μg", "50 mcg", "Greek mu to mcg"),
            ("50 µg", "50 mcg", "micro sign to mcg"),
            ("50 ug", "50 mcg", "ug without special char"),
            ("50 microgram", "50 mcg", "full word microgram"),
            ("50 mikrogram", "50 mcg", "Polish mikrogram"),
            # Other unit variations
            ("1 g", "1 g", "gram standard"),
            ("1 gram", "1 g", "full word gram"),
            ("1 gr", "1 g", "gram abbreviation"),
            ("100 ml", "100 ml", "milliliter standard"),
            ("100 milliliter", "100 ml", "full word milliliter"),
            ("100 mililitr", "100 ml", "Polish milliliter"),
            # Case variations
            ("50 MG", "50 mg", "uppercase"),
            ("50 Mg", "50 mg", "mixed case"),
            ("50 MCG", "50 mcg", "uppercase mcg"),
            # Common typos
            ("50 miligram", "50 mg", "miligram typo"),
        ]

        for input_dosage, expected, description in test_cases:
            result = PharmacyTextParser._normalize_dosage(input_dosage)
            assert result == expected, f"Failed {description}: '{input_dosage}' -> '{result}' (expected '{expected}')"

    def test_normalize_amount_fuzzy_user_input(self):
        """Test enhanced amount normalization with user input variants and typos."""
        test_cases = [
            # Tablet variations
            ("20 tabl", "20 tabl", "tabl standard"),
            ("20 tabl.", "20 tabl", "tabl with dot"),
            ("20 tab", "20 tabl", "tab abbreviation"),
            ("20 t", "20 tabl", "single letter t"),
            ("20 tabs", "20 tabl", "English plural tabs"),
            ("20 tablet", "20 tabl", "full word tablet"),
            ("20 tabletek", "20 tabl", "Polish plural tabletek"),
            ("20 tabletki", "20 tabl", "Polish tabletki"),
            # Capsule variations
            ("10 kaps", "10 kaps", "kaps standard"),
            ("10 kap", "10 kaps", "kap abbreviation"),
            ("10 k", "10 kaps", "single letter k"),
            ("10 capsule", "10 kaps", "full word capsule"),
            ("10 caps", "10 kaps", "caps abbreviation"),
            ("10 cap", "10 kaps", "cap abbreviation"),
            # Pieces variations
            ("50 szt", "50 szt", "szt standard"),
            ("50 sztuk", "50 szt", "Polish plural sztuk"),
            ("50 pieces", "50 szt", "English pieces"),
            ("50 pcs", "50 szt", "pcs abbreviation"),
            ("50 s", "50 szt", "single letter s"),
            # Ampoule variations
            ("5 amp", "5 amp", "amp standard"),
            ("5 ampułek", "5 amp", "Polish plural ampułek"),
            ("5 ampułki", "5 amp", "Polish ampułki"),
            ("5 ampoule", "5 amp", "full word ampoule"),
            ("5 a", "5 amp", "single letter a"),
            # Case variations
            ("20 TABL", "20 tabl", "uppercase"),
            ("20 Tab", "20 tabl", "mixed case"),
            ("10 KAPS", "10 kaps", "uppercase kaps"),
        ]

        for input_amount, expected, description in test_cases:
            result = PharmacyTextParser._normalize_amount(input_amount)
            assert result == expected, f"Failed {description}: '{input_amount}' -> '{result}' (expected '{expected}')"

    def test_matches_dosage_and_amount_fuzzy_user_input(self):
        """Test complete fuzzy matching with user input variants."""
        test_cases = [
            # User input with variants should match official format
            ("50 mg", "20 tab", "50 mg", "20 tabl", True, "tab vs tabl variant"),
            ("50 mcg", "30 t", "50 μg", "30 tabl", True, "mcg/μg and t/tabl variants"),
            ("100 mg", "10 kap", "100 mg", "10 kaps", True, "kap vs kaps variant"),
            ("50 ug", "20 tabs", "50 mcg", "20 tabl", True, "ug/mcg and tabs/tabl variants"),
            # Exact matches should still work
            ("50 mg", "20 tabl", "50 mg", "20 tabl", True, "exact match"),
            # Different values should not match
            ("50 mg", "20 tabl", "100 mg", "20 tabl", False, "different dosage"),
            ("50 mg", "20 tabl", "50 mg", "30 tabl", False, "different amount"),
            ("50 mg", "20 tabl", "50 g", "20 kaps", False, "completely different"),
            # Partial criteria (only dosage or amount specified)
            ("50 mg", None, "50 mg", "20 tabl", True, "only dosage matters"),
            (None, "20 tab", "50 mg", "20 tabl", True, "only amount matters with variant"),
            (None, None, "50 mg", "20 tabl", True, "no criteria specified"),
            # Case sensitivity should not matter
            ("50 MG", "20 TAB", "50 mg", "20 tabl", True, "case insensitive matching"),
        ]

        for search_dosage, search_amount, found_dosage, found_amount, expected_match, description in test_cases:
            actual_match = PharmacyTextParser.matches_dosage_and_amount(
                search_dosage, search_amount, found_dosage, found_amount
            )
            assert actual_match == expected_match, (
                f"Failed {description}: "
                f"Search: {search_dosage or 'None'} {search_amount or 'None'} "
                f"vs Found: {found_dosage or 'None'} {found_amount or 'None'} "
                f"-> got {actual_match}, expected {expected_match}"
            )


class TestMedicineAmount:
    """Test the Medicine class with amount field."""

    def test_medicine_full_name_with_amount(self):
        """Test full name includes amount when specified."""
        medicine = Medicine(name="Placeholderium R 1000", dosage="50 mcg", amount="50 tabl.")
        assert medicine.full_name == "Placeholderium R 1000 | 50 mcg | 50 tabl."

    def test_medicine_full_name_dosage_only(self):
        """Test full name with dosage but no amount."""
        medicine = Medicine(name="Placeholderium R 1000", dosage="50 mcg")
        assert medicine.full_name == "Placeholderium R 1000 | 50 mcg"

    def test_medicine_full_name_amount_only(self):
        """Test full name with amount but no dosage."""
        medicine = Medicine(name="Placeholderium R 1000", amount="50 tabl.")
        assert medicine.full_name == "Placeholderium R 1000 | 50 tabl."

    def test_medicine_to_dict_with_amount(self):
        """Test medicine serialization includes amount."""
        medicine = Medicine(name="Placeholderium R 1000", dosage="50 mcg", amount="50 tabl.", location="Gdańsk")
        data = medicine.to_dict()
        assert data["amount"] == "50 tabl."

    def test_medicine_from_dict_with_amount(self):
        """Test medicine deserialization includes amount."""
        data = {
            "name": "Placeholderium R 1000",
            "dosage": "50 mcg",
            "amount": "50 tabl.",
            "location": "Gdańsk",
            "radius_km": 5.0,
        }
        medicine = Medicine.from_dict(data)
        assert medicine.amount == "50 tabl."
