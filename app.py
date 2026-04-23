import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

st.title("🌱 Smart Irrigation AI System (Water Efficiency MVP)")

# ----------------------------
# INPUTS
# ----------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Latitude", value=43.2389)
    lon = st.number_input("Longitude", value=76.8897)

with col2:
    min_temp = st.number_input("Minimum temperature (°C)", value=15.0)
    max_current_rain = st.number_input("Maximum current rain (mm)", value=0.2)
    max_future_rain = st.number_input("Maximum rain next 12h (mm)", value=2.0)
    irrigation_hours = st.multiselect(
        "Allowed irrigation hours",
        options=list(range(24)),
        default=[4, 5, 6, 7]
    )

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


def calculate_water_volume(temp, stress):
    volume = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(volume, 1))


def recommend_irrigation(df, min_temp, max_current_rain, max_future_rain, irrigation_hours, stress):
    recommendations = []

    for i in range(len(df) - 12):
        current_time = df.loc[i, "time"]
        current_rain = df.loc[i, "rain"]
        current_temp = df.loc[i, "temp"]
        future_rain = df.loc[i:i+12, "rain"].sum()

        if current_time.hour in irrigation_hours:
            if (
                current_rain <= max_current_rain
                and future_rain <= max_future_rain
                and current_temp >= min_temp
            ):
                liters = calculate_water_volume(current_temp, stress)

                recommendations.append({
                    "time": current_time,
                    "liters": liters
                })

    return recommendations


def calculate_water_savings(schedule, days=14):
    traditional_daily = 10.0  # L/m²/day
    traditional_total = traditional_daily * days

    ai_total = sum(item["liters"] for item in schedule)

    saved = traditional_total - ai_total
    percent = (saved / traditional_total) * 100 if traditional_total > 0 else 0

    return round(saved, 1), round(percent, 1)


def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m


if st.session_state.run:

    try:
        data = get_data(lat, lon)
        df = build_df(data)

        stress = water_stress_index(df)

        schedule = recommend_irrigation(
            df,
            min_temp,
            max_current_rain,
            max_future_rain,
            irrigation_hours,
            stress
        )

        saved_liters, saved_percent = calculate_water_savings(schedule)

        # MAP
        st.subheader("📍 Location Map")
        m = create_map(lat, lon)
        st_folium(m, width=700, height=400, key="map")

        # STRESS
        st.subheader("🧠 Water Stress Index")
        st.metric("Stress Level", f"{stress:.1f}")

        # GRAPH
        st.subheader("📊 Weather & Irrigation Schedule")

        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df["time"], df["rain"], label="Rain (mm)")
        ax.plot(df["time"], df["temp"], label="Temperature (°C)")

        for item in schedule:
            ax.axvline(x=item["time"], linestyle="--", linewidth=2, alpha=0.8)

        ax.legend()
        plt.xticks(rotation=45)

        st.pyplot(fig)
        plt.close(fig)

        # RECOMMENDATIONS
        st.subheader("💧 Recommended Irrigation Volume")

        if schedule:
            for item in schedule[:10]:
                st.write(
                    f"💧 {item['time'].strftime('%d %b %Y %H:%M')} → {item['liters']} L/m²"
                )
        else:
            st.warning("No irrigation recommended")

        # WATER SAVINGS
        st.subheader("🌍 Estimated Water Savings")
        st.metric("Water Saved", f"{saved_liters} L/m²")
        st.metric("Savings", f"{saved_percent}%")

    except Exception as e:
        st.error(f"Error: {e}")
