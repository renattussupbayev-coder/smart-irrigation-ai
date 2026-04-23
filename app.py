import streamlit as st
import requests

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


if st.button("Load Weather Data"):
    try:
        data = get_weather(lat, lon)

        st.success("Weather data loaded successfully")
        st.write(data)

    except Exception as e:
        st.error(f"Error: {e}")
