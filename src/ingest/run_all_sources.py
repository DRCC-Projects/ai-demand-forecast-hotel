"""
Master event ingestion script - pulls from ALL sources and deduplicates.
Combines Eventbrite, Ticketmaster, web scraping, and manual CSV.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import json
import csv
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup
from haversine import haversine, Unit

from src.db.local_db import insert_events

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Hotel coordinates
HOTEL_LAT = 12.9915
HOTEL_LON = 77.7260

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Headers for web scraping
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}


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


def fetch_eventbrite_events() -> List[Dict]:
    """SOURCE 1: Fetch from Eventbrite API"""
    try:
        logger.info("Fetching from Eventbrite...")
        from src.ingest.eventbrite import fetch_eventbrite_events as eventbrite_fetch
        events = eventbrite_fetch()
        logger.info(f"Eventbrite: {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"Eventbrite fetch failed: {e}")
        return []


def fetch_ticketmaster_events() -> List[Dict]:
    """SOURCE 2: Fetch from Ticketmaster API"""
    try:
        logger.info("Fetching from Ticketmaster...")
        from src.ingest.ticketmaster import fetch_ticketmaster_events as tm_fetch
        events = tm_fetch()
        logger.info(f"Ticketmaster: {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"Ticketmaster fetch failed: {e}")
        return []


def scrape_bookmyshow_events() -> List[Dict]:
    """SOURCE 3: Scrape BookMyShow"""
    try:
        logger.info("Scraping BookMyShow...")
        url = "https://in.bookmyshow.com/explore/events-bengaluru"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.google.com/"
        }

        response = requests.get(url, headers=headers, timeout=15)
        events = []

        # Extract JSON-LD structured data
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')

        for script in scripts:
            try:
                data = json.loads(script.string)

                # Handle both single events and arrays
                events_data = [data] if isinstance(data, dict) else data
                if isinstance(data, list):
                    events_data = data

                for event_data in events_data:
                    if not isinstance(event_data, dict):
                        continue

                    if event_data.get('@type') == 'Event':
                        name = event_data.get('name')
                        start_str = event_data.get('startDate')

                        if name and start_str:
                            try:
                                start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
                            except:
                                start_date = date.today() + timedelta(days=7)

                            end_date = start_date

                            # Extract location
                            location = event_data.get('location', {})
                            venue_name = location.get('name', 'Bengaluru')

                            # Default to Bengaluru center
                            lat = 12.9716
                            lon = 77.5946

                            distance_km = calculate_distance_km(lat, lon)
                            attendance_tier = "medium"
                            impact_score = calculate_impact_score(attendance_tier, distance_km, start_date, end_date)

                            events.append({
                                'name': name,
                                'start_date': start_date,
                                'end_date': end_date,
                                'venue': venue_name,
                                'lat': lat,
                                'lon': lon,
                                'distance_km': round(distance_km, 2),
                                'attendance_tier': attendance_tier,
                                'impact_score': impact_score,
                                'source': 'bookmyshow',
                                'source_url': url
                            })
            except Exception:
                continue

        logger.info(f"BookMyShow: {len(events)} events")
        return events

    except Exception as e:
        logger.error(f"BookMyShow scrape failed: {e}")
        return []


def fetch_insider_api_events() -> List[Dict]:
    """SOURCE 4: Fetch from Paytm Insider API"""
    try:
        logger.info("Fetching from Insider API...")
        url = "https://api.insider.in/api/events?tags_slug=bengaluru&type=experiences,plays,sports,workshops,tech&page_size=50&page=1"

        headers = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        events = []

        events_data = data.get('events', [])

        for event_data in events_data:
            try:
                name = event_data.get('name')
                if not name:
                    continue

                # Convert unix timestamps to dates
                min_show_start = event_data.get('min_show_start_time')
                max_show_start = event_data.get('max_show_start_time')

                if min_show_start:
                    start_date = datetime.fromtimestamp(min_show_start).date()
                else:
                    continue

                if max_show_start:
                    end_date = datetime.fromtimestamp(max_show_start).date()
                else:
                    end_date = start_date

                # Extract venue info
                venues = event_data.get('venues', [])
                if venues and len(venues) > 0:
                    venue = venues[0]
                    venue_name = venue.get('name', 'Bengaluru')
                    lat = float(venue.get('lat', 12.9716))
                    lon = float(venue.get('lng', 77.5946))
                else:
                    venue_name = 'Bengaluru'
                    lat = 12.9716
                    lon = 77.5946

                distance_km = calculate_distance_km(lat, lon)
                attendance_tier = "medium"
                impact_score = calculate_impact_score(attendance_tier, distance_km, start_date, end_date)

                events.append({
                    'name': name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'venue': venue_name,
                    'lat': lat,
                    'lon': lon,
                    'distance_km': round(distance_km, 2),
                    'attendance_tier': attendance_tier,
                    'impact_score': impact_score,
                    'source': 'insider',
                    'source_url': 'https://insider.in/bengaluru'
                })

            except Exception as e:
                logger.warning(f"Error parsing Insider event: {e}")
                continue

        logger.info(f"Insider API: {len(events)} events")
        return events

    except Exception as e:
        logger.error(f"Insider API fetch failed: {e}")
        return []


def load_manual_events() -> List[Dict]:
    """SOURCE 7: Load from manual CSV"""
    try:
        logger.info("Loading manual events from CSV...")
        from src.ingest.manual_events import load_manual_events as manual_loader
        events = manual_loader()
        logger.info(f"Manual: {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"Manual events load failed: {e}")
        return []


def fuzzy_match_score(str1: str, str2: str) -> float:
    """Calculate fuzzy match score between two strings"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def deduplicate_events(all_events: List[Dict]) -> List[Dict]:
    """Deduplicate events by exact and fuzzy matching"""
    logger.info(f"Deduplicating {len(all_events)} events...")

    unique_events = []
    seen_keys = set()

    # Sort by impact score (descending) to keep higher impact events
    all_events_sorted = sorted(all_events, key=lambda x: x['impact_score'], reverse=True)

    for event in all_events_sorted:
        # Exact match key
        exact_key = (event['name'].lower().strip(), event['start_date'])

        if exact_key in seen_keys:
            continue

        # Check fuzzy matches
        is_duplicate = False
        for existing_event in unique_events:
            name_similarity = fuzzy_match_score(event['name'], existing_event['name'])
            date_diff = abs((event['start_date'] - existing_event['start_date']).days)

            # Fuzzy match: >80% name similarity and dates within 1 day
            if name_similarity > 0.8 and date_diff <= 1:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_events.append(event)
            seen_keys.add(exact_key)

    logger.info(f"After deduplication: {len(unique_events)} unique events")
    return unique_events


