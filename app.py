import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

st.title("🌱 Smart Irrigation AI System (Predictive MVP)")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Run AI Analysis"):
    st.session_state.run = True


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
    return r.json()


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


def recommend_irrigation(df):
    recommendations = []

    for i in range(len(df) - 12):
        current_time = df.loc[i, "time"]
        current_rain = df.loc[i, "rain"]
        current_temp = df.loc[i, "temp"]

        future_rain = df.loc[i:i+12, "rain"].sum()

        if current_time.hour in [4, 5, 6]:
            if current_rain == 0 and future_rain < 1 and current_temp > 20:
                recommendations.append(current_time)

    return recommendations


def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m


if st.session_state.run:

    try:
        data = get_data(lat, lon)
        df = build_df(data)

        stress = water_stress_index(df)
        schedule = recommend_irrigation(df)

        # MAP
        st.subheader("📍 Location Map")
        m = create_map(lat, lon)
        st_folium(m, width=700, height=400, key="map")

        # STRESS INDEX
        st.subheader("🧠 Water Stress Index")
        st.metric("Stress Level (0–100)", f"{stress:.1f}")

        # GRAPH
        st.subheader("📊 Weather & Irrigation Schedule")

        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(df["time"], df["rain"], label="Rain (mm)")
        ax.plot(df["time"], df["temp"], label="Temperature (°C)")

        # irrigation markers
        for t in schedule:
            ax.axvline(x=t, linestyle="--", alpha=0.7)

        ax.legend()
        plt.xticks(rotation=45)

        st.pyplot(fig)
        plt.close(fig)

        # WATER SAVINGS
        st.subheader("💧 Estimated Water Savings")
        saved = len(df[df["rain"] > 0]) * 2.5
        st.metric("Water Saved (liters)", f"{saved:.1f}")

        # TEXT RECOMMENDATIONS
        st.subheader("🌱 Recommended Irrigation Times")
        if schedule:
            for t in schedule[:10]:
                st.write("💧", t.strftime("%d %b %Y %H:%M"))
        else:
            st.info("No irrigation recommended")

    except Exception as e:
        st.error(f"Error: {e}")
