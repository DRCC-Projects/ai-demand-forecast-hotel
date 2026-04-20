"""
Generate CSV file with Indian national and Karnataka state holidays
for 2023-2026.
"""

import csv
from pathlib import Path
from datetime import date

# Output path
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = DATA_DIR / "india_holidays_2023_2026.csv"

# Years to generate
YEARS = [2023, 2024, 2025, 2026]

# Fixed date holidays (same date every year)
FIXED_HOLIDAYS = [
    # National holidays
    ("01-26", "Republic Day", "national"),
    ("08-15", "Independence Day", "national"),
    ("10-02", "Gandhi Jayanti", "national"),
    ("01-14", "Makar Sankranti", "national"),
    ("04-14", "Dr Ambedkar Jayanti", "national"),

    # Karnataka state holidays
    ("11-01", "Karnataka Rajyotsava", "karnataka"),
    ("11-15", "Kanakadasa Jayanti", "karnataka"),

    # Optional/Bank holidays
    ("12-25", "Christmas", "optional"),
    ("01-01", "New Year", "optional"),
    ("11-14", "Children's Day", "optional"),
    ("12-31", "New Year's Eve", "optional"),
]

# Variable date holidays (different date each year)
VARIABLE_HOLIDAYS = {
    2023: [
        ("03-08", "Holi", "national"),
        ("10-24", "Diwali", "national"),
        ("04-09", "Ugadi", "karnataka"),
    ],
    2024: [
        ("03-25", "Holi", "national"),
        ("11-01", "Diwali", "national"),
        ("03-29", "Ugadi", "karnataka"),
    ],
    2025: [
        ("03-14", "Holi", "national"),
        ("10-20", "Diwali", "national"),
        ("03-18", "Ugadi", "karnataka"),
    ],
    2026: [
        ("03-03", "Holi", "national"),
        ("11-08", "Diwali", "national"),
        ("04-06", "Ugadi", "karnataka"),
    ],
}


def generate_holidays():
    """Generate holiday data for all years"""
    holidays = []

    for year in YEARS:
        # Add fixed holidays
        for month_day, name, holiday_type in FIXED_HOLIDAYS:
            date_str = f"{year}-{month_day}"
            holidays.append({
                'date': date_str,
                'holiday_name': name,
                'type': holiday_type
            })

        # Add variable holidays
        if year in VARIABLE_HOLIDAYS:
            for month_day, name, holiday_type in VARIABLE_HOLIDAYS[year]:
                date_str = f"{year}-{month_day}"
                holidays.append({
                    'date': date_str,
                    'holiday_name': name,
                    'type': holiday_type
                })

    # Sort by date
    holidays.sort(key=lambda x: x['date'])

    return holidays


def save_to_csv(holidays):
    """Save holidays to CSV file"""
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'holiday_name', 'type'])
        writer.writeheader()
        writer.writerows(holidays)

    print(f"✓ Saved {len(holidays)} holidays to {OUTPUT_PATH}")


def print_summary(holidays):
    """Print summary of generated holidays"""
    print("\n" + "="*60)
    print("HOLIDAY GENERATION SUMMARY")
    print("="*60)
    print(f"Total holidays:    {len(holidays)}")
    print(f"Years covered:     {YEARS[0]}-{YEARS[-1]}")

    # Count by type
    national = sum(1 for h in holidays if h['type'] == 'national')
    karnataka = sum(1 for h in holidays if h['type'] == 'karnataka')
    optional = sum(1 for h in holidays if h['type'] == 'optional')

    print(f"National holidays: {national}")
    print(f"Karnataka holidays: {karnataka}")
    print(f"Optional holidays: {optional}")
    print("="*60)

    # Show first few holidays
    print("\nSample holidays (first 10):")
    for holiday in holidays[:10]:
        print(f"  {holiday['date']}: {holiday['holiday_name']} ({holiday['type']})")
    print("  ...")


if __name__ == '__main__':
    print("Generating India & Karnataka holidays for 2023-2026...")

    # Generate holidays
    holidays = generate_holidays()

    # Save to CSV
    save_to_csv(holidays)

    # Print summary
    print_summary(holidays)

    print("\n✓ Holiday generation complete!")
