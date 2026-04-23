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

st.title("🌱 Система умного полива на основе ИИ")

# ----------------------------
# ВВОД ДАННЫХ
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
    мин_температура = st.number_input("Минимальная температура для полива (°C)", value=15.0)
    макс_дождь = st.number_input("Максимальный текущий дождь (мм)", value=0.2)
    часы_полива = st.multiselect(
        "Разрешённые часы полива",
        options=list(range(24)),
        default=[4, 5, 6, 7]
    )

# ----------------------------
# КОЭФФИЦИЕНТЫ РАСТЕНИЙ
# ----------------------------
профили = {
    "Газон": 1.0,
    "Овощи": 1.3,
    "Деревья": 1.6
}

коэф = профили[тип_растения]

st.info("""
💡 Коэффициент водопотребления — это показатель,
который показывает, сколько воды требуется растению
по сравнению с газоном (1.0).

• Газон = 1.0 (базовый уровень)
• Овощи = 1.3 (повышенная потребность)
• Деревья = 1.6 (глубокие корни)
""")

# ----------------------------
# ЗАПУСК
# ----------------------------
if "run" not in st.session_state:
    st.session_state.run = False

if st.button("Запустить анализ ИИ"):
    st.session_state.run = True

# ----------------------------
# API ПОГОДЫ
# ----------------------------
@st.cache_data(show_spinner=False)
def получить_данные(lat, lon):
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

# ----------------------------
# DATAFRAME
# ----------------------------
def построить_df(data):
    return pd.DataFrame({
        "время": pd.to_datetime(data["hourly"]["time"]),
        "дождь": data["hourly"]["precipitation"],
        "температура": data["hourly"]["temperature_2m"]
    })

# ----------------------------
# ИНДЕКС ЗАСУХИ
# ----------------------------
def индекс_засухи(df):
    дождь = df["дождь"].sum()
    температура = df["температура"].mean()
    return max(0, min(100, 100 - дождь * 5 + (температура - 20) * 2))

# ----------------------------
# ОБЪЁМ ПОЛИВА
# ----------------------------
def объём_полива(temp, stress, coef):
    базовый = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(базовый * coef, 1))

# ----------------------------
# РЕКОМЕНДАЦИИ
# ----------------------------
def рекомендации(df, t_min, rain_max, часы, stress, coef):
    res = []

    for i in range(len(df) - 12):
        t = df.loc[i, "время"]
        дождь = df.loc[i, "дождь"]
        temp = df.loc[i, "температура"]

        будущий_дождь = df.loc[i:i+12, "дождь"].sum()

        if t.hour in часы:
            if дождь <= rain_max and temp >= t_min and будущий_дождь < 2:
                литры = объём_полива(temp, stress, coef)

                res.append({
                    "время": t,
                    "литры": литры
                })

    return res

# ----------------------------
# КАРТА
# ----------------------------
def карта(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip="Участок полива").add_to(m)
    return m

# ----------------------------
# ОСНОВНОЙ БЛОК
# ----------------------------
if st.session_state.run:

    data = получить_данные(широта, долгота)
    df = построить_df(data)

    stress = индекс_засухи(df)

    план = рекомендации(
        df,
        мин_температура,
        макс_дождь,
        часы_полива,
        stress,
        коэф
    )

    # ---------------- КАРТА ----------------
    st.subheader("📍 Карта участка")
    st_folium(карта(широта, долгота), width=700, height=400, key="map")

    # ---------------- ИНДЕКС ----------------
    st.subheader("🧠 Индекс засухи")
    st.metric("Уровень (0–100)", f"{stress:.1f}")

    # ---------------- ГРАФИК ----------------
    st.subheader("📊 Погода и план полива")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df["время"], df["дождь"], label="Дождь (мм)")
    ax.plot(df["время"], df["температура"], label="Температура (°C)")

    for p in план:
        ax.axvline(p["время"], linestyle="--", alpha=0.7)

    ax.legend()
    plt.xticks(rotation=45)

    st.pyplot(fig)
    plt.close(fig)

    # ---------------- ПЛАН ПОЛИВА ----------------
    st.subheader("💧 Рекомендованный полив")

    if план:
        for p in план:
            st.write(f"🌱 {p['время'].strftime('%d.%m %H:%M')} → {p['литры']} л/м²")
    else:
        st.warning("Полив не требуется при текущих условиях")

    # ---------------- ТИП РАСТЕНИЯ ----------------
    st.subheader("🌿 Тип растения")
    st.write(f"Выбрано: **{тип_растения}**")
    st.write(f"Коэффициент водопотребления: **{коэф}**")
