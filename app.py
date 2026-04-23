import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

st.title("Smart Irrigation TEST")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)


def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation"
        "&past_days=1"
        "&forecast_days=1"
        "&timezone=auto"
    )
    return requests.get(url).json()


if st.button("Run"):
    try:
        data = get_weather(lat, lon)

        df = pd.DataFrame({
            "time": data["hourly"]["time"],
            "rain": data["hourly"]["precipitation"]
        })

        st.write(df)

        m = folium.Map(location=[lat, lon], zoom_start=10)
        folium.Marker([lat, lon]).add_to(m)
        st_folium(m)

    except Exception as e:
        st.error(e)
