from __future__ import annotations

import joblib
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
MODEL_PATH = BASE_DIR / 'model' / 'best_used_car_price_xgb.xgb'

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

COLUMN_ALIASES = {
    'brand': 'brand',
    'model_year': 'model_year',
    'fuel_type': 'fuel_type',
    'transmission': 'transmission',
    'ext_col': 'ext_col',
    'accident': 'accident',
    'country_of_origin': 'Country_of_Origin',
    'Country_of_Origin': 'Country_of_Origin',
    'engine_cc': 'Engine_CC',
    'Engine_CC': 'Engine_CC',
    'mileage_km': 'Mileage_KM',
    'Mileage_KM': 'Mileage_KM',
    'base_model': 'base_model',
    'model': 'base_model',
}


def _normalize_record(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        normalized_key = str(key).strip()
        normalized_key = normalized_key.replace(' ', '_').replace('-', '_')
        canonical_key = COLUMN_ALIASES.get(normalized_key, normalized_key)
        normalized[canonical_key] = value
    return normalized


def _build_feature_frame(raw_data: Dict[str, Any]) -> pd.DataFrame:
    normalized = _normalize_record(raw_data)
    missing = [name for name in FEATURE_COLUMNS if name not in normalized]
    if missing:
        raise ValueError(f'Missing required fields: {missing}')

    ordered = {name: normalized[name] for name in FEATURE_COLUMNS}

    categorical_columns = [
        'brand', 'fuel_type', 'transmission', 'ext_col', 'accident',
        'Country_of_Origin', 'base_model',
    ]
    numeric_columns = ['model_year', 'Engine_CC', 'Mileage_KM']

    converted: Dict[str, Any] = {}
    for name, value in ordered.items():
        if name in categorical_columns:
            converted[name] = str(value)
        else:
            converted[name] = float(value)

    df = pd.DataFrame([converted])
    for name in categorical_columns:
        df[name] = df[name].astype(str)
    for name in numeric_columns:
        df[name] = pd.to_numeric(df[name], errors='coerce').astype(float)

    return df


def load_model(model_path: Optional[Path] = None):
    path = model_path or MODEL_PATH
    if not path.exists():
        raise FileNotFoundError(f'Model file not found: {path}')
    return joblib.load(str(path))


def predict_price(raw_data: Dict[str, Any], model=None, target_transformation: Optional[str] = None) -> float:
    if model is None:
        model = load_model()

    df = _build_feature_frame(raw_data)
    prediction = float(model.predict(df)[0])

    if model.log1p_target:
        return float(np.expm1(prediction))

    return prediction


def predict_price_range(
    predicted_price: float,
    model,
    confidence: float = 0.90,
    margin_percent: Optional[float] = None,
) -> Dict[str, float]:
    if margin_percent is None:
        margin_percent = 5.0

    margin = margin_percent / 100.0
    spread = predicted_price * margin

    return {
        'min_price_usd': max(0.0, round(predicted_price - spread, 2)),
        'max_price_usd': round(predicted_price + spread, 2),
        'margin_percent': margin_percent,
        'confidence': confidence,
    }


def predict_price_from_request(
    payload: Dict[str, Any],
    confidence: float = 0.90,
    margin_percent: Optional[float] = None,
) -> Dict[str, Any]:
    model = load_model()
    price = predict_price(payload, model=model)
    price_range = predict_price_range(price, model, confidence=confidence, margin_percent=margin_percent)
    return {
        'predicted_price_usd': round(price, 2),
        'target_transformation': 'Log1p(Price_USD)' if model.log1p_target else 'Direct Price_USD',
        'price_range': price_range,
    }