# PharmaRadar

[![Unit Tests](https://github.com/bartekmp/pharmaradar/actions/workflows/test.yml/badge.svg)](https://github.com/bartekmp/pharmaradar/actions/workflows/test.yml)
[![CI/CD](https://github.com/bartekmp/pharmaradar/actions/workflows/ci.yml/badge.svg)](https://github.com/bartekmp/pharmaradar/actions/workflows/ci.yml)

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

## License

MIT License