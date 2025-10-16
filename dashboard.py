import streamlit as st
import pandas as pd
import requests
import altair as alt
import uvicorn
import threading
import os
import time
from main import app  # Importa la app FastAPI desde tu archivo main.py

# --- CONFIGURACIÓN PARA CORRER FASTAPI Y STREAMLIT JUNTOS ---
# Usamos un 'lock' para asegurarnos de que la API se inicie solo una vez.
if "api_thread_started" not in st.session_state:
    st.session_state.api_thread_started = threading.Lock()

def run_api():
    """Función que inicia el servidor de la API."""
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level="info")

# Inicia la API en un hilo secundario la primera vez que se carga la página.
with st.session_state.api_thread_started:
    if "api_thread" not in st.session_state:
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        st.session_state.api_thread = api_thread
        time.sleep(2) # Damos un par de segundos para que la API se levante

# URL de la API (está corriendo en el mismo contenedor/máquina)
API_URL = "http://localhost:8000/api"

# --- INICIO DE LA APP DE STREAMLIT ---
st.set_page_config(page_title="Dashboard de Farmacia", layout="wide")
st.title("📊 Dashboard de Ventas - Farmacia Inteligente")

@st.cache_data(ttl=60)  # La data se refrescará cada 60 segundos
def cargar_ventas():
    """Carga los datos de ventas desde la API."""
    try:
        response = requests.get(f"{API_URL}/ventas")
        response.raise_for_status()  # Lanza un error si la respuesta es mala (ej. 404, 500)
        data = response.json()
        df = pd.DataFrame(data)
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"No se pudo conectar a la API. Asegúrate de que está corriendo. Error: {e}")
        return pd.DataFrame()

# Carga los datos
df_ventas = cargar_ventas()

if df_ventas.empty:
    st.warning("No hay datos de ventas para mostrar o la API no está respondiendo.")
    st.info("Reintentando en 60 segundos...")
else:
    st.subheader("Ventas Recientes")
    st.dataframe(df_ventas)

    st.subheader("Ventas Diarias")
    ventas_diarias = df_ventas.groupby(df_ventas['fecha'].dt.date)['subtotal'].sum().reset_index()
    chart_ventas = alt.Chart(ventas_diarias).mark_line(point=True).encode(
        x=alt.X('fecha:T', title='Fecha'),
        y=alt.Y('subtotal:Q', title='Total Ventas (S/.)', axis=alt.Axis(format='$,.2f'))
    ).interactive()
    st.altair_chart(chart_ventas, use_container_width=True)