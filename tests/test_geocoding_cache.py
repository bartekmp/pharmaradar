"""
Tests for geocoding result caching in MedicineFinder.
"""

from unittest.mock import MagicMock, patch

from pharmaradar.medicine_scraper import MedicineFinder


def _make_finder() -> MedicineFinder:
    """Create a MedicineFinder without starting Chrome."""
    finder = MedicineFinder.__new__(MedicineFinder)
    finder.headless = True
    finder.timeout = 15
    finder._webdriver_available = None
    finder._geocode_cache = {}
    finder.driver_manager = MagicMock()
    finder.log = MagicMock()
    return finder


class TestGeocodingCache:
    def test_geocode_called_once_for_same_location(self):
        finder = _make_finder()
        coords = (21.01, 52.23)

        with patch.object(MedicineFinder, "_geocode_address", return_value=coords) as mock_geocode:
            finder._set_location_via_js(finder.driver_manager, "Warszawa")
            finder._set_location_via_js(finder.driver_manager, "Warszawa")

        mock_geocode.assert_called_once_with("Warszawa")

    def test_geocode_called_separately_for_different_locations(self):
        finder = _make_finder()
        coords = (21.01, 52.23)

        with patch.object(MedicineFinder, "_geocode_address", return_value=coords) as mock_geocode:
            finder._set_location_via_js(finder.driver_manager, "Warszawa")
            finder._set_location_via_js(finder.driver_manager, "Kraków")

        assert mock_geocode.call_count == 2

    def test_failed_geocode_result_is_cached(self):
        """None result (geocoding failure) should also be cached — not retried every call."""
        finder = _make_finder()

        with patch.object(MedicineFinder, "_geocode_address", return_value=None) as mock_geocode:
            finder._set_location_via_js(finder.driver_manager, "Nieznane Miejsce")
            finder._set_location_via_js(finder.driver_manager, "Nieznane Miejsce")

        mock_geocode.assert_called_once()

    def test_cache_is_populated_after_first_call(self):
        finder = _make_finder()
        coords = (21.01, 52.23)

        with patch.object(MedicineFinder, "_geocode_address", return_value=coords):
            finder._set_location_via_js(finder.driver_manager, "Gdańsk")

        assert "Gdańsk" in finder._geocode_cache
        assert finder._geocode_cache["Gdańsk"] == coords

    def test_cache_starts_empty(self):
        finder = _make_finder()
        assert finder._geocode_cache == {}
