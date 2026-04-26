import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

# -----------------------------------
# НАСТРОЙКА СТРАНИЦЫ
# -----------------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")
st.title("🌱 Интеллектуальная система полива")

# -----------------------------------
# ВХОДНЫЕ ДАННЫЕ
# -----------------------------------
month = datetime.now().month

def seasonal_temp(month):
    if month in [12, 1, 2]:
        return 5
    elif month in [3, 4, 5]:
        return 8
    elif month in [6, 7, 8]:
        return 12
    else:
        return 7

recommended_temp = seasonal_temp(month)

col1, col2 = st.columns(2)

with col1:
    широта = st.number_input("Широта", value=43.2389)
    долгота = st.number_input("Долгота", value=76.8897)

    тип_растения = st.selectbox(
        "Тип растения",
        ["Газон", "Овощи", "Деревья"]
    )

with col2:
    мин_температура = st.number_input(
        "Мин. температура для полива (°C)",
        value=float(recommended_temp),
        min_value=5.0
    )

    st.caption(f"Рекомендуемая для сезона: {recommended_temp} °C")

    запрещенные_часы = st.multiselect(
        "Запрещённые часы полива",
        options=list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

# -----------------------------------
# ПРОФИЛИ РАСТЕНИЙ
# -----------------------------------
профили = {
    "Газон": 1.0,
    "Овощи": 1.3,
    "Деревья": 1.6
}

коэф = профили[тип_растения]

st.info("""
Коэффициент водопотребления:
• Газон = 1.0
• Овощи = 1.3
• Деревья = 1.6
""")

OPENWEATHER_API_KEY = ""

# -----------------------------------
# API
# -----------------------------------
@st.cache_data
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

# -----------------------------------
# DATAFRAME
# -----------------------------------
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
        "дождь2": [x.get("rain", {}).get("3h", 0) for x in data["list"]],
        "температура2": [x["main"]["temp"] for x in data["list"]]
    })

# -----------------------------------
# AI WEIGHTING
# -----------------------------------
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

    df["дождь"] = df["дождь"]*w1 + df["дождь2"].fillna(0)*w2
    df["температура"] = df["температура"]*w1 + df["температура2"].fillna(df["температура"])*w2

    return df

# -----------------------------------
# ИНДЕКС ЗАСУХИ
# -----------------------------------
def stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    return max(0, min(100, 100 - rain*5 + (temp-20)*2))

# -----------------------------------
# ДОПУСТИМЫЙ ДОЖДЬ AI
# -----------------------------------
def ai_rain_threshold(stress_level):
    return max(0.3, 2.5 - stress_level/50)

# -----------------------------------
# ОБЪЕМ ВОДЫ
# -----------------------------------
def volume(temp, stress_level, coef):
    base = 5 + (temp-20)*0.3 + stress_level*0.15
    return max(5, round(base*coef,1))

# -----------------------------------
# AI RECOMMENDATION
# -----------------------------------
def recommend(df, tmin, forbidden, stress_level, coef):
    results = []
    rain_limit = ai_rain_threshold(stress_level)

    df["date"] = df["время"].dt.date

    for day in df["date"].unique():
        day_df = df[df["date"] == day].copy()

        allowed = day_df[
            (~day_df["время"].dt.hour.isin(forbidden)) &
            (day_df["температура"] >= tmin) &
            (day_df["дождь"] <= rain_limit)
        ]

        if allowed.empty:
            continue

        allowed["score"] = (
            allowed["температура"]*0.3 -
            allowed["дождь"]*3 -
            abs(allowed["время"].dt.hour-5)
        )

        top = allowed.sort_values("score", ascending=False).head(2)

        for _, row in top.iterrows():
            liters = volume(row["температура"], stress_level, coef)

            results.append({
                "time": row["время"],
                "liters": liters
            })

    return results

# -----------------------------------
# КАРТА
# -----------------------------------
def make_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon]).add_to(m)
    return m

# -----------------------------------
# BUTTON
# -----------------------------------
if st.button("Запустить анализ ИИ"):

    data1 = openmeteo(широта, долгота)
    df1 = df_meteo(data1)

    data2 = openweather(широта, долгота, OPENWEATHER_API_KEY)
    df2 = df_owm(data2)

    df = fusion(df1, df2)

    s = stress(df)

    plan = recommend(df, мин_температура, запрещенные_часы, s, коэф)

    st.subheader("📍 Карта")
    st_folium(make_map(широта, долгота), width=700, height=400)

    st.subheader("🧠 Индекс засухи")
    st.metric("Значение", f"{s:.1f}")

    # -----------------------------------
    # ГРАФИК
    # -----------------------------------
    st.subheader("📊 Погода и полив")

    fig, ax = plt.subplots(figsize=(15,6))

    ax.plot(df["время"], df["дождь"], label="Дождь")
    ax.plot(df["время"], df["температура"], label="Температура")

    for p in plan:
        duration = p["liters"] * 2
        lines_count = max(1, int(duration / 15))

        if p["liters"] < 20:
            color = "lightblue"
            width = 1
        elif p["liters"] < 40:
            color = "blue"
            width = 1.5
        else:
            color = "darkblue"
            width = 2

        for n in range(lines_count):
            offset = pd.Timedelta(minutes=n*15)
            ax.axvline(
                p["time"] + offset,
                linestyle="--",
                alpha=0.8,
                color=color,
                linewidth=width
            )

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    st.info("""
🔹 Светлая линия — низкий полив  
🔵 Синяя линия — средний полив  
🔷 Тёмная линия — интенсивный полив
""")

    # -----------------------------------
    # ПЛАН ПОЛИВА
    # -----------------------------------
    st.subheader("💧 План полива")

    if plan:
        for p in plan:
            st.write(
                f"{p['time'].strftime('%d.%m %H:%M')} → {p['liters']} л/м²"
            )
    else:
        st.warning("Полив не требуется")

    # -----------------------------------
    # ЭКОНОМИЯ
    # -----------------------------------
    baseline = 10 * 14
    ai_total = sum(p["liters"] for p in plan)
    saved = baseline - ai_total

    st.subheader("🌍 Экономия воды")
    st.metric("Сэкономлено", f"{round(saved,1)} л/м²")
