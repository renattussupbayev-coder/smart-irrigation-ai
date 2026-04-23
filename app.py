import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Smart Irrigation AI", layout="wide")

st.title("🌱 Smart Irrigation AI System")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)


def get_data(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&hourly=precipitation,temperature_2m"
        "&past_days=7"
        "&forecast_days=8"
        "&timezone=auto"
    )
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def build_df(data):
    return pd.DataFrame({
        "time": pd.to_datetime(data["hourly"]["time"]),
        "rain": data["hourly"]["precipitation"],
        "temp": data["hourly"]["temperature_2m"]
    })


if st.button("Run AI Analysis"):

    try:
        data = get_data(lat, lon)
        df = build_df(data)

        st.success("Data loaded successfully")

        # MAP
        m = folium.Map(location=[lat, lon], zoom_start=9)
        folium.Marker([lat, lon]).add_to(m)
        st_folium(m, width=700, height=400)

        # GRAPH
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df["time"], df["rain"], label="Rain (mm)")
        ax.legend()
        plt.xticks(rotation=45)

        st.pyplot(fig)
        plt.close(fig)

    except Exception as e:
        st.error(f"Error: {e}")
