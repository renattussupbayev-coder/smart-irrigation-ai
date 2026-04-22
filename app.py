
import streamlit as st
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Smart Irrigation AI MVP", layout="wide")

st.title("🌱 Smart Irrigation AI System (V2 Prototype)")

# ------------------------
# INPUT
# ------------------------
lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

# ------------------------
# OPEN-METEO API
# ------------------------
def get_data(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&daily=precipitation_sum"
        "&past_days=7"
        "&forecast_days=7"
        "&timezone=auto"
    )
    return requests.get(url).json()

# ------------------------
# DATAFRAME
# ------------------------
def build_df(data):
    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })
    return df

# ------------------------
# AI INDEX (MOISTURE STRESS)
# ------------------------
def water_stress_index(df):
    rain = df["rain"].sum()
    temp = df["temp"].mean()

    index = 100 - (rain * 5) + (temp - 20) * 2

    return max(0, min(100, index))

# ------------------------
# IRRIGATION LOGIC
# ------------------------
def irrigation_schedule(df):
    schedule = []

    for i in range(len(df)):
        if df.loc[i, "rain"] == 0 and df.loc[i, "time"].hour in [5, 6, 7]:
            schedule.append(df.loc[i, "time"])

    return schedule

# ------------------------
# WATER SAVING MODEL
# ------------------------
def water_saved(df):
    no_irrigation_hours = len(df[df["rain"] > 0])
    return no_irrigation_hours * 2.5  # liters estimate

# ------------------------
# MAP
# ------------------------
def show_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m

# ------------------------
# RUN
# ------------------------
if st.button("Run AI Analysis"):

    data = get_data(lat, lon)
    df = build_df(data)

    # AI outputs
    stress = water_stress_index(df)
    schedule = irrigation_schedule(df)
    saved = water_saved(df)

    # ---------------- MAP ----------------
    st.subheader("📍 Location Map")
    map_obj = show_map(lat, lon)
    st_data = st_folium(map_obj, width=700, height=400)

    # ---------------- INDEX ----------------
    st.subheader("🧠 Water Stress Index (AI)")
    st.metric(label="Stress Level (0–100)", value=f"{stress:.1f}")

    if stress > 70:
        st.error("High irrigation need")
    elif stress > 40:
        st.warning("Moderate need")
    else:
        st.success("Low irrigation need")

    # ---------------- GRAPH ----------------
    st.subheader("📊 Precipitation & Temperature")

    fig, ax = plt.subplots()

    ax.plot(df["time"], df["rain"], label="Rain (mm)")
    ax.plot(df["time"], df["temp"], label="Temperature (°C)")

    ax.legend()
    plt.xticks(rotation=45)

    st.pyplot(fig)

    # ---------------- SCHEDULE ----------------
    st.subheader("💧 Recommended Irrigation Times")

    if schedule:
        for t in schedule:
            st.write("🌱", t)
    else:
        st.write("No irrigation needed")

    # ---------------- WATER SAVED ----------------
    st.subheader("💦 Water Efficiency")

    st.metric("Estimated Water Saved (liters)", f"{saved:.1f}")
