import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime

# Servicios
from src.services.data_service import (
    log_activity, get_sales_data, get_branch_goal, 
    update_own_record, verify_user_password, delete_sales_record
)
from src.services.pdf_service import generate_pdf_report
from src.config.settings import BRANCH_CONFIG
# LÓGICA VISUAL
from src.logic.analytics import (
    generate_pareto_chart, generate_product_pie_chart, 
    generate_product_bar_chart, generate_daily_trend_chart, 
    generate_activity_charts
)

# FUNCIÓN DE LIMPIEZA DE CLIENTES
def normalize_client_name(text):
    if not isinstance(text, str): return "DESCONOCIDO"
    text = text.upper()
    replacements = (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N"))
    for a, b in replacements:
        text = text.replace(a, b)
    text = re.sub(r'[^A-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    blacklist = ["STOCK", "ALMACEN", "INVENTARIO", "AJUSTE", "DESCONOCIDO", "CARGA MASIVA", "ADMIN", "NAN", "NONE"]
    for bad_word in blacklist:
        if bad_word in text: return "DESCONOCIDO"
    if len(text) < 2: return "DESCONOCIDO"
    return text

# FUNCIÓN DE LIMPIEZA DE PRODUCTOS
def clean_prod_name(txt):
    if not isinstance(txt, str): return "Desconocido"
    txt = txt.split("| SN:")[0].split("| Estado:")[0].strip()
    if "Ref:" in txt or "Pedido de venta" in txt: 
        return "VENTAS (Sin Detalle)"
    return txt

def render_sales(user):
    report_figures = {}
    branch_key = user['branch']
    branch_info = BRANCH_CONFIG.get(branch_key, {})
    branch_name = branch_info.get('name', branch_key)
    
    st.title(f"🚀 Panel Operativo: {branch_name}")
    st.caption(f"Bienvenido, {user['full_name']} | Cazador de Negocios")

    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("### 📅 Tiempo")
    today = datetime.now()
    default_start = today.replace(day=1)
    date_range = st.sidebar.date_input("Rango", value=(default_start, today), format="DD/MM/YYYY")
    
    if not (isinstance(date_range, tuple) and len(date_range) == 2):
        st.sidebar.warning("Selecciona fecha fin.")
        return

    start_d, end_d = date_range
    end_d_str = f"{end_d} 23:59:59"

    with st.spinner("Cargando tu actividad..."):
        # Se obtienen TODOS los datos de la sucursal (gracias a la corrección de data_service)
        df = get_sales_data('sales', branch_key, start_date=start_d, end_date=end_d_str)

    existing_clients = []
    
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', errors='coerce')
        df['date_only'] = df['created_at'].dt.date.fillna(datetime.now().date())
        df['description'] = df['description'].astype(str).fillna("")
        
        # NORMALIZACIÓN
        df['client_name'] = df['client_name'].apply(normalize_client_name)
        df['clean_prod'] = df['description'].apply(clean_prod_name)
        
        raw_clients = df['client_name'].unique().tolist()
        existing_clients = sorted([c for c in raw_clients if c != "DESCONOCIDO"])

    goals = get_branch_goal(branch_key)
    days_in_period = (end_d - start_d).days + 1
    if days_in_period < 1: days_in_period = 1
    time_factor = days_in_period / 30.0

    target_amount = goals['amount'] * time_factor
    target_clients = int(goals['clients'] * time_factor)
    target_meetings = int(goals['meetings'] * time_factor)
    target_products = int(goals['products'] * time_factor)

    real_rev = 0.0; real_clients = 0; real_meetings = 0; real_products = 0; pipeline = 0.0
    
    if not df.empty:
        sales_df = df[df['activity_type'] == 'Venta']
        real_rev = sales_df['amount'].sum()
        
        # Clientes Únicos (Solo Ventas)
        valid_clients_df = sales_df[sales_df['client_name'] != 'DESCONOCIDO']
        real_clients = valid_clients_df['client_name'].nunique()
        
        real_meetings = len(df[df['activity_type'].str.contains("Reunión", case=False, na=False)])
        
        # Productos (Sin referencia financiera)
        prod_rows = df[~df['clean_prod'].str.contains("VENTAS", case=False, na=False)]
        real_products = int(prod_rows['quantity'].sum())
        
        pipeline = df[df['activity_type'].str.contains("Oportunidad", case=False, na=False)]['amount'].sum()

    # Cálculo de Deltas
    delta_rev = real_rev - target_amount
    delta_clients = real_clients - target_clients
    delta_meetings = real_meetings - target_meetings
    delta_products = real_products - target_products
    
    # --- LAYOUT IDENTICO AL ADMIN (2 FILAS) ---
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Facturación", f"${real_rev:,.2f}", f"{delta_rev:,.2f} vs Meta", delta_color="normal")
    k2.metric("📅 Pipeline Activo", f"${pipeline:,.2f}")
    k3.metric("👥 Clientes (Ventas)", real_clients, f"{delta_clients} vs Meta ({target_clients})")
    
    k4, k5, k6 = st.columns(3)
    k4.metric("🤝 Reuniones", real_meetings, f"{delta_meetings}")
    k5.metric("🛒 Ventas Cerradas", len(df[df['activity_type']=='Venta']) if not df.empty else 0, "Transacciones")
    k6.metric("📦 Productos", real_products, f"{delta_products} vs Meta ({target_products})")

    if goals['amount'] > 0:
        prog_pct = min(real_rev / goals['amount'], 1.0)
        st.progress(prog_pct, text=f"Progreso Mensual: {prog_pct*100:.1f}%")

    st.divider()

    t_reg, t_stats, t_edit, t_pdf = st.tabs(["📝 Registrar", "📊 Estadísticas", "🛠️ Corregir", "📄 Reporte"])

    # ---------------- TAB REGISTRO ----------------
    with t_reg:
        c_left, c_right = st.columns([1, 1])
        with c_left:
            with st.container(border=True):
                st.subheader("Nueva Actividad")
                with st.form("sales_activity_form"):
                    act_type = st.selectbox("Tipo", ["Reunión Presencial", "Reunión Virtual", "Capacitación Técnica", "Oportunidad de Proyecto"])
                    client_options = ["➕ Nuevo Cliente..."] + existing_clients
                    selected_client_opt = st.selectbox("Cliente", client_options)
                    
                    new_client_input = ""
                    if selected_client_opt == "➕ Nuevo Cliente...":
                        new_client_input = st.text_input("Nombre Nuevo:", placeholder="Ej. Procesadora Tío Pollo")
                    
                    amount = 0.0; quantity = 1; notes = ""
                    if "Reunión" in act_type: notes = st.text_area("Resumen", placeholder="Acuerdos...")
                    elif "Capacitación" in act_type:
                        quantity = st.number_input("Asistentes", 1, 100, 5)
                        notes = st.text_area("Tema", placeholder="Fusión...")
                    elif "Oportunidad" in act_type:
                        amount = st.number_input("Valor Estimado ($)", 0.0)
                        notes = st.text_area("Detalles", placeholder="Descripción...")
                    
                    st.markdown("---")
                    tag = st.radio("Estrategia", ["Mantenimiento", "Cacería", "Recuperación"], horizontal=True)
                    
                    if st.form_submit_button("💾 Registrar", type="primary"):
                        if selected_client_opt == "➕ Nuevo Cliente...":
                            final_client_name = normalize_client_name(new_client_input)
                        else:
                            final_client_name = selected_client_opt

                        if final_client_name and final_client_name != "DESCONOCIDO":
                            log_activity(user['username'], branch_key, final_client_name, amount, notes, act_type, tag, quantity)
                            st.toast(f"Registrado: {final_client_name}", icon="✅"); time.sleep(1); st.rerun()
                        else: st.error("Nombre inválido.")

        with c_right:
            st.subheader("⏱️ Bitácora Reciente")
            if not df.empty:
                df['info'] = df.apply(lambda x: f"${x['amount']:,.2f}" if "Oportunidad" in str(x['activity_type']) else str(x['description'])[:40], axis=1)
                st.dataframe(df[['created_at', 'activity_type', 'client_name', 'info']].head(10), hide_index=True, use_container_width=True)
            else: st.info("Sin registros recientes.")

    # ---------------- TAB ESTADÍSTICAS (IGUAL AL ADMIN) ----------------
    with t_stats:
        if df.empty: st.warning("Sin datos.")
        else:
            c1, c2 = st.columns([1.2, 1.5])
            with c1:
                st.markdown("#### 🏆 Mejores Clientes")
                sales_only = df[(df['activity_type'] == 'Venta') & (df['client_name'] != 'DESCONOCIDO')]
                fig_p = generate_pareto_chart(sales_only)
                if fig_p: 
                    st.plotly_chart(fig_p, use_container_width=True)
                    report_figures['pareto'] = fig_p
                else: st.caption("Sin ventas.")

            with c2:
                st.markdown("#### 📦 Productos")
                
                # --- FILTRO INTELIGENTE ---
                col_opts = st.columns(2)
                metric_opt = col_opts[0].radio("Ver por:", ["Dinero ($)", "Cantidad"], horizontal=True)
                
                exclude_cables = False
                if metric_opt == "Cantidad":
                    exclude_cables = col_opts[1].checkbox("Excluir Cables/Fibra", value=True)

                df_prods = df.copy()
                if exclude_cables:
                    df_prods = df_prods[~df_prods['clean_prod'].str.contains("FIBRA|CABLE|DROP|BOBINA", case=False, na=False)]
                
                df_prods = df_prods[df_prods['clean_prod'] != "VENTAS (Sin Detalle)"]

                col_val = 'amount' if metric_opt == "Dinero ($)" else 'quantity'
                
                if metric_opt == "Dinero ($)":
                    df_prods = df_prods[df_prods['amount'] > 0]

                if not df_prods.empty:
                    stats = df_prods.groupby('clean_prod')[[col_val]].sum().reset_index().sort_values(by=col_val, ascending=False)
                    
                    if len(stats) > 10:
                        top_10 = stats.head(10).copy()
                        others_val = stats.iloc[10:][col_val].sum()
                        others_df = pd.DataFrame([{'clean_prod': 'OTROS PRODUCTOS', col_val: others_val}])
                        stats_final = pd.concat([top_10, others_df])
                    else:
                        stats_final = stats

                    f_pie = generate_product_pie_chart(stats_final, col_val, 'clean_prod')
                    if f_pie: 
                        st.plotly_chart(f_pie, use_container_width=True)
                        report_figures['products_pie'] = f_pie
                    
                    f_bar = generate_product_bar_chart(stats_final.head(10), col_val, 'clean_prod', metric_opt)
                    if f_bar: st.plotly_chart(f_bar, use_container_width=True)
                    
                    with st.expander("Ver tabla detallada"):
                        st.dataframe(stats, use_container_width=True)
                else: 
                    st.info("Sin datos de productos detallados.")

            st.divider()
            st.markdown("#### 📈 Actividad Diaria")
            _, f_bar_act = generate_activity_charts(df)
            if f_bar_act: 
                st.plotly_chart(f_bar_act, use_container_width=True)
                report_figures['act_bar'] = f_bar_act

    # ---------------- TAB CORREGIR (SOLUCIÓN KEYERROR) ----------------
    with t_edit:
        st.subheader("🛠️ Editar Mis Registros")
        
        # Filtro seguro: Solo si el usuario existe en el DataFrame
        if not df.empty and 'username' in df.columns:
            my_recs = df[df['username'] == user['username']].copy()
        else:
            my_recs = pd.DataFrame()
            
        if not my_recs.empty:
            search = st.text_input("🔍 Buscar:", "")
            if search:
                my_recs = my_recs[my_recs['client_name'].str.contains(search, case=False) | my_recs['activity_type'].str.contains(search, case=False)]
            sel = st.dataframe(my_recs[['created_at', 'client_name', 'activity_type', 'amount', 'id']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel.selection.rows:
                row = my_recs.iloc[sel.selection.rows[0]]
                st.divider()
                st.markdown(f"**Editando:** {row['client_name']}")
                with st.form("edit_row"):
                    nc = st.text_input("Cliente", value=row['client_name'])
                    # Evitar error si description no existe
                    desc_val = row['description'] if 'description' in row else ""
                    nd = st.text_input("Descripción", value=desc_val)
                    nm = st.number_input("Monto", value=float(row['amount']))
                    pw = st.text_input("Tu Contraseña:", type="password")
                    c_b1, c_b2 = st.columns(2)
                    if c_b1.form_submit_button("🔄 Actualizar"):
                        if verify_user_password(user['username'], pw):
                            update_own_record(row['id'], {"client_name":normalize_client_name(nc), "amount":nm, "description":nd})
                            st.toast("Actualizado", icon="✅"); time.sleep(1); st.rerun()
                        else: st.error("Clave incorrecta")
                    if c_b2.form_submit_button("🗑️ Eliminar"):
                        if verify_user_password(user['username'], pw):
                            delete_sales_record(row['id'])
                            st.toast("Eliminado", icon="🗑️"); time.sleep(1); st.rerun()
                        else: st.error("Clave incorrecta")
        else: st.info("No tienes registros propios para editar.")

    # ---------------- TAB PDF ----------------
    with t_pdf:
        st.subheader("📄 Mi Reporte")
        if st.button("🖨️ Generar PDF", type="primary"):
            if df.empty: st.error("Sin datos.")
            else:
                cfg = {'kpi':True, 'pareto':True, 'new_biz':True, 'activities':True}
                try:
                    pdf_bytes = generate_pdf_report(df, branch_name, start_d, end_d, cfg, report_figures)
                    st.download_button("Descargar", pdf_bytes, f"Reporte_{branch_key}.pdf", "application/pdf")
                except Exception as e: st.error(f"Error: {e}")