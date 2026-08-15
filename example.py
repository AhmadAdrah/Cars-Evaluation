print("--- Example Prediction ---")

new_car_data = {
    "brand": "Toyota",
    "model_year": 2020,
    "fuel_type": "Gasoline",#/Plug-In Hybrid/Hybrid/Diesel
    "transmission": "Automatic", #/Manual
    "ext_col": "White",
    "accident": "Clean", #/Accident Reported
    "Country_of_Origin": "Japan",
    "Engine_CC": 2500,
    "Mileage_KM": 50000,
    "base_model": "Camry"
}

new_car_df = pd.DataFrame([new_car_data])

# Ensure the new car DataFrame has the same column order as X_train
new_car_df = new_car_df[X_train.columns]

# Predict the price using the best model
if best_target_transformation == "Direct Price_USD":
    predicted_price = best_model.predict(new_car_df)[0]
else: # Log1p(Price_USD)
    predicted_price_log = best_model.predict(new_car_df)[0]
    predicted_price = np.expm1(predicted_price_log)

print(f"Predicted Price for the new car: ${predicted_price:,.2f}")