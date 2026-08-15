from __future__ import annotations

from typing import List, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apps.cars.models import Car

DEFAULT_LIMIT = 6


def _feature_text(car: Car) -> str:
    year_band = 5 * (car.model_year // 5)
    engine_band = 500 * (car.engine_cc // 500)
    mile_band = 20000 * (car.mileage_km // 20000)
    price = float(car.price_usd)
    price_band = 5000 * int(price // 5000)

    return ' '.join(
        [
            f'brand:{car.brand}',
            f'model:{car.base_model}',
            f'year:{year_band}',
            f'fuel:{car.fuel_type}',
            f'gearbox:{car.transmission}',
            f'color:{car.ext_col}',
            f'accident:{car.accident}',
            f'origin:{car.country_of_origin}',
            f'engine:{engine_band}',
            f'mileage:{mile_band}',
            f'price:{price_band}',
        ]
    )


def recommend_similar_cars(car: Car, limit: int = DEFAULT_LIMIT) -> List[Car]:
    """Content-based recommendation: returns the most similar AVAILABLE cars."""
    candidates = (
        Car.objects.filter(status=Car.Status.AVAILABLE)
        .exclude(pk=car.pk)
        .select_related('seller')
        .order_by('-created_at')
    )

    if not candidates.exists():
        return []

    candidates = list(candidates)
    texts = [_feature_text(car)] + [_feature_text(c) for c in candidates]

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(texts)

    scores = cosine_similarity(matrix[0:1], matrix[1:])[0]

    order = np.argsort(-scores)
    top_limit = min(limit, len(candidates))

    result = []
    for idx in order[:top_limit]:
        result.append(candidates[idx])
    return result