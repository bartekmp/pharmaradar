from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

from pharmaradar.availability_level import AvailabilityLevel


@dataclass
class PharmacyInfo:
    """Represents information about a pharmacy and medicine availability."""

    name: str
    address: str
    phone: Optional[str]
    availability: AvailabilityLevel
    opening_hours: Optional[str]
    distance_km: Optional[float]
    price_full: Optional[float] = None  # 100% payment price
    price_refunded: Optional[float] = None  # Refunded price (if available)
    reservation_url: Optional[str] = None
    additional_info: Optional[str] = None  # Prescription info, refund status, other details

    def __post_init__(self):
        """Convert string availability to enum if needed."""
        if isinstance(self.availability, str):
            self.availability = AvailabilityLevel.from_string(self.availability)

    def __str__(self) -> str:
        availability_emoji = {AvailabilityLevel.HIGH: "🟢", AvailabilityLevel.LOW: "⚠️", AvailabilityLevel.NONE: "❌"}

        result = f"{availability_emoji.get(self.availability, '❓')} {self.name}\n"

        if self.address:
            # Create a clickable Google Maps link for the address
            encoded_address = quote_plus(self.address)
            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
            result += f'📍 <a href="{google_maps_url}">{self.address}</a>\n'
        else:
            result += "📍 Address not available\n"

        if self.phone:
            result += f"📞 {self.phone}\n"

        if self.price_full is not None:
            result += f"💰 Full price: {self.price_full:.2f} zł\n"

        if self.price_refunded is not None:
            result += f"💊 Refunded price: {self.price_refunded:.2f} zł\n"

        if self.opening_hours:
            result += f"🕒 {self.opening_hours}\n"

        if self.distance_km is not None:
            result += f"🚗 {self.distance_km:.1f} km\n"

        if self.reservation_url:
            result += f'🔗 <a href="https://ktomalek.pl{self.reservation_url}">Zarezerwuj</a>\n'

        if self.additional_info:
            result += f"ℹ️ {self.additional_info}\n"

        return result.strip()
