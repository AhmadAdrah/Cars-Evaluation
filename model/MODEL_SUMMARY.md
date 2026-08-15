# Model Summary — Best Used Car Price XGBoost

## الملف
- **الاسم**: `best_used_car_price_xgb.xgb`
- **المسار**: `model/best_used_car_price_xgb.xgb`
- **النوع**: `sklearn.Pipeline` (محفوظ عبر `joblib`)

## البنية

| العنصر | القيمة |
|---|---|
| الخطوة الأولى | `preprocessor_xgb` — `ColumnTransformer` + `OneHotEncoder` |
| الخطوة الثانية | `regressor` — `XGBRegressor` |
| عدد الأشجار (n_estimators) | 800 |
| العمق الأقصى (max_depth) | 7 |
| معدل التعلم (learning_rate) | 0.05 |
| الأعمدة المشفرة بعد OneHot | **1106** |
| تحويل الهدف | `Log1p(Price_USD)` ثم `expm1` للعودة للسعر |

## بيانات التدريب
- **الملف**: `cleaned_used_cars_v2.csv`
- **عدد الصفوف**: 3449
- **عدد الخصائص المدخلة**: 10

```
brand, model_year, fuel_type, transmission, ext_col, accident,
Country_of_Origin, Engine_CC, Mileage_KM, base_model
```
- **الهدف**: `Price_USD`

## الدقة

### على كامل البيانات
| المقياس | القيمة |
|---|---|
| R² | **0.939** |
| MAE | **$3,155** |
| RMSE | **$5,128** |
| MAPE | **10.5%** |

### على اختبار 80/20 (hold-out)
| المقياس | القيمة |
|---|---|
| MAE | **$5,570** |
| R² | **0.83** |

### توزيع الخطأ (على كامل البيانات)
| النسبة المئوية | الخطأ |
|---|---|
| 25th percentile | $784 |
| 50th percentile (Median) | $1,969 |
| 75th percentile | $4,040 |
| 90th percentile | $6,825 |
| 95th percentile | $9,961 |

## إحصائيات الأسعار الفعلية
| المقياس | القيمة |
|---|---|
| الحد الأدنى | $2,000 |
| الحد الأقصى | $98,000 |
| المتوسط | $32,644 |
| الوسيط | $28,900 |

## ملاحظات
- متوسط الخطأ ~$1,969، و75% من التنبؤات ضمن ±$4,040 من السعر الحقيقي.
- أخطاء كبيرة (أكثر من $10,000) تظهر فقط في ~5% من الحالات، عادةً في السيارات الفاخرة خارج نطاق التدريب.
- النموذج متكامل مع الـ Pipeline، لذا يكفي تمرير الخصائص العشرة الخام مباشرة — المعالجة تتم تلقائياً.

## الاستخدام
```python
import joblib

model = joblib.load('model/best_used_car_price_xgb.xgb')

new_car = {
    'brand': 'Toyota', 'model_year': 2020, 'fuel_type': 'Gasoline',
    'transmission': 'Automatic', 'ext_col': 'White', 'accident': 'Clean',
    'Country_of_Origin': 'Japan', 'Engine_CC': 2500,
    'Mileage_KM': 50000, 'base_model': 'Camry',
}

import pandas as pd
price_log = model.predict(pd.DataFrame([new_car]))[0]
price = __import__('numpy').expm1(price_log)
print(f'Predicted Price: ${price:,.2f}')
```