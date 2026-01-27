import streamlit as st
import time
from src.services.data_service import login_user

def render_login():
    """Renderiza la pantalla de login y gestiona la sesión"""
    if 'user' not in st.session_state:
        st.session_state.user = None

    # Si ya está logueado, no mostrar nada (retornar usuario)
    if st.session_state.user:
        return st.session_state.user

    # Diseño del Login
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.image("assets/logo_infinity.png", width=200) # Asegúrate de tener una imagen o comenta esta línea
        st.title("Infinity Manager")
        st.markdown("### Acceso Corporativo")
        
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Bienvenido, {user['full_name']}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Credenciales inválidas o usuario inactivo")
    
    return None

def logout():
    st.session_state.user = None
    st.rerun()