import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
from datetime import datetime

# ---------------------------------
# THEME (CSS DESIGN ONLY)
# ---------------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")

st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }

    h1 {
        color: #7CFF6B;
        font-weight: 700;
    }

    .stMetric {
        background: #161b22;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #2c313c;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .stButton button {
        background: linear-gradient(90deg, #00C853, #64DD17);
        color: black;
        font-weight: 700;
        border-radius: 10px;
        padding: 0.6rem 1rem;
        border: none;
    }

    .stButton button:hover {
        transform: scale(1.02);
        transition: 0.2s;
    }

    .css-1d391kg {
        background-color: #161b22;
        border-radius: 12px;
        padding: 10px;
    }

    .stDataFrame {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------
# TITLE
# ---------------------------------
st.title("🌱 Система умного полива (AI multi-source model)")

# ---------------------------------
# SEASON TEMP
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
# INPUTS (CARDS STYLE)
# ---------------------------------
st.markdown("## 📍 Параметры")

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
# PLANT PROFILE
# ---------------------------------
профили = {
    "Газон": 1.0,
    "Овощи": 1.3,
    "Деревья": 1.6
}

коэф = профили[тип_растения]

st.info("💡 Коэффициент водопотребления: Газон 1.0 | Овощи 1.3 | Деревья 1.6")

# ---------------------------------
# API KEY
# ---------------------------------
OPENWEATHER_API_KEY = ""

# ---------------------------------
# RUN STATE
# ---------------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("🚀 Запустить анализ ИИ"):
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
# FUSION
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
# FUNCTIONS (UNCHANGED)
# ---------------------------------
def ai_rain_limit(temp, stress):
    return round(0.3 + (stress / 100) * 1.2 + max(0, temp - 20) * 0.05, 2)

def stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    return max(0, min(100, 100 - rain * 5 + (temp - 20) * 2))

def volume(temp, stress, coef):
    base = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(base * coef, 1))

# ---------------------------------
# RECOMMEND (UNCHANGED)
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

        if temp < tmin:
            continue

        if rain_now > rain_limit:
            continue

        if future_rain > rain_limit * 4:
            continue

        liters = volume(temp, stress_value, coef)

        if plan and plan[-1]["time"].date() == day:
            plan[-1]["liters"] += liters
        else:
            plan.append({"time": t, "liters": liters})
            daily_count[day] = daily_count.get(day, 0) + 1

    return plan

# ---------------------------------
# MAP STYLE WRAPPER
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

    # DASHBOARD LAYOUT
    st.markdown("## 📊 Dashboard")

    c1, c2 = st.columns([1,1])

    with c1:
        st.subheader("📍 Карта")
        st_folium(map_view(широта, долгота), width=500, height=350)

    with c2:
        st.subheader("🌡 Индекс засухи")
        st.metric("Уровень", f"{s:.1f}")

        st.subheader("💧 План")
        if plan:
            for p in plan[:5]:
                st.write(f"{p['time'].strftime('%d.%m %H:%M')} → {p['liters']} л/м²")
        else:
            st.success("Полив не требуется")

    # CHART
    st.markdown("## 📈 Аналитика")

    fig, ax = plt.subplots(figsize=(14,5))
    ax.plot(df["время"], df["дождь"], label="Дождь")
    ax.plot(df["время"], df["температура"], label="Температура")

    for p in plan:
        ax.axvline(p["time"], linestyle="--", alpha=0.3)

    ax.legend()
    st.pyplot(fig)
    plt.close(fig)
