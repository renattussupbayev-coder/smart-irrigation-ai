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
# СЕЗОННАЯ МИНИМАЛЬНАЯ ТЕМПЕРАТУРА
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
    temp_col1, temp_col2 = st.columns([2, 1])

    with temp_col1:
        мин_температура = st.number_input(
            "Мин. температура для полива (°C)",
            value=float(рек_темп)
        )

    with temp_col2:
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
    "Овощи": 1.3,
    "Деревья": 1.6
}

коэф = профили[тип_растения]

st.info("""
💡 Коэффициент водопотребления показывает,
сколько воды требуется растению относительно базового уровня.

Газон = 1.0  
Овощи = 1.3  
Деревья = 1.6  
""")

# ---------------------------------
# API KEY
# ---------------------------------
OPENWEATHER_API_KEY = ""

# ---------------------------------
# ЗАПУСК
# ---------------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Запустить анализ ИИ"):
    st.session_state.run = True

# ---------------------------------
# OPEN-METEO
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
# OPENWEATHER
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
# AI ВЗВЕШИВАНИЕ
# ---------------------------------
def fusion(df1, df2):
    if df2 is None:
        return df1

    w1 = 0.65
    w2 = 0.35

    df = pd.merge_asof(
        df1.sort_values("время"),
        df2.sort_values("время"),
        on="время"
    )

    df["дождь"] = df["дождь"]*w1 + df["дождь_2"].fillna(0)*w2
    df["температура"] = df["температура"]*w1 + df["температура_2"].fillna(df["температура"])*w2

    return df

# ---------------------------------
# AI ДОПУСТИМЫЙ ДОЖДЬ
# ---------------------------------
def ai_rain_limit(temp, stress):
    limit = 0.3 + (stress / 100) * 1.2 + max(0, temp - 20) * 0.05
    return round(limit, 2)

# ---------------------------------
# ИНДЕКС ЗАСУХИ
# ---------------------------------
def stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    return max(0, min(100, 100 - rain * 5 + (temp - 20) * 2))

# ---------------------------------
# ОБЪЕМ ВОДЫ
# ---------------------------------
def volume(temp, stress, coef):
    base = 4 + (temp - 20) * 0.15 + stress * 0.05
    return max(2, round(base * coef, 1))

# ---------------------------------
# ЭФФЕКТИВНОСТЬ ВОДОСБЕРЕЖЕНИЯ
# ---------------------------------
def water_saving(plan, days=14):
    standard_daily = 6  # стандартный расход воды л/м² в сутки
    standard_total = standard_daily * days

    ai_total = sum(p["liters"] for p in plan)

    saving_percent = ((standard_total - ai_total) / standard_total) * 100

    return round(max(0, saving_percent), 1), round(ai_total, 1), round(standard_total, 1)

# ---------------------------------
# УМНАЯ РЕКОМЕНДАЦИЯ
# ---------------------------------
def recommend(df, tmin, banned, stress_value, coef):
    plan = []
    daily_count = {}

    rain_limit = ai_rain_limit(df["температура"].mean(), stress_value)

    for i in range(len(df) - 12):
        t = df.loc[i, "время"]
        day = t.date()

        if t.hour in banned:
            continue

        if 9 <= t.hour <= 18:
            continue

        if daily_count.get(day, 0) >= 2:
            continue

        rain_now = df.loc[i, "дождь"]
        temp = df.loc[i, "температура"]
        future_rain = df.loc[i:i+12, "дождь"].sum()
        past_rain_12h = df.loc[i:i-12, "дождь"].sum()

        if temp < tmin:
            continue

        if rain_now > rain_limit:
            continue

        if future_rain > rain_limit * 4:
            continue

        liters = volume(temp, stress_value, coef)

        if plan and plan[-1]["time"].date() == day:
            continue

        else:
            plan.append({
                "time": t,
                "liters": liters
            })
            daily_count[day] = daily_count.get(day, 0) + 1

    return plan

# ---------------------------------
# КАРТА
# ---------------------------------
def map_view(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
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

    saving_pct, ai_water, standard_water = water_saving(plan)

    st.subheader("📍 Карта")
    st_folium(map_view(широта, долгота), width=700, height=400)

    st.subheader("Индекс засухи")
    st.metric("Уровень", f"{s:.1f}")

    st.subheader("📊 Погода и график полива")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["время"], df["дождь"], label="Дождь")
    ax.plot(df["время"], df["температура"], label="Температура")

    for p in plan:
        ax.axvline(p["time"], linestyle="--", alpha=0.7)

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("💧 План полива")

    if plan:
        for p in plan:
            st.write(
                f"{p['time'].strftime('%d.%m %H:%M')} → "
                f"{p['liters']} л/м²"
            )
    else:
        st.warning("Полив не требуется")

    st.subheader("🌍 Эффективность водосбережения")

    col_a, col_b, col_c = st.columns(3)

    col_a.metric("Экономия воды", f"{saving_pct}%")
    col_b.metric("AI расход", f"{ai_water} л/м²")
    col_c.metric("Стандартный расход", f"{standard_water} л/м²")
