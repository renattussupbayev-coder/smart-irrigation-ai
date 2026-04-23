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

st.title("🌱 Smart Irrigation AI System (Predictive MVP)")

# ----------------------------
# INPUT
# ----------------------------
lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

# ----------------------------
# SESSION STATE
# ----------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Run AI Analysis"):
    st.session_state.run = True

# ----------------------------
# WEATHER API
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
# WATER STRESS INDEX
# ----------------------------
def water_stress_index(df):
    rain = df["rain"].sum()
    temp = df["temp"].mean()

    index = 100 - (rain * 5) + (temp - 20) * 2
    return max(0, min(100, index))

# ----------------------------
# IRRIGATION RECOMMENDATION
# ----------------------------
def recommend_irrigation(df):
    recommendations = []

    for i in range(len(df) - 12):
        current_time = df.loc[i, "time"]
        current_rain = df.loc[i, "rain"]
        current_temp = df.loc[i, "temp"]

        future_rain = df.loc[i:i+12, "rain"].sum()

        if current_time.hour in [4, 5, 6, 7]:
            if current_rain < 0.2 and future_rain < 2 and current_temp > 15:
                recommendations.append(current_time)

    return recommendations

# ----------------------------
# MAP
# ----------------------------
def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m

# ----------------------------
# MAIN APP
# ----------------------------
if st.session_state.run:

    try:
        data = get_data(lat, lon)
        df = build_df(data)

        stress = water_stress_index(df)
        schedule = recommend_irrigation(df)

        # ---------------- MAP ----------------
        st.subheader("📍 Location Map")
        m = create_map(lat, lon)
        st_folium(m, width=700, height=400, key="map")

        # ---------------- STRESS INDEX ----------------
        st.subheader("🧠 Water Stress Index")
        st.metric("Stress Level (0–100)", f"{stress:.1f}")

        if stress > 70:
            st.error("High irrigation need")
        elif stress > 40:
            st.warning("Moderate irrigation need")
        else:
            st.success("Low irrigation need")

        # ---------------- DEBUG ----------------
        st.write("DEBUG recommendations found:", len(schedule))

        # ---------------- GRAPH ----------------
        st.subheader("📊 Weather & Irrigation Schedule")

        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(df["time"], df["rain"], label="Rain (mm)")
        ax.plot(df["time"], df["temp"], label="Temperature (°C)")

        # irrigation lines
        for t in schedule:
            ax.axvline(x=t, linestyle="--", linewidth=2, alpha=0.8)

        ax.legend()
        plt.xticks(rotation=45)

        st.pyplot(fig)
        plt.close(fig)

        # ---------------- WATER SAVINGS ----------------
        st.subheader("💧 Estimated Water Savings")
        saved = len(df[df["rain"] > 0]) * 2.5
        st.metric("Water Saved (liters)", f"{saved:.1f}")

        # ---------------- RECOMMENDATIONS ----------------
        st.subheader("🌱 Recommended Irrigation Times")

        if len(schedule) > 0:
            for t in schedule[:10]:
                st.write("💧", t.strftime("%d %b %Y %H:%M"))
        else:
            st.warning("No irrigation times found for current forecast")

    except Exception as e:
        st.error(f"Error: {e}")
