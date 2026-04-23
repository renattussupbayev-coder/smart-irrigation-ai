import streamlit as st

st.title("Smart Irrigation DEBUG TEST")

# 👉 Проверка запуска скрипта
st.write("DEBUG: script is running")

lat = st.number_input("Latitude", value=43.2389)
lon = st.number_input("Longitude", value=76.8897)

# 👉 Кнопка
if st.button("Run AI Analysis"):
    st.write("DEBUG: button clicked")
