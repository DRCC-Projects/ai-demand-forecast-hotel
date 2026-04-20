"""
Generate forecasts using trained XGBoost models.
Predicts occupancy and ADR for a specified date range.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
import argparse
import pickle
from pathlib import Path
from datetime import datetime, date, timedelta

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import xgboost as xgb

from src.db.local_db import DB_PATH, upsert_forecasts

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
MODELS_DIR = Path(__file__).parent.parent.parent / "models"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
HOLIDAYS_CSV = DATA_DIR / "india_holidays_2023_2026.csv"

# Default occupancy (dataset mean) for when lag values are unavailable
DEFAULT_OCCUPANCY = 74.0


def load_models_and_preprocessor():
    """Load trained models, feature columns, and preprocessor"""
    logger.info("Loading models and preprocessor...")

    # Load models
    occupancy_model_path = MODELS_DIR / "occupancy.ubj"
    adr_model_path = MODELS_DIR / "adr.ubj"

    if not occupancy_model_path.exists() or not adr_model_path.exists():
        raise FileNotFoundError("Model files not found. Please train models first.")

    occupancy_model = xgb.XGBRegressor()
    occupancy_model.load_model(occupancy_model_path)
    logger.info(f"Loaded occupancy model from {occupancy_model_path}")

    adr_model = xgb.XGBRegressor()
    adr_model.load_model(adr_model_path)
    logger.info(f"Loaded ADR model from {adr_model_path}")

    # Load feature columns
    features_path = MODELS_DIR / "feature_columns.pkl"
    if not features_path.exists():
        raise FileNotFoundError("feature_columns.pkl not found")

    with open(features_path, 'rb') as f:
        feature_columns = pickle.load(f)
    logger.info(f"Loaded {len(feature_columns)} feature columns")

    # Load preprocessor
    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    if not preprocessor_path.exists():
        raise FileNotFoundError("preprocessor.pkl not found")

    with open(preprocessor_path, 'rb') as f:
        preprocessor = pickle.load(f)
    logger.info("Loaded preprocessor")

    return occupancy_model, adr_model, feature_columns, preprocessor


def load_holidays():
    """Load holiday dates"""
    if not HOLIDAYS_CSV.exists():
        logger.warning(f"Holidays CSV not found: {HOLIDAYS_CSV}")
        return set()

    df_holidays = pd.read_csv(HOLIDAYS_CSV, parse_dates=['date'])
    holiday_dates = set(df_holidays['date'].dt.date)
    logger.info(f"Loaded {len(holiday_dates)} holidays")
    return holiday_dates


def load_events_from_db():
    """Load events from SQLite"""
    engine = create_engine(f"sqlite:///{DB_PATH}")
    try:
        df_events = pd.read_sql_table('events', engine, parse_dates=['start_date', 'end_date'])
        logger.info(f"Loaded {len(df_events)} events from database")
        return df_events
    except Exception as e:
        logger.warning(f"Could not load events: {e}")
        return pd.DataFrame(columns=['start_date', 'end_date', 'impact_score'])


def get_last_known_occupancy():
    """Get the most recent actual occupancy from daily_metrics"""
    engine = create_engine(f"sqlite:///{DB_PATH}")
    try:
        query = """
        SELECT date, occupancy_pct
        FROM daily_metrics
        WHERE occupancy_pct IS NOT NULL
        ORDER BY date DESC
        LIMIT 30
        """
        df = pd.read_sql_query(query, engine, parse_dates=['date'])
        if len(df) > 0:
            logger.info(f"Loaded last {len(df)} actual occupancy values")
            return df
        else:
            logger.warning("No historical occupancy data found")
            return pd.DataFrame()
    except Exception as e:
        logger.warning(f"Could not load historical data: {e}")
        return pd.DataFrame()


def build_features_for_date(target_date, holidays, df_events, df_historical, feature_columns):
    """Build feature vector for a single date"""
    features = {}

    # Calendar features
    features['day_of_week'] = target_date.weekday()
    features['is_weekend'] = 1 if target_date.weekday() >= 5 else 0
    features['is_holiday'] = 1 if target_date in holidays else 0
    features['month'] = target_date.month
    features['quarter'] = (target_date.month - 1) // 3 + 1
    features['is_peak_season'] = 1 if target_date.month in [10, 11, 12, 1, 2] else 0

    # Event features
    if len(df_events) > 0:
        date_min = target_date - timedelta(days=7)
        date_max = target_date + timedelta(days=7)

        nearby_events = df_events[
            (df_events['start_date'].dt.date >= date_min) &
            (df_events['start_date'].dt.date <= date_max)
        ]

        features['event_count_7d'] = len(nearby_events)
        features['max_impact_score_7d'] = nearby_events['impact_score'].max() if len(nearby_events) > 0 else 0.0
        features['sum_impact_scores_7d'] = nearby_events['impact_score'].sum() if len(nearby_events) > 0 else 0.0

        # Days to next event
        future_events = df_events[df_events['start_date'].dt.date >= target_date]
        if len(future_events) > 0:
            next_event_date = future_events['start_date'].dt.date.min()
            features['days_to_next_event'] = (next_event_date - target_date).days
        else:
            features['days_to_next_event'] = None

        # Days since last event
        past_events = df_events[df_events['end_date'].dt.date < target_date]
        if len(past_events) > 0:
            last_event_date = past_events['end_date'].dt.date.max()
            features['days_since_last_event'] = (target_date - last_event_date).days
        else:
            features['days_since_last_event'] = None
    else:
        features['event_count_7d'] = 0
        features['max_impact_score_7d'] = 0.0
        features['sum_impact_scores_7d'] = 0.0
        features['days_to_next_event'] = None
        features['days_since_last_event'] = None

    # Lag features (use last known actuals or default)
    if len(df_historical) > 0:
        # Get lag values from historical data
        hist_dict = dict(zip(df_historical['date'].dt.date, df_historical['occupancy_pct']))

        lag_1_date = target_date - timedelta(days=1)
        lag_7_date = target_date - timedelta(days=7)

        features['lag_1_occupancy'] = hist_dict.get(lag_1_date, DEFAULT_OCCUPANCY)
        features['lag_7_occupancy'] = hist_dict.get(lag_7_date, DEFAULT_OCCUPANCY)

        # Rolling means (use last known values as proxy)
        recent_values = [v for d, v in hist_dict.items() if d < target_date]
        if len(recent_values) > 0:
            features['rolling_mean_7d_occupancy'] = np.mean(recent_values[-7:])
            features['rolling_mean_30d_occupancy'] = np.mean(recent_values[-30:])
        else:
            features['rolling_mean_7d_occupancy'] = DEFAULT_OCCUPANCY
            features['rolling_mean_30d_occupancy'] = DEFAULT_OCCUPANCY
    else:
        features['lag_1_occupancy'] = DEFAULT_OCCUPANCY
        features['lag_7_occupancy'] = DEFAULT_OCCUPANCY
        features['rolling_mean_7d_occupancy'] = DEFAULT_OCCUPANCY
        features['rolling_mean_30d_occupancy'] = DEFAULT_OCCUPANCY

    # Return only the features that were used during training
    return {col: features.get(col, 0) for col in feature_columns}


def generate_forecast(start_date, end_date, output_format):
    """Generate forecasts for the specified date range"""
    logger.info(f"Generating forecast from {start_date} to {end_date}")

    # Load models and data
    occupancy_model, adr_model, feature_columns, preprocessor = load_models_and_preprocessor()
    holidays = load_holidays()
    df_events = load_events_from_db()
    df_historical = get_last_known_occupancy()

    # Generate date range
    current_date = start_date
    forecast_data = []

    while current_date <= end_date:
        # Build features
        features = build_features_for_date(
            current_date,
            holidays,
            df_events,
            df_historical,
            feature_columns
        )

        forecast_data.append({
            'date': current_date,
            **features
        })

        current_date += timedelta(days=1)

    # Create DataFrame
    df = pd.DataFrame(forecast_data)
    logger.info(f"Built features for {len(df)} dates")

    # Prepare feature matrix
    X = df[feature_columns].copy()
    X.columns = X.columns.astype(str)

    # Apply preprocessor (convert to numpy array first)
    X_processed = preprocessor.transform(X.values)

    # Make predictions
    logger.info("Making predictions...")
    occupancy_pred = occupancy_model.predict(X_processed)
    adr_pred = adr_model.predict(X_processed)

    # Generate confidence bounds
    lower_bound = occupancy_pred * 0.90
    upper_bound = occupancy_pred * 1.10

    # Create forecast DataFrame
    df_forecast = pd.DataFrame({
        'date': df['date'],
        'occupancy_pred': occupancy_pred,
        'adr_pred': adr_pred,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound
    })

    # Model version
    model_version = date.today().strftime("%Y%m%d")

    # Output
    if output_format in ['csv', 'both']:
        csv_path = DATA_DIR / f"forecast_{model_version}.csv"
        df_forecast.to_csv(csv_path, index=False)
        logger.info(f"Saved forecast to {csv_path}")

    if output_format in ['sqlite', 'both']:
        # Prepare records for database
        records = []
        for _, row in df_forecast.iterrows():
            records.append({
                'date': row['date'],
                'occupancy_pred': float(row['occupancy_pred']),
                'adr_pred': float(row['adr_pred']),
                'lower_bound': float(row['lower_bound']),
                'upper_bound': float(row['upper_bound']),
                'model_version': model_version
            })

        upsert_forecasts(records)
        logger.info(f"Saved forecast to SQLite forecasts table")

    # Print forecast table
    print("\n" + "="*80)
    print("FORECAST")
    print("="*80)
    print(df_forecast.to_string(index=False))
    print("="*80)

    print(f"\n✓ Forecast complete: {len(df_forecast)} days generated")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate hotel demand forecasts using trained models'
    )
    parser.add_argument(
        '--start_date',
        type=str,
        default=(date.today() + timedelta(days=1)).isoformat(),
        help='Start date (YYYY-MM-DD, default: tomorrow)'
    )
    parser.add_argument(
        '--end_date',
        type=str,
        default=(date.today() + timedelta(days=30)).isoformat(),
        help='End date (YYYY-MM-DD, default: 30 days from tomorrow)'
    )
    parser.add_argument(
        '--output',
        type=str,
        choices=['csv', 'sqlite', 'both'],
        default='both',
        help='Output format (default: both)'
    )

    args = parser.parse_args()

    try:
        # Parse dates
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date)

        if start_date > end_date:
            raise ValueError("start_date must be before end_date")

        # Generate forecast
        generate_forecast(start_date, end_date, args.output)

    except Exception as e:
        logger.error(f"Forecast generation failed: {e}")
        print(f"\n✗ Forecast generation failed: {e}")
        exit(1)
