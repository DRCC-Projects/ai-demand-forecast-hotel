"""
Train XGBoost models for hotel occupancy and ADR prediction.
Uses GPU acceleration if available, falls back to CPU.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import logging
from pathlib import Path
from datetime import datetime, date, timedelta
import pickle

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

from src.db.local_db import DB_PATH

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
MODELS_DIR = Path(__file__).parent.parent.parent / "models"
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Create directories
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Feature columns
FEATURE_COLUMNS = [
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
    'days_since_last_event',
    'month',
    'quarter',
    'is_peak_season'
]

# Time-series split date
SPLIT_DATE = date(2025, 7, 1)


def check_gpu_availability():
    """Check if GPU is available for XGBoost"""
    try:
        import torch
        if torch.cuda.is_available():
            tree_method = 'hist'
            device = 'cuda'
            logging.info("GPU detected: using CUDA for training")
            return tree_method, device
        else:
            tree_method = 'hist'
            device = 'cpu'
            logging.warning("GPU not available, using CPU")
            return tree_method, device
    except Exception as e:
        tree_method = 'hist'
        device = 'cpu'
        logging.warning(f"GPU check failed: {e}. Using CPU")
        return tree_method, device


def load_training_data():
    """Load features and metrics from SQLite"""
    logger.info("Loading training data from SQLite...")

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # Load features
    df_features = pd.read_sql_table('features', engine, parse_dates=['date'])
    logger.info(f"Loaded {len(df_features)} rows from features table")

    # Load daily metrics
    df_metrics = pd.read_sql_table('daily_metrics', engine, parse_dates=['date'])
    logger.info(f"Loaded {len(df_metrics)} rows from daily_metrics table")

    # Join features with metrics
    df = df_features.merge(
        df_metrics[['date', 'occupancy_pct', 'adr_inr']],
        on='date',
        how='inner'
    )

    # Drop rows where targets are null (future dates with no actuals)
    df = df.dropna(subset=['occupancy_pct', 'adr_inr'])
    logger.info(f"After dropping null targets: {len(df)} rows")

    if len(df) == 0:
        raise ValueError("No valid training data available")

    # Add additional engineered features
    logger.info("Engineering additional features...")
    df['month'] = pd.to_datetime(df['date']).dt.month
    df['quarter'] = pd.to_datetime(df['date']).dt.quarter
    df['is_peak_season'] = df['month'].isin([10, 11, 12, 1, 2]).astype(int)
    logger.info("Added features: month, quarter, is_peak_season")

    return df


def preprocess_features(df):
    """Preprocess features: drop high-null columns, impute, save preprocessor"""
    logger.info("Preprocessing features...")

    # Check for feature columns
    available_features = [col for col in FEATURE_COLUMNS if col in df.columns]
    missing_features = [col for col in FEATURE_COLUMNS if col not in df.columns]

    if missing_features:
        logger.warning(f"Missing feature columns: {missing_features}")

    X = df[available_features].copy()
    X.columns = X.columns.astype(str)

    # Drop columns with >30% nulls
    null_pct = X.isnull().mean()
    high_null_cols = null_pct[null_pct > 0.3].index.tolist()

    if high_null_cols:
        logger.warning(f"Dropping columns with >30% nulls: {high_null_cols}")
        X = X.drop(columns=high_null_cols)
        X.columns = X.columns.astype(str)

    # Get final feature columns
    final_features = X.columns.tolist()
    logger.info(f"Final feature columns: {final_features}")

    # Impute remaining nulls with median
    imputer = SimpleImputer(strategy='median')
    X_imputed = imputer.fit_transform(X.values)
    X = pd.DataFrame(X_imputed, columns=[str(c) for c in final_features], index=X.index)

    # Save preprocessor and feature columns
    preprocessor_path = MODELS_DIR / "preprocessor.pkl"
    with open(preprocessor_path, 'wb') as f:
        pickle.dump(imputer, f)
    logger.info(f"Saved preprocessor to {preprocessor_path}")

    features_path = MODELS_DIR / "feature_columns.pkl"
    with open(features_path, 'wb') as f:
        pickle.dump(final_features, f)
    logger.info(f"Saved feature columns to {features_path}")

    return X, final_features


def calculate_mape(y_true, y_pred):
    """Calculate Mean Absolute Percentage Error, handling zeros"""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    # Avoid division by zero
    mask = y_true != 0
    if mask.sum() == 0:
        return 0.0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def train_models(df, X, feature_columns):
    """Train XGBoost models for occupancy and ADR"""
    logger.info("Training XGBoost models...")

    # Check GPU availability
    tree_method, device = check_gpu_availability()

    logger.info(f"Using tree_method='{tree_method}', device='{device}'")

    # Time-series split
    train_mask = df['date'].dt.date < SPLIT_DATE
    val_mask = df['date'].dt.date >= SPLIT_DATE

    X_train = X[train_mask]
    X_val = X[val_mask]
    y_train_occ = df.loc[train_mask, 'occupancy_pct']
    y_val_occ = df.loc[val_mask, 'occupancy_pct']
    y_train_adr = df.loc[train_mask, 'adr_inr']
    y_val_adr = df.loc[val_mask, 'adr_inr']

    logger.info(f"Train size: {len(X_train)} rows")
    logger.info(f"Validation size: {len(X_val)} rows")

    if len(X_val) == 0:
        logger.warning("No validation data available. Using full dataset for training.")
        X_val = X_train
        y_val_occ = y_train_occ
        y_val_adr = y_train_adr

    # XGBoost parameters
    params = {
        'tree_method': tree_method,
        'device': device,
        'objective': 'reg:squarederror',
        'max_depth': 5,
        'learning_rate': 0.1,
        'n_estimators': 300,
        'subsample': 0.8,
        'early_stopping_rounds': 15,
        'random_state': 42,
        'verbosity': 1
    }

    # Train occupancy model
    logger.info("Training occupancy model...")
    occupancy_model = xgb.XGBRegressor(**params)
    occupancy_model.fit(
        X_train, y_train_occ,
        eval_set=[(X_val, y_val_occ)],
        verbose=False
    )

    # Train ADR model
    logger.info("Training ADR model...")
    adr_model = xgb.XGBRegressor(**params)
    adr_model.fit(
        X_train, y_train_adr,
        eval_set=[(X_val, y_val_adr)],
        verbose=False
    )

    # Evaluate models
    logger.info("Evaluating models on validation set...")

    # Occupancy predictions
    y_pred_occ = occupancy_model.predict(X_val)
    occ_mae = mean_absolute_error(y_val_occ, y_pred_occ)
    occ_mape = calculate_mape(y_val_occ, y_pred_occ)
    occ_r2 = r2_score(y_val_occ, y_pred_occ)

    # ADR predictions
    y_pred_adr = adr_model.predict(X_val)
    adr_mae = mean_absolute_error(y_val_adr, y_pred_adr)
    adr_mape = calculate_mape(y_val_adr, y_pred_adr)
    adr_r2 = r2_score(y_val_adr, y_pred_adr)

    # Print metrics
    print("\n" + "="*60)
    print("MODEL EVALUATION METRICS")
    print("="*60)
    print(f"Occupancy Model:")
    print(f"  MAE:  {occ_mae:.2f}%")
    print(f"  MAPE: {occ_mape:.2f}%")
    print(f"  R²:   {occ_r2:.4f}")
    print()
    print(f"ADR Model:")
    print(f"  MAE:  ₹{adr_mae:.2f}")
    print(f"  MAPE: {adr_mape:.2f}%")
    print(f"  R²:   {adr_r2:.4f}")
    print("="*60)

    metrics = {
        'occ_mae': occ_mae,
        'occ_mape': occ_mape,
        'occ_r2': occ_r2,
        'adr_mae': adr_mae,
        'adr_mape': adr_mape,
        'adr_r2': adr_r2,
        'train_rows': len(X_train),
        'val_rows': len(X_val)
    }

    return occupancy_model, adr_model, metrics


def save_models(occupancy_model, adr_model):
    """Save trained models to disk"""
    logger.info("Saving models...")

    # Save in native XGBoost format (.ubj)
    occ_path = MODELS_DIR / "occupancy.ubj"
    occupancy_model.save_model(occ_path)
    logger.info(f"Saved occupancy model to {occ_path}")

    adr_path = MODELS_DIR / "adr.ubj"
    adr_model.save_model(adr_path)
    logger.info(f"Saved ADR model to {adr_path}")


def log_metrics(metrics):
    """Log training metrics to CSV"""
    logger.info("Logging metrics...")

    log_path = REPORTS_DIR / "training_log.csv"

    # Create log entry
    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_entry = {
        'trained_at': datetime.now().isoformat(),
        'model_version': model_version,
        'train_rows': metrics['train_rows'],
        'val_rows': metrics['val_rows'],
        'occ_mae': round(metrics['occ_mae'], 2),
        'occ_mape': round(metrics['occ_mape'], 2),
        'occ_r2': round(metrics['occ_r2'], 4),
        'adr_mae': round(metrics['adr_mae'], 2),
        'adr_mape': round(metrics['adr_mape'], 2),
        'adr_r2': round(metrics['adr_r2'], 4)
    }

    # Append to CSV
    df_log = pd.DataFrame([log_entry])

    if log_path.exists():
        df_log.to_csv(log_path, mode='a', header=False, index=False)
    else:
        df_log.to_csv(log_path, index=False)

    logger.info(f"Logged metrics to {log_path}")
    return model_version


def generate_sample_forecast():
    """Generate sample 30-day forecast after training"""
    logger.info("Generating 30-day sample forecast...")

    try:
        # This is a placeholder - actual prediction logic would go here
        # For now, just create a simple forecast
        today = date.today()
        forecast_dates = [today + timedelta(days=i) for i in range(1, 31)]

        forecast_data = []
        for forecast_date in forecast_dates:
            # Simple projection (this would use actual model predictions)
            forecast_data.append({
                'date': forecast_date,
                'occupancy_pred': 70.0,  # Placeholder
                'adr_pred': 7000.0,      # Placeholder
                'note': 'Sample forecast'
            })

        df_forecast = pd.DataFrame(forecast_data)
        forecast_path = DATA_DIR / "sample_forecast.csv"
        df_forecast.to_csv(forecast_path, index=False)

        logger.info(f"Saved sample forecast to {forecast_path}")

    except Exception as e:
        logger.error(f"Failed to generate sample forecast: {e}")


def train():
    """Main training pipeline"""
    logger.info("="*60)
    logger.info("STARTING MODEL TRAINING")
    logger.info("="*60)

    try:
        # Load data
        df = load_training_data()

        # Preprocess features
        X, feature_columns = preprocess_features(df)

        # Train models
        occupancy_model, adr_model, metrics = train_models(df, X, feature_columns)

        # Save models
        save_models(occupancy_model, adr_model)

        # Log metrics
        model_version = log_metrics(metrics)

        # Generate sample forecast
        generate_sample_forecast()

        print(f"\n✓ Training complete")
        print(f"Model version: {model_version}")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        print(f"\n✗ Training failed: {e}")
        raise


if __name__ == '__main__':
    train()
