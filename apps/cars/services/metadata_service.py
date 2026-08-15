from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = BASE_DIR / 'cleaned_used_cars_v2.csv'


@lru_cache(maxsize=1)
def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f'Dataset file not found: {DATA_PATH}')
    return pd.read_csv(DATA_PATH)


def get_all_brands() -> list[str]:
    df = _load_data()
    brands = df['brand'].dropna().astype(str).str.strip().unique()
    return sorted(brands.tolist())


def get_base_models_for_brand(brand: str) -> list[str]:
    df = _load_data()
    brand_clean = brand.strip().lower()
    filtered = df[df['brand'].astype(str).str.strip().str.lower() == brand_clean]
    models = filtered['base_model'].dropna().astype(str).str.strip().unique()
    return sorted(models.tolist())