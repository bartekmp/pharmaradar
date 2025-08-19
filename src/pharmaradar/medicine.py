"""
Medicine module for searching pharmacy availability.

This module provides the Medicine class for representing medicine search data
and pharmacy availability information.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pharmaradar.availability_level import AvailabilityLevel
from pharmaradar.pharmacy_info import PharmacyInfo


@dataclass
class Medicine:
    """Represents a medicine search configuration."""

    id: Optional[int] = None
    name: str = ""
    dosage: Optional[str] = None
    amount: Optional[str] = None  # Amount per package (e.g., "50 tabl.", "200 ml")
    location: str = ""  # Address or city
    radius_km: float = 5.0
    max_price: Optional[float] = None
    min_availability: AvailabilityLevel = AvailabilityLevel.LOW  # Minimum required availability
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    last_search_at: Optional[datetime] = None
    active: bool = True  # Whether this medicine search is active

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

        # Convert string min_availability to enum if needed (backwards compatibility)
        if isinstance(self.min_availability, str):
            self.min_availability = AvailabilityLevel.from_string(self.min_availability)

    @property
    def full_name(self) -> str:
        """Returns full medicine name with dosage and amount if available."""
        result = self.name
        if self.dosage:
            result += f" | {self.dosage}"
        if self.amount:
            result += f" | {self.amount}"
        return result

    def __str__(self) -> str:
        result = f"💊 {self.full_name}\n"
        result += f"📍 {self.location}\n"
        result += f"📏 Radius: {self.radius_km} km\n"

        if self.max_price is not None:
            result += f"💰 Max price: {self.max_price:.2f} zł\n"

        result += f"📊 Min availability: {self.min_availability.value}\n"

        return result.strip()

    def matches_pharmacy(self, pharmacy: PharmacyInfo) -> bool:
        """Check if pharmacy matches the medicine search criteria."""
        # Check price filter - use the lower of the two prices if both available
        if self.max_price is not None:
            price_to_check = None
            if pharmacy.price_refunded is not None:
                price_to_check = pharmacy.price_refunded
            elif pharmacy.price_full is not None:
                price_to_check = pharmacy.price_full

            if price_to_check is not None and price_to_check > self.max_price:
                return False

        # Check availability using the new system:
        # - If min_availability is NONE, accept any availability (including NONE)
        # - If min_availability is LOW or HIGH, require pharmacy to be available (not NONE)
        # - If min_availability is HIGH, require pharmacy to be HIGH availability

        if self.min_availability == AvailabilityLevel.NONE:
            # Accept any availability level
            pass
        elif self.min_availability == AvailabilityLevel.LOW:
            # Require pharmacy to be available (LOW or HIGH, but not NONE)
            if not pharmacy.availability.is_available:
                return False
        elif self.min_availability == AvailabilityLevel.HIGH:
            # Require pharmacy to have HIGH availability
            if pharmacy.availability != AvailabilityLevel.HIGH:
                return False

        # Check distance
        if pharmacy.distance_km is not None and pharmacy.distance_km > self.radius_km:
            return False

        return True

    def to_dict(self) -> dict:
        """Convert Medicine object to dictionary for database storage."""
        return {
            "id": self.id,
            "name": self.name,
            "dosage": self.dosage,
            "amount": self.amount,
            "location": self.location,
            "radius_km": self.radius_km,
            "max_price": self.max_price,
            "min_availability": (
                self.min_availability.value
                if isinstance(self.min_availability, AvailabilityLevel)
                else self.min_availability
            ),
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_search_at": self.last_search_at.isoformat() if self.last_search_at else None,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Medicine":
        """Create Medicine object from dictionary."""
        # Convert min_availability string to enum
        if "min_availability" in data and isinstance(data["min_availability"], str):
            data["min_availability"] = AvailabilityLevel.from_string(data["min_availability"])

        medicine = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

        if data.get("created_at"):
            medicine.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("last_search_at"):
            medicine.last_search_at = datetime.fromisoformat(data["last_search_at"])

        return medicine
