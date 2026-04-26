import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

# ---------------------------------
# UI
# ---------------------------------
st.set_page_config(page_title="Smart Irrigation", layout="wide")
st.title("🌱 Smart Irrigation AI (stable version)")

# ---------------------------------
# SEASON TEMP
# ---------------------------------
def seasonal_temp():
    m = datetime.now().month
    if m in [12, 1, 2]:
        return 5
    if m in [3, 4, 5]:
        return 8
    if m in [6, 7, 8]:
        return 12
    return 7

rec_temp = seasonal_temp()

# ---------------------------------
# INPUT
# ---------------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Latitude", value=43.2389)
    lon = st.number_input("Longitude", value=76.8897)

    plant = st.selectbox("Plant type", ["Grass", "Vegetables", "Trees"])

with col2:
    min_temp = st.number_input("Min temp", value=float(rec_temp))
    st.metric("Recommended", f"{rec_temp} °C")

    banned = st.multiselect(
        "Blocked hours",
        list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

coef = {"Grass":1.0, "Vegetables":1.3, "Trees":1.6}[plant]

# ---------------------------------
# API
# ---------------------------------
@st.cache_data
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=3&forecast_days=3&timezone=auto"
    )
    return requests.get(url).json()

# ---------------------------------
# DATAFRAME (SAFE)
# ---------------------------------
def build_df(data):
    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

    df = df.fillna(0)
    return df

# ---------------------------------
# SOIL MOISTURE (FIXED)
# ---------------------------------
def soil_moisture(df):
    rain = df["rain"].tail(24).values

    moisture = 0
    weight = 1

    for r in reversed(rain):
        moisture += r * weight
        weight *= 0.85

    return moisture

# ---------------------------------
# STRESS
# ---------------------------------
def stress(df):
    rain = soil_moisture(df)
    temp = df["temp"].mean()

    return max(0, min(100,
        100 - rain * 15 + (temp - 20) * 1.2
    ))

# ---------------------------------
# WATER VOLUME
# ---------------------------------
def volume(temp, stress, coef):
    base = 4 + stress * 0.12 + (temp - 20) * 0.2
    return max(1, round(base * coef, 1))

# ---------------------------------
# RECOMMENDATION (SAFE INDEXING)
# ---------------------------------
def recommend(df, min_temp, banned, stress_val, coef):
    plan = []
    last_day = None
    daily_count = {}

    for i in range(len(df)):
        row = df.iloc[i]
        t = row["time"]

        if t.hour in banned:
            continue

        if 9 <= t.hour <= 18:
            continue

        day = t.date()
        if daily_count.get(day, 0) >= 2:
            continue

        if row["temp"] < min_temp:
            continue

        # 🌧 soil protection
        if i >= 3:
            recent_rain = df.iloc[i-3:i]["rain"].sum()
            if recent_rain > 2:
                continue

        liters = volume(row["temp"], stress_val, coef)

        if last_day == day:
            plan[-1]["liters"] += liters
        else:
            plan.append({"time": t, "liters": liters})
            last_day = day
            daily_count[day] = daily_count.get(day, 0) + 1

    return plan

# ---------------------------------
# MAP
# ---------------------------------
def map_view(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon]).add_to(m)
    return m

# ---------------------------------
# RUN
# ---------------------------------
if st.button("Run AI"):

    df = build_df(openmeteo(lat, lon))

    s = stress(df)
    plan = recommend(df, min_temp, banned, s, coef)

    st.subheader("🧠 Stress level")
    st.metric("Index", f"{s:.1f}")

    st.subheader("📊 Chart")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["time"], df["rain"], label="Rain")
    ax.plot(df["time"], df["temp"], label="Temp")

    if plan:
        min_l = min(p["liters"] for p in plan)
        max_l = max(p["liters"] for p in plan)

        def w(x):
            return 1 if max_l == min_l else 1 + (x-min_l)/(max_l-min_l)*5

        for p in plan:
            ax.axvline(
                p["time"],
                linestyle="--",
                linewidth=w(p["liters"]),
                alpha=0.8,
                color="blue"
            )

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("💧 Plan")
    if plan:
        for p in plan:
            st.write(f"{p['time']} → {p['liters']} L/m²")
    else:
        st.warning("No irrigation needed")

    st.subheader("📍 Map")
    st_folium(map_view(lat, lon), width=700, height=400)
