import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

st.title("🌱 Smart Irrigation AI System (MVP)")

# ----------------------------
# INPUT
# ----------------------------
lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

# ----------------------------
# API FUNCTION
# ----------------------------
def get_data(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7"
        "&forecast_days=7"
        "&timezone=auto"
    )

    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    if "hourly" not in data:
        st.error("No hourly data returned from API")
        st.stop()

    return data

# ----------------------------
# DATAFRAME
# ----------------------------
def build_df(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

# ----------------------------
# IRRIGATION LOGIC (simple AI index)
# ----------------------------
def water_stress_index(df):
    rain = df["rain"].sum()
    temp = df["temp"].mean()

    index = 100 - (rain * 5) + (temp - 20) * 2
    return max(0, min(100, index))

# ----------------------------
# MAP FUNCTION
# ----------------------------
def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m

# ----------------------------
# RUN BUTTON
# ----------------------------
if st.button("Run AI Analysis"):

    try:
        # LOAD DATA
        data = get_data(lat, lon)
        df = build_df(data)

        st.success("Data loaded successfully")

        # ---------------- MAP ----------------
        st.subheader("📍 Location Map")

        m = create_map(lat, lon)

        map_container = st.empty()
        with map_container:
            st_folium(m, width=700, height=400, key="map")

        # ---------------- AI INDEX ----------------
        st.subheader("🧠 Water Stress Index")

        stress = water_stress_index(df)
        st.metric("Stress Level (0–100)", f"{stress:.1f}")

        if stress > 70:
            st.error("High irrigation need")
        elif stress > 40:
            st.warning("Moderate irrigation need")
        else:
            st.success("Low irrigation need")

        # ---------------- GRAPH ----------------
        st.subheader("📊 Rain & Temperature")

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df["time"], df["rain"], label="Rain (mm)")
        ax.plot(df["time"], df["temp"], label="Temperature (°C)")

        ax.legend()
        plt.xticks(rotation=45)

        st.pyplot(fig)
        plt.close(fig)

        # ---------------- KPI ----------------
        st.subheader("💧 Water Insight")

        saved = len(df[df["rain"] > 0]) * 2.5
        st.metric("Estimated Water Saved (liters)", f"{saved:.1f}")

    except Exception as e:
        st.error(f"Error: {e}")
