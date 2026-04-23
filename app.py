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
    df = pd.DataFrame({
        "datetime": pd.to_datetime(data["hourly"]["time"]),
        "precipitation_mm": data["hourly"]["precipitation"]
    })

    return df


def recommend_irrigation(df):
    irrigation_times = []

    for _, row in df.iterrows():
        hour = row["datetime"].hour
        rain = row["precipitation_mm"]

        if rain == 0 and hour in [5, 6, 7]:
            irrigation_times.append(row["datetime"])

    return irrigation_times


def calculate_stress(df):
    total_rain = df["precipitation_mm"].sum()
    dry_hours = len(df[df["precipitation_mm"] == 0])

    score = 100 - (total_rain * 10) + (dry_hours * 0.5)

    return max(0, min(100, score))


def plot_rain(df, irrigation_times):
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(df["datetime"], df["precipitation_mm"], label="Precipitation (mm)")

    for t in irrigation_times:
        ax.axvline(t, linestyle="--", alpha=0.6)

    ax.set_xlabel("Date / Time")
    ax.set_ylabel("Precipitation (mm)")
    ax.set_title("Precipitation and Recommended Irrigation")
    ax.legend()

    plt.xticks(rotation=45)

    return fig


def show_map(lat, lon):
    m = folium.Map(location=[lat, lon], zoom_start=11)
    folium.Marker(
        [lat, lon],
        tooltip="Irrigation Site"
    ).add_to(m)

    return m


if st.button("Load Weather Data"):
    try:
        data = get_weather(lat, lon)
        df = build_dataframe(data)
        irrigation_times = recommend_irrigation(df)
        stress = calculate_stress(df)

        st.success("Weather data loaded successfully")

        # MAP
        st.subheader("Location")
        map_object = show_map(lat, lon)
        st_folium(map_object, width=700, height=400)

        # INDEX
        st.subheader("Water Stress Index")
        st.metric("Stress Score", f"{stress:.1f}/100")

        # GRAPH
        fig = plot_rain(df, irrigation_times)
        st.pyplot(fig)
        plt.close(fig)

        # SCHEDULE
        st.subheader("Recommended Irrigation Times")

        if irrigation_times:
            for t in irrigation_times:
                st.write(t)
        else:
            st.write("No irrigation recommended")

    except Exception as e:
        st.error(f"Error: {e}")
