import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

# ----------------------------
# НАСТРОЙКА СТРАНИЦЫ
# ----------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")

st.title("🌱 Система умного полива (AI multi-source model)")

# ----------------------------
# ВХОДНЫЕ ДАННЫЕ
# ----------------------------
col1, col2 = st.columns(2)

with col1:
    широта = st.number_input("Широта", value=43.2389)
    долгота = st.number_input("Долгота", value=76.8897)

    тип_растения = st.selectbox(
        "Тип растения",
        ["Газон", "Овощи", "Деревья"]
    )

with col2:
    мин_температура = st.number_input("Мин. температура для полива (°C)", value=15.0)
    макс_дождь = st.number_input("Макс. текущий дождь (мм)", value=0.2)
    часы_полива = st.multiselect(
        "Разрешённые часы полива",
        options=list(range(24)),
        default=[4, 5, 6, 7]
    )

# ----------------------------
# ПРОФИЛИ РАСТЕНИЙ
# ----------------------------
профили = {
    "Газон": 1.0,
    "Овощи": 1.3,
    "Деревья": 1.6
}

коэф = профили[тип_растения]

st.info("""
💡 Коэффициент водопотребления:
• Газон = 1.0  
• Овощи = 1.3  
• Деревья = 1.6  
""")

# ----------------------------
# API KEYS (опционально)
# ----------------------------
OPENWEATHER_API_KEY = ""  # вставь ключ если есть

# ----------------------------
# ЗАПУСК
# ----------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Запустить анализ ИИ"):
    st.session_state.run = True

# ----------------------------
# OPEN-METEO
# ----------------------------
@st.cache_data(show_spinner=False)
def openmeteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7&forecast_days=7&timezone=auto"
    )
    return requests.get(url, timeout=10).json()

# ----------------------------
# OPENWEATHERMAP
# ----------------------------
def openweather(lat, lon, key):
    if not key:
        return None

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={key}&units=metric"
    )
    return requests.get(url, timeout=10).json()

# ----------------------------
# DATA PREP
# ----------------------------
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

# ----------------------------
# AI WEIGHTED FUSION
# ----------------------------
def fusion(df1, df2):
    w1 = 0.65
    w2 = 0.35

    if df2 is None:
        return df1

    df = pd.merge_asof(
        df1.sort_values("время"),
        df2.sort_values("время"),
        on="время"
    )

    df["дождь"] = df["дождь"] * w1 + df["дождь_2"].fillna(df["дождь"]) * w2
    df["температура"] = df["температура"] * w1 + df["температура_2"].fillna(df["температура"]) * w2

    return df

# ----------------------------
# ИНДЕКС ЗАСУХИ
# ----------------------------
def stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    return max(0, min(100, 100 - rain * 5 + (temp - 20) * 2))

# ----------------------------
# ОБЪЁМ ПОЛИВА
# ----------------------------
def volume(temp, stress, coef):
    base = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(base * coef, 1))

# ----------------------------
# РЕКОМЕНДАЦИИ
# ----------------------------
def recommend(df, tmin, rmax, hours, stress, coef):
    out = []

    for i in range(len(df) - 12):
        t = df.loc[i, "время"]
        r = df.loc[i, "дождь"]
        temp = df.loc[i, "температура"]
        future_r = df.loc[i:i+12, "дождь"].sum()

        if t.hour in hours:
            if r <= rmax and temp >= tmin and future_r < 2:
                out.append({
                    "time": t,
                    "liters": volume(temp, stress, coef)
                })

    return out

# ----------------------------
# КАРТА
# ----------------------------
def map_view(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon]).add_to(m)
    return m

# ----------------------------
# MAIN
# ----------------------------
if st.session_state.run:

    meteo = openmeteo(широта, долгота)
    df1 = df_meteo(meteo)

    owm = openweather(широта, долгота, OPENWEATHER_API_KEY)
    df2 = df_owm(owm)

    df = fusion(df1, df2)

    s = stress(df)

    plan = recommend(df, мин_температура, макс_дождь, часы_полива, s, коэф)

    # ---------------- MAP ----------------
    st.subheader("📍 Карта")
    st_folium(map_view(широта, долгота), width=700, height=400, key="map")

    # ---------------- STRESS ----------------
    st.subheader("🧠 Индекс засухи")
    st.metric("Уровень", f"{s:.1f}")

    # ---------------- GRAPH ----------------
    st.subheader("📊 Погода и полив")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["время"], df["дождь"], label="Дождь")
    ax.plot(df["время"], df["температура"], label="Температура")

    for p in plan:
        ax.axvline(p["time"], linestyle="--", alpha=0.7)

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    # ---------------- PLAN ----------------
    st.subheader("💧 План полива")

    if plan:
        for p in plan:
            st.write(f"🌱 {p['time'].strftime('%d.%m %H:%M')} → {p['liters']} л/м²")
    else:
        st.warning("Полив не требуется")

    # ---------------- SAVINGS ----------------
    st.subheader("🌍 Экономия воды")

    baseline = 10 * 14
    ai = sum(p["liters"] for p in plan)
    saved = baseline - ai

    st.metric("Сэкономлено воды", f"{round(saved,1)} л/м²")
