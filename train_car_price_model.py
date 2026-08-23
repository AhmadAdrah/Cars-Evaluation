"""
Train a complete used-car price prediction pipeline.

Produces `model/best_used_car_price_xgb.xgb` as a joblib-saved sklearn
Pipeline containing the feature preprocessor (OneHotEncoder) and the
XGBRegressor. The preprocessor is embedded so prediction only needs the
raw car attributes (same 10 columns used in training).

The training logic lives in `apps/cars/services/model_training_service.py`
and is also exposed as a management command:
    python manage.py retrain_price_model

Usage:
    python train_car_price_model.py
"""
from apps.cars.services.model_training_service import train_and_save_model


def main() -> None:
    metrics = train_and_save_model()
    print('MAE :', metrics['mae'])
    print('R2  :', metrics['r2'])
    print('rows:', metrics['rows'], '| encoded features:', metrics['encoded_features'])
    print('target transform:', metrics['target_transform'])
    print('Model saved to:', metrics['model_path'])


if __name__ == '__main__':
    main()
