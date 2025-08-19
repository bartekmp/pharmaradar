from enum import Enum


class AvailabilityLevel(Enum):
    """Enum for medicine availability levels."""

    NONE = "none"  # Medicine not available
    LOW = "low"  # Low availability
    HIGH = "high"  # High availability

    @property
    def is_available(self) -> bool:
        """Returns True if this level means medicine is available (not NONE)."""
        return self != AvailabilityLevel.NONE

    @classmethod
    def from_string(cls, value: str) -> "AvailabilityLevel":
        """Convert string to AvailabilityLevel."""
        # Handle new enum values
        for level in cls:
            if level.value == value:
                return level

        # Default for unknown values
        return cls.NONE
