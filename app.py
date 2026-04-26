import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# ---------------------------------
# НАСТРОЙКА СТРАНИЦЫ
# ---------------------------------
st.set_page_config(page_title="Умный полив ИИ", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
}

h1 { font-size: 2rem !important; font-weight: 300 !important; letter-spacing: -0.5px; }
h2, h3 { font-weight: 400 !important; font-size: 0.75rem !important;
          letter-spacing: 0.1em; text-transform: uppercase; color: #888780; }

[data-testid="metric-container"] {
    background: #f1efe8;
    border-radius: 8px;
    padding: 1rem;
}
[data-testid="metric-container"] label {
    font-size: 11px !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #888780 !important;
}
[data-testid="metric-container"] [data-testid="metric-value"] {
    font-size: 24px !important;
    font-weight: 500 !important;
}

div.stButton > button {
    width: 100%;
    background: #0F6E56;
    color: white;
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: none;
    border-radius: 8px;
    padding: 14px;
    cursor: pointer;
}
div.stButton > button:hover { background: #085041; }

.season-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: #EAF3DE;
    border: 0.5px solid #C0DD97;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 12px;
    color: #3B6D11;
}
.hour-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 4px;
    margin-top: 6px;
}
.hour-pill {
    padding: 3px 0;
    text-align: center;
    font-size: 11px;
    border-radius: 4px;
}
.hour-banned { background: #FAEEDA; color: #BA7517; border: 0.5px solid #EF9F27; }
.hour-ok     { background: #E1F5EE; color: #0F6E56; border: 0.5px solid #5DCAA5; }

.plan-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    border: 0.5px solid #D3D1C7;
    border-radius: 8px;
    margin-bottom: 6px;
    background: white;
}
.plan-time  { font-size: 13px; font-weight: 500; }
.plan-liters{ font-size: 13px; color: #0F6E56; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------
# СЕЗОННАЯ ТЕМПЕРАТУРА
# ---------------------------------
def seasonal_temp():
    m = datetime.now().month
    if m in [12, 1, 2]:  return 5,  "зима"
    if m in [3,  4, 5]:  return 8,  "весна"
    if m in [6,  7, 8]:  return 12, "лето"
    return 7, "осень"

рек_темп, сезон = seasonal_temp()

# ---------------------------------
# ЗАГОЛОВОК
# ---------------------------------
st.markdown("# 🌱 умный полив")
st.markdown(f"""
<div class="season-banner">
  <span style="width:6px;height:6px;border-radius:50%;background:#639922;display:inline-block"></span>
  {сезон}: рекомендуется {рек_темп}°C
</div>
""", unsafe_allow_html=True)

# ---------------------------------
# ВХОДНЫЕ ДАННЫЕ
# ---------------------------------
st.markdown("### координаты")
col1, col2 = st.columns(2)
with col1:
    широта = st.number_input("Широта", value=43.2389, step=0.0001, format="%.4f")
with col2:
    долгота = st.number_input("Долгота", value=76.8897, step=0.0001, format="%.4f")

st.markdown("### тип растения")
col_g, col_o, col_d = st.columns(3)
профили = {"Газон": 1.0, "Овощи": 1.3, "Деревья": 1.6}
иконки  = {"Газон": "🌿", "Овощи": "🥦", "Деревья": "🌳"}

if "plant" not in st.session_state:
    st.session_state.plant = "Газон"

for col, name in zip([col_g, col_o, col_d], ["Газон", "Овощи", "Деревья"]):
    with col:
        active = st.session_state.plant == name
        border = "border: 1.5px solid #1D9E75; background: #E1F5EE;" if active else "border: 0.5px solid #D3D1C7;"
        st.markdown(f"""
        <div style="{border} border-radius:8px; padding:12px; text-align:center; margin-bottom:4px">
          <div style="font-size:22px">{иконки[name]}</div>
          <div style="font-size:13px;font-weight:500">{name}</div>
          <div style="font-size:11px;color:#888780">k = {профили[name]}</div>
        </div>""", unsafe_allow_html=True)
        if st.button(f"Выбрать", key=f"btn_{name}"):
            st.session_state.plant = name
            st.rerun()

коэф = профили[st.session_state.plant]

st.markdown("### температура")
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    мин_температура = st.number_input(
        "Мин. температура для полива (°C)",
        value=float(рек_темп), step=1.0
    )
with col_t2:
    st.metric("Рекомендовано", f"{рек_темп} °C")

# ---------------------------------
# ЗАПРЕЩЁННЫЕ ЧАСЫ
# ---------------------------------
st.markdown("### запрещённые часы полива")
default_banned = list(range(10, 18))
запрещенные_часы = st.multiselect(
    "Выберите часы",
    options=list(range(24)),
    default=default_banned,
    format_func=lambda h: f"{h:02d}:00"
)

pills_html = '<div class="hour-grid">'
for h in range(24):
    cls = "hour-banned" if h in запрещенные_часы else "hour-ok"
    pills_html += f'<div class="hour-pill {cls}">{h:02d}</div>'
pills_html += '</div>'
st.markdown(pills_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------
# API KEY (скрыт от UI, только код)
# ---------------------------------
OPENWEATHER_API_KEY = ""

# ---------------------------------
# ЗАПУСК
# ---------------------------------
run = st.button("↯ запустить анализ ИИ")

# ---------------------------------
# API ФУНКЦИИ
# ---------------------------------
@st.cache_data(show_spinner=False)
def fetch_meteo(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7&forecast_days=7&timezone=auto"
    )
    return requests.get(url, timeout=10).json()

def fetch_owm(lat, lon, key):
    if not key:
        return None
    try:
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={key}&units=metric"
        )
        return requests.get(url, timeout=10).json()
    except Exception:
        return None

def build_df_meteo(data):
    return pd.DataFrame({
        "время": pd.to_datetime(data["hourly"]["time"]),
        "дождь": data["hourly"]["precipitation"],
        "температура": data["hourly"]["temperature_2m"]
    })

def build_df_owm(data):
    if not data or "list" not in data:
        return None
    return pd.DataFrame({
        "время": pd.to_datetime([x["dt_txt"] for x in data["list"]]),
        "дождь_2": [x.get("rain", {}).get("3h", 0) for x in data["list"]],
        "температура_2": [x["main"]["temp"] for x in data["list"]]
    })

def fusion(df1, df2):
    if df2 is None:
        return df1, "Open-Meteo"
    w1, w2 = 0.65, 0.35
    df = pd.merge_asof(
        df1.sort_values("время"),
        df2.sort_values("время"),
        on="время"
    )
    df["дождь"] = df["дождь"] * w1 + df["дождь_2"].fillna(0) * w2
    df["температура"] = df["температура"] * w1 + df["температура_2"].fillna(df["температура"]) * w2
    return df, "Open-Meteo + OWM"

def calc_stress(df):
    rain = df["дождь"].sum()
    temp = df["температура"].mean()
    return max(0, min(100, 100 - rain * 5 + (temp - 20) * 2))

def ai_rain_limit(temp, stress):
    return 0.3 + (stress / 100) * 1.2 + max(0, temp - 20) * 0.05

def calc_volume(temp, stress, coef):
    base = 5 + (temp - 20) * 0.3 + stress * 0.1
    return max(2, round(base * coef, 1))

def recommend(df, tmin, banned, stress_val, coef):
    plan = []
    daily_count = {}
    avg_temp = df["температура"].mean()
    rain_limit = ai_rain_limit(avg_temp, stress_val)
    df = df.reset_index(drop=True)

    for i in range(len(df) - 12):
        t = df.loc[i, "время"]
        day = t.date()
        if t.hour in banned:
            continue
        if 9 <= t.hour <= 18:
            continue
        if daily_count.get(day, 0) >= 2:
            continue
        rain_now  = df.loc[i, "дождь"]
        temp      = df.loc[i, "температура"]
        future    = df.loc[i:i+12, "дождь"].sum()
        if temp < tmin:
            continue
        if rain_now > rain_limit:
            continue
        if future > rain_limit * 4:
            continue
        liters = calc_volume(temp, stress_val, coef)
        if plan and plan[-1]["time"].date() == day:
            plan[-1]["liters"] += liters
        else:
            plan.append({"time": t, "liters": liters})
            daily_count[day] = daily_count.get(day, 0) + 1

    return plan

# ---------------------------------
# MAIN
# ---------------------------------
if run:
    with st.spinner("⟳ загрузка данных..."):
        raw_meteo = fetch_meteo(широта, долгота)
        raw_owm   = fetch_owm(широта, долгота, OPENWEATHER_API_KEY)

    df1 = build_df_meteo(raw_meteo)
    df2 = build_df_owm(raw_owm)
    df, source = fusion(df1, df2)

    s    = calc_stress(df)
    plan = recommend(df, мин_температура, запрещенные_часы, s, коэф)

    # --- Метрики ---
    st.markdown("### индексы")
    m1, m2, m3 = st.columns(3)
    m1.metric("Индекс засухи",   f"{s:.1f} / 100")
    m2.metric("Сеансов полива",  len(plan))
    m3.metric("Источник данных", source)

    # --- Полоса стресса ---
    st.markdown("### уровень водного стресса")
    st.progress(int(s))

    # --- График ---
    st.markdown("### прогноз осадков и температуры")
    now = datetime.now()
    window = df[
        (df["время"] >= pd.Timestamp(now) - pd.Timedelta(hours=72)) &
        (df["время"] <= pd.Timestamp(now) + pd.Timedelta(hours=72))
    ].copy()

    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_facecolor("#FAFAF8")
    ax.set_facecolor("#FAFAF8")

    ax.bar(window["время"], window["дождь"],
           width=0.03, color="#9FE1CB", alpha=0.7, label="Осадки (мм)", zorder=2)
    ax2 = ax.twinx()
    ax2.plot(window["время"], window["температура"],
             color="#1D9E75", linewidth=1.5, label="Температура (°C)", zorder=3)

    ax.axvline(now, color="#B4B2A9", linewidth=0.8, linestyle="--", zorder=1)

    for p in plan:
        if abs((p["time"] - now).total_seconds()) < 72 * 3600:
            ax.axvline(p["time"], color="#0F6E56", linewidth=1.0, alpha=0.8, zorder=4)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    plt.xticks(rotation=45, fontsize=9)
    ax.set_ylabel("Осадки (мм)", fontsize=10, color="#5DCAA5")
    ax2.set_ylabel("Температура (°C)", fontsize=10, color="#1D9E75")
    ax.tick_params(colors="#888780")
    ax2.tick_params(colors="#888780")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")

    for spine in ax.spines.values():
        spine.set_edgecolor("#D3D1C7")
    for spine in ax2.spines.values():
        spine.set_edgecolor("#D3D1C7")

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # --- План полива ---
    st.markdown("### план полива")
    if not plan:
        st.info("Полив не требуется в ближайшие дни.")
    else:
        max_l = max(p["liters"] for p in plan)
        for p in plan:
            bar_w = int((p["liters"] / max_l) * 160)
            st.markdown(f"""
            <div class="plan-row">
              <div>
                <div class="plan-time">{p['time'].strftime('%d.%m %H:%M')}</div>
                <div style="height:3px;width:{bar_w}px;background:#5DCAA5;border-radius:2px;margin-top:4px"></div>
              </div>
              <div class="plan-liters">{p['liters']:.1f} л/м²</div>
            </div>
            """, unsafe_allow_html=True)
