"""
Feature engineering for hotel demand forecasting.
Builds features from daily metrics, events, and holidays.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from sqlalchemy import create_engine

from src.db.local_db import DB_PATH, upsert_features

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
HOLIDAYS_CSV = Path(__file__).parent.parent.parent / "data" / "india_holidays_2023_2026.csv"


def load_data_from_db():
    """Load daily_metrics and events from SQLite"""
    logger.info("Loading data from SQLite database...")

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # Load daily metrics
    df_metrics = pd.read_sql_table('daily_metrics', engine, parse_dates=['date'])
    logger.info(f"Loaded {len(df_metrics)} rows from daily_metrics")

    # Load events
    try:
        df_events = pd.read_sql_table('events', engine, parse_dates=['start_date', 'end_date'])
        logger.info(f"Loaded {len(df_events)} rows from events")
    except Exception as e:
        logger.warning(f"Could not load events table: {e}")
        df_events = pd.DataFrame(columns=['start_date', 'end_date', 'impact_score'])

    return df_metrics, df_events


def load_holidays():
    """Load holidays from CSV"""
    if not HOLIDAYS_CSV.exists():
        logger.warning(f"Holidays CSV not found: {HOLIDAYS_CSV}")
        return pd.DataFrame(columns=['date'])

    df_holidays = pd.read_csv(HOLIDAYS_CSV, parse_dates=['date'])
    logger.info(f"Loaded {len(df_holidays)} holidays")
    return df_holidays


def build_features():
    """Build all features for the hotel demand forecasting model"""
    logger.info("Starting feature engineering...")

    # Load data
    df_metrics, df_events = load_data_from_db()
    df_holidays = load_holidays()

    if len(df_metrics) == 0:
        logger.error("No data in daily_metrics table. Cannot build features.")
        raise ValueError("daily_metrics table is empty")

    # Get date range
    min_date = df_metrics['date'].min()
    max_date = df_metrics['date'].max()
    logger.info(f"Date range: {min_date} to {max_date}")

    # Create complete date range
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')
    df = pd.DataFrame({'date': date_range})

    # Merge with metrics
    df = df.merge(df_metrics[['date', 'occupancy_pct']], on='date', how='left')

    # --- Calendar Features ---
    logger.info("Building calendar features...")
    df['day_of_week'] = df['date'].dt.dayofweek  # 0=Monday, 6=Sunday
    df['is_weekend'] = df['day_of_week'] >= 5

    # Holiday flag
    if len(df_holidays) > 0:
        holiday_dates = set(df_holidays['date'].dt.date)
        df['is_holiday'] = df['date'].dt.date.isin(holiday_dates)
    else:
        df['is_holiday'] = False

    # --- Event Features ---
    logger.info("Building event features...")

    if len(df_events) == 0:
        logger.warning("No events found. Setting all event features to 0.")
        df['event_count_7d'] = 0
        df['max_impact_score_7d'] = 0.0
        df['sum_impact_scores_7d'] = 0.0
    else:
        # For each date, find events within 7 days before or after
        event_features = []

        for current_date in df['date']:
            # Events where start_date is within 7 days before or after current date
            date_min = current_date - timedelta(days=7)
            date_max = current_date + timedelta(days=7)

            nearby_events = df_events[
                (df_events['start_date'] >= date_min) &
                (df_events['start_date'] <= date_max)
            ]

            event_count = len(nearby_events)
            max_impact = nearby_events['impact_score'].max() if event_count > 0 else 0.0
            sum_impact = nearby_events['impact_score'].sum() if event_count > 0 else 0.0

            event_features.append({
                'date': current_date,
                'event_count_7d': event_count,
                'max_impact_score_7d': max_impact,
                'sum_impact_scores_7d': sum_impact
            })

        df_event_features = pd.DataFrame(event_features)
        df = df.merge(df_event_features, on='date', how='left')

    # --- Lag Features ---
    logger.info("Building lag features...")

    # Sort by date to ensure proper lag calculation
    df = df.sort_values('date').reset_index(drop=True)

    df['lag_1_occupancy'] = df['occupancy_pct'].shift(1)
    df['lag_7_occupancy'] = df['occupancy_pct'].shift(7)

    # Rolling means
    df['rolling_mean_7d_occupancy'] = df['occupancy_pct'].rolling(window=7, min_periods=1).mean()
    df['rolling_mean_30d_occupancy'] = df['occupancy_pct'].rolling(window=30, min_periods=1).mean()

    # --- Proximity Features ---
    logger.info("Building proximity features...")

    if len(df_events) == 0:
        df['days_to_next_event'] = None
        df['days_since_last_event'] = None
    else:
        # Days to next event
        days_to_next = []
        days_since_last = []

        for current_date in df['date']:
            # Next event: event that starts on or after current date
            future_events = df_events[df_events['start_date'] >= current_date]
            if len(future_events) > 0:
                next_event_date = future_events['start_date'].min()
                days_to = (next_event_date - current_date).days
                days_to_next.append(days_to)
            else:
                days_to_next.append(None)

            # Last event: event that ended before current date
            past_events = df_events[df_events['end_date'] < current_date]
            if len(past_events) > 0:
                last_event_date = past_events['end_date'].max()
                days_since = (current_date - last_event_date).days
                days_since_last.append(days_since)
            else:
                days_since_last.append(None)

        df['days_to_next_event'] = days_to_next
        df['days_since_last_event'] = days_since_last

    # --- Prepare for database insertion ---
    logger.info("Preparing data for database insertion...")

    # Select only the columns we need for the features table
    feature_columns = [
        'date',
        'day_of_week',
        'is_weekend',
        'is_holiday',
        'event_count_7d',
        'max_impact_score_7d',
        'sum_impact_scores_7d',
        'lag_1_occupancy',
        'lag_7_occupancy',
        'rolling_mean_7d_occupancy',
        'rolling_mean_30d_occupancy',
        'days_to_next_event',
        'days_since_last_event'
    ]

    df_features = df[feature_columns].copy()

    # Convert date to Python date objects
    df_features['date'] = df_features['date'].dt.date

    # Convert to list of dicts
    records = df_features.to_dict('records')

    # --- Insert into database ---
    logger.info(f"Upserting {len(records)} feature rows to database...")
    upsert_features(records)

    # --- Print summary ---
    print("\n" + "="*60)
    print("FEATURE ENGINEERING SUMMARY")
    print("="*60)
    print(f"Total feature rows:   {len(df_features)}")
    print(f"Date range:           {df_features['date'].min()} to {df_features['date'].max()}")
    print(f"Holiday dates:        {df_features['is_holiday'].sum()}")
    print(f"Weekend dates:        {df_features['is_weekend'].sum()}")
    print(f"Dates with events:    {(df_features['event_count_7d'] > 0).sum()}")
    print(f"Avg event count:      {df_features['event_count_7d'].mean():.2f}")
    print(f"Avg lag-1 occupancy:  {df_features['lag_1_occupancy'].mean():.2f}%")
    print(f"Avg rolling 7d occ:   {df_features['rolling_mean_7d_occupancy'].mean():.2f}%")
    print("="*60)

    print("\n✓ Feature engineering complete")

    return df_features


if __name__ == '__main__':
    try:
        build_features()
    except Exception as e:
        logger.error(f"Feature engineering failed: {e}")
        print(f"\n✗ Feature engineering failed: {e}")
        exit(1)
