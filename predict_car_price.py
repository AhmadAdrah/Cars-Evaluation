import json
from pathlib import Path

import requests


URL = 'http://127.0.0.1:8000/api/cars/predict-price/'

payload = {
    "brand": "Toyota",
    "model_year": 2020,
    "fuel_type": "Gasoline",
    "transmission": "Automatic",
    "ext_col": "White",
    "accident": "Clean",
    "Country_of_Origin": "Japan",
    "Engine_CC": 2500,
    "Mileage_KM": 50000,
    "base_model": "Camry",
    "target_transformation": "Direct Price_USD",
}

response = requests.post(URL, json=payload, timeout=30)
print('Status:', response.status_code)
print(response.json())
