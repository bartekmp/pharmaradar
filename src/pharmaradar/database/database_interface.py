"""
Database interface for medicine management operations.
"""

import datetime
from abc import ABC, abstractmethod
from typing import List, Optional

from pharmaradar.medicine import Medicine


class MedicineDatabaseInterface(ABC):
    """Abstract interface for database operations used by MedicineWatchdog."""

    @abstractmethod
    def get_medicines(self) -> List[Medicine]:
        """
        Get all medicines from the database.

        Returns:
            List[Medicine]: List of all medicines
        """
        pass

    @abstractmethod
    def get_medicine(self, medicine_id: int) -> Optional[Medicine]:
        """
        Get a specific medicine by ID.

        Args:
            medicine_id: The ID of the medicine to retrieve

        Returns:
            Optional[Medicine]: The medicine if found, None otherwise
        """
        pass

    @abstractmethod
    def save_medicine(self, medicine: Medicine) -> int:
        """
        Save a new medicine to the database.

        Args:
            medicine: The medicine object to save

        Returns:
            int: The ID of the saved medicine
        """
        pass

    @abstractmethod
    def update_medicine(
        self,
        medicine_id: int,
        *,
        name: Optional[str] = None,
        dosage: Optional[str] = None,
        amount: Optional[str] = None,
        location: Optional[str] = None,
        radius_km: Optional[float] = None,
        max_price: Optional[float] = None,
        min_availability: Optional[str] = None,
        title: Optional[str] = None,
        last_search_at: Optional[datetime.datetime] = None,
        active: Optional[bool] = None,
    ) -> bool:
        """
        Update an existing medicine in the database.

        Args:
            medicine_id: The ID of the medicine to update
            name: Medicine name (optional)
            dosage: Medicine dosage (optional)
            amount: Medicine amount (optional)
            location: Search location (optional)
            radius_km: Search radius in kilometers (optional)
            max_price: Maximum price filter (optional)
            min_availability: Minimum availability level (optional)
            title: Medicine title (optional)
            last_search_at: Last search timestamp (optional)
            active: Whether the medicine is active (optional)

        Returns:
            bool: True if update was successful, False otherwise
        """
        pass

    @abstractmethod
    def remove_medicine(self, medicine_id: int) -> bool:
        """
        Remove a medicine from the database.

        Args:
            medicine_id: The ID of the medicine to remove

        Returns:
            bool: True if removal was successful, False otherwise
        """
        pass
