import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

# ---------------------------------
# НАСТРОЙКА СТРАНИЦЫ
# ---------------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")
st.title("🌱 Система умного полива (AI SMART IRRIGATION)")

# ---------------------------------
# СЕЗОННАЯ РЕКОМЕНДУЕМАЯ ТЕМПЕРАТУРА
# ---------------------------------
def seasonal_temp():
    month = datetime.now().month

    if month in [12, 1, 2]:
        return 5
    elif month in [3, 4, 5]:
        return 8
    elif month in [6, 7, 8]:
        return 12
    else:
        return 7

рек_темп = seasonal_temp()

# ---------------------------------
# ВХОДНЫЕ ДАННЫЕ
# ---------------------------------
col1, col2 = st.columns(2)

with col1:
    широта = st.number_input("Широта", value=43.21032)
    долгота = st.number_input("Долгота", value=76.96681)

    тип_растения = st.selectbox(
        "Тип растения",
        ["Газон", "Овощи", "Деревья"]
    )

with col2:
    t1, t2 = st.columns([2, 1])

    with t1:
        мин_температура = st.number_input(
            "Мин. температура для полива (°C)",
            value=float(рек_темп)
        )

    with t2:
        st.metric("Рекомендовано", f"{рек_темп} °C")

    запрещенные_часы = st.multiselect(
        "Запрещённые часы полива",
        options=list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

# ---------------------------------
# ПРОФИЛИ РАСТЕНИЙ
# ---------------------------------
профили = {
    "Газон": 1.0,
    "Овощи": 1.2,
    "Деревья": 1.4
}

коэф = профили[тип_растения]

st.info("""
💡 Коэффициент водопотребления показывает
относительную потребность растения во влаге.

Газон = 1.0  
Овощи = 1.2  
Деревья = 1.4
""")

# ---------------------------------
# API
# ---------------------------------
OPENWEATHER_API_KEY = ""

# ---------------------------------
# КНОПКА ЗАПУСКА
# ---------------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Запустить анализ ИИ"):
    st.session_state.run = True

# ---------------------------------
# OPEN METEO
# ---------------------------------
@st.cache_data(show_spinner=False)
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7&forecast_days=7&timezone=auto"
    )
    return requests.get(url, timeout=10).json()

# ---------------------------------
# OPEN WEATHER
# ---------------------------------
def openweather(lat, lon, key):
    if not key:
        return None

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={key}&units=metric"
    )
    return requests.get(url, timeout=10).json()

# ---------------------------------
# DATAFRAME
# ---------------------------------
def df_meteo(data):
    return pd.DataFrame({
        "время": pd.to_datetime(data["hourly"]["time"]),
        "дождь": data["hourly"]["precipitation"],
        "температура": data["hourly"]["temperature_2m"]
    })

def df_owm(data):
    if not data:
        return None

    return pd.DataFrame({
        "время": pd.to_datetime([x["dt_txt"] for x in data["list"]]),
        "дождь_2": [x.get("rain", {}).get("3h", 0) for x in data["list"]],
        "температура_2": [x["main"]["temp"] for x in data["list"]]
    })

# ---------------------------------
# AI ОБЪЕДИНЕНИЕ ИСТОЧНИКОВ
# ---------------------------------
def fusion(df1, df2):
    if df2 is None:
        return df1

    df = pd.merge_asof(
        df1.sort_values("время"),
        df2.sort_values("время"),
        on="время"
    )

    w1 = 0.7
    w2 = 0.3

    df["дождь"] = df["дождь"] * w1 + df["дождь_2"].fillna(0) * w2
    df["температура"] = df["температура"] * w1 + df["температура_2"].fillna(df["температура"]) * w2

    return df

# ---------------------------------
# ИНДЕКС ЗАСУХИ
# ---------------------------------
def stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    value = 60 - rain * 4 + max(0, temp - 20) * 2
    return max(0, min(100, value))

# ---------------------------------
# AI ДОПУСТИМЫЙ ДОЖДЬ
# ---------------------------------
def ai_rain_limit(temp, stress_value):
    limit = 0.5 + stress_value * 0.01 + max(0, temp - 20) * 0.03
    return round(limit, 2)

# ---------------------------------
# ОБЪЕМ ВОДЫ
# ---------------------------------
def volume(temp, stress_value, coef):
    base = 4 + max(0, temp - 20) * 0.15 + stress_value * 0.03
    result = base * coef
    return round(min(result, 12), 1)

# ---------------------------------
# УМНЫЙ ПЛАН ПОЛИВА
# ---------------------------------
def recommend(df, tmin, banned, stress_value, coef):
    plan = []
    rain_limit = ai_rain_limit(df["температура"].mean(), stress_value)

    grouped = df.groupby(df["время"].dt.date)

    for day, day_df in grouped:
        candidates = []

        for _, row in day_df.iterrows():
            t = row["время"]

            if t.hour in banned:
                continue

            if 9 <= t.hour <= 18:
                continue

            if row["температура"] < tmin:
                continue

            if row["дождь"] > rain_limit:
                continue

            candidates.append(row)

        if not candidates:
            continue

        daily_volume = volume(day_df["температура"].mean(), stress_value, coef)

        if len(candidates) == 1:
            plan.append({
                "time": candidates[0]["время"],
                "liters": daily_volume
            })
        else:
            selected = [candidates[0], candidates[-1]]
            split_volume = round(daily_volume / 2, 1)

            for item in selected[:2]:
                plan.append({
                    "time": item["время"],
                    "liters": split_volume
                })

    return plan

# ---------------------------------
# КАРТА
# ---------------------------------
def map_view(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon]).add_to(m)
    return m

# ---------------------------------
# MAIN
# ---------------------------------
if st.session_state.run:

    df1 = df_meteo(openmeteo(широта, долгота))
    df2 = df_owm(openweather(широта, долгота, OPENWEATHER_API_KEY))
    df = fusion(df1, df2)

    s = stress(df)
    plan = recommend(df, мин_температура, запрещенные_часы, s, коэф)

    st.subheader("📍 Карта участка")
    st_folium(map_view(широта, долгота), width=700, height=400)

    st.subheader("🧠 Индекс засухи")
    st.metric("Уровень", f"{s:.1f}")

    st.subheader("📊 Погода и полив")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["время"], df["дождь"], label="Дождь")
    ax.plot(df["время"], df["температура"], label="Температура")

    for p in plan:
        lines = max(1, int(p["liters"] / 2))
        for _ in range(lines):
            ax.axvline(p["time"], linestyle="--", alpha=0.35)

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("💧 План полива")

    if plan:
        for p in plan:
            st.write(
                f"{p['time'].strftime('%d.%m %H:%M')} → {p['liters']} л/м²"
            )
    else:
        st.warning("Полив не требуется")
