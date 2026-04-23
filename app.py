import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

st.title("Smart Irrigation MVP")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)


def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&hourly=precipitation"
        "&past_days=2"
        "&forecast_days=2"
        "&timezone=auto"
    )
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def build_dataframe(data):
    return pd.DataFrame({
        "datetime": pd.to_datetime(data["hourly"]["time"]),
        "precipitation_mm": data["hourly"]["precipitation"]
    })


def show_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=10)
    folium.Marker([lat, lon], tooltip="Irrigation Site").add_to(m)
    return m


def plot_rain(df):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["datetime"], df["precipitation_mm"])
    plt.xticks(rotation=45)
    return fig


if st.button("Load Weather Data"):
    try:
        data = get_weather(lat, lon)
        df = build_dataframe(data)

        st.subheader("Map")
        m = show_map(lat, lon)
        st_folium(m, width=700, height=400)

        st.subheader("Rainfall")
        fig = plot_rain(df)
        st.pyplot(fig)
        plt.close(fig)

    except Exception as e:
        st.error(f"Error: {e}")
