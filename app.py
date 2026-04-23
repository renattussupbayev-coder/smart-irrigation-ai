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

st.title("🌱 Smart Irrigation AI System (Stable MVP)")

# ----------------------------
# INPUT
# ----------------------------
lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

# ----------------------------
# SESSION STATE (IMPORTANT FIX)
# ----------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Run AI Analysis"):
    st.session_state.run = True


# ----------------------------
# CACHED API (IMPORTANT FIX)
# ----------------------------
@st.cache_data(show_spinner=False)
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

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    if "hourly" not in data:
        raise ValueError("No hourly data returned")

    return data


def build_df(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })


def water_stress_index(df):
    rain = df["rain"].sum()
    temp = df["temp"].mean()
    index = 100 - (rain * 5) + (temp - 20) * 2
    return max(0, min(100, index))


def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m


# ----------------------------
# MAIN LOGIC
# ----------------------------
if st.session_state.run:

    try:
        # LOAD DATA
        data = get_data(lat, lon)
        df = build_df(data)

        st.success("Data loaded successfully")

        # ---------------- MAP ----------------
        st.subheader("📍 Location Map")

        m = create_map(lat, lon)
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

        st.pyplot(fig)
        plt.close(fig)

        # ---------------- KPI ----------------
        st.subheader("💧 Water Savings Estimate")

        saved = len(df[df["rain"] > 0]) * 2.5
        st.metric("Estimated Water Saved (liters)", f"{saved:.1f}")

    except Exception as e:
        st.error(f"Error: {e}")
