import streamlit as st
import pandas as pd
import time
import re
import plotly.express as px
from datetime import datetime, timedelta

# Servicios
from src.services.data_service import (
    get_sales_data, smart_process_excel, update_sales_record, 
    delete_bulk_sales_records, delete_all_data, login_user, 
    get_branch_goal, update_branch_goal, get_inventory_match_data,
    get_all_customer_profiles, smart_import_profiles,
    delete_bulk_profiles, delete_all_profiles
)
from src.services.pdf_service import generate_pdf_report
from src.config.settings import BRANCH_CONFIG
# LÓGICA VISUAL
from src.logic.analytics import (
    generate_pareto_chart, generate_product_pie_chart, 
    generate_product_bar_chart, generate_daily_trend_chart, 
    generate_activity_charts
)

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

def render_admin(user):
    report_figures = {}

    st.title("🗺️ Centro de Comando - Infinity Solutions")
    
    with st.sidebar:
        st.header("🔍 Auditoría")
        branch_options = ["Todas"] + list(BRANCH_CONFIG.keys())
        if "Global" in branch_options: branch_options.remove("Global")
        selected_branch = st.selectbox("Sucursal:", branch_options)
        
        today = datetime.now()
        default_start = today - timedelta(days=30)
        date_range = st.date_input("Período:", value=(default_start, today), format="DD/MM/YYYY")

    if not (isinstance(date_range, tuple) and len(date_range) == 2):
        st.warning("⚠️ Selecciona fecha final.")
        return
    
    start_d, end_d = date_range
    end_d_str = f"{end_d} 23:59:59"

    base_monthly_goal = 0.0
    base_clients_goal = 0; base_meetings_goal = 0; base_products_goal = 0

    if selected_branch == "Todas":
        real_branches_list = [b for b in BRANCH_CONFIG.keys() if b != "Global"]
        for branch in real_branches_list:
            g_data = get_branch_goal(branch)
            base_monthly_goal += g_data.get('amount', 0.0)
            base_clients_goal += g_data.get('clients', 0)
            base_meetings_goal += g_data.get('meetings', 0)
            base_products_goal += g_data.get('products', 0)
    else:
        g_data = get_branch_goal(selected_branch)
        base_monthly_goal = g_data.get('amount', 0.0)
        base_clients_goal = g_data.get('clients', 0)
        base_meetings_goal = g_data.get('meetings', 0)
        base_products_goal = g_data.get('products', 0)

    days_in_period = (end_d - start_d).days + 1
    if days_in_period < 1: days_in_period = 1
    time_factor = days_in_period / 30.0 
    
    target_amount = base_monthly_goal * time_factor
    target_daily = base_monthly_goal / 30.0
    target_clients = int(base_clients_goal * time_factor)
    target_meetings = int(base_meetings_goal * time_factor)
    target_products = int(base_products_goal * time_factor)
    target_sales_ops = int((base_monthly_goal / 200) * time_factor) if base_monthly_goal > 0 else 0

    with st.spinner("🔄 Procesando datos..."):
        df = get_sales_data(user['role'], user['branch'], selected_branch, start_d, end_d_str)

    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', errors='coerce')
        df['date_only'] = df['created_at'].dt.date.fillna(datetime.now().date())
        df['description'] = df['description'].astype(str).fillna("")
        df['client_name'] = df['client_name'].apply(normalize_client_name)

    total_rev = 0.0; daily_avg = 0.0; total_clients = 0; total_meetings = 0; total_sales_ops = 0; total_products = 0
    
    if not df.empty:
        sales_df = df[df['activity_type'] == 'Venta']
        total_rev = sales_df['amount'].sum()
        daily_avg = total_rev / days_in_period
        
        valid_clients_df = sales_df[sales_df['client_name'] != 'DESCONOCIDO']
        total_clients = valid_clients_df['client_name'].nunique()
        
        meetings_df = df[df['activity_type'].str.contains("Reunión", case=False, na=False)]
        total_meetings = len(meetings_df)
        total_sales_ops = len(sales_df)
        prod_filter = df[~df['description'].str.contains("Ref:|Pedido de venta", case=False, na=False)]
        total_products = int(prod_filter['quantity'].sum())

    delta_rev = total_rev - target_amount
    delta_daily = daily_avg - target_daily
    delta_clients = total_clients - target_clients
    delta_meetings = total_meetings - target_meetings
    delta_products = total_products - target_products
    
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Facturación Total", f"${total_rev:,.2f}", f"{delta_rev:,.2f}", delta_color="normal")
    k2.metric("📅 Venta Promedio Diaria", f"${daily_avg:,.2f}", f"{delta_daily:,.2f}")
    k3.metric("👥 Clientes Activos (Ventas)", total_clients, f"{delta_clients}", delta_color="normal")
    
    k4, k5, k6 = st.columns(3)
    k4.metric("🤝 Reuniones", total_meetings, f"{delta_meetings}")
    k5.metric("🛒 Ventas Cerradas", total_sales_ops, "Transacciones", delta_color="off")
    k6.metric("📦 Productos Despachados", total_products, f"{delta_products}", delta_color="normal")
    
    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Analytics", "🆕 Cacería", "📡 Actividades", 
        "🔗 Auditoría", "📥 Carga VENTAS", "⚙️ Gestión", "📄 PDF", "📇 Carga CONTACTOS"
    ])

    with tab1:
        if df.empty: st.info("Esperando datos...")
        else:
            with st.container(border=True):
                st.subheader("🏆 Ley de Pareto")
                sales_only = df[(df['activity_type'] == 'Venta') & (df['client_name'] != 'DESCONOCIDO')]
                fig_pareto = generate_pareto_chart(sales_only)
                if fig_pareto:
                    st.plotly_chart(fig_pareto, use_container_width=True)
                    report_figures['pareto'] = fig_pareto
                else: st.caption("Sin datos de venta.")

            st.markdown("### 📦 Productos")
            
            # Función de limpieza mejorada
            def clean_prod_name(txt):
                if not isinstance(txt, str): return "Desconocido"
                txt = txt.split("| SN:")[0].split("| Estado:")[0].strip()
                if "Ref:" in txt or "Pedido de venta" in txt: 
                    return "VENTAS (Sin Detalle)"
                return txt

            df_prods = df.copy()
            df_prods['clean_name'] = df_prods['description'].apply(clean_prod_name)
            
            # --- INTERRUPTORES DE VISUALIZACIÓN ---
            c_opt1, c_opt2 = st.columns([1, 1])
            with c_opt1:
                metric_opt = st.radio("Métrica:", ["Facturación ($)", "Volumen (Unidades)"], horizontal=True)
            with c_opt2:
                show_generic = st.checkbox("Incluir 'Ventas Sin Detalle'", value=False, 
                                          help="Muestra las ventas cargadas que no especifican producto (Solo Ref de Pedido)")
                exclude_cables = False
                if metric_opt == "Volumen (Unidades)":
                    exclude_cables = st.checkbox("Excluir Cables/Fibra", value=True, 
                                                help="Oculta productos medidos en metros (Fibra, Cable)")

            # --- FILTRADO DE DATOS ---
            if not show_generic:
                df_prods = df_prods[df_prods['clean_name'] != "VENTAS (Sin Detalle)"]
            
            if exclude_cables:
                df_prods = df_prods[~df_prods['clean_name'].str.contains("FIBRA|CABLE|DROP|BOBINA", case=False, na=False)]

            if metric_opt == "Facturación ($)":
                col_val = 'amount'; data_source = df_prods[df_prods['amount'] > 0]
            else:
                col_val = 'quantity'; data_source = df_prods

            # --- GENERACIÓN DE GRÁFICOS ---
            if not data_source.empty:
                prod_stats = data_source.groupby('clean_name')[[col_val]].sum().reset_index().sort_values(by=col_val, ascending=False)
                
                # Top 10 + Otros
                if len(prod_stats) > 10:
                    top_10 = prod_stats.head(10).copy()
                    others_val = prod_stats.iloc[10:][col_val].sum()
                    others_df = pd.DataFrame([{'clean_name': 'OTROS PRODUCTOS', col_val: others_val}])
                    prod_stats_final = pd.concat([top_10, others_df])
                else:
                    prod_stats_final = prod_stats

                c_pie, c_bar = st.columns([1, 1.5])
                with c_pie:
                    fig_pie = generate_product_pie_chart(prod_stats_final, col_val, 'clean_name')
                    if fig_pie: st.plotly_chart(fig_pie, use_container_width=True); report_figures['products_pie'] = fig_pie
                with c_bar:
                    fig_bar = generate_product_bar_chart(prod_stats_final.head(10), col_val, 'clean_name', metric_opt)
                    if fig_bar: st.plotly_chart(fig_bar, use_container_width=True); report_figures['products_bar'] = fig_bar
                
                with st.expander("🔎 Ver Tabla Detallada de Productos"):
                    st.dataframe(prod_stats, use_container_width=True)
            else:
                st.warning("⚠️ No hay productos visibles con los filtros actuales.")
                st.info("💡 Consejo: Si solo cargaste el archivo 'Ventas', activa la casilla 'Incluir Ventas Sin Detalle' para ver los montos globales. Para ver productos específicos, debes cargar el archivo de Inventario.")
            
            st.divider()
            st.subheader("📈 Tendencia")
            fig_hist, avg, last = generate_daily_trend_chart(df)
            if fig_hist:
                st.plotly_chart(fig_hist, use_container_width=True)
                report_figures['history'] = fig_hist
                c_a1, c_a2 = st.columns(2)
                c_a1.info(f"Promedio: ${avg:,.2f}")
    
    with tab2:
        if not df.empty:
            new_biz = df[df['strategic_tag'].fillna('').str.contains("Cacería")]
            if not new_biz.empty:
                st.metric("Ingresos Nuevos Clientes", f"${new_biz['amount'].sum():,.2f}")
                st.dataframe(new_biz[['created_at','client_name','amount','description']], use_container_width=True, hide_index=True)
            else: st.info("Sin registros de cacería.")

    with tab3:
        if not df.empty:
            c1, c2 = st.columns([1,2])
            fig_pie_act, fig_bar_act = generate_activity_charts(df)
            with c1: 
                if fig_pie_act: st.plotly_chart(fig_pie_act, use_container_width=True); report_figures['act_pie'] = fig_pie_act
            with c2: 
                if fig_bar_act: st.plotly_chart(fig_bar_act, use_container_width=True); report_figures['act_bar'] = fig_bar_act
            st.dataframe(df[['created_at', 'activity_type', 'client_name', 'description', 'amount', 'username']], use_container_width=True)

    with tab4:
        ventas, inventario = get_inventory_match_data(start_d, end_d_str)
        if ventas.empty and inventario.empty:
            st.warning("Datos insuficientes.")
        else:
            ventas['client_name'] = ventas['client_name'].apply(normalize_client_name)
            inventario['client_name'] = inventario['client_name'].apply(normalize_client_name)
            all_clients = sorted(list(set(ventas['client_name'].unique()) | set(inventario['client_name'].unique())))
            all_clients = [c for c in all_clients if c != "DESCONOCIDO"]
            
            client_match = st.selectbox("Auditar Cliente:", all_clients)
            if client_match:
                v_cli = ventas[ventas['client_name'] == client_match]
                i_cli = inventario[inventario['client_name'] == client_match]
                c1, c2 = st.columns(2)
                c1.info(f"Facturado: ${v_cli['amount'].sum():,.2f}")
                c1.dataframe(v_cli[['created_at','description','amount']], hide_index=True)
                c2.success(f"Entregado: {int(i_cli['quantity'].sum())}")
                c2.dataframe(i_cli[['created_at','description','quantity']], hide_index=True)

    with tab5:
        st.subheader("📥 Cargar VENTAS e INVENTARIO")
        st.info("Sube aquí solo los archivos de PEDIDOS o PRODUCTOS.")
        target_opts = ["Detectar Automático"] + [b for b in BRANCH_CONFIG.keys() if b!="Global"]
        target_br = st.selectbox("Destino Venta:", target_opts)
        up_file = st.file_uploader("Archivo Excel/CSV (Ventas)", type=['xlsx','csv'], key="up_sales")
        if up_file and st.button("🚀 Procesar Ventas"):
            with st.status("Procesando...", expanded=True) as status:
                try:
                    df_up = pd.read_csv(up_file) if up_file.name.endswith('.csv') else pd.read_excel(up_file)
                    status.write("Validando archivo...")
                    branch_param = None if target_br == "Detectar Automático" else target_br
                    success, msg = smart_process_excel(df_up, branch_param)
                    if success: 
                        status.update(label="¡Listo!", state="complete", expanded=False)
                        st.balloons(); st.toast(msg, icon="✅"); time.sleep(2); st.rerun()
                    else: status.update(label="Error", state="error"); st.error(msg)
                except Exception as e: st.error(f"Error: {e}")

    with tab6:
        st.markdown("### 🎯 Metas")
        with st.form("goal_form"):
            g_branch = st.selectbox("Sucursal Meta:", [b for b in BRANCH_CONFIG.keys() if b != "Global"])
            cur = get_branch_goal(g_branch)
            c1, c2 = st.columns(2)
            nm = c1.number_input("Monto ($)", value=cur['amount'])
            nc = c1.number_input("Clientes", value=cur['clients'])
            nmeet = c2.number_input("Reuniones", value=cur['meetings'])
            nprod = c2.number_input("Productos", value=cur['products'])
            if st.form_submit_button("Guardar"):
                if update_branch_goal(g_branch, nm, nc, nmeet, nprod):
                    st.toast("Guardado", icon="💾"); time.sleep(1); st.rerun()
        st.divider()
        with st.expander("🚨 ZONA DE PELIGRO"):
            st.subheader(f"Borrar datos de: {selected_branch}")
            pwd = st.text_input("Clave Admin:", type="password")
            if st.button("BORRAR TODO"):
                if login_user(user['username'], pwd):
                    delete_all_data(selected_branch)
                    st.toast("Borrado", icon="🗑️"); time.sleep(1); st.rerun()
                else: st.error("Clave incorrecta")

    with tab7:
        if st.button("🖨️ Generar PDF", type="primary"):
            if df.empty: st.error("Sin datos.")
            else:
                cfg = {'kpi':True, 'pareto':True, 'new_biz':True, 'activities':True}
                try:
                    pdf_bytes = generate_pdf_report(df, selected_branch, start_d, end_d, cfg, report_figures)
                    st.download_button("Descargar", pdf_bytes, f"Reporte_{selected_branch}.pdf", "application/pdf")
                except Exception as e: st.error(f"Error: {e}")

    # 8. CALIDAD DE FICHAS (CRM)
    with tab8:
        st.header("🗂️ Carga de Contactos (CRM)")
        
        if st.button("🔄 Actualizar Datos (Borrar Caché)", help="Presiona esto si los datos no se actualizan"):
            st.cache_data.clear()
            st.rerun()
        
        with st.expander("📥 Subir Archivo de Contactos", expanded=True):
            c_up_1, c_up_2 = st.columns([2, 1])
            with c_up_1:
                uploaded_crm = st.file_uploader("Subir Excel de Contactos Odoo", type=["xlsx", "csv"], key="up_crm")
                if uploaded_crm:
                    st.info("El sistema solo actualizará los campos vacíos de clientes existentes.")
                    if st.button("🚀 Procesar Contactos"):
                        with st.status("Analizando...", expanded=True):
                            try:
                                df_crm = pd.read_excel(uploaded_crm) if uploaded_crm.name.endswith('.xlsx') else pd.read_csv(uploaded_crm)
                                success, msg = smart_import_profiles(df_crm, selected_branch if selected_branch != "Todas" else "Vigia")
                                if success:
                                    st.success(msg); time.sleep(2); st.rerun()
                                else: st.error(msg)
                            except Exception as e: st.error(f"Error: {e}")

        st.divider()
        profiles = get_all_customer_profiles(selected_branch)
        
        if profiles.empty:
            st.warning("No hay perfiles cargados.")
        else:
            profiles['first_seen_at'] = pd.to_datetime(profiles['first_seen_at'])
            total_p = len(profiles)
            complete_p = profiles[profiles['is_complete'] == True].shape[0]
            pct_complete = (complete_p / total_p) * 100 if total_p > 0 else 0
            
            profiles['date_no_tz'] = profiles['first_seen_at'].dt.tz_localize(None)
            start_d_ts = pd.to_datetime(start_d)
            new_this_month = profiles[profiles['date_no_tz'] >= start_d_ts].shape[0]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Fichas", f"{total_p:,.0f}")
            k2.metric("Nuevos (Este Mes)", new_this_month)
            k3.metric("Porcentaje Completado", f"{pct_complete:.1f}%")
            k4.metric("Faltan Datos", total_p - complete_p, delta_color="inverse")

            st.markdown("---")
            g_left, g_right = st.columns([2, 1])
            with g_left:
                st.subheader("📊 Crecimiento de Base de Datos")
                profiles['month_year'] = profiles['date_no_tz'].dt.to_period('M').astype(str)
                evolution = profiles.groupby('month_year').size().reset_index(name='count')
                evolution['acumulado'] = evolution['count'].cumsum()
                fig_evo = px.area(evolution, x='month_year', y='acumulado', markers=True)
                st.plotly_chart(fig_evo, use_container_width=True)

            with g_right:
                st.subheader("🔍 Estado")
                has_email = profiles[profiles['email'].notna() & (profiles['email'] != '')].shape[0]
                has_phone = profiles[profiles['phone'].notna() & (profiles['phone'] != '')].shape[0]
                c_e, c_p = st.columns(2)
                c_e.info(f"📧 {has_email}"); c_p.error(f"📞 {has_phone}")
                
                df_pie = pd.DataFrame({'Estado': ['Completo', 'Incompleto'], 'Cantidad': [complete_p, total_p - complete_p]})
                fig_quality = px.pie(df_pie, values='Cantidad', names='Estado', hole=0.6, color_discrete_sequence=['#00CC96', '#EF553B'])
                fig_quality.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig_quality, use_container_width=True)
            
            # --- SECCIÓN GEOGRAFÍA ---
            st.markdown("---")
            st.subheader("📍 Distribución Geográfica")
            
            if 'city' in profiles.columns:
                df_city = profiles.copy()
                df_city['city'] = df_city['city'].astype(str).replace(['nan', 'None', ''], 'Sin Definir')
                df_city['city'] = df_city['city'].str.title()
                
                city_counts = df_city['city'].value_counts().reset_index()
                city_counts.columns = ['Ciudad', 'Cantidad']
                
                if len(city_counts) > 15:
                    top_cities = city_counts.head(15)
                    others_sum = city_counts.iloc[15:]['Cantidad'].sum()
                    others_df = pd.DataFrame([{'Ciudad': 'Otras', 'Cantidad': others_sum}])
                    city_counts = pd.concat([top_cities, others_df])
                
                c_pie_city, c_list_city = st.columns([1.5, 1])
                with c_pie_city:
                    fig_city = px.pie(city_counts, values='Cantidad', names='Ciudad', hole=0.4, title="Clientes por Ciudad")
                    st.plotly_chart(fig_city, use_container_width=True)
                with c_list_city:
                    st.dataframe(city_counts, use_container_width=True, hide_index=True)
            else: st.info("No se encontraron datos de ciudad.")
            
            st.divider()
            with st.expander("🗑️ Gestión y Borrado de Contactos"):
                st.warning(f"Estas acciones afectan a la base de contactos de: **{selected_branch}**")
                
                tab_del_sel, tab_del_all = st.tabs(["Selección Manual", "Borrado Masivo"])
                
                with tab_del_sel:
                    if not profiles.empty:
                        df_to_edit = profiles[['id', 'name', 'email', 'phone', 'city']].copy()
                        df_to_edit.insert(0, "Borrar", False)
                        
                        edited_df = st.data_editor(
                            df_to_edit, 
                            hide_index=True,
                            column_config={"Borrar": st.column_config.CheckboxColumn(required=True)},
                            key="editor_profiles"
                        )
                        
                        to_delete_ids = edited_df[edited_df["Borrar"] == True]['id'].tolist()
                        
                        if st.button(f"🗑️ Eliminar {len(to_delete_ids)} Seleccionados"):
                            if to_delete_ids:
                                success, msg = delete_bulk_profiles(to_delete_ids)
                                if success: st.success(msg); time.sleep(1); st.rerun()
                                else: st.error(msg)
                            else: st.info("Selecciona al menos uno.")
                    else: st.info("No hay contactos para mostrar.")

                with tab_del_all:
                    st.markdown(f"#### ⚠️ ¿Estás seguro?")
                    st.markdown(f"Esto eliminará **TODOS** los {len(profiles)} contactos de {selected_branch}.")
                    pwd_del = st.text_input("Contraseña de Admin:", type="password", key="pwd_del_crm")
                    if st.button("🔥 BORRAR TODOS LOS CONTACTOS", type="primary"):
                        if login_user(user['username'], pwd_del):
                            success, msg = delete_all_profiles(selected_branch)
                            if success: st.success(msg); time.sleep(2); st.rerun()
                            else: st.error(msg)
                        else: st.error("Contraseña incorrecta.")