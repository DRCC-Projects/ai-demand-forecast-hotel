"""
Local SQLite database models and operations for hotel demand forecasting.
Uses SQLAlchemy 2.0 with data/hotel.db as the database file.
"""

import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "hotel.db"
DB_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()


class Event(Base):
    """Events that may impact hotel demand (concerts, conferences, etc.)"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    venue = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    distance_km = Column(Float)
    attendance_tier = Column(String)  # small, medium, large
    impact_score = Column(Float)
    source = Column(String)
    source_url = Column(String)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('name', 'start_date', 'venue', name='_event_unique'),
    )


class DailyMetric(Base):
    """Daily hotel performance metrics"""
    __tablename__ = "daily_metrics"

    date = Column(Date, primary_key=True)
    occupancy_pct = Column(Float)
    adr_inr = Column(Float)
    rooms_sold = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Feature(Base):
    """Engineered features for ML model"""
    __tablename__ = "features"

    date = Column(Date, primary_key=True)
    day_of_week = Column(Integer)
    is_weekend = Column(Boolean)
    is_holiday = Column(Boolean)
    event_count_7d = Column(Integer)
    max_impact_score_7d = Column(Float)
    sum_impact_scores_7d = Column(Float)
    lag_1_occupancy = Column(Float)
    lag_7_occupancy = Column(Float)
    rolling_mean_7d_occupancy = Column(Float)
    rolling_mean_30d_occupancy = Column(Float)
    days_to_next_event = Column(Integer)
    days_since_last_event = Column(Integer)
    built_at = Column(DateTime, default=datetime.utcnow)


class Forecast(Base):
    """Model predictions for future occupancy and ADR"""
    __tablename__ = "forecasts"

    date = Column(Date, primary_key=True)
    occupancy_pred = Column(Float)
    adr_pred = Column(Float)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    model_version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create engine and session factory
engine = None
SessionLocal = None


def _get_engine():
    """Get or create database engine"""
    global engine, SessionLocal
    if engine is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        engine = create_engine(DB_URL, echo=False)
        SessionLocal = sessionmaker(bind=engine)
    return engine


def _get_session() -> Session:
    """Get a new database session"""
    if SessionLocal is None:
        _get_engine()
    return SessionLocal()


def init_db():
    """Initialize database by creating all tables"""
    try:
        eng = _get_engine()
        Base.metadata.create_all(eng)
        logger.info("DB initialised")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def insert_events(events: List[Dict]) -> int:
    """
    Upsert events by (name, start_date, venue).
    Updates existing events if the unique constraint is violated.
    """
    if not events:
        return 0
    try:
        eng = _get_engine()
        with sessionmaker(bind=eng)() as session:
            inserted = 0
            for event_data in events:
                try:
                    # Check if exists by unique constraint
                    existing = session.query(Event).filter_by(
                        name=event_data.get('name'),
                        start_date=event_data.get('start_date'),
                        venue=event_data.get('venue')
                    ).first()

                    if existing:
                        # Update impact score and scraped_at
                        for key, value in event_data.items():
                            if hasattr(existing, key):
                                setattr(existing, key, value)
                    else:
                        event = Event(**{k: v for k, v in event_data.items() if hasattr(Event, k)})
                        session.add(event)
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Skipping event {event_data.get('name')}: {e}")
                    session.rollback()
                    continue
            session.commit()
            logger.info(f"Successfully inserted/updated {inserted} events")
            return inserted
    except Exception as e:
        logger.error(f"Failed to insert events: {e}")
        return 0


def upsert_daily_metrics(rows: List[Dict]):
    """Upsert daily metrics by date"""
    try:
        session = _get_session()
        for row in rows:
            # Update timestamp on upsert
            row['updated_at'] = datetime.utcnow()
            metric = DailyMetric(**row)
            session.merge(metric)
        session.commit()
        session.close()
        logger.info(f"Successfully upserted {len(rows)} daily metrics")
    except Exception as e:
        logger.error(f"Failed to upsert daily metrics: {e}")
        if session:
            session.rollback()
            session.close()
        raise


def upsert_features(rows: List[Dict]):
    """Upsert features by date"""
    try:
        session = _get_session()
        for row in rows:
            # Update timestamp on upsert
            row['built_at'] = datetime.utcnow()
            feature = Feature(**row)
            session.merge(feature)
        session.commit()
        session.close()
        logger.info(f"Successfully upserted {len(rows)} features")
    except Exception as e:
        logger.error(f"Failed to upsert features: {e}")
        if session:
            session.rollback()
            session.close()
        raise


def upsert_forecasts(rows: List[Dict]):
    """Upsert forecasts by date"""
    try:
        session = _get_session()
        for row in rows:
            # Update timestamp on upsert
            row['created_at'] = datetime.utcnow()
            forecast = Forecast(**row)
            session.merge(forecast)
        session.commit()
        session.close()
        logger.info(f"Successfully upserted {len(rows)} forecasts")
    except Exception as e:
        logger.error(f"Failed to upsert forecasts: {e}")
        if session:
            session.rollback()
            session.close()
        raise


if __name__ == '__main__':
    # Smoke test
    print("Running smoke test...")

    # Initialize database
    init_db()

    # Sample data
    sample_event = [{
        'name': 'Test Concert',
        'start_date': date(2026, 5, 15),
        'end_date': date(2026, 5, 15),
        'venue': 'Test Venue',
        'lat': 12.9915,
        'lon': 77.7260,
        'distance_km': 2.5,
        'attendance_tier': 'large',
        'impact_score': 0.85,
        'source': 'test',
        'source_url': 'http://test.com'
    }]

    sample_metric = [{
        'date': date(2026, 5, 15),
        'occupancy_pct': 85.5,
        'adr_inr': 8500.0,
        'rooms_sold': 120
    }]

    sample_feature = [{
        'date': date(2026, 5, 15),
        'day_of_week': 4,
        'is_weekend': False,
        'is_holiday': False,
        'event_count_7d': 2,
        'max_impact_score_7d': 0.85,
        'sum_impact_scores_7d': 1.2,
        'lag_1_occupancy': 82.0,
        'lag_7_occupancy': 78.5,
        'rolling_mean_7d_occupancy': 80.2,
        'rolling_mean_30d_occupancy': 79.8,
        'days_to_next_event': 3,
        'days_since_last_event': 5
    }]

    sample_forecast = [{
        'date': date(2026, 5, 16),
        'occupancy_pred': 87.2,
        'adr_pred': 8800.0,
        'lower_bound': 82.0,
        'upper_bound': 92.0,
        'model_version': 'v1.0.0_test'
    }]

    # Insert sample data
    insert_events(sample_event)
    upsert_daily_metrics(sample_metric)
    upsert_features(sample_feature)
    upsert_forecasts(sample_forecast)

    # Verify counts
    session = _get_session()
    event_count = session.query(Event).count()
    metric_count = session.query(DailyMetric).count()
    feature_count = session.query(Feature).count()
    forecast_count = session.query(Forecast).count()
    session.close()

    print(f"Events: {event_count}")
    print(f"Daily Metrics: {metric_count}")
    print(f"Features: {feature_count}")
    print(f"Forecasts: {forecast_count}")

    if event_count == 1 and metric_count == 1 and feature_count == 1 and forecast_count == 1:
        print("\n✓ Smoke test passed")
    else:
        print("\n✗ Smoke test FAILED")
