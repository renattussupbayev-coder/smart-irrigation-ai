import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from sklearn.ensemble import RandomForestRegressor

# ---------------------------------
# PAGE
# ---------------------------------
st.set_page_config(page_title="AI Irrigation System", layout="wide")
st.title("🌱 Smart Irrigation AI (Stable Version)")

# ---------------------------------
# INPUTS
# ---------------------------------
lat = st.number_input("Широта", value=43.2389)
lon = st.number_input("Долгота", value=76.8897)

# ---------------------------------
# API
# ---------------------------------
@st.cache_data
def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=2&forecast_days=2&timezone=auto"
    )
    r = requests.get(url, timeout=10)
    return r.json()

# ---------------------------------
# DATA
# ---------------------------------
def build_df(data):
    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

    df = df.fillna(0)
    df = df.reset_index(drop=True)

    return df

# ---------------------------------
# FEATURES
# ---------------------------------
def make_features(df):
    df = df.copy()

    df["hour"] = df["time"].dt.hour

    # safe rolling (IMPORTANT FIX)
    df["rain_3h"] = df["rain"].rolling(3, min_periods=1).sum()
    df["rain_6h"] = df["rain"].rolling(6, min_periods=1).sum()

    return df

# ---------------------------------
# TARGET (synthetic irrigation need)
# ---------------------------------
def make_target(df):
    stress = (
        100
        - df["rain_6h"] * 4
        + (df["temp"] - 20) * 2
    )

    stress = stress.clip(0, 100)

    df["target"] = 5 + stress * 0.1

    return df

# ---------------------------------
# TRAIN MODEL
# ---------------------------------
def train_model(df):
    features = ["temp", "rain", "rain_3h", "rain_6h", "hour"]

    df = df.dropna()

    X = df[features]
    y = df["target"]

    if len(df) < 10:
        st.error("❌ Not enough data for training")
        return None

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        random_state=42
    )

    model.fit(X, y)

    return model

# ---------------------------------
# PREDICT
# ---------------------------------
def predict(df, model):
    features = ["temp", "rain", "rain_3h", "rain_6h", "hour"]
    df["pred"] = model.predict(df[features])
    return df

# ---------------------------------
# DECISION ENGINE
# ---------------------------------
def irrigation_decision(df):
    threshold = df["pred"].quantile(0.75)

    df["irrigate"] = df["pred"] > threshold

    return df, threshold

# ---------------------------------
# RUN
# ---------------------------------
if st.button("🚀 Run AI Irrigation"):

    try:
        data = get_weather(lat, lon)
        df = build_df(data)

        df = make_features(df)
        df = make_target(df)

        model = train_model(df)

        if model is None:
            st.stop()

        df = predict(df, model)

        df, threshold = irrigation_decision(df)

        # ---------------------------------
        # RESULTS
        # ---------------------------------

        st.subheader("📊 Prediction")

        fig, ax = plt.subplots(figsize=(12,5))
        ax.plot(df["time"], df["temp"], label="Temp")
        ax.plot(df["time"], df["rain"], label="Rain")
        ax.plot(df["time"], df["pred"], label="Water need (AI)")

        ax.legend()
        st.pyplot(fig)
        plt.close(fig)

        # ---------------------------------
        # DECISION
        # ---------------------------------

        st.subheader("💧 Irrigation Plan")

        st.info(f"Threshold: {round(threshold,2)}")

        plan = df[df["irrigate"]]

        if len(plan) == 0:
            st.success("✅ No irrigation needed")
        else:
            for _, row in plan.iterrows():
                st.write(
                    f"{row['time']} → "
                    f"{round(row['pred'],1)} units water"
                )

        # ---------------------------------
        # DEBUG TABLE
        # ---------------------------------
        st.subheader("📋 Data")
        st.dataframe(df[["time","temp","rain","pred","irrigate"]])

    except Exception as e:
        st.error(f"System error: {e}")
