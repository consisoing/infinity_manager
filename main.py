import streamlit as st
from src.auth.authenticator import render_login, logout
# --- ESTAS SON LAS LÍNEAS QUE FALTABAN ---
from src.ui.admin_dashboard import render_admin
from src.ui.sales_dashboard import render_sales
# -----------------------------------------

# Configuración de página
st.set_page_config(page_title="Infinity Solutions Manager", page_icon="🚀", layout="wide")

# Cargar CSS
try:
    with open('assets/style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    pass # Si no existe el CSS aún, no pasa nada

# 1. Autenticación
user = render_login()

# 2. Enrutamiento (Router)
if user:
    # Sidebar común
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=50) # Icono genérico temporal
        st.title(f"📍 {user['branch']}")
        st.write(f"👤 {user['full_name']}")
        st.divider()
        if st.button("Cerrar Sesión", type="primary"):
            logout()
            
    # Lógica de Vistas (Aquí es donde daba el error antes)
    if user['role'] == 'admin':
        render_admin(user) # Ahora sí llama a la función importada
        
    elif user['role'] == 'sales':
        render_sales(user) # Ahora sí llama a la función importada