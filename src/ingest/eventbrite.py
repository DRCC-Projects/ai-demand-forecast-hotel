"""
Eventbrite API integration for event data.
Fetches events within 15km of hotel in Whitefield, Bengaluru.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import os
import json
from datetime import datetime, date
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
SEARCH_RADIUS = "15km"
API_BASE_URL = "https://www.eventbriteapi.com/v3/events/search/"


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


def determine_attendance_tier(event_data: Dict) -> str:
    """
    Determine attendance tier based on event attributes.
    Returns: "small", "medium", or "large"
    """
    try:
        # Check if it's a paid event with high capacity
        capacity = event_data.get('capacity', 0)
        if capacity and capacity > 2000:
            return "large"
        elif capacity and capacity > 500:
            return "medium"

        # Check category for conferences/festivals
        category = event_data.get('category', {})
        if category:
            category_name = category.get('name', '').lower()
            if any(term in category_name for term in ['conference', 'festival', 'expo', 'summit']):
                return "large"

        # Check if it's a popular event (has many attendees interested)
        # This is a proxy but Eventbrite doesn't expose ticket sales
        return "small"

    except Exception as e:
        logger.warning(f"Error determining attendance tier: {e}")
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
def fetch_eventbrite_page(api_key: str, page: int = 1) -> Dict:
    """
    Fetch a single page from Eventbrite API with retry logic.
    Raises requests.exceptions.RequestException on failure.
    """
    # Try alternate endpoint with location.address first
    url_with_token = f"https://www.eventbriteapi.com/v3/events/search/?location.address=Bengaluru&location.within=15km&token={api_key}"

    params = {
        'expand': 'venue',
        'status': 'live',
        'page_size': 50,
        'page': page
    }

    logger.info(f"Fetching Eventbrite events - page {page}")
    response = requests.get(url_with_token, params=params, timeout=30)
    logger.info(f"Eventbrite API response: {response.status_code}")

    response.raise_for_status()
    return response.json()


def parse_event(event_data: Dict) -> Optional[Dict]:
    """
    Parse a single Eventbrite event into our schema.
    Returns None if event cannot be parsed (missing critical fields).
    """
    try:
        # Extract basic info
        name_obj = event_data.get('name', {})
        name = name_obj.get('text') if isinstance(name_obj, dict) else event_data.get('name')

        if not name:
            logger.warning("Event missing name, skipping")
            return None

        # Extract dates
        start_obj = event_data.get('start', {})
        start_local = start_obj.get('local') if isinstance(start_obj, dict) else None
        if not start_local:
            logger.warning(f"Event '{name}' missing start date, skipping")
            return None

        # Parse ISO datetime string to date
        start_date = datetime.fromisoformat(start_local.replace('Z', '+00:00')).date()

        # End date
        end_obj = event_data.get('end', {})
        end_local = end_obj.get('local') if isinstance(end_obj, dict) else None
        if end_local:
            end_date = datetime.fromisoformat(end_local.replace('Z', '+00:00')).date()
        else:
            end_date = start_date

        # Extract venue info
        venue_data = event_data.get('venue', {})
        venue_name = None
        venue_lat = None
        venue_lon = None

        if venue_data:
            venue_name = venue_data.get('name')
            lat_val = venue_data.get('latitude')
            lon_val = venue_data.get('longitude')

            if lat_val and lon_val:
                try:
                    venue_lat = float(lat_val)
                    venue_lon = float(lon_val)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid coordinates for event '{name}'")

        # If no valid coordinates, skip event
        if venue_lat is None or venue_lon is None:
            logger.warning(f"Event '{name}' missing venue coordinates, skipping")
            return None

        # Calculate distance
        distance_km = calculate_distance_km(venue_lat, venue_lon)

        # Determine attendance tier
        attendance_tier = determine_attendance_tier(event_data)

        # Calculate impact score
        impact_score = calculate_impact_score(attendance_tier, distance_km, start_date, end_date)

        # Extract source URL
        source_url = event_data.get('url')

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
            'source': 'eventbrite',
            'source_url': source_url
        }

    except Exception as e:
        logger.error(f"Error parsing event: {e}")
        return None


def fetch_eventbrite_events() -> List[Dict]:
    """
    Fetch all events from Eventbrite API with pagination.
    Returns list of parsed event dictionaries.
    Returns empty list if API key is missing or on error.
    """
    api_key = os.getenv('EVENTBRITE_API_KEY')
    if not api_key:
        logger.warning("EVENTBRITE_API_KEY not found in environment, returning empty list")
        return []

    all_events = []
    page = 1

    try:
        while True:
            # Fetch page
            response_data = fetch_eventbrite_page(api_key, page=page)

            # Extract events
            events = response_data.get('events', [])

            for event_data in events:
                parsed_event = parse_event(event_data)
                if parsed_event:
                    all_events.append(parsed_event)

            # Check pagination
            pagination = response_data.get('pagination', {})
            has_more = pagination.get('has_more_items', False)

            if not has_more:
                break

            page += 1

        logger.info(f"Total events fetched and parsed: {len(all_events)}")
        return all_events

    except Exception as e:
        logger.error(f"Failed to fetch Eventbrite events: {e}")
        logger.warning("Returning empty list due to error")
        return []


if __name__ == '__main__':
    print("Fetching events from Eventbrite API...")

    try:
        # Fetch events
        events = fetch_eventbrite_events()

        print(f"\nTotal events fetched: {len(events)}")

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
            print("\n⚠ No events found (check API key or network)")

        print("\n✓ Eventbrite ingest complete")

    except Exception as e:
        print(f"\n✗ Eventbrite ingest failed: {e}")
        print("Continuing with empty Eventbrite results")
