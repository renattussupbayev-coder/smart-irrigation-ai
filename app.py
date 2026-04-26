import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

# --------------------------------
# Настройка страницы
# --------------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")
st.title("🌱 Интеллектуальная система полива")

# --------------------------------
# Сезонная температура
# --------------------------------
def get_season_temp():
    month = datetime.now().month
    if month in [12, 1, 2]:
        return 5
    elif month in [3, 4, 5]:
        return 8
    elif month in [6, 7, 8]:
        return 12
    else:
        return 7

recommended_temp = get_season_temp()

# --------------------------------
# Интерфейс
# --------------------------------
col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("Широта", value=43.2389)
    lon = st.number_input("Долгота", value=76.8897)

    plant_type = st.selectbox(
        "Тип растения",
        ["Газон", "Овощи", "Деревья"]
    )

with col2:
    min_temp = st.number_input(
        "Минимальная температура полива (°C)",
        value=float(recommended_temp),
        min_value=5.0
    )

    st.caption(f"Рекомендуемая температура сезона: {recommended_temp} °C")

    forbidden_hours = st.multiselect(
        "Запрещённые часы полива",
        options=list(range(24)),
        default=[10,11,12,13,14,15,16,17]
    )

# --------------------------------
# Параметры растений
# --------------------------------
plant_coef = {
    "Газон": 1.0,
    "Овощи": 1.3,
    "Деревья": 1.6
}

coef = plant_coef[plant_type]

# --------------------------------
# Загрузка погоды
# --------------------------------
@st.cache_data
def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&forecast_days=7"
        "&timezone=auto"
    )

    response = requests.get(url, timeout=10)
    data = response.json()

    df = pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })

    return df

# --------------------------------
# Индекс засухи
# --------------------------------
def drought_index(df):
    rain_sum = df["rain"].sum()
    temp_avg = df["temp"].mean()

    index = 100 - rain_sum * 4 + (temp_avg - 20) * 2
    index = max(0, min(index, 100))

    return index

# --------------------------------
# Допустимый дождь AI
# --------------------------------
def rain_limit_ai(stress):
    return max(0.2, 2.5 - stress / 50)

# --------------------------------
# Объем воды
# --------------------------------
def calc_water(temp, stress, coef):
    base = 5 + (temp - 20) * 0.4 + stress * 0.12
    return round(max(5, base * coef), 1)

# --------------------------------
# Рекомендации
# --------------------------------
def recommend_irrigation(df, min_temp, forbidden_hours, stress, coef):
    result = []

    df = df.copy()
    df["date"] = df["time"].dt.date

    max_rain = rain_limit_ai(stress)

    for day in df["date"].unique():
        daily = df[df["date"] == day].copy()

        daily = daily[
            (~daily["time"].dt.hour.isin(forbidden_hours)) &
            (daily["temp"] >= min_temp) &
            (daily["rain"] <= max_rain)
        ]

        if daily.empty:
            continue

        daily["score"] = (
            -abs(daily["time"].dt.hour - 5) * 2
            + daily["temp"] * 0.3
            - daily["rain"] * 4
        )

        best = daily.sort_values("score", ascending=False).head(2)

        for _, row in best.iterrows():
            liters = calc_water(row["temp"], stress, coef)

            result.append({
                "time": row["time"],
                "liters": liters
            })

    return result

# --------------------------------
# Карта
# --------------------------------
def create_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon]).add_to(m)
    return m

# --------------------------------
# Запуск
# --------------------------------
if st.button("Запустить анализ ИИ"):

    try:
        df = get_weather(lat, lon)

        stress = drought_index(df)

        plan = recommend_irrigation(
            df,
            min_temp,
            forbidden_hours,
            stress,
            coef
        )

        st.subheader("📍 Карта")
        st_folium(create_map(lat, lon), width=700, height=400)

        st.subheader("🧠 Индекс засухи")
        st.metric("Уровень", f"{stress:.1f}")

        st.subheader("📊 График")

        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(df["time"], df["rain"], label="Дождь")
        ax.plot(df["time"], df["temp"], label="Температура")

        for p in plan:
            duration = p["liters"] * 2
            lines = max(1, int(duration / 15))

            if p["liters"] < 20:
                color = "lightblue"
                width = 1
            elif p["liters"] < 40:
                color = "blue"
                width = 1.5
            else:
                color = "darkblue"
                width = 2

            for i in range(lines):
                offset = pd.Timedelta(minutes=i * 15)
                ax.axvline(
                    p["time"] + offset,
                    linestyle="--",
                    alpha=0.7,
                    color=color,
                    linewidth=width
                )

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

        baseline = 10 * 14
        total_ai = sum(x["liters"] for x in plan)
        saved = baseline - total_ai

        st.subheader("🌍 Экономия воды")
        st.metric("Сэкономлено", f"{round(saved,1)} л/м²")

    except Exception as e:
        st.error(f"Ошибка: {e}")
