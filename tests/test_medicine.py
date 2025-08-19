"""
Test module for basic medicine functionality.
"""

from pharmaradar import Medicine
from pharmaradar.availability_level import AvailabilityLevel
from pharmaradar.pharmacy_info import PharmacyInfo


class TestMedicineBasic:
    """Test basic medicine functionality."""

    def test_medicine_creation(self):
        """Test creating a Medicine object."""
        medicine = Medicine(
            name="Placeholderium R 1000",
            dosage="400mg",
            location="Lublin",
            radius_km=10.0,
            max_price=20.0,
            min_availability=AvailabilityLevel.HIGH,
            title="Placeholderium R 1000 search",
        )

        assert medicine.name == "Placeholderium R 1000"
        assert medicine.dosage == "400mg"
        assert medicine.location == "Lublin"
        assert medicine.radius_km == 10.0
        assert medicine.max_price == 20.0
        assert medicine.min_availability == AvailabilityLevel.HIGH
        assert medicine.title == "Placeholderium R 1000 search"
        assert medicine.full_name == "Placeholderium R 1000 | 400mg"
        assert medicine.active  # Default should be True

    def test_pharmacy_info_creation(self):
        """Test creating a PharmacyInfo object."""
        pharmacy = PharmacyInfo(
            name="Apteka Zielona Miła",
            address="ul. Parkowa 12, Białystok",
            phone="123-456-789",
            availability=AvailabilityLevel.HIGH,
            price_full=15.50,
            opening_hours="8:00-20:00",
            distance_km=2.5,
        )

        assert pharmacy.name == "Apteka Zielona Miła"
        assert pharmacy.address == "ul. Parkowa 12, Białystok"
        assert pharmacy.phone == "123-456-789"
        assert pharmacy.availability == AvailabilityLevel.HIGH
        assert pharmacy.price_full == 15.50
        assert pharmacy.opening_hours == "8:00-20:00"
        assert pharmacy.distance_km == 2.5

    def test_medicine_matching(self):
        """Test medicine matching against pharmacy info."""
        # Test with matching criteria
        medicine = Medicine(
            name="Placeholderium R 1000", max_price=20.0, min_availability=AvailabilityLevel.HIGH, radius_km=5.0
        )

        matching_pharmacy = PharmacyInfo(
            name="Apteka Pod Różą",
            address="ul. Kolejowa 8, Szczecin",
            phone=None,
            availability=AvailabilityLevel.HIGH,
            price_full=15.0,
            opening_hours=None,
            distance_km=3.0,
        )

        non_matching_price = PharmacyInfo(
            name="Apteka Droższa",
            address="ul. Morska 14, Szczecin",
            phone=None,
            availability=AvailabilityLevel.HIGH,
            price_full=25.0,
            opening_hours=None,
            distance_km=3.0,
        )

        non_matching_availability = PharmacyInfo(
            name="Apteka Ograniczona",
            address="ul. Leśna 33, Szczecin",
            phone=None,
            availability=AvailabilityLevel.NONE,
            price_full=15.0,
            opening_hours=None,
            distance_km=3.0,
        )

        non_matching_distance = PharmacyInfo(
            name="Apteka Daleka",
            address="ul. Zamkowa 45, Kraków",
            phone=None,
            availability=AvailabilityLevel.HIGH,
            price_full=15.0,
            opening_hours=None,
            distance_km=10.0,
        )

        assert medicine.matches_pharmacy(matching_pharmacy) is True
        assert medicine.matches_pharmacy(non_matching_price) is False
        assert medicine.matches_pharmacy(non_matching_availability) is False
        assert medicine.matches_pharmacy(non_matching_distance) is False

    def test_medicine_with_amount(self):
        """Test Medicine class with amount field."""
        medicine = Medicine(
            name="Placeholderium R 1000",
            dosage="50 mcg",
            amount="50 tabl.",
            location="Warszawa",
            radius_km=3.0,
        )

        assert medicine.name == "Placeholderium R 1000"
        assert medicine.dosage == "50 mcg"
        assert medicine.amount == "50 tabl."
        assert medicine.full_name == "Placeholderium R 1000 | 50 mcg | 50 tabl."

    def test_medicine_full_name_variations(self):
        """Test full_name property with different combinations."""
        # Name only
        medicine1 = Medicine(name="Placeholderium R 1000")
        assert medicine1.full_name == "Placeholderium R 1000"

        # Name + dosage
        medicine2 = Medicine(name="Placeholderium R 1000", dosage="50 mcg")
        assert medicine2.full_name == "Placeholderium R 1000 | 50 mcg"

        # Name + amount
        medicine3 = Medicine(name="Placeholderium R 1000", amount="50 tabl.")
        assert medicine3.full_name == "Placeholderium R 1000 | 50 tabl."

        # Name + dosage + amount
        medicine4 = Medicine(name="Placeholderium R 1000", dosage="50 mcg", amount="50 tabl.")
        assert medicine4.full_name == "Placeholderium R 1000 | 50 mcg | 50 tabl."

    def test_medicine_to_dict_with_amount(self):
        """Test Medicine.to_dict includes amount field."""
        medicine = Medicine(
            name="Placeholderium R 1000",
            dosage="50 mcg",
            amount="50 tabl.",
            location="Kraków",
            max_price=25.0,
        )

        data = medicine.to_dict()

        assert data["name"] == "Placeholderium R 1000"
        assert data["dosage"] == "50 mcg"
        assert data["amount"] == "50 tabl."
        assert data["location"] == "Kraków"
        assert data["max_price"] == 25.0

    def test_medicine_from_dict_with_amount(self):
        """Test Medicine.from_dict handles amount field."""
        data = {
            "name": "Placeholderium R 1000",
            "dosage": "50 mcg",
            "amount": "50 tabl.",
            "location": "Gdańsk",
            "radius_km": 2.5,
            "max_price": 30.0,
        }

        medicine = Medicine.from_dict(data)

        assert medicine.name == "Placeholderium R 1000"
        assert medicine.dosage == "50 mcg"
        assert medicine.amount == "50 tabl."
        assert medicine.location == "Gdańsk"
        assert medicine.radius_km == 2.5
        assert medicine.max_price == 30.0

    def test_medicine_active_field(self):
        """Test Medicine active field functionality."""
        # Test default active field
        medicine = Medicine(name="TestMed", location="TestCity")
        assert medicine.active

        # Test explicit active field
        inactive_medicine = Medicine(name="TestMed", location="TestCity", active=False)
        assert not inactive_medicine.active

        # Test serialization with active field
        medicine_dict = medicine.to_dict()
        assert "active" in medicine_dict
        assert medicine_dict["active"]

        inactive_dict = inactive_medicine.to_dict()
        assert not inactive_dict["active"]

        # Test deserialization with active field
        restored_medicine = Medicine.from_dict(medicine_dict)
        assert restored_medicine.active

        restored_inactive = Medicine.from_dict(inactive_dict)
        assert not restored_inactive.active

        # Test backward compatibility - dict without active field should default to True
        legacy_dict = {
            "name": "LegacyMed",
            "location": "LegacyCity",
            "radius_km": 5.0,
            "min_availability": AvailabilityLevel.LOW,
        }
        legacy_medicine = Medicine.from_dict(legacy_dict)
        assert legacy_medicine.active
