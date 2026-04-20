"""
Load historical hotel data from Excel/CSV into SQLite database.
Supports both .xlsx and .csv formats.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict

import pandas as pd

from src.db.local_db import upsert_daily_metrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_row(row: pd.Series, index: int) -> bool:
    """
    Validate a single row of hotel data.
    Returns True if valid, False otherwise.
    """
    try:
        # Check date
        if pd.isna(row['date']):
            logger.warning(f"Row {index}: Missing date")
            return False

        # Check occupancy_pct
        if pd.notna(row['occupancy_pct']):
            occ = float(row['occupancy_pct'])
            if occ < 0 or occ > 100:
                logger.warning(f"Row {index}: Invalid occupancy {occ}% (must be 0-100)")
                return False

        # Check adr_inr
        if pd.notna(row['adr_inr']):
            adr = float(row['adr_inr'])
            if adr < 0:
                logger.warning(f"Row {index}: Invalid ADR {adr} (must be positive)")
                return False

        # Check rooms_sold
        if pd.notna(row['rooms_sold']):
            rooms = int(row['rooms_sold'])
            if rooms < 0:
                logger.warning(f"Row {index}: Invalid rooms_sold {rooms} (must be positive)")
                return False

        return True

    except Exception as e:
        logger.warning(f"Row {index}: Validation error - {e}")
        return False


def load_historical_data(file_path: str):
    """
    Load historical hotel data from Excel or CSV file.

    Args:
        file_path: Path to the Excel (.xlsx) or CSV (.csv) file
    """
    file_path = Path(file_path)

    # Check if file exists
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info(f"Loading data from: {file_path}")

    # Read file based on extension
    try:
        if file_path.suffix.lower() == '.xlsx':
            df = pd.read_excel(file_path)
        elif file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}. Use .xlsx or .csv")

        logger.info(f"Read {len(df)} rows from file")

    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise

    # Validate required columns
    required_columns = ['date', 'occupancy_pct', 'adr_inr', 'rooms_sold']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Parse date column
    try:
        df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        logger.error(f"Failed to parse date column: {e}")
        raise

    # Validate each row
    total_rows = len(df)
    valid_mask = df.apply(lambda row: validate_row(row, row.name), axis=1)
    df_valid = df[valid_mask].copy()
    skipped_rows = total_rows - len(df_valid)

    if skipped_rows > 0:
        logger.warning(f"Skipped {skipped_rows} invalid rows")

    if len(df_valid) == 0:
        logger.error("No valid rows to load")
        raise ValueError("No valid rows found in file")

    # Get date range
    min_date = df_valid['date'].min()
    max_date = df_valid['date'].max()
    logger.info(f"Date range in data: {min_date.date()} to {max_date.date()}")

    # Fill missing dates in range with NaN
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')
    df_full = pd.DataFrame({'date': date_range})
    df_full = df_full.merge(df_valid, on='date', how='left')

    missing_dates = df_full['occupancy_pct'].isna().sum()
    if missing_dates > 0:
        logger.info(f"Filled {missing_dates} missing dates with NaN for visibility")

    # Convert to list of dicts for database insertion
    records = []
    for _, row in df_full.iterrows():
        record = {
            'date': row['date'].date(),  # Convert to Python date object
            'occupancy_pct': float(row['occupancy_pct']) if pd.notna(row['occupancy_pct']) else None,
            'adr_inr': float(row['adr_inr']) if pd.notna(row['adr_inr']) else None,
            'rooms_sold': int(row['rooms_sold']) if pd.notna(row['rooms_sold']) else None
        }
        records.append(record)

    # Upsert to database
    logger.info(f"Upserting {len(records)} records to database...")
    upsert_daily_metrics(records)

    # Print summary
    print("\n" + "=" * 60)
    print("LOAD SUMMARY")
    print("=" * 60)
    print(f"File:              {file_path}")
    print(f"Total rows read:   {total_rows}")
    print(f"Valid rows loaded: {len(df_valid)}")
    print(f"Skipped rows:      {skipped_rows}")
    print(f"Date range:        {min_date.date()} to {max_date.date()}")
    print(f"Total days:        {len(records)}")
    print(f"Missing dates:     {missing_dates}")
    print("=" * 60)

    print("\n✓ Historical data load complete")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Load historical hotel data from Excel/CSV into SQLite database'
    )
    parser.add_argument(
        '--file',
        type=str,
        default='data/historical_hotel_data.xlsx',
        help='Path to Excel (.xlsx) or CSV (.csv) file (default: data/historical_hotel_data.xlsx)'
    )

    args = parser.parse_args()

    try:
        load_historical_data(args.file)
    except Exception as e:
        logger.error(f"Failed to load historical data: {e}")
        print(f"\n✗ Historical data load failed: {e}")
        exit(1)
