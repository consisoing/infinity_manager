import streamlit as st
from src.auth.authenticator import render_login, logout
from src.ui.admin_dashboard import render_admin
from src.ui.sales_dashboard import render_sales

# 1. Configuración de página (Debe ser lo primero)
st.set_page_config(
    page_title="Infinity Solutions Manager", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS FORZADO (ESTILO CORPORATIVO DARK MODE)
# Esto corrige el problema de Brave/Opera unificando colores
st.markdown("""
    <style>
        /* Fondo Principal */
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        /* Barras laterales */
        [data-testid="stSidebar"] {
            background-color: #161B22;
        }
        /* Inputs y Textbox */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #262730;
            color: white;
            border-color: #4B4B4C;
        }
        /* Métricas */
        [data-testid="stMetricValue"] {
            color: #00CC96 !important; /* Verde Neón para números */
        }
        [data-testid="stMetricLabel"] {
            color: #E0E0E0 !important;
        }
        /* Tablas */
        [data-testid="stDataFrame"] {
            background-color: #262730;
        }
        /* Botones Primarios */
        .stButton > button {
            background-color: #FF4B4B;
            color: white;
            border: none;
        }
        .stButton > button:hover {
            background-color: #FF2B2B;
        }
    </style>
""", unsafe_allow_html=True)

# 3. Lógica de Aplicación
def main():
    # Autenticación
    user = render_login()

    # Enrutamiento (Router)
    if user:
        # Sidebar común
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=50)
            st.title(f"📍 {user['branch']}")
            st.write(f"👤 {user['full_name']}")
            st.divider()
            if st.button("Cerrar Sesión", type="secondary"):
                logout()
                
        # Renderizar Dashboard según Rol
        if user['role'] == 'admin':
            render_admin(user)
        elif user['role'] == 'sales':
            render_sales(user)

if __name__ == "__main__":
    main()
