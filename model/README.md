# Model Info: Best Used Car Price XGBoost

## الملف
- الاسم: `best_used_car_price_xgb.xgb`
- المسار: `model/best_used_car_price_xgb.xgb`
- النوع: XGBoost Regressor
- الغرض: تقدير سعر السيارة المستعملة بالدولار الأمريكي

## وصف النموذج
هذا النموذج يستخدم للتنبؤ بسعر السيارة المستخدمة بناءً على خصائص السيارة الأساسية. يتم استخدامه عادةً لتقدير سعر السيارة قبل البيع أو بعد إدراجها في النظام.

## الميزات المدربة عليها
بناءً على مثال الاستخدام الموجود في الملف `example.py`، فإن النماذج تم تدريبها على ميزات مثل:

- brand
- model_year
- fuel_type
- transmission
- ext_col
- accident
- Country_of_Origin
- Engine_CC
- Mileage_KM
- base_model

ملاحظة مهمة:
- في قاعدة البيانات، اسم الحقل يكون غالبًا بصيغة أحرف صغيرة مثل `country_of_origin` و`engine_cc` و`mileage_km`.
- في مثال التوقع، تم استخدام أسماء أعمدة بصيغة `Country_of_Origin` و`Engine_CC` و`Mileage_KM`، وهذا يشير إلى أن النموذج تم تدريبُه على ترتيب/أسماء محددة للميزات.
- لذلك يجب التأكد من ترتيب الأعمدة وتطابقها تمامًا مع ما تم تدريبه عليه.

## شكل البيانات المتوقع
مثال مدخل:

```python
new_car_data = {
    "brand": "Toyota",
    "model_year": 2020,
    "fuel_type": "Gasoline",
    "transmission": "Automatic",
    "ext_col": "White",
    "accident": "Clean",
    "Country_of_Origin": "Japan",
    "Engine_CC": 2500,
    "Mileage_KM": 50000,
    "base_model": "Camry"
}
```

## طريقة الاستخدام
```python
import pandas as pd
import numpy as np
import xgboost as xgb

model = xgb.XGBRegressor()
model.load_model("model/best_used_car_price_xgb.xgb")

new_car_data = {
    "brand": "Toyota",
    "model_year": 2020,
    "fuel_type": "Gasoline",
    "transmission": "Automatic",
    "ext_col": "White",
    "accident": "Clean",
    "Country_of_Origin": "Japan",
    "Engine_CC": 2500,
    "Mileage_KM": 50000,
    "base_model": "Camry"
}

new_car_df = pd.DataFrame([new_car_data])

# تأكد من ترتيب الأعمدة مطابقًا لاستخدام التدريب
# new_car_df = new_car_df[X_train.columns]

# إذا كان النموذج تم تدريبه على السعر المباشر
predicted_price = model.predict(new_car_df)[0]

# إذا كان النموذج تم تدريبه على log1p(Price_USD)
# predicted_price_log = model.predict(new_car_df)[0]
# predicted_price = np.expm1(predicted_price_log)

print(f"Predicted Price: ${predicted_price:,.2f}")
```

## ملاحظة حول target transformation
في ملف `example.py` يوجد هذا الشرط:

```python
if best_target_transformation == "Direct Price_USD":
    predicted_price = best_model.predict(new_car_df)[0]
else:
    predicted_price_log = best_model.predict(new_car_df)[0]
    predicted_price = np.expm1(predicted_price_log)
```

هذا يعني أن النموذج قد تم تدريبه إما:
- على السعر المباشر: `Direct Price_USD`
- أو على `log1p(Price_USD)` ثم تحويله مرة أخرى باستخدام `expm1`

## ملاحظات مهمة
1. يجب حفظ أسماء الأعمدة بالضبط كما تم تدريب النموذج عليها.
2. يجب أن تكون القيم من نفس الأنواع (على سبيل المثال `model_year` عدد صحيح، `Mileage_KM` عدد صحيح).
3. في حال وجود اختلاف في أسماء الأعمدة، يجب إعادة ترتيب المصفوفة أو إعادة تدريب النموذج.
4. هذا النموذج يعتمد على بيانات سوق السيارات المستعملة، وبالتالي تكون التقديرات دقيقة بحسب جودة البيانات المستخدمة في التدريب.

## حالة الاستخدام داخل المشروع
يمكن استخدام هذا النموذج في تطبيق Django عند حساب `estimated_price_usd` لسيارة جديدة أو في شاشة التقدير قبل حفظ السيارة.
