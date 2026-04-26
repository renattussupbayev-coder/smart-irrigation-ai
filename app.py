import streamlit as st
import requests
import pandas as pd
from datetime import datetime

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

st.set_page_config(page_title="DEBUG AI IRRIGATION", layout="wide")
st.title("🧪 DEBUG MODE - AI Irrigation")

# -----------------------
# INPUTS
# -----------------------
lat = st.number_input("lat", value=43.2389)
lon = st.number_input("lon", value=76.8897)

st.write("STARTED OK")

# -----------------------
# API TEST
# -----------------------
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=2&forecast_days=2&timezone=auto"
    )
    r = requests.get(url, timeout=10)
    st.write("API status:", r.status_code)
    data = r.json()

    st.write("RAW keys:", data.keys())
    return data

# -----------------------
# BUILD DF
# -----------------------
def build_df(data):
    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

    st.write("DF created:", df.shape)
    st.dataframe(df.head())

    return df

# -----------------------
# FEATURES
# -----------------------
def features(df):
    df["hour"] = df["time"].dt.hour
    df["rain_6h"] = df["rain"].rolling(3, min_periods=1).sum()
    df["rain_24h"] = df["rain"].rolling(6, min_periods=1).sum()
    return df

# -----------------------
# TRAIN SAFE MODEL
# -----------------------
def train(df):
    df = df.dropna()

    st.write("After dropna:", df.shape)

    if len(df) < 10:
        st.error("❌ Too little data for training")
        return None

    df["target"] = df["temp"] * 0.5 + df["rain"] * -2 + 5

    X = df[["temp", "rain", "rain_6h", "rain_24h", "hour"]]
    y = df["target"]

    model = RandomForestRegressor(n_estimators=50)

    model.fit(X, y)

    st.success("✅ Model trained")

    return model

# -----------------------
# RUN
# -----------------------
if st.button("RUN DEBUG AI"):

    try:
        data = openmeteo(lat, lon)
        df = build_df(data)

        df = features(df)

        model = train(df)

        if model is None:
            st.stop()

        df["pred"] = model.predict(df[["temp","rain","rain_6h","rain_24h","hour"]])

        st.write("PREDICTIONS:")
        st.dataframe(df[["time","pred"]].head(20))

    except Exception as e:
        st.error(f"CRASH: {e}")
