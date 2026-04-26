import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# ---------------------------------
# PAGE
# ---------------------------------
st.set_page_config(page_title="Умный полив ИИ (ML)", layout="wide")
st.title("🌱 AI Irrigation System (ML version)")

# ---------------------------------
# SEASON TEMP
# ---------------------------------
def seasonal_temp():
    month = datetime.now().month
    if month in [12, 1, 2]:
        return 5
    elif month in [3, 4, 5]:
        return 8
    elif month in [6, 7, 8]:
        return 12
    else:
        return 7

rec_temp = seasonal_temp()

# ---------------------------------
# INPUTS
# ---------------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Широта", value=43.2389)
    lon = st.number_input("Долгота", value=76.8897)

    plant = st.selectbox("Тип растения", ["Газон", "Овощи", "Деревья"])

with col2:
    min_temp = st.number_input("Мин. температура", value=float(rec_temp))
    banned_hours = st.multiselect(
        "Запрещённые часы",
        options=list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

# plant coefficients
plant_coef = {"Газон":1.0, "Овощи":1.3, "Деревья":1.6}
coef = plant_coef[plant]

# ---------------------------------
# API
# ---------------------------------
@st.cache_data
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7&forecast_days=7&timezone=auto"
    )
    return requests.get(url).json()

# ---------------------------------
# DF
# ---------------------------------
def build_df(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

# ---------------------------------
# FEATURE ENGINEERING
# ---------------------------------
def features(df, coef):
    df = df.copy()
    df["hour"] = df["time"].dt.hour
    df["month"] = df["time"].dt.month
    df["is_night"] = ((df["hour"] < 6) | (df["hour"] > 20)).astype(int)
    df["coef"] = coef

    # rolling rain (important!)
    df["rain_6h"] = df["rain"].rolling(6).sum().fillna(0)
    df["rain_24h"] = df["rain"].rolling(24).sum().fillna(0)

    return df

# ---------------------------------
# SYNTHETIC LABELS (BOOTSTRAP TRAINING)
# ---------------------------------
def make_labels(df):
    stress = (
        100
        - df["rain_24h"] * 4
        + (df["temp"] - 20) * 2
    )

    stress = stress.clip(0, 100)

    liters = (5 + stress * 0.1) * df["coef"]

    df["target"] = liters
    df["stress"] = stress

    return df

# ---------------------------------
# TRAIN MODEL
# ---------------------------------
def train_model(df):
    features_cols = [
        "temp", "rain", "rain_6h", "rain_24h",
        "hour", "month", "is_night", "coef"
    ]

    X = df[features_cols]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        random_state=42
    )

    model.fit(X_train, y_train)

    return model

# ---------------------------------
# AI PREDICT
# ---------------------------------
def predict(df, model):
    cols = [
        "temp", "rain", "rain_6h", "rain_24h",
        "hour", "month", "is_night", "coef"
    ]

    df["predicted_liters"] = model.predict(df[cols])

    return df

# ---------------------------------
# MAP
# ---------------------------------
def map_view(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon]).add_to(m)
    return m

# ---------------------------------
# RUN
# ---------------------------------
if st.button("🚀 Запустить AI модель"):

    raw = openmeteo(lat, lon)
    df = build_df(raw)

    df = features(df, coef)
    df = make_labels(df)

    model = train_model(df)
    df = predict(df, model)

    # filter irrigation
    plan = df[
        (df["predicted_liters"] > 2.5) &
        (~df["hour"].isin(banned_hours)) &
        (df["temp"] >= min_temp)
    ]

    # ---------------- MAP
    st.subheader("📍 Карта")
    st_folium(map_view(lat, lon), width=700, height=400)

    # ---------------- CHART
    st.subheader("📊 AI прогноз")

    fig, ax = plt.subplots(figsize=(14,6))
    ax.plot(df["time"], df["temp"], label="Temp")
    ax.plot(df["time"], df["rain"], label="Rain")
    ax.plot(df["time"], df["predicted_liters"], label="AI water need")

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    # ---------------- PLAN
    st.subheader("💧 AI план полива")

    if len(plan) == 0:
        st.warning("Полив не требуется")
    else:
        for _, row in plan.iterrows():
            st.write(
                f"{row['time'].strftime('%d.%m %H:%M')} → "
                f"{round(row['predicted_liters'],1)} л/м²"
            )
