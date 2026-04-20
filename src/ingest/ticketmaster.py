"""
Ticketmaster Discovery API integration for event data.
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
SEARCH_RADIUS = 15  # km
COUNTRY_CODE = "IN"
API_BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


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
    Determine attendance tier based on price ranges and classifications.
    Returns: "small", "medium", or "large"
    """
    try:
        # Check price ranges
        price_ranges = event_data.get('priceRanges', [])
        if price_ranges:
            max_price = max([pr.get('max', 0) for pr in price_ranges if pr.get('max')])
            if max_price > 5000:
                return "large"
            elif max_price >= 1000:
                return "medium"

        # Check classifications for festivals/conferences
        classifications = event_data.get('classifications', [])
        for classification in classifications:
            genre = classification.get('genre', {})
            genre_name = genre.get('name', '').lower() if genre else ''
            if 'festival' in genre_name or 'conference' in genre_name:
                return "large"

            segment = classification.get('segment', {})
            segment_name = segment.get('name', '').lower() if segment else ''
            if 'festival' in segment_name or 'conference' in segment_name:
                return "large"

        return "small"
    except Exception as e:
        logger.warning(f"Error determining attendance tier: {e}")
        return "small"


def calculate_impact_score(attendance_tier: str, distance_km: float,
                          start_date: date, end_date: date) -> float:
    """Calculate event impact score"""
    # Attendance weight
    attendance_weights = {
        "small": 0.2,
        "medium": 0.5,
        "large": 1.0
    }
    attendance_weight = attendance_weights.get(attendance_tier, 0.2)

    # Proximity weight
    proximity_weight = calculate_proximity_weight(distance_km)

    # Duration weight
    duration_weight = calculate_duration_weight(start_date, end_date)

    return round(attendance_weight * proximity_weight * duration_weight, 2)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def fetch_ticketmaster_page(api_key: str, page: int = 0) -> Dict:
    """
    Fetch a single page from Ticketmaster API with retry logic.
    Raises requests.exceptions.RequestException on failure.
    """
    params = {
        'apikey': api_key,
        'latlong': f'{HOTEL_LAT},{HOTEL_LON}',
        'radius': SEARCH_RADIUS,
        'unit': 'km',
        'countryCode': COUNTRY_CODE,
        'size': 200,
        'page': page
    }

    logger.info(f"Fetching Ticketmaster events - page {page}")
    response = requests.get(API_BASE_URL, params=params, timeout=30)
    logger.info(f"Ticketmaster API response: {response.status_code} - URL: {response.url}")

    response.raise_for_status()
    return response.json()


def parse_event(event_data: Dict) -> Optional[Dict]:
    """
    Parse a single Ticketmaster event into our schema.
    Returns None if event cannot be parsed (missing critical fields).
    """
    try:
        # Extract basic info
        name = event_data.get('name')
        if not name:
            logger.warning("Event missing name, skipping")
            return None

        # Extract dates
        dates = event_data.get('dates', {})
        start_info = dates.get('start', {})
        start_date_str = start_info.get('localDate')
        if not start_date_str:
            logger.warning(f"Event '{name}' missing start date, skipping")
            return None

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

        # End date
        end_info = dates.get('end', {})
        end_date_str = end_info.get('localDate')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date

        # Extract venue info
        embedded = event_data.get('_embedded', {})
        venues = embedded.get('venues', [])
        venue_name = None
        venue_lat = None
        venue_lon = None

        if venues and len(venues) > 0:
            venue = venues[0]
            venue_name = venue.get('name')
            location = venue.get('location', {})
            lat_str = location.get('latitude')
            lon_str = location.get('longitude')

            if lat_str and lon_str:
                try:
                    venue_lat = float(lat_str)
                    venue_lon = float(lon_str)
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
            'source': 'ticketmaster',
            'source_url': source_url
        }

    except Exception as e:
        logger.error(f"Error parsing event: {e}")
        return None


def fetch_ticketmaster_events() -> List[Dict]:
    """
    Fetch all events from Ticketmaster API with pagination.
    Returns list of parsed event dictionaries.
    """
    api_key = os.getenv('TICKETMASTER_API_KEY')
    if not api_key:
        logger.error("TICKETMASTER_API_KEY not found in environment")
        raise ValueError("TICKETMASTER_API_KEY not set")

    all_events = []
    page = 0

    try:
        # Fetch first page
        response_data = fetch_ticketmaster_page(api_key, page=0)

        # Extract page info
        page_info = response_data.get('page', {})
        total_pages = page_info.get('totalPages', 1)

        logger.info(f"Total pages to fetch: {total_pages}")

        # Process all pages
        for page in range(total_pages):
            if page > 0:  # Already fetched page 0
                response_data = fetch_ticketmaster_page(api_key, page=page)

            # Parse events from this page
            embedded = response_data.get('_embedded', {})
            events = embedded.get('events', [])

            for event_data in events:
                parsed_event = parse_event(event_data)
                if parsed_event:
                    all_events.append(parsed_event)

        logger.info(f"Total events fetched and parsed: {len(all_events)}")
        return all_events

    except Exception as e:
        logger.error(f"Failed to fetch Ticketmaster events: {e}")
        raise


if __name__ == '__main__':
    print("Fetching events from Ticketmaster API...")

    try:
        # Fetch events
        events = fetch_ticketmaster_events()

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
        if events:
            from src.db.local_db import insert_events
            insert_events(events)
            print(f"\n✓ Inserted {len(events)} events into database")

        print("\n✓ Ticketmaster ingest complete")

    except Exception as e:
        print(f"\n✗ Ticketmaster ingest failed: {e}")
        raise
