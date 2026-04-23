import streamlit as st

st.title("Smart Irrigation MVP")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

st.write("Selected coordinates:")
st.write("Latitude:", lat)
st.write("Longitude:", lon)
