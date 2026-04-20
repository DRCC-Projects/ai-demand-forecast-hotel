"""
Generate realistic synthetic hotel occupancy data for training.
Creates 3 years of daily data (2023-01-01 to 2025-12-31) for a
4-star business hotel in Whitefield, Bengaluru.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path

# Set random seed for reproducibility
np.random.seed(42)

# Hotel configuration
BASE_OCCUPANCY = 65.0  # Base occupancy percentage
BASE_ADR = 6500.0      # Base Average Daily Rate in INR
TOTAL_ROOMS = 180      # Total rooms in hotel

# Date range
START_DATE = date(2023, 1, 1)
END_DATE = date(2025, 12, 31)

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
XLSX_PATH = DATA_DIR / "historical_hotel_data.xlsx"
CSV_PATH = DATA_DIR / "historical_hotel_data.csv"

# Indian holidays (approximate dates)
HOLIDAYS = {
    # 2023
    date(2023, 1, 26): "Republic Day",
    date(2023, 3, 8): "Holi",
    date(2023, 8, 15): "Independence Day",
    date(2023, 10, 24): "Diwali",
    date(2023, 12, 25): "Christmas",
    # 2024
    date(2024, 1, 26): "Republic Day",
    date(2024, 3, 25): "Holi",
    date(2024, 8, 15): "Independence Day",
    date(2024, 11, 1): "Diwali",
    date(2024, 12, 25): "Christmas",
    # 2025
    date(2025, 1, 26): "Republic Day",
    date(2025, 3, 14): "Holi",
    date(2025, 8, 15): "Independence Day",
    date(2025, 10, 20): "Diwali",
    date(2025, 12, 25): "Christmas",
}


def is_peak_season(date_obj: date) -> bool:
    """Check if date is in peak season (Oct-Feb)"""
    month = date_obj.month
    return month >= 10 or month <= 2


def is_slow_season(date_obj: date) -> bool:
    """Check if date is in slow season (Apr-Jun)"""
    month = date_obj.month
    return 4 <= month <= 6


def is_holiday_week(date_obj: date) -> bool:
    """Check if date is within 3 days of Diwali or Christmas"""
    for holiday_date in HOLIDAYS:
        if abs((date_obj - holiday_date).days) <= 3:
            if "Diwali" in HOLIDAYS[holiday_date] or "Christmas" in HOLIDAYS[holiday_date]:
                return True
    return False


def is_weekend(date_obj: date) -> bool:
    """Check if date is Friday or Saturday"""
    return date_obj.weekday() in [4, 5]  # 4=Friday, 5=Saturday


def is_corporate_weekday(date_obj: date) -> bool:
    """Check if date is Mon-Thu"""
    return date_obj.weekday() in [0, 1, 2, 3]  # Mon-Thu


def calculate_occupancy(date_obj: date) -> float:
    """Calculate occupancy percentage based on date characteristics"""
    occ = BASE_OCCUPANCY

    # Weekend boost
    if is_weekend(date_obj):
        occ += 10.0

    # Peak season boost
    if is_peak_season(date_obj):
        occ += 15.0

    # Slow season penalty
    if is_slow_season(date_obj):
        occ -= 15.0

    # Holiday week dip
    if is_holiday_week(date_obj):
        occ -= 10.0

    # Corporate weekday boost
    if is_corporate_weekday(date_obj):
        occ += 8.0

    # Add realistic noise (-5% to +5%)
    noise = np.random.uniform(-5, 5)
    occ += noise

    # Clip to realistic range
    occ = np.clip(occ, 20.0, 98.0)

    return round(occ, 2)


def calculate_adr(occupancy: float, date_obj: date) -> float:
    """Calculate ADR based on occupancy and season"""
    adr = BASE_ADR

    # ADR rises with occupancy (elasticity)
    # Every 10% occupancy above 65% increases ADR by 5%
    occupancy_premium = (occupancy - BASE_OCCUPANCY) / 10.0 * 0.05
    adr *= (1 + occupancy_premium)

    # Peak season ADR boost
    if is_peak_season(date_obj):
        adr *= 1.20

    # Add small noise (-3% to +3%)
    noise = np.random.uniform(-0.03, 0.03)
    adr *= (1 + noise)

    # Round to nearest 50 INR (realistic pricing)
    adr = round(adr / 50) * 50

    return adr


def generate_hotel_data():
    """Generate synthetic hotel data"""
    print("Generating synthetic hotel data...")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Base occupancy: {BASE_OCCUPANCY}%")
    print(f"Base ADR: ₹{BASE_ADR}")
    print(f"Total rooms: {TOTAL_ROOMS}")
    print()

    # Generate date range
    current_date = START_DATE
    data = []

    while current_date <= END_DATE:
        # Calculate occupancy
        occupancy_pct = calculate_occupancy(current_date)

        # Calculate ADR
        adr_inr = calculate_adr(occupancy_pct, current_date)

        # Calculate rooms sold
        rooms_sold = round(occupancy_pct / 100.0 * TOTAL_ROOMS)

        data.append({
            'date': current_date,
            'occupancy_pct': occupancy_pct,
            'adr_inr': adr_inr,
            'rooms_sold': rooms_sold
        })

        current_date += timedelta(days=1)

    # Create DataFrame
    df = pd.DataFrame(data)

    # Save to Excel
    df.to_excel(XLSX_PATH, index=False, sheet_name='Hotel Data')
    print(f"✓ Saved to {XLSX_PATH}")

    # Save to CSV (backup)
    df.to_csv(CSV_PATH, index=False)
    print(f"✓ Saved to {CSV_PATH}")

    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(f"Date range:        {df['date'].min()} to {df['date'].max()}")
    print(f"Total days:        {len(df)}")
    print(f"Average occupancy: {df['occupancy_pct'].mean():.2f}%")
    print(f"Min occupancy:     {df['occupancy_pct'].min():.2f}%")
    print(f"Max occupancy:     {df['occupancy_pct'].max():.2f}%")
    print(f"Average ADR:       ₹{df['adr_inr'].mean():.2f}")
    print(f"Min ADR:           ₹{df['adr_inr'].min():.2f}")
    print(f"Max ADR:           ₹{df['adr_inr'].max():.2f}")
    print(f"Average rooms sold: {df['rooms_sold'].mean():.1f}")
    print("="*60)

    # Show sample rows
    print("\nSample data (first 5 rows):")
    print(df.head().to_string(index=False))

    print("\n✓ Data generation complete!")

    return df


if __name__ == '__main__':
    generate_hotel_data()
