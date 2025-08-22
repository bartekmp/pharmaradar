"""
Medicine service for managing medicine searches and pharmacy lookups.
"""

import asyncio
import datetime
import logging
from typing import List, Optional

from pharmaradar.database.database_interface import MedicineDatabaseInterface
from pharmaradar.medicine import Medicine
from pharmaradar.medicine_scraper import MedicineFinder
from pharmaradar.pharmacy_info import PharmacyInfo


class MedicineWatchdog:
    """
    Service for managing medicine searches and pharmacy lookups.
    It comes in handy when there's a need to store search requests in the database
    and perform searches asynchronously. Use it for scheduled tasks like checking
    medicine availability in periodic intervals.
    """

    def __init__(self, database_interface: MedicineDatabaseInterface, log: logging.Logger = logging.getLogger()):
        self.db_client = database_interface
        self.scraper = MedicineFinder()
        self.log = log

    def _sort_pharmacies_by_availability(self, pharmacies: List[PharmacyInfo]) -> List[PharmacyInfo]:
        """
        Sort pharmacies by availability priority (HIGH -> LOW -> NONE).

        Args:
            pharmacies: List of pharmacies to sort

        Returns:
            Sorted list with high availability pharmacies first
        """

        def _get_availability_priority(pharmacy: PharmacyInfo) -> int:
            """Get numeric priority for availability level (higher number = higher priority)."""
            availability_str = pharmacy.availability.value
            priority_map = {"high": 3, "low": 2, "none": 1}
            return priority_map.get(availability_str, 0)

        return sorted(pharmacies, key=_get_availability_priority, reverse=True)

    def _select_best_pharmacies(self, pharmacies: List[PharmacyInfo], max_count: int = 5) -> List[PharmacyInfo]:
        """
        Select the best pharmacies prioritizing availability over proximity.

        Args:
            pharmacies: List of all available pharmacies
            max_count: Maximum number of pharmacies to return (default: 5)

        Returns:
            List of selected pharmacies, prioritizing high availability
        """
        if not pharmacies:
            return []

        # Separate pharmacies by availability level
        high_availability = [p for p in pharmacies if p.availability.value == "high"]
        low_availability = [p for p in pharmacies if p.availability.value == "low"]
        no_availability = [p for p in pharmacies if p.availability.value == "none"]

        # Take up to max_count high availability first, then fill with low/none if needed
        selected_pharmacies = []
        selected_pharmacies.extend(high_availability[:max_count])

        if len(selected_pharmacies) < max_count:
            remaining_slots = max_count - len(selected_pharmacies)
            selected_pharmacies.extend(low_availability[:remaining_slots])

        if len(selected_pharmacies) < max_count:
            remaining_slots = max_count - len(selected_pharmacies)
            selected_pharmacies.extend(no_availability[:remaining_slots])

        return selected_pharmacies

    def _log_pharmacy_selection(self, selected_pharmacies: List[PharmacyInfo], total_count: int) -> None:
        """Log the pharmacy selection results with availability breakdown."""
        high_count = len([p for p in selected_pharmacies if p.availability.value == "high"])
        low_count = len([p for p in selected_pharmacies if p.availability.value == "low"])
        none_count = len([p for p in selected_pharmacies if p.availability.value == "none"])

        self.log.info(
            f"Found {len(selected_pharmacies)} pharmacies out of {total_count} total - "
            f"High: {high_count}, Low: {low_count}, None: {none_count}"
        )

    async def search_medicine(self, medicine: Medicine) -> List[PharmacyInfo]:
        """
        Search for medicine availability and update last search time.

        Args:
            medicine: Medicine object to search for

        Returns:
            List of PharmacyInfo objects with found pharmacies
        """
        self.log.info(f"Starting medicine search for: {medicine.full_name}")

        try:
            # Perform the search asynchronously
            loop = asyncio.get_event_loop()
            pharmacies = await loop.run_in_executor(None, self.scraper.search_medicine, medicine)

            # Update last search time
            if medicine.id:
                self.db_client.update_medicine(medicine.id, last_search_at=datetime.datetime.now())

            # Filter results based on medicine criteria
            filtered_pharmacies = [pharmacy for pharmacy in pharmacies if medicine.matches_pharmacy(pharmacy)]

            # Sort and select the best pharmacies
            sorted_pharmacies = self._sort_pharmacies_by_availability(filtered_pharmacies)
            selected_pharmacies = self._select_best_pharmacies(sorted_pharmacies)
            self._log_pharmacy_selection(selected_pharmacies, len(pharmacies))

            return selected_pharmacies

        except RuntimeError as e:
            # Handle WebDriver initialization errors specifically
            error_msg = str(e)
            if "No WebDriver available" in error_msg:
                self.log.error("WebDriver initialization failed. Medicine scraping is not available.")
            else:
                self.log.error(f"Runtime error in medicine search: {error_msg}")
            return []
        except Exception as e:
            self.log.error(f"Unexpected error searching medicine: {str(e)}")
            return []

    def get_all_medicines(self) -> List[Medicine]:
        """
        Get all medicines from the database.

        Returns:
            List[Medicine]: List of all medicines
        """
        try:
            medicines_data: List[Medicine] = self.db_client.get_medicines()
            return medicines_data
        except Exception as e:
            self.log.error(f"Error getting all medicines: {e}")
            return []

    def get_medicine(self, medicine_id: int) -> Optional[Medicine]:
        """Get a specific medicine by ID."""
        try:
            medicine_data: Optional[Medicine] = self.db_client.get_medicine(medicine_id)
            return medicine_data
        except Exception as e:
            self.log.error(f"Error getting medicine {medicine_id}: {str(e)}")
            return None

    def add_medicine(self, medicine: Medicine) -> Optional[Medicine]:
        """Add a new medicine to the database."""
        try:
            # Ensure created_at is set
            if not medicine.created_at:
                medicine.created_at = datetime.datetime.now()

            # Save medicine and update ID
            medicine_id: int = self.db_client.save_medicine(medicine)
            if medicine_id:
                medicine.id = medicine_id
                return medicine
            else:
                self.log.error(f"Failed to save medicine {medicine.full_name}")
                return None
        except Exception as e:
            self.log.error(f"Error adding medicine {medicine.full_name}: {str(e)}")
            return None

    def update_medicine(self, medicine: Medicine) -> bool:
        """Update an existing medicine in the database."""
        try:
            if not medicine.id:
                self.log.error("Cannot update medicine without ID")
                return False

            # Extract individual fields for compatibility with DbClient
            success = self.db_client.update_medicine(
                medicine.id,
                name=medicine.name,
                dosage=medicine.dosage,
                amount=medicine.amount,
                location=medicine.location,
                radius_km=medicine.radius_km,
                max_price=medicine.max_price,
                min_availability=medicine.min_availability.value,
                title=medicine.title,
                last_search_at=medicine.last_search_at,
                active=medicine.active,
            )

            if success:
                self.log.info(f"Updated medicine {medicine.full_name} with ID {medicine.id}")
            else:
                self.log.warning(f"Failed to update medicine {medicine.full_name} with ID {medicine.id}")

            return bool(success)
        except Exception as e:
            self.log.error(f"Error updating medicine {medicine.full_name}: {str(e)}")
            return False

    def update_medicine_fields(self, medicine_id: int, **kwargs) -> bool:
        """Update specific fields of a medicine by ID.

        Args:
            medicine_id: ID of the medicine to update
            **kwargs: Fields to update (name, dosage, amount, location, radius_km,
                    max_price, min_availability, title, last_search_at, active)

        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            if not medicine_id:
                self.log.error("Cannot update medicine without ID")
                return False

            # Filter out None values and unsupported parameters
            valid_params = {}
            supported_fields = {
                "name",
                "dosage",
                "amount",
                "location",
                "radius_km",
                "max_price",
                "min_availability",
                "title",
                "last_search_at",
                "active",
            }

            for key, value in kwargs.items():
                if key in supported_fields and value is not None:
                    # Handle special case for min_availability if it's an AvailabilityLevel enum
                    if key == "min_availability" and hasattr(value, "value"):
                        valid_params[key] = value.value
                    else:
                        valid_params[key] = value

            if not valid_params:
                self.log.warning(f"No valid parameters provided for updating medicine {medicine_id}")
                return False

            # Call the db_client update_medicine with individual parameters
            success = self.db_client.update_medicine(medicine_id, **valid_params)

            if success:
                self.log.info(f"Updated medicine ID {medicine_id} with parameters: {valid_params}")
            else:
                self.log.warning(f"Failed to update medicine ID {medicine_id}")

            return bool(success)
        except Exception as e:
            self.log.error(f"Error updating medicine ID {medicine_id}: {str(e)}")
            return False

    def remove_medicine(self, medicine_id: Optional[int]) -> bool:
        """Remove a medicine from the database."""
        if medicine_id is None:
            return False

        medicine = self.db_client.get_medicine(medicine_id)
        if medicine:
            success = self.db_client.remove_medicine(medicine_id)
            if success:
                self.log.info(f"Removed medicine: {medicine.full_name}")
            return success
        return False

    async def search_all_medicines(self) -> dict[Medicine, List[PharmacyInfo]]:
        """
        Search for all medicines in the database asynchronously.

        Returns:
            Dictionary mapping Medicine objects to their pharmacy results
        """
        medicines = self.db_client.get_medicines()
        results = {}

        self.log.info(f"Searching for {len(medicines)} medicines asynchronously")

        # Create tasks for concurrent medicine searches
        tasks = []
        for medicine in medicines:
            task = self.search_medicine(medicine)
            tasks.append((medicine, task))

        # Wait for all searches to complete
        for medicine, task in tasks:
            try:
                pharmacies = await task
                if pharmacies:
                    results[medicine] = pharmacies
            except Exception as e:
                self.log.error(f"Error searching medicine {medicine.full_name}: {str(e)}")
                continue

        return results
