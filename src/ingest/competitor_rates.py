"""
Xotelo API integration for competitor hotel rates.
Fetches current rates from major OTAs for Bengaluru hotels.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
API_BASE_URL = "https://data.xotelo.com/api/rates"

HOTEL_LIST = [
    ('g297628-d12732541', 'Conrad Bengaluru', 5),
    ('g297628-d4470098',  'JW Marriott Bengaluru', 5),
    ('g297628-d1567342',  'ITC Gardenia', 5),
    ('g297628-d302480',   'The Leela Palace', 5),
    ('g297628-d1776454',  'Lemon Tree Whitefield', 4),
    ('g297628-d13451291', 'Courtyard Marriott Hebbal', 4),
    ('g297628-d6781827',  'ibis Bengaluru City Centre', 3),
    ('g297628-d25424107', 'GreenPark Bengaluru', 4),
    ('g297628-d23498278', 'The Leela Bhartiya City', 5),
    ('g297628-d15215123', 'Grand Mercure Gopalan Mall', 4),
]


def fetch_hotel_rates(hotel_key: str, hotel_name: str, stars: int,
                     chk_in: str, chk_out: str) -> Optional[Dict]:
    """
    Fetch rates for a single hotel from Xotelo API.
    Returns dict with rate data or None on error.
    """
    try:
        params = {
            'hotel_key': hotel_key,
            'chk_in': chk_in,
            'chk_out': chk_out,
            'currency': 'INR'
        }

        logger.info(f"Fetching rates for {hotel_name}")
        response = requests.get(API_BASE_URL, params=params, timeout=30)

        if response.status_code != 200:
            logger.warning(f"API returned {response.status_code} for {hotel_name}")
            return None

        data = response.json()

        # Parse rates from response
        result = data.get('result', {})
        rates_list = result.get('rates', [])

        if not rates_list:
            logger.warning(f"No rates found for {hotel_name}")
            return None

        # Extract rates by OTA code
        rate_map = {}
        for rate_obj in rates_list:
            code = rate_obj.get('code')
            rate = rate_obj.get('rate')

            if code and rate is not None:
                try:
                    rate_map[code] = float(rate)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rate for {code}: {rate}")

        # Get specific OTA rates
        booking_com = rate_map.get('BookingCom')
        expedia = rate_map.get('Expedia')
        agoda = rate_map.get('Agoda')
        trip_com = rate_map.get('TripCom')

        # Find cheapest rate from all available (only rates > 0)
        all_rates = [r for r in rate_map.values() if r > 0]
        cheapest = min(all_rates) if all_rates else None

        # Validate INR rates - valid INR rates should be > 1000
        # If all rates < 1000, currency param was ignored and we got USD
        if cheapest and cheapest < 1000:
            logger.warning(f"{hotel_name}: rates appear to be in USD (< 1000), converting to INR")
            usd_to_inr = 83.5
            cheapest = cheapest * usd_to_inr if cheapest else None
            booking_com = booking_com * usd_to_inr if booking_com else None
            expedia = expedia * usd_to_inr if expedia else None
            agoda = agoda * usd_to_inr if agoda else None
            trip_com = trip_com * usd_to_inr if trip_com else None

        if cheapest:
            logger.info(f"{hotel_name}: cheapest = ₹{cheapest:,.0f}")
        else:
            logger.warning(f"{hotel_name}: no valid rates found")

        return {
            'name': hotel_name,
            'stars': stars,
            'cheapest': cheapest,
            'booking_com': booking_com,
            'expedia': expedia,
            'agoda': agoda,
            'trip_com': trip_com,
            'chk_in': chk_in,
            'fetched_at': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching rates for {hotel_name}: {e}")
        return None


def fetch_all_competitor_rates(nights_ahead: int = 0) -> List[Dict]:
    """
    Fetch rates for all competitor hotels.
    Returns list of rate dicts sorted by cheapest rate.
    """
    # Calculate check-in/out dates
    chk_in_date = datetime.now().date() + timedelta(days=nights_ahead)
    chk_out_date = chk_in_date + timedelta(days=1)

    chk_in = chk_in_date.isoformat()
    chk_out = chk_out_date.isoformat()

    logger.info(f"Fetching rates for check-in: {chk_in}, check-out: {chk_out}")

    all_rates = []

    for hotel_key, hotel_name, stars in HOTEL_LIST:
        rates = fetch_hotel_rates(hotel_key, hotel_name, stars, chk_in, chk_out)

        if rates:
            all_rates.append(rates)

        # Sleep between requests to be polite to API
        time.sleep(0.5)

    # Sort by cheapest rate (hotels with no rate go to end)
    all_rates.sort(key=lambda x: x['cheapest'] if x['cheapest'] else float('inf'))

    logger.info(f"Successfully fetched rates for {len(all_rates)}/{len(HOTEL_LIST)} hotels")

    # Save to JSON file
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), 'data')
        os.makedirs(data_dir, exist_ok=True)

        output_path = os.path.join(data_dir, 'competitor_rates.json')
        with open(output_path, 'w') as f:
            json.dump(all_rates, f, indent=2)
        logger.info(f"Saved rates to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save rates to file: {e}")

    return all_rates


if __name__ == '__main__':
    print("Fetching competitor rates from Xotelo API...")
    print("This may take a minute...\n")

    rates = fetch_all_competitor_rates()

    if rates:
        print(f'\nMarket Rates for tonight - Bengaluru Hotels')
        print(f'{"Hotel":<35} {"Stars":<7} {"Cheapest (INR)"}')
        print('-' * 60)

        for h in rates:
            stars = '*' * h['stars']
            rate = f"Rs.{h['cheapest']:,.0f}" if h['cheapest'] else 'N/A'
            print(f"{h['name']:<35} {stars:<7} {rate}")

        print("\n✓ Competitor rates fetch complete")
    else:
        print("\n⚠ No competitor rates found")
