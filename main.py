import streamlit as st
from src.auth.authenticator import render_login, logout
from src.ui.admin_dashboard import render_admin
from src.ui.sales_dashboard import render_sales

# 1. Configuración de página
st.set_page_config(
    page_title="Infinity Solutions Manager", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS FORZADO (TEMA CLARO / LIGHT MODE)
st.markdown("""
    <style>
        /* Fondo Principal */
        .stApp {
            background-color: #FFFFFF;
            color: #31333F;
        }
        
        /* Barras laterales */
        [data-testid="stSidebar"] {
            background-color: #F8F9FB;
            border-right: 1px solid #E0E0E0;
        }
        
        /* Encabezados */
        h1, h2, h3 {
            color: #0E1117 !important;
        }
        
        /* Inputs y Selectbox */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #FFFFFF;
            color: #31333F;
            border: 1px solid #D6D6D6;
        }
        
        /* Métricas (KPIs) */
        [data-testid="stMetricValue"] {
            color: #FF5722 !important; /* Naranja Infinity */
            font-weight: bold;
        }
        [data-testid="stMetricLabel"] {
            color: #555555 !important;
        }
        
        /* Contenedores y Tarjetas */
        [data-testid="stForm"] {
            background-color: #F8F9FB;
            border: 1px solid #E0E0E0;
            padding: 20px;
            border-radius: 10px;
        }
        
        /* Botones Primarios */
        .stButton > button {
            background-color: #FF5722;
            color: white;
            border: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .stButton > button:hover {
            background-color: #E64A19;
            color: white;
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
            # Logo (puedes poner tu URL real aquí)
            st.markdown("## ♾️ Infinity Manager") 
            st.caption(f"📍 Sucursal: {user['branch']}")
            st.write(f"👤 **{user['full_name']}**")
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