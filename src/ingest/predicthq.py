"""
PredictHQ API integration for event data.
Fetches events within 15km of hotel in Whitefield, Bengaluru.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv
from haversine import haversine, Unit
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
HOTEL_LAT = 12.9915
HOTEL_LON = 77.7260
API_BASE_URL = "https://api.predicthq.com/v1/events/"
MAX_PAGES = 5


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


def determine_attendance_tier(phq_rank: int) -> str:
    """Determine attendance tier based on PredictHQ rank"""
    if phq_rank >= 70:
        return "large"
    elif phq_rank >= 40:
        return "medium"
    else:
        return "small"


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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def fetch_predicthq_page(api_key: str, url: str = None, params: dict = None) -> Dict:
    """
    Fetch a page from PredictHQ API with retry logic.
    Raises requests.exceptions.RequestException on failure.
    """
    if url is None:
        url = API_BASE_URL

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }

    logger.info(f"Fetching PredictHQ events from: {url}")
    response = requests.get(url, headers=headers, params=params, timeout=30)
    logger.info(f"PredictHQ API response: {response.status_code}")

    response.raise_for_status()
    return response.json()


def parse_event(event_data: Dict) -> Optional[Dict]:
    """
    Parse a single PredictHQ event into our schema.
    Returns None if event cannot be parsed (missing critical fields).
    """
    try:
        # Extract basic info
        name = event_data.get('title')
        if not name:
            logger.warning("Event missing title, skipping")
            return None

        # Extract dates
        start_str = event_data.get('start')
        if not start_str:
            logger.warning(f"Event '{name}' missing start date, skipping")
            return None

        start_date = datetime.fromisoformat(start_str[:10]).date()

        # End date
        end_str = event_data.get('end')
        if end_str:
            end_date = datetime.fromisoformat(end_str[:10]).date()
        else:
            end_date = start_date

        # Extract venue info
        venue_name = "Bengaluru"
        entities = event_data.get('entities', [])
        if entities and len(entities) > 0:
            venue_name = entities[0].get('name', 'Bengaluru')

        # Extract location (PredictHQ format is [lon, lat])
        location = event_data.get('location')
        if location and len(location) == 2:
            venue_lon = float(location[0])
            venue_lat = float(location[1])
        else:
            # Default to Bengaluru center if no location
            venue_lat = 12.9716
            venue_lon = 77.5946

        # Calculate distance
        distance_km = calculate_distance_km(venue_lat, venue_lon)

        # Get PredictHQ rank
        phq_rank = event_data.get('rank', 0)

        # Determine attendance tier
        attendance_tier = determine_attendance_tier(phq_rank)

        # Calculate impact score
        impact_score = calculate_impact_score(attendance_tier, distance_km, start_date, end_date)

        # Extract source URL
        source_url = event_data.get('url', '')

        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue_name,
            'lat': venue_lat,
            'lon': venue_lon,
            'distance_km': round(distance_km, 2),
            'attendance_tier': attendance_tier,
            'impact_score': impact_score,
            'source': 'predicthq',
            'source_url': source_url,
            'phq_rank': phq_rank
        }

    except Exception as e:
        logger.error(f"Error parsing event: {e}")
        return None


def fetch_predicthq_events() -> List[Dict]:
    """
    Fetch all events from PredictHQ API with pagination.
    Returns list of parsed event dictionaries.
    Returns empty list if API key is missing or on error.
    """
    api_key = os.getenv('PREDICTHQ_API_KEY')
    if not api_key:
        logger.warning("PREDICTHQ_API_KEY not found in environment, returning empty list")
        return []

    all_events = []
    page_count = 0

    try:
        # Set up initial parameters
        today = date.today()
        ninety_days = today + timedelta(days=90)

        params = {
            'within': f'15km@{HOTEL_LAT},{HOTEL_LON}',
            'active.gte': today.isoformat(),
            'active.lte': ninety_days.isoformat(),
            'category': 'conferences,expos,concerts,festivals,performing-arts,community,sports',
            'limit': 100,
            'sort': 'rank'
        }

        next_url = None

        while page_count < MAX_PAGES:
            # Fetch page
            if next_url:
                response_data = fetch_predicthq_page(api_key, url=next_url)
            else:
                response_data = fetch_predicthq_page(api_key, params=params)

            page_count += 1

            # Extract events
            results = response_data.get('results', [])
            logger.info(f"Page {page_count}: {len(results)} events")

            for event_data in results:
                parsed_event = parse_event(event_data)
                if parsed_event:
                    all_events.append(parsed_event)

            # Check for next page
            next_url = response_data.get('next')
            if not next_url:
                break

        logger.info(f"Total events fetched and parsed: {len(all_events)}")
        return all_events

    except Exception as e:
        logger.error(f"Failed to fetch PredictHQ events: {e}")
        logger.warning("Returning empty list due to error")
        return []


if __name__ == '__main__':
    print("Fetching events from PredictHQ API...")

    try:
        # Fetch events
        events = fetch_predicthq_events()

        print(f"\nTotal events fetched: {len(events)}")

        # Print first 3 events
        if events:
            print("\nFirst 3 events:")
            import json
            print(json.dumps(events[:3], indent=2, default=str))

            # Insert into database
            from src.db.local_db import insert_events
            insert_events(events)
            print(f"\n✓ Inserted {len(events)} events into database")
        else:
            print("\n⚠ No events found (check API key or network)")

        print("\n✓ PredictHQ ingest complete")

    except Exception as e:
        print(f"\n✗ PredictHQ ingest failed: {e}")
        print("Continuing with empty PredictHQ results")
