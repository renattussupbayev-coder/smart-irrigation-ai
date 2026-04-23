import streamlit as st
import folium
from streamlit_folium import st_folium

st.title("Map test")

lat = 43.2389
lon = 76.8897

m = folium.Map(location=[lat, lon], zoom_start=10)
folium.Marker([lat, lon], tooltip="Test point").add_to(m)

st_folium(m, width=700, height=400)
