# PharmaRadar

[![Unit Tests](https://github.com/bartekmp/pharmaradar/actions/workflows/test.yml/badge.svg)](https://github.com/bartekmp/pharmaradar/actions/workflows/test.yml)
[![CI/CD](https://github.com/bartekmp/pharmaradar/actions/workflows/ci.yml/badge.svg)](https://github.com/bartekmp/pharmaradar/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/pharmaradar.svg)](https://pypi.org/project/pharmaradar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Python package for searching and managing pharmacy medicine availability from [KtoMaLek.pl](https://ktomalek.pl).

## Requirements
Pharmaradar requires `chromium-browser`, `chromium-chromedriver` and `xvfb` to run, as the prerequisites for Selenium used to scrape the data from the KtoMaLek.pl page, as they do not provide an open API to get the data easily.

## Installation

```bash
pip install pharmaradar
```

## Usage

To work with searches use the `Medicine` object, which represents a search query including all required details about what you're looking for.
If you'd like to find nearest pharmacies, that have at least low availability of Euthyrox N 50 medicine, nearby the location like Złota street in Warsaw and the max radius of 10 kilometers, create it like this:
```python
import pharmaradar

medicine = pharmaradar.Medicine(
        name="Euthyrox N 50",
        dosage="50 mcg",
        location="Warszawa, Złota",
        radius_km=10.0,
        min_availability=AvailabilityLevel.LOW,
    )
```

Now create an instance of `MedicineFinder` class:
```python
finder = pharmaradar.MedicineFinder()
```

Then test if the connection to KtoMaLek.pl is possible and search for given medicine:
```python
if finder.test_connection():
    pharmacies = finder.search_medicine(medicine)
```

If the search was successful, the `pharmacies` will contain a list of `PharmacyInfo` objects, with all important data found on the page:
```python
for pharmacy in pharmacies:
    print(f"Pharmacy Name: {pharmacy.name}")
    print(f"Address: {pharmacy.address}")
    print(f"Availability: {pharmacy.availability}")
    if pharmacy.price_full:
        print(f"Price: {pharmacy.price_full} zł")
    if pharmacy.distance_km:
        print(f"Distance: {pharmacy.distance_km} km")
    if pharmacy.reservation_url:
        print(f"Reservation URL: {pharmacy.reservation_url}")
```

## Medicine watchdog

`MedicineWatchdog` is a class useful in async and continuous tasks. It implements certain methods, like `add_medicine`, `update_medicine`, `remove_medicine`, `get_medicine`, etc. that interact with the database layer, which is responsible for operating on the actual database. It can be used to create an automated bot, which periodically will retrieve the medicine quieries using `get_all_medicines` method, and then will perform searching and notifying.
```python
import sqlite3
from time import sleep

sql_db_client = SqliteInterface("my_database.db")
watchdog = pharmaradar.MedicineWatchdog(db_client)

while True:

    all_medicines: list[Medicine] = watchdog.get_all_medicines()
    for medicine in all_medicines:

        print(f"Medicine: {medicine.name}")

        found_pharmacies_for_medicine: list[PharmacyInfo] = await watchdog.search_medicine(medicine)

        if found_pharmacies_for_medicine:

            print(f"Found {len(found_pharmacies_for_medicine)}")

            for p in found_pharmacies_for_medicine:
                print(str(p))
        else:
            print(f"Medicine not available in pharmacies located in {medicine.distance_km} kilometer distance")

    sleep(60) # 1 minute
```

### Database interface
The database interface instance passed to `MedicineWatchdog` must implement `MedicineDatabaseInterface`, which is basically a CRUD interface. The watchdog object will use this interface to interact with the data in the table. Example for an implementation for `sqlite` database:

```python
from pharmaradar import Medicine, MedicineDatabaseInterface

class SqliteInterface(MedicineDatabaseInterface):
    def __init__(self, db_file_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cur = self.conn.cursor()

    def _parse_row_to_medicine(self, row: tuple) -> Medicine:
        """Convert a database row to a Medicine object."""
        medicine_data = {
            "id": row[0],
            "name": row[1],
            "dosage": row[2],
            "amount": row[3],
            "location": row[4],
            "radius_km": row[5],
            "max_price": row[6],
            "min_availability": row[7],
            "title": row[8],
            "created_at": datetime.datetime.fromisoformat(row[9]) if row[9] else None,
            "last_search_at": datetime.datetime.fromisoformat(row[10]) if row[10] else None,
            "active": row[11],  # Default to True for existing records
        }
        return Medicine(**medicine_data)

    def get_medicine(self, medicine_id: int) -> Medicine | None:
        row = self.cur.execute("SELECT * FROM medicine WHERE id = ?", (medicine_id,)).fetchone()
        if row is None:
            return None
        return self._parse_row_to_medicine(row)

    def get_medicines(self) -> list[Medicine]:
        rows = self.cur.execute("SELECT * FROM medicine").fetchall()
        medicines = []
        for medicine_row in res:
            medicines.append(self._parse_row_to_medicine(medicine_row))
        return medicines

    def remove_medicine(self, medicine_id: int) -> bool:
        with self.conn:
            res = self.cur.execute("DELETE FROM medicine WHERE id = (?)", (medicine_id,))
            return res.rowcount > 0

    def save_medicine(self, medicine: Medicine) -> int:
        with self.conn:
            self.cur.execute(
                    "INSERT INTO medicine VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        medicine.name,
                        medicine.dosage,
                        medicine.amount,
                        medicine.location,
                        medicine.radius_km,
                        medicine.max_price,
                        medicine.min_availability.value,
                        medicine.title,
                        medicine.created_at.isoformat() if medicine.created_at else None,
                        medicine.last_search_at.isoformat() if medicine.last_search_at else None,
                        medicine.active,
                    ),
                )
                return self.cur.lastrowid or 0

    def update_medicine(
        self,
        medicine_id: int,
        *,
        name: str | None = None,
        dosage: str | None = None,
        amount: str | None = None,
        location: str | None = None,
        radius_km: float | None = None,
        max_price: float | None = None,
        min_availability: str | None = None,
        title: str | None = None,
        last_search_at: datetime.datetime | None = None,
        active: bool | None = None,
    ) -> bool:
        sql = []
        values = []
        if name is not None:
            sql.append("name = ?")
            values.append(name)
        if dosage is not None:
            sql.append("dosage = ?")
            values.append(dosage)
        if amount is not None:
            sql.append("amount = ?")
            values.append(amount)
        if location is not None:
            sql.append("location = ?")
            values.append(location)
        if radius_km is not None:
            sql.append("radius_km = ?")
            values.append(radius_km)
        if max_price is not None:
            sql.append("max_price = ?")
            values.append(max_price)
        if min_availability is not None:
            sql.append("min_availability = ?")
            values.append(min_availability)
        if title is not None:
            sql.append("title = ?")
            values.append(title)
        if last_search_at is not None:
            sql.append("last_search_at = ?")
            values.append(last_search_at.isoformat())
        if active is not None:
            sql.append("active = ?")
            values.append(active)

        values.append(medicine_id)
        sql = f"UPDATE medicine SET {', '.join(sql)} WHERE id = ?"

        with self.conn:
            result = self.cur.execute(sql, values)
            return result.rowcount > 0 
    
```

Currently, the database itself must define the `medicine` table, declared as follows:
```sql
medicine(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            dosage TEXT,
            amount TEXT,
            location TEXT NOT NULL,
            radius_km REAL DEFAULT 10,
            max_price REAL,
            min_availability TEXT DEFAULT 'low',
            title TEXT,
            created_at TEXT,
            last_search_at TEXT,
            active BOOLEAN DEFAULT 1
        )
```

## License

MIT License