"""Training pipeline for the used-car price prediction model (SRS retraining)."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DATA_PATH = BASE_DIR / 'cleaned_used_cars_v2.csv'
DEFAULT_MODEL_PATH = BASE_DIR / 'model' / 'best_used_car_price_xgb.xgb'

FEATURE_COLUMNS = [
    'brand',
    'model_year',
    'fuel_type',
    'transmission',
    'ext_col',
    'accident',
    'Country_of_Origin',
    'Engine_CC',
    'Mileage_KM',
    'base_model',
]

CATEGORICAL_COLUMNS = [
    'brand', 'fuel_type', 'transmission', 'ext_col',
    'accident', 'Country_of_Origin', 'base_model',
]

NUMERIC_COLUMNS = ['model_year', 'Engine_CC', 'Mileage_KM']


def train_and_save_model(
    data_path: Optional[Path] = None,
    model_path: Optional[Path] = None,
) -> dict:
    """Train the XGBoost pipeline on the cleaned dataset and save it atomically."""
    warnings.filterwarnings('ignore')

    import xgboost as xgb
    from sklearn.compose import ColumnTransformer
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    data_path = Path(data_path or DEFAULT_DATA_PATH)
    model_path = Path(model_path or DEFAULT_MODEL_PATH)

    df = pd.read_csv(data_path)
    missing = [col for col in FEATURE_COLUMNS + ['Price_USD'] if col not in df.columns]
    if missing:
        raise ValueError(f'Missing columns in dataset: {missing}')

    X = pd.DataFrame({col: df[col] for col in FEATURE_COLUMNS})
    y = df['Price_USD'].astype(float).to_numpy()

    for col in NUMERIC_COLUMNS:
        X[col] = pd.to_numeric(X[col], errors='coerce')
        X[col] = X[col].fillna(X[col].median()).replace([np.inf, -np.inf], 0).astype(float)

    mask = y > 0
    X = X[mask].reset_index(drop=True)
    y = y[mask]

    for col in CATEGORICAL_COLUMNS:
        X[col] = X[col].astype(str)

    use_log_target = bool(y.min() > 0)
    y_target = np.log1p(y) if use_log_target else y.copy()

    categorical_indices = [FEATURE_COLUMNS.index(col) for col in CATEGORICAL_COLUMNS]
    numeric_indices = [FEATURE_COLUMNS.index(col) for col in NUMERIC_COLUMNS]

    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_indices),
            ('num', 'passthrough', numeric_indices),
        ],
        verbose_feature_names_out=False,
    )

    regressor = xgb.XGBRegressor(
        n_estimators=800,
        learning_rate=0.05,
        max_depth=7,
        colsample_bytree=0.8,
        subsample=0.8,
        enable_categorical=False,
        objective='reg:squarederror',
        random_state=42,
    )

    pipeline = Pipeline(steps=[('preprocessor_xgb', preprocessor), ('regressor', regressor)])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_target, test_size=0.2, random_state=42,
    )

    pipeline.fit(X_train, y_train)
    pred_test = pipeline.predict(X_test)

    if use_log_target:
        pred_test_price = np.expm1(pred_test)
        y_test_price = np.expm1(y_test)
    else:
        pred_test_price = pred_test
        y_test_price = y_test

    mae = mean_absolute_error(y_test_price, pred_test_price)
    r2 = r2_score(y_test_price, pred_test_price)

    residuals = np.abs(y_test_price - pred_test_price)
    price_coefs = np.polyfit(pred_test_price, residuals, 1)

    pipeline.log1p_target = use_log_target
    pipeline.mae = float(mae)
    pipeline.r2 = float(r2)
    pipeline.error_a = float(price_coefs[0])
    pipeline.error_b = float(price_coefs[1])

    model_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = model_path.with_suffix('.tmp')
    joblib.dump(pipeline, str(tmp_path))
    tmp_path.replace(model_path)

    return {
        'mae': round(float(mae), 2),
        'r2': round(float(r2), 4),
        'rows': int(len(X)),
        'encoded_features': int(len(preprocessor.get_feature_names_out())),
        'target_transform': 'log1p' if use_log_target else 'direct',
        'model_path': str(model_path),
    }
