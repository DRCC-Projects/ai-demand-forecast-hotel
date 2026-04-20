"""
Manual event loader from CSV file.
Loads events from data/manual_events.csv for events not covered by APIs.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import json
import csv
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict

from haversine import haversine, Unit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
HOTEL_LAT = 12.9915
HOTEL_LON = 77.7260
CSV_PATH = Path(__file__).parent.parent.parent / "data" / "manual_events.csv"


def calculate_distance_km(event_lat: float, event_lon: float) -> float:
    """Calculate haversine distance from hotel to event venue"""
    hotel_coords = (HOTEL_LAT, HOTEL_LON)
    event_coords = (event_lat, event_lon)
    return haversine(hotel_coords, event_coords, unit=Unit.KILOMETERS)


def calculate_proximity_weight(distance_km: float) -> float:
    """Calculate proximity weight based on distance"""
    if distance_km < 2:
        return 1.0
    elif distance_km < 5:
        return 0.7
    elif distance_km < 10:
        return 0.4
    else:
        return 0.1


def calculate_duration_weight(start_date: date, end_date: date) -> float:
    """Calculate duration weight based on event length"""
    duration_days = (end_date - start_date).days + 1
    if duration_days == 1:
        return 0.8
    elif duration_days <= 3:
        return 1.0
    else:
        return 1.2


def calculate_impact_score(attendance_tier: str, distance_km: float,
                          start_date: date, end_date: date) -> float:
    """Calculate event impact score"""
    attendance_weights = {
        "small": 0.2,
        "medium": 0.5,
        "large": 1.0
    }
    attendance_weight = attendance_weights.get(attendance_tier, 0.2)
    proximity_weight = calculate_proximity_weight(distance_km)
    duration_weight = calculate_duration_weight(start_date, end_date)
    return round(attendance_weight * proximity_weight * duration_weight, 2)


def load_manual_events() -> List[Dict]:
    """
    Load events from CSV file.
    Returns list of parsed event dictionaries.
    Returns empty list if file doesn't exist or on error.
    """
    if not CSV_PATH.exists():
        logger.warning(f"CSV file not found: {CSV_PATH}")
        return []

    events = []

    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Extract and validate required fields
                    name = row.get('name', '').strip()
                    if not name:
                        logger.warning("Row missing name, skipping")
                        continue

                    # Parse dates
                    start_date_str = row.get('start_date', '').strip()
                    end_date_str = row.get('end_date', '').strip()

                    if not start_date_str:
                        logger.warning(f"Event '{name}' missing start_date, skipping")
                        continue

                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date

                    # Extract venue and coordinates
                    venue = row.get('venue', '').strip()
                    lat = float(row.get('lat', 0))
                    lon = float(row.get('lon', 0))

                    if lat == 0 or lon == 0:
                        logger.warning(f"Event '{name}' has invalid coordinates, skipping")
                        continue

                    # Extract attendance tier
                    attendance_tier = row.get('attendance_tier', 'small').strip().lower()
                    if attendance_tier not in ['small', 'medium', 'large']:
                        logger.warning(f"Invalid attendance_tier '{attendance_tier}' for '{name}', defaulting to 'small'")
                        attendance_tier = 'small'

                    # Calculate distance
                    distance_km = calculate_distance_km(lat, lon)

                    # Calculate impact score
                    impact_score = calculate_impact_score(attendance_tier, distance_km, start_date, end_date)

                    event_dict = {
                        'name': name,
                        'start_date': start_date,
                        'end_date': end_date,
                        'venue': venue if venue else None,
                        'lat': lat,
                        'lon': lon,
                        'distance_km': round(distance_km, 2),
                        'attendance_tier': attendance_tier,
                        'impact_score': impact_score,
                        'source': 'manual',
                        'source_url': ''
                    }

                    events.append(event_dict)
                    logger.debug(f"Loaded event: {name}")

                except Exception as e:
                    logger.error(f"Error parsing CSV row: {e}")
                    continue

        logger.info(f"Successfully loaded {len(events)} manual events from CSV")
        return events

    except Exception as e:
        logger.error(f"Failed to load manual events: {e}")
        return []


if __name__ == '__main__':
    print("Loading manual events from CSV...")

    try:
        # Load events
        events = load_manual_events()

        print(f"\nTotal events loaded: {len(events)}")

        # Print first 2 events
        if events:
            print("\nFirst 2 events:")
            for event in events[:2]:
                # Convert date objects to strings for JSON serialization
                event_copy = event.copy()
                event_copy['start_date'] = event['start_date'].isoformat()
                event_copy['end_date'] = event['end_date'].isoformat()
                print(json.dumps(event_copy, indent=2))

            # Insert into database
            from src.db.local_db import insert_events
            insert_events(events)
            print(f"\n✓ Inserted {len(events)} events into database")
        else:
            print("\n⚠ No events found in CSV")

        print("\n✓ Manual events ingest complete")

    except Exception as e:
        print(f"\n✗ Manual events ingest failed: {e}")
        print("Continuing with empty manual events")
