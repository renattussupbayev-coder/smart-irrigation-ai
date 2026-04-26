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
st.set_page_config(page_title="Умный полив ИИ", layout="wide")
st.title("🌱 AI Smart Irrigation System")

# ---------------------------------
# СЕЗОН
# ---------------------------------
def seasonal_temp():
    month = datetime.now().month
    if month in [12, 1, 2]:
        return 5
    elif month in [3, 4, 5]:
        return 8
    elif month in [6, 7, 8]:
        return 12
    return 7

rec_temp = seasonal_temp()

# ---------------------------------
# INPUT
# ---------------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Широта", value=43.2389)
    lon = st.number_input("Долгота", value=76.8897)

    plant = st.selectbox("Тип растения", ["Газон", "Овощи", "Деревья"])

with col2:
    min_temp = st.number_input("Мин. температура", value=float(rec_temp))
    st.metric("Рекомендовано", f"{rec_temp} °C")

    banned_hours = st.multiselect(
        "Запрещённые часы",
        options=list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

coef = {"Газон": 1.0, "Овощи": 1.3, "Деревья": 1.6}[plant]

# ---------------------------------
# API
# ---------------------------------
OPENWEATHER_API_KEY = ""

@st.cache_data(show_spinner=False)
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7&forecast_days=7&timezone=auto"
    )
    return requests.get(url).json()

def openweather(lat, lon, key):
    if not key:
        return None

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={key}&units=metric"
    )
    return requests.get(url).json()

# ---------------------------------
# DF
# ---------------------------------
def df_meteo(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

def df_owm(data):
    if not data:
        return None

    return pd.DataFrame({
        "time": pd.to_datetime([x["dt_txt"] for x in data["list"]]),
        "rain2": [x.get("rain", {}).get("3h", 0) for x in data["list"]],
        "temp2": [x["main"]["temp"] for x in data["list"]]
    })

# ---------------------------------
# FUSION (FIXED)
# ---------------------------------
def fusion(df1, df2):
    df1 = df1.sort_values("time").copy()

    if df2 is None:
        return df1

    df2 = df2.sort_values("time").copy()

    df = pd.merge_asof(df1, df2, on="time")

    # нормализация колонок (КЛЮЧЕВОЙ FIX)
    df["rain"] = df["rain"].fillna(0) + df.get("rain2", 0).fillna(0)
    df["temp"] = df["temp"].fillna(df["temp"])

    if "temp2" in df:
        df["temp"] = df["temp"] * 0.65 + df["temp2"].fillna(df["temp"]) * 0.35

    return df

# ---------------------------------
# 🌧 SOIL MOISTURE (FIXED STABLE)
# ---------------------------------
def soil_moisture(df, decay=0.88):
    rain_series = df["rain"].fillna(0).astype(float).tail(48).values

    moisture = 0.0
    weight = 1.0

    for r in reversed(rain_series):
        moisture += r * weight
        weight *= decay

    return moisture

# ---------------------------------
# STRESS (FIXED)
# ---------------------------------
def stress(df):
    rain = soil_moisture(df)
    temp = df["temp"].mean()

    return max(0, min(100,
        100
        - rain * 12
        + (temp - 20) * 1.5
    ))

# ---------------------------------
# VOLUME
# ---------------------------------
def volume(temp, stress, coef):
    base = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(base * coef, 1))

# ---------------------------------
# RECOMMENDATION
# ---------------------------------
def recommend(df, min_temp, banned, stress_val, coef):
    plan = []
    daily = {}

    for i in range(len(df) - 12):
        t = df.loc[i, "time"]
        day = t.date()

        if t.hour in banned:
            continue

        if 9 <= t.hour <= 18:
            continue

        if daily.get(day, 0) >= 2:
            continue

        temp = df.loc[i, "temp"]

        if temp < min_temp:
            continue

        # 🌧 защита после дождя (локальная влажность)
        recent_rain = df.loc[max(0, i-6):i, "rain"].sum()
        if recent_rain > 2:
            continue

        liters = volume(temp, stress_val, coef)

        if plan and plan[-1]["time"].date() == day:
            plan[-1]["liters"] += liters
        else:
            plan.append({"time": t, "liters": liters})
            daily[day] = daily.get(day, 0) + 1

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
if st.button("Запустить анализ"):

    df1 = df_meteo(openmeteo(lat, lon))
    df2 = df_owm(openweather(lat, lon, OPENWEATHER_API_KEY))
    df = fusion(df1, df2)

    s = stress(df)
    plan = recommend(df, min_temp, banned_hours, s, coef)

    st.subheader("🧠 Индекс засухи")
    st.metric("Уровень", f"{s:.1f}")

    st.subheader("📊 График")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["time"], df["rain"], label="Rain")
    ax.plot(df["time"], df["temp"], label="Temp")

    # ---------------------------------
    # WATER LINES (THICKNESS = VOLUME)
    # ---------------------------------
    if plan:
        min_l = min(p["liters"] for p in plan)
        max_l = max(p["liters"] for p in plan)

        def w(l):
            if max_l == min_l:
                return 2
            return 1 + (l - min_l) / (max_l - min_l) * 6

        for p in plan:
            ax.axvline(
                p["time"],
                linestyle="--",
                linewidth=w(p["liters"]),
                alpha=0.85,
                color="blue"
            )

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("💧 План полива")
    if plan:
        for p in plan:
            st.write(f"{p['time'].strftime('%d.%m %H:%M')} → {p['liters']} л/м²")
    else:
        st.warning("Полив не требуется")

    st.subheader("📍 Карта")
    st_folium(map_view(lat, lon), width=700, height=400)
