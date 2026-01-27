# src/config/connection.py
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_connection() -> Client:
    try:
        # Streamlit busca automáticamente en .streamlit/secrets.toml
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Error de Conexión: Verifica tu archivo .streamlit/secrets.toml. Detalle: {e}")
        return None