def get_all_events() -> List[Dict]:
    """
    Fetch and deduplicate events from all sources.
    Returns combined list without inserting to database.
    """
    logger.info("="*60)
    logger.info("FETCHING EVENTS FROM ALL SOURCES")
    logger.info("="*60)

    all_events = []
    source_counts = {}

    # Fetch from all sources
    sources = {
        'Eventbrite': fetch_eventbrite_events,
        'Ticketmaster': fetch_ticketmaster_events,
        'BookMyShow': scrape_bookmyshow_events,
        'Insider': fetch_insider_api_events,
        'Manual': load_manual_events
    }

    for source_name, fetch_func in sources.items():
        try:
            events = fetch_func()
            all_events.extend(events)
            source_counts[source_name] = len(events)
        except Exception as e:
            logger.error(f"Source {source_name} failed: {e}")
            source_counts[source_name] = 0

    # Deduplicate
    unique_events = deduplicate_events(all_events)

    # Print summary table
    print("\n" + "="*60)
    print("EVENT SOURCE SUMMARY")
    print("="*60)
    for source_name, count in source_counts.items():
        print(f"{source_name:<20} {count:>5} events")
    print("-"*60)
    print(f"{'Total raw events':<20} {len(all_events):>5}")
    print(f"{'Unique events':<20} {len(unique_events):>5}")
    print("="*60)

    return unique_events


def run_all_sources():
    """Main function: fetch from all sources and insert to database"""
    # Get all events
    unique_events = get_all_events()

    # Insert to database
    if len(unique_events) > 0:
        logger.info("Inserting events to database...")
        insert_events(unique_events)
        print(f"\n✓ Inserted {len(unique_events)} unique events to database")
    else:
        print("\n⚠ No events to insert")

    print("\n✓ All sources ingestion complete")


if __name__ == '__main__':
    run_all_sources()
