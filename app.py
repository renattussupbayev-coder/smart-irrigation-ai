import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

st.title("🌱 Smart Irrigation AI System (Plant-Based MVP)")

# ----------------------------
# INPUTS
# ----------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Latitude", value=43.2389)
    lon = st.number_input("Longitude", value=76.8897)

    plant_type = st.selectbox(
        "Plant Type",
        ["Grass", "Vegetables", "Trees", "Greenhouse crops"]
    )

with col2:
    min_temp = st.number_input("Min temperature (°C)", value=15.0)
    max_rain = st.number_input("Max rain (mm)", value=0.2)
    irrigation_hours = st.multiselect(
        "Allowed irrigation hours",
        options=list(range(24)),
        default=[4, 5, 6, 7]
    )

# ----------------------------
# PLANT PROFILES
# ----------------------------
plant_profiles = {
    "Grass": {"coef": 1.0, "img": "https://upload.wikimedia.org/wikipedia/commons/4/4f/Grass_closeup.jpg"},
    "Vegetables": {"coef": 1.3, "img": "https://upload.wikimedia.org/wikipedia/commons/6/6f/Vegetable_garden.jpg"},
    "Trees": {"coef": 1.6, "img": "https://upload.wikimedia.org/wikipedia/commons/3/3a/Oak_tree.jpg"},
    "Greenhouse crops": {"coef": 1.8, "img": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Greenhouse_tomatoes.jpg"}
}

profile = plant_profiles[plant_type]

st.image(profile["img"], caption=plant_type, use_container_width=True)

# ----------------------------
# STATE
# ----------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Run AI Analysis"):
    st.session_state.run = True

# ----------------------------
# API
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
    return r.json()


def build_df(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })


def stress_index(df):
    rain = df["rain"].sum()
    temp = df["temp"].mean()
    return max(0, min(100, 100 - rain * 5 + (temp - 20) * 2))


def irrigation_volume(temp, stress, coef):
    base = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(base * coef, 1))


def recommend(df, temp_min, rain_max, hours, stress, coef):
    res = []

    for i in range(len(df) - 12):
        t = df.loc[i, "time"]
        rain = df.loc[i, "rain"]
        temp = df.loc[i, "temp"]
        future_rain = df.loc[i:i+12, "rain"].sum()

        if t.hour in hours:
            if rain <= rain_max and temp >= temp_min and future_rain < 2:
                vol = irrigation_volume(temp, stress, coef)

                res.append({
                    "time": t,
                    "liters": vol
                })

    return res


def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon]).add_to(m)
    return m


# ----------------------------
# RUN
# ----------------------------
if st.session_state.run:

    data = get_data(lat, lon)
    df = build_df(data)

    stress = stress_index(df)

    schedule = recommend(
        df,
        min_temp,
        max_rain,
        irrigation_hours,
        stress,
        profile["coef"]
    )

    # MAP
    st.subheader("📍 Location Map")
    st_folium(create_map(lat, lon), width=700, height=400, key="map")

    # STRESS
    st.subheader("🧠 Water Stress Index")
    st.metric("Stress", f"{stress:.1f}")

    # GRAPH
    st.subheader("📊 Weather & Irrigation Plan")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["time"], df["rain"], label="Rain")
    ax.plot(df["time"], df["temp"], label="Temp")

    for s in schedule:
        ax.axvline(s["time"], linestyle="--", alpha=0.7)

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    # IRRIGATION
    st.subheader("💧 Irrigation Plan")

    if schedule:
        for s in schedule:
            st.write(f"🌱 {s['time'].strftime('%d %b %H:%M')} → {s['liters']} L/m²")
    else:
        st.warning("No irrigation needed")

    # PLANT INFO
    st.subheader("🌿 Plant Profile")
    st.write(f"Coefficient: {profile['coef']}")
