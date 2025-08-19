"""
Tests for medicine name fuzzy matching functionality.
"""

from pharmaradar.text_parsers import MedicineNameMatcher


class TestMedicineNameMatcher:
    """Test cases for medicine name fuzzy matching."""

    def test_case_insensitive_matching(self):
        """Test that matching works regardless of case."""
        assert MedicineNameMatcher.is_name_match("euthyrox n 100", "Euthyrox N 100")
        assert MedicineNameMatcher.is_name_match("ASPIRIN", "aspirin")
        assert MedicineNameMatcher.is_name_match("Vitamin C", "VITAMIN C")

    def test_polish_diacritics_matching(self):
        """Test that Polish diacritics are normalized correctly."""
        assert MedicineNameMatcher.is_name_match("witamina c", "Witamina C")
        assert MedicineNameMatcher.is_name_match("lek z ą", "Lek z a")

    def test_partial_matching(self):
        """Test partial matching for medicine names."""
        assert MedicineNameMatcher.is_name_match("aspirin", "Aspirin 500mg")
        assert MedicineNameMatcher.is_name_match("euthyrox", "Euthyrox N 100")

    def test_dosage_conflict_prevention(self):
        """Test that different dosages are properly distinguished."""
        # These should NOT match due to different dosages
        similarity = MedicineNameMatcher.calculate_similarity("euthyrox n 100", "Euthyrox N 50")
        assert similarity < 0.7  # Below default threshold

    def test_polish_english_variants(self):
        """Test Polish-English medicine name variants."""
        assert MedicineNameMatcher.is_name_match("witamina c", "Vitamin C")
        similarity = MedicineNameMatcher.calculate_similarity("witamina c", "Vitamin C")
        assert similarity >= 0.7

    def test_special_characters_normalization(self):
        """Test that special characters are handled correctly."""
        assert MedicineNameMatcher.is_name_match("euthyrox-100", "Euthyrox N 100")
        assert MedicineNameMatcher.is_name_match("co-q10", "Coenzyme Q10", min_similarity=0.5)

    def test_short_name_prevention(self):
        """Test that very short names don't match everything."""
        assert not MedicineNameMatcher.is_name_match("C", "Vitamin C")
        assert not MedicineNameMatcher.is_name_match("Mg", "Magnesium")

    def test_find_best_match(self):
        """Test finding best match from a list of options."""
        available_medicines = [
            "Euthyrox N 50",
            "Euthyrox N 100",
            "Aspirin 500mg",
            "Ibuprofen forte",
        ]

        result = MedicineNameMatcher.find_best_match("euthyrox n 100", available_medicines)
        assert result is not None
        best_match, similarity = result
        assert best_match == "Euthyrox N 100"
        assert similarity >= 0.9

        # Test no match found
        result = MedicineNameMatcher.find_best_match("nonexistent medicine", available_medicines)
        assert result is None

    def test_no_common_words(self):
        """Test that completely different medicines don't match."""
        assert not MedicineNameMatcher.is_name_match("aspirin", "ibuprofen")
        assert not MedicineNameMatcher.is_name_match("euthyrox", "completely different medicine")

    def test_similarity_scores(self):
        """Test that similarity scores are reasonable."""
        # Exact match should be 1.0
        assert MedicineNameMatcher.calculate_similarity("aspirin", "aspirin") == 1.0

        # Case difference should still be 1.0
        assert MedicineNameMatcher.calculate_similarity("aspirin", "ASPIRIN") == 1.0

        # Partial match should be high but not 1.0
        similarity = MedicineNameMatcher.calculate_similarity("aspirin", "Aspirin 500mg")
        assert 0.8 <= similarity < 1.0

        # No match should be 0.0
        assert MedicineNameMatcher.calculate_similarity("aspirin", "ibuprofen") == 0.0
